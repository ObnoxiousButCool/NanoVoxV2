"""Logging is controlled by a flag (D5), and switching it off must leave no trace on disk."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from domain.errors import ConfigurationError
from infrastructure.config.settings import Settings
from infrastructure.logging.correlation import reset_correlation_id, set_correlation_id
from infrastructure.logging.llm_audit import LLM_AUDIT_LOGGER_NAME, LlmAuditLog
from infrastructure.logging.setup import (
    ACCESS_LOGGER_NAME,
    APP_LOG_FILENAME,
    LLM_AUDIT_LOG_FILENAME,
    configure_logging,
    shutdown_logging,
)
from tests.support.settings import make_settings


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    yield
    shutdown_logging()


def _settings(log_dir: Path, *, enabled: bool) -> Settings:
    return make_settings(
        log_enabled=enabled,
        log_to_console=False,
        log_dir=log_dir,
        log_format="json",
    )


def test_disabled_logging_writes_no_files(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"

    configure_logging(_settings(log_dir, enabled=False))
    logging.getLogger("nanovox.test").error("this must not be written anywhere")

    assert not log_dir.exists()


def test_disabled_logging_attaches_only_a_null_handler(tmp_path: Path) -> None:
    configure_logging(_settings(tmp_path / "logs", enabled=False))

    handlers = logging.getLogger().handlers
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.NullHandler)


def test_enabled_logging_writes_json_with_the_correlation_id(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    configure_logging(_settings(log_dir, enabled=True))

    token = set_correlation_id("abc123")
    try:
        logging.getLogger("nanovox.test").warning("hello", extra={"widget": 7})
    finally:
        reset_correlation_id(token)
    logging.shutdown()

    lines = (log_dir / APP_LOG_FILENAME).read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(lines[-1])

    assert record["message"] == "hello"
    assert record["level"] == "WARNING"
    assert record["correlation_id"] == "abc123"
    assert record["widget"] == 7


def test_records_outside_a_request_still_carry_a_correlation_field(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    configure_logging(_settings(log_dir, enabled=True))

    logging.getLogger("nanovox.test").info("startup")
    logging.shutdown()

    record = json.loads(
        (log_dir / APP_LOG_FILENAME).read_text(encoding="utf-8").strip().splitlines()[-1]
    )
    assert record["correlation_id"] == "-"


def test_access_records_do_not_leak_into_the_application_log(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    configure_logging(_settings(log_dir, enabled=True))

    logging.getLogger(ACCESS_LOGGER_NAME).info("request completed")
    logging.shutdown()

    app_log = log_dir / APP_LOG_FILENAME
    assert not app_log.exists() or "request completed" not in app_log.read_text(encoding="utf-8")


def test_exceptions_are_serialised_into_the_json_record(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    configure_logging(_settings(log_dir, enabled=True))

    try:
        raise ValueError("something specific went wrong")
    except ValueError:
        logging.getLogger("nanovox.test").exception("failed")
    logging.shutdown()

    record = json.loads(
        (log_dir / APP_LOG_FILENAME).read_text(encoding="utf-8").strip().splitlines()[-1]
    )
    assert "ValueError: something specific went wrong" in record["exception"]


def test_stack_information_is_serialised_when_requested(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    configure_logging(_settings(log_dir, enabled=True))

    logging.getLogger("nanovox.test").warning("where am I", stack_info=True)
    logging.shutdown()

    record = json.loads(
        (log_dir / APP_LOG_FILENAME).read_text(encoding="utf-8").strip().splitlines()[-1]
    )
    assert "Stack (most recent call last)" in record["stack"]


def test_text_format_produces_plain_lines(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    configure_logging(
        make_settings(log_enabled=True, log_to_console=False, log_dir=log_dir, log_format="text")
    )

    token = set_correlation_id("plain-1")
    try:
        logging.getLogger("nanovox.test").info("readable line")
    finally:
        reset_correlation_id(token)
    logging.shutdown()

    contents = (log_dir / APP_LOG_FILENAME).read_text(encoding="utf-8")
    assert "[plain-1] nanovox.test: readable line" in contents
    assert not contents.lstrip().startswith("{")


def test_console_logging_adds_a_second_handler(tmp_path: Path) -> None:
    configure_logging(
        make_settings(log_enabled=True, log_to_console=True, log_dir=tmp_path / "logs")
    )

    handler_types = {type(handler) for handler in logging.getLogger().handlers}
    assert logging.StreamHandler in handler_types
    assert len(logging.getLogger().handlers) == 2


def test_an_unwritable_log_directory_is_a_configuration_error(tmp_path: Path) -> None:
    # A file where the log directory should be: mkdir cannot succeed.
    blocker = tmp_path / "logs"
    blocker.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="LOG_DIR is not writable"):
        configure_logging(_settings(blocker, enabled=True))


def test_the_llm_audit_log_has_its_own_file(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    configure_logging(_settings(log_dir, enabled=True))

    LlmAuditLog().attempt(
        provider="ollama",
        model="qwen2.5:7b-instruct",
        prompt_id="provider_check",
        prompt_version="1.0.0",
        attempt=1,
        outcome="ok",
        latency_ms=120.5,
        input_tokens=113,
        output_tokens=48,
        usage_reported=True,
    )
    logging.shutdown()

    record = json.loads(
        (log_dir / LLM_AUDIT_LOG_FILENAME).read_text(encoding="utf-8").strip().splitlines()[-1]
    )
    assert record["provider"] == "ollama"
    assert record["input_tokens"] == 113

    # Cost records must not be mixed into the application log.
    app_log = log_dir / APP_LOG_FILENAME
    assert not app_log.exists() or "qwen2.5" not in app_log.read_text(encoding="utf-8")


def test_the_audit_log_survives_a_raised_global_log_level(tmp_path: Path) -> None:
    # It is a cost and provenance record: setting LOG_LEVEL=WARNING must not
    # silently stop collecting it.
    log_dir = tmp_path / "logs"
    configure_logging(
        make_settings(log_enabled=True, log_to_console=False, log_dir=log_dir, log_level="WARNING")
    )

    assert logging.getLogger(LLM_AUDIT_LOGGER_NAME).level == logging.INFO


def test_disabled_logging_writes_no_audit_file(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    configure_logging(_settings(log_dir, enabled=False))

    LlmAuditLog().attempt(
        provider="ollama",
        model="m",
        prompt_id="p",
        prompt_version="1",
        attempt=1,
        outcome="ok",
        latency_ms=1.0,
        input_tokens=0,
        output_tokens=0,
        usage_reported=False,
    )

    assert not log_dir.exists()


def test_uvicorn_access_log_is_silenced_in_favour_of_our_own(tmp_path: Path) -> None:
    # Our middleware records every request with a correlation ID and a duration.
    # Leaving uvicorn's access logger on would write each request a second time,
    # without an ID.
    configure_logging(_settings(tmp_path / "logs", enabled=True))

    uvicorn_access = logging.getLogger("uvicorn.access")
    assert not uvicorn_access.propagate
    assert all(isinstance(h, logging.NullHandler) for h in uvicorn_access.handlers)


def test_uvicorn_error_records_are_routed_into_our_handlers(tmp_path: Path) -> None:
    configure_logging(_settings(tmp_path / "logs", enabled=True))

    uvicorn_error = logging.getLogger("uvicorn.error")
    assert uvicorn_error.propagate
    assert uvicorn_error.handlers == []


def test_uvicorn_colour_copy_is_stripped_from_the_json_record(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    configure_logging(_settings(log_dir, enabled=True))

    logging.getLogger("uvicorn.error").info("Started", extra={"color_message": "\x1b[1mStarted"})
    logging.shutdown()

    record = json.loads(
        (log_dir / APP_LOG_FILENAME).read_text(encoding="utf-8").strip().splitlines()[-1]
    )
    assert "color_message" not in record


def test_configuring_twice_does_not_duplicate_handlers(tmp_path: Path) -> None:
    settings = _settings(tmp_path / "logs", enabled=True)

    configure_logging(settings)
    configure_logging(settings)

    assert len(logging.getLogger().handlers) == 1

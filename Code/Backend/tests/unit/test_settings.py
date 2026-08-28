"""Configuration is validated at startup, so bad values fail loudly and early (D4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.errors import ConfigurationError
from infrastructure.config.settings import get_settings
from tests.support.settings import make_settings as _settings


def test_defaults_produce_a_usable_local_configuration() -> None:
    settings = _settings()

    assert settings.app_env == "local"
    assert settings.api_prefix == "/api/v1"
    assert settings.database_url.startswith("sqlite+aiosqlite:///")
    assert not settings.is_production


def test_cors_origins_are_parsed_from_a_comma_separated_string() -> None:
    settings = _settings(cors_origins="  a , b ,, c ")

    assert settings.cors_origin_list == ["a", "b", "c"]


def test_api_prefix_must_be_rooted() -> None:
    with pytest.raises(ValueError, match="must start with"):
        _settings(api_prefix="api/v1")


def test_api_prefix_trailing_slash_is_normalised() -> None:
    assert _settings(api_prefix="/api/v1/").api_prefix == "/api/v1"


def test_synchronous_database_url_is_rejected() -> None:
    # A sync driver would only fail once a request reached the database.
    with pytest.raises(ValueError, match="async SQLite driver"):
        _settings(database_url="sqlite:///./nanovox.db")


def test_database_file_is_derived_from_the_url() -> None:
    settings = _settings(database_url="sqlite+aiosqlite:///C:/tmp/nanovox.db")

    assert settings.database_file == Path("C:/tmp/nanovox.db")


def test_in_memory_database_has_no_file() -> None:
    assert _settings(database_url="sqlite+aiosqlite:///:memory:").database_file is None


def test_invalid_port_is_rejected() -> None:
    with pytest.raises(ValueError, match="less than or equal to 65535"):
        _settings(app_port=70000)


def test_get_settings_reports_invalid_configuration_as_a_domain_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_PORT", "not-a-port")
    get_settings.cache_clear()

    with pytest.raises(ConfigurationError) as exc_info:
        get_settings()

    get_settings.cache_clear()
    assert "cannot start" in exc_info.value.message
    assert exc_info.value.detail is not None
    assert "app_port" in exc_info.value.detail

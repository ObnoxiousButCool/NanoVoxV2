"""Shared test fixtures.

Tests never read the developer's ``.env``: settings are constructed explicitly
with ``_env_file=None`` so a local configuration change cannot make the suite
pass or fail.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from frameworks_drivers.main import create_app
from infrastructure.config.settings import Settings
from tests.support.settings import make_settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Isolated settings: temporary database, logging off."""
    return make_settings(
        app_env="local",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
        log_enabled=False,
        log_to_console=False,
        log_dir=tmp_path / "logs",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    """An application instance, not yet started."""
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """A client for a fully started application, including lifespan."""
    with TestClient(app) as test_client:
        yield test_client

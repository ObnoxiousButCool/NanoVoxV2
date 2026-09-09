"""Settings factory for tests.

Tests must not be influenced by a developer's local ``.env``: a passing suite has
to mean the code is correct, not that someone's machine happens to be configured
a particular way. The subclass below disables dotenv loading through
``model_config`` — which is type-checked — rather than by passing the private
``_env_file`` keyword, which is not part of the public typed signature.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic_settings import SettingsConfigDict

from infrastructure.config.settings import Settings


class IsolatedSettings(Settings):
    """Settings that ignore any ``.env`` file on disk."""

    model_config = SettingsConfigDict(env_file=None, case_sensitive=False, extra="ignore")


# A path that will not exist, so a test application never serves the frontend.
#
# The SPA is a catch-all route, which by construction matches anything the API
# did not. A test that adds its own route after ``create_app`` would find it
# shadowed — and the failure looks like a broken error handler rather than a
# route that was never reached. Tests exercise the API; the build is not theirs
# to serve.
_NO_FRONTEND = Path(__file__).resolve().parent / "no-frontend-build"

# A database URL that cannot be opened, so no test can reach a real database by
# omission. Left at its default, ``database_url`` resolves to ``Data/nanovox.db``
# — the developer's own working database. A test that touched it would write to
# it, and in CI, where the file is gitignored and therefore absent, SQLite
# creates an empty one and the test fails on a missing table instead. Both
# happened: every test in ``test_spa.py`` passed locally and failed in CI for
# exactly that reason.
#
# The parent here is this module — a file, not a directory. That matters:
# ``create_database_engine`` calls ``mkdir(parents=True)`` on the parent, so a
# merely absent directory would be created and the accident would stay silent.
# A parent that is a file cannot be made into one, so the engine raises
# ``ConfigurationError`` the moment it is constructed, naming the path. A test
# that needs a database passes its own URL, as ``conftest.settings`` does.
_NO_DATABASE = f"sqlite+aiosqlite:///{(Path(__file__).resolve() / 'unused.db').as_posix()}"


def make_settings(**overrides: Any) -> Settings:
    """Build settings for a test, with the given field overrides."""
    overrides.setdefault("frontend_dist_path", _NO_FRONTEND)
    overrides.setdefault("database_url", _NO_DATABASE)
    return IsolatedSettings(**overrides)

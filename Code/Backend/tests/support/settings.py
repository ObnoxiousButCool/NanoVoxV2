"""Settings factory for tests.

Tests must not be influenced by a developer's local ``.env``: a passing suite has
to mean the code is correct, not that someone's machine happens to be configured
a particular way. The subclass below disables dotenv loading through
``model_config`` — which is type-checked — rather than by passing the private
``_env_file`` keyword, which is not part of the public typed signature.
"""

from __future__ import annotations

from typing import Any

from pydantic_settings import SettingsConfigDict

from infrastructure.config.settings import Settings


class IsolatedSettings(Settings):
    """Settings that ignore any ``.env`` file on disk."""

    model_config = SettingsConfigDict(env_file=None, case_sensitive=False, extra="ignore")


def make_settings(**overrides: Any) -> Settings:
    """Build settings for a test, with the given field overrides."""
    return IsolatedSettings(**overrides)

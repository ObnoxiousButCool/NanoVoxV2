"""Domain error hierarchy.

Every error the application raises deliberately derives from :class:`NanoVoxError`,
which carries a stable machine-readable ``code``. The delivery layer maps these
onto RFC 9457 problem responses, so an error's HTTP representation is decided in
one place rather than at each raise site.
"""

from __future__ import annotations


class NanoVoxError(Exception):
    """Base class for every error raised deliberately by NanoVox."""

    code = "nanovox_error"

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class ConfigurationError(NanoVoxError):
    """Configuration is missing, malformed or mutually inconsistent.

    Raised during startup validation so the process fails fast with an actionable
    message instead of failing on first use.
    """

    code = "configuration_error"


class ValidationError(NanoVoxError):
    """Input failed a business rule."""

    code = "validation_error"


class NotFoundError(NanoVoxError):
    """A requested resource does not exist."""

    code = "not_found"


class DependencyUnavailableError(NanoVoxError):
    """An external dependency (database, model provider) could not be reached."""

    code = "dependency_unavailable"


class ProviderUnavailableError(DependencyUnavailableError):
    """A model provider could not be reached, or refused the request transiently.

    Distinct from a bad response: the request never produced an answer, so
    retrying it is meaningful.
    """

    code = "provider_unavailable"


class ProviderResponseError(NanoVoxError):
    """A model provider answered, but not with the structure that was demanded.

    Raised only after the repair attempt has also failed. The analysis is
    abandoned rather than stored partially: a half-parsed layer would be worse
    than no layer, because it would look like a result.
    """

    code = "provider_response_error"


class ProviderNotImplementedError(NanoVoxError):
    """A provider is registered but not implemented in this build.

    Azure AI Foundry is registered so it appears in the provider list and fails
    with an explicit message (DEC-05). It must never silently fall back to
    another provider — a caller who asked for Azure and got OpenAI would have no
    way to know.
    """

    code = "provider_not_implemented"

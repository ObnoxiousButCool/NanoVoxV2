"""Who is speaking in a transcript turn."""

from __future__ import annotations

from enum import Enum


class SpeakerRole(str, Enum):
    """The role a turn belongs to.

    ``SYSTEM`` covers hold music, IVR prompts and similar non-participant lines,
    which must not be attributed to the agent when scoring.
    """

    AGENT = "AGENT"
    MEMBER = "MEMBER"
    SYSTEM = "SYSTEM"

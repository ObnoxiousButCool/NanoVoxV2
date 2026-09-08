"""Who placed the call.

Not every caller is a member. An employer's HR director calling about a group's
renewal and a broker chasing a commission statement reach the same queue as a
member asking about a copay, and counting all three as members inflates every
per-member figure on the dashboard.

This enum is the *vocabulary*, not a validation rule. Stored calls keep
``caller_type`` as free text on purpose: the value comes from a corpus header
this system does not control, and a fourth kind of caller appearing in a future
corpus should be stored and shown rather than rejected at ingest. What the enum
gives is a stable list for the filter dropdown and one place where the three
known values are named.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["CallerType"]


class CallerType(str, Enum):
    """The three kinds of caller the corpus distinguishes."""

    MEMBER = "MEMBER"
    EMPLOYER = "EMPLOYER"
    BROKER = "BROKER"

"""Call outcome.

Modelled as an enum rather than as taxonomy data because the aggregation code
branches on specific members: first-contact resolution and the escalation rate
are defined in terms of RESOLVED and ESCALATED. A value that code must reason
about individually is part of the model, not configuration.
"""

from __future__ import annotations

from enum import Enum


class Resolution(str, Enum):
    """The four outcomes used across the corpus index."""

    RESOLVED = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY RESOLVED"
    ESCALATED = "ESCALATED"
    UNRESOLVED = "UNRESOLVED"

    @property
    def is_first_contact_resolution(self) -> bool:
        """Whether this outcome counts toward FCR.

        Only a full resolution counts. Partially resolved is deliberately
        excluded: counting it would inflate the figure against the industry
        benchmark it is compared with.
        """
        return self is Resolution.RESOLVED

    @property
    def needs_follow_up(self) -> bool:
        return self is not Resolution.RESOLVED

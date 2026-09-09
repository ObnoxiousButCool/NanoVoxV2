"""Turning the page-level Week/Month filter into a concrete date range.

Every other read-model on the dashboard (agent performance, resolution time,
the minute ledger, work mix, signal distribution, the overview metrics) filters
its SQL by a plain ``[start, end)`` range — none of them bucket into weeks the
way ``trend.py`` does. This module is the one place that turns "the week
containing this date" or "this calendar month" into that range, so every card
narrows to exactly the same calls for the same filter selection.

``month_range`` uses the calendar month a call's own date falls in, matching
``trend.Bucket.MONTH`` — not ``month_window``'s week-ownership rule, which
would disagree with it: the month picker itself is now built from
``available_months``, which lists a month only when a call is dated in it, so
the two have to agree on what "in it" means or a month the picker offers here
could filter to a different, disjoint set of calls than the top strip shows
for the same selection.
"""

from __future__ import annotations

from datetime import date, timedelta

__all__ = ["month_range", "resolve_period", "week_range"]


def week_range(anchor: date) -> tuple[date, date]:
    """The Monday-Sunday week containing ``anchor``, as a half-open range."""
    start = anchor - timedelta(days=anchor.weekday())
    return start, start + timedelta(days=7)


def month_range(month: date) -> tuple[date, date]:
    """Every day in ``month``'s calendar month, as a half-open range."""
    start = date(month.year, month.month, 1)
    end = date(month.year + 1, 1, 1) if month.month == 12 else date(month.year, month.month + 1, 1)
    return start, end


def resolve_period(anchor: date | None, month: date | None) -> tuple[date, date] | None:
    """The header filter's own request, as a date range — or ``None`` for
    all-time. ``month`` takes precedence, matching every other place on this
    dashboard where an anchor and a month can arrive together."""
    if month is not None:
        return month_range(month)
    if anchor is not None:
        return week_range(anchor)
    return None

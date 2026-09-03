"""Which single team owns a call, when its findings belong to several.

A call can raise findings in more than one L4 category, and those categories can
have different owners. Counting the call under each of them answers "how many
findings does this team have to read", which is not the question the owner chart
is asked: a manager reads it as "how many calls are mine", and a call that shows
up on two teams' bars is a call two teams each believe they are accountable for.

So each call is attributed to exactly one owner — the one whose finding on that
call is the most serious. The alternative, splitting a call fractionally between
teams, produces bars that total correctly and mean nothing.

The per-category figures are deliberately *not* built from this. A call really
did raise both findings, and the category bars are the place that stays true to
it; this is only for the rollup that has to sum to a number of calls.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from domain.taxonomy import L4Category
from domain.value_objects.severity import Severity

__all__ = ["L4Finding", "primary_category_by_call"]


@dataclass(frozen=True)
class L4Finding:
    """One operational finding on one call."""

    call_id: int
    category_code: str
    severity: Severity


def primary_category_by_call(
    findings: Sequence[L4Finding], categories: Sequence[L4Category]
) -> Mapping[int, str]:
    """The one category each call is counted under, keyed by call id.

    Ranked by three keys, in order:

    1. **The severity the analysis gave this finding on this call.** A CRITICAL
       compliance finding outranks a MEDIUM process one on the same call, which
       is the judgement a human would make reading the two side by side.
    2. **The category's configured default severity.** Reached only when a call's
       two findings were scored the same, and it defers to the standing policy in
       ``taxonomy.yaml`` rather than to whichever row SQL happened to return.
    3. **Declaration order in the taxonomy.** The last resort exists to make the
       result deterministic: without it the same corpus could attribute a call to
       Operations today and Compliance tomorrow, and the chart would move with no
       change in the data behind it.

    Findings in categories the taxonomy does not define are ignored rather than
    guessed at — an undefined category has no owner to attribute the call to.
    """
    order = {category.code: index for index, category in enumerate(categories)}
    defaults = {category.code: category.default_severity for category in categories}

    best: dict[int, tuple[int, int, int]] = {}
    winner: dict[int, str] = {}

    for finding in findings:
        if finding.category_code not in order:
            continue
        # Negated index so that "earlier in the taxonomy" is the larger key and
        # a single max() covers all three tie-breaks.
        key = (
            finding.severity.rank,
            defaults[finding.category_code].rank,
            -order[finding.category_code],
        )
        if finding.call_id not in best or key > best[finding.call_id]:
            best[finding.call_id] = key
            winner[finding.call_id] = finding.category_code

    return winner

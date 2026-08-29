"""Discard every stored analysis, keeping the hand-labelled ground truth.

Re-running the corpus against a different provider or a corrected prompt means
starting from nothing, and deleting a hundred calls by hand is not a workflow.

Two things are deliberately *not* cleared:

* **Ground truth.** It is hand-labelled reference data. Re-analysis regenerates
  calls, signals and scores; it cannot regenerate a human's judgement of what the
  right answer was. Losing it would silently remove the only thing accuracy is
  measured against.
* **Nothing at all, while a run is working.** Clearing under a live run would
  delete rows the worker is still writing to.
"""

from __future__ import annotations

from dataclasses import dataclass

from application.ports.analysis_repository import AnalysisRepository
from application.ports.run_repository import RunRepository
from domain.errors import ConflictError


@dataclass(frozen=True)
class ClearedCorpus:
    """What was removed, so the caller can report it rather than guess."""

    calls: int
    runs: int


class ClearCorpus:
    """Empties the analysed corpus, leaving ground truth in place."""

    def __init__(self, analyses: AnalysisRepository, runs: RunRepository) -> None:
        self._analyses = analyses
        self._runs = runs

    async def execute(self) -> ClearedCorpus:
        active = await self._runs.active()
        if active is not None:
            raise ConflictError(
                "A corpus run is in progress, so the corpus cannot be cleared.",
                detail=(
                    f"Run {active.id} is still working. Cancel it and wait for it to "
                    "stop, then clear."
                ),
            )

        # Runs first. Their items reference calls with ON DELETE SET NULL, so
        # clearing calls first would leave every item orphaned in the moment
        # between the two deletes rather than simply gone.
        runs = await self._runs.delete_all()
        calls = await self._analyses.delete_all()
        return ClearedCorpus(calls=calls, runs=runs)

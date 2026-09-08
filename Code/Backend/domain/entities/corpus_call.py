"""One authored call from the corpus, before anything has been analyzed.

The corpus is the input side of DEC-01: every call is re-analyzed by the model
rather than trusted from the spreadsheet. This entity therefore carries the raw
transcript the model will see, and — kept strictly apart — the authored panel it
will later be measured against.

``source_id`` is the file stem, and it is the run's idempotency key. The call
*reference* is derived from it but is a display concern; identity has to survive a
reference being taken by an unrelated call.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.entities.ground_truth import GroundTruth


@dataclass(frozen=True)
class CorpusCall:
    """A transcript from the corpus, with its authored ground truth."""

    source_id: str
    reference: str
    title: str
    transcript: str
    # All stated in the file's header, not inferred. These are facts the source
    # already knows; asking a model to estimate them from the words produces
    # plausible numbers instead of the real ones.
    duration_minutes: int | None = None
    # Seconds, where the corpus states handle time to that precision ("AHT 5m
    # 21s"). Kept alongside the minutes rather than replacing them: the older
    # corpus states only whole minutes, and rounding every figure to match it
    # would throw away precision this one has.
    duration_seconds: int | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    # MEMBER, EMPLOYER or BROKER. Not every caller is a member, and treating an
    # employer's HR director as one would put their name in the member column.
    caller_type: str | None = None
    ground_truth: GroundTruth | None = None
    sequence: int = 0

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("A corpus call must carry the id of the file it came from.")
        if not self.reference.strip():
            raise ValueError(f"Corpus call {self.source_id!r} has no reference.")
        if not self.transcript.strip():
            # A file with a heading and no transcript is a corpus defect. Letting
            # it through would spend a model call to produce a meaningless result.
            raise ValueError(f"Corpus call {self.source_id!r} has an empty transcript.")

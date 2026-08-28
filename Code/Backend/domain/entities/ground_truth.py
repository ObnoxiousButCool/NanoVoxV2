"""The figures a human author wrote for a corpus call (plan A3).

This is **not** analysis output and must never be mixed into it. The corpus files
carry an authored insights panel — a score, a tier, a resolution — and those
numbers were written by hand, not computed by the rubric. Storing them beside the
model's own conclusions is what makes the P8 fidelity report possible: it is the
only way to answer "is the model actually good?" with evidence.

Every field is optional. A corpus file that omits a heading yields ``None`` there
rather than a plausible default, because a guessed ground truth would silently
corrupt the very comparison this record exists to support.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GroundTruth:
    """Authored expectations for one corpus call."""

    agent_name: str | None = None
    tier: str | None = None
    score: int | None = None
    resolution: str | None = None
    sentiment_start: str | None = None
    sentiment_end: str | None = None
    topics: tuple[str, ...] = ()
    # Brokers the author named. Recall against these is one of the fidelity
    # measures in plan §11.2, and it is the measure most likely to expose a model
    # inventing an attribution — which is why the names are kept, not just a count.
    broker_names: tuple[str, ...] = ()
    member_context: str | None = None
    panel_text: str = ""

    def __post_init__(self) -> None:
        if self.score is not None and not 0 <= self.score <= 100:
            raise ValueError(f"Authored score out of range: {self.score}")

    @property
    def is_empty(self) -> bool:
        """Whether the file carried no usable expectations at all.

        An empty record is stored rather than dropped: "this call has no authored
        panel" is itself a finding when the fidelity report runs.
        """
        return not any(
            (
                self.agent_name,
                self.tier,
                self.score is not None,
                self.resolution,
                self.sentiment_start,
                self.topics,
                self.broker_names,
                self.panel_text,
            )
        )

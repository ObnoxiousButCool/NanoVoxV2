"""The attention queue: what needs doing, ranked, with an owner.

Plan §6.6. **Every number here comes from aggregation, never from a model.** The
prototype's queue makes book-level claims — "13 of 16 prior auth calls
unresolved", "five member-reported conduct issues" — and a claim like that is
either counted or it is invented. Counting it is the only version anyone can act
on.

Rules are configuration, so what counts as "needs attention" is tunable by
someone who does not read Python. Each rule declares a threshold, an owner and a
severity; evaluation is a pure function over counts.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from domain.errors import ValidationError
from domain.value_objects.severity import Severity


class RuleKind(str, Enum):
    """What a rule counts."""

    SIGNAL_PRESENT = "signal_present"
    L4_CATEGORY_VOLUME = "l4_category_volume"
    BROKER_NEGATIVE = "broker_negative"
    UNRESOLVED_IN_CATEGORY = "unresolved_in_category"


@dataclass(frozen=True)
class AttentionRule:
    """One condition that puts something on the queue."""

    id: str
    kind: RuleKind
    title: str
    minimum: int
    severity: Severity
    owner: str
    why: str
    applies_to: str | None = None
    """The one group this rule watches, or None to watch every group of its kind.

    Without this a rule matches every group of its kind, so a rule written for
    clinical risk would fire on an unrelated signal and headline it "Agents are
    not escalating clinical urgency". A dashboard that puts the wrong headline
    over a real count is worse than one that shows nothing."""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValidationError("Attention rule id must not be empty.")
        if not self.title.strip():
            raise ValidationError(f"Attention rule {self.id!r} must have a title.")
        if not self.owner.strip():
            raise ValidationError(
                f"Attention rule {self.id!r} must name an owner. "
                "An item nobody owns will not get done."
            )
        if self.minimum < 1:
            raise ValidationError(
                f"Attention rule {self.id!r} needs a minimum of at least 1, got {self.minimum}."
            )


@dataclass(frozen=True)
class GroupCount:
    """A counted group: a signal, an L4 category, a broker, or a call category."""

    key: str
    label: str
    count: int
    unresolved: int = 0
    references: tuple[str, ...] = ()


@dataclass(frozen=True)
class AttentionInputs:
    """Everything the rules are evaluated against."""

    total_calls: int
    signal_counts: tuple[GroupCount, ...] = ()
    l4_category_counts: tuple[GroupCount, ...] = ()
    broker_negative_counts: tuple[GroupCount, ...] = ()
    category_unresolved_counts: tuple[GroupCount, ...] = ()

    def for_kind(self, kind: RuleKind) -> tuple[GroupCount, ...]:
        if kind is RuleKind.SIGNAL_PRESENT:
            return self.signal_counts
        if kind is RuleKind.L4_CATEGORY_VOLUME:
            return self.l4_category_counts
        if kind is RuleKind.BROKER_NEGATIVE:
            return self.broker_negative_counts
        return self.category_unresolved_counts


@dataclass(frozen=True)
class AttentionItem:
    """One ranked item on the queue."""

    rule_id: str
    kind: RuleKind
    title: str
    subject: str
    subject_key: str
    """The code of the thing counted, where `subject` is its label.

    An item is a claim about a specific set of calls, and a reader who believes
    the claim will want to see them. Only the label survived before, which is
    what a person reads and not what the calls list filters on — so the queue
    could state "13 calls" and offer no way to reach the 13. Carried with the
    kind, which says which of the four things the key names."""

    why: str
    owner: str
    severity: Severity
    count: int
    unresolved: int
    references: tuple[str, ...]

    @property
    def rank_key(self) -> tuple[int, int]:
        """Severity first, then how many calls are affected (plan §6.6)."""
        return (self.severity.rank, self.count)


def _count_for(kind: RuleKind, group: GroupCount) -> int:
    if kind is RuleKind.UNRESOLVED_IN_CATEGORY:
        return group.unresolved
    return group.count


def evaluate_rules(
    rules: Sequence[AttentionRule], inputs: AttentionInputs
) -> tuple[AttentionItem, ...]:
    """Produce the ranked attention queue.

    Ranked by severity then volume — the prototype's stated ordering, calls
    affected by severity. An item is only produced when its rule's threshold is
    genuinely met, so an empty queue means nothing crossed a threshold rather
    than that nothing was checked.
    """
    items: list[AttentionItem] = []

    for rule in rules:
        for group in inputs.for_kind(rule.kind):
            if rule.applies_to is not None and group.key != rule.applies_to:
                continue
            count = _count_for(rule.kind, group)
            if count < rule.minimum:
                continue
            items.append(
                AttentionItem(
                    rule_id=rule.id,
                    kind=rule.kind,
                    title=rule.title.format(subject=group.label, count=count),
                    subject=group.label,
                    subject_key=group.key,
                    why=rule.why.format(
                        subject=group.label,
                        count=count,
                        unresolved=group.unresolved,
                        total=inputs.total_calls,
                    ),
                    owner=rule.owner,
                    severity=rule.severity,
                    count=count,
                    unresolved=group.unresolved,
                    references=group.references,
                )
            )

    return tuple(sorted(items, key=lambda item: item.rank_key, reverse=True))

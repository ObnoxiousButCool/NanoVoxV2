"""Validation of model-raised signals against the transcript.

A signal is the most consequential thing the pipeline stores. ``clinical_risk``
alone withholds a call's score and puts it in a clinical-review queue, so it is
read as "a human must look at this call". It was, until now, the one claim in
the system that nothing checked: markers are validated against the turn they
cite and broker attributions must quote evidence, while signals arrived as a
bare list of codes and went straight to the scoring gate.

The cost of not checking showed up the first time it met a corpus with no
clinical calls in it: ``clinical_risk`` fired on eight of fifty ancillary
benefits calls — an eye-exam frequency limit, a bereavement claim, a COBRA
question — and every one was wrong. A safety queue that is entirely noise is
not a safety queue; it is something people learn to close.

So a signal now has to say *where* it saw what it saw, and the quote has to be
in that turn. Rejections are returned rather than dropped, because a model that
keeps inventing evidence is a finding about the model.

The prompt is deliberately left broad: a safety net should over-trigger, and it
is this check — not a narrower instruction — that is the right place to catch
what it sweeps up.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from domain.entities.transcript import Transcript

__all__ = [
    "RaisedSignal",
    "RejectedSignal",
    "SignalRejection",
    "SignalValidation",
    "validate_signals",
]


@dataclass(frozen=True)
class RaisedSignal:
    """A signal the model raised, with the evidence it claims."""

    code: str
    quote: str
    evidence_turn_seq: int


class SignalRejection(str, Enum):
    """Why a signal was refused."""

    UNKNOWN_CODE = "unknown_code"
    MISSING_TURN = "missing_turn"
    QUOTE_NOT_IN_TURN = "quote_not_in_turn"
    NO_QUOTE = "no_quote"


@dataclass(frozen=True)
class RejectedSignal:
    """A signal that was refused, and why."""

    signal: RaisedSignal
    reason: SignalRejection

    @property
    def explanation(self) -> str:
        if self.reason is SignalRejection.UNKNOWN_CODE:
            return f"Signal {self.signal.code!r} is not in the taxonomy."
        if self.reason is SignalRejection.NO_QUOTE:
            return f"Signal {self.signal.code!r} cited no evidence."
        if self.reason is SignalRejection.MISSING_TURN:
            return (
                f"Signal {self.signal.code!r} cites turn "
                f"{self.signal.evidence_turn_seq}, which does not exist."
            )
        return (
            f"Signal {self.signal.code!r} quoted text absent from turn "
            f"{self.signal.evidence_turn_seq}: {self.signal.quote!r}"
        )


@dataclass(frozen=True)
class SignalValidation:
    """The outcome of validating the signals on one call."""

    accepted: tuple[str, ...]
    rejected: tuple[RejectedSignal, ...]

    @property
    def has_rejections(self) -> bool:
        return bool(self.rejected)

    @property
    def rejection_notes(self) -> tuple[str, ...]:
        return tuple(item.explanation for item in self.rejected)


def _reject_reason(
    signal: RaisedSignal, transcript: Transcript, known: frozenset[str]
) -> SignalRejection | None:
    if signal.code not in known:
        return SignalRejection.UNKNOWN_CODE

    if not signal.quote.strip():
        # An empty quote is the shape this failure takes when a model wants to
        # raise a signal it cannot support: the field is present but says
        # nothing. Treated as no evidence rather than as a quote that happens
        # to match every turn.
        return SignalRejection.NO_QUOTE

    turn = transcript.turn(signal.evidence_turn_seq)
    if turn is None:
        return SignalRejection.MISSING_TURN

    if not turn.contains(signal.quote):
        return SignalRejection.QUOTE_NOT_IN_TURN

    return None


def validate_signals(
    signals: Iterable[RaisedSignal], transcript: Transcript, known_codes: Iterable[str]
) -> SignalValidation:
    """Keep the signals whose evidence is really in the transcript.

    Accepted codes are deduplicated and returned in the order first raised: two
    quotes for one condition are one condition, and the scoring gate asks only
    whether a code is present.
    """
    known = frozenset(known_codes)
    accepted: list[str] = []
    rejected: list[RejectedSignal] = []

    for signal in signals:
        reason = _reject_reason(signal, transcript, known)
        if reason is not None:
            rejected.append(RejectedSignal(signal=signal, reason=reason))
        elif signal.code not in accepted:
            accepted.append(signal.code)

    return SignalValidation(accepted=tuple(accepted), rejected=tuple(rejected))

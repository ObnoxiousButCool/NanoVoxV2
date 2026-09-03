"""The response schemas the model must fill, one per layer.

These are built **from the loaded taxonomy and rubric**, not hard-coded. Every
vocabulary-constrained field becomes a ``Literal`` of the configured values, so
the JSON Schema sent to the provider enumerates exactly which categories,
sentiment states, signal types, L4 categories and rubric dimensions are
acceptable.

That matters because all three providers constrain decoding to the schema. The
model is not asked to please use the vocabulary — it is unable to emit anything
else. This is what makes the dashboard groupable (plan §4.2): a free-text
sentiment state would produce a chart category of one, and an invented rubric
dimension would silently drop a penalty.

Adding a category to ``taxonomy.yaml`` therefore changes what the model may
answer, with no code change — which is the point of DEC-02.

Every field is required and non-nullable. Optional fields are poorly supported by
strict structured-output modes, so absence is expressed as an empty string or an
empty list and normalised afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, create_model

from domain.scoring.rubric import Rubric
from domain.taxonomy import Taxonomy
from domain.value_objects.polarity import Polarity
from domain.value_objects.resolution import Resolution
from domain.value_objects.severity import Severity

# A turn index of this value means "not tied to a specific turn". Strict schema
# modes handle a sentinel far more reliably than a nullable integer.
NO_TURN = -1


def _one_of(values: tuple[str, ...]) -> Any:
    """A ``Literal`` over the configured vocabulary.

    Returns ``Any`` because the members are only known at runtime — the vocabulary
    comes from a YAML file. The constraint itself is real and is enforced by the
    provider's schema; the type checker simply cannot see it.
    """
    return Literal[values]


def _list_of(model: Any) -> Any:
    """``list[model]`` for a model class built at runtime.

    The dynamic-typing escape hatch is confined to these two helpers rather than
    scattered as ignores across every field below.
    """
    return list[model]


@dataclass(frozen=True)
class AnalysisSchemas:
    """The five response models, bound to one taxonomy and rubric."""

    l1: type[BaseModel]
    l2: type[BaseModel]
    l3: type[BaseModel]
    l4: type[BaseModel]
    l5: type[BaseModel]


def build_analysis_schemas(taxonomy: Taxonomy, rubric: Rubric) -> AnalysisSchemas:
    """Build the layer schemas for the currently loaded configuration."""
    sentiment = _one_of(taxonomy.sentiment_states)
    signal_codes = _one_of(tuple(item.code for item in taxonomy.signal_types))
    categories = _one_of(tuple(item.code for item in taxonomy.categories))
    l4_categories = _one_of(tuple(item.code for item in taxonomy.l4_categories))
    dimensions = _one_of(tuple(sorted(rubric.dimensions)))
    resolutions = _one_of(tuple(member.value for member in Resolution))
    severities = _one_of(tuple(member.value for member in Severity))
    polarities = _one_of(tuple(member.value for member in Polarity))

    raised_signal = create_model(
        "RaisedSignalOut",
        code=(signal_codes, Field(description="The condition this call raises.")),
        evidence_turn_seq=(
            int,
            Field(description="Zero-based index of the transcript turn that proves this."),
        ),
        quote=(
            str,
            Field(
                description=(
                    "The member's or agent's own words from that turn, copied exactly. "
                    "Not a paraphrase: the text is matched against the turn."
                )
            ),
        ),
    )

    l1 = create_model(
        "L1Understanding",
        call_type=(str, Field(description="What the member called about, in a short phrase.")),
        member_sentiment_start=(
            sentiment,
            Field(description="The member's state at the start of the call."),
        ),
        member_sentiment_end=(
            sentiment,
            Field(description="The member's state by the end of the call."),
        ),
        agent_tone=(str, Field(description="The agent's manner, in one or two words.")),
        member_context=(
            str,
            Field(description="Who the member is and their situation. Empty string if unclear."),
        ),
        key_terms=(
            list[str],
            Field(description="Up to eight salient terms or phrases from the call."),
        ),
        signals=(
            _list_of(raised_signal),
            Field(
                description=(
                    "Conditions this call raises, each with the words that prove it. "
                    "Include 'clinical_risk' whenever the member describes symptoms or "
                    "a lapse in essential medication that the agent did not escalate. "
                    "A signal whose quote is not in the turn it cites is discarded, so "
                    "raise one only where the transcript says it. Empty list if none."
                )
            ),
        ),
    )

    key_moment = create_model(
        "KeyMoment",
        sequence=(int, Field(description="Order of this moment in the call, starting at 1.")),
        description=(str, Field(description="What happened, in one sentence.")),
        is_negative=(bool, Field(description="True if this moment went badly for the member.")),
    )

    l2 = create_model(
        "L2Insights",
        title=(
            str,
            Field(description="A headline naming what this call was really about, under 90 chars."),
        ),
        summary=(
            str,
            Field(description="What happened and how it ended, in two or three sentences."),
        ),
        category=(categories, Field(description="The single best-fitting call category.")),
        resolution=(resolutions, Field(description="The outcome for the member.")),
        topics=(list[str], Field(description="Up to six topic keywords.")),
        key_moments=(
            _list_of(key_moment),
            Field(description="The turning points of the call, in order."),
        ),
        duration_minutes=(
            int,
            Field(description="Approximate call length in minutes. Use 0 if it cannot be judged."),
        ),
    )

    marker = create_model(
        "ScoreMarkerOut",
        polarity=(polarities, Field(description="POSITIVE if it counts for the agent.")),
        dimension=(
            dimensions,
            Field(description="The rubric dimension this observation belongs to."),
        ),
        description=(str, Field(description="What the agent did or failed to do.")),
        evidence_turn_seq=(
            int,
            Field(description="Zero-based index of the transcript turn that proves this."),
        ),
        quote=(
            str,
            Field(
                description=(
                    "Text copied verbatim from that turn. It is checked against the "
                    "transcript and the observation is discarded if it does not match."
                )
            ),
        ),
    )

    l3 = create_model(
        "L3Quality",
        agent_name=(str, Field(description="The agent's name, or an empty string if unnamed.")),
        markers=(
            _list_of(marker),
            Field(
                description=(
                    "Every observation about the agent's handling, positive and negative. "
                    "Do not assign a score; the score is computed from these."
                )
            ),
        ),
    )

    l4_signal = create_model(
        "L4SignalOut",
        category=(l4_categories, Field(description="The action category this finding belongs to.")),
        severity=(severities, Field(description="How serious this finding is.")),
        narrative=(str, Field(description="What was found and why it matters.")),
        recommended_action=(str, Field(description="What the owning team should do.")),
    )

    broker_signal = create_model(
        "BrokerSignalOut",
        broker_name=(str, Field(description="The broker's name exactly as the member said it.")),
        polarity=(polarities, Field(description="POSITIVE if this reflects well on the broker.")),
        issue=(str, Field(description="What the broker did or failed to do.")),
        evidence_turn_seq=(
            int,
            Field(description="Zero-based index of the turn where the member named the broker."),
        ),
        quote=(
            str,
            Field(
                description=(
                    "The member's own words naming the broker, copied verbatim. Only "
                    "record a broker when the member names them aloud."
                )
            ),
        ),
    )

    l4 = create_model(
        "L4OperationalBi",
        signals=(
            _list_of(l4_signal),
            Field(description="Operational findings. Empty list if none."),
        ),
        broker_signals=(
            _list_of(broker_signal),
            Field(
                description=(
                    "Broker attributions. Empty list unless the member named a broker "
                    "aloud. Never infer a broker from context."
                )
            ),
        ),
    )

    assist_event = create_model(
        "AssistEventOut",
        outcome=(
            Literal["FIRED", "SHOULD_HAVE_FIRED"],
            Field(
                description=(
                    "SHOULD_HAVE_FIRED when nothing helped the agent but something ought to have."
                )
            ),
        ),
        trigger=(str, Field(description="The condition that would activate this assist.")),
        recommendation=(
            str,
            Field(description="What the assist should have put in front of the agent."),
        ),
        severity=(severities, Field(description="How serious the missed or delivered assist was.")),
        at_turn_seq=(
            int,
            Field(description=f"Zero-based turn index, or {NO_TURN} if not tied to one turn."),
        ),
        timestamp_label=(
            str,
            Field(description="Approximate time in the call, like '2:30'. Empty if unknown."),
        ),
    )

    l5 = create_model(
        "L5Assist",
        events=(
            _list_of(assist_event),
            Field(
                description=(
                    "Real-time assist replay. If nothing would have fired but something "
                    "should have, say so with SHOULD_HAVE_FIRED — the absence is the finding."
                )
            ),
        ),
    )

    return AnalysisSchemas(l1=l1, l2=l2, l3=l3, l4=l4, l5=l5)

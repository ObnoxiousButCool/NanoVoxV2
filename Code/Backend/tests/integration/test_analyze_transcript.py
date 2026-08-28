"""The five-layer pipeline, end to end, against Call #89 without a model.

This is the P3 exit criterion expressed as tests: pasting Call #89's transcript
must produce a complete, evidence-anchored L1-L5 analysis.
"""

from __future__ import annotations

import pytest

from application.dto.analysis_schemas import build_analysis_schemas
from application.ports.redaction import NoRedaction
from application.use_cases.analyze_transcript import (
    REASON_KEY,
    UNAVAILABLE_KEY,
    AnalyzeTranscript,
    AnalyzeTranscriptCommand,
)
from domain.entities.analysis import CallAnalysis, Layer
from domain.errors import ProviderResponseError, ValidationError
from domain.scoring.rubric import Rubric
from domain.taxonomy import Taxonomy
from domain.value_objects.resolution import Resolution
from domain.value_objects.score import ScoreStatus
from domain.value_objects.tier import Tier
from infrastructure.config.paths import DEFAULT_RUBRIC_PATH, DEFAULT_TAXONOMY_PATH
from infrastructure.config.rubric_loader import load_rubric
from infrastructure.config.taxonomy_loader import load_taxonomy
from tests.support.analysis import (
    L3_PAYLOAD,
    PAYLOADS_BY_PROMPT,
    InMemoryAnalysisRepository,
    ScriptedLayerProvider,
    StubPromptSource,
)
from tests.support.clock import FixedClock
from tests.unit.scoring.test_call_89_reproduction import TRANSCRIPT

CALL_89 = "\n".join(
    f"{turn.speaker_name or turn.role.value.title()}: {turn.text}" for turn in TRANSCRIPT.turns
)


@pytest.fixture(scope="module")
def taxonomy() -> Taxonomy:
    return load_taxonomy(DEFAULT_TAXONOMY_PATH)


@pytest.fixture(scope="module")
def rubric(taxonomy: Taxonomy) -> Rubric:
    return load_rubric(DEFAULT_RUBRIC_PATH, taxonomy)


def build(
    taxonomy: Taxonomy,
    rubric: Rubric,
    provider: ScriptedLayerProvider,
    repository: InMemoryAnalysisRepository | None = None,
) -> tuple[AnalyzeTranscript, InMemoryAnalysisRepository]:
    store = repository or InMemoryAnalysisRepository()
    use_case = AnalyzeTranscript(
        prompts=StubPromptSource(),
        schemas=build_analysis_schemas(taxonomy, rubric),
        taxonomy=taxonomy,
        rubric=rubric,
        redaction=NoRedaction(),
        repository=store,
        clock=FixedClock(),
    )
    return use_case, store


async def analyse(
    taxonomy: Taxonomy, rubric: Rubric, provider: ScriptedLayerProvider
) -> tuple[CallAnalysis, InMemoryAnalysisRepository]:
    use_case, store = build(taxonomy, rubric, provider)
    analysis = await use_case.execute(AnalyzeTranscriptCommand(transcript=CALL_89), provider)
    return analysis, store


class TestCompleteAnalysis:
    async def test_all_five_layers_are_produced(self, taxonomy: Taxonomy, rubric: Rubric) -> None:
        provider = ScriptedLayerProvider()

        analysis, _ = await analyse(taxonomy, rubric, provider)

        assert [layer.layer for layer in analysis.layers] == list(Layer)
        assert provider.prompts_seen == list(PAYLOADS_BY_PROMPT)

    async def test_the_call_is_classified_from_the_model_output(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        analysis, _ = await analyse(taxonomy, rubric, ScriptedLayerProvider())

        assert analysis.title == "ER copay question that was a cardiac presentation"
        assert analysis.category.code == "coverage_benefits"
        assert analysis.category.label == "Coverage & Benefits"
        assert analysis.resolution is Resolution.UNRESOLVED
        assert str(analysis.sentiment) == "WORRIED → DISMISSED"
        assert analysis.agent_name == "Brad"
        assert analysis.duration_minutes == 6

    async def test_the_clinical_signal_suspends_the_score(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        # The whole point of Call #89: it must not present a confident number.
        analysis, _ = await analyse(taxonomy, rubric, ScriptedLayerProvider())

        assert "clinical_risk" in analysis.signal_codes
        assert analysis.score.status is ScoreStatus.PROVISIONAL
        assert analysis.score.tier is Tier.POOR
        assert analysis.score.messages == ("Score withheld pending clinical review.",)

    async def test_the_score_is_computed_from_markers_not_taken_from_the_model(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        # DEC-03: the model supplies evidence; the rubric supplies the number.
        analysis, _ = await analyse(taxonomy, rubric, ScriptedLayerProvider())

        # escalation 40 (capped) + compliance 15 + resolution 20, offset by 2.
        assert analysis.score.total_negative == 75
        assert analysis.score.total_positive == 2
        assert analysis.score.score.value == 27

    async def test_every_stored_marker_is_backed_by_the_transcript(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        analysis, _ = await analyse(taxonomy, rubric, ScriptedLayerProvider())

        assert len(analysis.accepted_markers) == 6
        for marker in analysis.accepted_markers:
            turn = analysis.transcript.turn(marker.evidence_turn_seq)
            assert turn is not None
            assert turn.contains(marker.quote)

    async def test_the_l4_finding_carries_its_owning_team(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        analysis, _ = await analyse(taxonomy, rubric, ScriptedLayerProvider())

        assert len(analysis.l4_signals) == 1
        assert analysis.l4_signals[0].owner_name == "Compliance"

    async def test_the_missing_assist_is_recorded_as_a_gap(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        # The absence is the finding, not an empty state.
        analysis, _ = await analyse(taxonomy, rubric, ScriptedLayerProvider())

        assert len(analysis.assist_gaps) == 1
        assert analysis.assist_gaps[0].timestamp_label == "2:30"

    async def test_provenance_records_what_produced_the_analysis(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        analysis, _ = await analyse(taxonomy, rubric, ScriptedLayerProvider())

        assert analysis.provenance.provider == "scripted"
        assert analysis.provenance.model == "scripted-model"
        assert analysis.provenance.rubric_version == rubric.version
        assert analysis.provenance.prompt_version == "1.0.0"
        # Five layer calls, each reporting 100 in and 50 out.
        assert analysis.provenance.total_input_tokens == 500
        assert analysis.provenance.total_output_tokens == 250

    async def test_the_analysis_is_persisted(self, taxonomy: Taxonomy, rubric: Rubric) -> None:
        analysis, store = await analyse(taxonomy, rubric, ScriptedLayerProvider())

        assert len(store.saved) == 1
        assert store.saved[0].reference == analysis.reference == "C0001"


class TestEvidenceEnforcement:
    async def test_an_invented_quote_is_discarded_and_does_not_score(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        payloads = dict(PAYLOADS_BY_PROMPT)
        payloads["l3_quality"] = {
            "agent_name": "Brad",
            "markers": [
                *L3_PAYLOAD["markers"],
                {
                    "polarity": "NEGATIVE",
                    "dimension": "empathy",
                    "description": "Told the member he could not help.",
                    "evidence_turn_seq": 4,
                    "quote": "I am not going to help you with that",
                },
            ],
        }
        provider = ScriptedLayerProvider(payloads)

        analysis, _ = await analyse(taxonomy, rubric, provider)

        assert len(analysis.accepted_markers) == 6
        assert len(analysis.rejected_marker_notes) == 1
        assert "does not appear in turn 4" in analysis.rejected_marker_notes[0]
        # The invented criticism must not have cost the agent anything.
        assert analysis.score.total_negative == 75

    async def test_a_broker_attribution_without_a_quote_is_dropped(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        # These records name real people; unevidenced ones must not be stored.
        payloads = dict(PAYLOADS_BY_PROMPT)
        payloads["l4_operational_bi"] = {
            "signals": [],
            "broker_signals": [
                {
                    "broker_name": "Marcus Trent",
                    "polarity": "NEGATIVE",
                    "issue": "Gave the member incorrect advice.",
                    "evidence_turn_seq": 3,
                    "quote": "",
                }
            ],
        }

        analysis, _ = await analyse(taxonomy, rubric, ScriptedLayerProvider(payloads))

        assert analysis.broker_signals == ()
        assert not analysis.has_broker_attribution


class TestLayerFailure:
    async def test_an_additive_layer_failure_degrades_that_layer_only(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        provider = ScriptedLayerProvider(
            failures={"l5_assist": ProviderResponseError("Model would not comply.")}
        )

        analysis, store = await analyse(taxonomy, rubric, provider)

        l5 = analysis.layer(Layer.L5)
        assert l5 is not None
        assert l5.payload[UNAVAILABLE_KEY] is True
        assert "would not comply" in str(l5.payload[REASON_KEY])
        # The call is still scored, classified and stored.
        assert analysis.score.tier is Tier.POOR
        assert len(store.saved) == 1

    async def test_an_unavailable_layer_is_distinguishable_from_an_empty_one(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        empty = dict(PAYLOADS_BY_PROMPT)
        empty["l5_assist"] = {"events": []}
        found_nothing, _ = await analyse(taxonomy, rubric, ScriptedLayerProvider(empty))

        failed, _ = await analyse(
            taxonomy,
            rubric,
            ScriptedLayerProvider(failures={"l5_assist": ProviderResponseError("down")}),
        )

        nothing_layer = found_nothing.layer(Layer.L5)
        failed_layer = failed.layer(Layer.L5)
        assert nothing_layer is not None and failed_layer is not None
        assert UNAVAILABLE_KEY not in nothing_layer.payload
        assert failed_layer.payload[UNAVAILABLE_KEY] is True

    async def test_an_essential_layer_failure_abandons_the_analysis(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        # Without L2 there is no category and no outcome; storing a call anyway
        # would put a hole in every dashboard figure.
        provider = ScriptedLayerProvider(
            failures={"l2_insights": ProviderResponseError("Model would not comply.")}
        )
        use_case, store = build(taxonomy, rubric, provider)

        with pytest.raises(ProviderResponseError):
            await use_case.execute(AnalyzeTranscriptCommand(transcript=CALL_89), provider)

        assert store.saved == []


class TestInputValidation:
    async def test_text_without_speaker_prefixes_is_rejected_before_any_model_call(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        provider = ScriptedLayerProvider()
        use_case, _ = build(taxonomy, rubric, provider)

        with pytest.raises(ValidationError):
            await use_case.execute(AnalyzeTranscriptCommand(transcript="a wall of text"), provider)

        assert provider.prompts_seen == []

    async def test_an_oversized_transcript_is_refused(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        provider = ScriptedLayerProvider()
        use_case, _ = build(taxonomy, rubric, provider)

        with pytest.raises(ValidationError, match="too long"):
            await use_case.execute(
                AnalyzeTranscriptCommand(transcript="Agent: " + "x" * 200_001), provider
            )


class TestPromptContext:
    async def test_each_layer_receives_the_numbered_transcript(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        # Turn indices are how the model cites evidence; without them the quote
        # check has nothing to anchor to.
        provider = ScriptedLayerProvider()

        await analyse(taxonomy, rubric, provider)

        assert "[5] MEMBER" in provider.rendered["l3_quality"]

    async def test_later_layers_receive_what_earlier_layers_established(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        provider = ScriptedLayerProvider()

        await analyse(taxonomy, rubric, provider)

        assert "clinical_risk" in provider.rendered["l2_insights"]
        assert "Computed agent score" in provider.rendered["l4_operational_bi"]

    async def test_the_rubric_dimensions_are_described_to_the_scoring_layer(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        provider = ScriptedLayerProvider()

        await analyse(taxonomy, rubric, provider)

        assert "escalation_appropriateness" in provider.rendered["l3_quality"]


class TestAttributionEvidence:
    """A broker record names a real person, so its evidence is checked too.

    Found by a live run: the local model, having no broker to report, filled the
    fields with the literal string "None" and the record was stored. Requiring
    the evidence to be *present* was not enough — it has to be *real*.
    """

    async def test_a_placeholder_attribution_is_discarded(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        payloads = dict(PAYLOADS_BY_PROMPT)
        payloads["l4_operational_bi"] = {
            "signals": [],
            "broker_signals": [
                {
                    "broker_name": "None",
                    "polarity": "NEGATIVE",
                    "issue": "No broker was mentioned by the member.",
                    "evidence_turn_seq": 0,
                    "quote": "None",
                }
            ],
        }

        analysis, _ = await analyse(taxonomy, rubric, ScriptedLayerProvider(payloads))

        assert analysis.broker_signals == ()
        assert len(analysis.rejected_attribution_notes) == 1
        assert "does not appear in turn 0" in analysis.rejected_attribution_notes[0]

    async def test_an_attribution_citing_a_missing_turn_is_discarded(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        payloads = dict(PAYLOADS_BY_PROMPT)
        payloads["l4_operational_bi"] = {
            "signals": [],
            "broker_signals": [
                {
                    "broker_name": "Marcus Trent",
                    "polarity": "NEGATIVE",
                    "issue": "Told the member no prior authorization was needed.",
                    "evidence_turn_seq": 99,
                    "quote": "My broker, Marcus Trent, told me I didn't need one.",
                }
            ],
        }

        analysis, _ = await analyse(taxonomy, rubric, ScriptedLayerProvider(payloads))

        assert analysis.broker_signals == ()
        assert "does not exist" in analysis.rejected_attribution_notes[0]

    async def test_a_genuine_attribution_survives(self, taxonomy: Taxonomy, rubric: Rubric) -> None:
        # The rule must not be so strict that it discards real evidence.
        payloads = dict(PAYLOADS_BY_PROMPT)
        payloads["l4_operational_bi"] = {
            "signals": [],
            "broker_signals": [
                {
                    "broker_name": "Brad",
                    "polarity": "NEGATIVE",
                    "issue": "Quoted the plan rate without engaging with the member's concern.",
                    "evidence_turn_seq": 4,
                    "quote": "That's the plan rate.",
                }
            ],
        }

        analysis, _ = await analyse(taxonomy, rubric, ScriptedLayerProvider(payloads))

        assert len(analysis.broker_signals) == 1
        assert analysis.rejected_attribution_notes == ()

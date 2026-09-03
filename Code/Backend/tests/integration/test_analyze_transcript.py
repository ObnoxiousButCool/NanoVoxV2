"""The five-layer pipeline, end to end, against Call #89 without a model.

This is the P3 exit criterion expressed as tests: pasting Call #89's transcript
must produce a complete, evidence-anchored L1-L5 analysis.
"""

from __future__ import annotations

from typing import Any

import pytest

from application.dto.analysis_schemas import build_analysis_schemas
from application.ports.llm_provider import LlmRequest, StructuredResult, TModel
from application.ports.redaction import NoRedaction
from application.use_cases.analyze_transcript import (
    REASON_KEY,
    UNAVAILABLE_KEY,
    AnalyzeTranscript,
    AnalyzeTranscriptCommand,
)
from domain.broker_evidence import compile_broker_terms
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
    L1_PAYLOAD,
    L3_PAYLOAD,
    PAYLOADS_BY_PROMPT,
    InMemoryAnalysisRepository,
    ScriptedLayerProvider,
    StubPromptSource,
)
from tests.support.clock import FixedClock
from tests.support.settings import make_settings
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
        # The shipped vocabulary, not a test-only one: the evidence rule these
        # tests exercise is the rule the application actually applies.
        broker_terms=compile_broker_terms(make_settings().broker_evidence_terms),
    )
    return use_case, store


async def analyse(
    taxonomy: Taxonomy, rubric: Rubric, provider: ScriptedLayerProvider
) -> tuple[CallAnalysis, InMemoryAnalysisRepository]:
    use_case, store = build(taxonomy, rubric, provider)
    stored = await use_case.execute(AnalyzeTranscriptCommand(transcript=CALL_89), provider)
    return stored.analysis, store


class TestSignalEvidence:
    """A signal has to prove itself, like every other stored claim."""

    async def test_an_evidenced_signal_reaches_the_score(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        analysis, _ = await analyse(taxonomy, rubric, ScriptedLayerProvider())

        assert "clinical_risk" in analysis.signal_codes
        # And it does what a signal is for: the score is held for review.
        assert analysis.score.status is ScoreStatus.PROVISIONAL

    async def test_a_signal_whose_quote_is_not_in_the_call_is_discarded(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        # The failure this check exists for: clinical_risk asserted on a call
        # whose transcript never said it. Eight of fifty ancillary-benefit calls
        # were flagged this way, every one wrong, each withholding a score.
        provider = ScriptedLayerProvider(
            payloads={
                **PAYLOADS_BY_PROMPT,
                "l1_understanding": {
                    **L1_PAYLOAD,
                    "signals": [
                        {
                            "code": "clinical_risk",
                            "evidence_turn_seq": 1,
                            "quote": "my prescription changed",
                        }
                    ],
                }
            }
        )
        analysis, _ = await analyse(taxonomy, rubric, provider)

        assert analysis.signal_codes == ()
        # Recorded, not silently dropped: a model inventing evidence is a
        # finding about the model.
        assert any("clinical_risk" in note for note in analysis.rejected_marker_notes)

    async def test_a_discarded_signal_no_longer_withholds_the_score(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        # The consequence that matters: an unevidenced signal used to open a
        # clinical review queue nobody could act on.
        provider = ScriptedLayerProvider(
            payloads={
                **PAYLOADS_BY_PROMPT,
                "l1_understanding": {
                    **L1_PAYLOAD,
                    "signals": [
                        {
                            "code": "clinical_risk",
                            "evidence_turn_seq": 0,
                            "quote": "nothing like this was said",
                        }
                    ],
                }
            }
        )
        analysis, _ = await analyse(taxonomy, rubric, provider)

        assert analysis.score.status is ScoreStatus.CONFIRMED


class TestDuration:
    """The stated duration beats the model's estimate."""

    async def test_a_stated_duration_wins(self, taxonomy: Taxonomy, rubric: Rubric) -> None:
        # The corpus files carry the real figure in their header; L2 only ever
        # estimated it from the words. Every duration figure on the dashboard is
        # built on this, so the source has to win.
        provider = ScriptedLayerProvider()
        use_case, _ = build(taxonomy, rubric, provider)

        stored = await use_case.execute(
            AnalyzeTranscriptCommand(transcript=CALL_89, duration_minutes=11), provider
        )

        # The L2 stub says 6.
        assert stored.analysis.duration_minutes == 11

    async def test_the_estimate_is_used_when_the_source_states_nothing(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        # A pasted transcript has no header. The estimate is then the only
        # figure available, and dropping it would empty the minute charts.
        provider = ScriptedLayerProvider()
        use_case, _ = build(taxonomy, rubric, provider)

        stored = await use_case.execute(AnalyzeTranscriptCommand(transcript=CALL_89), provider)

        assert stored.analysis.duration_minutes == 6


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
        assert store.saved[0].reference == analysis.reference == "P0001"


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

    async def test_an_attribution_naming_the_agent_is_discarded(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        """The agent who answered the call is not the member's broker.

        A verbatim quote of the agent speaking is real evidence of nothing but
        the agent speaking. Left unchecked this put the agents themselves on a
        screen that names people for Compliance review.
        """
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

        assert analysis.broker_signals == ()
        assert "names the agent" in analysis.rejected_attribution_notes[0]

    async def test_an_attribution_whose_quote_names_no_broker_is_discarded(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        """A surgeon named in a real quote is still not a broker.

        Doctors, pharmacies and the plan itself all reached the broker scorecard
        this way: the words were genuinely said, but they say nothing about a
        broker relationship.
        """
        payloads = dict(PAYLOADS_BY_PROMPT)
        payloads["l4_operational_bi"] = {
            "signals": [],
            "broker_signals": [
                {
                    "broker_name": "Dr. Ridgeway",
                    "polarity": "NEGATIVE",
                    "issue": "Sent the member to urgent care.",
                    "evidence_turn_seq": 8,
                    "quote": "There's one on Ridgeway if you're nearby.",
                }
            ],
        }

        analysis, _ = await analyse(taxonomy, rubric, ScriptedLayerProvider(payloads))

        assert analysis.broker_signals == ()
        assert "does not name a broker relationship" in analysis.rejected_attribution_notes[0]

    async def test_a_genuine_attribution_survives(self, taxonomy: Taxonomy, rubric: Rubric) -> None:
        # The rule must not be so strict that it discards real evidence: a member
        # naming their own broker is exactly what the screen is for.
        named_broker = chr(10).join(
            [
                "Agent Brad: Choice Administrators, Brad.",
                "Member: My broker, Marcus Trent, told me I didn't need prior authorisation.",
                "Agent Brad: Let me check that for you.",
            ]
        )
        payloads = dict(PAYLOADS_BY_PROMPT)
        payloads["l4_operational_bi"] = {
            "signals": [],
            "broker_signals": [
                {
                    "broker_name": "Marcus Trent",
                    "polarity": "NEGATIVE",
                    "issue": "Told the member no prior authorisation was needed.",
                    "evidence_turn_seq": 1,
                    "quote": "My broker, Marcus Trent, told me I didn't need prior authorisation.",
                }
            ],
        }
        use_case, _ = build(taxonomy, rubric, ScriptedLayerProvider(payloads))

        stored = await use_case.execute(
            AnalyzeTranscriptCommand(transcript=named_broker),
            ScriptedLayerProvider(payloads),
        )

        assert len(stored.analysis.broker_signals) == 1
        assert stored.analysis.broker_signals[0].broker_name == "Marcus Trent"
        assert stored.analysis.rejected_attribution_notes == ()


class _RetryingProvider(ScriptedLayerProvider):
    """Answers L4 differently the second time it is asked.

    The repair only means anything if the model can say something new; a provider
    that repeats itself would prove the retry happened but not that it works.
    """

    def __init__(self, first: dict[str, Any], second: dict[str, Any] | None) -> None:
        payloads = dict(PAYLOADS_BY_PROMPT)
        payloads["l4_operational_bi"] = first
        super().__init__(payloads)
        self._second = second
        self.l4_calls = 0
        self.corrections: list[str] = []

    async def complete(self, request: LlmRequest[TModel]) -> StructuredResult[TModel]:
        if request.prompt_id == "l4_operational_bi":
            self.l4_calls += 1
            if self.l4_calls > 1:
                self.corrections.append(request.prompt)
                if self._second is not None:
                    self._payloads["l4_operational_bi"] = self._second
        return await super().complete(request)


# Turn 1 reads: "Hello. I wanted to ask what my emergency room copay is. Member
# The repair scenario needs a turn that both names a broker and has something
# skippable in the middle. BROKER_CALL below is that turn: the elided quote joins
# its first and last parts across the member ID, so every word is real while the
# run is not continuous — exactly how a genuine attribution was lost.
BROKER_CALL = chr(10).join(
    [
        "Agent Brad: Choice Administrators, Brad.",
        "Member: My broker, Marcus Trent, told me — member ID CHM-2208814 — "
        "that I did not need prior authorisation.",
        "Agent Brad: Let me look into that.",
    ]
)
ELIDED_QUOTE = "My broker, Marcus Trent, told me that I did not need prior authorisation."
CONTIGUOUS_QUOTE = "My broker, Marcus Trent, told me"


async def _analyse_broker_call(
    taxonomy: Taxonomy, rubric: Rubric, provider: ScriptedLayerProvider
) -> CallAnalysis:
    """Analyse a transcript in which the member does name a broker."""
    use_case, _ = build(taxonomy, rubric, provider)
    stored = await use_case.execute(AnalyzeTranscriptCommand(transcript=BROKER_CALL), provider)
    return stored.analysis


def _attribution(quote: str) -> dict[str, Any]:
    return {
        "signals": [],
        "broker_signals": [
            {
                "broker_name": "Marcus Trent",
                "polarity": "NEGATIVE",
                "issue": "Told the member no prior authorization was needed.",
                "evidence_turn_seq": 1,
                "quote": quote,
            }
        ],
    }


class TestAttributionRepair:
    async def test_an_elided_quote_is_re_asked_and_recovered(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        provider = _RetryingProvider(_attribution(ELIDED_QUOTE), _attribution(CONTIGUOUS_QUOTE))

        analysis = await _analyse_broker_call(taxonomy, rubric, provider)

        assert provider.l4_calls == 2
        assert len(analysis.broker_signals) == 1
        assert analysis.broker_signals[0].quote == CONTIGUOUS_QUOTE
        assert analysis.rejected_attribution_notes == ()

    async def test_the_retry_is_told_what_failed_and_shown_the_turn(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        # Without the turn's text the model has nothing new to copy from, and the
        # second answer is as likely to be wrong as the first.
        provider = _RetryingProvider(_attribution(ELIDED_QUOTE), _attribution(CONTIGUOUS_QUOTE))

        await _analyse_broker_call(taxonomy, rubric, provider)

        correction = provider.corrections[0]
        assert "CORRECTION" in correction
        assert "Marcus Trent" in correction
        assert "member ID CHM-2208814" in correction

    async def test_a_repair_that_fails_again_leaves_the_attribution_rejected(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        # The rule is not relaxed by asking twice: a quote that never matches is
        # still not evidence.
        provider = _RetryingProvider(_attribution(ELIDED_QUOTE), None)

        analysis = await _analyse_broker_call(taxonomy, rubric, provider)

        assert provider.l4_calls == 2
        assert analysis.broker_signals == ()
        assert len(analysis.rejected_attribution_notes) == 1

    async def test_a_clean_first_answer_is_not_re_asked(
        self, taxonomy: Taxonomy, rubric: Rubric
    ) -> None:
        # The repair costs a model call, so it must only run when one is needed.
        provider = _RetryingProvider(_attribution(CONTIGUOUS_QUOTE), None)

        analysis = await _analyse_broker_call(taxonomy, rubric, provider)

        assert provider.l4_calls == 1
        assert len(analysis.broker_signals) == 1

"""Test doubles for the analysis pipeline."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from application.ports.analysis_repository import AnalysisRepository
from application.ports.llm_provider import (
    LLMProvider,
    LlmRequest,
    ProviderStatus,
    StructuredResult,
    TModel,
    TokenUsage,
)
from application.ports.prompts import PromptSource, RenderedPrompt
from domain.entities.analysis import CallAnalysis
from domain.errors import NanoVoxError

# Layer payloads for Call #89, as a competent model would answer.
L1_PAYLOAD: dict[str, Any] = {
    "call_type": "Emergency room copay enquiry",
    "member_sentiment_start": "WORRIED",
    "member_sentiment_end": "DISMISSED",
    "agent_tone": "transactional",
    "member_context": "Member aged 68 on a CalChoice HMO plan.",
    "key_terms": ["chest pressure", "arm ache", "ER copay", "urgent care"],
    "signals": ["clinical_risk"],
}

L2_PAYLOAD: dict[str, Any] = {
    "title": "ER copay question that was a cardiac presentation",
    "summary": "The member asked which setting cost less, then disclosed overnight chest "
    "pressure and an aching arm. The agent repeated the cheaper option and ended the call.",
    "category": "coverage_benefits",
    "resolution": "UNRESOLVED",
    "topics": ["triage", "urgency cue missed", "cost steering"],
    "key_moments": [
        {"sequence": 1, "description": "Member opens with a cost question.", "is_negative": False},
        {"sequence": 2, "description": "Member discloses chest pressure.", "is_negative": True},
    ],
    "duration_minutes": 6,
}

L3_PAYLOAD: dict[str, Any] = {
    "agent_name": "Brad",
    "markers": [
        {
            "polarity": "NEGATIVE",
            "dimension": "escalation_appropriateness",
            "description": "Did not recognise chest pressure with arm pain as an emergency.",
            "evidence_turn_seq": 5,
            "quote": "I've had this pressure in my chest since last night",
        },
        {
            "polarity": "NEGATIVE",
            "dimension": "escalation_appropriateness",
            "description": "Did not advise calling 911 or recommend emergency evaluation.",
            "evidence_turn_seq": 6,
            "quote": "urgent care is cheaper if you want to go that route",
        },
        {
            "polarity": "NEGATIVE",
            "dimension": "compliance_disclosure",
            "description": "Steered toward a lower level of care on cost grounds.",
            "evidence_turn_seq": 8,
            "quote": "Urgent care can handle most things",
        },
        {
            "polarity": "NEGATIVE",
            "dimension": "resolution_ownership",
            "description": "Did not offer a nurse line transfer.",
            "evidence_turn_seq": 8,
            "quote": "There's one on Ridgeway if you're nearby",
        },
        {
            "polarity": "NEGATIVE",
            "dimension": "resolution_ownership",
            "description": "Closed a patient-safety call as routine.",
            "evidence_turn_seq": 8,
            "quote": "Urgent care can handle most things",
        },
        {
            "polarity": "POSITIVE",
            "dimension": "accuracy",
            "description": "Copay figures were correct.",
            "evidence_turn_seq": 2,
            "quote": "ER copay is $250, waived if you're admitted",
        },
    ],
}

L4_PAYLOAD: dict[str, Any] = {
    "signals": [
        {
            "category": "compliance_risk",
            "severity": "CRITICAL",
            "narrative": "Cost information influenced a care-setting decision after symptoms "
            "were disclosed.",
            "recommended_action": "Contact this member for a welfare check.",
        }
    ],
    "broker_signals": [],
}

L5_PAYLOAD: dict[str, Any] = {
    "events": [
        {
            "outcome": "SHOULD_HAVE_FIRED",
            "trigger": "Symptom keywords with member age 68",
            "recommendation": "Mandatory nurse line transfer; suppress the cost comparison.",
            "severity": "CRITICAL",
            "at_turn_seq": 5,
            "timestamp_label": "2:30",
        }
    ],
}

PAYLOADS_BY_PROMPT = {
    "l1_understanding": L1_PAYLOAD,
    "l2_insights": L2_PAYLOAD,
    "l3_quality": L3_PAYLOAD,
    "l4_operational_bi": L4_PAYLOAD,
    "l5_assist": L5_PAYLOAD,
}


class ScriptedLayerProvider(LLMProvider):
    """Answers each layer prompt from a prepared payload.

    The pipeline is exercised without a model: analysis behaviour has to be
    testable without a network, a GPU, or a bill.
    """

    def __init__(
        self,
        payloads: dict[str, dict[str, Any]] | None = None,
        *,
        failures: dict[str, Exception] | None = None,
    ) -> None:
        self._payloads = payloads or dict(PAYLOADS_BY_PROMPT)
        self._failures = failures or {}
        self.prompts_seen: list[str] = []
        self.rendered: dict[str, str] = {}

    @property
    def name(self) -> str:
        return "scripted"

    @property
    def model(self) -> str:
        return "scripted-model"

    async def complete(self, request: LlmRequest[TModel]) -> StructuredResult[TModel]:
        self.prompts_seen.append(request.prompt_id)
        self.rendered[request.prompt_id] = request.prompt

        failure = self._failures.get(request.prompt_id)
        if failure is not None:
            raise failure

        payload = self._payloads.get(request.prompt_id, {})
        value = request.response_model.model_validate(payload)
        return StructuredResult(
            value=value,
            provider=self.name,
            model=self.model,
            prompt_id=request.prompt_id,
            prompt_version=request.prompt_version,
            usage=TokenUsage(input_tokens=100, output_tokens=50),
            latency_ms=1.0,
            attempts=1,
        )

    async def status(self) -> ProviderStatus:
        return ProviderStatus(name=self.name, model=self.model, reachable=True)


class StubPromptSource(PromptSource):
    """Renders a recognisable placeholder instead of reading files."""

    def __init__(self, version: str = "1.0.0") -> None:
        self._version = version

    def render(self, prompt_id: str, **values: Any) -> RenderedPrompt:
        body = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
        return RenderedPrompt(id=prompt_id, version=self._version, text=f"[{prompt_id}]\n{body}")

    def version_of(self, prompt_id: str) -> str:
        return self._version


class InMemoryAnalysisRepository(AnalysisRepository):
    """Keeps saved analyses in a list."""

    def __init__(self) -> None:
        self.saved: list[CallAnalysis] = []

    async def save(self, analysis: CallAnalysis) -> int:
        self.saved.append(analysis)
        return len(self.saved)

    async def get(self, call_id: int) -> CallAnalysis | None:
        index = call_id - 1
        if 0 <= index < len(self.saved):
            return self.saved[index]
        return None

    async def next_reference(self) -> str:
        return f"P{len(self.saved) + 1:04d}"

    async def existing_references(self, references: Sequence[str]) -> frozenset[str]:
        stored = {analysis.reference for analysis in self.saved}
        return frozenset(stored.intersection(references))

    async def delete_by_reference(self, reference: str) -> bool:
        remaining = [item for item in self.saved if item.reference != reference]
        removed = len(remaining) != len(self.saved)
        self.saved = remaining
        return removed


class FailingRepository(InMemoryAnalysisRepository):
    """A repository whose writes fail."""

    async def save(self, analysis: CallAnalysis) -> int:
        raise NanoVoxError("The database is unavailable.")


class SentimentOnly(BaseModel):
    """Minimal model used where a response shape is irrelevant."""

    sentiment: str

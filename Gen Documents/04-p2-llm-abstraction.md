# P2 — LLM abstraction: completion record

**Status:** Complete, with one exit criterion **partially met** — see §2.
**Date:** 2026-08-28
**Plan reference:** [01-implementation-plan.md](01-implementation-plan.md) §7.1, §10 phase P2

---

## 1. Gate results

| Gate | Result |
|---|---|
| Backend format / lint | Pass |
| Backend types — mypy strict | Pass, 112 files |
| Architecture contracts | **3 kept, 0 broken** |
| Backend tests | **307 passed** (was 222), coverage **94.2%** (floor 85%) |
| Frontend lint / types / tests | Pass, 30 tests, 100% statements |

`./scripts/verify.sh` → **all gates passed**.

## 2. Exit criteria — one caveat, stated plainly

| Criterion (plan §10) | Result |
|---|---|
| Contract suite passes against a fake provider | **Met** — 48 contract tests |
| Live smoke test on Ollama | **Met** — real call, real structured output (§4) |
| Live smoke test on one cloud provider | **NOT met — blocked, not skipped** |

**No cloud credentials exist on this machine.** `OPENAI_API_KEY` and
`ANTHROPIC_API_KEY` are both unset, so neither cloud adapter has been executed
against a real endpoint. What has been done instead:

- Both adapters are driven end to end in tests through their real SDK client
  objects, with only the final transport call substituted — so request shaping,
  error translation and status classification are all exercised.
- The specific things that would fail *only* at runtime are pinned by assertion:
  no sampling parameters to Anthropic, no date suffix on the model ID,
  `strict: true` and closed `additionalProperties` for OpenAI.

That is genuinely weaker than a live call, and I am not going to describe it as
equivalent. **To close this, set one key in `Code/Backend/.env` and run:**

```bash
Code/Backend/.venv/Scripts/python.exe -m frameworks_drivers.cli.smoke --call --provider anthropic
```

## 3. What was built

| Component | Responsibility |
|---|---|
| `application/ports/llm_provider.py` | The port. Callers ask for a **validated pydantic object**, never for text |
| `infrastructure/llm/base.py` | Retry, repair, audit — implemented once, shared by every adapter |
| `providers/ollama.py` | Local default; schema-constrained decoding over plain HTTP |
| `providers/anthropic_provider.py` | Official `anthropic` SDK, `messages.parse` with `output_format` |
| `providers/openai_provider.py` | Official `openai` SDK, strict `json_schema` response format |
| `providers/azure_foundry.py` | Registered, fails fast, never falls back (DEC-05) |
| `registry.py` | Name → adapter; a missing key becomes a clear error |
| `prompts.py` + `prompts/*.md` | Versioned templates; the version is stored with every result |
| `logging/llm_audit.py` | One line per attempt, in its own file |
| `cli/smoke.py` | Provider availability, and a real call with `--call` |
| `GET /api/v1/providers` | Feeds the provider picker, with reasons for unusable ones |

**The port returns objects, not strings.** A caller cannot accidentally consume
unparsed output, and "did the model return the right shape?" is answered in one
place rather than at each call site.

**Retry policy lives in the base class, not the adapters.** Transient failures
(network, timeout, 429, 5xx) retry with exponential backoff. A schema violation
retries *exactly once*, feeding the validation errors back as a correction — a
model that ignored the correction will ignore it again, and repeating just spends
money on the same mistake. Both SDKs' own retry loops are disabled
(`max_retries=0`) so there is one retry policy, not two multiplying, and so every
attempt reaches the audit log.

## 4. Live verification (Ollama)

```
Registered providers:
  OK ollama          qwen2.5:7b-instruct          (default)
  -- openai          gpt-4o-mini      Provider 'openai' was selected but OPENAI_API_KEY is not set.
  -- anthropic       claude-opus-5    Provider 'anthropic' was selected but ANTHROPIC_API_KEY is not set.
  -- azure_foundry   not-configured   Azure AI Foundry is registered but not implemented in this build.

Calling ollama / qwen2.5:7b-instruct ...
  sentiment     NEUTRAL
  justification The sentence expresses a physical symptom and a decision to check
                costs, without strong positive or negative emotions.
  confidence    0.8
  attempts 1  repaired False  18232 ms  tokens 113+48
```

Schema in, validated object out, first attempt, no repair needed. The matching
audit line:

```json
{"provider": "ollama", "model": "qwen2.5:7b-instruct", "prompt_id": "provider_check",
 "prompt_version": "1.0.0", "attempt": 1, "outcome": "ok", "latency_ms": 18231.67,
 "input_tokens": 113, "output_tokens": 48, "usage_reported": true}
```

**Note the latency: 18 seconds for a one-sentence classification.** A 5-layer
analysis of a full transcript on this hardware will be substantially slower. That
is a real constraint on the P7 corpus run over 100 calls, and it is better known
now than discovered during a demo.

## 5. Decisions taken during P2

| # | Decision | Reasoning |
|---|---|---|
| P2-1 | **Official SDKs for Anthropic and OpenAI**, not hand-rolled HTTP as plan §7.1 implied | They track API changes, expose typed error hierarchies, and are the supported path for structured output. Ollama stays on plain HTTP: it is one POST to a local server, and the local-first path should not carry an extra dependency. |
| P2-2 | **Anthropic uses structured outputs, not the tool-use trick** the plan named | `messages.parse` with `output_format` is the current mechanism for exactly this job and guarantees the response parses. Forcing a schema through a tool definition is the older workaround. |
| P2-3 | **No sampling parameters sent to Anthropic** | `temperature` / `top_p` / `top_k` are removed on current Claude models and are **rejected with a 400**. Determinism there comes from the schema constraint, not from `temperature=0`. This would have failed only at runtime; it is now pinned by a test. |
| P2-4 | **No global `LLM_TEMPERATURE` setting** | It cannot mean the same thing across providers — one of them rejects it outright. Deterministic decoding is a design invariant (a named constant), applied where the provider supports it. |
| P2-5 | **`additionalProperties: false` injected recursively for OpenAI strict mode** | Strict mode requires it on every object; pydantic emits it on none. Without this the API rejects the schema outright. |
| P2-6 | **`claude-opus-5` as the Anthropic default** | Per current Anthropic guidance: use the most capable model unless told otherwise, and never append a date suffix to the ID. |
| P2-7 | **`qwen2.5:7b-instruct` as the Ollama default** | The 7–8B instruct model proposed in plan §15, and already installed on this machine. Still the open question in §7 below. |
| P2-8 | **Provider selection never falls back** | A caller who asked for Azure and quietly received OpenAI output would have no way to know their governance requirement was not met. Unconfigured means fail, with the variable named. |
| P2-9 | **The audit logger is pinned at INFO**, independent of `LOG_LEVEL` | It is a cost and provenance record. Setting `LOG_LEVEL=WARNING` for quieter operations must not silently stop collecting it. |
| P2-10 | **`LOG_LLM_PROMPTS` defaults to false** | Transcripts are member conversations. An audit log is not the place to accumulate them; the flag exists for prompt debugging. |
| P2-11 | **`/providers` lists unusable providers with the reason** | An empty list tells the user nothing about why they cannot proceed. "OPENAI_API_KEY is not set" is actionable; a missing row is not. |

## 6. Notes for whoever reviews this

Two things that cost time and are worth knowing:

- **The two SDKs use different HTTP libraries.** `anthropic` 1.x is built on
  `httpx2`; `openai` 2.x is on `httpx` (v1). Objects from one are rejected by the
  other. Both are declared explicitly rather than relied on transitively.
- **A running Ollama server missing the model** reports as unreachable with
  `Run: ollama pull qwen2.5:7b-instruct` rather than a bare "down". The
  difference between "no server" and "no model" is the whole of the fix.

## 7. Open question, now live

**Which Ollama model should be the local default?** `qwen2.5:7b-instruct` is in
place and works. The 18-second latency on a trivial prompt suggests the tradeoff
between quality and speed deserves a deliberate choice before the P7 corpus run.
`llama3.1:latest` (4.9 GB) and `gemma3:4b` are also installed and could be
compared. The P8 fidelity report is designed to settle this with evidence; an
earlier preference saves a cycle.

## 8. Next phase

**P3 — Analysis pipeline.** The `AnalyzeTranscript` use case, the transcript
parser, the L1–L5 prompts and their response schemas, persistence, and
`POST /api/v1/analyses`. Exit criterion: pasting Call #89's transcript yields a
complete, evidence-anchored L1–L5 analysis.

This is where P1's rubric and P2's providers meet: the model returns markers, the
marker validator checks them against the transcript, and the rubric engine turns
the survivors into a score.

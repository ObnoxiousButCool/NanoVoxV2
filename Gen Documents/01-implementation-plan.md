# NanoVox V2 — Implementation Plan

**Document status:** Draft for approval
**Date:** 2026-08-28
**Author:** Chief Architect
**Scope:** Call Intelligence POC for Choice Administrators (member call centre)

---

## 1. Purpose and success criteria

Choice Administrators handles several thousand member calls a month with zero content
visibility — no scoring, no sentiment signal, no view of whether agents resolve issues.
This build delivers a working application that turns a pasted call transcript into the
NanoVox 5-layer output, persists it, and aggregates every analysed call into the
operational dashboards leadership needs.

**Definition of done**

| # | Criterion | Verification |
|---|---|---|
| D1 | A pasted transcript produces a complete L1–L5 analysis matching the depth of Call #89 in the prototype | Manual + golden-fixture test |
| D2 | Dashboard renders live-computed Overview, Agent Performance, Broker Scorecard and L4 Signal Distribution | Integration test against seeded DB |
| D3 | Provider and model are chosen by the end user at analysis time | E2E test across Ollama + one cloud provider |
| D4 | Zero hardcoded configuration — every URL, key, path, threshold, weight and taxonomy value is env- or config-file-driven | Static scan; grep audit gate in CI |
| D5 | Error logging is flag-controlled and writes to `C:\Technossus\Code\NanoVox-V2\Logs` | Runtime check with flag on and off |
| D6 | Clean Architecture dependency rule holds — domain depends on nothing | Automated import-linter contract |
| D7 | Code audit scores 10/10 with no carried technical debt | Section 13 checklist |

---

## 2. Confirmed decisions

These were settled with the product owner before planning and are binding for Phase 1.

| ID | Decision | Rationale / consequence |
|----|----------|-------------------------|
| **DEC-01** | **Corpus is re-analysed through the LLM**, not seeded from the authored panels | Dashboard is 100% model-derived and proves the pipeline end to end. Consequence: computed figures **will differ** from `call_corpus_v3_index.xlsx` and from the prototype's hardcoded numbers. This is expected and must be communicated, not hidden. |
| **DEC-02** | **Taxonomy = the 7 categories in the xlsx**, unchanged | Guarantees continuity with the index Rebekah has already seen. The 10–12 category expansion was raised and deliberately deferred; taxonomy lives in `config/taxonomy.yaml`, so growing it later is a config edit plus a re-classification run, not a code change. |
| **DEC-03** | **Agent score is computed deterministically from a rubric**; the LLM supplies evidence-anchored markers only | Same transcript + same rubric = same score, every marker traceable to a transcript quote. A bare LLM number is not auditable and drifts between providers. |
| **DEC-04** | **Paste transcript only.** No audio/ASR, no Outlook email ingestion in Phase 1 | Domain model is channel-agnostic so both are additive later (§12). No dead UI affordances — the prototype's "upload audio" wording is removed. |
| **DEC-05** | **Providers: Ollama, OpenAI, Anthropic.** Azure AI Foundry registered but not implemented | The Azure adapter exists as a registry entry that fails fast with an explicit "not implemented in this build" error. No silent fallback, no half-built path. |
| **DEC-06** | **Corpus re-analysis is triggered from the UI with live progress** | Requires a background job runner and a Server-Sent Events progress channel (§7.4). Best demo moment; scoped as its own phase. |
| **DEC-07** | No authentication in Phase 1 | POC runs on localhost. A documented seam exists at the API boundary; nothing is half-built. |
| **DEC-08** | No PHI redaction stage in Phase 1 | Corpus is synthetic. The pipeline carries a no-op `RedactionPort` so a real implementation drops in without touching use cases. Flagged as a **hard prerequisite before any real member data** reaches a cloud provider. |

### 2.1 Assumptions requiring no further approval

- **A1** — The prototype (`Documents/nanovox_ui_v3.html`) is a **look-and-feel and information-architecture reference**. Its numbers are illustrative; every figure in the built app is computed from SQLite.
- **A2** — Charts are reproduced with **pure CSS and inline SVG**, no charting library. The prototype's bar tracks and histogram are already CSS; a chart library would fight the design and add a dependency for no gain.
- **A3** — Ground truth from the authored `## AI Insights Panel` sections is **parsed and stored in a separate `ground_truth` table**, never mixed into dashboard data. It costs nothing extra (we already parse those files for transcripts) and enables the model-fidelity report in §11.2.

### 2.2 Source conflicts found and how they are resolved

| Conflict | Prototype | xlsx index | Resolution |
|---|---|---|---|
| Category counts | 6 + Uncategorised (31/27/15/8/8/6/3) | 7 (19/19/14/14/13/11/10) | xlsx taxonomy (DEC-02); counts computed live |
| Agent roster | 10 agents | 13 (adds Nicole, Tony, Priya) | 13 — agents derive from data, not a fixed list |
| Median score | 96 | per-agent 33.5–94.5, spread 22–98 | Computed live |
| First-contact resolution | 42% | RESOLVED 54%, PARTIALLY 16% | Computed live; FCR defined explicitly in §6.3 |
| Escalation rate / broker signals | 16% / 22 | ESCALATED 16 / 22 signals | Consistent — used as a pipeline sanity check |

`scripts/start.bat`, `start.sh` and `README.md` already exist from an earlier attempt. They
reference an **NVIDIA** provider that is not in scope, and are otherwise sound.
**Action:** keep them, adopt their module path (`frameworks_drivers.main:app`) as the
canonical naming, and correct the provider documentation.

---

## 3. Solution architecture

### 3.1 Clean Architecture layers (backend)

Dependencies point inward only. Enforced automatically by `import-linter` in CI, not by convention.

```
┌─────────────────────────────────────────────────────────────┐
│ frameworks_drivers/   FastAPI app, routers, DI container,    │
│                       SSE, exception handlers, middleware    │
├─────────────────────────────────────────────────────────────┤
│ infrastructure/       SQLite repositories, LLM adapters,     │
│                       corpus file reader, logging, config    │
├─────────────────────────────────────────────────────────────┤
│ application/          Use cases + PORTS (abstract interfaces)│
│                       AnalyzeTranscript, GetOverview, ...    │
├─────────────────────────────────────────────────────────────┤
│ domain/               Entities, value objects, rubric engine │
│                       Pure Python. No imports outside stdlib │
└─────────────────────────────────────────────────────────────┘
```

**The rubric engine lives in `domain/`.** It is pure, has no I/O, and is the most heavily
unit-tested component in the system — because it produces the number leadership trusts.

### 3.2 Folder structure

```
NanoVox-V2/
├─ Code/
│  ├─ Backend/
│  │  ├─ domain/
│  │  │  ├─ entities/          call.py, transcript.py, turn.py, agent.py,
│  │  │  │                     broker.py, analysis.py, score_marker.py,
│  │  │  │                     l4_signal.py, assist_event.py
│  │  │  ├─ value_objects/     score.py, tier.py, resolution.py,
│  │  │  │                     sentiment_arc.py, category.py, severity.py
│  │  │  ├─ scoring/           rubric.py, rubric_engine.py, gates.py
│  │  │  ├─ aggregation/       attention_rules.py, significance.py
│  │  │  └─ errors.py
│  │  ├─ application/
│  │  │  ├─ ports/             llm_provider.py, call_repository.py,
│  │  │  │                     analysis_repository.py, corpus_reader.py,
│  │  │  │                     redaction.py, clock.py, unit_of_work.py,
│  │  │  │                     run_repository.py, progress_publisher.py
│  │  │  ├─ dto/               request/response models (pydantic)
│  │  │  └─ use_cases/
│  │  │     ├─ analyze_transcript.py
│  │  │     ├─ list_calls.py
│  │  │     ├─ get_call_detail.py
│  │  │     ├─ get_overview.py
│  │  │     ├─ get_agent_performance.py
│  │  │     ├─ get_broker_scorecard.py
│  │  │     ├─ get_signal_distribution.py
│  │  │     ├─ list_providers.py
│  │  │     └─ run_corpus_analysis.py
│  │  ├─ infrastructure/
│  │  │  ├─ persistence/       engine.py, models.py (SQLAlchemy),
│  │  │  │                     repositories/, migrations/ (alembic)
│  │  │  ├─ llm/               base.py, registry.py, schemas.py,
│  │  │  │                     prompts/ (versioned templates),
│  │  │  │                     providers/{ollama,openai,anthropic,azure}.py
│  │  │  ├─ corpus/            markdown_corpus_reader.py, ground_truth_parser.py
│  │  │  ├─ logging/           setup.py, correlation.py, llm_audit.py
│  │  │  └─ config/            settings.py, taxonomy_loader.py, rubric_loader.py
│  │  ├─ frameworks_drivers/
│  │  │  ├─ main.py            app factory + lifespan
│  │  │  ├─ container.py       dependency wiring
│  │  │  ├─ api/v1/            routers: calls, analyses, dashboard,
│  │  │  │                     providers, corpus_runs, health
│  │  │  ├─ middleware/        correlation_id, request_logging, error_handler
│  │  │  └─ sse/               progress_stream.py
│  │  ├─ config/               taxonomy.yaml, rubric.yaml, attention_rules.yaml,
│  │  │                        providers.yaml
│  │  ├─ tests/                unit/ integration/ contract/ fixtures/
│  │  ├─ .env.example
│  │  ├─ pyproject.toml        ruff, mypy, pytest, coverage, import-linter
│  │  └─ requirements.txt
│  └─ Frontend/
│     ├─ src/
│     │  ├─ app/               router, providers, layout/ (AppShell, Rail)
│     │  ├─ features/
│     │  │  ├─ overview/       AttentionQueue, MetricStrip, ScoreHistogram,
│     │  │  │                  ResolutionByAgent, CategoryBars, SignalsByOwner
│     │  │  ├─ calls/          CallsTable, filters
│     │  │  ├─ call-detail/    Hero, LayerL1..L5, TranscriptView, Sidebar
│     │  │  ├─ brokers/        BrokerScorecard
│     │  │  ├─ analyze/        TranscriptInput, ProviderPicker, ResultView
│     │  │  └─ corpus-run/     RunTrigger, ProgressPanel (SSE)
│     │  ├─ shared/
│     │  │  ├─ api/            client, generated types, query hooks
│     │  │  ├─ ui/             Card, Chip, Badge, Bar, Ring, Alert, Table
│     │  │  ├─ hooks/          useCollapsibleRail, useEventSource
│     │  │  └─ styles/         tokens.css (prototype variables verbatim)
│     │  └─ entities/          domain types mirrored from OpenAPI
│     ├─ .env.example          VITE_API_BASE_URL, VITE_APP_NAME
│     ├─ vite.config.ts  tsconfig.json  eslint.config.js  vitest.config.ts
│     └─ package.json
├─ Gen Documents/              this plan + generated design docs
├─ Documents/                  source material (read-only)
├─ Samples/                    100 call transcripts (read-only input)
├─ Logs/                       runtime logs (git-ignored)
├─ Data/                       nanovox.db (git-ignored, path is env-driven)
└─ scripts/                    existing start.bat / start.sh / README.md
```

---

## 4. Domain model

### 4.1 Core entities

- **Call** — one member interaction. Holds category, agent, resolution, sentiment arc, duration, computed score, tier, score status, and provenance (provider, model, prompt version, analysed-at).
- **Transcript** → ordered **Turns** (`seq`, `speaker_role` ∈ {AGENT, MEMBER, SYSTEM}, `speaker_name`, `text`). Turn indices are the anchor for every piece of evidence in the system.
- **Analysis** — the 5-layer output, one row per layer with a validated JSON payload.
- **ScoreMarker** — polarity (+/−), rubric dimension, weight, description, **and a mandatory `evidence_turn_seq` plus verbatim quote**. A marker without evidence is rejected at validation, not silently accepted.
- **L4Signal** — one of six categories with a named owner, severity and narrative.
- **BrokerSignal** — broker, polarity, issue text, evidence quote, `named_in_audio` flag.
- **AssistEvent** — whether real-time assist fired or *should* have fired, with timestamp label and the recommended/suppressed action.

### 4.2 Reference data (config-driven, not hardcoded)

`config/taxonomy.yaml` holds:

- **7 call categories** (DEC-02): Coverage & Benefits, Claims & EOB, Provider Network, Billing & Premium, Enrollment & ID Cards, Pharmacy, Broker-Attributed.
- **4 resolution states**: RESOLVED, PARTIALLY RESOLVED, ESCALATED, UNRESOLVED.
- **3 tiers with thresholds**: GOOD ≥ 86, AVERAGE 60–85, POOR ≤ 59. *(Derived from the xlsx: Carlos 91.2 GOOD, Linda 85.4 and Michael 85.2 AVERAGE, Nicole 75.6 AVERAGE, Kayla 40.2 POOR — the boundary sits between 85.4 and 91.2, so 86 is the defensible cut. Tunable in one file.)*
- **6 L4 categories with owners**: PROCESS BREAKDOWN → Operations; BROKER ATTRIBUTION → Broker Relations; MEMBER COMMUNICATION GAP → Member Communications; COMPLIANCE & RISK → Compliance / Quality & Clinical; AGENT COACHING → Call Centre Management; PROVIDER PERFORMANCE → Provider Relations.
- **Sentiment vocabulary** — a controlled list for the `X → Y` arc. The corpus contains 44 distinct arcs built from roughly 24 unique states; constraining the model to the vocabulary is what lets the dashboard group them.

---

## 5. Scoring engine (DEC-03)

### 5.1 How a score is produced

1. The LLM returns **markers only** — no number. Each marker: `{polarity, dimension, description, evidence_turn_seq, quote}`.
2. Every marker is validated: the dimension must exist in the rubric, and `quote` must be a genuine substring of the referenced turn. Failures are dropped and logged, never scored.
3. `RubricEngine` (pure domain code) starts at the configured base and applies each marker's dimension weight, clamped to 0–100.
4. **Gates** run last. A gate can override or suspend a score.

### 5.2 `config/rubric.yaml` shape

```yaml
version: "1.0.0"
base_score: 100
dimensions:
  empathy:                    { positive: +0, negative: -8,  max_negative: -24 }
  accuracy:                   { positive: +0, negative: -12, max_negative: -36 }
  proactivity:                { positive: +3, negative: -6,  max_negative: -18 }
  compliance_disclosure:      { positive: +0, negative: -15, max_negative: -45 }
  resolution_ownership:       { positive: +2, negative: -10, max_negative: -30 }
  escalation_appropriateness: { positive: +2, negative: -20, max_negative: -40 }
tiers:
  good: 86
  average: 60
significance:
  min_calls_for_tier_rating: 5
gates:
  - id: clinical_urgency_unrecognised
    when: signal_present(CLINICAL_RISK)
    effect: score_status = PROVISIONAL
    message: "Score withheld pending clinical review"
```

The clinical gate is what reproduces the prototype's *"Score withheld pending clinical
review — the rubric score of 36 is provisional"* on Call #89, as a rule rather than as prose
the model happened to write that day.

### 5.3 Why this survives an audit

Reproducible across runs and providers; every point of deduction traces to a quoted
sentence; thresholds and weights are reviewable by a non-engineer in one YAML file; and the
engine is pure, so it is exhaustively unit-testable without a model in the loop.

---

## 6. Analytics definitions

Ambiguous metrics are defined once, in code, with the definition surfaced in the UI as a
tooltip — so nobody has to guess what a number means.

- **6.1 Agent Performance** (mirrors the xlsx sheet): calls, avg/min/max score, tier, unresolved, escalated. Agents below `min_calls_for_tier_rating` are **shown but not tier-rated**, carrying the "below significance threshold" note — the prototype's fairness rule, preserved.
- **6.2 Broker Scorecard**: signals, negative, positive, call IDs, profile. **Net, not cumulative** — a broker with one error against strong overall performance is a coaching signal, not a conduct signal. Attribution is recorded **only** when the member names the broker aloud or the member ID resolves to a broker of record, and every signal links to the sentence that produced it. Nothing is inferred.
- **6.3 Overview metrics**: calls analysed; median **and** mean agent score (the distribution is bimodal — reporting one number hides the low cluster); **first-contact resolution** = `RESOLVED / total`, excluding PARTIALLY RESOLVED, stated explicitly in the UI; escalation rate = `ESCALATED / total`; broker-attributed signal count and distinct brokers.
- **6.4 Score histogram**: fixed bins from config; bins below the coaching threshold render in the alert colour.
- **6.5 L4 Signal Distribution**: calls flagged and % of corpus per category. Categories with zero signals are **rendered with an em-dash rather than omitted** — the absence is itself a finding.
- **6.6 Attention Queue**: deterministic aggregation rules in `config/attention_rules.yaml` (e.g. *"≥ N unresolved calls sharing one L4 category"*, *"≥ N negative signals against one broker"*, *"any CLINICAL_RISK signal"*). Each rule declares severity, owner and an evidence query. The ranked list and every number in it come from SQL. An optional LLM pass writes only the human-readable "why" paragraph **over already-computed evidence**, cached per run and clearly attributed. Book-level claims are never invented by a model.

---

## 7. Backend detail

### 7.1 Provider abstraction

`LLMProvider` port: `analyze(prompt, schema, options) -> StructuredResult`. Adapters:

| Provider | Config | Structured output strategy |
|---|---|---|
| Ollama | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | JSON format + schema in prompt, then validate/repair |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_MODEL`, optional `OPENAI_BASE_URL` | native structured outputs |
| Anthropic | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | tool-use forced schema |
| Azure AI Foundry | registered only | raises `ProviderNotImplementedError` with a clear message (DEC-05) |

Cross-cutting: bounded retry with exponential backoff on transient errors, one JSON-repair
retry on schema violation, per-provider timeout, and a token/latency record written to the
LLM audit log. Provider selection is per-request; **no provider is ever silently
substituted** — a failure surfaces as a failure.

### 7.2 Analysis pipeline

`parse turns → redact (no-op, DEC-08) → L1 → L2 → L3 markers → rubric engine → gates → L4 → L5 → persist atomically`

L1–L5 are separate prompts with separate schemas. Rationale: small models (Ollama)
reliably produce a focused schema and routinely fail one large one; each layer is
independently testable and retryable; and a partial failure degrades one layer rather than
losing the call. Prompts are versioned files, and `prompt_version` is stored on every call
so any output traces back to the exact prompt that produced it.

### 7.3 Persistence

SQLAlchemy 2.0 + SQLite in WAL mode, with Alembic migrations from commit one. The database
path comes from `DATABASE_URL`. Repository interfaces live in `application/ports`,
implementations in `infrastructure`. A unit of work wraps a full analysis so a call is
never half-written.

### 7.4 Corpus re-analysis with live progress (DEC-06)

`POST /api/v1/corpus/runs {provider, model, force}` creates an `analysis_run`, returns a
`run_id`, and starts an in-process worker with a bounded concurrency semaphore
(`CORPUS_RUN_CONCURRENCY`). `GET /api/v1/corpus/runs/{id}/stream` is an SSE channel
emitting per-call `started` / `completed` / `failed` events plus a rolling summary.
`POST /api/v1/corpus/runs/{id}/cancel` requests cooperative cancellation.

Run state is **persisted per item**, so a browser refresh reattaches to a live run and a
crash leaves a resumable record. Runs are idempotent — already-analysed calls are skipped
unless `force` is set. No Celery, no Redis: an in-process runner backed by SQLite is the
right weight for a single-node POC, and the port boundary means swapping in a real queue
later touches exactly one adapter.

**Guard rail:** the UI shows an explicit cost warning before a cloud-provider run across
100 calls, with the local Ollama option pre-selected.

### 7.5 API surface (v1)

```
GET  /api/v1/health
GET  /api/v1/providers                    available providers + models + reachability
GET  /api/v1/taxonomy                     categories, resolutions, tiers, L4 owners
POST /api/v1/analyses                     { transcript, provider, model } -> full analysis
GET  /api/v1/calls                        filters: category, agent, resolution, score band,
                                          broker signal, search; paginated
GET  /api/v1/calls/{id}                   full detail incl. transcript + all 5 layers
GET  /api/v1/dashboard/overview           attention queue + metric strip + histogram
GET  /api/v1/dashboard/agents             agent performance
GET  /api/v1/dashboard/brokers            broker scorecard
GET  /api/v1/dashboard/signals            L4 distribution + signals by owner
POST /api/v1/corpus/runs                  start re-analysis
GET  /api/v1/corpus/runs/{id}             run status
GET  /api/v1/corpus/runs/{id}/stream      SSE progress
POST /api/v1/corpus/runs/{id}/cancel      cancel
```

All errors return RFC 9457 Problem Details carrying the correlation ID. OpenAPI is
generated, and the frontend's TypeScript types are generated **from it** — so contract
drift is a build failure rather than a runtime surprise.

### 7.6 Logging (D5)

Flag-driven via env: `LOG_ENABLED`, `LOG_LEVEL`, `LOG_DIR` (default
`C:\Technossus\Code\NanoVox-V2\Logs`), `LOG_FORMAT` (json|text), `LOG_ROTATION_MB`,
`LOG_RETENTION_DAYS`, `LOG_LLM_PROMPTS` (default **false**).

Three sinks:

- `nanovox-app.log` — application events and errors
- `nanovox-access.log` — requests with correlation ID, method, path, status, duration
- `nanovox-llm-audit.log` — provider, model, prompt version, tokens, latency, outcome; prompt and response bodies only when `LOG_LLM_PROMPTS=true`

With `LOG_ENABLED=false` a null handler is installed and no file is created. Every log line
carries the correlation ID, so a UI error traces to its LLM call in one grep.

---

## 8. Frontend detail

### 8.1 Stack

React 18 + TypeScript (strict) + Vite. React Router. TanStack Query for server state
(caching, retry, background refresh). No global state library — there is no client state
worth the abstraction. CSS Modules over the prototype's design tokens copied **verbatim**
into `tokens.css`. No UI kit, no chart library (A2).

### 8.2 Collapsible rail

The rail is 210px expanded (brand, labels, counts, footer) and 64px collapsed (icons only,
with accessible names preserved and tooltips on hover/focus). A single toggle button drives
it; the state persists to `localStorage`; `aria-expanded` and `aria-current` are set
correctly; the transition respects `prefers-reduced-motion`. Below 1080px the rail collapses
automatically, matching the prototype's existing breakpoint.

### 8.3 Screens

| Screen | Prototype section | Notes |
|---|---|---|
| Overview | `#dash` | Attention queue, 5-metric strip, histogram, resolution-by-agent, category bars, signals by owner |
| Calls | `#calls` | Sortable/filterable table; the prototype's filter buttons made functional; server-side pagination |
| Brokers | `#brokers` | Scorecard cards plus the "how attribution works" explainer, which is a real product statement and stays |
| Call detail | `#detail` | Hero ring, L1–L5 timeline, transcript with evidence quotes highlighted **from stored turn indices** — not string matching in the browser |
| Analyze new | `#new` | Transcript textarea with live turn counter, **provider/model picker**, validation, result view |
| Corpus run | *new* | Trigger plus live SSE progress (DEC-06) |

### 8.4 Non-negotiables

Real loading, empty and error states on every data surface — an empty broker scorecard says
so rather than rendering a blank card. Keyboard navigable, WCAG 2.1 AA contrast, semantic
landmarks. Zero hardcoded API URLs (`VITE_API_BASE_URL`). Zero mock data left in the bundle.

---

## 9. Configuration (D4)

The backend uses `pydantic-settings` with a single typed `Settings` object validated at
startup — missing or malformed configuration **fails fast with an explicit message**, never
a runtime `KeyError` on the first analysis. `.env.example` documents every variable with
sensible defaults for the local Ollama path.

```
APP_ENV, APP_HOST, APP_PORT, CORS_ORIGINS
DATABASE_URL
LLM_PROVIDER, LLM_TIMEOUT_SECONDS, LLM_MAX_RETRIES
OLLAMA_BASE_URL, OLLAMA_MODEL
OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL
ANTHROPIC_API_KEY, ANTHROPIC_MODEL
LOG_ENABLED, LOG_LEVEL, LOG_DIR, LOG_FORMAT, LOG_ROTATION_MB,
LOG_RETENTION_DAYS, LOG_LLM_PROMPTS
CORPUS_PATH, CORPUS_RUN_CONCURRENCY
TAXONOMY_PATH, RUBRIC_PATH, ATTENTION_RULES_PATH
```

Rule enforced in review: **no literal URL, path, key, threshold, weight or category name
appears in a `.py` or `.tsx` file.** A CI grep gate checks the common offenders.

---

## 10. Delivery phases

| Phase | Deliverable | Exit criteria |
|---|---|---|
| **P0 — Foundation** | Repo scaffolding, settings, logging, DB engine + migrations, health endpoint, CI (ruff, mypy, import-linter, pytest, eslint, tsc, vitest) | `start.bat` brings up both servers; health green; dependency-rule contract passes |
| **P1 — Domain + rubric** | Entities, value objects, rubric engine, gates, taxonomy/rubric loaders | Rubric unit tests ≥ 95% branch coverage; Call #89's markers reproduce a provisional score |
| **P2 — LLM abstraction** | Port, registry, 3 adapters, Azure stub, versioned prompts, schema validation + repair, LLM audit log | Contract suite passes against a fake provider; live smoke test on Ollama and one cloud provider |
| **P3 — Analysis pipeline** | `AnalyzeTranscript` use case, transcript parser, persistence, `POST /analyses` | Pasting Call #89's transcript yields a complete, evidence-anchored L1–L5 |
| **P4 — Read models + dashboard API** | Aggregation queries, attention rules, all `/dashboard/*` and `/calls` endpoints | Integration tests assert every figure against a known fixture DB |
| **P5 — Frontend shell + Analyze** | Tokens, AppShell, collapsible rail, routing, Analyze screen with provider picker, Call detail | Call #89 detail is visually faithful to the prototype |
| **P6 — Dashboards** | Overview, Calls, Brokers screens with all charts | All four xlsx views reproduced from live data |
| **P7 — Corpus run** | Background runner, SSE progress, run UI, cancel/resume, cost warning | 100 calls analysed end to end via Ollama with live progress and a resumable run record |
| **P8 — Hardening** | Fidelity report (§11.2), docs, `scripts/` correction, accessibility and audit pass | §13 checklist fully green |

Phases P1–P4 (backend) and P5–P6 (frontend) overlap once the OpenAPI contract is frozen at
the end of P4.

---

## 11. Quality strategy

### 11.1 Testing

- **Unit** — domain rubric, gates, aggregation rules, transcript parser, taxonomy loader. Pure, fast, no I/O.
- **Contract** — every `LLMProvider` adapter runs the same suite against recorded fixtures; a new provider must pass it to be registered.
- **Integration** — use cases against a real temporary SQLite database with a deterministic fake provider. Dashboard figures asserted numerically.
- **API** — schema and status-code assertions per endpoint, including error shapes.
- **Frontend** — Vitest + Testing Library on chart maths, rail behaviour, filters and evidence highlighting; MSW for API mocking.
- **E2E (smoke)** — Playwright: paste → analyze → detail → dashboard reflects the new call.
- **Gates** — backend line coverage ≥ 85%, domain ≥ 95%; the build fails below either.

### 11.2 Model fidelity report (enabled by A3)

Because DEC-01 re-analyses everything, output *will* differ from the authored panels. A
generated report compares model output against stored ground truth on category accuracy,
resolution accuracy, score MAE, broker-signal recall and L4 category agreement. This is how
we answer *"is the model actually good?"* with evidence rather than assertion — and it is
the honest way to present a re-analysed corpus whose numbers no longer match the xlsx.

---

## 12. Deferred scope (documented seams, not built)

| Item | Seam already in place |
|---|---|
| Audio + ASR | `Interaction` abstraction; a `TranscriptionPort` sits in front of the parser |
| Outlook email (~7k/month) | Channel-agnostic domain; the pipeline takes turns, not "calls" |
| PHI redaction | No-op `RedactionPort` in the pipeline (**required before real member data**) |
| Authentication | Single middleware insertion point at the API boundary |
| Azure AI Foundry | Registered provider entry; adapter to implement |
| 10–12 category taxonomy | `taxonomy.yaml` plus a re-classification run |
| Multi-node scale | `ProgressPublisher` and run-repository ports abstract the in-process runner |

---

## 13. Audit checklist (D7)

- [ ] Dependency rule enforced by an import-linter contract in CI
- [ ] No hardcoded URLs, keys, paths, thresholds, weights or taxonomy strings (CI grep gate)
- [ ] Every config value documented in `.env.example` with a safe default
- [ ] Fail-fast startup validation with actionable messages
- [ ] Typed end to end — mypy strict, TypeScript strict, no `any`, no unjustified `# type: ignore`
- [ ] Every score marker carries verifiable transcript evidence
- [ ] Scoring reproducible across runs and providers
- [ ] Structured logging with correlation IDs; flag honoured in both states
- [ ] RFC 9457 error responses; no stack traces reach the client
- [ ] Migrations from commit one; no ad-hoc schema changes
- [ ] Coverage gates met; no skipped or flaky tests
- [ ] No TODO/FIXME or commented-out code on the main branch
- [ ] No mock or placeholder data in shipped code paths
- [ ] Loading, empty and error states on every data surface
- [ ] WCAG 2.1 AA: contrast, keyboard, landmarks, reduced motion
- [ ] OpenAPI-generated frontend types; contract drift breaks the build
- [ ] README and runbook accurate; `scripts/` corrected (NVIDIA reference removed)

---

## 14. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Small local models produce weak or malformed 5-layer output | Demo quality | Per-layer schemas, repair retry, fidelity report to choose a model on evidence; the Ollama model is env-configurable |
| Re-analysed figures differ from the xlsx Rebekah has already seen | Stakeholder confusion | Stated openly (DEC-01); the fidelity report explains the delta; provenance shown per call |
| Cloud cost on a 100-call run | Budget | Local default, explicit cost warning, per-run token accounting in the audit log |
| Model hallucinates a broker attribution | Reputational / compliance | Attribution requires a member-spoken name plus a stored evidence quote; unverifiable signals are dropped and logged |
| Score perceived as arbitrary | Adoption | Deterministic rubric, visible weights, evidence per marker, clinical gate |
| SQLite write contention during a concurrent run | Reliability | WAL, bounded concurrency, single-writer unit of work |

---

## 15. Open items for the product owner

None blocking. Two are worth an early decision, neither of which changes the architecture:

1. **Ollama model choice** for the default local path (e.g. a 7–8B instruct model versus something larger). The fidelity report in P8 will answer this with evidence, but an early preference saves a cycle.
2. **Attention-queue thresholds** in `attention_rules.yaml` — I will seed defensible defaults from the corpus, but you may want to tune what counts as "needs attention" before the demo.

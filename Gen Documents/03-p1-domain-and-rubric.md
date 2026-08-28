# P1 — Domain and rubric: completion record

**Status:** Complete. Both exit criteria met.
**Date:** 2026-08-28
**Plan reference:** [01-implementation-plan.md](01-implementation-plan.md) §4, §5, §10 phase P1

---

## 1. Exit criteria

| Criterion (plan §10) | Target | Result |
|---|---|---|
| Rubric unit tests at ≥ 95% branch coverage | 95% | **100% statement and branch across the whole domain layer** (665 statements, 172 branches, 0 missed) |
| Call #89's markers reproduce a provisional score | — | **Met** — POOR tier, `ScoreStatus.PROVISIONAL`, message "Score withheld pending clinical review." |

Full suite: **222 backend tests passing**, 98.98% overall coverage, mypy strict clean across
88 files, 3 architecture contracts kept, all frontend gates still green.

## 2. What was built

### Scoring (`domain/scoring/`)

The deterministic engine DEC-03 promised. The model never returns a number.

| Component | Responsibility |
|---|---|
| `rubric.py` | `Dimension`, `Gate`, `Rubric` — every field validated on construction |
| `marker_validation.py` | Rejects markers whose dimension is unknown, whose turn does not exist, or whose quote does not appear in that turn |
| `rubric_engine.py` | The arithmetic, plus the full working behind each result |
| `gates.py` | Post-arithmetic policy overrides, evaluated separately from the weights |

**How a score is produced.** Start at `base_score` (100 = "nothing went wrong"). Sum
negatives per dimension, capped at `max_negative`. Sum positives, capped at `max_positive`.
Positives then *offset* penalties — up to a global `max_positive_offset` — rather than
adding to the score. Clamp to 0–100, derive the tier, run the gates.

That offset rule is the substantive design decision. Letting positives add would mean five
pleasantries could cancel a compliance failure; letting them raise the score above base
would mean a call could be better than one where nothing went wrong. Neither is defensible
to a manager, so neither is possible.

### Domain model

Value objects that cannot hold invalid state: `Score` (bounded 0–100), `TierThresholds`,
`Resolution`, `Severity`, `SentimentArc`, `Category`, `SpeakerRole`, `Polarity`.
Entities: `Turn`, `Transcript`, `ScoreMarker`, `L4Signal`, `BrokerSignal`, `AssistEvent`.
Plus `Taxonomy` and the significance rule.

Three constructor rules are worth naming, because they enforce commitments from the plan
rather than merely tidying data:

- **`ScoreMarker` cannot exist without a quote and a turn index.** Traceability is
  structural, not a convention a prompt might drift away from.
- **`BrokerSignal` cannot exist without evidence.** This record names a real person; an
  unevidenced conduct claim is not something to discourage, it is something to make
  impossible to construct.
- **`AssistEvent` has a `SHOULD_HAVE_FIRED` state.** Call #89's L5 panel presents the
  absence of a trigger as the finding. Modelling that as an empty list would lose it.

### Configuration (`config/taxonomy.yaml`, `config/rubric.yaml`)

The reviewable surface. `rubric.yaml` carries every weight, threshold and gate with the
reasoning inline; `taxonomy.yaml` carries the seven categories (DEC-02), six L4 categories
with owners, signal types and the sentiment vocabulary. Both are loaded and validated at
startup, and the loaders report the exact path of a bad value —
`Rubric (rubric.yaml): dimensions.empathy.positive must be a whole number.`

## 3. Decisions taken during P1

| # | Decision | Reasoning |
|---|---|---|
| P1-1 | **Enums for values the code branches on; config for values it only counts** | This resolves a contradiction in plan §4.2, which listed resolutions and tiers as taxonomy data. First-contact resolution is *defined* as RESOLVED — if that were configurable, configuration could break arithmetic. Categories, L4 categories, signal types and sentiment states are only grouped and counted, so those stay data. Tiers and significance moved to `rubric.yaml`, where they belong with scoring. |
| P1-2 | **Positives offset penalties; they never add** | See above. Capped globally so praise cannot erase a serious failure. |
| P1-3 | **Per-dimension caps** | A model that phrases one criticism five ways would otherwise sink a call on a single issue. Both raw and capped totals are reported, so a reviewer can see the cap engaged. |
| P1-4 | **Quote matching tolerates whitespace and case, nothing else** | Corpus transcripts are line-wrapped, so an exact comparison would reject correct evidence. The words themselves must match. |
| P1-5 | **Rejected markers are returned, not discarded** | A model that repeatedly invents quotes is a finding about the model. P3 logs these. |
| P1-6 | **The loader cross-checks gate arguments against the taxonomy** | Renaming a signal would otherwise silently disable the clinical gate, and nothing would fail until a call scored as confirmed that should have been withheld. Verified: the app refuses to start, naming the gate and the missing signal. |
| P1-7 | **Config loaded at startup, held on the container** | A malformed rubric is a configuration failure and should stop the process, not fail partway through an analysis. Startup logs the rubric version and vocabulary sizes. |
| P1-8 | **Call #89 tested against the shipped config, not a fixture** | The test fails if `rubric.yaml` or `taxonomy.yaml` is edited such that this call stops being caught. |

## 4. Defect found and fixed

**`Severity` was sorting alphabetically.** It is declared `class Severity(str, Enum)`, and
`@functools.total_ordering` only fills in comparison operators that are *missing* — `str`
already supplies all of them. The decorator therefore installed nothing, and
`max([MEDIUM, CRITICAL, LOW])` returned `MEDIUM`. Any "most severe signal" ranking would
have been silently wrong.

Fixed by defining all four operators explicitly against an explicit rank, with the reason
recorded in the class docstring so it is not "simplified" back later.

A related note worth recording: mypy accepts `True` where an `int` is expected, because
`bool` subclasses `int`. Several `type: ignore` comments asserting otherwise were removed —
the runtime guards in `Score`, `Turn` and `ScoreMarker` are the only thing catching a
boolean where a number belongs, which is precisely why they exist.

## 5. Calibration: an honest number

Call #89 scores **27** against the corpus's hand-written **36** — same tier (POOR), same
conclusion, gate fires correctly.

The gap is expected and is not being hidden. Those corpus scores were authored by a person,
not computed; tuning weights until one of them matched exactly would be fitting to a number
that was never derived. The rubric is calibrated instead against the *marker patterns* in
the corpus, and the tests assert behaviour — tier, gate, provisional status — rather than
an exact figure.

The P8 fidelity report measures score MAE across all 100 calls and is the intended basis
for tuning. Every weight lives in one YAML file, so acting on that report is a config
change.

**Known calibration item:** with `base_score: 100` and no negative markers, a clean call
scores exactly 100, where the corpus authors gave strong calls 90–98. Whether "nothing went
wrong" should read as 100 or as ~95 is a product judgement, not a technical one. Flagged
for your decision alongside the fidelity report.

## 6. Verification

```bash
./scripts/verify.sh
```

Current result: **all gates passed** — backend format, lint, mypy strict, 3 architecture
contracts, 222 tests at 98.98%; frontend lint, types, 30 tests at 100% statements.

Additionally verified by hand:

- The application starts and logs `Analysis configuration loaded` with
  `rubric_version 1.0.0, dimensions 6, gates 1, categories 7, l4_categories 6`.
- Renaming `clinical_risk` in the taxonomy makes startup fail with:
  *"Gate 'clinical_urgency_unrecognised' watches for signal 'clinical_risk_RENAMED', which
  is not defined in the taxonomy. The gate would never fire."*

## 7. Next phase

**P2 — LLM abstraction.** The `LLMProvider` port, registry, three adapters (Ollama, OpenAI,
Anthropic), the Azure stub that fails fast, versioned prompts, schema validation with a
repair retry, and the LLM audit log. Exit criteria: the contract suite passes against a
fake provider, plus a live smoke test on Ollama and one cloud provider.

P2 is where the first of the two open questions from plan §15 becomes live: **which Ollama
model** should be the local default. A preference now saves a cycle; otherwise I will pick
a 7–8B instruct model and let the P8 fidelity report settle it.

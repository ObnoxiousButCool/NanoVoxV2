# Reducing churn: implementation plan

Six changes that turn the dashboard from *"how well did we handle these calls?"*
into *"which members are about to leave?"*

---

## Does any of this need the corpus re-analyzed?

**Five of the six do not.** Only the new signal type needs a model, and even that
can be narrowed to about eight calls instead of a hundred.

| # | Change | Re-analyse the corpus? | Why |
|---|---|---|---|
| 1 | Member ID column | **No** | The IDs are already in the stored `turns` rows. A backfill script reads them; no model involved. |
| 2 | Call date | **No — but unavailable** | No date exists anywhere in the source. Nothing to backfill; it must come from the telephony system for future calls. |
| 2b | Membership / churn outcome join | **No** | External data joined on member ID. Nothing about the calls changes. |
| 3 | "Intent to leave" signal | **Yes, partially** | Signal codes are constrained by the JSON schema built from `taxonomy.yaml`, so the model can only emit a new code on a *new* analysis. Scope: ~8 candidate calls, not 100. |
| 4 | Member-centric attention queue | **No** | Pure aggregation over stored calls. Read models and UI only. |
| 5 | Sentiment-end surfacing | **No** | `sentiment_start` / `sentiment_end` are already stored on all 102 calls. |
| 6 | Effort metrics | **No** | `duration_minutes` is already populated on all 102 calls. |

Two distinct kinds of work are being compared here, and the difference matters:

- **A backfill** reads data already in the database and writes it into a new
  column. Deterministic, free, instant, repeatable. Points 1, 2b, 4, 5, 6.
- **A re-analysis** sends transcripts to a model again. A full corpus run is
  100 calls × 5 layers = **500 model calls**, and because the model is not
  perfectly repeatable it can also change scores and classifications on calls
  that were fine. Point 3 only.

---

## Phase 1 — Make members identifiable (unblocks everything else)

### 1.1 Add `member_id` to `calls`

**Verified:** a regex over the stored `turns` table finds member IDs in
**101 of 102 calls** — 99 distinct IDs. The data is present; the schema discards
it at parse time.

Steps:

1. Alembic migration: add a nullable `member_id` column to `calls`, indexed.
2. Extract during analysis in the transcript parser, not by the model. The ID is
   a fixed pattern (`CHM-` plus digits) — a regex is exact and free, where a
   model would be approximate and billed. Store it on the call.
3. **Backfill** existing rows in the same migration, reading the `turns` already
   stored. No model calls.
4. Leave it nullable. One call has no ID, and inventing one would be worse than
   recording its absence.

Effort: small. Unlocks points 4 and 6, and all of phase 2.

> The pattern belongs in configuration, not code — a different plan
> administrator will use a different member ID format.

### 1.2 Add `occurred_at` to `calls`

**Verified:** the corpus headers carry Agent, Tier, Score, Sentiment Arc,
Resolution, Duration, Topics and Broker Signal — **no date**. `analysed_at`
records when *we processed* the call, which for the whole corpus is a two-day
window in August 2026 and says nothing about when members actually rang.

Steps:

1. Migration: add a nullable `occurred_at`.
2. Populate it from the call source for future calls (the telephony export, the
   CRM record, or a `Date:` line added to the transcript header).
3. **Leave it null for the existing corpus.** There is nothing to backfill.
   Anything else invents data.

Consequence to accept: until real calls arrive with real dates, "third contact
in 30 days" cannot be computed on this corpus. Repeat-contact *counting* still
works from `member_id` alone — only the time window is missing.

---

## Phase 2 — Make churn measurable

### 2.1 Join to membership outcomes

Nothing in this system knows whether anyone cancelled. Until it does, every
"risk" signal is a plausible guess that nobody can score.

Steps:

1. New table `member_outcomes`: `member_id`, `status`, `left_on`, `checked_at`.
2. A nightly job populating it from the membership system, keyed on the
   `member_id` from 1.1.
3. A derived read model: *did this member leave within 90 days of this call?*

This is the difference between a churn dashboard and a guesswork dashboard. It
does not change a single stored call.

### 2.2 Validate signals against outcomes

Once 2.1 exists, measure each candidate signal:

| Signal | Question it answers |
|---|---|
| ended negative | Do members who hang up frustrated leave more often? |
| unresolved | Does an unfixed problem predict leaving? |
| repeat contact | Does effort predict leaving better than sentiment? |
| exit intent | How many who say it actually go? |

Ship only what survives. Build the score from measured weights, not intuition.

---

## Phase 3 — Detect exit intent (the one model change)

### 3.1 Add the signal type

Add to `taxonomy.yaml` under `signal_types`:

```yaml
  - code: intent_to_leave
    label: Member signalled intent to leave
    severity: CRITICAL
```

Then extend the L1 prompt to describe it: a request to cancel, a broker-of-record
change, a mention of switching plans or carriers, or an explicit threat to leave.
Bump the prompt version — it is recorded on every analysis.

### 3.2 Scope the re-analysis

Adding the code changes the JSON schema the model is constrained to, so existing
calls cannot have it. But a full re-run is unnecessary.

**A regex over stored transcripts finds 10 calls containing departure language**
(8 unique — two are duplicate pasted analyses of C0100). Inspected:

| Call | Language found | Genuine? |
|---|---|---|
| C0100 | "I want to change my broker" | **Yes** — broker-of-record change |
| C0098 | "I came into this call ready to cancel my coverage" | **Yes** — and RESOLVED: a save |
| C0054 | "Can I switch to a cheaper plan then?" | **Yes** — price-driven, UNRESOLVED, ended FRUSTRATED, score 29 |
| C0062 | "whether I should switch plans at renewal" | **Yes** — renewal risk |
| C0044 | agent listing plan options | Ambiguous |
| C0033, C0053, C0080 | agent suggesting mail-order / in-network / HDHP | **No** — false positives |

So the regex is roughly half precise. It is a **triage tool, not a detector**:

1. Run it to produce the candidate list.
2. Re-analyse **only those calls** — about 8, so ~40 model calls rather than 500.
3. Everything else keeps its existing analysis untouched.

> Re-analysing a call replaces its whole analysis, so those calls' scores may
> shift slightly. Acceptable for eight; not something to do casually to a hundred.

For calls that were never re-analyzed, exit intent is simply absent — which is
honest, and matches how the system already treats a layer it could not produce.

### 3.3 Put it on the Overview

Give it its own attention rule at CRITICAL with a minimum of 1. One member
announcing departure is worth a card; it should never be averaged into a bar
chart. Today C0100 appears as one of just **2** calls in the "Broker Conduct"
category bar, where nobody will ever see it.

---

## Phase 4 — Surface what is already there (no model, no migration)

These three read from data already stored on all 102 calls.

### 4.1 "How members left" (point 5)

`sentiment_end` is stored and shown nowhere prominent.

**In the current data:** only **4 of 102** calls ended negative — and **3 of them
are the 3 worst-scoring unresolved calls** (46, 29, 29, against a corpus average
near 80). Unfixed *and* unhappy is the closest thing to a churn signal this data
currently contains.

Add a metric and a small distribution to the Overview. Four calls proves nothing
on its own — it is the shape to watch once phase 2 can validate it.

### 4.2 Effort metrics (point 6)

`duration_minutes` is populated on all 102 calls and completely unused. Add:

- average handling time, and the long tail
- repeat-contact rate (needs `member_id` from 1.1)
- calls per member distribution

Effort is the best-evidenced churn predictor in service research — it catches
members drifting away without complaining, who are the ones still savable.

### 4.3 Members at risk (point 4)

A new read model grouping by `member_id` rather than by rule, scoring each member
on the signals they carry: unresolved outcome, negative ending, repeat contact,
low score, exit intent.

Why it needs to be separate from the existing queue: that queue groups by *which
rule fired*, so each card knows only about its own rule and cannot express
"unresolved **and** ended badly **and** called before". Churn is a conjunction,
and it happens to a person rather than to a rule.

Render it as a work queue — one row per member, ranked, with the calls behind it.

---

## Suggested order

| Phase | Depends on | Re-analysis | Value |
|---|---|---|---|
| 1.1 member ID | — | none | Unblocks 4.2, 4.3, all of phase 2 |
| 4.1 sentiment end | — | none | Immediate, visible |
| 4.2 effort | 1.1 | none | Immediate, visible |
| 2.1 outcome join | 1.1 | none | Makes everything else provable |
| 4.3 members at risk | 1.1 | none | The retention work queue |
| 3 exit intent | — | ~8 calls | Highest signal, smallest cost |
| 1.2 call date | — | none | Needed for time windows; future calls only |
| 2.2 validation | 2.1 | none | Turns the score from guess to measurement |

Phase 1.1 first: it costs little and four other items depend on it.

---

## Before building a churn score on these signals

**The underlying signal extraction is not yet trustworthy.**

| Signal | Calls flagged | Comment |
|---|---|---|
| `clinical_risk` | **67 of 102** | Defined as an exceptional patient-safety event. Two thirds of calls is clearly over-flagging. |
| `broker_conduct` | **1** | While the L4 layer records broker attributions on **41** calls. |
| `repeat_contact` | **2** | And no member ID exists to verify it against. |

There is also an over-attribution gap worth checking: the authored corpus marks a
Broker Signal on **22** calls, while the model recorded broker attributions on
**41**.

A churn score derived from these today would be built on sand. There are 100
hand-labelled `ground_truth` rows to measure extraction accuracy against — do
that first, or phase 2.2 will end up measuring the extractor's noise rather than
members' behaviour.

## Also worth fixing while here

The corpus reads **102**, not 100: two `PASTED` analyses duplicate call C0100.
Nothing dedupes a pasted transcript against a call already analyzed. Minor now,
but it quietly inflates every rate on the dashboard.

# The Scoring Rubric — Matrix, Arithmetic, and How to Present It

**Source of truth:** `Code/Backend/config/rubric.yaml` (matrix) and
`Code/Backend/domain/scoring/rubric_engine.py` (logic)
**Rubric version:** 1.0.0
**Figures in this document:** read from `Data/nanovox.db` at 53 scored calls
**Companion deck:** `Gen Documents/NanoVox_Scoring_Rubric.pptx`

---

## 0. The one idea everything rests on

**The model never returns a score.** It returns *evidence-anchored markers* — a polarity, a
dimension, a turn index, and a verbatim quote — and a fixed rubric turns those into a number.

Two consequences, both worth stating to a client in these words:

> The same transcript produces the same score, on any provider, on any machine.
> Every deduction traces to a line somebody actually said.

Changing what a failure costs is a change to one YAML file, reviewable by someone who does not
read Python.

---

## 1. The matrix

Six dimensions. `per +` / `per −` are the magnitudes for a **single** marker; the engine applies
the sign. The two cap columns limit what **one dimension** can contribute in total, so a model
that phrases the same criticism five ways cannot sink a call on one issue.

| Dimension | Code | per + | per − | cap + | cap − |
|---|---|--:|--:|--:|--:|
| Recognising and acting on urgency | `escalation_appropriateness` | +3 | −20 | 9 | 40 |
| Required disclosures and compliant conduct | `compliance_disclosure` | +2 | −15 | 6 | 45 |
| Factual and procedural accuracy | `accuracy` | +2 | −12 | 6 | 36 |
| Ownership of the member's outcome | `resolution_ownership` | +2 | −10 | 6 | 30 |
| Empathy and acknowledgement | `empathy` | +3 | −8 | 9 | 24 |
| Proactive help beyond the question asked | `proactivity` | +3 | −6 | 9 | 18 |
| **If every cap were reached at once** | | | | **45** | **193** |

Two things the shape encodes:

- **Negatives outweigh positives three- to fourfold in every dimension.** The rubric is a
  deduction instrument, not a points-scoring game.
- **The two most expensive dimensions are the ones whose consequences leave the call.** An
  unrecognised clinical urgency costs 20 points a marker; a missed disclosure 15.

**On the 193.** Total possible penalty exceeds the 100-point base, which means the caps limit
*per-issue* damage, not aggregate damage. A genuinely bad call reaches zero long before every
dimension maxes out. That is intended — past a point, worse is worse — but it is an internal
fact, not a slide (see §7).

### The governing constants

| Constant | Value | Meaning |
|---|--:|---|
| `base_score` | 100 | "Nothing detracted from this call" |
| `max_positive_offset` | 15 | The most praise can offset, in total |
| `tiers.good` | 86 | Lower bound, inclusive |
| `tiers.average` | 60 | Below this is POOR |
| `min_calls_for_tier_rating` | 5 | Fewer calls: average shown, tier withheld |

**The 86 is empirical, not round.** In the reference corpus Carlos averages 91.2 while Linda
averages 85.4 and Michael 85.2, so the defensible cut sits in the gap between them.

---

## 2. The computation

Five steps, in `rubric_engine.py`. The order is load-bearing: capping before summing, and
offsetting before clamping, each change the result.

1. **Start at `base_score` = 100.** Markers only ever move the score down. There is no way to
   earn 101.
2. **Sum negative markers per dimension, then cap each at its `max_negative`.** Per dimension,
   not per call — so one repeated criticism is bounded while two distinct failures both land in
   full.
3. **Sum positive markers the same way, against `max_positive`.**
4. **Positives *offset* penalties; they never add to the score.**

   ```
   applied_offset = min(total_positive, 15, total_negative)
   raw            = 100 − (total_negative − applied_offset)
   ```

   The third term of that `min` is what keeps the ceiling at 100: an offset can only cancel a
   penalty that exists. Strong handling can soften a poor outcome — it cannot erase a compliance
   failure, and it cannot lift a call above "nothing went wrong".
5. **Clamp into 0–100, derive the tier, then run the gates.** Gates come last precisely so they
   can override the arithmetic's conclusion.

---

## 3. Worked example — call C0002, scored 90

Five markers survived validation. No cap binds: total positives of 8 sit below both the dimension
ceilings and the 15-point offset limit.

| Dimension | Marker (model's own text, condensed) | Points |
|---|---|--:|
| `empathy` | Acknowledged the member's concerns about potential costs and reassured her about the annual maximum | +3 |
| `accuracy` | Explained dental coverage levels correctly, including crowns at 80% under her plan tier | +2 |
| `proactivity` | Offered to email a one-page summary of her coverage and remaining annual maximum | +3 |
| `empathy` | Never explicitly acknowledged how the member felt about the unexpected cost | −8 |
| `resolution_ownership` | Did not check whether she had further questions before closing | −10 |
| **Totals** | | **+8 / −18** |

```
applied_offset = min(8, 15, 18) = 8
raw            = 100 − (18 − 8) = 90
tier           = 90 ≥ 86        → GOOD
status         = CONFIRMED
```

Those totals are read back from the stored row, not recomputed for this document.

---

## 4. Before the arithmetic — validation

Validation runs first, and it is the reason the number can be audited. A marker counts only if it
names a dimension the rubric knows, cites a turn that exists, **and** quotes text that genuinely
appears in that turn.

| Rejection reason | What it means |
|---|---|
| `unknown_dimension` | The rubric has no such dimension — scoring it would silently drop the penalty |
| `missing_turn` | The transcript has no turn at that index. Usually a parse failure upstream |
| `quote_not_in_turn` | The quoted words are not in the turn cited. The commonest single rejection |

Refusals are kept, not discarded quietly, and shown on the call: a model that keeps inventing
quotes is a finding about the model, and someone should be able to see it accumulating.

---

## 5. After the arithmetic — the two withholding gates

A gate is a **policy, not a penalty**. "A clinician must look at this before anyone quotes a
number" expressed as a subtraction would be the wrong shape, so gates sit outside the weights and
can override what the arithmetic concluded. Both produce `PROVISIONAL` rather than `CONFIRMED`.

**Gate 1 — `clinical_urgency_unrecognised`**
Condition: signal `clinical_risk` present. Effect: `suspend_score`.
Message: *"Score withheld pending clinical review."*
The number is still shown to a reviewer with its reason — hiding how bad a call looks while it
waits for sign-off would help nobody.

**Gate 2 — evidence found, and all of it refused**
Condition: rejected markers > 0 **and** accepted markers = 0.
The arithmetic then runs over an empty list: no penalty applies because none survived, and 100
comes through untouched. That is not a call that went well — it is a call nobody has scored, and
it would otherwise publish the highest number on the dashboard for the least evidence behind it.

This second gate is deliberately narrow. A call the model read and had no criticism of is a
**quiet call** and stays confirmed. Nothing proposed is not the same as nothing surviving, and
conflating the two would make the withheld count meaningless.

---

## 6. Where the corpus lands

| Band | Calls |
|---|--:|
| GOOD (≥ 86) | 18 |
| AVERAGE (≥ 60) | 29 |
| POOR (< 60) | 6 |
| **Total** | **53** |

All 53 are currently confirmed — no call has tripped a gate. Worth stating rather than leaving to
be inferred from an absence.

### Honest limits

- **The weights are a starting point, not a fit.** They are derived from the marker patterns in
  the sample corpus, not regressed against the hand-written scores in those files. Those scores
  were authored, not computed, so matching them exactly would be false precision. The fidelity
  report measures the gap and is the intended basis for tuning.
- **Deductions describe the handling, never the agent.** The engine's own vocabulary is
  POSITIVE / NEGATIVE rather than good / bad, for the same reason the wording in the YAML is
  careful: an agent reads these numbers.
- **Fewer than five calls means no tier.** Four agents in the corpus have four calls each. Their
  average is shown — withholding it would tell them nothing — but the tier is not, because rating
  a career on four calls is unfair and reads as more certain than it is.

---

## 7. Presenting this to a client

A client does not need the arithmetic; they need to **believe the number**. Lead with the trust
argument and reach the matrix only once the audience wants to see it.

| # | Slide | The point it must land | Visual |
|--:|---|---|---|
| 1 | The model does not score the call | The idea the whole deck rests on | Two boxes, one arrow. Nothing else |
| 2 | Why that matters to you | Same transcript, same score, any provider | One transcript, three providers, one identical number |
| 3 | One real call, end to end | C0002's five markers **with their quotes** | The ledger, revealed a row at a time |
| 4 | Where did 90 come from | `100 − (18 − 8)` | The formula, large, terms coloured to match slide 3 |
| 5 | The matrix | Negatives outweigh positives; escalation and compliance cost most | The table with worst-case bars |
| 6 | What we refuse to score | The number is *checked*, not just produced | A rejected marker beside the turn it claimed to quote |
| 7 | When we withhold a score | Restraint, not gaps | Two provisional pills with their one-line triggers |
| 8 | Where the corpus sits | 18 / 29 / 6, and the empirical 86 cut | Three-bar distribution + the three agent averages |
| 9 | Changing the policy is a YAML edit | Governance: the weights are data | The dimension block, before and after a weight change |

**Two ordering rules that matter more than the content:**

- **Evidence before weights.** Slide 3 makes the audience ask the question slide 4 answers.
  Reversed, the matrix lands flat.
- **Slide 6 is the strongest slide in the deck**, counter-intuitively. Everything before it
  *claims* the number is trustworthy; slide 6 is the only one that demonstrates it.

**Three things to leave out:**

- **The per-dimension caps.** They answer a question no client asks in the room. Appendix.
- **The 193.** True, and useful internally; on a slide it sounds alarming.
- **Any Python.** One YAML block on the closing slide, and nothing from the engine. The engine
  being pure arithmetic is the claim — showing the code is not the proof.

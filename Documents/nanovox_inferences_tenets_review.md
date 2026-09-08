# Inferences tenets mockup — review

Reviewing `Documents/nanovox_inferences_tenets.html` against the screen that
exists today, `Code/Frontend/src/features/inferences/InferencesPage.tsx`.

Written 2026-09-08. Nothing here has been implemented; the questions at the end
are open and change what the work is.

---

## 1. What the current screen has

`InferencesPage.tsx` (133 lines) renders exactly one thing: the
`attention` array from `GET /api/v1/dashboard/overview`. Per item it shows
title, `why`, owner, severity, a reference chip, a count with an unresolved
sub-count, and a link into the filtered calls list built from the server's own
`call_filter`.

Two rules are stated on the page and both still hold in the mockup:

- every figure is counted from stored analyses, never written by a model
- every item opens its own evidence

## 2. What the mockup adds that does not exist anywhere

| Mockup element | Status in the system today |
| --- | --- |
| Mean score, total points deducted, per-call average | Not exposed. Score is per call only; no corpus-level roll-up. |
| Five tenets: score lost, calls affected, % clean | **No per-dimension aggregation exists at all.** |
| Points destroyed per finding (`690 PTS`) | Attention items carry call counts, not points. |
| Churn count (`12 CHURN`) | Not exposed. |

Checked: `domain/aggregation/` holds thirteen modules
(`attention`, `caller_mix`, `effort`, `hourly`, `member_risk`,
`resolution_time`, `run_progress`, `sentiment_movement`, `signal_attribution`,
`significance`, `statistics`, `time_value`, `trend`) and **none references
`dimension`**. Outside `domain/scoring`, the only occurrence in the backend is
`application/use_cases/analyze_transcript.py`.

`OverviewResponse` carries `metrics`, `histogram`, `categories`, `attention`,
`taxonomy_coverage` — no dimension or tenet field. The frontend `types.ts` has
no `dimension`, `score_lost` or `points`.

**So the tenets panel is a new domain aggregation, a new response field and new
frontend types. The page component is the small part of this job.**

## 3. The tenet mapping the mockup implies

Stated in the mockup's own footnote: "Duty of Care combines
`escalation_appropriateness` and `compliance_disclosure`". That fixes five
tenets over the six rubric dimensions:

| Tenet | Rubric dimension(s) |
| --- | --- |
| Follow-Through | `resolution_ownership` |
| Duty of Care | `escalation_appropriateness` + `compliance_disclosure` |
| Initiative | `proactivity` |
| Information Accuracy | `accuracy` |
| Communication | `empathy` |

## 4. The mockup's figures do not reproduce against current data

Implemented the roll-up above, applying the rubric's per-dimension
`max_negative` caps per call, against `Data/nanovox.db` as of the 2026-09-08
run (100 calls, openai/gpt-4o-mini, with the resolution and signal glossaries
and the ten-category taxonomy).

| | Mockup | Current DB |
| --- | --- | --- |
| Calls | 100 | 100 |
| Mean score | 80.8 | **76.0** |
| Total deducted | 1,921 | **2,895** |
| Per call | 19.2 | **28.9** |
| Follow-Through | 690 · 36% · 51 calls · 49% clean | 600 · 21% · 60 · 40% |
| Duty of Care | 625 · 33% · 26 calls · 74% clean | **1,135 · 39% · 55 · 45%** |
| Initiative | 342 · 18% · 41 calls · 59% clean | 324 · 11% · 54 · 46% |
| Information Accuracy | 192 · 10% · 14 calls · 86% clean | 372 · 13% · 29 · 71% |
| Communication | 72 · 4% · 9 calls · 91% clean | **464 · 16% · 58 · 42%** |

Two differences matter more than the rest.

**The headline reverses.** The mockup's central claim is "Follow-Through is the
single largest destroyer of score". On this data **Duty of Care is**, by a wide
margin — 1,135 points against 600.

**Communication is not a rounding error.** The mockup shows it as the cleanest
tenet at 4% of loss across 9 calls. Actual: 16% across 58 calls.

### The narrative paragraph's specific claims

| Claim in the mockup | Current DB |
| --- | --- |
| accuracy "70 positive against 17 negative", four-to-one | 77 / 31 — about 2.5-to-1 |
| Follow-Through "69 negative against 4 positive" | 60 negative against **36 positive** |

The argument of the whole section rests on that second asymmetry — facts right,
follow-through wrong — and on this run it is not present.

Also worth noting: **`escalation_appropriateness` produced zero positive
markers** across all 100 calls. The model never once credits an agent for
recognising urgency. That is a finding in its own right, and it distorts any
"% clean" figure for Duty of Care.

### The mockup is internally consistent

It is a coherent dataset, just not this one. Its escalation finding
(23 calls · 580 pts) plus its disclosure finding (3 calls · 45 pts) equal its
Duty of Care tenet (26 calls · 625 pts) exactly. So these numbers were counted
from *something* — most likely an earlier run.

### Marker counts by dimension, current run

| Dimension | Positive | Negative |
| --- | --- | --- |
| `empathy` | 49 | 58 |
| `accuracy` | 77 | 31 |
| `proactivity` | 41 | 54 |
| `compliance_disclosure` | 11 | 21 |
| `resolution_ownership` | 36 | 60 |
| `escalation_appropriateness` | **0** | 41 |

## 5. Open questions

1. **What is the deliverable?** Gap analysis toward implementing this, a design
   critique, or a check on whether its claims are true? The three produce
   different work.
2. **Are the figures real or illustrative?** If counted from a specific run,
   which one — a discrepancy this size means either my cap logic or the
   mockup's is wrong, and that needs settling before anything is built. If
   they are placeholders, ignore them and design against live data.
3. **Where does the tenet mapping live?** `rubric.yaml` beside the dimensions,
   `dashboard.yaml` with the other display thresholds, or the frontend? The
   mockup insists tenets are "not a second scoring system", which argues for
   config the business can read, but DEC-02/03 would support either file.
4. **What exactly is "% of calls clean"?** Zero negative markers in that tenet,
   or zero deduction after caps? And is the denominator all 100 calls or only
   calls where the dimension was assessed? The readings diverge materially here
   because `escalation_appropriateness` has no positive markers at all.
5. **Is "The pattern behind the numbers" hand-written or generated?** It draws a
   causal conclusion — a process and accountability problem, not a knowledge
   problem. If generated, it needs the rule that decides that. If hand-written,
   it goes stale on the next run, and it sits oddly beside the page's own
   footer promise that nothing is written at render time.
6. **Are the six findings the existing `dashboard.yaml` rules or a new set?**
   They read like richer attention items, but "Broker failures are surfacing as
   member churn" may or may not be an existing rule.
7. **Does this replace the current screen or extend it?** The findings list
   looks like it supersedes the attention list. Worth confirming before
   treating a working page as disposable.
8. **Which run should this be built against?** The 2026-09-08 run found that
   the rubric's per-dimension weights **invert GOOD and AVERAGE**: marker counts
   order the tiers correctly (GOOD 1.90 negative vs AVERAGE 2.11) while the
   weighted points reverse them (GOOD 24.71 vs AVERAGE 21.97), and so does the
   final score (82.4 vs 83.7). A screen built entirely on per-dimension point
   totals inherits that distortion. This is the one I would resolve first.

## 6. Reproducing the table in §4

Read-only. Backend need not be running.

```python
import sqlite3, collections

CAPS = {
    "empathy": 24, "accuracy": 36, "proactivity": 18,
    "compliance_disclosure": 45, "resolution_ownership": 30,
    "escalation_appropriateness": 40,
}
TENET = {
    "resolution_ownership": "Follow-Through",
    "escalation_appropriateness": "Duty of Care",
    "compliance_disclosure": "Duty of Care",
    "proactivity": "Initiative",
    "accuracy": "Information Accuracy",
    "empathy": "Communication",
}

c = sqlite3.connect(r"C:\Technossus\Code\NanoVox-V2\Data\nanovox.db")
c.row_factory = sqlite3.Row

per = collections.defaultdict(lambda: collections.defaultdict(int))
pos, neg = collections.Counter(), collections.Counter()
for r in c.execute("select call_id, dimension, polarity, points from score_markers"):
    if r["polarity"] == "NEGATIVE":
        per[r["call_id"]][r["dimension"]] += abs(r["points"] or 0)
        neg[r["dimension"]] += 1
    else:
        pos[r["dimension"]] += 1

lost, affected = collections.Counter(), collections.defaultdict(set)
for call, dims in per.items():
    for dim, pts in dims.items():
        capped = min(pts, CAPS[dim])          # the cap is per dimension per call
        lost[TENET[dim]] += capped
        if capped:
            affected[TENET[dim]].add(call)

total_calls = c.execute("select count(*) from calls").fetchone()[0]
total_lost = sum(lost.values())
mean = c.execute("select avg(score) from calls").fetchone()[0]
print(f"calls {total_calls}  mean {mean:.1f}  deducted {total_lost}  per call {total_lost / total_calls:.1f}")
for t, n in lost.most_common():
    a = len(affected[t])
    print(f"{t:22s} {n:6d} {100 * n / total_lost:4.0f}% {a:4d} calls {100 * (total_calls - a) / total_calls:4.0f}% clean")
```

Caveat on the cap: this applies `max_negative` per dimension per call, which is
what `rubric.yaml` describes. If the scoring engine applies it differently, the
per-tenet totals move and §4 should be recomputed against the engine rather
than against this script.

# P6 — Dashboards

**Status:** complete
**Date:** 2026-08-28
**Exit criterion (plan §10):** *All four xlsx views reproduced from live data* — met.

---

## 1. What was built

Three screens against the read models finished in P4, plus the chart primitives they
share.

| Screen | Route | Reproduces |
| --- | --- | --- |
| Overview | `/overview` | Attention queue, headline metrics, score distribution, resolution by agent, category volume, L4 signal distribution by owner |
| Calls | `/calls` | The prototype's call table, severity-ordered, with the quick filters made real |
| Brokers | `/brokers` | Broker Attribution Scorecard |

`/overview` is now the default route. An unknown path lands there rather than on
Analyze; Overview itself points at Analyze while nothing has been analysed, so a
fresh install still arrives somewhere it can act.

### Chart primitives — `src/shared/ui/charts.tsx`

`Bar`, `BarRows`, `Legend`, `Histogram`, `MetricStrip`, `Metric`. Drawn in CSS, no
charting library (plan A2): the prototype's bars are already CSS, and a library would
fight the design for no gain.

One rule runs through all of them and is tested: **a zero is drawn, not omitted.** An
absent bar reads as "this does not happen", which is the exact misreading the
dashboard exists to prevent. An empty histogram bin renders at 2% height rather than
collapsing, because the gap between the two clusters *is* the finding.

## 2. Backend change in this phase

`AgentAggregate`, `AgentPerformance` and `AgentResponse` now carry all four
outcomes — `resolved`, `partially_resolved`, `escalated`, `unresolved` — rather than
three plus a derived remainder. Deriving `resolved` as "everything else" would
silently absorb any outcome added later into the healthy-looking bar.

`test_the_four_outcomes_account_for_every_call` asserts the four sum to the call
count, so the invariant fails loudly instead of drifting.

A dead `_owner_load` helper was removed from the read-model repository.

## 3. Decisions worth recording

**Median leads, mean follows.** The corpus is bimodal. The mean (64.4) falls in a gap
where almost no call actually sits, so the strip prints the median as the headline and
the mean beneath it, labelled *distribution is split*. A single number here would
misinform, which is why the histogram sits directly under it.

**Rates carry their reference range.** "41.7%" means nothing on its own; the strip
prints "Industry range 65–75%" beside it. Judgement belongs next to the number, not in
the reader's memory.

**Withheld scores stay withheld on every screen.** An agent below the n=5 significance
threshold is *shown* — omitting them would hide a workload — but the score renders as
`—`, not as a number. Priya, with the single highest average in the seeded corpus, is
correctly unrated. Same rule on the call table, where a provisional score is stamped
`WITHHELD`.

**Filters narrow the server query, not the rendered page.** Filtering client-side would
make the count under the table ("Showing 1–1 of 60") a lie. Changing a filter resets
the offset — page 3 of the old result set is not page 3 of the new one.

**Broker scoring is net, not cumulative.** A broker with one error against otherwise
strong performance is a coaching signal, not a conduct case. The card says which it is
in words ("Best practice" / "Conduct review") and shows the positive/negative split
behind the total, because a bare "3" hides whether it is three complaints or three
compliments. The attribution rule is stated on the page itself, since this is the one
screen that names real people.

## 4. Verification

`bash scripts/verify.sh` — **all gates passed.**

| Gate | Result |
| --- | --- |
| Backend format, lint, types | pass |
| Architecture contracts | pass |
| Backend tests | 493 passed, 96% coverage |
| Frontend lint, types | pass |
| Frontend tests | 122 passed in 17 files |
| Frontend coverage | 96.4% statements, 83.33% branches, 95.72% functions |

New this phase: `charts.test.tsx`, `tone.test.ts`, `OverviewPage.test.tsx`,
`CallsPage.test.tsx`, `BrokersPage.test.tsx` — 41 tests.

Verified live in the browser against a 12-call database (the 11-call fixture corpus
plus the real Call #89 analysis): attention queue ranked CRITICAL→HIGH with owners and
call references; metric strip reading 12 / median 65 / 41.7% / 16.7% / 5 signals across
2 named brokers; 9 populated histogram bins with "5 calls fall below the coaching
threshold"; resolution-by-agent showing Priya unrated; category bars including
`Broker-Attributed 0`; signal owners with no signals shown as `—`.

### Two fixes the gate caught

`App.test.tsx` still asserted P5's landing screen (Analyze). Updated to the new
default rather than left passing on a stale assumption.

An `OverviewPage.tsx` template literal interpolated a number directly, which
`restrict-template-expressions` rejects. Fixed at source.

## 5. Still open — model judgement

Unchanged from P3 §5 and restated because P6 puts it on the front page: **the
architecture is sound; the local model's judgement is not.** Two runs of Call #89 gave
74 AVERAGE and 48 POOR from identical input, both misclassifying the category and
marking a patient-safety call RESOLVED.

Every figure on the Overview is now computed from that judgement. The dashboard is
correct — it faithfully reports what the analyser concluded. That is precisely why the
model choice needs settling before the corpus run in P7, when 100 calls of it become
the headline numbers. Recommendation stands: tune the prompts, re-measure, and hold a
cloud provider for the demo run.

## 6. Next — P7, corpus run

Background runner over the 100-call corpus with SSE progress, a UI trigger, cancel and
resume, and a cost warning before a paid provider is used. Exit criterion: the full
corpus analysed and the dashboard populated from it rather than from fixtures.

At current local-model latency (~4 min/call) that run is roughly 6.5 hours.

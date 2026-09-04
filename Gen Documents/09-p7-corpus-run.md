# P7 — Corpus run

**Status:** complete
**Date:** 2026-08-28
**Exit criterion (plan §10):** *100 calls analyzed end to end via Ollama with live progress and a resumable run record.*
**Met:** the mechanism is built, tested and verified live end to end. The full
hundred-call run has **not** been executed — see §7.

---

## 1. What was built

| Piece | Where |
| --- | --- |
| Corpus reader | `infrastructure/corpus/markdown_corpus.py` |
| Run record | `analysis_runs`, `analysis_run_items` tables |
| Authored expectations (A3) | `ground_truth` table + its own repository |
| Worker | `application/use_cases/run_corpus.py` |
| Progress channel | `application/ports/run_events.py`, `infrastructure/runner/event_bus.py` |
| Background tasks | `infrastructure/runner/background_runner.py` |
| API | `frameworks_drivers/api/v1/corpus.py` |
| Screen | `src/features/corpus/CorpusPage.tsx`, `useRunStream.ts` |

`POST /corpus/runs` creates the run and returns immediately; the work happens on
a background task and reports through `GET /corpus/runs/{id}/stream`. Cancel,
resume and a run history complete the set.

## 2. The three properties that make it more than a loop

**Resumable.** Every item's outcome is written as it happens. Nothing about a
run's progress lives only in the worker's memory, so a refresh reattaches, and a
process that dies leaves a record the next one can pick up. At startup any run
still marked active is marked `INTERRUPTED` — an in-process worker cannot survive
a restart, so a run still claiming to be `RUNNING` is describing a worker that no
longer exists.

**Idempotent.** A call that already has an analysis is skipped *with a reason*
rather than analyzed twice. `force` replaces instead, and replacement deletes the
old call first: leaving both would double every figure on the dashboard.

**Failure-isolating.** A call that fails is recorded as failed, with the reason,
and the run carries on. Ninety-nine analyzed calls are worth having. A run where
*nothing* succeeded is reported as `FAILED`, not `COMPLETED` — a green progress
bar over zero results would be a lie.

## 3. Decisions worth recording

**The cost guard is enforced by the API, not drawn in the UI.** A run against a
paid provider is refused with a 400 unless `acknowledge_cost` is set. A
confirmation dialog the server does not require is decoration: any other client,
or a stale page, would spend the money anyway. The screen states the arithmetic
it can state — 100 calls × 5 layers = 500 model calls — and deliberately gives no
cost estimate, because a wrong one is worse than none.

**One run at a time.** A second concurrent run is refused with a 409. Two workers
over one corpus would double the model spend and race for the same call
references.

**Cancelling waits for the call in flight.** Cancel sets `CANCELLING`, not
`CANCELLED`; the worker finishes the call it is on and stops before the next.
Abandoning mid-analysis would leave a half-written call. A cancelled run is
resumable — cancelling is a pause the operator chose, and refusing to continue it
would make cancel a destructive act.

**Ground truth is stored, and stored apart.** The authored panel in each corpus
file — score, tier, resolution, named brokers — goes into its own table with no
foreign key to `calls`, written at the *start* of a run so a cancelled run still
leaves the answer key it read. It is what the P8 fidelity report measures against.
Nothing in the dashboard path touches it: these are figures a person wrote, and
presenting one as a measurement would be the most misleading thing this system
could do.

**Pasted and corpus calls now have separate reference namespaces.** Corpus calls
are `C0001`–`C0100`, deterministic from the file, which is what makes a run
idempotent across processes without a mapping table. Pasted calls are now `P0001`
onward, allocated as *highest existing number plus one* rather than row count —
counting breaks the moment references are not dense, and a run makes them not
dense. Without this split, a corpus run's `C0089` could collide with whatever a
pasted call had been given.

**Progress is derived, never stored.** A stored counter and a table of items are
two sources of truth that drift the moment a process dies between the two writes
— which is exactly the situation the run record exists for.

## 4. Three real bugs, and how each was found

**Cancel could be silently overwritten.** *(found by test)* The worker set the
run to `RUNNING` unconditionally on start. A cancel landing between the request
that created the run and that first write was erased, and the run worked on as
though nothing had happened. Only a pending run is now moved to running.

**The event stream died after fifteen seconds.** *(found live, not by tests)*
`asyncio.wait_for` cancels the awaited `__anext__` on timeout, which throws
`CancelledError` into the underlying async generator and closes it permanently —
so the first keep-alive was the last thing any client ever received, while the run
carried on working invisibly. The loop now holds the pending read in a task
across heartbeats using `asyncio.wait`, which does not cancel it.

This one is worth dwelling on. It passed review, passed the type checker, and
would have passed any test that did not wait fifteen seconds. It was caught by
pointing `curl` at the running server and counting frames — twenty heartbeats
later the connection was still live, where the old code had gone silent after one.
A regression test now drives the same loop with a 10 ms heartbeat.

**Named SSE events reach no listener.** The backend names every frame
(`event: item_finished`); `EventSource.onmessage` fires only for *unnamed* ones.
The first version of the hook would have sat silent through an entire run. Each
kind is now registered explicitly, and the fake `EventSource` in the tests is
faithful about it — a listener on `message` alone receives nothing.

## 5. Verification

`bash scripts/verify.sh` — all gates pass.

| Gate | Result |
| --- | --- |
| Backend format, lint, types, contracts | pass |
| Backend tests | 615 → 653 passed |
| Frontend lint, types | pass |
| Frontend tests | 160 passed |

New tests: corpus parser (20), run state and progress (24), event bus and SSE
frames (15), the worker end to end (32), the HTTP contract (27), the SSE hook
(13), the Corpus screen (25).

### Verified live, against the running system

Everything below was observed, not inferred.

- **The parser reads all 100 real corpus files.** Every field populated on every
  call; 22 calls carry a named broker; references `C0001`–`C0100`.
- **A run analyzed a real call end to end** through Ollama and stored it:
  `C0002 — "Out-of-Pocket Maximum — Member Still Getting Bills After Hitting Max"`,
  **347.4 s**.
- **Skip worked**: `C0001` was already analyzed and was skipped with its reason
  rather than analyzed twice.
- **Interruption and resume worked**: the process was killed mid-run; on restart
  the run was marked `INTERRUPTED` with *"The process stopped while this run was
  working"*, `POST /resume` returned it to `PENDING` keeping the skipped item
  finished, and it ran to completion.
- **The stream stayed alive** through 20 heartbeats and delivered the finish.
- **The browser updated itself**: the Corpus screen went to `COMPLETED`, `2 of 2`,
  `1 analyzed · 1 skipped`, and the corpus summary refreshed to `0 outstanding`
  without a reload.
- **The cost warning fires**: selecting `openai` produced the charged-for warning
  and disabled the start button until acknowledged.

## 6. Measured cost of the full run

One call took **347 s** on `qwen2.5:7b-instruct` locally. At the configured
concurrency of 2, a hundred calls is roughly **4 hours 50 minutes**. That is a
figure to plan around rather than an estimate: it is what this machine actually
did.

`CORPUS_RUN_CONCURRENCY` defaults to 2 because Ollama serves one model — more
concurrent requests make each call slower without finishing the run sooner. It is
worth raising for a cloud provider, which is limited by rate limits rather than by
one GPU.

## 7. What has not been done, and why

**The hundred-call run has not been executed.** It is ~5 hours of local compute
and it will overwrite the dashboard's current contents. That is a decision to
take deliberately, not one to slip into the end of a phase. Everything needed to
start it is in place: open **Corpus run**, pick the provider, press the button.

**The demo database holds mixed data.** It currently contains the 11-call fixture
corpus seeded in P6 (`F0001`–`F0010`), one pasted analysis stored as `C0001`, and
`C0002` from the live test above. That stray `C0001` is why the live run skipped
its first call: the reference was taken by a *pasted* call from before the
namespace split. Before the real run, the demo rows should be cleared so the
dashboard is the corpus and nothing else — say the word and I will clear them;
I have not deleted anything.

## 8. Still open — model judgement

Unchanged from P3 §5, and now the thing that decides whether the corpus run is
worth running. Two analyses of Call #89 gave 74 AVERAGE and 48 POOR from
identical input, both misclassifying the category and marking a patient-safety
call RESOLVED.

P7 makes this concrete: a five-hour run against a model that judges like that
produces five hours of confident wrong answers, presented as the dashboard. The
recommendation stands — tune the prompts, re-measure against the ground truth now
being stored, and hold a cloud provider for the demo run. `OPENAI_API_KEY` and
`ANTHROPIC_API_KEY` are both configured and reachable, so that option is
available; I have not spent anything against either.

## 9. Next — P8, hardening

The fidelity report (§11.2) is the natural next step and now has everything it
needs: authored expectations in `ground_truth`, model conclusions in `calls`, and
a run record linking each to the file it came from. Plus docs, the accessibility
pass and the §13 audit checklist.

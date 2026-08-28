# P5 — Frontend shell, Analyze and Call detail: completion record

**Status:** Complete. Exit criterion met.
**Date:** 2026-08-28
**Plan reference:** [01-implementation-plan.md](01-implementation-plan.md) §8, §10 phase P5

---

## 1. Gate results

| Gate | Result |
|---|---|
| Backend format / lint / types | Pass, 150 files, mypy strict |
| Architecture contracts | 3 kept, 0 broken |
| Backend tests | **492 passed**, 95.9% coverage |
| Frontend lint / types | Pass — ESLint `strictTypeChecked`, TS strict with `exactOptionalPropertyTypes` |
| Frontend tests | **75 passed** (was 30), 91.6% statements, 81.3% functions |

`./scripts/verify.sh` → **all gates passed**.

## 2. Exit criterion

> *Call #89's detail page is visually faithful to the prototype.*

**Met**, verified against a live analysis rather than a mock. The page renders the
hero score ring, all five layer blocks with the prototype's badge colours, the
evidence list with turn citations, the operational findings with owners, the L5
gap panel, and the transcript with highlighted evidence.

Checked in the running browser:

- Score ring `74` in amber — `rgb(178,106,0)`, the prototype's `--sev-md`.
- Accent token resolves to `#14514f`, the prototype's value.
- **4 highlighted quotes** in the transcript, each matching a stored marker.
- 13 turn anchors, so every evidence link scrolls to its line.

## 3. The collapsible rail

Working as asked: expanded it is 210px with labels; collapsed it is 64px with
icons only. The preference persists, and below 1080px it collapses on its own
without overwriting what the user chose.

Verified live: reload restored `64px` from the stored preference, and toggling
returned it to `210px`.

Collapsed, every link keeps its accessible name — the label is visually hidden,
not removed — and carries a tooltip. An icon nobody can identify is not a smaller
menu, it is a worse one.

## 4. Defects found and fixed

**1. Migrations were silently deleting every child row — the worst defect so far.**
Opening a stored call failed with *"A transcript must contain at least one speaker
turn."* Both stored calls had lost their turns, layers, markers, signals and
events.

Cause: SQLite cannot ALTER most columns, so Alembic's `batch_alter_table` drops
and recreates the table. With `PRAGMA foreign_keys=ON` — which the application
engine sets — that DROP performs an implicit `DELETE FROM`, firing every child
table's `ON DELETE CASCADE`. **Two migrations that only added a column emptied
the database**, and nothing reported it.

In P4 I found this cascade for `call_signals` and fixed only that one table. The
same mechanism was destroying all the others, and I did not look further. Fixed
properly: `env.py` now disables foreign keys for the migration connection, which
is the documented approach for SQLite batch migrations — the application still
enforces them at runtime.

Guarded by `tests/audit/test_migrations_preserve_data.py`, which seeds a call
*with children* at the first revision, migrates to head, and asserts every child
table survives. It fails on the old code.

The two dev calls were unrecoverable and were removed; one was re-analysed to
give the UI real data.

**2. The collapse silently did nothing.** The DOM said collapsed, the preference
saved, every unit test passed — and the rail stayed 210px wide. Transitioning
`grid-template-columns` between values containing `fr` leaves the property stuck
at its start value in Chromium. Disabling the transition made it snap correctly.

The animation was decorative and the prototype has none, so it was removed.
jsdom does no layout, so no rendering test can catch this; `railStyles.test.ts`
reads the stylesheet and fails if the transition returns.

**Both defects share a shape worth naming: the system reported success while
doing nothing.** Neither would have been caught by the test suite as it stood;
both needed the running application.

## 5. What was built

| Component | Responsibility |
|---|---|
| `shared/api/schema.ts` | **Generated** from the backend's OpenAPI document |
| `shared/api/types.ts` | Aliases over the generated schema — nothing hand-written |
| `shared/api/endpoints.ts` / `queries.ts` | Every call in one place; query keys declared once |
| `app/layout/AppShell.tsx` | Collapsible rail plus content area |
| `shared/ui/primitives.tsx` | Card, Chip, Alert, Button and the loading / empty / failure states |
| `features/analyze/` | Transcript box, live turn counter, provider picker |
| `features/call-detail/` | Five layers, evidence, transcript highlighting |
| `cli/openapi.py` | Writes the OpenAPI document, so types can be regenerated |

**The audit checklist item for OpenAPI-generated types is now closed.** The
hand-written health types from P0 are deleted; `npm run generate:api` regenerates
from the backend. A contract change the frontend has not accounted for is a build
failure.

**Transcript highlighting uses the stored turn index and quote**, matched with
the same whitespace-and-case tolerance the backend validator uses. Searching the
text in the browser would highlight the wrong line whenever words repeat, and
would silently disagree with the evidence the score was computed from.

**The turn counter mirrors the backend parser**, including folding wrapped
continuation lines into the turn above, and is tested against the same corpus
extract the backend's parser tests use. If they disagreed, the box would say
"12 turns" and the analysis would say 6.

## 6. Decisions taken during P5

| # | Decision | Reasoning |
|---|---|---|
| P5-1 | The rail lists only screens that exist | Overview, Calls and Brokers arrive in P6; a nav entry to an empty page is a worse lie than a short rail |
| P5-2 | Unknown routes land on Analyze | Nothing has been analysed on a fresh install, so a dashboard would be an empty room |
| P5-3 | A withheld score shows its number and reason | A reviewer needs to know how bad a call looks while it waits for sign-off |
| P5-4 | An unavailable layer is drawn differently from an empty one | "Nothing fired" is a finding; "L5 unavailable" is a fault |
| P5-5 | Unusable providers are listed with the reason | A choice that silently vanished tells the user nothing |
| P5-6 | The Analyze screen states the wait up front | Four minutes on a local model; a bare spinner looks stuck |

## 7. Known gaps

- **No Calls list yet.** Call detail is reachable from a completed analysis or by
  URL. The list is P6, and without it there is no way back to an earlier call
  from the UI.
- **Model quality, unchanged.** The re-analysed Call #89 again scored 74 AVERAGE,
  classified the call as Provider Network, and marked it RESOLVED. The UI is
  faithfully displaying what P3 §5 documented. It is now visible on a screen a
  stakeholder would look at.

## 8. Next phase

**P6 — Dashboards.** Overview, Calls and Brokers screens against the read models
finished in P4, including the attention queue, the bimodal histogram, and the
resolution-by-agent bars. Exit criterion: all four corpus views reproduced from
live data.

The model question from P3 §7 is still open and is now the largest risk to the
demo: P6 puts those figures on the first screen anyone sees.

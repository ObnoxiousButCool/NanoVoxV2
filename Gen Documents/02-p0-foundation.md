# P0 — Foundation: completion record

**Status:** Complete. All exit criteria met.
**Date:** 2026-08-28
**Plan reference:** [01-implementation-plan.md](01-implementation-plan.md) §10, phase P0

---

## 1. Exit criteria

| Criterion (plan §10) | Status | Evidence |
|---|---|---|
| Both servers start | Met | Backend on :8000, Vite on :5173; the diagnostics page renders live data from the API |
| Health endpoint green | Met | `GET /api/v1/health` → 200, `{"status":"up","components":[{"name":"database","status":"up"}]}` |
| Dependency-rule contract passes | Met | import-linter: **3 contracts kept, 0 broken** |
| CI configured | Met | `.github/workflows/ci.yml` plus `scripts/verify.{bat,sh}` running the identical gates locally |

## 2. Gate results

| Gate | Result |
|---|---|
| Backend format (`ruff format --check`) | Pass |
| Backend lint (`ruff check`, 17 rule families incl. bandit, no-print, no-TODO, no-commented-code) | Pass |
| Backend types (`mypy --strict`) | Pass — 50 source files, no `Any`, no `type: ignore` |
| Architecture contracts (`lint-imports`) | 3 kept, 0 broken |
| Backend tests | **58 passed**, coverage **98.4%** (floor 85%, build fails below) |
| Frontend lint (`eslint`, `strictTypeChecked`) | Pass |
| Frontend types (`tsc --build`) | Pass — strict, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` |
| Frontend tests | **30 passed**, statements **100%**, branches 96% |

Domain layer coverage is 100%.

## 3. What was built

### Backend (`Code/Backend`)

The four Clean Architecture layers exist and are enforced, exercised by one thin
vertical slice (health) that proves the wiring rather than stubbing it:

- `domain/` — error hierarchy with stable codes; health value objects carrying the
  rule that *healthy means every component is up*. Zero framework imports, enforced.
- `application/` — `Clock` and `HealthProbe` ports; `GetHealth` use case, which
  probes concurrently and reports a probe that breaks its own contract as `DOWN`
  rather than letting it take down the endpoint.
- `infrastructure/` — typed settings with fail-fast validation; flag-controlled
  structured logging; async SQLAlchemy engine with WAL, foreign keys and a busy
  timeout; Alembic wired to the application's own database URL.
- `frameworks_drivers/` — app factory, composition root, middleware stack, RFC 9457
  error handling, `/api/v1/health`.

### Frontend (`Code/Frontend`)

React 18 + TypeScript (strict) + Vite 6, TanStack Query, CSS Modules over the
prototype's design tokens copied verbatim. No UI kit, no chart library (plan A2).

The Diagnostics screen is deliberately the first one built: it answers "why is
nothing loading?", and it establishes the loading / empty / error / correlated-error
states that every later data surface is required to have.

## 4. Decisions taken during P0

| # | Decision | Reasoning |
|---|---|---|
| P0-1 | **Target Python ≥ 3.10, not 3.11+** | `python` on the target machine is 3.10.11 (`py` resolves to 3.14.6). The old README claimed 3.11+. The code avoids 3.11-only constructs (`tomllib`, `StrEnum`, `ExceptionGroup`) so it runs on the interpreter that is actually installed. CI pins 3.10 to keep that honest. |
| P0-2 | **Async SQLAlchemy + aiosqlite** | The corpus runner (P7) needs concurrent, cancellable work alongside SSE progress. Choosing sync now would mean rewriting the persistence layer then. |
| P0-3 | **Daily log rotation with `LOG_RETENTION_DAYS`**, replacing the plan's `LOG_ROTATION_MB` | The standard library cannot rotate by both size and time in one handler. Time-based retention is what an operator actually reasons about, and it is one setting rather than two that interact confusingly. |
| P0-4 | **No `@app.exception_handler(Exception)`; a middleware catch-all instead** | Starlette routes an `Exception` handler to `ServerErrorMiddleware`, which sits *outside* all user middleware — so its response never passes back through the correlation middleware and reaches the client with no `X-Correlation-ID`. Catching inside the stack fixes that. Found by a test, not by review. |
| P0-5 | **Middleware order: CORS → CorrelationId → UnhandledError → RequestLogging** | CORS outermost so the browser can read error responses; correlation above the error catch-all so even a 500 carries a traceable ID. |
| P0-6 | **`expose` is a per-error decision, not a status-code rule** | The first draft genericised every response ≥ 500, which silently swallowed the detail of a legitimate 503 ("model provider unreachable"). Now each error type declares whether its detail is safe to disclose. |
| P0-7 | **Literal `422` behind a named constant** | `http.HTTPStatus.UNPROCESSABLE_CONTENT` exists only on 3.13+; Starlette has deprecated its `HTTP_422_UNPROCESSABLE_ENTITY` alias. No spelling is both available and undeprecated across supported versions. |
| P0-8 | **`httpx2` as a test dependency** | Starlette's `TestClient` now deprecates `httpx`. Following the library's guidance beat muting the warning. |
| P0-9 | **Vitest 3, not 2** | Vitest 2 bundles its own Vite 5, which collides with Vite 6 and produces two incompatible copies of the plugin types. |
| P0-10 | **Settings arrive with the phase that uses them** | `.env.example` documents only what exists today. An audit test asserts `.env.example` and the settings class stay in exact sync in both directions, so a setting cannot be added without being documented, nor documented without existing. |
| P0-11 | **`cx()` class-name helper** | With `noUncheckedIndexedAccess`, CSS-module lookups are correctly typed `string | undefined` — a typo really does yield undefined. The helper keeps that safety instead of loosening the compiler. |

## 5. Corrections to pre-existing files

`scripts/` predated this work and contained two defects:

1. **`start.sh` and `start.bat` referenced `Code/backend` and `Code/frontend` in
   lowercase.** Harmless on Windows, but a hard failure on macOS and Linux, where
   the directories are `Code/Backend` and `Code/Frontend`. Corrected in both.
2. **`README.md` documented an NVIDIA provider** that is not in scope, and claimed
   Python 3.11+. Rewritten to match the agreed provider list and the real floor.

## 6. Audit checklist status (plan §13)

| Item | Status |
|---|---|
| Dependency rule enforced in CI | Done — import-linter, 3 contracts |
| No hardcoded URLs, keys, paths, thresholds | Done — enforced by `tests/audit/test_no_hardcoded_configuration.py`, which fails if a URL or absolute path appears outside `infrastructure/config` |
| Every config value documented in `.env.example` | Done — bidirectional parity test |
| Fail-fast startup validation | Done — configuration, log directory and database connection all verified at startup |
| Typed end to end | Done — mypy strict, TS strict; no `any`, no unjustified ignores |
| Structured logging, flag honoured both ways | Done — with `LOG_ENABLED=false` no directory is created at all |
| RFC 9457 errors, no stack traces to client | Done — tested that internal detail never reaches the body |
| Migrations from commit one | Done — Alembic wired; no revisions yet because P0 defines no tables, guarded by an explicit test |
| Coverage gates met | Done — backend 98.4% (floor 85), frontend 100% statements |
| No TODO/FIXME or commented-out code | Done — enforced by ruff `FIX` and `ERA` rules |
| No mock or placeholder data | Done — the only screen reads live backend data |
| Loading, empty and error states | Done on Diagnostics, including the empty-components case |
| WCAG 2.1 AA | Partial — semantic landmarks, `role="status"`/`role="alert"`, tokens carry the prototype's contrast. Full keyboard and contrast audit lands with the real UI in P5/P6 |
| OpenAPI-generated frontend types | Deferred to P4 as planned — health types are hand-written and marked as such |
| README and runbook accurate | Done |

Two items remain open by design and are scheduled, not forgotten.

## 7. Verification

```bash
./scripts/verify.sh
```

```bat
scripts\verify.bat
```

Runs every gate above in CI order. Current result: **all gates passed**.

## 8. Next phase

**P1 — Domain and rubric.** Entities, value objects, the deterministic rubric
engine and its gates, plus the taxonomy and rubric loaders. Exit criteria: rubric
unit tests at ≥ 95% branch coverage, and Call #89's markers reproducing a
provisional score through the clinical gate.

Two non-blocking questions from plan §15 remain open: the default Ollama model,
and whether you want to set the attention-queue thresholds yourself. Neither
blocks P1.

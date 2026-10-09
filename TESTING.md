# HealthCore Test Plan and Results

## Purpose and phase

This document tracks Phase 5 testing for the HealthCore authentication API and applicable internal TypeScript auth utilities, based on the official [ai-eng-building-bullet-proof-applications syllabus project](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/projects/ai-eng-building-bullet-proof-applications/README.md).

Detailed execution plan: [`services/api/PHASE_5_TESTING_PLAN.md`](services/api/PHASE_5_TESTING_PLAN.md).

## Planned coverage

Every endpoint below must have happy-path, edge-case, and failure-mode coverage, either in a focused test or a clearly identified shared test. Existing test coverage is to be inventoried before adding tests.

| Endpoint | Happy path | Edge cases | Failure modes |
|---|---|---|---|
| `POST /users` | Register user; optional profile creation | normalized/duplicate email; absent optional profile; UTF-8 password byte boundary | invalid/missing fields; privilege or extra fields |
| `POST /auth/login` | Issue bearer token | normalized email; active status | unknown account; wrong password; inactive user; malformed hash; invalid body |
| `GET /auth/me` | Safe identity with/without profile | valid identity and profile state | missing, malformed, expired, bad-signature, unknown-subject, inactive-user token |
| `POST /auth/forgot-password` | Generic confirmation for known active account | unknown/inactive account; repeat request | provider failure does not enumerate or leave live reset token |
| `POST /auth/reset-password` | Reset password and consume token once | expired, superseded, reused, concurrent redemption | unknown/malformed token; invalid password/body |
| `POST /auth/change-password` | Change password and verify new login | reset-token invalidation; password boundaries | unauthenticated; wrong current password; invalid body |
| `GET /users` | Admin lists users | list includes safe response fields | unauthenticated; non-admin |
| `GET /users/{id}` | Self/admin read | self vs admin ownership | unauthenticated; cross-user; missing user |
| `PUT /users/{id}` | Permitted user/admin update | email normalization/duplicate; empty/null updates | unauthenticated; cross-user; unauthorized privilege/password update; invalid body; missing user |
| `DELETE /users/{id}` | Permitted deletion and profile cascade | self/admin policy | unauthenticated; cross-user; missing user |
| `GET /profiles/me` | Read own profile | account without profile | unauthenticated; missing profile |
| `PUT /profiles/me` | Update own profile | nullable optional fields | unauthenticated; invalid/empty input; missing profile |

Applicable TypeScript utility candidates in `uis/backoffice/lib/auth.ts`: token storage and clearing, API error allowlisting, and response parsing for successful JSON, safe error details, unknown details, and non-JSON responses. Broader backoffice endpoint and multi-utility suites are optional syllabus extras and are not included by default.

## Test commands and results

Environment used: Linux, Python 3.12.1 in `services/api/.venv`, pytest 9.1.1, pytest-cov 7.1.0, Node 22.15.0, Vitest 3.2.7, Next.js 16.3.6.

The API test extra now declares `pytest-cov`. From `services/api`:

```sh
uv sync --extra test
uv run pytest -q
uv run pytest --cov=auth --cov=routes.auth --cov=routes.users --cov=database --cov=models_auth --cov-report=term-missing --cov-fail-under=70
```

Results on this Phase 5 worktree:

- `python -m pytest -q`: **34 passed** on final run, with two non-blocking deprecation warnings (Starlette's TestClient/httpx integration and telemetry use of `HTTP_422_UNPROCESSABLE_ENTITY`).
- `python -m pytest --cov=auth --cov=routes.auth --cov=routes.users --cov=database --cov=models_auth --cov-report=term-missing --cov-fail-under=70`: **34 passed** on final run, **90.12% combined coverage**, exceeding the 70% gate. Per-module coverage: `auth/dependencies.py` 100%, `auth/recovery.py` 53%, `auth/security.py` 89%, `auth/settings.py` 86%, `database.py` 94%, `models_auth.py` 96%, `routes/auth.py` 100%, `routes/users.py` 89%. The reset-email provider construction/sending implementation in `auth/recovery.py` remains partially uncovered because tests mock delivery; no real provider credentials or delivery were used.
- From `uis/backoffice`, `npm test`: **7 passed** in `lib/auth.test.ts` (token storage, safe API error allowlisting, successful/error/non-JSON response parsing).
- From `uis/backoffice`, `npm run lint`: passed.
- From `uis/backoffice`, `npm run build`: passed.
- Commands were invoked with the API venv's Python executable because no root workspace runner is configured. `uv sync --extra test` remains the documented reproducible dependency setup command.

## AI-assisted test discovery

AI assistance is being used to compare the endpoint contracts and current tests against the three required categories (happy path, edge case, failure mode), identify missing assertions, and propose regression scenarios. Every proposed case is checked against the actual route, model, and authorization policy before implementation; no speculative contract changes are accepted.

**Findings/bugs uncovered:** No application behavior regression was found by the added gap tests. One test-authoring failure (`NameError` from misplaced pre-existing authorization assertions) was corrected before the passing run. One Vitest setup failure (`window` absent in the Node environment) led to a focused localStorage stub; no DOM dependency was needed. Delivery to a real email provider remains unverified and is not claimed.

## Execution results

Phase 5 test suites and the 70% coverage gate currently pass. The endpoint matrix audit and staged-path review are still required before the phase snapshot. Existing suite coverage complements the newly added cases; see [`services/api/PHASE_5_TESTING_PLAN.md`](services/api/PHASE_5_TESTING_PLAN.md) for scope and contracts.

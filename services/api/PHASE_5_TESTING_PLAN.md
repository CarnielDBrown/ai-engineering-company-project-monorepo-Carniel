# Phase 5 — Building Bullet-Proof Applications: Test Plan

## Goal and authoritative source

Create and execute an endpoint-oriented test plan for HealthCore's authentication API, including happy paths, edge cases, and failure modes. Meet the syllabus requirement of at least 70% coverage for the authentication implementation, and add applicable TypeScript utility tests. Record AI-assisted test discovery and any bugs found in the root `TESTING.md`.

Authoritative syllabus: [ai-eng-building-bullet-proof-applications](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/projects/ai-eng-building-bullet-proof-applications/README.md).

## Phase gate and branch

Phase 4 is implemented, validated, and pushed at `feature/auth-recovery` commit `6a8eef0`. Phase 5 starts from that snapshot on `feature/bullet-proof-tests`. The worktree contains unrelated dirty/untracked files; preserve them and stage only explicitly reviewed Phase 5 paths. Never modify `uis/website` or include local data, environments, generated artifacts, secrets, or unrelated backoffice edits.

## Scope

- Inventory every authentication, user, and profile endpoint and map existing tests to happy-path, edge, and failure cases.
- Add only tests needed to close documented endpoint coverage gaps; preserve existing contracts and implementation unless a reproducible bug is found.
- Measure coverage across the authentication dependency/security/recovery helpers and auth/user/profile route handlers. The threshold must be at least 70%.
- Add Jest tests for applicable existing TypeScript auth utilities in `uis/backoffice/lib/auth.ts`, if the smallest compatible setup can run under the repository's Node/Next environment.
- Create root `TESTING.md` with the detailed test matrix, commands, suite coverage, measured results, AI-assisted discovery method, and bugs found (or explicitly none).
- Keep syllabus extras optional: additional broad backoffice endpoint and three-utility frontend suites are out of required scope unless evidence shows they are necessary to validate existing authentication helpers.

## Endpoint test matrix

Endpoints in scope:

- `POST /users` — success creates safe user and optional profile; edge cases include omitted optional profile fields, normalized email, bcrypt UTF-8 byte limit; failures include duplicate email, invalid/missing fields, forbidden privilege/extra fields.
- `POST /auth/login` — success returns bearer token; edge cases include normalized email and account state; failures include unknown email, wrong password, inactive account, malformed stored hash, invalid payload.
- `GET /auth/me` — success returns safe identity with or without profile; failures include absent, malformed, expired, invalid-signature, unknown-subject, and inactive-user token.
- `POST /auth/forgot-password` — same response for active known and unknown accounts; edge cases include inactive account and repeated request; failure includes provider exception without leaking details or leaving an active token.
- `POST /auth/reset-password` — success changes password and consumes token once; edge cases include expired, unknown, superseded, repeated, concurrent token redemption; failures include malformed token/password and invalid request body.
- `POST /auth/change-password` — success verifies replacement login and invalidates reset tokens; failures include unauthenticated request, incorrect current password, malformed payload, and password byte/length boundaries.
- `GET /users` — admin success; unauthenticated and non-admin denial.
- `GET /users/{user_id}` — self/admin success; unauthenticated, cross-user non-admin, and missing-user cases.
- `PUT /users/{user_id}` — allowed self/admin updates; edge cases include duplicate email, empty update, null/invalid fields; failures include unauthenticated request, cross-user denial, non-admin role/status/password changes, and missing user.
- `DELETE /users/{user_id}` — self/admin allowed behavior and profile cascade; unauthenticated, cross-user, and missing-user cases.
- `GET /profiles/me` — success and unauthenticated behavior; missing-profile result for an account created without profile data.
- `PUT /profiles/me` — success; invalid/empty fields, unauthenticated request, and missing-profile behavior.

Before adding tests, compare each matrix entry with current tests to avoid duplicating coverage. If actual route policy differs from the stated test expectation, document the repository's current contract and avoid speculative API changes.

## TypeScript utility scope

Applicable existing auth utilities: token storage/clearing, safe API error allowlisting, and `readApiResponse()` handling of valid JSON, safe error details, unknown details, and non-JSON responses. `authFetch()` requires browser globals and is only included if it can be tested without brittle mocking or changing production behavior. Do not invent redundant frontend authentication logic. Document any runner/environment limitation and whether those utilities are genuinely tested.

## Coverage approach

- Add `pytest-cov` to the API's `test` optional dependency if absent.
- Use the API environment and run the full API suite, then measure only authentication-owned implementation to prevent suppliers/incidents from distorting the threshold. Measured modules: `auth`, `routes.auth`, `routes.users`, `database`, and `models_auth`; `auth/recovery.py` remains partially covered because provider delivery is mocked and no real email credentials are used.
- Record exact interpreter/tool versions, test counts, coverage percentage, and command in `TESTING.md`.
- Do not claim the gate passes unless coverage is >=70% and required tests pass.

## Validation commands

From `services/api` after syncing the test extra:

```sh
uv sync --extra test
uv run pytest -q
uv run pytest --cov=auth --cov=routes.auth --cov=routes.users --cov=database --cov=models_auth --cov-report=term-missing --cov-fail-under=70
```

Run the selected backoffice Jest command from `uis/backoffice`, plus existing `npm run lint` and `npm run build` if utility test setup or implementation changes warrant them. At completion, run `git diff --check` and inspect the full staged file list before snapshot.

## Exclusions and safety

- No production feature changes unless tests reproduce a specific defect and the smallest fix is within Phase 5's stated objective.
- No public website changes.
- No real PHI, credentials, reset tokens/links, provider payloads, or production/local database contents in fixtures, logs, or docs.
- No broad extra suites that are explicitly optional in the syllabus, unless separately authorized.
- No staging/committing until acceptance evidence and staged paths are reviewed; the user requests a snapshot/commit after each completed phase.

## Status

Endpoint inventory and the initial gap assessment are complete. Added tests exercise inactive-account login/recovery, `/auth/me` token rejection, safe admin listing, missing-user behavior, user/profile validation failures, and password endpoint request validation. The full API suite has 34 passing tests; measured authentication-module total is 90.12%. Backoffice auth utility tests pass (7 tests), and lint/build passed. Exact commands, warnings, test evidence, and remaining matrix limitations are recorded in root `TESTING.md`; final documentation/matrix audit and snapshot review remain.

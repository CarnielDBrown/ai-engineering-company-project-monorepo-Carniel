# HealthCore Authentication Saga

## Purpose

Deliver HealthCore's internal application and inventory work in ordered, independently verifiable phases. This document is the cross-project roadmap; implementation details and task checklists belong in a phase plan created immediately before that phase starts.

## Scope and guardrails

- Build a centralized FastAPI authentication service in `services/api`; persist users and profiles in TinyDB, separate from supplier data.
- Keep the public `uis/website` unauthenticated and unchanged. Authentication UI belongs only in the existing internal application(s) selected for the frontend phase.
- Use stateless bearer JWTs for access authentication. Never introduce cookie/session auth as a substitute, hardcode signing keys, or commit credentials.
- Keep credentials and authorization metadata on User; keep display/contact data on a one-to-one Profile. Minimize exposure of personal information and never log credentials, tokens, or reset links.
- Preserve existing application behavior except for the deliberate authentication boundary. Review the authorization impact of every protected endpoint, including incident-analysis access, before applying protection.
- Follow repository ownership, validation, and minimal-change guidance. Keep phase snapshots free of unrelated pre-existing worktree changes.

## Ordered phases and gates

### Phase 1 — Authentication API

**Source specification:** [ai-eng-user-authentication-api](https://github.com/4GeeksAcademy/ai-engineering-syllabus/tree/main/content/projects/ai-eng-user-authentication-api)

Provide TinyDB-backed user/profile lifecycle and permissions, password hashing, login and identity endpoints, environment-configured JWT issuance/validation, and bearer protection for the agreed existing API surface. Establish automated security and regression coverage.

**Exit gate:** API acceptance criteria are implemented; tests verify registration/login, valid and invalid authentication, authorization boundaries, persistence, and existing protected-route behavior; configuration and local setup are documented without secrets. Snapshot this phase on its own branch before starting phase 2.

### Phase 2 — Internal authentication flows

**Source specification:** [ai-eng-user-authentication-flows](https://github.com/4GeeksAcademy/ai-engineering-syllabus/tree/main/content/projects/ai-eng-user-authentication-flows)

Integrate registration, login, profile, protected-route, logout, and expired/unauthorized-session behavior into the existing internal Next.js experience. Store the access token in local storage and send it as a bearer token. Keep the public website unaffected.

**Dependency:** Phase 1 API contract and branch snapshot.

**Exit gate:** Internal-user flows work against the API, protected navigation and API 401 handling behave consistently, and relevant UI checks pass. Snapshot this phase separately before starting phase 3.

### Phase 3 — Password recovery and change

**Source specification:** [ai-eng-user-authentication-restore](https://github.com/4GeeksAcademy/ai-engineering-syllabus/tree/main/content/projects/ai-eng-user-authentication-restore)

Add forgot-password, reset-password, and authenticated change-password capabilities to the API and internal UI. Use a transactional email provider for reset links, keep email credentials in environment configuration, make reset tokens short-lived and single-use, and avoid revealing whether an account exists.

**Dependency:** Phases 1 and 2, including their snapshots.

**Exit gate:** End-to-end recovery/change behavior is covered, email configuration and local testing are documented, enumeration and token-reuse protections are tested, and the phase is snapshotted separately.

### Phase 4 — Error handling

**Source specification:** [ai-eng-error-handling](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/projects/ai-eng-error-handling/README.md)

Review the frontend, FastAPI backend, and project scripts for failure paths. Add scoped error handling, user-readable error states and recovery actions, safe defaults for uncertain data, structured backend errors that do not leak sensitive details, and reliable loading cleanup. Handle script input and file errors with actionable stderr messages and non-zero exits where required.

**Dependency:** Phase 3, including its reviewed phase snapshot.

**Exit gate:** Async UI operations expose loading, success, and actionable error states; API and script failures are handled at the relevant operation scope without sensitive output; and targeted lint, tests, and error-path checks pass. Snapshot this phase separately before starting phase 5.

### Phase 5 — Building bullet-proof applications

**Source specification:** [ai-eng-building-bullet-proof-applications](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/projects/ai-eng-building-bullet-proof-applications/README.md)

Create and execute a documented test plan for the authentication API, covering happy paths, edge cases, and failure modes for each endpoint. Add TypeScript utility tests where applicable and document AI-assisted test-case discovery and any bugs uncovered. The syllabus also lists backoffice endpoint and frontend utility suites as extra activities; keep them explicitly optional unless project scope is expanded.

**Dependency:** Phase 4, including its reviewed phase snapshot.

**Exit gate:** A root-level `TESTING.md` records planned cases, suite coverage, run commands, and results; the required API and applicable TypeScript tests pass; and authentication-module coverage is at least 70% using the syllabus-prescribed coverage run. Snapshot this phase separately after reviewing the staged paths and results.

### Phase 6 — Backend inventory development

**Source specification:** [ai-eng-milestone-backend-development](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/projects/ai-eng-milestone-backend-development/README.md)

Extend the existing centralized FastAPI service with a dedicated `/inventory` API. Retain TinyDB for authentication and user lookup, and use SQLModel with Supabase PostgreSQL for inventory and order data. Define HealthCore-specific product, inbound-order, and outbound-order entities and separate request/response schemas using the authoritative backend company context. Compute stock from order history instead of storing an editable quantity, enforce product foreign keys and authenticated access, reject outbound orders that exceed available stock, and seed only the context-specified records. Avoid N+1 order/product reads.

**Dependency:** Phase 5, including its reviewed phase snapshot. The prior authentication API and its TinyDB user UUID contract must remain intact.

**Exit gate:** All required `/inventory` routes are functional and covered for success, validation, authorization, missing product, and insufficient stock; both database connections are configured and used for their intended domains; ORM relationships enforce product foreign keys; computed stock is verified against orders and cannot be set directly; context seed data is documented; and database-dependent checks run against a test/local instance without exposing real credentials. Snapshot this backend phase separately before starting phase 7.

### Phase 7 — Inventory management backoffice

**Source specification:** [ai-eng-inventory-management-backoffice](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/projects/ai-eng-inventory-management-backoffice/README.md)

Add authenticated inventory views to the existing `uis/backoffice` application: a product/stock list with low-stock visual cues, inbound and outbound order forms, and a read-only order history showing product and creator. The outbound form must display current available stock before submission. Consume live Phase 6 API data through the existing secure server-side backoffice/API integration and show actionable API failures without leaking sensitive details.

**Dependency:** Phase 6, including its reviewed backend snapshot and documented API contract.

**Exit gate:** The four inventory views operate against the live inventory API; unauthenticated access redirects to login; outbound stock is shown before submit and API rejection/errors are handled; relevant frontend tests, lint, and build pass. Snapshot this phase separately after reviewing staged paths and results.

## Delivery protocol

1. Keep this saga at roadmap level; do not pre-write detailed plans for phases that have not started.
2. At the start of a phase, verify the prior phase's branch snapshot and create a focused, phase-specific implementation plan from its authoritative specification and the current repository state.
3. Implement only that phase's scope; run targeted tests and relevant regressions; update owning documentation and the memory-bank with verified outcomes.
4. Before snapshotting, inspect staged paths and ensure no unrelated user changes, generated artifacts, secrets, or local data are included. Record the branch and validation evidence.
5. Do not begin the next phase until the current phase passes its exit gate and is snapshotted.

## Current status

- Phase 1 — Authentication API: implemented and validated on branch `feature/auth-api`, commit `beba6d9` (`feat(api): add JWT authentication`). Validation recorded in `services/api/AUTHENTICATION_API_PLAN.md`.
- Phase 2 — Internal authentication flows: implemented and validated on branch `feature/auth-frontend`, including API-response hotfix snapshot `7b4c555`.
- Phase 3 — Password recovery and change: implemented and snapshotted on the pushed branch `feature/auth-recovery` at `2af5061`; API suite (**22 passed**), backoffice lint/build, and editor diagnostics passed. Real Resend delivery remains unverified without user-supplied provider configuration; see `services/api/PASSWORD_RECOVERY_PLAN.md`.
- Phase 4 — Error handling: implemented, validated, and snapshotted in pushed commit `6a8eef0` on `feature/auth-recovery`; see `services/api/ERROR_HANDLING_PLAN.md` for checks and the pandas runtime limitation.
- Phase 5 — Building bullet-proof applications: started from the verified Phase 4 snapshot on `feature/bullet-proof-tests`; see `services/api/PHASE_5_TESTING_PLAN.md` for the active plan.
- Phase 6 — Backend inventory development: implementation and local validation were snapshotted at `db00690` on `feature/bullet-proof-tests`; see `services/api/PHASE_6_INVENTORY_BACKEND_PLAN.md`. Shared Supabase schema/revision presence was later observed read-only, but this does not establish deployment approval or release governance. The `.env.example` database placeholder and release-operations details remain open.
- Phase 7 — Inventory management backoffice: in progress on `feature/inventory-backoffice`, based on the Phase 6 snapshot; see `services/api/PHASE_7_INVENTORY_BACKOFFICE_PLAN.md`. Page and auth-request tests have been added; tests, lint, and build pass. A browser-driven live API/auth-redirect run remains outstanding, so the Phase 7 exit gate is not yet claimed as passed.
- The worktree contains unrelated changes and generated/local artifacts. Preserve them and stage only explicitly reviewed phase-owned files.

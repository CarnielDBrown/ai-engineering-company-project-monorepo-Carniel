# Phase 8 — Centralized Incident Manager

## Goal and source

Implement the HealthCore incident register in the existing centralized FastAPI service and authenticated backoffice, following the [Centralized Incident Manager briefing](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/contexts/centralized-incident-manager/healthcore-BRIEFING.en.md).

The root `CONTEXT.md` is absent in this worktree. The linked HealthCore briefing is the source for this phase; use `memory-bank/contexts/CONTEXT.md` for applicable company and privacy constraints. Keep all incident data out of the existing aggregate-only analyzer contract.

## Phase boundary and safety

- Start from the pushed Phase 7 snapshot on `feature/inventory-backoffice`; do not alter or re-snapshot Phase 7.
- Keep the manager separate from the existing `/api/incidents/analyze` and export endpoints.
- Add SQLModel tables and an additive Alembic revision. Never create or migrate SQL schema on API startup.
- Require the existing bearer authentication for every manager endpoint. Store actor UUIDs for audit; do not introduce a SQL user table.
- Do not model patient names, dates of birth, medical record numbers, contact details, patient IDs, or the source CSV `incident_id`. Do not log request bodies, descriptions, corrective-action text, or CSV rows.
- Show a prominent warning before any free-text input: do not enter identifying patient data. Preserve patient references only as opaque identifiers if a future approved requirement adds them; this phase has no patient-reference field.
- Keep the source CSV local and out of the phase snapshot unless it is explicitly approved as a synthetic, non-identifying fixture. Seed only through an explicit command, never app startup.
- Preserve unrelated dirty worktree content. Review and stage only phase-owned paths; do not push the existing user's unrelated changes.

## Scope

- Persist incident title, description, category, branch, status, origin, staff-entered critical flag, created/updated timestamps and actor UUIDs, and corrective action for resolution.
- Implement authenticated create/list/detail/status-update and aggregate-summary endpoints. Support category, branch, status, and date-range filters with bounded pagination.
- Enforce only `open → in_progress`, `open → discarded`, `in_progress → resolved`, and `in_progress → discarded`. Treat `resolved` and `discarded` as final. Require non-empty corrective action when resolving.
- Count critical open incidents by country, deriving country from the defined branch mapping (`central` is US). The briefing does not define criticality criteria; expose the flag for explicit staff classification and document that HealthCore policy is required before operational reliance.
- Seed the anonymized analyzer CSV only on explicit request. Reuse shared row-validation logic, apply the exact status/category/branch mappings, parse dates as midnight UTC, set origin to `customer`, trim/truncate title to 120 characters, discard invalid/unmapped rows with count-only reports, and make repeat imports idempotent without storing raw CSV `incident_id` values.
- Build the `/incident-manager` backoffice workflow with English labels, prominent PHI warnings, filters, status/corrective-action controls, aggregate summary, loading/empty/error states, and same-origin authenticated API requests.
- Document local migration and seed steps without credentials or production URLs.

## Acceptance criteria

1. API tests cover unauthenticated access, schema validation, creation/list/detail, filters/date boundaries, all valid and invalid lifecycle transitions, required corrective action, final states, audit actor metadata, summaries, and no leakage of free-text values in errors/logging.
2. The seed command maps all rows as specified, skips invalid rows without printing record data, is safe to rerun, and yields 94 valid records with expected post-transformation totals: status `open=28`, `resolved=52`, `discarded=14`; category `patient_experience=61`, `billing_error=20`, `other=13`; branches as listed in the briefing.
3. API tests use an isolated database. Migration SQL is reviewed and migration behavior is tested against an isolated PostgreSQL database when available; no shared or production database is touched.
4. Backoffice tests verify authenticated requests, prominent warnings, filtering, lifecycle updates, corrective-action entry, summary rendering, and actionable error/loading/empty states.
5. API tests, backoffice tests, lint, production build, migration checks, and `git diff --check` pass. The local CSV and generated artifacts are not staged.

## Not specified

- Rules or accountable role for classifying incidents as critical; the implementation will not invent a severity scale.
- Authorization roles for creating, updating, discarding, or classifying incidents; all operations remain authenticated-only until policy is specified.
- Retention period, escalation thresholds, notification mechanism, and production database approval.

## Progress

Implementation and local validation are complete. The authoritative syllabus CSV was checked through the shared validator and exact mappings: 100 total, 94 valid, 6 invalid; status `open=28`, `resolved=52`, `discarded=14`; category `patient_experience=61`, `billing_error=20`, `other=13`; all expected branch counts match. A synthetic test CSV verifies insertion, count-only invalid reporting, HMAC idempotency, and rejection before writes for mismatched distributions.

API validation: the full service suite passed (57 passed, 2 opt-in PostgreSQL inventory cases skipped) with `PYTHON_DOTENV_DISABLED=1`; the ignored local API `.env` was not read or modified. Backoffice validation: 25 tests passed, `npm run lint` passed, and `npm run build` passed. Migration validation: the full Alembic history was applied on a disposable local PostgreSQL 16 database from `0001_initial_inventory`; a synthetic inventory row survived the upgrade to `0002_incident_manager`; both manager tables existed; `alembic check` reported no drift. The temporary database was removed. No shared or production database was accessed.

The untracked workspace file `scripts/incidents-healthcore.csv` has a different clinic/branch distribution from the authoritative syllabus sample. The importer now refuses that file before writing. The authoritative CSV at the linked syllabus path matches all expected aggregate counts. Keep the workspace copy out of the phase snapshot.

Phase 8 is isolated on `feature/incident-manager`, based on the pushed Phase 7 branch. Reviewed phase-owned paths are staged; unrelated user changes and local artifacts remain outside the snapshot.
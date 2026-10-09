# Phase 6 — Backend Inventory Development

## Goal and sources

Extend the centralized FastAPI service with authenticated HealthCore medical-supply inventory using SQLModel/PostgreSQL, while retaining TinyDB for authentication and user lookup.

- Milestone source: [`CONTEXT-healthcore.en.Milestone5.md`](../../CONTEXT-healthcore.en.Milestone5.md)
- Syllabus: [ai-eng-milestone-backend-development](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/projects/ai-eng-milestone-backend-development/README.md)
- Ordered roadmap: [`docs/AUTHENTICATION_SAGA.md`](../../docs/AUTHENTICATION_SAGA.md)

The Milestone 5 HealthCore document is authoritative for entity fields, routes, validation, stock calculation, and seed records. Do not invent operational or user data.

## Phase gate and worktree safety

Phase 5 was snapshotted at `07ccd2e` on `feature/bullet-proof-tests`. Phase 6 was implemented and snapshotted at `db00690` on that branch. The current branch `feature/inventory-backoffice` is based on that snapshot. Preserve unrelated modified, deleted, untracked, and generated worktree paths; do not treat their presence as Phase 6 work.

The root `.gitignore` was empty. It now contains ignore rules for local environment files, venvs, API TinyDB JSON, database files, and API test artifacts, while preserving `.env.example`.

## Implemented checklist

| Requirement                                | Status and evidence                                                                                                                                                                                                                                                                                                                                                    |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SQLModel/PostgreSQL driver                 | `sqlmodel` and `psycopg2-binary` are declared in `pyproject.toml` and resolved in `uv.lock`.                                                                                                                                                                                                                                                                           |
| Lazy configured engine and request session | `database.py` has a lazy SQLModel engine factory and request-scoped `get_db`. Missing `DATABASE_URL` raises a clear configuration error; there is no default URL and startup/import does not connect. An authenticated API workflow against the configured inventory database was also verified during Phase 7 validation.                                                                                    |
| Inventory ORM and schemas                  | `models.py` defines `MedicalSupply`, `SupplyDelivery`, and `SupplyConsumption`, including supply relationships and movement foreign keys. `schemas.py` holds strict create/response schemas; `current_stock` is computed response-only.                                                                                                                                |
| API routes                                 | `routes/inventory.py` implements all six required routes and is registered by `main.py`. Every route requires existing bearer auth. Responses use Pydantic schemas.                                                                                                                                                                                                    |
| Computed stock/history                     | Delivery and consumption totals are aggregated; order history batches supply loading rather than querying each order's product separately.                                                                                                                                                                                                                             |
| Validation/overspend                       | Category, unit, country, consumption type, positive quantity, clinic range, and missing supply are validated. Overspend returns the exact context message and occurs before insert. Outbound writes use a transaction and `SELECT ... FOR UPDATE` on the supply row.                                                                                                   |
| TinyDB actor UUID                          | New users receive stable UUID strings. Legacy user records receive and persist a UUID on first lookup. Existing integer IDs and JWT subject/public IDs remain unchanged; no SQL user table was added.                                                                                                                                                                  |
| Local data safety                          | Root ignore rules prevent local `.env`, `.venv`, DB files, TinyDB runtime JSON and test artifacts from accidental staging. `services/api/.env.example` still has no `DATABASE_URL` placeholder; this is a documented setup limitation and remains open.                                                                                                         |
| Development seed data                      | `routes/seed_inventory.py` contains the exact six context supplies, four deliveries (two distinct PPE deliveries), and three consumptions with both types. It is opt-in via `uv run seed-inventory`, inserts missing entries only, and requires an existing active TinyDB user to provide the movement UUID. The command does not create tables or run at API startup. |
| Inventory regression coverage              | `tests/test_inventory.py` covers duplicate SKU rejection, FK enforcement, seed idempotence/exact rows, computed seeded stock through the API, auth, validation, and movement workflows.                                                                                                                                                                                |
| PostgreSQL concurrency test harness        | `tests/test_inventory_postgres.py` is opt-in, rejects non-local hosts and DB names without the `test_` prefix, creates an isolated temporary schema, and tests two concurrent outbound writes against limited stock. It passed on 2026-10-09 against a disposable local PostgreSQL 16 container; one request succeeded and one was rejected.                           |
| Production migration policy                | `PRODUCTION_MIGRATIONS.md` adopts Alembic as the only production schema-change path. Alembic configuration, SQLModel metadata loading, and a manually reviewed clean-install revision for the three inventory tables are present. The API does not run migrations or create tables at startup. Revision `0001_initial_inventory` and the three inventory tables were later observed on the configured shared Supabase database; this confirms schema presence only, not who applied it, the approved release process, or production readiness. |
| Documentation                              | API README describes separate DB configuration, UUID migration, local-only schema caution, the adopted migration policy, and the verified disposable-local PostgreSQL concurrency test. It still needs an explicit `DATABASE_URL` placeholder in `.env.example`.                                                                                                                                                                                           |

## Remaining work / limitations

1. Add a `DATABASE_URL=` placeholder and safety explanation to `services/api/.env.example`; the file remains unchanged.
2. The initial revision is for clean installs only. Before using Alembic against any existing target, inspect its schema/data and explicitly decide whether to use a clean install or a separately reviewed baseline/adoption procedure. Schema presence was observed on shared Supabase, but no migration was run there in this audit.
3. Confirm the production release owner, staging target, backup/recovery procedures, approval roles, and deployment window before any managed migration; these operating details are still **Not specified**.
4. Phase 6 source/validation snapshot exists at `db00690`; a Phase 7 working branch is based on it. Do not infer that shared database schema presence constitutes deployment approval or that API deployment is complete.

## Validation completed

From `services/api`:

- `uv run pytest -q tests/test_inventory.py`: **9 passed** against an isolated in-memory SQLite database.
- `INVENTORY_TEST_DATABASE_URL=postgresql+psycopg2://… uv run pytest -q tests/test_inventory_postgres.py -vv`, pointed at a temporary loopback-only PostgreSQL 16 container: **1 passed**. The test verified concurrent outbound locking; the temporary container and its data were removed afterward.
- `DATABASE_URL=postgresql+psycopg2://… uv run alembic upgrade head`, `uv run alembic check`, and `alembic current` against a temporary loopback-only PostgreSQL 16 database: passed; metadata comparison found no schema drift and the current revision was `0001_initial_inventory`. Offline SQL generation included all three tables without exposing URL credentials. A separate guard test confirmed the intentional downgrade rejection leaves an inserted inventory row intact. All temporary containers were removed afterward. A later read-only inspection of the user's configured Supabase database observed the same revision and all three tables; no migration was run there in this audit.
- `uv run pytest -q tests/test_inventory.py tests/test_inventory_postgres.py` without the opt-in variable: **9 passed, 1 skipped**; the full API suite was **44 passed, 1 skipped**, with two non-blocking Starlette deprecation warnings.
- `uv run python -m compileall -q database.py models.py schemas.py routes/inventory.py routes/__init__.py main.py`: passed.
- Before Phase 6 implementation, the Phase 5 regression suite passed (**35 tests**) and measured auth coverage was **90.12%** (70% minimum). The current full suite, including those regressions, passes.
- Seed idempotence and exact context rows are validated using SQLite. The local PostgreSQL concurrency test passed. The configured shared Supabase endpoint was inspected read-only for its current schema/revision; no schema/data writes were performed as part of this audit.

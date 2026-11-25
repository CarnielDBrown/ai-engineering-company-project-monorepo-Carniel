# API database migration policy

**Status:** Adopted for future SQLModel/PostgreSQL schema changes. Alembic tooling and the clean-install inventory revision were verified against a disposable local PostgreSQL 16 database. On 2026-10-26, the additive incident-manager revision was applied from the prior inventory revision on a disposable local PostgreSQL 16 database; a synthetic inventory row survived, both new tables existed, and `alembic check` reported no metadata drift. This does not authorize changes to the currently configured shared Supabase database.

## Decision

Use **Alembic** as the sole production schema migration mechanism for the centralized SQLModel/PostgreSQL database, including inventory and incident-manager tables. SQLModel metadata describes the current ORM shape, but `SQLModel.metadata.create_all()` is prohibited in deployed environments and must not run during API startup. It remains acceptable only inside isolated automated tests and explicitly disposable local development databases.

The API process must never apply migrations implicitly. Once Alembic is configured, migrations are an explicit, separately invoked deployment/release step (normally `alembic upgrade head` using a one-shot migration job). Do not add an Alembic revision or execute a migration against an existing/shared database until its current schema has been inspected and reconciled with the proposed initial revision.

## Change and release requirements

1. Every production schema change is represented by a committed, uniquely revisioned Alembic migration. Review the generated migration; autogeneration is a draft, not approval. Keep revisions in one reviewed history and do not rewrite revisions already applied to a shared environment.
2. Test each revision against a disposable PostgreSQL database: apply the full history to an empty database and upgrade a copy of the prior revision's schema/data. Add assertions for required constraints, indexes, and data transformations. SQLite route tests are not migration or PostgreSQL-locking evidence.
3. Prefer expand/migrate/contract changes so old and new application versions can coexist during rollout. Make backfills restartable and bounded. Document anticipated locks, duration, data impact, and operational prerequisites in the migration/release notes.
4. Before applying to a production environment, require an environment-specific backup/snapshot and a verified recovery procedure. The release owner reviews the migration and confirms the backup and deployment window. The migration job applies revisions once, checks the resulting revision and application health, then the application is rolled out.
5. Application runtime credentials must not have schema-owner/DDL privileges. Keep migration credentials separate, narrowly scoped, secret-managed, and unavailable to frontend/browser code and normal API runtime.
6. Prefer a corrective forward migration for a migration that has reached a shared environment. A downgrade is permitted only when it is explicitly reviewed, tested as data-safe, and does not discard user/operational data. Restore from backup only through the documented incident/recovery process; migrations are not a backup substitute.
7. Record applied revisions and release evidence per environment. Never use the sample/local database as proof that a production migration ran.

## Not specified

The repository does not define the production hosting/release platform, database owner, approval roles, backup retention or recovery objectives, maintenance windows, or separate staging/production database URLs. Those must be agreed by the service/database owners before the first non-production or production migration. No schema has been migrated under this policy yet.

## Enablement work before first use

- Alembic is declared and locked; `alembic.ini` contains no database credentials, and `migrations/env.py` requires an explicit PostgreSQL `DATABASE_URL` and imports SQLModel metadata.
- `migrations/versions/0001_initial_inventory.py` is a manually reviewed clean-install revision. It creates only the three inventory tables; it is not an adoption/baseline revision for an existing database.
- `migrations/versions/0002_incident_manager.py` adds the manager and audit tables without modifying inventory data. Its presence does not establish approval or application to any shared database; follow the same target inspection, PostgreSQL testing, and release gates as every schema revision.
- `migrations/versions/0002_incident_manager.py` adds the manager and audit tables without modifying inventory data. Its presence does not establish approval or application to any shared database; follow the same target inspection, PostgreSQL testing, and release gates as every schema revision. The Phase 8 PostgreSQL validation used a temporary local container, which was removed after testing.
- The initial revision was applied and compared against ORM metadata (`alembic check` reported no drift) on a disposable loopback-only PostgreSQL 16 database. The initial revision intentionally refuses downgrade because it would delete inventory data. The temporary database was removed after validation.
- Before using the revision against an existing target, inspect that target's schema/data and decide whether it needs a reviewed baseline/adoption procedure. Do not assume it is empty.
- Establish environment-specific backup, recovery, access, and release-owner procedures before production use.

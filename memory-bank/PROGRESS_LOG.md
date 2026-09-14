- 2026-09-14 | Milestone 2 | packages/shared/types | Added typed company entities, generic filtering/sorting, linear and binary search, aggregation reports, and HealthCore enquiry validation. | Add focused automated tests and connect the shared contracts to the next application surface.

# HealthCore Progress Log

Purpose: maintain an append-only timeline of milestone and implementation progress.

## Log Entries

Use this format for each entry:

- Date: YYYY-MM-DD
- Milestone: name or number
- Area: folder or feature
- Change: what was completed
- Next: immediate follow-up

## Entries

- 2026-08-29 | Repo governance | memory-bank | Added mandatory operating rule to use memory-bank for context, technology tracking, and progress updates. | Start logging milestone-specific development updates.
- 2026-08-29 | Repo governance | .agents/rules | Added active rule file to enforce when and how memory-bank must be referenced during implementation tasks. | Use this rule as the default workflow guardrail for future tasks.
- 2026-08-29 | Repo governance | .agents/rules | Added companion rule defining strict one-line templates and validation checks for TECH_STACK and PROGRESS_LOG entries. | Apply template rule to all future memory-bank updates.
- 2026-08-29 | Repo governance | .agents/rules | Added branch origin rule requiring feature branches to use feature/project-name and to be created from the most up-to-date relevant base branch instead of defaulting to main. | Apply this branch workflow for all new projects and features.
- 2026-08-29 | Repo governance | .agents/rules | Updated branch origin rule to use main when main is confirmed up to date with origin/main and no other target branch is specified. | Apply this main-first condition during branch creation.
- 2026-09-11 | Milestone 1 | uis/website | Implemented bilingual semantic landing page with hero, services, why-HealthCore, locations table, footer contact block, and Schema.org MedicalOrganization and MedicalClinic markup. | Review responsive layout on real devices before milestone submission.
- 2026-09-11 | Milestone 1 | uis/website | Implemented patient application form with fieldset grouping, labelled inputs, and required-field markup for all specified field names. | Confirm field names against the milestone specification during review.
- 2026-09-11 | Milestone 1 | uis/website/js | Implemented real-time bilingual validation blocking submission on any error and showing the localized success message on valid submit. | Add automated tests for cross-field validation rules.
- 2026-09-11 | Milestone 1 | uis/website | Removed the insurance section, added French, Arabic, Japanese, and Chinese preferred-language options, and split phone entry into a country-code select plus digits-only number input. | Confirm the reduced field set with the stakeholder.
- 2026-09-11 | Milestone 1 | infra | Exposed the static site on the public Codespaces URL for port 8080 to allow external auditing. | Revoke public port visibility once the external audit is complete.

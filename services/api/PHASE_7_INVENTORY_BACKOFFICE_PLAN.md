# Phase 7 — Inventory Management Backoffice

## Goal and source

Connect the authenticated HealthCore backoffice to the Phase 6 inventory API. The UI must use live API values rather than synthetic stock, keep the bearer token in the existing client auth utility, show useful error/retry states, and never imply that stock is editable directly.

- Roadmap: [`docs/AUTHENTICATION_SAGA.md`](../../docs/AUTHENTICATION_SAGA.md)
- Backend API and data contract: [`PHASE_6_INVENTORY_BACKEND_PLAN.md`](PHASE_6_INVENTORY_BACKEND_PLAN.md)
- Authoritative company requirements: [`CONTEXT-healthcore.en.Milestone5.md`](../../CONTEXT-healthcore.en.Milestone5.md)
- Syllabus project: [ai-eng-inventory-management-backoffice](https://github.com/4GeeksAcademy/ai-engineering-syllabus/tree/main/content/projects/ai-eng-inventory-management-backoffice)

## Phase gate and worktree safety

Phase 6 is snapshotted at `db00690` on `feature/bullet-proof-tests`. Phase 7 is being prepared on `feature/inventory-backoffice` based on that snapshot; the origin remote does not yet have a `feature/inventory-backoffice` branch. Phase 6 pull-request review/merge status is not part of this phase audit and has not been checked. Preserve unrelated pre-existing changes and generated artifacts, avoid overlapping authentication UI paths, and stage only reviewed Phase 7 files.

## Scope

- Add authenticated inventory routes in `uis/backoffice` for product stock, inbound delivery, outbound consumption, and combined order history.
- Use the same-origin `/api` proxy and `authFetch`/`readApiResponse`; do not expose or read API secrets in browser code.
- Show computed on-hand stock and a conspicuous low-stock visual cue. Phase 6 has no reorder threshold field, so any display cutoff must be explicitly presented as a UI advisory, not a configured HealthCore policy; do not add operational data or silently extend the API contract.
- Inbound/outbound forms must validate required values and show server rejections. Display available stock when an outbound product is selected, and refresh after writes.
- Show order type, product/SKU, quantity, clinic, creator UUID, date, and inbound vendor or outbound consumption type in read-only history.
- Gate the page behind the existing auth flow; on 401, preserve its redirect behavior.
- Add tests for rendering, loading/error/retry, form submission and error responses, stock display, history, and auth-aware requests where practical.

## Acceptance criteria

1. Products are loaded from `GET /inventory/products`; no fabricated stock/order fixtures appear in the user-facing inventory route.
2. Inbound and outbound orders submit to their Phase 6 endpoints; successful actions refresh product stock and history.
3. Outbound submission is informed by currently displayed stock and handles the API's insufficient-stock rejection without losing the user's input.
4. Order history is read-only and clearly distinguishes delivery from consumption.
5. Loading, empty, actionable failure, and retry states are present; errors do not reveal tokens or internal exception details.
6. Unauthenticated users reach login via the existing auth gate and protected API calls use the same-origin proxy.
7. Backoffice tests cover rendering, loading/error/retry, form submission, server rejection and input retention, live stock/history, and auth-aware same-origin requests; tests, lint, and production build pass; unrelated files remain unstaged.

## Operational/data limitations

The Phase 6 contract exposes `user_uuid`, not a user display-name endpoint suitable for order attribution, so show the UUID unless an approved API contract provides a safe display name. No reorder-point/low-stock threshold exists in the current API or authoritative context; do not represent an arbitrary value as a company policy. API availability and credentials for live end-to-end testing must be supplied/configured by the user; never inspect `.env` values or write to shared/production data. This session verified an authenticated TestClient inventory create/list flow against the configured inventory DB in a controlled temporary test workflow and removed its temporary TinyDB user and SQL supply. This is API integration evidence, not an interactive browser session against the persistent shared API.

## Progress

Implemented the authenticated inventory page at `/inventory`, inventory contract/display helpers, sidebar navigation, scoped responsive styles, and explicit same-origin inventory rewrites. The UI shows API-derived stock, provides product/inbound/outbound forms and read-only order history, with server errors handled through the existing safe response helper. The low-stock cue is a relative UI advisory only; actor attribution is the API-provided UUID. Added page-level Vitest/jsdom interaction coverage and a bearer-token same-origin request helper test. Browser automation against a running Next/API pair has not been run.

Changed paths for this phase:

- `services/api/PHASE_7_INVENTORY_BACKOFFICE_PLAN.md`
- `uis/backoffice/app/inventory/page.tsx`
- `uis/backoffice/app/globals.css`
- `uis/backoffice/components/sidebar.tsx`
- `uis/backoffice/lib/inventory.ts`
- `uis/backoffice/lib/inventory.test.ts`
- `uis/backoffice/app/inventory/page.test.tsx`
- `uis/backoffice/vitest.config.ts`
- `uis/backoffice/vitest.setup.ts`
- `uis/backoffice/package.json`
- `uis/backoffice/package-lock.json`
- `uis/backoffice/lib/auth.test.ts` (Phase 7 auth-proxy assertion only; do not include unrelated auth implementation changes)
- `uis/backoffice/next.config.ts`

The shared `lib/auth.ts` implementation and pre-existing `lib/auth.test.ts` assertion for the safe duplicate-SKU API message were already dirty from other work. They are intentionally excluded from the Phase 7 snapshot; only the auth-request test hunk listed above belongs here, and it must be staged without the adjacent unrelated hunk.

Validation: final `npm test -- --reporter=dot` passed (3 files, 14 tests); `npm run lint` and `npm run build` passed. Targeted API inventory tests passed (11 passed, 2 skipped) in the service-local environment; the two opt-in PostgreSQL cases skipped because no test DB URL was supplied for this run. An authenticated API create/list smoke test and cleanup were reported earlier in this session. Do not mark Phase 7 complete until browser-level live API/auth redirect acceptance and confirmation that the Phase 6 release dependency is acceptable; tests/lint/build success alone does not pass that exit gate.

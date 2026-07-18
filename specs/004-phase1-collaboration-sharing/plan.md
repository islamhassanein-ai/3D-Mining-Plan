# Implementation Plan: Phase 1 — Collaboration & Multi-Tenancy

**Branch**: `004-phase1-collaboration-sharing` | **Date**: 2026-07-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-phase1-collaboration-sharing/spec.md`

## Summary

Add a multi-project workspace switcher, revocable/time-limited read-only share
links, and a visible audit-trail (import history + supersession chain) on top of
the Phase 0 backend and frontend from `specs/003-phase0-core-visualization/`. No new
technology is introduced — this extends the existing FastAPI/PostgreSQL backend and
vanilla-JS/Three.js frontend with one new entity (Share Link) and three new UI
surfaces (project switcher, share panel, history panel).

## Technical Context

**Language/Version**: Same as feature 003 — Python 3.11+ (backend), Vanilla
JavaScript (frontend). No change.

**Primary Dependencies**: Same as feature 003 (FastAPI, SQLAlchemy 2.0,
GeoAlchemy2, Alembic, Pydantic, Three.js). Share-link tokens use Python's built-in
`secrets` module (`secrets.token_urlsafe`) — no new dependency required.

**Storage**: Same PostgreSQL 16 + PostGIS database as feature 003; one new table
(`share_link`).

**Testing**: pytest is REQUIRED for share-link issuance, expiry, and revocation
logic — this is an access-control feature and carries the same correctness-risk
tier as feature 003's desurvey/import-validation logic (constitution Principle I's
spirit applied to data-exposure risk, per Tension 2 in `reviews/phase0_review.md`).
Workspace switching and history-panel UI are validated manually via `quickstart.md`,
consistent with feature 003's testing scope decision.

**Target Platform**: Same as feature 003 (desktop web browser; API server on any
Linux-compatible host). The share-link viewer route must also work for a recipient
with no account on the system at all.

**Project Type**: Web application — extends feature 003's existing backend/frontend,
not a new project.

**Performance Goals**: Project switch completes and re-scopes the scene within 5
seconds (SC-001). Share-link validity checks (expiry/revocation) must be fast enough
to not add perceptible latency to the read-only viewer's scene load.

**Constraints**: No new multi-tenancy model — reuses the single-shared-database,
`project_id`-scoped approach already fixed in `docs/architecture_baseline.md` § 3.
Share-link tokens MUST be cryptographically random and unguessable (research.md
Decision 1) and MUST carry a bounded expiry (spec FR-005) in addition to owner
revocation (FR-006). The share-link viewer route is a deliberate, narrow exception
to "every write/read needs a logged-in user" — see Constitution Check below for why
this doesn't violate the constitution's auth requirement.

**Scale/Scope**: Same 1-3 user assumption as `docs/architecture_baseline.md`; a
handful of projects per user, occasional share links per project.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. Geological Data Integrity | **PASS** — No data-mutation logic changes; this feature only adds read paths (workspace list, share-link viewer, history) and one new non-geological entity (Share Link). |
| II. CRS and Coordinate Rigor | **PASS** — Untouched; the share-link viewer reuses feature 003's existing scene/collar endpoints' data as-is. |
| III. Boring & Maintainable Architecture | **PASS** — One new table, one new service, a few new routes and frontend components, no new frameworks or dependencies. |
| IV. Visual Performance & CAD-Feel | **PASS** — Reuses feature 003's existing instanced-rendering scene loader; project switching re-invokes it with a different `project_id`, it doesn't reimplement rendering. |
| V. Soft Versioning & Audit Trail | **PASS, and this feature is largely *about* this principle** — US3 surfaces the existing `import_batch`/`superseded_by` audit trail. Share Link revocation is modeled as setting `revoked_at`, never deleting the row, for consistency with the no-hard-delete discipline even though a Share Link isn't drillhole data. |
| Technology Stack Constraints | **PASS** — No new dependency; token generation uses the Python standard library. |
| Development Workflow & Quality Gates | **PASS** — Continues the established `specs/` + `docs/` + `reviews/` structure; spec checklist is 16/16 passing after clarification. |

**Auth exception — considered explicitly, not a violation**: The constitution
(Authentication) and Tension 2 in `reviews/phase0_review.md` require "real auth"
because unauthenticated access to proprietary exploration data is a genuine business
risk. This feature's share-link viewer route *is* unauthenticated by design (per the
resolved clarification in spec.md). This is judged consistent with the
constitution's intent, not a violation, because: (a) it's a narrow, explicitly-scoped
exception the project owner opted into after seeing the tradeoff, not a general
weakening of the primary auth model; (b) the token is unguessable
(research.md Decision 1) and time-bounded (FR-005), unlike "no auth at all"; (c) the
share-link route is strictly read-only — no write capability is reachable through it
(FR-004). If this reasoning ever needs revisiting, it should happen via a
constitution amendment, not a silent reinterpretation in a future feature.

No other violations identified. Complexity Tracking table is not needed.

**Post-Phase 1 re-check**: `data-model.md`, `contracts/api.md`, and `quickstart.md`
add exactly one entity (Share Link) and reuse feature 003's existing scene/collar
endpoints for the token-authenticated viewer routes rather than reimplementing them.
No new technology, no new tenancy model, no change to existing entities. The auth
exception reasoning above still holds — nothing in Phase 1 design widened it beyond
strictly-read-only, token-scoped, time-bounded access. All gates above still
**PASS**.

## Project Structure

### Documentation (this feature)

```text
specs/004-phase1-collaboration-sharing/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── api.md
├── quickstart.md         # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

This feature extends the existing `backend/` and `frontend/` trees from feature
003 — no new top-level directories.

```text
backend/src/models/share_link.py        # new
backend/src/services/share_link.py      # new — token issuance, expiry check
backend/src/api/workspace.py            # new — GET /workspace/projects (switcher)
backend/src/api/share_links.py          # new — create/revoke/renew + public viewer routes
backend/src/api/history.py              # new — GET /projects/{id}/history
backend/tests/unit/test_share_link.py   # new — issuance/expiry/revocation tests

frontend/src/components/project_switcher.js   # new
frontend/src/components/share_panel.js        # new
frontend/src/components/history_panel.js      # new
frontend/src/views/shared_view.js             # new — read-only entry point reusing
                                               # feature 003's scene/inspector
                                               # components, omitting write-capable UI
```

**Structure Decision**: Additive to feature 003's existing web-application layout —
no new backend or frontend project, no new persistence technology.

## Complexity Tracking

*No violations — table not needed.*

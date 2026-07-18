---

description: "Task list for feature implementation"
---

# Tasks: Phase 1 — Collaboration & Multi-Tenancy

**Input**: Design documents from `specs/004-phase1-collaboration-sharing/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md,
quickstart.md (all present). This feature extends the existing `backend/` and
`frontend/` trees built in feature 003 — it does not create a new project.

**Tests**: Automated tests are REQUIRED for share-link issuance, expiry, revocation,
and renewal — this is an access-control feature (plan.md Technical Context →
Testing). Workspace switching and history-panel UI are validated manually via
`quickstart.md`, matching feature 003's testing scope decision.

**Note for the executor**: Every task names the exact file(s) to create or edit and
the exact source document/section it is built from (`data-model.md`,
`contracts/api.md`, or `research.md`). Reuse feature 003's existing code
(`scene_loader.js`, the scene/collar query logic, `api_client.js`) wherever a task
says "reuse" — do not duplicate that logic into new files. Where quickstart.md
requires a human-run end-to-end check (T024), do not mark it done without a genuine
run — fabricating a verification result is exactly the mistake called out in
feature 001's and feature 002's tasks.md and must not be repeated here.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US3)
- Setup, Foundational, and Polish tasks have no `[Story]` label.

## Path Conventions

Per `plan.md` Project Structure (additive to feature 003's existing tree):
- Backend: `backend/src/{models,services,api}/`, `backend/tests/{unit,integration}/`
- Frontend: `frontend/src/{components,services,views}/`

---

## Phase 1: Setup

**Purpose**: Confirm the feature 003 foundation this feature builds on is in place.
No new dependencies are needed (plan.md — token generation uses the Python standard
library only).

- [ ] T001 Confirm `backend/` and `frontend/` from
  `specs/003-phase0-core-visualization/` run successfully (backend serves, frontend
  loads a project's scene) before adding any code from this feature. Do not modify
  feature 003's files in this task — verification only.

**Checkpoint**: Feature 003 is a working base to extend.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The Share Link model, its issuance/validity service, and the read-only
viewer-context dependency every user-story task needs.

**⚠️ CRITICAL**: No user-story task may begin until this phase is complete.

- [ ] T002 Create the Share Link model in `backend/src/models/share_link.py` per
  `data-model.md` § Share Link (fields: id, project_id, token, created_by,
  created_at, expires_at, revoked_at).
- [ ] T003 Generate an Alembic migration in `backend/alembic/versions/` adding the
  `share_link` table from T002, on top of feature 003's existing schema. Depends on
  T002.
- [ ] T004 Implement the share-link service in `backend/src/services/share_link.py`:
  `issue(project_id, created_by) -> ShareLink` (token via
  `secrets.token_urlsafe(32)`, `expires_at = now() + 7 days`, per research.md
  Decisions 1-2), `is_valid(link) -> bool` (`revoked_at IS NULL AND expires_at >
  now()`, per `data-model.md` Validation Rules), `revoke(link)` (sets `revoked_at`,
  idempotent), and `renew(link)` (sets `expires_at = now() + 7 days`; raises if the
  link is already revoked or expired, per `contracts/api.md`). Depends on T002.
- [ ] T005 Write pytest unit tests for `share_link.py` in
  `backend/tests/unit/test_share_link.py`: issued token is unique and
  URL-safe-length; `expires_at` defaults to 7 days out; `is_valid` is true for a
  fresh link, false after revocation, false after expiry; `renew` extends
  `expires_at` on an active link and raises on a revoked/expired one. Depends on
  T004.
- [ ] T006 Implement a token-authenticated, read-only "viewer context" dependency in
  `backend/src/api/dependencies.py` (create this file if it doesn't exist), per
  research.md Decision 3: given a Share Link token, calls T004's `is_valid`; on
  success returns a context carrying only `project_id` and a read-only flag; on
  failure raises the 410 Gone response with a clear "access no longer available"
  body specified in `contracts/api.md`. This dependency must be structurally
  distinct from feature 003's JWT `get_current_user` dependency — no mutating route
  may accept it. Depends on T004.

**Checkpoint**: Share links can be issued, validated, revoked, and renewed at the
service layer; the viewer-context dependency is ready for routes to use.

---

## Phase 3: User Story 1 - Switch between multiple prospects in one workspace (Priority: P1) 🎯 MVP (part 1 of 2)

**Goal**: A user can see all their projects and switch the active one, with the
scene fully re-scoping each time.

**Independent Test**: `quickstart.md` Scenario 1 passes without any Share Link or
history code existing.

### Implementation for User Story 1

- [ ] T007 [US1] Implement `GET /workspace/projects` in
  `backend/src/api/workspace.py`, per `contracts/api.md` § Workspace: returns
  lightweight metadata (id, name, commodity) for every project the authenticated
  user owns or has been granted access to. Uses feature 003's JWT
  `get_current_user` dependency, not the viewer context from T006.
- [ ] T008 [US1] Add a `getWorkspaceProjects` function to
  `frontend/src/services/api_client.js`.
- [ ] T009 [US1] Build the project switcher component in
  `frontend/src/components/project_switcher.js` (+ CSS): lists the projects from
  T008 and emits a "project selected" event.
- [ ] T010 [US1] Wire the project switcher (T009) to feature 003's existing
  `frontend/src/scene/scene_loader.js`: selecting a project calls
  `GET /projects/{id}/scene` (feature 003's endpoint, unchanged) with the new id and
  fully replaces the current scene. Do not write a second scene-loading code path
  (research.md Decision 4). Depends on T009 and feature 003's `scene_loader.js`.

**Checkpoint**: `quickstart.md` Scenario 1 passes. FR-001, FR-002 satisfied.

---

## Phase 4: User Story 2 - Share a project as read-only with a colleague (Priority: P1) 🎯 MVP (part 2 of 2)

**Goal**: An owner can generate, list, revoke, and renew a Share Link; a recipient
can view (never modify) the project through it with no login.

**Independent Test**: `quickstart.md` Scenario 2 passes without US1 or US3 code
existing (a project can be created directly for this test if needed).

### Implementation for User Story 2

- [ ] T011 [US2] Implement `POST /projects/{project_id}/share-links` in
  `backend/src/api/share_links.py`, using T004's `issue`, per `contracts/api.md` §
  Share Links. JWT-authenticated; only the project owner may call it.
- [ ] T012 [US2] Implement
  `POST /projects/{project_id}/share-links/{link_id}/revoke` in
  `backend/src/api/share_links.py`, using T004's `revoke` (idempotent — revoking an
  already-inactive link is not an error). Depends on T011.
- [ ] T013 [US2] Implement `POST /projects/{project_id}/share-links/{link_id}/renew`
  in `backend/src/api/share_links.py`, using T004's `renew`; returns 409 if the
  link is already revoked or expired. Depends on T011.
- [ ] T014 [US2] Implement `GET /projects/{project_id}/share-links` in
  `backend/src/api/share_links.py`, listing all links (active and inactive) for
  the owner. Depends on T011.
- [ ] T015 [US2] Implement `GET /share/{token}/scene` and
  `GET /share/{token}/collars/{collar_id}` in `backend/src/api/share_links.py`,
  using T006's viewer-context dependency and reusing feature 003's existing
  scene/collar query logic (call the same underlying functions feature 003's
  `GET /projects/{id}/scene` and `GET /collars/{id}` use — do not duplicate the
  query logic into new functions). Returns 410 per T006 for an invalid token; 404
  for a `collar_id` outside the token's `project_id`. Depends on T006.
- [ ] T016 [US2] Write a pytest integration test in
  `backend/tests/integration/test_share_link_flow.py` covering the full sequence:
  create link → view via token succeeds → a write attempt via the token is
  rejected → revoke → view via token now returns 410 → renew an active link
  succeeds → renew a revoked link returns 409. Depends on T011-T015.
- [ ] T017 [US2] Build the share panel component in
  `frontend/src/components/share_panel.js` (+ CSS): generate-link button showing
  the resulting URL, a list of existing links with their status (active/expired/
  revoked), and revoke/renew controls per link.
- [ ] T018 [US2] Build the read-only viewer entry point in
  `frontend/src/views/shared_view.js`, reusing feature 003's scene, inspector,
  measurement, and slicing-plane components, but omitting the import panel and any
  owner-only controls (grade-cutoff is fine to keep — it's not a write action).
  Points at `GET /share/{token}/...` instead of the authenticated endpoints.
- [ ] T019 [US2] Add `createShareLink`, `revokeShareLink`, `renewShareLink`,
  `listShareLinks`, `getSharedScene`, and `getSharedCollar` functions to
  `frontend/src/services/api_client.js`, and wire them to T017 and T018. Depends on
  T011-T015, T017, T018.

**Checkpoint**: `quickstart.md` Scenario 2 passes. FR-003–FR-006 satisfied. This
completes the MVP (US1 + US2).

---

## Phase 5: User Story 3 - See who changed what and when (Priority: P2)

**Goal**: A user can view a project's import history and trace superseded records
forward.

**Independent Test**: `quickstart.md` Scenario 3 passes without US1 or US2 code
existing (a project with import history from feature 003 is sufficient).

### Implementation for User Story 3

- [ ] T020 [US3] Implement `GET /projects/{project_id}/history` in
  `backend/src/api/history.py`, returning import batches (source_file,
  import_date, importing user) and, given an entity id, its `superseded_by` chain
  forward to the current record, per `contracts/api.md` § History. JWT-authenticated
  only — do not accept the T006 viewer context on this route, per the contract's
  explicit note that history is not part of the read-only share scope.
- [ ] T021 [US3] Build the history panel component in
  `frontend/src/components/history_panel.js` (+ CSS): lists import batches and lets
  the user select a record to trace its supersession chain.
- [ ] T022 [US3] Add a `getProjectHistory` function to
  `frontend/src/services/api_client.js` and wire it to T021. Depends on T020, T021.

**Checkpoint**: `quickstart.md` Scenario 3 passes. FR-007, FR-008 satisfied.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Apply the project-scoping rule everywhere and prove the whole feature
works together.

- [ ] T023 Apply project-scoping (a request for data outside the authenticated
  user's accessible projects returns 404, never 403) to every route added in this
  feature: T007, T011-T015, T020, per `contracts/api.md` § Cross-cutting behavior
  (same rule as feature 003's contract). Depends on T007, T011-T015, T020.
- [ ] T024 Run `quickstart.md` Scenarios 1-3 and its Edge Cases end-to-end against a
  running instance (feature 003's backend/frontend plus this feature's additions).
  Fix any gap found in the relevant earlier task's output before re-running. Do not
  mark this complete without a genuine run — see the Note for the executor above.

**Checkpoint**: All of spec.md's Success Criteria (SC-001–SC-004) are checked
against real usage.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies (verification only).
- **Foundational (Phase 2)**: Depends on Phase 1.
- **User Stories (Phases 3-5)**: All depend on Phase 2. US1 (Phase 3) and US2 (Phase
  4) have no dependency on each other and can proceed in parallel if staffed. US3
  (Phase 5) depends only on Phase 2 and feature 003's existing import-batch data —
  independent of US1 and US2.
- **Polish (Phase 6)**: Depends on all routes added in Phases 3-5 (T023) and on
  those phases being functionally complete (T024).

### Within Each User Story

- US1: T007 independent; T008 depends on T007; T009 independent (frontend); T010
  depends on T008, T009, and feature 003's `scene_loader.js`.
- US2: T011 independent; T012, T013, T014 each depend on T011 (same router file,
  can be added in any order after it exists); T015 depends on T006; T016 depends on
  T011-T015; T017, T018 independent (frontend); T019 depends on T011-T015, T017,
  T018.
- US3: T020 independent; T021 independent (frontend); T022 depends on T020, T021.

---

## Parallel Execution Examples

```text
# Phase 3 (US1) and Phase 4 (US2) can proceed in parallel once Phase 2 is done —
# different files, no shared dependency beyond Foundational:
Phase 3 (T007-T010)  ||  Phase 4 (T011-T019)

# Within Phase 4, once T011 exists:
T012, T013, T014 (different endpoints in the same file — coordinate if same file,
                   otherwise treat as sequential edits to share_links.py)
T017, T018 (different frontend files, fully parallel)

# Phase 5 (US3) can run alongside Phase 3 and Phase 4 — no shared files:
Phase 5 (T020-T022)
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2, both P1)

1. Complete Phase 1: Setup (verify feature 003 works).
2. Complete Phase 2: Foundational (Share Link model, service, viewer-context
   dependency).
3. Complete Phase 3: User Story 1 (workspace switching).
4. Complete Phase 4: User Story 2 (read-only sharing).
5. **STOP and VALIDATE**: run `quickstart.md` Scenarios 1-2. This is the MVP — the
   owner can manage multiple projects and safely share one with a colleague.

### Incremental Delivery

1. Setup + Foundational → share-link machinery ready, nothing user-visible yet.
2. US1 → multi-project workspace usable.
3. US2 → safe, revocable sharing → MVP complete.
4. US3 → audit-trail visibility (valuable but not blocking).
5. Polish → project-scoping hardened everywhere, full end-to-end validation.

---

## Notes

- [Story] label maps task to specific user story for traceability.
- Reuse feature 003's scene/collar/auth code wherever a task says "reuse" — this
  feature should not end up with two implementations of scene loading or query
  logic.
- Commit after each phase (or task) so partial progress is recoverable.
- Do not mark T024 complete without a genuine end-to-end run — fabricating this
  result was exactly the problem caught during feature 001's implementation review
  and guarded against again in feature 002's and 003's tasks.md.

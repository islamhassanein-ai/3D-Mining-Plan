# Quickstart Validation: Phase 1 Collaboration & Multi-Tenancy

Prerequisites: feature 003's backend and frontend running, with at least 2-3
committed projects for the same authenticated user (per feature 003's quickstart).

## Scenario 1 — Workspace switching (US1, FR-001, FR-002, SC-001)

1. Sign in and open the workspace. Confirm `GET /workspace/projects` returns all of
   the user's projects.
2. Select a project; confirm the 3D scene loads scoped to it.
3. Switch to a different project; confirm the scene fully reloads with the new
   project's data and nothing from the previous project remains visible (inspect
   the network response and the rendered scene, not just the UI label).
4. Time the switch from selection to fully-loaded scene; confirm it's under 5
   seconds (SC-001).

## Scenario 2 — Read-only share link (US2, FR-003–FR-006, SC-002, SC-003)

1. As the owner, create a Share Link for a project via
   `POST /projects/{id}/share-links`. Confirm the response includes a token/URL and
   a 7-day `expires_at`.
2. Open the share URL in a separate, unauthenticated browser session (no login).
   Confirm the 3D scene, drillhole inspection, grade cutoff, slicing, and
   measurement all work.
3. Attempt a write action through the share session (e.g., call the import endpoint
   directly with the share token). Confirm it is rejected — never accepted (SC-002).
4. Revoke the link via `POST .../revoke`. Immediately retry the share URL from step
   2. Confirm it now returns the "access no longer available" state, not the scene
   (SC-003) — no delay window.
5. Create a second link, then manually set/observe its `expires_at` in the past (or
   wait past expiry in a test environment with a short window). Confirm an expired,
   never-revoked link behaves identically to a revoked one from the viewer's
   perspective.
6. Renew an active link via `POST .../renew`; confirm `expires_at` extends and the
   token/URL is unchanged. Attempt to renew a revoked link; confirm it returns 409,
   not a silently-revived link.

## Scenario 3 — Audit trail visibility (US3, FR-007, FR-008, SC-004)

1. As the owner, open a project's history via `GET /projects/{id}/history`. Confirm
   every import batch shows its source file, import date, and importing user.
2. Pick a record that has been superseded (re-import/correct one from feature 003's
   flow if needed). Confirm the history view lets you trace it forward to the
   record that replaced it.
3. Confirm the history endpoint is NOT reachable via a Share Link token (only via
   JWT session), per `contracts/api.md`.

## Edge Cases

1. Confirm a Share Link scoped to Project A returns 404 (not the data) when used
   against a Project B collar id.
2. Confirm the workspace list and project switch both show a sensible empty state
   for a brand-new user with zero projects, consistent with feature 003's
   empty-state discipline (FR-015 there).

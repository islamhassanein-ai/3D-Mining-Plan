# API Contract: Phase 1 Collaboration & Multi-Tenancy

Extends the API surface from `specs/003-phase0-core-visualization/contracts/api.md`.
All routes below require a valid JWT session (from feature 003's auth) unless
explicitly marked "token-authenticated."

## Workspace

- `GET /workspace/projects` — returns lightweight metadata (id, name, commodity) for
  every project the authenticated user owns or has been granted access to (FR-001,
  FR-009). Does not include scene data — the client re-uses feature 003's
  `GET /projects/{id}/scene` after the user selects a project (research.md Decision
  4).

## Share Links

- `POST /projects/{project_id}/share-links` — creates a Share Link scoped to
  `project_id` with a 7-day default expiry (research.md Decision 2). Returns the
  token and the full shareable URL. JWT-authenticated; only the project owner may
  call this.
- `POST /projects/{project_id}/share-links/{link_id}/revoke` — sets `revoked_at`
  on the link; idempotent (revoking an already-revoked or expired link is a no-op,
  not an error).
- `POST /projects/{project_id}/share-links/{link_id}/renew` — extends `expires_at`
  to `now() + 7 days` on an active (non-revoked, non-expired) link; returns 409 if
  the link is already revoked or expired (renewal doesn't resurrect a dead link —
  the owner must create a new one).
- `GET /projects/{project_id}/share-links` — lists all Share Links for the project
  (active and inactive), for the owner to manage/audit them.

## Token-Authenticated Viewer Routes

These routes accept a Share Link token in place of a JWT session (research.md
Decision 3) and are strictly read-only — no mutating route ever accepts a token.

- `GET /share/{token}/scene` — mirrors `GET /projects/{id}/scene` from feature 003,
  scoped to the token's `project_id`. Returns 410 Gone with a clear
  "access no longer available" body if the token is revoked or expired (FR-006,
  spec Edge Cases) — never a raw 401/403/500.
- `GET /share/{token}/collars/{collar_id}` — mirrors
  `GET /collars/{collar_id}` from feature 003, scoped to the token's `project_id`
  (rejecting a `collar_id` from a different project with 404, same as the
  cross-project rule in feature 003's contract). Read-only: no true-thickness write
  or measurement-save capability exists to accidentally expose.

## History

- `GET /projects/{project_id}/history` — returns the project's Import Batches
  (source file, import date, importing user) and, for a given entity id, its
  `superseded_by` chain forward to the current record (FR-007, FR-008).
  JWT-authenticated only — not exposed via a Share Link token, since it reveals
  user identities and isn't part of the read-only viewing scope in FR-004.

## Cross-cutting behavior

- Every token-authenticated route validates the Share Link per
  `data-model.md`'s Validation Rules on every request — no caching of a "was valid"
  result across requests, so revocation/expiry take effect immediately (SC-003).
- Project-scoping (404-not-403 on cross-project access) from feature 003's contract
  applies identically to every new route here.

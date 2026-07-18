# Phase 1 Data Model: Phase 1 Collaboration & Multi-Tenancy

Reuses Project, User, and Import Batch from
`specs/003-phase0-core-visualization/data-model.md` unchanged — this feature adds
exactly one new entity.

## New Entity: Share Link

| Field | Type | Constraints |
|---|---|---|
| id | UUID (PK) | |
| project_id | UUID (FK → project.id) | not null, indexed; immutable once created |
| token | String | not null, unique, indexed — generated via
`secrets.token_urlsafe(32)` (research.md Decision 1) |
| created_by | UUID (FK → user.id) | not null |
| created_at | Timestamptz | not null, default now() |
| expires_at | Timestamptz | not null, default `created_at + 7 days`
(research.md Decision 2) |
| revoked_at | Timestamptz | nullable — set, never deleted, when the owner revokes
the link ahead of expiry (constitution Principle V discipline applied by analogy) |

## Validation Rules

- A Share Link grants access if and only if `revoked_at IS NULL AND expires_at >
  now()` — evaluated on every request through the viewer routes (FR-005, FR-006,
  SC-003).
- Renewing a Share Link (research.md Decision 2) sets `expires_at = now() + 7 days`
  on the existing row; it never creates a new token or a new row.
- `project_id` on a Share Link is set once at creation and never changed — a link
  cannot be repointed to a different project.
- No Share Link row is ever hard-deleted; revocation and expiry are both
  state, not removal, so the audit trail (who created which link, when, and whether
  it was later revoked) remains queryable — consistent with Principle V.

## No changes to existing entities

Project, User, and Import Batch keep exactly the fields defined in
`specs/003-phase0-core-visualization/data-model.md`. This feature's audit-trail
story (US3) is implemented entirely by *reading* the existing `import_batch` and
`superseded_by` data — no new columns are added to expose it.

## Entity → User Story Mapping

| Entity | Primary User Stories |
|---|---|
| Project (read-only list) | US1 |
| Share Link | US2 |
| Import Batch, `superseded_by` chain (read-only) | US3 |

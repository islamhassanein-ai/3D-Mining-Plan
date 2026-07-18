# API Contract: Phase 0 Core Visualization & Modeling

Summary-level contract for the FastAPI backend this feature introduces. Full request/
response schemas belong in the implementation (Pydantic models), not duplicated here
— this documents the surface area and behavior each endpoint must guarantee, so
`tasks.md` and the implementation stay aligned with the functional requirements.

## Auth

- `POST /auth/magic-link` — body: `{ email }`. Sends a one-time login link. Always
  returns 202 regardless of whether the email is registered (no user enumeration).
- `GET /auth/verify?token=...` — exchanges a magic-link token for a short-lived JWT
  session token. Invalid/expired tokens return 401.

## Projects

- `POST /projects` — creates a Project. `utm_zone` is not required at creation; it is
  set by the first committed import (data-model.md Validation Rules).
- `GET /projects/{project_id}` — returns Project metadata.
- `GET /projects/{project_id}/scene` — returns everything the 3D scene needs to
  render in one call: collars + surveys + assay intervals + lithology intervals +
  trenches + wireframes + topography reference, all already resolved (desurveyed
  positions, not raw survey rows) — serves US2, US3, US7. Supports the empty-state
  case (FR-015) by returning an explicit empty-but-valid payload for a project with
  no committed imports yet, not an error.

## Imports

- `POST /projects/{project_id}/imports` — multipart upload of Collar/Survey/Assay/
  Lithology CSV files. Runs parsing, minimum-curvature desurveying, CRS zone
  detection, and all validation rules from `data-model.md`, but does **not** write
  to the committed tables. Returns an `import_batch_id` with `status:
  pending_review` and the full raw-vs-interpreted diff (FR-003), including any
  flagged rows (FR-004, FR-006, FR-007, FR-008, FR-009).
- `GET /projects/{project_id}/imports/{import_batch_id}` — re-fetches the diff/
  validation result for a pending import (for a page reload during review).
- `POST /projects/{project_id}/imports/{import_batch_id}/commit` — commits a
  `pending_review` batch: writes Collar/Survey/Assay/Lithology rows (creating new
  rows and setting `superseded_by` on any prior rows they replace), sets
  `import_batch.status = committed`. Requires the client to have already resolved or
  acknowledged every flagged row from the diff step — commit is rejected (422) if
  unacknowledged blocking flags remain.
- `POST /projects/{project_id}/imports/{import_batch_id}/reject` — discards a
  `pending_review` batch without writing anything; sets `status = rejected`.

## Collars

- `GET /collars/{collar_id}` — the drillhole-card payload for US3: collar
  coordinates, full survey list, full assay and lithology interval tables. Must
  include every field listed for these entities in `data-model.md` (SC-004 — zero
  missing fields).
- `GET /collars/{collar_id}/true-thickness?interval_id=...` — computed true
  thickness for a given assay interval, using the collar's survey dip at that depth
  (FR-018). Returns an explicit "unavailable" result (not a fabricated number) when
  dip data is missing (per spec Edge Cases).

## Supplementary Data

- `POST /projects/{project_id}/topography` — upload/register a topography surface
  reference for the scene endpoint to include (FR-021).
- `POST /projects/{project_id}/trenches` — bulk-create Trench rows (FR-022).
- `POST /projects/{project_id}/wireframes` — upload a wireframe/vein solid file via
  the storage abstraction and register it for the scene endpoint (FR-023). A parse
  failure on this endpoint returns a per-file error and never blocks the rest of the
  project's scene from loading (spec Edge Cases).

## Cross-cutting behavior

- Every endpoint that returns geological data enforces project-scoping: a request for
  data outside the authenticated user's accessible projects returns 404, not 403 (no
  existence leakage).
- Every write endpoint requires a valid session (from `/auth/verify`); no endpoint
  accepts anonymous writes.

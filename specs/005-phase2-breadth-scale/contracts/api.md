# API Contract: Phase 2 Breadth & Scale

Extends the API surface from `specs/003-phase0-core-visualization/contracts/api.md`
and `specs/004-phase1-collaboration-sharing/contracts/api.md`. All routes below
require a valid JWT session unless noted otherwise, and follow the same
project-scoping (404-not-403) rule already established.

## Import — DXF & Shapefile

- `POST /projects/{project_id}/wireframes` *(extended from feature 003)* — now
  accepts a DXF file in addition to an opaque reference; when the extension is
  `.dxf`, the file is parsed via `ezdxf` (research.md Decision 1) and its geometry
  is stored alongside the existing `file_ref`, so the scene endpoint can return real
  vertex/face data instead of a reference-only placeholder. A parse failure returns
  a per-file error without affecting other project data (FR-002), unchanged from
  feature 003's error-handling contract.
- `POST /projects/{project_id}/trenches/shapefile` — accepts a Shapefile (`.shp` +
  companion `.dbf`/`.shx`), parsed via `pyshp` (research.md Decision 2), producing
  the same Trench rows `POST /projects/{project_id}/trenches` (feature 003) would
  from CSV. Runs the same CRS auto-detect-then-confirm flow as any other import
  (FR-004).
- `POST /projects/{project_id}/topography/shapefile` — same pattern as above, for
  the topography surface.

## Export

- `GET /projects/{project_id}/export/wireframes.dxf` — exports all of a project's
  wireframes as a single DXF file via `ezdxf` (FR-005).
- `GET /projects/{project_id}/export/section.pdf?plane=...` — exports the current
  section-view slice (same plane parameters the frontend's 2D section view uses) as
  a PDF via `reportlab` (FR-006).
- `GET /projects/{project_id}/export/data.csv?entity=collars|surveys|assays|lithologies`
  — exports the requested entity type as CSV, schema-compatible with the Phase 0
  import path (FR-007).

## Structural Data

- `POST /projects/{project_id}/structural-readings` — creates one or more
  Structural Reading rows (fault trace or dip/strike), per `data-model.md`.
- `GET /projects/{project_id}/structural-readings` — lists a project's structural
  readings; included in `GET /projects/{project_id}/scene`'s response so they
  render alongside drillholes without a second round-trip (FR-009).

## RQD / Core Recovery

No new endpoints — `rqd_percent` and `core_recovery_percent` are accepted on the
existing Lithology CSV import path (feature 003's `POST
/projects/{project_id}/imports`) and validated per `data-model.md`; they already
appear in `GET /collars/{collar_id}`'s response since that endpoint returns every
field on Lithology Interval (FR-011).

## QA/QC

- `POST /projects/{project_id}/qaqc-standards` — creates a QA/QC Standard
  Reference (`standard_name`, expected range, `grade_unit`).
- `GET /projects/{project_id}/qaqc-standards` — lists configured standards, for the
  owner to manage.
- `qaqc_flag` and any out-of-range warning are accepted/produced on the existing
  assay import path (`POST /projects/{project_id}/imports`), extending its
  validation response per `data-model.md`'s Validation Rules — no separate endpoint.

## Scale (LOD)

No new endpoints. `GET /projects/{project_id}/scene` (feature 003) is unchanged —
LOD is a purely client-side rendering behavior (research.md Decision 4); the backend
always returns complete data regardless of project size.

## Cross-cutting behavior

- Every new endpoint follows the same project-scoping (404-not-403) and
  `import_batch_id` provenance rules established in features 003/004's contracts.
- DXF and Shapefile uploads go through the same storage abstraction
  (`backend/src/storage/`) as CSV uploads — no direct filesystem access introduced.

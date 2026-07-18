# Phase 1 Data Model: Phase 2 Breadth & Scale

Reuses Project, Collar, Survey, Assay Interval, Lithology Interval, Trench,
Wireframe, Import Batch, and User from
`specs/003-phase0-core-visualization/data-model.md` unchanged. This feature
activates two already-reserved fields and adds two new entities.

## Activated Fields (no schema change — already present per feature 003)

- `LithologyInterval.rqd_percent`, `LithologyInterval.core_recovery_percent` — now
  validated (0-100%) and shown in the UI (FR-010, FR-011).
- `AssayInterval.qaqc_flag` — now populated with one of `duplicate` / `standard` /
  `blank` / `null` (regular sample) during import (FR-012).

## New Entity: Structural Reading

| Field | Type | Constraints |
|---|---|---|
| id | UUID (PK) | |
| project_id | UUID (FK → project.id) | not null, indexed |
| reading_type | String | not null — e.g. `fault_trace`, `dip_strike` |
| easting, northing, elevation | Float | UTM meters, same rigor as Collar/Trench |
| dip, strike | Float, nullable | degrees; required when `reading_type = dip_strike` |
| import_batch_id | UUID (FK → import_batch.id) | not null |
| superseded_by | UUID (FK → structural_reading.id), nullable | no hard deletes, consistent with every other importable entity |

## New Entity: QA/QC Standard Reference

| Field | Type | Constraints |
|---|---|---|
| id | UUID (PK) | |
| project_id | UUID (FK → project.id) | not null, indexed |
| standard_name | String | not null — must match the value used in an assay
row's QA/QC identification during import |
| expected_grade_min, expected_grade_max | Numeric | not null |
| grade_unit | String | not null — must match `AssayInterval.grade_unit` for the
comparison to be meaningful |

## Validation Rules

- `LithologyInterval.rqd_percent` and `core_recovery_percent`, when present, MUST be
  within `[0, 100]`; an import row with a value outside this range is a blocking
  error (unlike overlap/gap warnings — an impossible percentage is not a judgment
  call, it's invalid data).
- `AssayInterval.qaqc_flag` is set from an explicit column in the assay import file;
  rows without a QA/QC indicator get `qaqc_flag = null` (regular sample).
- A `standard`-flagged assay row is compared against the `QA/QC Standard Reference`
  matching its `standard_name` (from the row) and `grade_unit`. If no matching
  reference is configured, the row is flagged `unconfigured` (per spec Edge Cases) —
  never silently skipped or treated as passing.
- An assay row flagged `standard` whose value falls outside
  `[expected_grade_min, expected_grade_max]` is flagged as a warning (not a blocking
  error) — consistent with this project's flag-don't-auto-correct discipline; the
  geologist reviews and acknowledges it the same way overlap/gap warnings are
  acknowledged (feature 003's `acknowledge_warnings` commit gate).
- Structural Readings follow the same no-hard-delete, `import_batch_id`-traced
  discipline as every other importable entity (constitution Principle V).
- DXF and Shapefile imports run through the same CRS auto-detect-then-confirm flow
  as CSV imports (feature 003's `crs.py`) before any row is committed.

## Entity → User Story Mapping

| Entity / Field | Primary User Stories |
|---|---|
| Wireframe (DXF-parsed geometry) | US1 |
| Trench, Wireframe (topography) via Shapefile | US2 |
| (export uses existing entities, no new ones) | US3 |
| Structural Reading | US4 |
| `rqd_percent`, `core_recovery_percent` | US5 |
| `qaqc_flag`, QA/QC Standard Reference | US6 |
| (LOD is rendering-only, no entity) | US7 |

# Phase 1 Data Model: Phase 0 Core Visualization & Modeling

Base entities are already fixed in `docs/architecture_baseline.md` § 2 and
`specs/002-architecture-baseline/data-model.md` (including the `superseded_by`
reconciliation for constitution Principle V). This document does not redefine those
entities — it adds the implementation-level detail (concrete types, indexes,
constraints) needed to build the SQLAlchemy models and API for this feature.

## Entities (implementation detail over the fixed baseline)

### Project
| Field | Type | Constraints |
|---|---|---|
| id | UUID (PK) | default gen_random_uuid() |
| name | String | not null |
| utm_zone | String | not null (set via import auto-detect-then-confirm) |
| commodity | String | nullable |
| created_at | Timestamptz | not null, default now() |
| superseded_by | UUID (FK → project.id) | nullable |

### Collar
| Field | Type | Constraints |
|---|---|---|
| id | UUID (PK) | |
| project_id | UUID (FK → project.id) | not null, indexed |
| hole_id | String | not null, unique per project |
| easting, northing, elevation | Double precision | UTM meters |
| utm_zone | String | not null |
| import_batch_id | UUID (FK → import_batch.id) | not null |
| created_at | Timestamptz | not null, default now() |
| superseded_by | UUID (FK → collar.id) | nullable |

Index: `(project_id, hole_id)` for lookup during import validation (FR-009 orphan
reference check).

### Survey
| Field | Type | Constraints |
|---|---|---|
| id | UUID (PK) | |
| collar_id | UUID (FK → collar.id) | not null, indexed |
| depth | Double precision | not null, >= 0 |
| dip | Double precision | not null, -90 to 90 |
| azimuth | Double precision | not null, 0 to 360 |
| desurvey_method | String | not null, must equal `"minimum_curvature"` (enforced at the service layer, not just a free-text column — see Validation Rules) |

### Assay Interval
| Field | Type | Constraints |
|---|---|---|
| id | UUID (PK) | |
| collar_id | UUID (FK → collar.id) | not null, indexed |
| from_depth, to_depth | Double precision | not null, `to_depth > from_depth` |
| grade_value | Numeric | not null (preserved even when below detection limit) |
| grade_unit | String | not null, one of `ppm`/`g/t`/`%` |
| below_detection_limit | Boolean | not null, default false |
| qaqc_flag | String | nullable, reserved (no validation logic this phase) |
| import_batch_id | UUID (FK → import_batch.id) | not null |
| superseded_by | UUID (FK → assay_interval.id) | nullable |

Index: `(collar_id, from_depth, to_depth)` to support overlap/gap detection.

### Lithology Interval
| Field | Type | Constraints |
|---|---|---|
| id | UUID (PK) | |
| collar_id | UUID (FK → collar.id) | not null, indexed |
| from_depth, to_depth | Double precision | not null, `to_depth > from_depth` |
| lith_code | String | not null |
| rqd_percent, core_recovery_percent | Integer | nullable, reserved (no validation logic this phase) |
| superseded_by | UUID (FK → lithology_interval.id) | nullable |

### Trench
| Field | Type | Constraints |
|---|---|---|
| id | UUID (PK) | |
| project_id | UUID (FK → project.id) | not null, indexed |
| trench_id | String | not null |
| easting, northing | Double precision | UTM meters |
| grade_value | Numeric | nullable |

### Wireframe
| Field | Type | Constraints |
|---|---|---|
| id | UUID (PK) | |
| project_id | UUID (FK → project.id) | not null, indexed |
| name | String | not null |
| solid_type | String | not null |
| file_ref | String | not null — points to the storage abstraction (research.md Decision 7), never a raw filesystem path |

### Import Batch
| Field | Type | Constraints |
|---|---|---|
| id | UUID (PK) | |
| source_file | String | not null |
| import_date | Timestamptz | not null, default now() |
| status | String | not null, one of `pending_review` / `committed` / `rejected` |

### User
| Field | Type | Constraints |
|---|---|---|
| id | UUID (PK) | |
| email | String | not null, unique |
| role | String | not null |

## Validation Rules (service-layer, not just DB constraints)

- `desurvey_method` MUST be computed as `"minimum_curvature"` by
  `backend/src/services/desurvey.py` — the API never accepts a client-supplied
  desurvey method (FR-002, constitution Principle I).
- Import commit MUST be blocked until every row has passed the diff-view review step
  (`import_batch.status` transitions `pending_review` → `committed` only via an
  explicit commit action) — FR-003.
- `utm_zone` on a new Collar MUST match the confirmed zone from the import session;
  a project's `utm_zone` is set on first import and subsequent imports must be
  reconciled (flagged, not silently overwritten) if they suggest a different zone —
  FR-004.
- `grade_unit` MUST be declared once per import file, applied to every Assay Interval
  row in that file; mixed units within one file are rejected at validation time, not
  converted — FR-008.
- `below_detection_limit = true` rows MUST retain their original detection-limit
  value in `grade_value` — enforced by the import validator rejecting any row that
  would zero/null this field when the flag is true — FR-005.
- Overlap/gap detection runs per `collar_id` across `from_depth`/`to_depth` on both
  Assay Interval and Lithology Interval before commit; flagged rows block commit
  until the geologist acknowledges them in the diff view — FR-006.
- A Survey/Assay/Lithology row referencing a `hole_id` absent from the Collar rows in
  the same import batch MUST be flagged as an orphan reference — FR-009.
- No entity listed above is ever hard-deleted; corrections create a new row and set
  `superseded_by` on the prior row (constitution Principle V, unchanged from feature
  002's reconciliation).

## Entity → User Story Mapping

| Entity | Primary User Stories |
|---|---|
| Project, Import Batch | US1 |
| Collar, Survey | US1, US2, US3 |
| Assay Interval | US1, US2, US3, US4 |
| Lithology Interval | US1, US2, US3 |
| Trench, Wireframe | US7 |
| User | Authentication (cross-cutting, all stories) |

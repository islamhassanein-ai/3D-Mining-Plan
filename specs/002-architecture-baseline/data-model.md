# Phase 1 Data Model: Core Platform Architecture Baseline

Source: `mining_tool_planning_Final_claude4-7-2026.md` § 6 (Data Model), reconciled
against `.specify/memory/constitution.md` v1.0.0 where the two diverge (constitution
governs, per spec.md's Assumptions).

## Entities

### Project
Top-level container for a single gold prospect.
| Field | Type | Notes |
|---|---|---|
| id | uuid (PK) | |
| name | string | |
| utm_zone | string | Required. Set at project creation via the CSV-import auto-detect-then-confirm flow (FR-005). |
| commodity | string | |
| created_at | timestamp | |
| superseded_by | uuid (FK → Project.id), nullable | **Addition over the source ERD** — required by constitution Principle V (No Hard Deletes). See Reconciliation Note below. |

Relationships: has many Collar, Trench, Wireframe.

### Collar
A drillhole's surface location.
| Field | Type | Notes |
|---|---|---|
| id | uuid (PK) | |
| project_id | uuid (FK → Project.id) | |
| hole_id | string | |
| easting, northing, elevation | float | UTM meters only (FR-005). |
| utm_zone | string | Must match or be reconcilable with the parent Project's zone. |
| import_batch_id | uuid (FK → ImportBatch.id) | Required — every row traces to its import (FR-012 audit/provenance baseline). |
| created_at | timestamp | |
| superseded_by | uuid (FK → Collar.id), nullable | **Addition over the source ERD** — see Reconciliation Note. |

Relationships: belongs to Project; has many Survey, Assay Interval, Lithology Interval.

### Survey
A downhole deviation reading.
| Field | Type | Notes |
|---|---|---|
| id | uuid (PK) | |
| collar_id | uuid (FK → Collar.id) | |
| depth | float | |
| dip, azimuth | float | |
| desurvey_method | string | Must be the minimum-curvature method per constitution Principle I; no other value is valid. |

Relationships: belongs to Collar.

### Assay Interval
A sampled interval on a Collar.
| Field | Type | Notes |
|---|---|---|
| id | uuid (PK) | |
| collar_id | uuid (FK → Collar.id) | |
| from_depth, to_depth | float | Overlaps/gaps across a Collar's intervals must be flagged, never auto-corrected (FR-007). |
| grade_value | float | Preserved as-is even when below detection limit (never zeroed). |
| grade_unit | string | Required per row; never assumed or silently mixed across a single import (FR-006). |
| below_detection_limit | bool | When true, `grade_value` holds the detection limit, per constitution Principle I. |
| qaqc_flag | string, nullable | Schema reserved; no UI/validation logic in Phase 0 (Phase 2 scope). |
| import_batch_id | uuid (FK → ImportBatch.id) | Required. |
| superseded_by | uuid (FK → AssayInterval.id), nullable | **Addition over the source ERD** — see Reconciliation Note. |

Relationships: belongs to Collar.

### Lithology Interval
A geological interval on a Collar.
| Field | Type | Notes |
|---|---|---|
| id | uuid (PK) | |
| collar_id | uuid (FK → Collar.id) | |
| from_depth, to_depth | float | Same overlap/gap flagging rule as Assay Interval. |
| lith_code | string | |
| rqd_percent, core_recovery_percent | int, nullable | Schema reserved for Phase 2; no UI/validation logic in Phase 0. |
| superseded_by | uuid (FK → LithologyInterval.id), nullable | **Addition over the source ERD** — see Reconciliation Note. |

Relationships: belongs to Collar.

### Trench
A surface sample location.
| Field | Type | Notes |
|---|---|---|
| id | uuid (PK) | |
| project_id | uuid (FK → Project.id) | |
| trench_id | string | |
| easting, northing | float | UTM meters only. |
| grade_value | float | |

Relationships: belongs to Project.

### Wireframe
An imported solid/vein model reference.
| Field | Type | Notes |
|---|---|---|
| id | uuid (PK) | |
| project_id | uuid (FK → Project.id) | |
| name | string | |
| solid_type | string | |
| file_ref | string | Points to object storage, not stored inline (FR-009). |

Relationships: belongs to Project.

### Import Batch
Provenance record for any imported data.
| Field | Type | Notes |
|---|---|---|
| id | uuid (PK) | |
| source_file | string | |
| import_date | timestamp | |
| status | string | |

Relationships: referenced by Collar and Assay Interval (and, by the same
provenance rule, should be referenced by any other importable entity added later).

### User
An account with access to the system.
| Field | Type | Notes |
|---|---|---|
| id | uuid (PK) | |
| email | string | |
| role | string | |

## Validation Rules

- Every entity that can be corrected after initial import (Project, Collar, Assay
  Interval, Lithology Interval) carries a nullable `superseded_by` self-reference;
  rows are never hard-deleted, only superseded (constitution Principle V).
- `utm_zone` is required wherever coordinates are stored and must be presented to the
  user for explicit confirmation at import time — never silently assumed (FR-005).
- `grade_unit` is required per Assay Interval row; mixed units within a single import
  must be rejected, not silently converted without a per-file unit declaration
  (FR-006).
- `below_detection_limit = true` rows must retain the original detection-limit value
  in `grade_value`; this value must never be zeroed, nulled, or dropped (FR-006).
- Overlapping or gapped `from_depth`/`to_depth` ranges within a Collar's Assay
  Interval or Lithology Interval sets must be flagged for geologist review, never
  auto-corrected or silently merged (FR-007).
- Coordinate values that fall outside plausible UTM Easting/Northing ranges for the
  project's region must be flagged as a possible lat/long swap (FR-007).
- `rqd_percent`, `core_recovery_percent`, and `qaqc_flag` are reserved fields: present
  in the schema now, but Phase 0 builds no UI or validation logic against them
  (deferred to Phase 2, per the source document's "schema-complete,
  feature-deferred" resolution).
- Every row that originates from a file import carries a non-null `import_batch_id`
  tracing to a Import Batch record with `source_file`, `import_date`, and the
  importing user (FR-012 audit/provenance baseline).

## Reconciliation Note: `superseded_by`

The source planning document's Section 6 ERD does not include a `superseded_by`
column on any entity — only a narrative mention in Section 1 ("soft versioning —
never overwrite an import; append/supersede with audit trail"). The ratified
constitution (Principle V: Soft Versioning & Audit Trail) makes this a hard
requirement: *"The database must never hard delete drillhole data... link older rows
using the superseded_by foreign key."* Per this baseline's own governance rule
(constitution governs where it and the source document diverge), this data model
adds `superseded_by` to every entity that represents importable/correctable drillhole
data. This is a **reconciliation**, not a new architectural decision — it makes the
already-ratified constitution requirement concrete in the entity list, which the
source document's ERD had not yet caught up to.

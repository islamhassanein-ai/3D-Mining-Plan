# Data Model Specification

## Source
Master Plan §6 (Data Model) + §1 (Panel Non-Negotiables)

---

## Overview

PostgreSQL 16 + PostGIS database storing exploration drilling data with full provenance tracking. The schema must:
- Support all JORC-aware fields (even if UI is deferred to Phase 2)
- Track import provenance (source_file, import_date, batch_id)
- Never overwrite — append/supersede with audit trail
- Store coordinates in UTM with explicit zone per project
- Handle below-detection-limit (BDL) assay values explicitly

---

## Entity Relationship Diagram

```mermaid
erDiagram
    PROJECT ||--o{ COLLAR : contains
    PROJECT ||--o{ TRENCH : contains
    PROJECT ||--o{ WIREFRAME : contains
    PROJECT ||--o{ TOPO_SURFACE : contains
    COLLAR ||--o{ SURVEY : has
    COLLAR ||--o{ ASSAY_INTERVAL : has
    COLLAR ||--o{ LITHOLOGY_INTERVAL : has
    IMPORT_BATCH ||--o{ COLLAR : imported_in
    IMPORT_BATCH ||--o{ ASSAY_INTERVAL : imported_in
    IMPORT_BATCH ||--o{ TRENCH : imported_in

    PROJECT {
        uuid id PK
        varchar_255 name "NOT NULL"
        varchar_10 utm_zone "e.g. 36N"
        varchar_50 commodity "e.g. Gold"
        varchar_20 crs_epsg "e.g. EPSG:32636"
        text description
        timestamp created_at "DEFAULT NOW()"
        timestamp updated_at
    }

    COLLAR {
        uuid id PK
        uuid project_id FK "NOT NULL"
        varchar_50 hole_id "NOT NULL, UNIQUE per project"
        float8 easting "NOT NULL, UTM meters"
        float8 northing "NOT NULL, UTM meters"
        float8 elevation "NOT NULL, meters ASL"
        float8 total_depth "meters"
        varchar_10 utm_zone
        varchar_50 status "e.g. completed, abandoned"
        uuid import_batch_id FK
        timestamp created_at "DEFAULT NOW()"
    }

    SURVEY {
        uuid id PK
        uuid collar_id FK "NOT NULL"
        float8 depth "NOT NULL, meters downhole"
        float8 dip "NOT NULL, degrees -90 to 0"
        float8 azimuth "NOT NULL, degrees 0 to 360"
        varchar_30 desurvey_method "minimum_curvature"
        float8 computed_x "desurveyed XYZ"
        float8 computed_y
        float8 computed_z
        uuid import_batch_id FK
    }

    ASSAY_INTERVAL {
        uuid id PK
        uuid collar_id FK "NOT NULL"
        float8 from_depth "NOT NULL, meters"
        float8 to_depth "NOT NULL, meters"
        float8 grade_value "nullable if BDL"
        varchar_10 grade_unit "NOT NULL: ppm, g_per_t, percent"
        float8 detection_limit "detection limit value if BDL"
        boolean below_detection_limit "DEFAULT false"
        varchar_20 qaqc_type "NULL, duplicate, standard, blank"
        varchar_50 qaqc_flag "pass, fail, suspect"
        uuid import_batch_id FK
        timestamp created_at "DEFAULT NOW()"
        uuid superseded_by "NULL = current"
    }

    LITHOLOGY_INTERVAL {
        uuid id PK
        uuid collar_id FK "NOT NULL"
        float8 from_depth "NOT NULL, meters"
        float8 to_depth "NOT NULL, meters"
        varchar_20 lith_code "NOT NULL"
        varchar_255 lith_description
        varchar_50 color_code "for rendering"
        int4 rqd_percent "0-100, nullable Phase 2"
        int4 core_recovery_percent "0-100, nullable Phase 2"
        varchar_100 structure_type "fault, fold etc, nullable Phase 2"
        float8 structure_dip "nullable Phase 2"
        float8 structure_azimuth "nullable Phase 2"
        uuid import_batch_id FK
    }

    TRENCH {
        uuid id PK
        uuid project_id FK "NOT NULL"
        varchar_50 trench_id "NOT NULL"
        float8 easting "UTM meters"
        float8 northing "UTM meters"
        float8 elevation
        float8 grade_value
        varchar_10 grade_unit "ppm, g_per_t, percent"
        varchar_255 description
        uuid import_batch_id FK
        timestamp created_at "DEFAULT NOW()"
    }

    WIREFRAME {
        uuid id PK
        uuid project_id FK "NOT NULL"
        varchar_100 name "NOT NULL"
        varchar_50 solid_type "vein, ore_body, fault, lithology_contact"
        varchar_500 file_ref "path in object storage"
        jsonb vertices_json "vertex/face data or reference"
        varchar_20 format "obj, dxf, custom_json"
        timestamp created_at "DEFAULT NOW()"
    }

    TOPO_SURFACE {
        uuid id PK
        uuid project_id FK "NOT NULL"
        varchar_100 name "DEFAULT topography"
        varchar_500 file_ref "path in object storage"
        jsonb grid_metadata "resolution, bounds"
        varchar_20 format "dem, xyz_grid, tin"
        timestamp created_at "DEFAULT NOW()"
    }

    IMPORT_BATCH {
        uuid id PK
        uuid project_id FK "NOT NULL"
        varchar_500 source_file "original filename"
        varchar_500 stored_path "path in object storage"
        varchar_50 data_type "collar, survey, assay, lithology, trench"
        int4 row_count "rows in source file"
        int4 imported_count "successfully imported"
        int4 error_count "rows with errors"
        jsonb error_log "array of row-level errors"
        varchar_20 status "pending, validated, committed, superseded"
        timestamp import_date "DEFAULT NOW()"
        uuid imported_by "user reference"
    }

    USER_ACCOUNT {
        uuid id PK
        varchar_255 email "UNIQUE NOT NULL"
        varchar_100 display_name
        varchar_20 role "owner, editor, viewer"
        timestamp created_at "DEFAULT NOW()"
        timestamp last_login
    }
```

---

## Coordinate Reference System Handling

| Scenario | Behavior |
|---|---|
| **Import with known UTM zone** | Store zone in project + collar records |
| **Import without UTM zone** | Auto-detect from coordinate ranges (Egypt: UTM 36N typically). Show detected zone for user confirmation. |
| **Coordinates look like lat/long** | Heuristic: values < 180 suggest lat/long. Warn user, suggest UTM conversion. |
| **Swapped easting/northing** | Range-check: Egypt easting ~200,000-800,000, northing ~2,500,000-3,200,000. Flag if reversed. |
| **Mixed zones in one import** | Reject. One project = one UTM zone. |

---

## Unit Handling

| Field | Allowed Units | Storage |
|---|---|---|
| Assay grade | `ppm`, `g/t`, `%` | Store in original unit with explicit `grade_unit` column. Never convert silently. |
| Depth | meters only | Convert feet→meters at import with audit note |
| Coordinates | UTM meters | Always meters |
| Detection limit | Same unit as grade | Store alongside `below_detection_limit` flag |

---

## Below-Detection-Limit (BDL) Handling

**Rule:** Never zero-out or drop BDL values.

| Import Value | Storage |
|---|---|
| `<0.01` | `grade_value = 0.01`, `below_detection_limit = true`, `detection_limit = 0.01` |
| `BDL` or `-` | `grade_value = NULL`, `below_detection_limit = true`, `detection_limit = NULL` (unknown) |
| `0.5` | `grade_value = 0.5`, `below_detection_limit = false` |

---

## Import Error Handling

| Issue | Behavior | User Sees |
|---|---|---|
| Missing UTM zone | Block commit | "Select UTM zone" dialog |
| Mixed units in same file | Block commit | "File contains both ppm and g/t — select primary unit" |
| Swapped easting/northing | Warn, allow override | "Coordinates may be swapped — confirm or swap" |
| Overlapping intervals | Warn, do NOT auto-fix | Highlighted rows in diff view, geologist decides |
| Gap in intervals | Warn, do NOT auto-fix | Highlighted rows in diff view |
| Duplicate hole_id | Warn | "Hole X already exists — merge or skip?" |
| Non-numeric grade | Reject row | Row highlighted red with error message |

---

## Indexes (Performance)

```sql
-- Essential indexes for Phase 0
CREATE INDEX idx_collar_project ON collar(project_id);
CREATE INDEX idx_collar_hole_id ON collar(project_id, hole_id);
CREATE INDEX idx_survey_collar ON survey(collar_id, depth);
CREATE INDEX idx_assay_collar ON assay_interval(collar_id, from_depth);
CREATE INDEX idx_assay_grade ON assay_interval(collar_id, grade_value);
CREATE INDEX idx_lith_collar ON lithology_interval(collar_id, from_depth);
CREATE INDEX idx_trench_project ON trench(project_id);
CREATE INDEX idx_import_batch_project ON import_batch(project_id, import_date);
```

---

## Soft Versioning / Audit Trail

- **Never DELETE rows** — use `superseded_by` column (points to the newer record)
- Current records: `WHERE superseded_by IS NULL`
- Full history: `ORDER BY created_at` (no WHERE filter)
- Each import batch has a unique ID for traceability
- `import_batch.status` transitions: `pending → validated → committed` (or `superseded`)

---

## Reserved Fields (Phase 2, schema-present now)

These columns exist in the schema but have NO UI or validation in Phase 0:

| Table | Field | Phase |
|---|---|---|
| `lithology_interval` | `rqd_percent` | Phase 2 |
| `lithology_interval` | `core_recovery_percent` | Phase 2 |
| `lithology_interval` | `structure_type` | Phase 2 |
| `lithology_interval` | `structure_dip` | Phase 2 |
| `lithology_interval` | `structure_azimuth` | Phase 2 |
| `assay_interval` | `qaqc_type` | Phase 2 |
| `assay_interval` | `qaqc_flag` | Phase 2 |

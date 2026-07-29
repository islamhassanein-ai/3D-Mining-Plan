---

description: "Task list for feature implementation"
---

# Tasks: Combined CSV Import — Zone Splitting, Hole Types & Trench Polylines

**Input**: This document is self-contained. No other design doc exists for this feature.

**Prerequisites**: Extends the existing `backend/` and `frontend/` trees from features
003–005. Does not create a new project.

**Tests**: Automated tests are REQUIRED. This feature carries data-loss risk (T014 fixes
an existing bug that silently destroys assay data) and data-duplication risk (T012). Both
must have regression tests.

**Note for the executor**: Every task names the exact file(s) to create or edit. Reuse the
existing helpers named in each task — `get_csv_reader`, `clean_header`,
`compute_minimum_curvature_trace`, `check_coordinate_anomalies`, `orderTrenchPoints` — do
not write parallel implementations. Where a task says "do NOT", there is a specific
failure behind it; read the rationale before deviating.

---

## Background — what we are building and why

The app currently requires four separate CSVs (collar / survey / assay / lithology) plus a
disconnected trench uploader, and every import targets exactly one project.

Real field data is a single **Master Reference CSV** per project area that mixes all
exploration types, carries inline `Dip`/`Azimuth`/`Total_Length`, and spans multiple
prospect zones in one file. Reference file: `F:\Monark\15_Leapfrog\CSV\Collar.csv`.

```
Hole Id,Zone,X,Y,Z,Dip,Azimuth,Total_Length,Type
ARCH001,Abo elmajd,208322,2467932,297,-8,48,11,CH
ARTR001,Abo elmajd,208272,2467864,299.13,16,100,145,TR
ARTR014A,Abo elmajd,208303.025,2467933.65,302.858,16,120,23.5,TR
ARTR031,Samir,207593.546,2467771.849,309.923,0,92,25,TR
ARDD0001,Abo elmajd,208316.223,2467944.22,301.67,-50,122,44.3,DD
ARDD0001A,Abo elmajd,208299.053,2467942.149,300.55,-50,50,32.4,DD
```

That file has 25 data rows: 3 `DD`, 21 `TR`, 1 `CH`, across 5 zones (`Abo elmajd`, `Adel`,
`Tallat`, `Nabil`, `Samir`).

Goal: upload that one file, route each row by `Type`, auto-create or append to a project
per `Zone`, and give TR/CH/FC visible 3D geometry. Because it is a *master reference*
file, re-uploading it must update existing records and append new ones **without
duplicating data and without destroying anything already imported**.

### Scope boundary — READ THIS FIRST

The combined CSV is **header-level only: one row per hole/trench**. Every `Hole Id` in the
reference file is unique. `ARTR014A/B/C` are three separate trenches, not three segments of
one.

The 1-metre multi-point interval data and per-sample surveyed coordinates live in a
**separate Sampling/Assay Sheet** handled in later work.

Therefore this feature does **NOT** build polylines by grouping repeated `hole_id` rows —
there is no such data in this file. We add the `point_order` column now so the future
sampling sheet can populate points `1..N` without another migration.

### Key geological constraint — do not get this wrong

`Dip`/`Azimuth` on TR/CH/FC describe **the local ground slope at the starting collar point
only** — *not* the trajectory of the whole trench. A trench follows undulating terrain: it
may start on a rise, descend, then flatten.

**Never extrapolate the start dip across the trench length.** Doing so puts `ARTR001`
(dip +16°, length 145 m) **40 metres in the air** above its collar, floating over the
terrain mesh. Eight TR rows in the reference file have a positive dip.

With only a start coordinate available, the generated trench stays flat at collar
elevation (`dz = 0`), and dip/azimuth are stored as start-point metadata. True per-point
elevations arrive later from the sampling sheet.

### Locked decisions

| Decision | Value |
|---|---|
| Supported `hole_type` values | `DD`, `RC`, `TR`, `CH`, `FC` |
| Missing `hole_type` column | Warning + default to `DD` |
| Invalid `hole_type` value | Error on that row |
| Default fallback CRS | `37N` (EPSG:32637); `utm_zone_confirm` overrides when supplied |
| Auto-project commodity | `Gold` |
| TR/CH/FC storage | `Trench` table, multi-point with `point_order` |
| DD/RC storage | `Collar` + optional inline `Survey` |
| Zone splitting | Auto-create project if not found; append if found |
| Hole/Trench IDs | Used verbatim — never strip suffixes |

---

## How to run things

```bash
cd backend && python -m pytest tests/ -v
```

```bash
cd backend && alembic upgrade head
```

**Critical testing caveat**: `backend/tests/integration/test_import_flow.py` builds its
schema with `Base.metadata.create_all(bind=engine)` against in-memory **SQLite** — not via
Alembic. Consequences:

1. A model change with a **missing or wrong migration still passes every test.** After
   T001/T002 you must verify the migration separately with `alembic upgrade head` against
   a real PostgreSQL database.
2. SQLite does not enforce foreign keys by default, so FK violations (T011) will not
   surface in tests. Reason about them from the schema.

---

## Phase 1: Schema (Foundational — blocks everything else)

Migration style reference: `backend/alembic/versions/f1a2b3c4d5e6_add_trench_elevation.py`.
**Current Alembic head is `f1a2b3c4d5e6`** — chain the first new migration from it.

- [ ] **T001** Create migration `backend/alembic/versions/<rev>_add_collar_hole_type.py`
  (`down_revision = 'f1a2b3c4d5e6'`):
  - `op.add_column('collar', sa.Column('hole_type', sa.String(10), nullable=True))`
  - Backfill existing rows: `op.execute("UPDATE collar SET hole_type = 'DD' WHERE hole_type IS NULL")`
  - `op.create_index('idx_collar_project_hole_type', 'collar', ['project_id', 'hole_type'])`
  - `downgrade()` drops the index then the column.

  Then add `hole_type = Column(String(10), nullable=True)` to
  `backend/src/models/collar.py` and add the index to its existing `__table_args__`
  tuple (which already contains `idx_collar_project_hole`).

- [ ] **T002** Create migration `backend/alembic/versions/<rev>_add_trench_polyline_fields.py`
  (`down_revision` = T001's revision). All columns **nullable** — the two legacy uploaders
  in `backend/src/api/projects.py` (`upload_trenches`, `upload_trenches_shapefile`) will
  never set them, and existing rows have no values:
  - `point_order INTEGER`
  - `hole_type VARCHAR(10)`
  - `import_batch_id UUID` FK → `import_batch.id`
  - `superseded_by UUID` FK → `trench.id`
  - `dip FLOAT`, `azimuth FLOAT`
  - `op.create_index('idx_trench_project_trench_order', 'trench', ['project_id', 'trench_id', 'point_order'])`

  Then update `backend/src/models/trench.py` to match, adding an `import_batch`
  relationship. Add a `trenches` relationship to
  `backend/src/models/import_batch.py` alongside the existing `collars` /
  `assay_intervals` ones.

  Document in the model docstring: **`Trench.superseded_by` points at the replacement
  polyline's `point_order = 0` row** (the anchor), not at a per-point counterpart —
  point counts change between imports. Reads only ever filter `superseded_by IS NULL`;
  the FK serves audit lineage alone.

**Checkpoint**: `alembic upgrade head` then `alembic downgrade -2` runs clean against
PostgreSQL, and `pytest tests/ -v` is still green.

---

## Phase 2: Parser

- [ ] **T003** Add `parse_combined_csv(file_content: bytes) -> Tuple[List[Dict], List[Dict]]`
  to `backend/src/services/csv_import.py`.

  **Do NOT modify `parse_collar_csv`** — it is shared with the existing four-file import
  flow and changing it risks that path. Reuse `get_csv_reader` and `clean_header`
  (already in this file); `get_csv_reader` handles encoding fallback, delimiter sniffing,
  and header normalization.

  Header aliasing, applied after `clean_header` lowercases and underscores each header
  (`Hole Id` → `hole_id`, `Total_Length` → `total_length`):

  | Canonical | Accepted |
  |---|---|
  | `hole_id` | `hole_id`, `holeid`, `hole`, `trench_id` |
  | `easting` | `x`, `easting`, `east` |
  | `northing` | `y`, `northing`, `north` |
  | `elevation` | `z`, `elevation`, `elev`, `rl` |
  | `dip` | `dip` |
  | `azimuth` | `azimuth`, `azi`, `bearing` |
  | `total_length` | `total_length`, `total_depth`, `length`, `eoh` |
  | `hole_type` | `type`, `hole_type` |
  | `zone` | `zone`, `area`, `prospect` |

  > The `x`/`y`/`z` aliases are **mandatory**. Without them the reference file is
  > rejected outright: `parse_collar_csv` requires `{hole_id, easting, northing,
  > elevation}` at `csv_import.py:59` and the real header row supplies `X,Y,Z`.

  Rules:
  - Required: `hole_id` + all three coordinates. Missing → header-level error with
    `"row": 0`, matching the existing parsers' shape.
  - `hole_type`: normalize `.strip().upper()`. Column absent → **one** warning for the
    whole file (not per row) and default every row to `DD`. Value not in
    `{DD, RC, TR, CH, FC}` → row-level error.
  - **Distinguish an empty string from a literal `0`.** `ARTR031` has a real `Dip=0` and
    `ARTR008` has `Azimuth=2`. A truthiness check (`if not dip_str`) wrongly treats `0`
    as missing — test for `== ""` after stripping.
  - `dip`/`azimuth` present without `total_length` → error.
  - `total_length` present without both `dip` and `azimuth` → error.
  - `total_length <= 0` → error (otherwise zero-length geometry).
  - Range checks matching `parse_survey_csv`: dip `-90..90`, azimuth `0..360`.
  - `zone`: `" ".join(raw.split())` to collapse internal whitespace and strip. Blank or
    column absent → leave as `None`; the caller falls back to the URL project.
  - Use `enumerate(reader, start=2)` so reported row numbers match spreadsheet line
    numbers. (The existing parsers use `start=1` and are off by one; leave them alone.)

  Each returned row:

  ```python
  {
      "hole_id": str, "easting": float, "northing": float, "elevation": float,
      "hole_type": str,            # normalized, always populated
      "zone": str | None,
      "inline_survey": {"dip": float, "azimuth": float, "total_length": float} | None,
  }
  ```

  Errors keep the existing shape: `{"row": int, "error": str, "raw_data": dict}`.

- [ ] **T004 [P]** Unit tests in `backend/tests/unit/test_csv_import.py`:
  - `X`/`Y`/`Z` aliasing and `Hole Id` → `hole_id`.
  - Missing `Type` column → exactly one warning, all rows default to `DD`.
  - `Type=XX` → row error naming the invalid value; valid rows in the same file still parse.
  - `total_length` absent / `0` / negative / present-without-dip → errors.
  - Literal `Dip=0` and `Azimuth=0` parse as `0.0`, not as missing.
  - Zone normalization: `"Abo elmajd"`, `"  Abo  elmajd "` produce the same normalized key.
  - Error row numbers match spreadsheet lines (first data row reports `2`).
  - Existing `parse_collar_csv` tests still pass unchanged.

---

## Phase 3: Routing

- [ ] **T005** Create `backend/src/services/combined_routing.py` with
  `route_combined_rows(rows: List[Dict]) -> Dict[str, List[Dict]]` returning
  `{"collars": [...], "surveys": [...], "trench_points": [...]}`.

  **DD / RC → collars**
  - One collar dict per row, carrying `hole_type`.
  - When `inline_survey` is present, emit **one** survey at
    **`depth = total_length`** — not `0`.

    > Rationale: `compute_minimum_curvature_trace` at
    > `backend/src/services/desurvey.py:79` auto-prepends a virtual station at depth 0
    > with the same orientation, producing a correct two-station trace. A single station
    > at depth 0 yields a **one-point trace** and the hole renders as an invisible point.

  **TR / CH / FC → trench_points** — generate a provisional two-point, **horizontal**
  polyline per row:

  | `point_order` | `easting` | `northing` | `elevation` |
  |---|---|---|---|
  | 0 | `x` | `y` | `z` |
  | 1 | `x + L*sin(radians(az))` | `y + L*cos(radians(az))` | `z` — **unchanged, dz = 0** |

  - `dip` and `azimuth` stored on the `point_order = 0` row only (start-point slope
    metadata); leave them `None` on row 1.
  - `hole_type` stored on both points.
  - The `sin`/`cos` assignment matches `get_direction_cosine` at `desurvey.py:102-105`
    (azimuth measured clockwise from North, so easting takes `sin`).
  - **Do NOT call `compute_minimum_curvature_trace` for trenches.** It applies dip along
    the full length — see "Key geological constraint" above.
  - `grade_value` stays `None`; the combined CSV carries no grade column.

- [ ] **T006 [P]** Unit tests in new `backend/tests/unit/test_combined_routing.py`:
  - `TR` row → exactly 2 points, `point_order` 0 and 1, **identical elevations**.
  - Endpoint bearing: azimuth `90`, length `100` → easting `+100`, northing unchanged
    (within 1e-6); azimuth `0` → northing `+100`, easting unchanged.
  - A positive-dip TR row (`dip=16, total_length=145`) produces **zero** elevation change —
    the explicit regression guard for the floating-trench bug.
  - `DD` row → one survey at `depth == total_length`; feeding it through
    `compute_minimum_curvature_trace` yields a 2-point trace.
  - `DD` row with no dip/azimuth → collar with no survey, no crash.
  - `CH` and `FC` route to `trench_points`, not `collars`.

---

## Phase 4: Zone resolution and batch fan-out

- [ ] **T007** Add `resolve_or_create_zone_projects(db, zones, current_user, utm_zone, commodity="Gold")`
  to `backend/src/services/combined_routing.py`. Returns
  `{normalized_zone_key: {"project": Project, "action": "created" | "appended"}}`.

  - Match key: `" ".join(zone.split()).casefold()`, so `"Abo elmajd"`, `"Abo Elmajd"`,
    and `"abo elmajd "` all resolve to one project. Store the **first-seen original
    casing** as the project name.
  - An existing project matches only when **`owner_id == current_user.id`** AND
    **`superseded_by IS NULL`**. `Project.name` has no unique constraint; without these
    filters an import can land in a superseded project or in another user's project.
  - On create, set `owner_id = current_user.id`. A null owner makes a project
    inaccessible to everyone — see the comment at `backend/src/models/project.py:16-22`.

- [ ] **T008** UTM zone resolution. Precedence: `utm_zone_confirm` from the commit
  request when supplied, else **`37N`**.
  - In `backend/src/services/crs.py`: change the `project_default_zone` default at line 6
    from `"36N"` to `"37N"`, and add a module-level
    `EPSG_BY_UTM_ZONE = {"36N": 32636, "37N": 32637}` lookup for downstream export use.
  - In `backend/src/api/imports.py:106`: change the `"36N"` fallback to `"37N"`.
  - Applies uniformly to auto-created projects, `Collar.utm_zone` (NOT NULL), and the
    zone stamped at commit. An existing project that already has a `utm_zone` keeps it —
    the fallback only fills a null.
  - **Leave `backend/src/api/projects.py:297` and `:323` alone** (the legacy shapefile
    uploaders). Changing the CRS assumption for already-imported data is out of scope.

- [ ] **T009** Extend `create_import` in `backend/src/api/imports.py` with an optional
  `combined_file: Optional[UploadFile] = File(None)` parameter, alongside the existing
  four. When supplied, parse via `parse_combined_csv`, route via `route_combined_rows`,
  and resolve zones — **without creating projects yet** (preview must not mutate).

  Add a `zones` key to the validation payload, before any commit happens:

  ```
  zones: [{ zone, project_id: str | null, action: "created" | "appended",
            collar_count, trench_count, hole_type_breakdown: {DD: n, TR: n, ...} }]
  ```

  > Without this, creating four new projects is an invisible side effect of clicking
  > Commit. `project_id` is `null` for zones that would be newly created.

- [ ] **T010** Batch fan-out in `commit_import`. `ImportBatch.project_id` is a NOT NULL FK
  to exactly one project, so create **one `ImportBatch` row per resolved project**, all
  sharing the same `source_file` blob ref. The batch created at preview time belongs to
  the URL project; commit adds the rest and sets every one to `status="committed"`.

  Each collar/trench row must get the `import_batch_id` of the batch **belonging to its
  own project**.

  > Without this, collars in project *Adel* carry an `import_batch_id` whose batch has
  > `project_id` = *Abo elmajd*. Two consequences: provenance and history are
  > misattributed, and `delete_project` (`backend/src/api/projects.py:105`) deletes
  > `ImportBatch` rows by `project_id` while collars in other projects still reference
  > them — an `IntegrityError` that leaves the project permanently undeletable.

  Wrap the whole commit in a single `try` / one `db.commit()` / `except: db.rollback(); raise`.

  Commit response:

  ```
  { "message": str,
    "batches": [{ project_id, project_name, import_batch_id,
                  action, collar_count, trench_count }] }
  ```

  Project **IDs**, not just counts — the frontend needs them to navigate.

---

## Phase 5: Idempotent re-import and the data-loss fix

- [ ] **T011** Trench supersede in `commit_import`. Before inserting a trench's points,
  mark all rows for that `(project_id, trench_id)` with `superseded_by IS NULL` as
  superseded, setting `superseded_by` to the **new `point_order = 0` row**.

  > Without this, re-uploading the master CSV silently duplicates every trench polyline —
  > `Trench` currently has no batch tracking and no unique constraint. The two legacy
  > uploaders sidestep this with a `DELETE WHERE project_id` wipe
  > (`projects.py:197`, `:307`); the additive commit path does not.

- [ ] **T012** **Fix an existing data-loss bug** in `commit_import`
  (`backend/src/api/imports.py:255-288`).

  Current behaviour: superseding a collar inserts a **new** `Collar` row with a new UUID
  and points the old one at it. The old collar's `Survey`, `AssayInterval`, and
  `LithologyInterval` rows stay attached to the **old** collar id. Every read path fetches
  children by the *active* collar's id (`backend/src/api/scene.py:68-127`,
  `backend/src/api/collars.py:44-69`).

  > Consequence: re-uploading a master collar file **without also re-supplying assays and
  > lithologies silently wipes every drillhole's assays, lithologies, and survey trace
  > from the 3D scene.** With no surveys, `compute_minimum_curvature_trace` returns `[]`
  > and the hole collapses to a zero-length point. This triggers on the very first
  > re-upload of a Master Reference CSV.

  Fix: when `old_collar` exists —
  - If the incoming batch supplies surveys/assays/lithologies for that `hole_id`, keep
    current behaviour (old children stay with the old collar).
  - If it does **not**, re-point the old collar's active `Survey`, `AssayInterval`, and
    `LithologyInterval` rows to `new_collar_id`.

  Replace the now-inaccurate explanatory comment at `imports.py:266-276` — its reasoning
  holds only when the same batch replaces the intervals.

- [ ] **T013** Validation, in `backend/src/services/import_validation.py`:
  - Add a `trenches` parameter to `validate_import_batch`. Trench rows must stay out of
    the `collars` list **and** their inline dip/azimuth must stay out of `surveys`.

    > Otherwise the `orphan_hole_id` rule at `import_validation.py:75` raises a blocking
    > **error** for every trench row (they have no matching collar), `has_errors` is
    > true, and no combined import can ever commit (`imports.py:220`).
  - New rule: the same `hole_id` appearing under two different zones → error (ambiguous
    routing).
  - New rule: the same `hole_id` appearing with two different `hole_type`s → error.
  - Run the existing `check_coordinate_anomalies` per zone group rather than once for the
    whole file.
  - The existing collar-vs-project UTM comparison must use each row's **resolved** project
    zone, not the URL project's (`imports.py:94` currently passes `project.utm_zone`).

---

## Phase 6: Scene and frontend

- [ ] **T014** `backend/src/api/scene.py:156-168`: filter `Trench.superseded_by.is_(None)`,
  order by `(trench_id, point_order)`, and serialize `point_order`, `hole_type`, `dip`,
  `azimuth` alongside the existing fields. Without this the new columns are dead weight.

- [ ] **T015** `frontend/src/scene/trenches.js:99-111`: sort each group by `point_order`
  when **every** point in that group has one; otherwise fall back to the existing
  `orderTrenchPoints` nearest-neighbour chaining.

  > Legacy trench rows have `point_order = NULL` and would sort unpredictably. Keep
  > `orderTrenchPoints` — do not delete it.

  Note the two-point polylines this feature generates already render correctly:
  `orderTrenchPoints` returns early for `length <= 2` (line 11).

- [ ] **T016** `frontend/src/components/import_panel.js` and
  `frontend/src/services/api_client.js:106`:
  - Add a single "Combined CSV" file input to the existing import panel, sending
    `combined_file`.
  - Render the preview `zones` breakdown before commit, so the user sees which projects
    will be created versus appended and can reject.
  - After commit, list the created/appended projects from `batches` with links.

  > `handleCommit` (`import_panel.js:479`) currently only reloads the current project's
  > scene — a multi-project import would look like nothing happened.

---

## Phase 7: Integration tests

- [ ] **T017** Add `backend/tests/fixtures/combined_master.csv` — a verbatim copy of the
  25-row reference file above. Then in
  `backend/tests/integration/test_import_flow.py`:
  - Full file → **5 projects, 3 collars, 22 trenches × 2 points = 44 trench rows**.
  - Pre-create a project named `Abo elmajd` owned by the test user → it is **appended**
    to, not duplicated; the other 4 are created.
  - A project named `Abo elmajd` owned by a *different* user is **not** matched — a new
    one is created for the importing user.
  - Re-upload the identical file → counts unchanged, zero duplicates, prior trench rows
    superseded. **(T011 regression)**
  - Import collar + assay, then re-import collar only → the scene still returns the assays
    and the drillhole still has a 2-point trace. **(T012 regression — this is the
    data-loss guard; it must fail before the T012 fix and pass after.)**
  - Every collar's `import_batch_id` resolves to a batch whose `project_id` equals that
    collar's `project_id`; `delete_project` then succeeds on all 5 projects. **(T010)**
  - A file with no `Type` column imports as all-`DD` with a warning, and still commits.

---

## Manual verification

After `alembic upgrade head` against PostgreSQL, start the app and upload
`F:\Monark\15_Leapfrog\CSV\Collar.csv` through the import panel. Confirm:

1. The preview lists **5 zones** with per-zone counts **before** commit.
2. After commit, the 3 DD holes render with visible traces (not zero-length points).
3. The 22 trenches render as flat fences at collar elevation — **nothing floating above
   the terrain**. Check `ARTR001` specifically (dip +16, length 145): its far end must sit
   at Z ≈ 299.13, not ≈ 339.
4. Re-uploading the same file changes no counts and creates no duplicate geometry.

Record honestly if any check has not genuinely been performed — do not fabricate a result.

---

## Out of scope

- Grouping repeated `hole_id` rows into multi-point polylines (no such data in this file;
  arrives with the Sampling/Assay Sheet).
- Draping trench points onto the topography mesh (needs the sampling sheet's surveyed Z).
- Stripping suffixes from hole IDs. `ARTR014A/B/C` are distinct trenches and `ARDD0001A`
  is a twin of `ARDD0001` — any stripping rule would be wrong for one of these cases.
- Changing the CRS assumption of the legacy shapefile uploaders.
- Making `detect_utm_zone` (`crs.py:3-18`) actually detect anything — it is a stub that
  echoes its default, and stays that way.

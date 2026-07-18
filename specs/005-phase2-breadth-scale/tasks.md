---

description: "Task list for feature implementation"
---

# Tasks: Phase 2 — Breadth & Scale

**Input**: Design documents from `specs/005-phase2-breadth-scale/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md,
quickstart.md (all present). This feature extends the existing `backend/` and
`frontend/` trees from features 003 and 004 — it does not create a new project.

**Tests**: Automated tests are REQUIRED for DXF/Shapefile parsing correctness and
for the new RQD/core-recovery and QA/QC range-validation rules (plan.md Technical
Context → Testing) — these carry the same data-corruption risk tier as feature 003's
CSV import validation. Export byte-level fidelity and LOD rendering behavior are
validated manually via `quickstart.md`.

**Note for the executor**: Every task names the exact file(s) to create or edit and
the exact source document/section it is built from (`data-model.md`,
`contracts/api.md`, or `research.md`). Reuse feature 003's existing code (`crs.py`,
`import_validation.py`, the `InstancedMesh` buffers in `assay_intervals.js`/
`lithology_intervals.js`, the storage abstraction) wherever a task says "reuse" or
"extend" — do not create parallel/duplicate implementations. Where `quickstart.md`
requires a human-judgment check (e.g., "remains smoothly interactive"), do not
fabricate a result — record honestly if it hasn't genuinely been checked, exactly as
required throughout this project's tasks.md files since feature 001.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US7)
- Setup, Foundational, and Polish tasks have no `[Story]` label.

## Path Conventions

Per `plan.md` Project Structure (additive to features 003/004's existing tree):
- Backend: `backend/src/{models,services,api}/`, `backend/tests/unit/`
- Frontend: `frontend/src/{scene,components,services}/`

---

## Phase 1: Setup

**Purpose**: Add the three new backend dependencies this feature needs.

- [ ] T001 Add `ezdxf`, `pyshp`, and `reportlab` to `backend/requirements.txt` (per
  research.md Decisions 1-3 and plan.md Primary Dependencies) and install them into
  the existing backend virtual environment. No other new dependency may be added
  without updating plan.md.

**Checkpoint**: The three new libraries are importable in the backend environment.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The two new entities every relevant user story depends on.

**⚠️ CRITICAL**: No user-story task may begin until this phase is complete.

- [ ] T002 [P] Create the Structural Reading model in
  `backend/src/models/structural_reading.py` per `data-model.md` § Structural
  Reading (fields: id, project_id, reading_type, easting, northing, elevation, dip,
  strike, import_batch_id, superseded_by).
- [ ] T003 [P] Create the QA/QC Standard Reference model in
  `backend/src/models/qaqc_standard.py` per `data-model.md` § QA/QC Standard
  Reference (fields: id, project_id, standard_name, expected_grade_min,
  expected_grade_max, grade_unit).
- [ ] T004 Generate an Alembic migration in `backend/alembic/versions/` adding the
  `structural_reading` and `qaqc_standard` tables from T002-T003, on top of the
  existing schema. Depends on T002, T003.

**Checkpoint**: Both new tables exist in the schema. User-story work can now begin.

---

## Phase 3: User Story 1 - Import a DXF wireframe with real geometry validation (Priority: P1) 🎯 MVP (part 1 of 3)

**Goal**: A DXF wireframe file is parsed (not just referenced) and its real geometry
renders in the 3D scene.

**Independent Test**: `quickstart.md` Scenario 1 passes without Shapefile import,
export, or any P2/P3 story's code existing.

### Implementation for User Story 1

- [ ] T005 [US1] Implement `parse_dxf_wireframe(file_bytes) -> (vertices, faces,
  errors)` in `backend/src/services/dxf_service.py`, using `ezdxf` per research.md
  Decision 1. Parse errors are returned as data, not raised as exceptions that
  abort the whole request.
- [ ] T006 [US1] Write pytest unit tests for `parse_dxf_wireframe` in
  `backend/tests/unit/test_dxf_service.py`: a valid small DXF fixture parses to the
  expected vertex/face counts; a corrupt/non-DXF file produces a parse error result,
  not an unhandled exception. Depends on T005.
- [ ] T007 [US1] Extend `POST /projects/{project_id}/wireframes` (existing endpoint
  in `backend/src/api/projects.py` from feature 003) so that when the uploaded
  file's extension is `.dxf`, it is parsed via T005 and the resulting geometry is
  stored alongside the existing `file_ref`; a parse failure returns a per-file
  error without touching any other project data, per `contracts/api.md` and
  feature 003's established wireframe error-handling behavior. Depends on T005.
- [ ] T008 [US1] Extend `GET /projects/{project_id}/scene`
  (`backend/src/api/scene.py`) so each wireframe's payload includes the parsed
  DXF geometry (vertices/faces) when available, instead of only the file
  reference. Depends on T007.
- [ ] T009 [US1] Update `frontend/src/scene/wireframes.js` to render parsed DXF
  geometry (vertices/faces) from T008's scene payload when present, instead of a
  placeholder. Depends on T008.

**Checkpoint**: `quickstart.md` Scenario 1 passes. FR-001, FR-002 satisfied.

---

## Phase 4: User Story 2 - Import Shapefiles for trenches and topography (Priority: P1) 🎯 MVP (part 2 of 3)

**Goal**: Trench and topography data can be imported from Shapefiles with the same
CRS/validation rigor as CSV.

**Independent Test**: `quickstart.md` Scenario 2 passes without DXF import, export,
or any P2/P3 story's code existing.

### Implementation for User Story 2

- [ ] T010 [US2] Implement `parse_trench_shapefile(file_bytes) -> (rows, errors)`
  and `parse_topography_shapefile(file_bytes) -> (surface_data, errors)` in
  `backend/src/services/shapefile_service.py`, using `pyshp` per research.md
  Decision 2.
- [ ] T011 [US2] Write pytest unit tests for both functions in
  `backend/tests/unit/test_shapefile_service.py`: valid trench/topography
  fixtures parse correctly; a Shapefile with a missing/ambiguous CRS is flagged,
  not silently assumed. Depends on T010.
- [ ] T012 [US2] Implement `POST /projects/{project_id}/trenches/shapefile` in
  `backend/src/api/projects.py`, reusing feature 003's CRS auto-detect-then-confirm
  flow (`backend/src/services/crs.py`) and `import_validation.py` rules before
  commit, per `contracts/api.md`. Depends on T010.
- [ ] T013 [US2] Implement `POST /projects/{project_id}/topography/shapefile` in
  `backend/src/api/projects.py`, same pattern as T012. Depends on T010.
- [ ] T014 [US2] Add a Shapefile upload option to
  `frontend/src/components/import_panel.js` for trench/topography data, reusing
  the existing diff/CRS-confirmation UI pattern from feature 003's CSV import flow.
  Depends on T012, T013.

**Checkpoint**: `quickstart.md` Scenario 2 passes. FR-003, FR-004 satisfied.

---

## Phase 5: User Story 3 - Export project data for use in other tools (Priority: P1) 🎯 MVP (part 3 of 3)

**Goal**: Wireframes, the current section view, and drillhole data can each be
exported.

**Independent Test**: `quickstart.md` Scenario 3 passes without any P2/P3 story's
code existing (a project with data from features 003/004 is sufficient).

### Implementation for User Story 3

- [ ] T015 [US3] Implement `export_wireframes_to_dxf(project_id) -> bytes` in
  `backend/src/services/dxf_service.py`, using `ezdxf` to write all of a project's
  wireframe geometry into one DXF file, per research.md Decision 1.
- [ ] T016 [US3] Implement `export_section_to_pdf(project_id, plane_params) ->
  bytes` in `backend/src/services/pdf_export.py`, using `reportlab` to render the
  same section-view geometry the frontend's 2D section component uses, per
  research.md Decision 3.
- [ ] T017 [US3] Implement `export_entity_to_csv(project_id, entity_type) -> bytes`
  in `backend/src/services/csv_export.py` for `collars`/`surveys`/`assays`/
  `lithologies`, schema-compatible with the Phase 0 import path, per
  `contracts/api.md`.
- [ ] T018 [US3] Implement `backend/src/api/exports.py` with
  `GET /projects/{project_id}/export/wireframes.dxf`,
  `GET /projects/{project_id}/export/section.pdf`, and
  `GET /projects/{project_id}/export/data.csv`, wiring in T015-T017 and enforcing
  the project-scoping (404-not-403) rule from `contracts/api.md`. Depends on T015,
  T016, T017.
- [ ] T019 [US3] Register the exports router in `backend/src/api/main.py`. Depends
  on T018.
- [ ] T020 [US3] Build `frontend/src/components/export_panel.js` with buttons that
  trigger each export endpoint as a file download. Depends on T019.

**Checkpoint**: `quickstart.md` Scenario 3 passes. FR-005–FR-007 satisfied. This
completes the MVP (US1 + US2 + US3).

---

## Phase 6: User Story 4 - Record and view structural/fault data (Priority: P2)

**Goal**: Structural readings can be entered and seen in the 3D scene.

**Independent Test**: `quickstart.md` Scenario 4 passes without US5, US6, or US7's
code existing.

### Implementation for User Story 4

- [ ] T021 [US4] Implement `POST /projects/{project_id}/structural-readings` and
  `GET /projects/{project_id}/structural-readings` in
  `backend/src/api/structural.py`, per `contracts/api.md` and `data-model.md`.
  Depends on T002.
- [ ] T022 [US4] Register the structural router in `backend/src/api/main.py`.
  Depends on T021.
- [ ] T023 [US4] Extend `GET /projects/{project_id}/scene`
  (`backend/src/api/scene.py`) to include structural readings in its response, per
  `contracts/api.md`. Depends on T021.
- [ ] T024 [US4] Implement fault trace / dip-strike rendering in
  `frontend/src/scene/structural_readings.js`, consuming T023's scene payload.
  Depends on T023.
- [ ] T025 [US4] Build `frontend/src/components/structural_panel.js` for entering
  structural readings, wired to T021's endpoints via new functions in
  `frontend/src/services/api_client.js`. Depends on T021.

**Checkpoint**: `quickstart.md` Scenario 4 passes. FR-008, FR-009 satisfied.

---

## Phase 7: User Story 5 - Record and validate RQD/core recovery (Priority: P2)

**Goal**: RQD/core-recovery values are validated on import and visible on
inspection.

**Independent Test**: `quickstart.md` Scenario 5 passes without US4, US6, or US7's
code existing.

### Implementation for User Story 5

- [ ] T026 [US5] Extend `backend/src/services/import_validation.py` with a rule
  rejecting `rqd_percent`/`core_recovery_percent` values outside `[0, 100]` as a
  blocking error, per `data-model.md` § Validation Rules and research.md
  Decision 5.
- [ ] T027 [US5] Write pytest unit tests for the new rule in
  `backend/tests/unit/test_rqd_qaqc_validation.py`: a valid value passes; a value
  outside 0-100 is a blocking error. Depends on T026.
- [ ] T028 [US5] Confirm/extend `frontend/src/components/inspector_panel.js` to
  display `rqd_percent`/`core_recovery_percent` in the interval table — these
  fields already exist on Lithology Interval per feature 003's data model; this
  task ensures the UI actually surfaces them, per FR-011.

**Checkpoint**: `quickstart.md` Scenario 5 passes. FR-010, FR-011 satisfied.

---

## Phase 8: User Story 6 - Record and validate QA/QC sample flags (Priority: P2)

**Goal**: Duplicate/standard/blank samples are flagged and standard results are
checked against a configured expected range.

**Independent Test**: `quickstart.md` Scenario 6 passes without US4, US5, or US7's
code existing.

### Implementation for User Story 6

- [ ] T029 [US6] Implement `POST /projects/{project_id}/qaqc-standards` and
  `GET /projects/{project_id}/qaqc-standards` in `backend/src/api/qaqc.py`, per
  `contracts/api.md`. Depends on T003.
- [ ] T030 [US6] Register the qaqc router in `backend/src/api/main.py`. Depends on
  T029.
- [ ] T031 [US6] Extend `backend/src/services/import_validation.py` with: (a)
  `qaqc_flag` assignment from the assay CSV's QA/QC indicator column
  (`duplicate`/`standard`/`blank`/none), and (b) for `standard`-flagged rows,
  comparison against the matching QA/QC Standard Reference (T029's data) — a
  warning (not blocking error) when out of range, and an `unconfigured` flag when
  no matching reference exists — per `data-model.md` § Validation Rules. Depends
  on T029.
- [ ] T032 [US6] Write pytest unit tests for the new rules in
  `backend/tests/unit/test_rqd_qaqc_validation.py` (same file as T027): correct
  flag assignment for each sample type; in-range standard passes silently;
  out-of-range standard produces a warning; a standard with no configured
  reference produces `unconfigured`. Depends on T031.
- [ ] T033 [US6] Build `frontend/src/components/qaqc_panel.js` for configuring QA/QC
  Standard References and viewing flagged samples, wired to T029's endpoints via
  new functions in `frontend/src/services/api_client.js`. Depends on T029.

**Checkpoint**: `quickstart.md` Scenario 6 passes. FR-012, FR-013 satisfied.

---

## Phase 9: User Story 7 - Stay responsive as a prospect grows dense (Priority: P3)

**Goal**: The scene stays smoothly interactive well beyond the Phase 0 baseline
scale, with no data loss.

**Independent Test**: `quickstart.md` Scenario 7 passes without any other Phase 2
story's code existing (only feature 003's scene is required).

### Implementation for User Story 7

- [ ] T034 [US7] Implement `frontend/src/scene/lod_manager.js` per research.md
  Decision 4: distance-based visibility toggling over the existing `InstancedMesh`
  buffers in `frontend/src/scene/assay_intervals.js` and
  `frontend/src/scene/lithology_intervals.js`, activating only when the combined
  assay + lithology interval count exceeds ~20,000. Must not alter what
  `GET /projects/{id}/scene` returns or what `frontend/src/scene/selection.js`
  resolves on click — rendering-only.
- [ ] T035 [US7] Wire `lod_manager.js` into `frontend/src/scene/scene_loader.js` so
  it runs automatically after scene load. Depends on T034.

**Checkpoint**: `quickstart.md` Scenario 7 passes. FR-014 satisfied.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Apply the project-scoping rule everywhere and prove the whole feature
works together.

- [ ] T036 Apply project-scoping (a request for data outside the authenticated
  user's accessible projects returns 404, never 403) to every route added in this
  feature: T007, T012, T013, T018, T021, T029, per `contracts/api.md` §
  Cross-cutting behavior. Depends on all listed endpoint tasks.
- [ ] T037 Run `quickstart.md` Scenarios 1-7 end-to-end, using real (not synthetic)
  DXF/Shapefile files where possible, per this project's kill-criterion discipline.
  Fix any gap found in the relevant earlier task's output before re-running. Do not
  fabricate the human-judgment parts of Scenario 7 (whether the scene "remains
  smoothly interactive") — record honestly if this hasn't genuinely been checked.

**Checkpoint**: All of spec.md's Success Criteria (SC-001–SC-006) are checked
against real usage.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Phase 1.
- **User Stories (Phases 3-9)**: All depend on Phase 2 (though most only need the
  parts of it relevant to their own entity — US1/US2/US3/US5/US7 don't actually
  need T002/T003 at all, only US4 and US6 do; they're grouped into one Foundational
  phase for simplicity since it's small). US1, US2, US3 have no dependencies on
  each other. US4, US5, US6, US7 each depend only on Phase 2 and feature 003's
  existing code — independent of each other and of US1-US3.
- **Polish (Phase 10)**: Depends on all routes/stories it touches.

### Within Each User Story

- US1: T005 → T006; T007 depends on T005; T008 depends on T007; T009 depends on
  T008.
- US2: T010 → T011; T012, T013 each depend on T010 (can be added in either order);
  T014 depends on T012, T013.
- US3: T015, T016, T017 are independent of each other (different files); T018
  depends on all three; T019 depends on T018; T020 depends on T019.
- US4: T021 independent; T022, T023 depend on T021; T024 depends on T023; T025
  depends on T021.
- US5: T026 → T027; T028 is independent (frontend) but logically follows once
  RQD/core-recovery data can actually be imported (T026).
- US6: T029 independent; T030, T031 depend on T029; T032 depends on T031; T033
  depends on T029.
- US7: T034 → T035.

---

## Parallel Execution Examples

```text
# Phase 2 (Foundational):
T002, T003 (different model files)

# Phases 3, 4, 5 (US1, US2, US3) can proceed in parallel once Phase 2 is done —
# no shared files:
Phase 3 (T005-T009)  ||  Phase 4 (T010-T014)  ||  Phase 5 (T015-T020)

# Phases 6, 7, 8, 9 (US4-US7) can likewise all proceed in parallel with each other
# and with Phases 3-5 — no shared files:
Phase 6 (T021-T025)  ||  Phase 7 (T026-T028)  ||  Phase 8 (T029-T033)  ||  Phase 9 (T034-T035)

# Within Phase 5 (US3), the three export services are independent:
T015, T016, T017
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 + 3, all P1)

1. Complete Phase 1: Setup (new dependencies).
2. Complete Phase 2: Foundational (new entities).
3. Complete Phase 3: User Story 1 (DXF import).
4. Complete Phase 4: User Story 2 (Shapefile import).
5. Complete Phase 5: User Story 3 (export).
6. **STOP and VALIDATE**: run `quickstart.md` Scenarios 1-3. This is the MVP — real
   breadth (import formats + export) without yet touching the deferred-field
   activations or scale work.

### Incremental Delivery

1. Setup + Foundational → new entities ready, nothing user-visible yet.
2. US1 → DXF import usable.
3. US2 → Shapefile import usable.
4. US3 → export usable → MVP complete.
5. US4 → structural data usable.
6. US5 → RQD/core recovery usable.
7. US6 → QA/QC usable.
8. US7 → scale headroom for dense prospects.
9. Polish → project-scoping hardened everywhere, full end-to-end validation.

---

## Notes

- [Story] label maps task to specific user story for traceability.
- Reuse feature 003's `crs.py`, `import_validation.py`, storage abstraction, and
  `InstancedMesh` rendering wherever a task says "reuse" or "extend" — this feature
  should not end up with a second, parallel implementation of any of those.
- Commit after each phase (or task) so partial progress is recoverable.
- Do not mark T037 complete without genuinely running the quickstart scenarios —
  fabricating this result is exactly the mistake caught and guarded against in
  every tasks.md in this project since feature 001.

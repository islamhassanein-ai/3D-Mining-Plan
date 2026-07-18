---

description: "Task list for feature implementation"
---

# Tasks: Phase 0 — Core Visualization & Modeling

**Input**: Design documents from `specs/003-phase0-core-visualization/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md,
quickstart.md (all present).

**Tests**: Automated tests are REQUIRED only for the two areas the constitution and
`plan.md` flag as correctness-critical: the minimum-curvature desurvey algorithm and
the import-validation rules. Everything else is validated manually via
`quickstart.md` (see plan.md Technical Context → Testing, and research.md Decision 8).
Do not add test frameworks or test files beyond what is explicitly listed below.

**Note for the executor**: Every task names the exact file(s) to create or edit and
the exact source document/section to build it from (`data-model.md`,
`contracts/api.md`, `research.md`, or the referenced constitution section). Do not
invent fields, endpoints, or behavior beyond what those documents state. Where a task
says a check is "human-verified" (Phase 12), do not fabricate the result — say
honestly if it hasn't happened yet, exactly as required in feature 002's tasks.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US8)
- Setup, Foundational, and Polish tasks have no `[Story]` label.

## Path Conventions

Per `plan.md` Project Structure:
- Backend: `backend/src/{models,services,api,storage,db}/`, `backend/tests/{unit,integration}/`
- Frontend: `frontend/src/{scene,components,services}/`
- Design docs: `specs/003-phase0-core-visualization/`

---

## Phase 1: Setup

**Purpose**: Initialize both projects so later tasks have somewhere to write code.

- [ ] T001 Create the backend project skeleton: `backend/src/models/`,
  `backend/src/services/`, `backend/src/api/`, `backend/src/storage/`,
  `backend/src/db/`, `backend/tests/unit/`, `backend/tests/integration/` (empty
  `__init__.py` in each Python package directory). Add `backend/pyproject.toml` (or
  `requirements.txt`) listing exactly: `fastapi`, `uvicorn`, `sqlalchemy>=2.0`,
  `geoalchemy2`, `alembic`, `pydantic`, `python-jose` (JWT), `pytest` — per plan.md
  Primary Dependencies. No other dependency may be added without updating plan.md.
- [ ] T002 [P] Create the frontend project skeleton: `frontend/src/scene/`,
  `frontend/src/components/`, `frontend/src/services/`, and `frontend/index.html`.
  Add `frontend/package.json` listing exactly `three` as a dependency and a minimal
  dev/build script (e.g. esbuild) — no UI framework, per constitution Technology
  Stack Constraints and plan.md.
- [ ] T003 [P] Initialize Alembic in `backend/alembic/` (`alembic.ini` reading the
  database URL from an environment variable, not hardcoded) per research.md Decision
  2.
- [ ] T004 [P] Add `backend/pytest.ini` (or `[tool.pytest.ini_options]` in
  `pyproject.toml`) pointing at `backend/tests/`.

**Checkpoint**: Both project skeletons exist and `pytest` runs (with zero tests) in
`backend/`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database models, migrations, storage abstraction, desurvey algorithm,
and auth scaffolding that every user story depends on.

**⚠️ CRITICAL**: No user-story task may begin until this phase is complete.

- [ ] T005 Create the SQLAlchemy declarative Base and session/engine setup in
  `backend/src/db/session.py`, reading the database URL from an environment
  variable.
- [ ] T006 [P] Create the Project model in `backend/src/models/project.py` per
  `data-model.md` § Project (fields: id, name, utm_zone, commodity, created_at,
  superseded_by).
- [ ] T007 [P] Create the ImportBatch model in `backend/src/models/import_batch.py`
  per `data-model.md` § Import Batch (fields: id, source_file, import_date, status).
- [ ] T008 [P] Create the User model in `backend/src/models/user.py` per
  `data-model.md` § User (fields: id, email, role).
- [ ] T009 [P] Create the Collar model in `backend/src/models/collar.py` per
  `data-model.md` § Collar, including the `(project_id, hole_id)` index.
- [ ] T010 [P] Create the Survey model in `backend/src/models/survey.py` per
  `data-model.md` § Survey.
- [ ] T011 [P] Create the Assay Interval model in
  `backend/src/models/assay_interval.py` per `data-model.md` § Assay Interval,
  including the `(collar_id, from_depth, to_depth)` index.
- [ ] T012 [P] Create the Lithology Interval model in
  `backend/src/models/lithology_interval.py` per `data-model.md` § Lithology
  Interval.
- [ ] T013 [P] Create the Trench model in `backend/src/models/trench.py` per
  `data-model.md` § Trench.
- [ ] T014 [P] Create the Wireframe model in `backend/src/models/wireframe.py` per
  `data-model.md` § Wireframe.
- [ ] T015 Generate the initial Alembic migration in `backend/alembic/versions/`
  covering all models from T006-T014. Depends on T006-T014 being complete.
- [ ] T016 [P] Implement the storage abstraction: an interface in
  `backend/src/storage/base.py` (`save(file) -> file_ref`, `load(file_ref) ->
  bytes`) and a local-filesystem implementation in
  `backend/src/storage/local_filesystem.py`, per research.md Decision 7. No code
  outside `backend/src/storage/` may call the filesystem directly for uploaded
  files.
- [ ] T017 [P] Implement the minimum-curvature desurvey function in
  `backend/src/services/desurvey.py`, per research.md Decision 4 (ratio-factor
  formulation). The function must accept a list of survey stations (depth, dip,
  azimuth) for one collar and return 3D positions along the trace. No other
  desurvey method may be implemented.
- [ ] T018 [P] Write pytest unit tests for `desurvey.py` in
  `backend/tests/unit/test_desurvey.py`, including explicit cases at near-vertical
  (dip ≈ -90°) and near-horizontal (dip ≈ 0°) stations, per research.md Decision 4
  and plan.md Testing. Depends on T017.
- [ ] T019 Implement the FastAPI application skeleton in `backend/src/api/main.py`
  (app instance, CORS config, a `get_current_user` dependency stub for auth).
- [ ] T020 Implement magic-link authentication in `backend/src/api/auth.py`:
  `POST /auth/magic-link` and `GET /auth/verify`, per `contracts/api.md` § Auth and
  research.md Decision 6. `/auth/verify` issues a short-lived JWT session token.
  Depends on T008 (User model) and T019.

**Checkpoint**: Database schema migrates cleanly; desurvey unit tests pass; a client
can obtain a JWT via the magic-link flow. User-story work can now begin.

---

## Phase 3: User Story 1 - Import CSV data with validation before commit (Priority: P1) 🎯 MVP (part 1 of 3)

**Goal**: A user can upload Collar/Survey/Assay/Lithology CSVs, see a validated
raw-vs-interpreted diff, and commit or reject the batch.

**Independent Test**: Following `quickstart.md` Scenario 1 end-to-end (upload → diff
→ confirm zone → commit) succeeds without any other user story's code existing.

### Implementation for User Story 1

- [ ] T021 [US1] Implement UTM zone auto-detection in `backend/src/services/crs.py`
  per research.md Decision 5 (Easting/Northing range heuristic).
- [ ] T022 [US1] Write pytest unit tests for `crs.py` in
  `backend/tests/unit/test_crs.py` covering a clearly-in-zone case and an
  out-of-range/ambiguous case. Depends on T021.
- [ ] T023 [US1] Implement CSV parsing functions
  (`parse_collar_csv`, `parse_survey_csv`, `parse_assay_csv`,
  `parse_lithology_csv`) in `backend/src/services/csv_import.py` using Python's
  built-in `csv` module only, per research.md Decision 1. Each function returns
  parsed rows plus per-row parse errors (not exceptions that abort the whole file).
- [ ] T024 [US1] Implement import validation rules in
  `backend/src/services/import_validation.py`, per `data-model.md` § Validation
  Rules: BDL preservation, overlap/gap detection on `(from_depth, to_depth)` per
  collar, mixed-unit rejection within one file, swapped lat/long heuristic, and
  orphan `hole_id` detection against the batch's own Collar rows. Depends on T023.
- [ ] T025 [US1] Write pytest unit tests for `import_validation.py` in
  `backend/tests/unit/test_import_validation.py`, with one test per rule: BDL
  preserved (not zeroed), overlapping interval flagged, gap flagged, mixed units
  rejected, swapped lat/long flagged, orphan hole_id flagged. Depends on T024.
- [ ] T026 [US1] Implement `POST /projects/{project_id}/imports` in
  `backend/src/api/imports.py`, per `contracts/api.md` § Imports: parses (T023),
  desurveys (T017), detects CRS zone (T021), runs validation (T024), stores the
  batch as `pending_review` (do not write to Collar/Survey/Assay/Lithology tables
  yet), and returns the full diff payload. Depends on T015, T021, T023, T024.
- [ ] T027 [US1] Implement `GET /projects/{project_id}/imports/{import_batch_id}` in
  `backend/src/api/imports.py` to re-fetch a pending batch's diff. Depends on T026.
- [ ] T028 [US1] Implement `POST /projects/{project_id}/imports/{import_batch_id}/commit`
  in `backend/src/api/imports.py`: writes Collar/Survey/Assay/Lithology rows
  (setting `superseded_by` on any rows they replace), sets `import_batch.status =
  committed`; returns 422 if unacknowledged blocking flags remain, per
  `contracts/api.md`. Depends on T026.
- [ ] T029 [US1] Implement `POST /projects/{project_id}/imports/{import_batch_id}/reject`
  in `backend/src/api/imports.py`, setting `status = rejected` without writing any
  committed rows. Depends on T026.
- [ ] T030 [US1] Implement `POST /projects` in `backend/src/api/projects.py`
  (creates a Project; `utm_zone` is left unset until the first committed import,
  per `data-model.md` § Validation Rules). Depends on T006.
- [ ] T031 [US1] Write a pytest integration test in
  `backend/tests/integration/test_import_flow.py` covering the full
  create-project → upload → commit flow using small fixture CSV files checked into
  `backend/tests/integration/fixtures/`. Depends on T026, T028, T030.
- [ ] T032 [US1] Build the frontend import UI in
  `frontend/src/components/import_panel.js` (+ matching CSS): file inputs for the
  four CSV types, a diff table (raw vs. interpreted, flags highlighted), the
  detected-UTM-zone confirmation control, and commit/reject buttons.
- [ ] T033 [US1] Implement the API client functions `createProject`,
  `uploadImports`, `getImportBatch`, `commitImport`, `rejectImport` in
  `frontend/src/services/api_client.js`, and wire `import_panel.js` (T032) to them.
  Depends on T032.

**Checkpoint**: `quickstart.md` Scenario 1 passes. FR-001–FR-009 satisfied.

---

## Phase 4: User Story 2 - View drillholes and grade-colored intervals in an interactive 3D scene (Priority: P1) 🎯 MVP (part 2 of 3)

**Goal**: A committed project's drillholes render in a Three.js scene with CAD-style
navigation.

**Independent Test**: Following `quickstart.md` Scenario 2 against a committed
project (from US1) succeeds without US3-US8 code existing.

### Implementation for User Story 2

- [ ] T034 [US2] Implement `GET /projects/{project_id}/scene` in
  `backend/src/api/scene.py`, per `contracts/api.md` § Projects: returns desurveyed
  collar/survey positions, assay/lithology intervals, trenches, and wireframes for
  the project. Returns an explicit empty-but-valid payload (not an error) for a
  project with no committed imports, per FR-015. Depends on T009-T014, T017.
- [ ] T035 [US2] Implement grade-to-color mapping in
  `backend/src/services/grade_coloring.py`, used by T034's response to attach a
  color value to each assay interval.
- [ ] T036 [US2] Set up the Three.js scene bootstrap (renderer, camera, lighting) in
  `frontend/src/scene/scene.js`.
- [ ] T037 [US2] Implement damped orbit/pan/zoom camera controls that orbit around
  the point under the cursor (not the scene origin) in
  `frontend/src/scene/camera_controls.js`, per constitution Principle IV. Depends
  on T036.
- [ ] T038 [US2] Implement plan/section/isometric camera presets, exposed via a
  toolbar component (`frontend/src/components/toolbar.js`) and keyboard shortcuts.
  Depends on T037.
- [ ] T039 [US2] Implement drillhole trace rendering (line geometry from the
  desurveyed positions returned by T034) in
  `frontend/src/scene/drillhole_traces.js`. Depends on T036.
- [ ] T040 [US2] Implement `InstancedMesh` rendering for assay-interval cylinders,
  with per-instance color from T035's grade-color values, in
  `frontend/src/scene/assay_intervals.js`, per research.md Decision 3. Depends on
  T036.
- [ ] T041 [US2] Implement `InstancedMesh` rendering for lithology-interval
  cylinders in `frontend/src/scene/lithology_intervals.js`. Depends on T036.
- [ ] T042 [US2] Implement `frontend/src/scene/scene_loader.js`, which calls
  `GET /projects/{id}/scene` (add a `getScene` function to `api_client.js`) and
  feeds the response into T039-T041. Depends on T034, T039, T040, T041.

**Checkpoint**: `quickstart.md` Scenario 2 passes. FR-010–FR-014 satisfied.

---

## Phase 5: User Story 3 - Inspect a drillhole's full record on click (Priority: P1) 🎯 MVP (part 3 of 3)

**Goal**: Clicking a rendered drillhole shows its full collar/survey/interval
record.

**Independent Test**: Following `quickstart.md` Scenario 3 against a scene from US2
succeeds without US4-US8 code existing.

### Implementation for User Story 3

- [ ] T043 [US3] Implement `GET /collars/{collar_id}` in
  `backend/src/api/collars.py`, per `contracts/api.md` § Collars: returns collar
  coordinates, full survey list, and full assay/lithology interval tables, with
  every field from `data-model.md` present. Depends on T009-T012.
- [ ] T044 [US3] Implement click-to-select raycasting against the rendered
  drillhole traces (T039) in `frontend/src/scene/selection.js`. Depends on T039.
- [ ] T045 [US3] Build the drillhole inspector card component in
  `frontend/src/components/inspector_panel.js` (+ CSS), showing collar
  coordinates, survey dip/azimuth, and the full interval table.
- [ ] T046 [US3] Add a `getCollar` function to `frontend/src/services/api_client.js`
  and wire `selection.js` (T044) to `inspector_panel.js` (T045) so a click calls
  `GET /collars/{id}` and populates the card. Depends on T043, T044, T045.

**Checkpoint**: `quickstart.md` Scenario 3 passes. FR-016 satisfied. This completes
the MVP (US1 + US2 + US3).

---

## Phase 6: User Story 4 - Adjust grade cutoff in real time (Priority: P2)

**Goal**: A slider hides/dims assay intervals below a chosen grade in real time.

**Independent Test**: `quickstart.md` Scenario 4, step 1, against a scene from US2.

### Implementation for User Story 4

- [ ] T047 [US4] Build the grade-cutoff slider component in
  `frontend/src/components/grade_cutoff_slider.js`.
- [ ] T048 [US4] Extend `frontend/src/scene/assay_intervals.js` (from T040) to
  expose a `setGradeCutoff(value)` function that updates per-instance visibility
  without reloading the scene, and wire the slider (T047) to it. Depends on T040,
  T047.

**Checkpoint**: FR-019 satisfied.

---

## Phase 7: User Story 5 - Slice the model with a synced 2D section view (Priority: P2)

**Goal**: An interactive slicing plane drives a synced 2D section view.

**Independent Test**: `quickstart.md` Scenario 4, step 2, against a scene from US2.

### Implementation for User Story 5

- [ ] T049 [US5] Implement the slicing-plane control (N-S, E-W, arbitrary azimuth)
  in `frontend/src/scene/slicing_plane.js`. Depends on T036.
- [ ] T050 [US5] Implement the synced 2D section view component in
  `frontend/src/components/section_view.js`, updating as the slicing plane (T049)
  moves. Depends on T049.

**Checkpoint**: FR-020 satisfied.

---

## Phase 8: User Story 6 - Measure distances and true thickness (Priority: P2)

**Goal**: Two-point 3D distance measurement, plus true-thickness computation.

**Independent Test**: `quickstart.md` Scenario 4, steps 3-5, against a scene from
US2 and an inspector card from US3.

### Implementation for User Story 6

- [ ] T051 [US6] Implement two-point 3D distance measurement in
  `frontend/src/scene/measurement.js`. Depends on T036.
- [ ] T052 [US6] Implement `GET /collars/{collar_id}/true-thickness` in
  `backend/src/api/collars.py` (extending T043's router), computing true thickness
  from the collar's survey dip at the interval's depth; returns an explicit
  "unavailable" result when dip data is missing, per `contracts/api.md` and the
  spec's Edge Cases. Depends on T043.
- [ ] T053 [US6] Add a `getTrueThickness` function to `api_client.js` and display
  the result (or "unavailable") in `inspector_panel.js` (T045). Depends on T052,
  T045.

**Checkpoint**: FR-017, FR-018 satisfied.

---

## Phase 9: User Story 7 - View topography, trenches, and imported solids alongside drillholes (Priority: P2)

**Goal**: Topography surface, trench points, and wireframe solids render in the same
scene as drillholes.

**Independent Test**: `quickstart.md` Scenario 5, steps 1-2, against a scene from
US2.

### Implementation for User Story 7

- [ ] T054 [US7] Implement `POST /projects/{project_id}/topography` in
  `backend/src/api/supplementary.py`, storing the surface reference via the
  storage abstraction (T016). Depends on T016, T030.
- [ ] T055 [US7] Implement `POST /projects/{project_id}/trenches` in
  `backend/src/api/supplementary.py` (bulk-create Trench rows). Depends on T013.
- [ ] T056 [US7] Implement `POST /projects/{project_id}/wireframes` in
  `backend/src/api/supplementary.py`, storing the file via T016; a parse failure
  on this endpoint returns a per-file error and never rejects other data, per the
  spec's Edge Cases. Depends on T014, T016.
- [ ] T057 [US7] Extend `GET /projects/{project_id}/scene` (T034) to include
  topography, trench, and wireframe data from T054-T056. Depends on T034, T054,
  T055, T056.
- [ ] T058 [US7] Implement topography surface rendering in
  `frontend/src/scene/topography.js`. Depends on T036, T057.
- [ ] T059 [US7] Implement trench point rendering in
  `frontend/src/scene/trenches.js`. Depends on T036, T057.
- [ ] T060 [US7] Implement wireframe/vein solid rendering in
  `frontend/src/scene/wireframes.js`, with a visible per-item error state when a
  wireframe failed to parse (per spec Edge Cases). Depends on T036, T057.

**Checkpoint**: FR-021–FR-023 satisfied.

---

## Phase 10: User Story 8 - Orient myself with a CAD-style gizmo (Priority: P3)

**Goal**: An orientation gizmo reflects the current camera orientation.

**Independent Test**: `quickstart.md` Scenario 2, step 7, against a scene from US2.

### Implementation for User Story 8

- [ ] T061 [US8] Implement a CAD-style orientation gizmo synced to camera
  orientation in `frontend/src/scene/orientation_gizmo.js`. Depends on T036, T037.

**Checkpoint**: FR-014 satisfied.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Reliability behaviors that span every user story.

- [ ] T062 [P] Implement empty/loading/error state UI components in
  `frontend/src/components/states.js`, used wherever a project has no data yet or a
  request is in flight/failed, per FR-015.
- [ ] T063 [P] Implement a client-side last-loaded-project cache in
  `frontend/src/services/project_cache.js`, per FR-024, so a brief connectivity
  drop doesn't blank the screen.
- [ ] T064 Add project-scoping authorization to every API router (T026-T030, T034,
  T043, T052, T054-T056): a request for data outside the authenticated user's
  accessible projects returns 404, never 403, per `contracts/api.md` § Cross-cutting
  behavior. Depends on T020 and all listed endpoint tasks.

---

## Phase 12: Final Validation (Human-Verified)

**Purpose**: Confirm the feature actually works end-to-end and meets its success
criteria — this phase cannot be done by transcription alone.

- [ ] T065 Run `quickstart.md` Scenarios 1-6 end-to-end against a real (not
  synthetic) CSV dataset, per the spec's kill criterion (SC-002). Fix any gap found
  in the relevant earlier task's output before re-running. Record the SC-002 (import
  friction vs. prior workflow) and SC-006 (5-minute first-impression) results
  honestly — these require a real human doing the import/using the tool, not a
  fabricated pass. Do not mark this task complete without that having genuinely
  happened.

**Checkpoint**: All of spec.md's Success Criteria (SC-001–SC-006) are checked
against real usage, not assumed.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Phase 1.
- **User Stories (Phases 3-10)**: All depend on Phase 2. US1/US2/US3 (Phases 3-5)
  have no dependencies on each other and can proceed in parallel if staffed, though
  US2/US3 are most useful once US1 can produce committed data to view. US4-US8
  (Phases 6-10) each depend only on Phase 2 and, for frontend wiring, on relevant
  US2/US3 scene/inspector code already existing (noted per-task above).
- **Polish (Phase 11)**: Depends on the user stories whose endpoints/components it
  touches (see T064's dependency list).
- **Final Validation (Phase 12)**: Depends on all of Phases 3-11.

### Within Each User Story

- US1: T021 → T022; T023 → T024 → T025; T026 depends on T021/T023/T024; T027-T029
  depend on T026; T030 is independent; T031 depends on T026/T028/T030; T032 → T033.
- US2: T034 depends on models + T017; T035 independent; T036 → T037 → T038;
  T036 → T039/T040/T041 (parallelizable once T036 exists); T042 depends on all of
  T034, T039, T040, T041.
- US3: T043 independent (backend); T044 depends on T039; T045 independent
  (frontend); T046 depends on T043, T044, T045.
- US6: T052 depends on T043 (shares the collars router).

---

## Parallel Execution Examples

```text
# Phase 1 (Setup) — all four can run together:
T001, T002, T003, T004

# Phase 2 (Foundational) — model files are independent of each other:
T006, T007, T008, T009, T010, T011, T012, T013, T014
# (T015 migration must wait for all of the above)
T016, T017 can run alongside the model tasks (different files)

# Phase 4 (US2) — once T036 exists:
T039, T040, T041 (different files, all read-only against the scene from T036)

# Phase 11 (Polish):
T062, T063
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 + 3, all P1)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (models, migration, storage, desurvey, auth).
3. Complete Phase 3: User Story 1 (import with validation).
4. Complete Phase 4: User Story 2 (3D scene + navigation).
5. Complete Phase 5: User Story 3 (drillhole inspection).
6. **STOP and VALIDATE**: run `quickstart.md` Scenarios 1-3. This is the MVP — a
   geologist can import real data and look at it with confidence.

### Incremental Delivery

1. Setup + Foundational → nothing user-visible yet, but the ground is solid.
2. US1 → data can be trusted into the system (kill criterion territory).
3. US2 → data can be seen, CAD-quality.
4. US3 → data can be verified in place → MVP complete.
5. US4-US6 → grade cutoff, section view, measurement — deepen the analysis loop.
6. US7 → topography/trench/wireframe — full spatial picture.
7. US8 → orientation gizmo — polish.
8. Phase 11 → reliability under real-world conditions (empty projects, dropped
   connectivity, cross-project access).
9. Phase 12 → the actual, human-verified proof this all works together.

---

## Notes

- [Story] label maps task to specific user story for traceability.
- Every task names its exact target file(s) and the design document it must be
  built from — no task requires inventing fields, endpoints, or behavior not
  already specified in `data-model.md`, `contracts/api.md`, or `research.md`.
- Commit after each phase (or task) so partial progress is recoverable.
- Do not mark T065 (or claim SC-002/SC-006 results) without a genuine human having
  done the import/usage check — this is the one phase in this file that requires a
  human, not just code, exactly as called out for feature 002's T024.

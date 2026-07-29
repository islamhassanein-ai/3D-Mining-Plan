---

description: "Task list for feature implementation"
---

# Tasks: Export Project as Interactive Standalone HTML

**Input**: Design documents from `specs/006-standalone-html-export/`

**Prerequisites**: `spec.md`, `plan.md`, `contracts/api.md`, `quickstart.md` (all
present). This feature extends the existing `backend/` and `frontend/` trees from
features 003–005 — it does not create a new project and adds no Python or npm
dependency.

**Tests**: Automated tests are REQUIRED for (a) true-thickness JS↔Python parity and
(b) the self-containment / escaping / size-budget properties of the assembled
document. Both carry the risk tier this project has always tested: (a) puts wrong
geology numbers in a client deliverable; (b) puts credentials or injected script in
a file that gets emailed outside the company. Rendering fidelity and offline
behaviour are validated by hand via `quickstart.md` — a browser is the only honest
oracle for those.

**Note for the executor**:

- Every task names exact files and the source section it is built from.
- **Reuse, do not re-implement.** Where a task says "reuse", use the existing
  function — `get_project_scene`, `get_collar_details`, `DampedCameraControls`,
  `AssayIntervals`, `parseOBJ`, the `InstancedMesh` buffers. Creating a parallel
  implementation is the specific failure this plan exists to prevent (`plan.md`
  ADR-001/ADR-003).
- **Phase 1 must not change any behaviour.** It is a pure refactor. If the live app
  looks or acts different after Phase 1, the refactor is wrong — fix it before
  moving on.
- Where `quickstart.md` asks for a human-judgment check ("orbits smoothly", "surface
  reads correctly"), do not fabricate a result. Record honestly if it has not
  genuinely been checked — as required in every `tasks.md` in this repo since
  feature 001.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1–US4 from `spec.md`. Setup / Foundational / Polish carry no label.

## Path Conventions

- Backend: `backend/src/{services,api}/`, `backend/tests/unit/`
- Frontend: `frontend/src/{scene,components,services,export}/`, `frontend/styles/`,
  `frontend/tests/`
- Spec assets: `specs/006-standalone-html-export/fixtures/`

---

## Phase 1 — Foundational Refactor (no behaviour change)

> Gate: after T010, the live app must pass `quickstart.md` §1 with zero observable
> difference. Do not start Phase 2 until it does.

### T001 — Extract the true-thickness algorithm to JavaScript

**Create** `frontend/src/services/true_thickness.js`.

Port `backend/src/api/collars.py:172–249`, preserving structure so the two stay
diffable:

- `interpolateSurveyOrientation(surveys, midDepth) -> {dip, azimuth}` —
  `collars.py:178–216`. Defaults `-90.0` / `0.0` with no surveys; clamp below the
  first / above the last station; **interpolate azimuth on the unit circle**
  (`atan2` of the blended cos/sin, mod 360) — never linearly.
- `computeTrueThickness({surveys, fromDepth, toDepth, dipDirection, dip}) -> TrueThicknessDTO`
  — `collars.py:218–249`. Return every field listed in `contracts/api.md` §4.

Pure functions, no imports, no DOM. Do not delete or alter the Python
implementation — it remains authoritative for the live app.

---

### T002 [P] — Create the parity fixture

**Create** `specs/006-standalone-html-export/fixtures/true_thickness_vectors.json`
per `contracts/api.md` §5, covering all seven required cases. Compute expected
values by hand or from the Python implementation, and state which in a `"source"`
field per case.

---

### T003 [P] — Parity tests, both languages

**Create** `backend/tests/unit/test_true_thickness_vectors.py` — load the fixture,
drive `collars.py::get_true_thickness`'s math (extract the pure part into a helper
if the DB coupling makes it untestable; keep the endpoint calling that helper),
assert within `tolerance`.

**Create** `frontend/tests/true_thickness_parity.test.mjs` — `node --test`, no
dependencies:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
```

Load the same fixture, drive `computeTrueThickness`, assert within `tolerance`.

**Modify** `frontend/package.json`: add `"test": "node --test frontend/tests/"` (run
from repo root) or `"test": "node --test tests/"` (from `frontend/`) — match whichever
directory the script's `--prefix` implies, and document the exact command in
`quickstart.md` §6.

**Both tests must fail** if either implementation is edited in isolation. Verify by
temporarily breaking one — that verification is the point of the task.

---

### T004 — Extract the project-summary calculation

**Create** `frontend/src/services/project_summary.js`, exporting
`computeProjectSummary(sceneData) -> { drillholes: {holes, meters, avgGrade, peakGrade},
trenches: {count, samples, avgGrade, peakGrade} }`.

Move the arithmetic from `index.html:1252–1287` (`updateDdAndTrenchSummary`) verbatim
— including its documented convention that total metres come from each hole's
deepest assay interval, not raw trace length.

**Modify** `frontend/index.html`: `updateDdAndTrenchSummary` keeps its name and its
DOM writes but takes its numbers from `computeProjectSummary`. Same rendered values.

---

### T005 — Introduce the `SceneDataSource` seam

**Create** `frontend/src/services/data_source.js` per `contracts/api.md` §4 and
`plan.md` ADR-002. Export `ApiDataSource`, `ShareTokenDataSource`.

**Create** `frontend/src/services/static_data_source.js`. Export `StaticDataSource`.
This file imports **only** `./true_thickness.js` — no `api_client.js`, no
`window.location`, no API base URL. This isolation is required for T022/T023: the
export viewer bundle must not ship any live-app credentials or API metadata.

- `ApiDataSource(projectId)` / `ShareTokenDataSource(token)` wrap the existing
  `ApiClient` methods — no new fetch logic; move the `/uploads/` fetches from
  `topography.js:47` and `wireframes.js:77` in as-is.
- `StaticDataSource(payload)` reads `payload.scene`, `payload.collar_details`,
  `payload.topography.points` (expanding `[e,n,el]` → `{e,n,el}`) and delegates
  `getTrueThickness` to `true_thickness.js` using the collar's embedded `surveys`.
  Throw a descriptive `Error` on an unknown `collarId`.
- Do **not** re-export `StaticDataSource` from `data_source.js`.

Export `isStatic` on each (`false`, `false`, `true`).

---

### T006 — Split fetching from rendering in `SceneLoader`

**Modify** `frontend/src/scene/scene_loader.js`.

- Extract the identical bodies of `loadProject` (`:28–45`) and `loadSharedProject`
  (`:62–79`) into `renderScene(data)`.
- Add `async load(dataSource)`: `getScene()` → resolve topography and wireframe
  geometry through the same data source → `renderScene(data)` → return `data`.
- Keep `loadProject(projectId)` and `loadSharedProject(token)` as two-line wrappers
  over `load(new ApiDataSource(...))` / `load(new ShareTokenDataSource(...))`, so
  `index.html:1073,1431` need no change.
- Preserve the `this.loading` re-entrancy guard and the `fitCameraToData` call.
- Drop the direct `ApiClient` import once nothing in the file uses it.

---

### T007 [P] — Make `TopographyRenderer` data-source agnostic

**Modify** `frontend/src/scene/topography.js`.

Add `renderPoints(points)` taking already-parsed `[{e,n,el}]` and running the
existing `_buildPointCloud` / `_buildTriangulatedMesh` / `_applyDisplayMode` / bounds
helper (`:89–98`) untouched. `renderCSVPoints(csvText)` keeps parsing (`:62–85`) and
then calls `renderPoints`. `loadAndRender(fileRef)` keeps its signature and
behaviour. No change to `elevationColor`, materials, or `setDisplayMode`.

---

### T008 [P] — Make `WireframesRenderer` data-source agnostic

**Modify** `frontend/src/scene/wireframes.js`.

Replace the inline `fetch` fallback (`:76–84`) with an injected resolver:
`constructor(scene, resolveGeometry = null)`. When `w.vertices`/`w.faces` are
present, keep the existing inline path (`:63–74`) — that stays the fast path. When
absent, `await this.resolveGeometry(w)`; on `null`, `console.warn` and skip that
wireframe (never throw — one bad wireframe must not blank the scene, matching the
current `try/catch` at `:122`).

Keep `parseOBJ` exported — `ApiDataSource` and the backend port (T014) both mirror it.

---

### T009 — Make `InspectorPanel` data-source driven

**Modify** `frontend/src/components/inspector_panel.js`.

Replace `options.shareToken` (`:11`) with `options.dataSource`. Route `:174–178` to
`dataSource.getCollarDetails(collarId)` and `:446–450` to
`dataSource.getTrueThickness(...)`. Remove the `ApiClient` import. All rendering,
tabs, highlighting, and scroll-to-row behaviour unchanged.

---

### T010 — Wire the live app to the seam

**Modify** `frontend/index.html`.

- `loadProjectScene` (`:1048`): `new InspectorPanel('inspector-container', { dataSource: new ApiDataSource(projectId), onIntervalSelected })`.
- `loadSharedScene` (`:1405`): the `ShareTokenDataSource(token)` equivalent.
- Everything else unchanged.

**Gate**: run `quickstart.md` §1 (live app regression). Owner mode and share-link
mode must both behave exactly as before. Do not proceed until this passes.

---

## Phase 2 — Build Pipeline & Shared Styling

### T011 — Extract the app stylesheet

**Create** `frontend/styles/app.css` — a **verbatim** move of `index.html:8–614`
(the contents of `<style>`, without the tags). No reformatting, no reordering, no
"while I'm here" fixes; that keeps the diff reviewable and makes the regression
check meaningful.

**Modify** `frontend/index.html`: replace the `<style>` block with
`<link rel="stylesheet" href="styles/app.css">`.

The file is served by the existing catch-all static mount (`main.py:69`) — no backend
change needed.

**Verify**: live app at 1280×800 and 1600×900, panels collapsed and expanded, 2D
section open and closed — pixel-identical to before (`quickstart.md` §1).

---

### T012 — Add the export bundle to the build

**Modify** `frontend/package.json`:

```json
"scripts": {
  "dev": "esbuild src/scene/scene.js --bundle --outfile=dist/bundle.js --serve=8001 --servedir=. --watch",
  "build:app": "esbuild src/scene/scene.js --bundle --minify --outfile=dist/bundle.js",
  "build:export": "esbuild src/export/viewer_main.js --bundle --minify --format=iife --outfile=dist/export_viewer.js",
  "build": "npm run build:app && npm run build:export",
  "test": "node --test tests/"
}
```

`--format=iife` is mandatory (`plan.md` ADR-004): an ES-module bundle cannot load
from `file://`. `run.ps1:44` already calls `npm run build`, so it fans out with no
change to the script.

---

## Phase 3 — Exported Viewer (US1, US2, US3)

### T013 [US1] — Build the static viewer shell

**Create** `frontend/src/export/shell.html` — the `<body>` content only (no
`<!DOCTYPE>`, `<html>`, `<head>`, or `<script>` tags; the backend supplies those).

Start from `index.html:618–849` and remove, per FR-014: the project selector and
create/delete buttons (`:653–661`), the whole **Data Actions** block (`:757–764`),
the login/modal container (`:818`), and the UTM zone *editing* control (`:707–716` —
keep the zone as read-only footer text).

Keep: header + brand + `#header-stats`, the visual-controls sidebar (cutoff,
histogram, grade legend, layers, topography display mode, go-to-coordinate, camera
presets, ruler), `#viewport-3d`, `#viewport-hint-card`, `#section-view-container`,
`#section-edge-tab`, `#toolbar-3d-container`, the inspector aside, both panel edge
tabs, `#global-loading`, and `#shortcut-help-overlay`.

Add, per FR-015: a `STATIC EXPORT` chip in the header, and a `#export-footer` bar for
project name, UTM zone, export timestamp, exporter, counts, and `notices`. All of it
populated at runtime via `textContent` — never interpolated server-side
(`plan.md` §6).

**Modify** `frontend/styles/app.css`: append styles for the chip and footer. Reuse
the existing custom properties (`--gold`, `--border-light`, `--text-muted`); add no
new palette.

---

### T014 [US1] [P] — Server-side OBJ geometry resolution

**Create** `backend/src/services/obj_geometry.py` with
`parse_obj(text) -> {"vertices": [[x, y, z]], "faces": [[i, j, k]]}`.

Mirror `frontend/src/scene/wireframes.js:3–40`: `v` lines in raw UTM order
`(easting, northing, elevation)` — **do not** apply the Y-up swap here; that is the
renderer's job (`wireframes.js:68`) and doing it twice silently mirrors the model.
Triangulate quads as `(0,1,2)` + `(0,2,3)`. Skip comments and blanks. 1-indexed →
0-indexed. Return empty lists rather than raising on malformed input.

---

### T015 [US1] — HTML assembly service

**Create** `backend/src/services/html_export.py`.

```python
MAX_TOPO_POINTS  = 60_000
MAX_EXPORT_BYTES = 60 * 1024 ** 2
SIZE_WARN_BYTES  = 15 * 1024 ** 2

def decimate_topography(points, max_points=MAX_TOPO_POINTS): ...
def parse_topography_csv(text): ...
def encode_payload(payload: dict) -> str: ...
def build_standalone_html(payload, shell_html, css_text, bundle_js) -> bytes: ...
```

- `parse_topography_csv` — same rules as `topography.js:62–85`; header match is
  case-insensitive on `east*` / `north*` / `elev*`|`z`|`alt*`; skip non-numeric rows.
- `decimate_topography` — grid-bin per `plan.md` ADR-006: grid sized so occupied
  cells ≈ `max_points`; keep the sample nearest each cell centre. Deterministic
  (same input → same output; a test asserts this). Degenerate extents (all points
  collinear or identical) must not divide by zero.
- `encode_payload` — `json.dumps(payload, ensure_ascii=False, separators=(",", ":"))`
  then escape the five characters that can break out of the script element or
  the JS parser, replacing each with its JSON unicode escape sequence:
  `<` -> `\u003c`, `>` -> `\u003e`, `&` -> `\u0026`,
  LINE SEPARATOR (U+2028) -> `\u2028`, PARAGRAPH SEPARATOR (U+2029) -> `\u2029`.
  All five substitutions are lossless inside JSON string literals, and none of
  these characters occur structurally in JSON.
- `build_standalone_html` — substitute the sentinels of `contracts/api.md` §3
  **in this order**: `MONARK_TITLE` (via `html.escape`), `MONARK_CSS`,
  `MONARK_SHELL`, then `MONARK_DATA`, then `MONARK_BUNDLE`. Single pass per
  sentinel; **never** re-scan the assembled output. Raise a typed
  `ExportTooLargeError(size, largest_contributor)` above `MAX_EXPORT_BYTES`; log a
  warning above `SIZE_WARN_BYTES`.

Keep this module DB-free and dependency-free so it is unit-testable without a
database (T022).

---

### T016 [US1] — The export endpoint

**Modify** `backend/src/api/export.py` — add
`GET /projects/{project_id}/export/standalone.html` per `contracts/api.md` §1.

Sequence:

1. `project = get_owned_project_or_404(project_id, db, current_user)` — same guard as
   the sibling routes.
2. `scene = get_project_scene(project_id=str(project.id), db=db, current_user=None)`
   — the reuse pattern already used at `share_links.py:130`.
3. For each drillhole, `get_collar_details(collar_id=..., db=db, current_user=None)`
   → `collar_details` map (`share_links.py:150` pattern).
4. Topography: pop `topography_ref`; if present and `include_topography`, read
   `os.path.join(storage.base_dir, ref)`, `parse_topography_csv`, decimate, emit
   `TOPOGRAPHY_DECIMATED`. Unreadable → `TOPOGRAPHY_UNREADABLE` notice, `included: false`,
   never a 500 — one missing file must not block the export.
5. Wireframes: skip `solid_type == "topography"` (already handled); if `vertices`/
   `faces` are absent, read `uploads/{file_ref}` and `parse_obj`; on failure, drop the
   wireframe with a `WIREFRAME_UNRESOLVED` notice. **Strip `file_ref` from every
   entry** before embedding.
6. Read `frontend/dist/export_viewer.js` — missing or empty → **HTTP 503** with the
   build command (FR-009). Capture its mtime as `generator.viewer_bundle_built_at`.
7. Read `frontend/src/export/shell.html` and `frontend/styles/app.css` (resolve via
   the existing `REPO_ROOT`/`FRONTEND_DIR` constants in `main.py:8–9`, or an
   equivalent module-local constant — do not hardcode absolute paths).
8. Assemble; catch `ExportTooLargeError` → **HTTP 413** with the contributor message.
9. `StreamingResponse(io.BytesIO(html_bytes), media_type="text/html; charset=utf-8")`
   with `Content-Disposition` (ASCII `filename` + RFC 5987 `filename*`) and
   `Cache-Control: no-store`.

---

### T017 [US1] [US2] [US3] — Viewer bootstrap

**Create** `frontend/src/export/viewer_main.js` — the `build:export` entry point.

1. On `DOMContentLoaded`, `JSON.parse(document.getElementById('monark-scene-data').textContent)`.
   Reject `format_version !== 1` with a readable in-page message, not a console error.
2. `const ds = new StaticDataSource(payload)`.
3. `window.init3DViewport('viewport-3d', { onSelect })` — unchanged `scene.js`.
4. `const data = await viewport.sceneLoader.load(ds)`.
5. Instantiate, mirroring `index.html:1048–1146`: `InspectorPanel({ dataSource: ds })`,
   `SceneToolbar`, `LayerTogglePanel`, `GradeHistogram`, `CutoffSlider`,
   `SectionViewPanel`, `MeasurementTool`, `hover.setData(data.drillholes)`,
   `lodManager.setDrillholes` (via `sceneLoader`), camera presets + reset,
   `setupGotoCoordinate`, `setupTopoModeToggle`.
6. Header stats via `computeProjectSummary` (T004).
7. Panel collapse tabs + `animateResize` (`index.html:909–936`), hint-card dismiss,
   shortcut help overlay + `?`/`Esc` handling (`:947–965`). Extract these into small
   local helpers rather than copying the inline handlers wholesale.
8. Provenance: `STATIC EXPORT` chip; footer from `payload.generator` /
   `payload.project` / counts / `notices` — all via `textContent`.
9. Hide `#global-loading` when the first frame is up; on any bootstrap throw, replace
   the viewport with a plain-language error panel (no stack traces — the recipient
   is a geologist, not a developer).

**Must not import**: `api_client.js`, `import_panel.js`, `share_panel.js`,
`history_panel.js`, `structural_panel.js`, `qaqc_panel.js`, `project_switcher.js`,
`export_panel.js`. Note that `scene.js` imports all of them for its `window.*`
registrations — so `viewer_main.js` must import the specific modules it needs
(`init3DViewport` and each component) **directly from their own files**, not rely on
`window.*` globals. Getting this wrong pulls `ApiClient` into the bundle and fails T023.

Import `StaticDataSource` from `services/static_data_source.js`, **never** from
`data_source.js` — the latter imports `ApiClient` and would reintroduce the bundle
pollution T023 is designed to catch.

---

### T018 [US1] — Add the HTML export row to the export panel

**Modify** `frontend/src/components/export_panel.js`.

Add a fourth `.export-option-row`: title "Interactive 3D Viewer (HTML)", description
naming what it is — a single self-contained file that opens in any browser with no
login or internet, showing the project as of the export date.

Generalise `handleDownload` (`:193–257`): add `html: 'standalone.html'` to
`routePaths` (`:220`) and `html` to `this.loading` (`:8–12`); fix the filename
derivation (`:236–241`), which currently produces `project_<id>_export.html` for any
unknown format — make it `{project}_3D_Viewer_{date}.html`, or better, honour the
server's `Content-Disposition` when present. Reuse the existing status banner and
spinner states unchanged.

Add an "Include topography surface" checkbox mapping to `include_topography`. This is
the one lever a user needs when a file comes out too large.

---

## Phase 4 — Tests & Hardening

### T019 [P] — Endpoint authorisation tests

**Create/extend** `backend/tests/unit/test_export.py`:

- owner → 200, `text/html`, `Content-Disposition: attachment`
- non-owner → 404 (indistinguishable from unknown project)
- unauthenticated → 401
- unknown `project_id` → 404
- project with zero drillholes → 200 with an empty but valid payload (an empty
  project must export, not error)

---

### T020 [P] [US4] — Topography decimation tests

**Create** `backend/tests/unit/test_html_export.py::TestDecimation`:

- below cap → returned unchanged, order preserved
- above cap → result ≤ cap, deterministic across runs, E/N bounding box preserved
  within one cell width (coverage, not just count)
- all-identical points, all-collinear points, single point → no division by zero
- CSV parsing matches `topography.js` rules: header aliases, non-numeric rows
  skipped, `\r\n` line endings, trailing blank line

---

### T021 [P] — OBJ parser tests

**Create** `backend/tests/unit/test_html_export.py::TestObjGeometry` (or alongside
the existing `test_dxf_service.py`): triangles, quads → two triangles, comments and
blanks, `f v/vt/vn` index forms, malformed input → empty lists not an exception.
Assert vertex order stays raw UTM `(e, n, z)` — the mirroring bug T014 warns about
is invisible in a small fixture unless asserted explicitly.

---

### T022 — Assembly / escaping / budget tests

**Create** `backend/tests/unit/test_html_export.py::TestAssembly`:

- **Self-containment**: the assembled document contains no `src="http`, `href="http`,
  `@import`, `//fonts.`, or `url(http`.
- **No credentials**: no `mining_session_token`, `localStorage`, `Bearer`, `/auth/`,
  or API base URL.
- **No storage paths**: no `file_ref` key and no `uploads/` substring.
- **Escaping**: a project named `</script><img src=x onerror=alert(1)>` and a
  `hole_id` of `"><script>` round-trip through `JSON.parse` to their exact original
  values, and the raw document contains no unescaped `</script>` inside the JSON
  island.
- **Sentinel injection**: a project named `<!--MONARK_BUNDLE-->` does not cause the
  bundle or any other sentinel to be substituted twice (guards `contracts/api.md` §3).
- **Budget**: a payload over `MAX_EXPORT_BYTES` raises `ExportTooLargeError` and the
  endpoint surfaces 413; nothing partial is returned.
- **Payload validity**: extract the JSON island from the assembled bytes,
  `json.loads` it, and assert `format_version == 1` plus the presence of every
  top-level key in `contracts/api.md` §2.

---

### T023 — Static-bundle purity test

**Add** to `backend/tests/unit/test_html_export.py` (skipped with a clear reason when
`frontend/dist/export_viewer.js` is absent, so a backend-only checkout still passes):

Read the built bundle and assert it contains none of: `mining_session_token`,
`localStorage`, `/auth/magic-link`, `/workspace/projects`, `share-links`.

This is the automated guard behind FR-006 and the T017 import discipline. A
minified bundle preserves these string literals, so the check is sound.

---

### T024 — Manual verification pass

Execute `quickstart.md` end to end — including the offline `file://` open with
networking disabled in Chrome, Edge, and Firefox, and the DevTools zero-request
check. Record actual results, including anything that failed.

---

### T025 [P] — Documentation

**Modify** `README.md`: a short "Share a project as a standalone HTML file" section —
what the recipient needs (a browser), what they do not (account, internet, install),
and the fact that the file is a dated snapshot.

**Modify** `docs/architecture_baseline.md`: record the `SceneDataSource` seam
(ADR-002) — it changes how every future data-consuming component should be written,
so it belongs in the baseline rather than only in a feature spec.

---

## Dependencies

```
T001 ──┬─> T003
T002 ──┘
T001 ──> T005 ──> T006 ──> T010 ──> [GATE: quickstart §1] ──> T011 ──> T012 ──> T013
T004 ──> T010                                                              │
T007 ──> T006                                                              ├──> T017
T008 ──> T006                                                              │
T009 ──> T010                                                              │
T014 ──> T015 ──> T016 ──────────────────────────────────────────────────> T017 ──> T018
T016 ──> T019, T022, T023
T015 ──> T020, T021
T018 ──> T024 ──> T025
```

## Parallelisable Batches

| Batch | Tasks | Notes |
|---|---|---|
| 1 | T001, T002 | Independent files |
| 2 | T003, T004 | After T001/T002 |
| 3 | T005 → T006; T007, T008, T009 in parallel | T006 needs T007/T008 merged before its wiring is complete |
| 4 | T010 → **GATE** | Sequential; regression gate |
| 5 | T011, T012, T014 | Independent |
| 6 | T013, T015 | Shell and assembly service |
| 7 | T016 → T017 → T018 | Sequential |
| 8 | T019, T020, T021, T022, T023 | Independent test files |
| 9 | T024 → T025 | Manual pass, then docs |

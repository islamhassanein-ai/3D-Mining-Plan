# Implementation Plan: Export Project as Interactive Standalone HTML

**Branch**: `006-standalone-html-export` | **Spec**: [spec.md](spec.md)

**Input**: `spec.md`, `contracts/api.md`, `docs/architecture_baseline.md`, existing
`frontend/src/**` and `backend/src/**` trees from features 003–005.

---

## 1. Technical Context

| Aspect | Value |
|---|---|
| Backend | Python 3.11 / FastAPI, SQLAlchemy 2.0, no new dependencies (`backend/requirements.txt` unchanged — note: **Jinja2 is not installed**, so templating is plain string substitution) |
| Frontend | Vanilla JS + Three.js 0.160 + Delaunator 5, bundled by esbuild 0.19 |
| New build output | `frontend/dist/export_viewer.js` (IIFE, minified) — a **second esbuild entry point**, alongside the existing `dist/bundle.js` |
| Artifact | One `text/html` file, self-contained, opens from `file://` |
| Testing | `pytest` (backend, existing harness); `node --test` (frontend parity check, zero new deps); `quickstart.md` for human-judgment checks |
| Performance target | NFR-002 — inherited from the live renderer, not re-engineered |

---

## 2. Architecture Decisions

### ADR-001 — Reuse the Three.js renderer; do **not** port to Plotly

**Context**: The reference artifact is Plotly-based. The live app is Three.js.

**Decision**: The exported viewer runs **the same** `frontend/src/scene/**` and
`frontend/src/components/**` code as the live app, bundled through a second entry
point.

**Rationale**:
- Every behaviour the reference demonstrates already exists here, in most cases
  better: GPU-shader grade cutoff (`assay_intervals.js:72–99`) vs. the reference's
  per-trace `Plotly.restyle` bucket toggling; Delaunay terrain mesh
  (`topography.js:121`); instanced cylinders; `LodManager`; damped CAD controls.
- A Plotly port would fork the rendering codebase permanently. Every future change
  to grade colouring, desurveying, or section logic would have to be made twice, and
  the two would diverge — the failure mode this repo has explicitly avoided since
  feature 003 (see `specs/005-*/tasks.md` "do not create parallel/duplicate
  implementations").
- The reference is itself unfinished (stubbed `buildDrillTraces()`), so "port it"
  means "rewrite it", at the cost of the features listed above.

**Consequence**: The reference governs *layout, chrome, and interaction inventory*.
`spec.md` FR-011/FR-012 encode that inventory. Nothing from the reference file is
copied verbatim except conventions already adopted (the six-bucket grade scale in
`grade_scale.js` is already noted as "copied verbatim from the Abo Elmagd Hill
reference viewer").

---

### ADR-002 — Introduce a `SceneDataSource` seam (the load-bearing change)

**Context**: Today, data access is hard-wired into rendering and UI code:

| Call site | Dependency |
|---|---|
| `scene_loader.js:26` | `ApiClient.getProjectScene` |
| `scene_loader.js:60` | `ApiClient.getSharedScene` |
| `inspector_panel.js:175,177` | collar details (share / owner) |
| `inspector_panel.js:447,449` | true thickness (share / owner) |
| `topography.js:47` | `fetch('/uploads/{fileRef}')` |
| `wireframes.js:77` | `fetch('/uploads/{file_ref}')` OBJ fallback |

Each is an offline blocker. Patching them with `if (offline)` branches would scatter
export awareness across six files.

**Decision**: Add `frontend/src/services/data_source.js` defining one interface with
three implementations:

```
SceneDataSource
  getScene()                                          -> SceneDTO
  getCollarDetails(collarId)                          -> CollarDetailDTO
  getTrueThickness(collarId, intervalId, dipDir, dip) -> TrueThicknessDTO
  getTopographyPoints(topographyRef)                  -> [{e,n,el}] | null
  getWireframeGeometry(wireframe)                     -> {vertices,indices} | null

  ApiDataSource         — live owner session (wraps ApiClient)
  ShareTokenDataSource  — read-only token session (wraps ApiClient share routes)
  StaticDataSource      — embedded snapshot; pure, synchronous under the hood,
                          async-shaped for interface parity; never touches the
                          network, localStorage, or the DOM's origin
```

**Rationale**: One seam, three implementations, zero export-specific branching in
renderer or component code. It also cleans up the existing share/owner duplication —
`SceneLoader.loadProject` and `loadSharedProject` (`scene_loader.js:21–87`) are
byte-for-byte identical apart from one line, and collapse into one path.

**Consequence**: `SceneLoader`, `InspectorPanel`, `TopographyRenderer`, and
`WireframesRenderer` take a data source (or a geometry-resolver callback) instead of
importing `ApiClient`. `index.html` changes only where it constructs them.

---

### ADR-003 — Assemble server-side from the existing endpoint functions

**Decision**: `build_standalone_html()` calls `get_project_scene(...)` and
`get_collar_details(...)` **as Python functions**, exactly as `share_links.py:130,150`
already does with `current_user=None`.

**Rationale**: The export is by definition "what the app would have shown". Any
second serialisation path would drift from desurveying (`desurvey.py`), grade
colouring (`grade_coloring.py`), and supersession filtering. This pattern is already
established and tested in this codebase.

**Consequence**: The export inherits every scene-endpoint fix for free, and the
payload schema is a superset of the wire format the frontend already parses — so
`StaticDataSource` needs no translation layer.

---

### ADR-004 — IIFE bundle, inline everything, no ES modules

**Decision**: `esbuild --format=iife --bundle --minify`; the bundle, the shell HTML,
the CSS, and the JSON payload are all inlined into one document. No `type="module"`,
no Web Workers, no `importmap`, no web fonts.

**Rationale**: `file://` enforces an opaque origin. ES modules, Workers, and any
`fetch` (including of a same-directory file) fail there. The reference file's
`<link href="https://fonts.googleapis.com/...">` (its lines 7–8) is exactly the kind
of dependency that breaks the offline guarantee and must **not** be reproduced — the
live app already relies on the local-font stack `'Inter', system-ui, -apple-system,
sans-serif`, which needs nothing.

**Consequence**: Label rendering stays canvas-based (`label_sprite.js` — already
canvas + `THREE.CanvasTexture`, so it is `file://`-safe as written).

---

### ADR-005 — Raw JSON payload in v1; compression only on evidence

**Decision**: Embed the payload as raw JSON inside
`<script type="application/json" id="monark-scene-data">`. Do **not** gzip+base64 it
in v1.

**Rationale**: Bounding the only unbounded input (topography, via ADR-006
decimation) keeps realistic projects inside NFR-003 without a second encoding path.
A `DecompressionStream('gzip')` path adds a browser-support fork (Safari < 16.4),
an async bootstrap, and an opaque payload that cannot be diffed or inspected during
support triage.

**Trigger to revisit**: real projects breaching NFR-003 (15 MB). At that point add
gzip+base64 behind the same endpoint, keyed off measured payload size, with the raw
path retained as fallback.

---

### ADR-006 — Grid-bin decimation for topography

**Decision**: When topography exceeds `MAX_TOPO_POINTS` (60 000), overlay a uniform
grid over the E/N extent sized to yield ≈ the cap in occupied cells, and keep, per
occupied cell, the sample nearest that cell's centre.

**Rationale**: The points feed a Delaunay triangulation (`topography.js:121`).
Random or head-of-file sampling produces clustered coverage and sliver triangles,
visibly corrupting the surface. Grid-binning preserves spatial coverage and the
convex hull, which is what the mesh's readability depends on.

**Consequence**: The reduction is disclosed in the footer (FR-015) so a recipient
never silently reads a decimated surface as the surveyed one.

---

### ADR-007 — Client-side true thickness, fixture-locked to the server

**Decision**: Port `collars.py:172–249` (survey interpolation at mid-depth +
apparent×|cos θ|) to `frontend/src/services/true_thickness.js`. Lock the two
implementations together with a shared fixture,
`specs/006-standalone-html-export/fixtures/true_thickness_vectors.json`, asserted by
both a `pytest` case and a `node --test` case.

**Rationale**: This is the one server computation the exported viewer genuinely
needs at interaction time (it depends on user-entered vein orientation, so it cannot
be precomputed). It is pure, ~40 lines, and deterministic. The real risk is not the
port — it is silent divergence later; the shared fixture is what actually manages
that.

**Rejected alternative**: precomputing a lookup table over dip/dip-direction. Wrong
shape (continuous 2-D input space) and would bloat the payload per interval.

---

## 3. Component & File Map

### New files

```
frontend/
  styles/
    app.css                        # extracted from index.html <style> (ADR: single CSS source)
  src/
    export/
      viewer_main.js               # IIFE entry: bootstrap the static viewer
      shell.html                   # static export DOM shell (no owner controls)
    services/
      data_source.js               # ApiDataSource | ShareTokenDataSource | StaticDataSource
      true_thickness.js            # JS port of collars.py:172-249
      project_summary.js           # extracted from index.html:1252 updateDdAndTrenchSummary
  tests/
    true_thickness_parity.test.mjs # node --test, zero deps

backend/src/services/
  html_export.py                   # assembly + escaping + budget enforcement (pure, DB-free)
  obj_geometry.py                  # server-side OBJ -> vertices/faces (mirrors wireframes.js:3-40)

backend/tests/unit/
  test_html_export.py
  test_true_thickness_vectors.py

specs/006-standalone-html-export/
  fixtures/true_thickness_vectors.json
```

### Modified files

| File | Change | Risk |
|---|---|---|
| `frontend/package.json` | `build` runs app + export bundles; add `build:export` | Low |
| `frontend/index.html` | move `<style>` → `styles/app.css`; construct data sources | **Medium — visual regression risk; see §7 R5** |
| `frontend/src/scene/scene_loader.js` | split fetch from render; take a data source | Medium |
| `frontend/src/scene/topography.js` | split `loadAndRender` into fetch + `renderPoints(points)` | Low |
| `frontend/src/scene/wireframes.js` | accept a geometry-resolver callback instead of inline `fetch` | Low |
| `frontend/src/components/inspector_panel.js` | take a data source; drop direct `ApiClient` import | Medium |
| `frontend/src/components/export_panel.js` | add the HTML export row; generalise filename/extension handling | Low |
| `backend/src/api/export.py` | add `GET .../export/standalone.html` | Low |
| `run.ps1` | unchanged if `npm run build` fans out (preferred) | Low |

---

## 4. Data Flow

### Export (server)

```
GET /projects/{id}/export/standalone.html   [owner auth]
  │
  ├─ get_owned_project_or_404(...)                        # existing guard
  ├─ get_project_scene(id, db, current_user=None)         # ADR-003 — same DTO as live
  ├─ for each collar: get_collar_details(...)             # ADR-003
  ├─ topography: read uploads/{topography_ref}
  │     └─ parse CSV -> points -> grid-decimate if > MAX_TOPO_POINTS   # ADR-006
  ├─ wireframes: ensure vertices/faces present
  │     └─ if only file_ref: parse OBJ via obj_geometry.py; else omit + record reason
  ├─ strip file_ref / storage paths from the payload
  ├─ assemble MONARK_EXPORT dict  (contracts/api.md)
  ├─ json.dumps -> escape < > & U+2028 U+2029                          # FR-007
  ├─ read frontend/dist/export_viewer.js   -> 503 if missing           # FR-009
  ├─ read frontend/src/export/shell.html + frontend/styles/app.css
  ├─ substitute sentinels; enforce MAX_EXPORT_BYTES                    # FR-018
  └─ StreamingResponse(text/html, Content-Disposition: attachment)     # FR-008
```

### Boot (exported file, offline)

```
DOMContentLoaded
  └─ viewer_main.js
       ├─ JSON.parse(#monark-scene-data.textContent)
       ├─ new StaticDataSource(payload)
       ├─ init3DViewport('viewport-3d', { onSelect })          # unchanged scene.js
       ├─ sceneLoader.load(dataSource)                         # renders from memory
       ├─ SceneToolbar, LayerTogglePanel, CutoffSlider, GradeHistogram,
       │  SectionViewPanel, MeasurementTool, InspectorPanel(dataSource),
       │  hover.setData, lodManager.setDrillholes, coordinate flag, topo mode
       ├─ project_summary.js -> header stats                   # shared with live app
       └─ provenance chip + footer from payload.generator
```

---

## 5. Refactor Details (exact shapes for the executor)

**`SceneLoader`** — keep `loadProject(projectId)` / `loadSharedProject(token)` as
thin wrappers so `index.html` behaviour is unchanged; extract the identical bodies of
`scene_loader.js:28–45` and `62–79` into one `renderScene(data)`; add
`async load(dataSource)` = `renderScene(await dataSource.getScene())`, plus
topography and wireframe resolution routed through the same data source.

**`TopographyRenderer`** — `loadAndRender(fileRef)` keeps its signature and becomes
`fetch → parse → renderPoints(points)`. `renderCSVPoints` keeps parsing; the new
`renderPoints(points)` takes the already-parsed `[{e,n,el}]` and runs
`_buildPointCloud` / `_buildTriangulatedMesh` / `_applyDisplayMode` / bounds helper
(`topography.js:89–98`) unchanged. `StaticDataSource` supplies the array directly.

**`WireframesRenderer.render(wireframes)`** — already prefers inline
`w.vertices`/`w.faces` (`wireframes.js:63–74`). Replace the `fetch` fallback
(`:77`) with an injected `this.resolveGeometry(w)` callback; `ApiDataSource` supplies
today's fetch+`parseOBJ`, `StaticDataSource` returns `null` (skip + `console.warn`).
Server-side resolution (FR-005) means the null branch should never fire in practice.

**`InspectorPanel`** — replace the `shareToken` option with `dataSource`
(`inspector_panel.js:11,174–178,446–450`). `getTrueThickness` on `StaticDataSource`
delegates to `true_thickness.js` using the collar's embedded surveys.

**CSS extraction** — move `index.html:7–615` verbatim into `frontend/styles/app.css`;
`index.html` gains `<link rel="stylesheet" href="styles/app.css">`; the export
inlines the same file inside `<style>`. Verbatim move, no reformatting, so the diff
is reviewable and §7 R5 is testable.

---

## 6. Security Model

| Concern | Control |
|---|---|
| Markup/script injection from user strings (project name, `hole_id`, `lith_code`, wireframe `name`) | JSON-serialise, then escape `<` `>` `&` U+2028 U+2029 to `\uXXXX`. These never occur structurally in JSON, so escaping is lossless and `JSON.parse` restores them. Never string-interpolate user values into HTML — the shell reads them from the payload at runtime and assigns via `textContent`. |
| Credential leakage into a redistributable file | `viewer_main.js` must not (transitively) import `api_client.js`. Enforced by a test that greps the built bundle **and** the assembled HTML for `mining_session_token`, `localStorage`, `/auth/`, `Bearer`. |
| Accidental network egress | Inline CSP `default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; connect-src 'none'; base-uri 'none'; form-action 'none'`. `connect-src 'none'` makes NFR-001 enforced, not aspirational. WebGL, canvas textures, and `CanvasTexture` need no `connect-src`. |
| Storage-path disclosure | `file_ref` and any `uploads/` path are stripped from the payload before embedding. |
| Author PII in a forwarded file | `include_author` query param (default `true`); when false, `generator.exported_by` is `null` (FR-003 of US3). |
| Authorisation | Owner-only, via the existing `get_owned_project_or_404`; no share-token export in v1. |

---

## 7. Risks & Mitigations

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | ES-module or Worker output breaks `file://` | Feature dead on arrival | `--format=iife`; quickstart opens from `file://`, not `http://localhost` |
| R2 | CSP blocks something needed (canvas textures, blob URLs) | Blank viewport | Verify in quickstart across all three browsers with the CSP active from the first build, not bolted on last |
| R3 | Stale `dist/export_viewer.js` (someone forgot `npm run build`) | Exported file silently ships an old viewer | Fold the export bundle into the default `build` script; 503 when absent (FR-009); embed the bundle's build timestamp in `generator` |
| R4 | JS/Python true-thickness drift | Wrong geology numbers in a client deliverable | Shared fixture, asserted from both languages (ADR-007) |
| R5 | CSS extraction regresses the live app's layout | Visible breakage in the shipped app | Verbatim move (no edits in the same commit); before/after screenshots of the live app at 1280×800 and 1600×900 in `quickstart.md` §1 |
| R6 | Payload size on dense topography | Unusable file / browser hang | Grid decimation (ADR-006) + 413 above 60 MB + footer disclosure |
| R7 | Delaunator over 60 000 points at boot | Slow first frame | Measured in quickstart §4 against NFR-002; if breached, lower `MAX_TOPO_POINTS` — do **not** move triangulation server-side (no Delaunay lib in `requirements.txt`; adding one is a bigger cost than a lower cap) |
| R8 | Recipient mistakes a snapshot for live data | Professional/reporting hazard | FR-015 provenance chip + footer; verified in quickstart §2 |
| R9 | `getGradeBucketIndex` / colours drift from `grade_coloring.py` | Legend disagrees with geometry | Pre-existing risk, unchanged: colours arrive precomputed from the server in the payload; the client bucket function is used only for radius/histogram |

---

## 8. Execution Order

1. **Foundational seam** — `data_source.js`, `true_thickness.js`, `project_summary.js`,
   plus the renderer/component refactors. The live app must still pass `quickstart.md`
   §1 with **no behaviour change** before anything export-specific is written.
2. **Build pipeline** — second esbuild entry, `package.json` scripts.
3. **Viewer shell + bootstrap** — `shell.html`, `viewer_main.js`, CSS extraction.
4. **Backend assembly** — `obj_geometry.py`, `html_export.py`, the endpoint.
5. **UI wiring** — `export_panel.js` row.
6. **Tests & verification** — parity fixture, `test_html_export.py`, quickstart pass.

Step 1 is deliberately a no-op refactor: it is the only step that touches shipped
behaviour, so it is isolated, reviewable, and verifiable on its own.

Task-level detail: [tasks.md](tasks.md). Contract detail: [contracts/api.md](contracts/api.md).

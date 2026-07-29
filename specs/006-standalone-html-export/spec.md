# Feature Specification: Export Project as Interactive Standalone HTML

**Feature Branch**: `006-standalone-html-export`

**Created**: 2026-07-28

**Status**: Draft — ready for implementation

**Input**: "Implement an 'Export Project as Interactive Standalone HTML' feature.
Reference behaviour/visual target: `Example to share the project as html/Abo_Elmagd_Hill_3D_Design_Pro (2).html`."

**Reference artifact status**: The supplied reference file is a *behavioural
prototype*, not an implementation to copy. Its Plotly library and geological data
blocks are elided (see its lines 378–381, 388–392, 1125–1130 — `buildDrillTraces()`
etc. are empty stubs). It is authoritative for **what the exported file must do and
look like**; it is **not** authoritative for **how** (see `plan.md` → ADR-001, which
rejects the Plotly path in favour of reusing this repo's existing Three.js renderer).

---

## Problem Statement

Today a project can only be shared two ways:

| Mechanism | Where | Limitation |
|---|---|---|
| Share link (`?share=<token>`) | `share_links.py`, `index.html:863` | Requires the server to be running and reachable; expires after 7 days; recipient needs a live URL. |
| File exports (CSV / PDF / DXF) | `export.py` | Not interactive — a PDF section sheet is a flat picture, a CSV is not a model. |

A geologist needs to hand a **client, investor, JORC reviewer, or field colleague** a
single file — over email, USB stick, or a shared drive — that opens in any browser
with **no server, no login, no internet**, and still lets the recipient orbit the
model, filter by grade, slice a section, and click a hole to read its log.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Hand off a self-contained interactive model (Priority: P1)

As the project owner, I want to export the active project as one `.html` file, so
that I can email it to a colleague who will open it by double-clicking, with no
software to install and no account to create.

**Why this priority**: This is the entire feature. Everything else is refinement of
it.

**Independent Test**: Export a project, copy the file to a machine with networking
disabled, open it from the filesystem (`file://`), and confirm the 3D scene renders
and orbits.

**Acceptance Scenarios**:

1. **Given** a project with drillholes, **When** the owner clicks *Export Project
   Data → Interactive 3D Viewer (HTML) → Download*, **Then** a single `.html` file
   downloads with no sidecar files, folders, or `.zip` wrapper.
2. **Given** the downloaded file, **When** it is opened from `file://` with the
   network disconnected, **Then** the 3D scene renders and the browser DevTools
   Network panel records **zero** outbound requests.
3. **Given** the downloaded file, **When** it is opened in current Chrome, Edge,
   and Firefox, **Then** it behaves identically in all three.

---

### User Story 2 — Interrogate the model without the app (Priority: P1)

As the recipient, I want the same core interactions the live app gives me, so the
file is a working model and not a screenshot.

**Why this priority**: A static picture is already covered by the existing PDF
export. Interactivity is the value.

**Independent Test**: With the exported file open offline, exercise each interaction
in the in-scope table below and confirm behaviour matches the live app for the same
project.

**Acceptance Scenarios**:

1. **Given** the exported viewer, **When** the recipient drags / scrolls /
   right-drags, **Then** the camera orbits / zooms / pans exactly as in the live app
   (same `DampedCameraControls`).
2. **Given** the exported viewer, **When** the recipient moves the Au grade cutoff
   slider, **Then** intervals below cutoff disappear in the same frame and the grade
   histogram updates, at any project size.
3. **Given** the exported viewer, **When** the recipient clicks a drillhole trace or
   assay interval, **Then** the right-hand inspector shows that hole's collar,
   surveys, assay and lithology logs, and merged interval timeline.
4. **Given** a selected assay interval, **When** the recipient enters a vein dip
   direction and dip, **Then** a true thickness is computed and displayed **without
   any network call**, agreeing with the server's answer to within 1e-6 m.
5. **Given** the exported viewer, **When** the recipient opens the 2D cross-section
   panel and drags the slicing plane, **Then** the section updates live, as in the
   live app.
6. **Given** the exported viewer, **When** the recipient presses `P` / `N` / `E` /
   `I` / `?`, **Then** the camera presets and the shortcut help overlay respond as in
   the live app.

---

### User Story 3 — Trust what the file says (Priority: P1)

As the recipient — and as the owner who will be held to this file in a technical
report — I want the export to state plainly what it is and when it was made, so a
month-old snapshot is never mistaken for the live project.

**Why this priority**: In a mining-reporting context an undated, unattributed model
that *looks* live is a professional hazard, not a nice-to-have.

**Independent Test**: Open the exported file and read the header chip and footer
without touching any control.

**Acceptance Scenarios**:

1. **Given** the exported viewer, **When** it opens, **Then** the header shows a
   persistent `STATIC EXPORT` chip and the footer shows project name, UTM zone,
   export timestamp (UTC, ISO 8601), and record counts.
2. **Given** the exported viewer, **When** the recipient looks for edit controls,
   **Then** no import, upload, share, delete, project-switch, history, or
   server-export control exists anywhere in the UI.
3. **Given** an export produced with `include_author=false`, **When** the file is
   inspected, **Then** no user email address appears anywhere in it.

---

### User Story 4 — Export large projects predictably (Priority: P2)

As the owner of a project with a dense topography survey, I want the export to
either succeed at a sane file size or fail with a clear, actionable message.

**Why this priority**: Topography point clouds are the only unbounded input; a
silent 300 MB HTML file that hangs the recipient's browser is worse than a refusal.

**Independent Test**: Export a project whose topography CSV exceeds the decimation
cap, and one that exceeds the hard size cap.

**Acceptance Scenarios**:

1. **Given** a topography survey above `MAX_TOPO_POINTS`, **When** exported, **Then**
   the points are grid-decimated, the surface still reads correctly, and the footer
   discloses `topography decimated: N of M points`.
2. **Given** an assembled payload above `MAX_EXPORT_BYTES`, **When** exported,
   **Then** the request fails with HTTP 413 and a message naming the dominant
   contributor and the remedy, and **no** partial file is downloaded.

---

## Requirements *(mandatory)*

### Functional Requirements

**Export production**

- **FR-001**: The system MUST expose `GET /projects/{project_id}/export/standalone.html`,
  restricted to the project owner via the existing `get_owned_project_or_404` guard.
- **FR-002**: The response MUST be a single, self-contained `text/html` document —
  no external scripts, stylesheets, fonts, images, or data files, and no
  same-document reference to any URL scheme other than `data:`.
- **FR-003**: The exported document MUST embed the project's full scene snapshot,
  produced by reusing `backend/src/api/scene.py::get_project_scene` — the export
  MUST NOT re-derive drillhole desurveying, grade colouring, or interval positions
  through a second code path.
- **FR-004**: The exported document MUST embed per-collar detail records equivalent
  to `GET /collars/{collar_id}` for every non-superseded collar in the project,
  produced by reusing `backend/src/api/collars.py::get_collar_details`.
- **FR-005**: The exported document MUST embed topography as parsed point data.
  Wireframe solids MUST be embedded as resolved `vertices`/`faces` arrays; any
  wireframe that would have required a runtime file fetch (`wireframes.js:77`) MUST
  be resolved server-side at export time or omitted with a recorded reason.
- **FR-006**: The exported document MUST NOT contain any session token, share
  token, `localStorage` access, `fetch(` to an application origin, or API base URL.
- **FR-007**: All embedded user-controlled strings (project name, `hole_id`,
  `trench_id`, `lith_code`, wireframe `name`, commodity, UTM zone) MUST be escaped
  such that no value can terminate the embedding `<script>` element or inject
  markup.
- **FR-008**: The response MUST set `Content-Disposition: attachment` with a
  filename of the form `{project_slug}_3D_Viewer_{YYYYMMDD}.html`, using RFC 5987
  `filename*` when the project name is non-ASCII.
- **FR-009**: When the required built viewer bundle is absent from disk, the
  endpoint MUST fail with HTTP 503 and a message naming the exact build command to
  run — it MUST NOT emit a broken HTML file.
- **FR-010**: `frontend/src/components/export_panel.js` MUST offer the HTML export
  as a fourth option alongside CSV / PDF / DXF, reusing the existing download
  plumbing and status-banner behaviour.

**Exported viewer behaviour**

- **FR-011**: The exported viewer MUST render, from embedded data alone: drillhole
  traces, assay intervals, lithology intervals, topography (mesh **and** point-cloud
  modes), trenches, vein wireframes, structural readings, and borehole/trench labels.
- **FR-012**: The exported viewer MUST support: orbit/pan/zoom, camera presets +
  reset, keyboard shortcuts (`P`/`N`/`E`/`I`/`?`/`Esc`), the orientation gizmo, layer
  toggles, the GPU grade-cutoff slider, the grade histogram, hover highlight +
  tooltip, click-to-inspect, the 2D cross-section panel with its slicing plane, the
  3D ruler, go-to-coordinate with the coordinate flag, LOD, panel collapse, the
  viewport hint card, and the shortcut help overlay.
- **FR-013**: The exported viewer MUST compute true thickness client-side, using a
  JavaScript port of the algorithm in `backend/src/api/collars.py:172–249`, held to
  numerical parity with the Python implementation by a shared fixture.
- **FR-014**: The exported viewer MUST NOT present any control that mutates project
  state or contacts a server (import, supplementary upload, structural editing,
  QA/QC editing, share links, history, project create/delete/switch, CSV/PDF/DXF
  export, UTM zone editing).
- **FR-015**: The exported viewer MUST display provenance: a `STATIC EXPORT` header
  chip and a footer carrying project name, UTM zone, export timestamp (UTC),
  exporter identity (unless suppressed), record counts, and any decimation notice.
- **FR-016**: The exported viewer MUST reuse the live app's renderer, component, and
  styling source — not a parallel re-implementation. Any behaviour divergence
  between the live app and the exported viewer, other than the deliberate omissions
  in FR-014, is a defect.

**Scale & limits**

- **FR-017**: Topography points exceeding `MAX_TOPO_POINTS` (60 000) MUST be reduced
  by uniform grid-bin decimation — retaining, per occupied cell, the sample nearest
  the cell centre — never by random or head-of-file sampling.
- **FR-018**: An assembled document exceeding `MAX_EXPORT_BYTES` (60 MB) MUST be
  rejected with HTTP 413 rather than returned.

### Key Entities

No new database entities. The feature introduces one **transport artifact**, the
embedded export payload (`MONARK_EXPORT`, `format_version: 1`), specified in
`contracts/api.md`.

### Non-Functional Requirements

- **NFR-001 (Offline)**: Opening the file from `file://` with networking disabled
  produces a fully working viewer and zero network requests.
- **NFR-002 (Performance)**: On a mid-range 2023 laptop, a project of 50 holes /
  5 000 assay intervals / 60 000 topography points reaches first rendered frame in
  ≤ 3 s and sustains ≥ 30 fps while orbiting; the grade cutoff slider remains
  same-frame at any interval count (it drives a shader uniform — `assay_intervals.js:170`).
- **NFR-003 (Size)**: A typical project (≤ 30 holes, ≤ 3 000 intervals, ≤ 20 000
  topography points) produces a file ≤ 15 MB.
- **NFR-004 (Compatibility)**: Current Chrome, Edge, Firefox, and Safari 16.4+, on
  desktop, from both `file://` and `https://`.
- **NFR-005 (Maintainability)**: Adding a rendering feature to the live app requires
  no export-specific work beyond wiring it in the viewer bootstrap; the renderer,
  components, grade scale, and CSS have exactly one source of truth each.
- **NFR-006 (Security)**: The artifact carries a restrictive inline CSP including
  `connect-src 'none'`, making the offline guarantee enforced rather than merely
  intended.

---

## Success Criteria *(mandatory)*

- **SC-001**: A geologist exports a project and a recipient with no account, no
  install, and no internet interrogates the model — orbit, cutoff, section, hole log
  — in under 60 seconds from receiving the file.
- **SC-002**: For an identical project, every in-scope interaction produces visually
  and numerically identical results in the exported viewer and the live app.
- **SC-003**: Automated tests fail the build if the exported document gains an
  external reference, a credential-shaped string, or an unescaped user string.
- **SC-004**: The exported file's own footer is sufficient to answer "what project,
  which coordinate system, as of when, exported by whom" with no other artifact.

---

## Out of Scope (v1)

Deferred deliberately; each is a candidate follow-up, not an oversight:

| Item | Reason |
|---|---|
| Export from a share-token session (`/share/{token}/export/...`) | Owner-only in v1; a read-only viewer minting further redistributable artifacts is a policy decision, not a technical one. |
| gzip + `DecompressionStream` payload compression | Decimation plus the size budget covers the realistic range; adding a second encoding path before it is measurably needed doubles the failure surface. Trigger to build it: NFR-003 breached by real projects. See `plan.md` → ADR-005. |
| Password protection / expiry inside the file | Client-side "protection" on a file the recipient holds is theatre; real access control stays with share links. |
| Editing, annotating, or re-importing from the exported file | The artifact is a read-only snapshot by design (FR-014). |
| Print / PDF layout inside the exported viewer | The existing `section.pdf` export covers paper output. |
| Mobile-optimised layout | Desktop is the stated target (NFR-004); the layout degrades acceptably but is not tuned. |

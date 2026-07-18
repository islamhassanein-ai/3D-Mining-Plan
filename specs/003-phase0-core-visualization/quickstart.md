# Quickstart Validation: Phase 0 Core Visualization & Modeling

Prerequisites: backend running against a PostgreSQL 16 + PostGIS database with
migrations applied; frontend served and pointed at the backend; a small set of real
(not synthetic) Collar/Survey/Assay/Lithology CSVs to import (per the kill criterion,
SC-002 — synthetic clean data does not validate this feature).

## Setup

1. Run backend Alembic migrations against a fresh database.
2. Start the backend API server.
3. Start the frontend (static files or dev server) pointed at the backend.
4. Request a magic-link for a test account and complete sign-in (`/auth/magic-link`
   → `/auth/verify`).

## Scenario 1 — Import with validation (US1, FR-001–FR-009, SC-001, SC-002, SC-005)

1. Create a Project.
2. Upload the four CSVs via `POST /projects/{id}/imports`.
3. Confirm the response includes a raw-vs-interpreted diff for every row, the
   auto-detected UTM zone, and explicit flags for any BDL values, overlapping/gap
   intervals, mixed units, or orphan `hole_id` references present in the test data.
4. Confirm no flagged value was silently altered — compare flagged rows' values
   against the source CSV byte-for-byte.
5. Confirm the detected UTM zone requires explicit confirmation before commit.
6. Commit the batch. Confirm `import_batch.status` becomes `committed` and the
   elapsed time from file selection to commit is under 60 seconds (SC-001) and under
   30 seconds of that is import processing (per `docs/architecture_baseline.md` § 4).

**Expected outcome**: A committed project with zero silently-altered values, and an
import experience requiring no more manual correction than the prior ad-hoc workflow
did (SC-002 — this is a human judgment call, not a mechanical check; record the
result honestly).

## Scenario 2 — 3D scene renders and navigates like CAD software (US2, FR-010–FR-014, SC-003)

1. Load the committed project's scene (`GET /projects/{id}/scene`).
2. Confirm every drillhole trace renders using minimum-curvature-computed positions
   (spot-check one hole's trace against a hand-computed or reference position).
3. Confirm assay intervals are colored by grade value.
4. Orbit, pan, and zoom the scene. Confirm damped motion and orbit-around-cursor
   behavior (not orbit-around-origin).
5. Trigger each camera preset (plan, section, isometric) via toolbar and keyboard
   shortcut.
6. With a scene containing at least several hundred assay intervals (ideally
   approaching 5,000), confirm no perceptible stutter during orbit/pan/zoom (SC-003).
7. Confirm an orientation gizmo is visible and updates with camera movement (US8).

## Scenario 3 — Drillhole inspection (US3, FR-016, SC-004)

1. Click a rendered drillhole.
2. Confirm the card shows collar coordinates, survey dip/azimuth, and the full
   assay and lithology interval table, with every field from `data-model.md` present
   (SC-004 — zero missing fields).

## Scenario 4 — Grade cutoff, slicing, measurement (US4–US6, FR-017–FR-020)

1. Move the grade-cutoff slider; confirm the scene updates without a page reload.
2. Place and move a slicing plane; confirm the synced 2D section view updates
   without lag.
3. Click two points; confirm a 3D distance measurement is displayed.
4. Select an assay interval with known dip; confirm true thickness is computed and
   visibly distinguished from downhole length.
5. Select an interval on a hole with missing dip data; confirm the true-thickness
   result is shown as unavailable, not a fabricated number.

## Scenario 5 — Supplementary data and resilience (US7, FR-021–FR-024)

1. Register a topography surface, trench data, and a wireframe file for the project;
   confirm all three render alongside the drillholes in the scene.
2. Upload a deliberately corrupt wireframe file; confirm it produces a per-file error
   without breaking the rest of the scene.
3. Load a brand-new project with no committed imports; confirm a clear empty state
   appears, not a blank or broken screen (FR-015).
4. Load a project, then simulate a brief connectivity drop; confirm the last-loaded
   project remains visible from client-side cache (FR-024).

## Scenario 6 — First-impression interaction check (SC-006)

Have someone unfamiliar with the tool use it for 5 minutes without guidance. Confirm
they can find and use all six signature patterns: smooth damped camera, instant
drillhole card, real-time grade-cutoff, synced section view, one-flow import, and
camera presets. Record the result honestly — do not mark this passed without an
actual person doing it.

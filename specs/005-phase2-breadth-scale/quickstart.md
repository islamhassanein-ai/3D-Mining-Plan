# Quickstart Validation: Phase 2 Breadth & Scale

Prerequisites: features 003 and 004's backend/frontend running, with a committed
project available. Have a real (not synthetic) DXF wireframe file and a real
Shapefile (trench or topography) on hand where possible, consistent with this
project's kill-criterion discipline of testing against real messy data.

## Scenario 1 — DXF wireframe import (US1, FR-001, FR-002, SC-001)

1. Import a DXF wireframe via `POST /projects/{id}/wireframes`. Confirm the response
   includes parsed geometry (vertex/face counts), not just a file reference.
2. Load the project's scene. Confirm the wireframe renders using the parsed
   geometry — visually compare against opening the same DXF file in any DXF viewer.
3. Attempt to import a deliberately corrupted DXF file. Confirm a clear per-file
   error is returned and the rest of the project's data is unaffected.

## Scenario 2 — Shapefile import (US2, FR-003, FR-004, SC-002)

1. Import a trench Shapefile via `POST /projects/{id}/trenches/shapefile`. Confirm
   the resulting Trench rows match the Shapefile's attribute data.
2. Import a topography Shapefile. Confirm it renders in the scene.
3. Import a Shapefile with an ambiguous/missing CRS. Confirm it is flagged for
   confirmation rather than silently assumed.

## Scenario 3 — Export (US3, FR-005–FR-007, SC-003)

1. Export a project's wireframes to DXF (`GET .../export/wireframes.dxf`). Open the
   file in a DXF viewer and confirm the geometry matches the scene.
2. Set a section-view slice in the frontend, then export it to PDF
   (`GET .../export/section.pdf`). Confirm the PDF matches what was on screen.
3. Export drillhole data to CSV (`GET .../export/data.csv?entity=collars`, etc.).
   Confirm the exported file could be re-imported through the Phase 0 import path
   without schema errors.

## Scenario 4 — Structural data (US4, FR-008, FR-009)

1. Create a structural reading (fault trace or dip/strike) via
   `POST /projects/{id}/structural-readings`.
2. Load the scene. Confirm the reading renders alongside drillhole data.

## Scenario 5 — RQD/core recovery (US5, FR-010, FR-011, SC-004)

1. Import a Lithology CSV including `rqd_percent`/`core_recovery_percent` values,
   including one row with a value outside 0-100. Confirm that row is rejected as a
   blocking error (not a warning).
2. Import valid RQD/core-recovery values. Confirm they appear in
   `GET /collars/{id}`'s interval table.

## Scenario 6 — QA/QC (US6, FR-012, FR-013, SC-005)

1. Configure a QA/QC Standard Reference via `POST /projects/{id}/qaqc-standards`.
2. Import an assay CSV including duplicate/standard/blank sample indicators.
   Confirm each is flagged with the correct `qaqc_flag` value.
3. Include a standard sample whose value falls outside its configured range.
   Confirm it's flagged as a warning (not blocking) and requires the same
   `acknowledge_warnings` gate as any other warning before commit (feature 003).
4. Include a standard sample referencing a `standard_name` with no configured QA/QC
   Standard Reference. Confirm it's flagged `unconfigured`, not silently skipped.

## Scenario 7 — Scale / LOD (US7, FR-014, SC-006)

1. Load a project with well beyond 20,000 combined assay/lithology intervals (or a
   synthetic stress-test project, if no real one exists at this scale yet).
2. Confirm the scene remains smoothly interactive during orbit/pan/zoom.
3. Click-to-inspect a drillhole that is currently rendered at reduced detail
   (distant from camera). Confirm the inspector card still shows full, accurate
   data — LOD must never be visible in inspection results, only in rendering.
4. Export the same project's data (Scenario 3). Confirm the export is complete,
   with no intervals silently dropped due to LOD.

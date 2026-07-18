# Feature Specification: Phase 2 — Breadth & Scale

**Feature Branch**: `005-phase2-breadth-scale`

**Created**: 2026-07-18

**Status**: Draft

**Input**: User description: "Please read the master plan in `mining_tool_planning_Final_claude4-7-2026.md` and the approved baseline document in `docs/architecture_baseline.md`. We want to run the full `spec-kit` workflow to specify, plan, and generate tasks for the remaining execution phases described in the master plan: Section 5: PHASE 2 — BREADTH & SCALE."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import a DXF wireframe with real geometry validation (Priority: P1)

As the geologist, I want to import a DXF wireframe/vein solid file and have its
geometry actually parsed and validated, so I can trust the solid I see in the 3D
scene matches the file I uploaded rather than being an opaque, unverified reference.

**Why this priority**: Master plan §3 already lets a wireframe file be referenced in
Phase 0, but without real parsing; this closes that gap and is the more commonly
needed of the two new import formats for a solo prospect workflow.

**Independent Test**: Given a valid DXF file, it can be imported and its parsed
geometry verified against the rendered scene, independent of Shapefile import,
export, or any other Phase 2 capability.

**Acceptance Scenarios**:

1. **Given** a valid DXF wireframe file, **When** imported, **Then** its
   vertices/faces are parsed and the solid renders in the 3D scene using that parsed
   geometry, not a placeholder.
2. **Given** a corrupt or unsupported DXF file, **When** imported, **Then** a clear
   per-file error is shown and the rest of the project's data is unaffected,
   consistent with the wireframe error-handling behavior already established in
   Phase 0.

---

### User Story 2 - Import Shapefiles for trenches and topography (Priority: P1)

As the geologist, I want to import trench sample points and a topography surface
from Shapefiles, so I can bring in survey data from other GIS tools without manually
converting it to CSV first.

**Why this priority**: Explicitly named in master plan §5 alongside DXF import as
the two headline "additional import formats" for this phase.

**Independent Test**: Given a valid Shapefile, trench or topography data can be
imported and verified in the scene, independent of DXF import or export features.

**Acceptance Scenarios**:

1. **Given** a valid Shapefile containing trench sample points, **When** imported,
   **Then** trench records are created with the same validation rigor as the Phase 0
   CSV import path (UTM zone confirmation, explicit grade units).
2. **Given** a valid Shapefile containing a topography surface, **When** imported,
   **Then** the topography renders in the 3D scene.
3. **Given** a Shapefile with an ambiguous or missing coordinate reference, **When**
   imported, **Then** it is flagged for explicit user confirmation, never silently
   assumed.

---

### User Story 3 - Export project data for use in other tools (Priority: P1)

As the geologist, I want to export a project's wireframes to DXF, a section view to
PDF, and drillhole/assay data to CSV, so I can share deliverables with colleagues or
load them into other mining software without being locked into this tool.

**Why this priority**: Master plan §5 names exports alongside imports as the core
"breadth" this phase delivers; without an export path, data can only ever flow in,
which limits the tool's usefulness once real work depends on it.

**Independent Test**: Given a committed project, each export type (DXF, PDF, CSV) can
be produced and verified independently of the others and of any import feature.

**Acceptance Scenarios**:

1. **Given** a project with wireframes, **When** exported to DXF, **Then** the
   exported file's geometry matches what is rendered in the scene.
2. **Given** a current 2D section-view slice, **When** exported to PDF, **Then** the
   PDF shows the same section content visible on screen at the time of export.
3. **Given** a project's drillhole data, **When** exported to CSV, **Then** the
   exported file uses the same schema and units as the Phase 0 import path, so it
   could be re-imported cleanly.

---

### User Story 4 - Record and view structural/fault data (Priority: P2)

As the geologist, I want to record fault traces and dip/strike readings and see them
in the 3D scene, so structural interpretation isn't left out of the tool once I need
it.

**Why this priority**: Named in master plan §5 as one of the deferred-but-reserved
fields now getting UI and validation logic; valuable but not blocking on the import/
export headline capabilities above.

**Independent Test**: Structural readings can be entered and viewed independent of
RQD, QA/QC, or scale features.

**Acceptance Scenarios**:

1. **Given** structural readings for a project, **When** entered, **Then** they are
   stored using the schema fields already reserved since Phase 0.
2. **Given** structural data exists for a project, **When** the scene loads, **Then**
   fault traces and readings render alongside drillhole data.

---

### User Story 5 - Record and validate RQD/core recovery (Priority: P2)

As the geologist, I want to enter RQD and core recovery percentages on lithology
intervals and have them validated, so geotechnical quality data isn't just sitting
unused in the schema.

**Why this priority**: Named alongside structural data in master plan §5 as
deferred-but-reserved; same priority tier.

**Independent Test**: RQD/core recovery values can be entered and validated
independent of structural data, QA/QC, or scale features.

**Acceptance Scenarios**:

1. **Given** a lithology interval, **When** RQD or core recovery values are entered,
   **Then** they are validated to fall within a 0-100% range.
2. **Given** RQD/core recovery data exists, **When** a drillhole is inspected,
   **Then** these values appear in the interval table established in Phase 0.

---

### User Story 6 - Record and validate QA/QC sample flags (Priority: P2)

As the geologist, I want duplicate, standard, and blank samples flagged and
validated, so I can trust assay data quality at scale rather than taking it on
faith.

**Why this priority**: The third deferred-but-reserved item named in master plan §5;
directly supports data trust, echoing the Phase 0 kill criterion's spirit at a
deeper level of rigor.

**Independent Test**: QA/QC flags can be applied and validated on an assay import
independent of structural data, RQD, or scale features.

**Acceptance Scenarios**:

1. **Given** an assay CSV import that includes QA/QC sample-type indicators, **When**
   imported, **Then** duplicate, standard, and blank samples are flagged using the
   already-reserved QA/QC field, rather than being treated identically to regular
   samples.
2. **Given** a standard sample with a configured expected grade range, **When** its
   assay value falls outside that range, **Then** it is flagged for review — never
   silently accepted or auto-corrected.

---

### User Story 7 - Stay responsive as a prospect grows dense (Priority: P3)

As the geologist, I want the 3D scene to stay smoothly interactive even when a
prospect has grown well beyond the Phase 0 baseline scale, so the tool doesn't
degrade as my data grows over time.

**Why this priority**: Named in master plan §5 as a scale concern "if a prospect
grows very dense" — a real but lower-urgency risk than the breadth capabilities
above, since most prospects won't hit this ceiling immediately.

**Independent Test**: Interaction smoothness at high interval counts can be verified
independent of any import/export/data-activation feature.

**Acceptance Scenarios**:

1. **Given** a project whose interval count significantly exceeds the Phase 0
   baseline (~5,000), **When** the scene loads, **Then** it remains smoothly
   interactive via level-of-detail or tiling techniques rather than degrading.

---

### Edge Cases

- What happens when a DXF or Shapefile references a coordinate reference different
  from the project's established UTM zone? It MUST be flagged for confirmation, the
  same as any Phase 0 CRS mismatch — never silently assumed.
- What happens when an export is requested for a project with no data yet? The
  system MUST show a reasonable empty/disabled state, never produce a broken or
  misleading export file.
- What happens when a QA/QC standard sample's expected range hasn't been configured
  yet? It MUST be flagged as "unconfigured" rather than silently skipping the check
  or blocking the import outright.
- What happens to click-to-inspect accuracy when level-of-detail/tiling is active?
  Inspection MUST always return full, accurate data regardless of the current
  rendering detail level — only rendering fidelity may degrade, never the underlying
  data.

## Requirements *(mandatory)*

### Functional Requirements

**Import — DXF & Shapefile**

- **FR-001**: Users MUST be able to import a wireframe/vein solid from a DXF file,
  with its geometry parsed and validated, not merely stored as an opaque reference.
- **FR-002**: A DXF import that fails to parse MUST produce a clear per-file error
  without affecting any other project data, consistent with Phase 0's wireframe
  error-handling behavior.
- **FR-003**: Users MUST be able to import trench sample points and a topography
  surface from Shapefiles, with the same CRS-confirmation and validation rigor as the
  Phase 0 CSV import path.
- **FR-004**: A Shapefile import with an ambiguous or missing coordinate reference
  MUST be flagged for explicit user confirmation, never silently assumed.

**Export**

- **FR-005**: Users MUST be able to export a project's wireframes to DXF, with
  geometry matching what is rendered in the 3D scene.
- **FR-006**: Users MUST be able to export the current 2D section view to PDF,
  matching the section content visible on screen at the time of export.
- **FR-007**: Users MUST be able to export a project's drillhole, survey, assay, and
  lithology data to CSV in a schema compatible with the Phase 0 import path.

**Structural/Fault Data**

- **FR-008**: Users MUST be able to record structural readings (fault traces,
  dip/strike) for a project, using the schema fields reserved since Phase 0.
- **FR-009**: Structural data MUST render in the 3D scene alongside drillhole data
  when present.

**RQD/Core Recovery**

- **FR-010**: Users MUST be able to enter RQD and core recovery percentages on
  lithology intervals, validated to fall within a 0-100% range.
- **FR-011**: RQD/core recovery values MUST appear in the drillhole inspection card
  established in Phase 0.

**QA/QC**

- **FR-012**: The system MUST let assay imports flag duplicate, standard, and blank
  samples using the already-reserved QA/QC field, rather than treating all samples
  identically.
- **FR-013**: A standard sample whose assay value falls outside its configured
  expected range MUST be flagged for review, never silently accepted or
  auto-corrected.

**Scale**

- **FR-014**: The 3D scene MUST remain smoothly interactive for projects whose
  interval count significantly exceeds the Phase 0 baseline (~5,000), via
  level-of-detail or tiling techniques, without omitting or degrading the underlying
  data available on inspection.

### Key Entities

- **Project, Collar, Survey, Assay Interval, Lithology Interval, Trench, Wireframe,
  Import Batch, User**: Already defined per `docs/architecture_baseline.md` § 2 and
  the Phase 0 data model. This feature activates fields already reserved on Assay
  Interval (`qaqc_flag`) and Lithology Interval (`rqd_percent`,
  `core_recovery_percent`) rather than introducing new columns on them.
- **Structural Reading** *(new)*: A fault trace or dip/strike reading for a
  project — location, orientation (dip/strike), reading type, and its source import
  batch.
- **QA/QC Standard Reference** *(new)*: A named standard sample's configured expected
  grade range, used to flag out-of-range standard results — standard identifier,
  expected range, commodity/unit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can import a real DXF wireframe file and see its actual parsed
  geometry — not a placeholder — in the 3D scene.
- **SC-002**: A user can import trench/topography data from a Shapefile with the
  same confidence (CRS confirmation, no silent data loss) as a Phase 0 CSV import.
- **SC-003**: A project's wireframes, current section view, and drillhole data can
  each be exported and independently verified to match what is shown in the tool.
- **SC-004**: 100% of RQD/core recovery values entered are validated to be within
  0-100%, with zero invalid values reaching the database.
- **SC-005**: 100% of QA/QC-flagged samples (duplicates, standards, blanks) are
  visibly distinguishable from regular samples wherever assay data is displayed.
- **SC-006**: A project with interval counts well beyond the Phase 0 baseline remains
  smoothly interactive, with zero data loss on inspection at any level of detail.

## Assumptions

- This specification covers only Phase 2 (Section 5 of
  `mining_tool_planning_Final_claude4-7-2026.md`); it does not redefine or replace
  any Phase 0 or Phase 1 capability, only extends them where the master plan
  explicitly calls for it (new import/export formats, activation of reserved fields,
  and scale handling).
- The reserved-but-inactive fields this feature activates (`rqd_percent`,
  `core_recovery_percent`, `qaqc_flag`) already exist in the data model per
  `docs/architecture_baseline.md` and the Phase 0 data model; this feature adds UI
  and validation logic for them, consistent with the master plan's
  "schema-complete, feature-deferred" resolution — it does not introduce new schema
  from scratch for these fields.
- A "QA/QC standard's" expected grade range is assumed to be a simple reference
  table the user maintains within the tool, not an integration with any external
  laboratory system — no such integration is described anywhere in the master plan.
- Level-of-detail/tiling is a rendering-layer technique only; it must never reduce
  the accuracy or completeness of data returned by inspection, export, or any other
  data-facing feature — only the number of full-detail objects rendered
  simultaneously.
- Exports (DXF, PDF, CSV) are one-way, point-in-time snapshots of current committed
  data; this feature does not include any two-way sync or round-trip editing
  workflow with external tools.

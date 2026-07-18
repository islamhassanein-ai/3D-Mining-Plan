# Feature Specification: Phase 0 — Core Visualization & Modeling

**Feature Branch**: `003-phase0-core-visualization`

**Created**: 2026-07-17

**Status**: Draft

**Input**: User description: "Please read the master plan in `mining_tool_planning_Final_claude4-7-2026.md` and the approved baseline document in `docs/architecture_baseline.md`. We want to run the full `spec-kit` workflow to specify, plan, and generate tasks for the remaining execution phases described in the master plan: Section 3: Phase 0 — Core Visualization & Modeling (this feature); Section 4: Phase 1 — Collaboration & Multi-Tenancy and Section 5: Phase 2 — Breadth & Scale are separate features, specified independently — see Assumptions."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import CSV drillhole data with validation before commit (Priority: P1)

As the geologist, I want to drag in my collar/survey/assay/lithology CSV files and see
a validated preview before anything is committed, so that I trust the data going into
my project and don't waste time on bad imports.

**Why this priority**: This is the kill criterion (per `docs/architecture_baseline.md`
§ 1) — if import isn't trustworthy and low-friction, nothing else in this feature
matters.

**Independent Test**: Given a real, messy set of collar/survey/assay/lithology CSVs,
a user can reach a validated, committed project without more manual correction than
their prior ad-hoc workflow required.

**Acceptance Scenarios**:

1. **Given** valid collar/survey/assay/lithology CSVs, **When** imported, **Then** a
   diff view shows each raw source row next to its interpreted row before commit.
2. **Given** a CSV with an ambiguous or unset UTM zone, **When** imported, **Then**
   the system auto-detects a candidate zone and requires explicit user confirmation
   before commit.
3. **Given** a CSV with overlapping or gapped assay/lithology intervals, **When**
   imported, **Then** those rows are flagged visually for review, never silently
   corrected.
4. **Given** assay values below detection limit, **When** imported, **Then** they are
   preserved with the below-detection-limit flag and original detection limit, never
   zeroed or dropped.
5. **Given** a CSV with mixed grade units within one file, **When** imported, **Then**
   the system rejects the silent mix and requires an explicit per-file unit
   declaration.

---

### User Story 2 - View drillhole traces and grade-colored assay intervals in an interactive 3D scene (Priority: P1)

As the geologist, I want to see my drillholes rendered in 3D with assay grade shown by
interval color, and navigate the scene the way I would in professional CAD software,
so that I can build spatial intuition about the prospect.

**Why this priority**: This is the "does it look and feel professional" bar the whole
tool is judged on in the first few minutes.

**Independent Test**: Given an imported project, the 3D scene renders every drillhole
trace and assay interval, and camera navigation feels smooth and CAD-like without any
other feature being built yet.

**Acceptance Scenarios**:

1. **Given** an imported project, **When** the 3D scene loads, **Then** all drillhole
   traces render using minimum-curvature-computed positions.
2. **Given** assay intervals, **When** rendered, **Then** each interval is colored
   according to its grade value.
3. **Given** the scene, **When** the user orbits/pans/zooms, **Then** the camera
   moves smoothly with damping, orbiting around the point under the cursor rather
   than the scene origin.
4. **Given** the scene, **When** the user selects a camera preset (plan, section, or
   isometric), **Then** the view snaps to that preset.
5. **Given** a scene with up to ~5,000 assay intervals, **When** the user interacts
   with it, **Then** it remains smoothly interactive with no perceptible stutter.

---

### User Story 3 - Inspect a drillhole's full record on click (Priority: P1)

As the geologist, I want to click a drillhole and immediately see its collar
coordinates, dip/azimuth, and full interval table, so I can verify what I'm looking
at without leaving the 3D view.

**Why this priority**: Trusting the visualization requires being able to check it
against the underlying record at any time — this is table stakes alongside US1/US2.

**Independent Test**: Given a rendered drillhole from US2, clicking it shows a
complete record without requiring any other feature (grade cutoff, slicing, etc.) to
exist.

**Acceptance Scenarios**:

1. **Given** a rendered drillhole, **When** clicked, **Then** a card appears showing
   collar coordinates, survey dip/azimuth, and the full assay and lithology interval
   table.
2. **Given** the fields shown in this card, **When** compared to the data model in
   `docs/architecture_baseline.md` § 2, **Then** no relevant field is missing.

---

### User Story 4 - Adjust grade cutoff in real time (Priority: P2)

As the geologist, I want to move a grade-cutoff slider and see the 3D scene update
immediately, so I can explore which intervals matter without reloading.

**Why this priority**: A strong differentiator from a static export, but the scene is
still useful without it.

**Independent Test**: Given a loaded scene from US2, moving the grade-cutoff control
visibly changes which intervals are shown or dimmed, with no other feature required.

**Acceptance Scenarios**:

1. **Given** a loaded scene, **When** the grade-cutoff slider is moved, **Then**
   intervals below the cutoff are hidden or dimmed without a page reload.

---

### User Story 5 - Slice the model with a synced 2D section view (Priority: P2)

As the geologist, I want an interactive slicing plane (N-S, E-W, or arbitrary
azimuth) with a synced 2D section view, so I can think in section the way I would in
professional mining software.

**Why this priority**: Important for engineering-style thinking, but the 3D scene
already stands on its own without it.

**Independent Test**: Given a loaded scene from US2, placing and moving a slicing
plane updates a 2D section view in sync, independent of any other feature.

**Acceptance Scenarios**:

1. **Given** a loaded scene, **When** a slicing plane is placed and moved, **Then**
   the 2D section view updates in sync without lag.

---

### User Story 6 - Measure distances and true thickness (Priority: P2)

As the geologist, I want to click two points to measure 3D distance and derive true
thickness versus downhole length, so my grade-thickness intuition is directionally
correct.

**Why this priority**: Directly affects whether conclusions drawn in the tool are
trustworthy (per the Mining Engineer non-negotiable in the panel review), but is an
add-on to an already-functioning scene.

**Independent Test**: Given a loaded scene from US2, selecting two points shows a
distance measurement, and true thickness can be derived for a selected assay
interval, independent of any other feature.

**Acceptance Scenarios**:

1. **Given** two points in the 3D scene, **When** selected, **Then** the measured 3D
   distance between them is displayed.
2. **Given** an assay interval and its hole's dip, **When** true thickness is
   requested, **Then** it is computed and clearly distinguished from downhole length.

---

### User Story 7 - View topography, trenches, and imported solids alongside drillholes (Priority: P2)

As the geologist, I want to see a topography surface, trench sample data, and
imported wireframe/vein solids in the same 3D scene as my drillholes, so I get
pit-shape and strip-ratio intuition even informally.

**Why this priority**: Flagged in the panel review as "riskier to omit than it
looks" — without it, core spatial reasoning the tool exists for is impossible — but
it augments rather than blocks the base drillhole scene.

**Independent Test**: Given a project with topography, trench, or wireframe data
available, each renders correctly alongside the drillholes from US2, independent of
any other feature.

**Acceptance Scenarios**:

1. **Given** a topography surface is available, **When** the scene loads, **Then**
   it renders alongside the drillholes.
2. **Given** trench data, **When** the scene loads, **Then** trench sample points
   render alongside the drillholes.
3. **Given** an imported wireframe or vein solid, **When** the scene loads, **Then**
   it renders as a 3D solid alongside the drillholes.

---

### User Story 8 - Orient myself with a CAD-style gizmo (Priority: P3)

As the geologist, I want a CAD-style orientation gizmo visible in the scene, so I
always know which way is north/up without guessing.

**Why this priority**: A small, well-understood polish item professionals judge
tools on quickly, but the scene is fully usable without it.

**Independent Test**: Given a loaded scene from US2, an orientation gizmo is visible
and reflects the current camera orientation, independent of any other feature.

**Acceptance Scenarios**:

1. **Given** the 3D scene, **When** viewed from any angle, **Then** an orientation
   gizmo is visible and reflects the current camera orientation.

---

### Edge Cases

- What happens when an assay or survey CSV references a `hole_id` that doesn't exist
  in the collar file? It MUST be flagged as an orphan reference during import
  validation (US1), never silently dropped.
- What happens when a project has no data yet? The scene MUST show a clear empty
  state, never a blank or broken screen.
- What happens when network connectivity drops mid-session? The last-loaded project
  MUST remain visible from a client-side cache rather than blanking the screen (per
  `docs/architecture_baseline.md` § 4 Offline/Field Use baseline).
- What happens when an imported wireframe/vein solid file fails to parse? The system
  MUST show a clear error for that item without crashing or blanking the rest of the
  scene.
- What happens when true thickness cannot be computed (e.g., missing dip data)? The
  system MUST indicate the value is unavailable rather than showing a misleading
  number.

## Requirements *(mandatory)*

### Functional Requirements

**Data Import**

- **FR-001**: Users MUST be able to import Collar, Survey, Assay, and Lithology data
  via CSV files, one file per data type.
- **FR-002**: The system MUST compute every drillhole trace using the minimum
  curvature method (per `docs/architecture_baseline.md` § 2 and constitution
  Principle I) — no alternative desurvey method may be offered.
- **FR-003**: Before any import is committed, the system MUST present a diff view
  comparing each raw source row to its interpreted row.
- **FR-004**: The system MUST auto-detect the likely UTM zone from coordinate ranges
  and require the user's explicit confirmation before committing any import.
- **FR-005**: The system MUST preserve below-detection-limit assay values with their
  flag and original detection limit, never zeroing or dropping them.
- **FR-006**: The system MUST flag overlapping or gapped assay/lithology intervals
  for user review rather than auto-correcting them.
- **FR-007**: The system MUST flag likely swapped latitude/longitude values using a
  plausible coordinate-range heuristic.
- **FR-008**: The system MUST reject silent unit-mixing within a single assay import
  and require an explicit per-file unit declaration.
- **FR-009**: The system MUST flag import rows that reference a `hole_id` not present
  in the corresponding collar data, rather than silently dropping them.

**3D Scene & Navigation**

- **FR-010**: The system MUST render all drillhole traces and assay intervals in an
  interactive 3D scene, with each assay interval colored according to its grade
  value.
- **FR-011**: Camera navigation MUST support smooth, damped orbit/pan/zoom, orbiting
  around the point under the cursor rather than a fixed scene origin.
- **FR-012**: The system MUST provide plan, section, and isometric camera presets,
  reachable via toolbar and keyboard shortcut.
- **FR-013**: The 3D scene MUST remain smoothly interactive with up to ~5,000
  rendered assay intervals.
- **FR-014**: The system MUST display a CAD-style orientation gizmo reflecting the
  current camera orientation.
- **FR-015**: The system MUST show a clear empty state when a project has no data
  yet, and clear loading/error states during import and scene load.

**Inspection & Measurement**

- **FR-016**: Clicking a drillhole MUST display a card with its collar coordinates,
  survey dip/azimuth, and full assay and lithology interval table.
- **FR-017**: Users MUST be able to click two points in the 3D scene to measure the
  distance between them.
- **FR-018**: The system MUST compute and clearly distinguish true thickness from
  downhole length for assay intervals, given hole dip.
- **FR-019**: Users MUST be able to adjust a grade-cutoff control that updates which
  intervals are shown or dimmed in the scene without a full reload.
- **FR-020**: The system MUST provide an interactive slicing plane (N-S, E-W, or
  arbitrary azimuth) with a synced 2D section view that updates as the plane moves.

**Supplementary Data**

- **FR-021**: The system MUST render an imported topography surface in the 3D scene
  alongside drillholes.
- **FR-022**: The system MUST render trench sample data (location and grade) in the
  3D scene alongside drillholes.
- **FR-023**: The system MUST import and render wireframe/vein solid files in the 3D
  scene alongside drillholes.

**Reliability & Consistency**

- **FR-024**: The system MUST cache the last-loaded project client-side so a brief
  connectivity drop does not blank the screen.
- **FR-025**: Every entity and rule this feature introduces MUST conform to the data
  model and architecture already fixed in `docs/architecture_baseline.md`; where a
  need arises that the baseline doesn't cover, that document must be amended, not
  silently contradicted (per its own FR-015 governance rule).

### Key Entities

This feature builds against the entities already defined in
`docs/architecture_baseline.md` § 2 (Project, Collar, Survey, Assay Interval,
Lithology Interval, Trench, Wireframe, Import Batch, User) — see that document for
fields and relationships. This spec does not redefine them.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A geologist can go from selecting CSV files to a validated, committed
  project in under 60 seconds for a typical prospect-sized dataset.
- **SC-002**: Given 2-3 real messy CSVs from past projects, import requires no more
  manual correction than the prior ad-hoc (spreadsheet + charting) workflow required
  — the kill criterion; if this fails, subsequent work pivots to import-robustness
  only before any further visual features are added.
- **SC-003**: A scene with up to 5,000 assay intervals sustains smooth interaction
  (no perceptible stutter) during orbit/pan/zoom.
- **SC-004**: Clicking any drillhole shows its full record (collar, survey,
  intervals) with zero fields missing relative to the data model.
- **SC-005**: 100% of below-detection-limit assay values and overlapping/gapped
  intervals in a test import are visibly flagged, with zero silently altered or
  dropped values.
- **SC-006**: A first-time user unfamiliar with the tool can identify and use the
  six signature interaction patterns (smooth camera, drillhole card, grade-cutoff,
  synced section view, one-flow import, camera presets) within their first 5 minutes
  of use.

## Assumptions

- This specification covers only Phase 0 (Section 3 of
  `mining_tool_planning_Final_claude4-7-2026.md`). Phase 1 (Collaboration &
  Multi-Tenancy, Section 4) and Phase 2 (Breadth & Scale, Section 5) are separate
  features to be specified independently in their own `/speckit-specify` runs,
  consistent with Spec Kit's one-feature-per-specification model and with this
  project's own governance discipline (see `docs/architecture_baseline.md` § 1
  non-goals, which excludes multi-tenancy from V1).
- All data model, CRS, desurvey-method, and system-architecture decisions are
  inherited from `docs/architecture_baseline.md` and the project constitution; this
  spec does not redefine them, it only builds functionality against them.
- "User" throughout this spec refers to the project owner acting as the geologist
  reviewing their own data, consistent with `docs/architecture_baseline.md` § 1
  Target Users/JTBD — not a multi-tenant end-user base (that's explicitly Phase 1
  scope).
- RQD/core-recovery, structural/fault data, and QA/QC duplicate/standard/blank
  fields remain schema-reserved but inactive in this phase (no UI or validation
  logic), per `docs/architecture_baseline.md` § 2 and the master plan's Phase 2
  deferral.
- DXF and Shapefile import are out of scope for this feature; CSV/Excel is the only
  import format, per the constitution's Technology Stack Constraints (CSV-only in
  Phase 0).

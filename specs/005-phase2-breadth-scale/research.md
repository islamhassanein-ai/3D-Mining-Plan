# Phase 0 Research: Phase 2 Breadth & Scale

No `NEEDS CLARIFICATION` markers remain in the Technical Context. The decisions
below are the implementation-level choices needed to build this feature's import,
export, and scale capabilities.

## Decision 1: DXF parsing and writing library

**Decision**: Use `ezdxf` for both parsing (import) and writing (export) DXF files.

**Rationale**: `ezdxf` is the standard, actively-maintained, pure-Python library for
DXF — no native/GDAL dependency, well-documented, and it's the same library for both
directions (import geometry in, export geometry out), avoiding a second library just
for writing.

**Alternatives considered**: Writing a custom minimal DXF parser — rejected as
reinventing a well-solved, format-detail-heavy problem (DXF has many entity types and
version quirks); a CAD-focused heavier library — rejected, `ezdxf` already covers the
wireframe/solid geometry this feature needs without extra weight.

## Decision 2: Shapefile parsing library

**Decision**: Use `pyshp` (the `shapefile` package) to parse trench and topography
Shapefiles.

**Rationale**: `pyshp` is pure Python with no GDAL/native binary dependency, reads
the geometry and attribute data this feature needs (points for trenches, a surface
mesh or point cloud for topography), and matches Principle III's preference for
minimal, boring dependencies over heavier GIS stacks.

**Alternatives considered**: `fiona`/`geopandas` — rejected; both require a GDAL
native binary, which is a much heavier, harder-to-install dependency than this
feature's actual needs (reading point/polygon geometry from a file) justify.

## Decision 3: PDF export library

**Decision**: Use `reportlab` to generate a 2D vector PDF of the current section view
from the same geometry data the frontend section view renders (from feature 003's
slicing-plane / 2D section component), generated server-side.

**Rationale**: Keeps the frontend "boring" (no new JS PDF library, no client-side
canvas-to-PDF conversion complexity); `reportlab` is a mature, minimal, pure-Python
PDF library well suited to simple 2D vector output. Generating server-side also keeps
export logic consistent with DXF/CSV export (all three live in the backend).

**Alternatives considered**: Client-side PDF generation (e.g., rendering the section
canvas and converting to PDF in the browser) — rejected; would add a new frontend
dependency and duplicate geometry logic that already exists server-side for the
scene/section data.

## Decision 4: LOD activation threshold and technique

**Decision**: Level-of-detail management activates client-side once a project's
combined assay + lithology interval count exceeds roughly 20,000 (4x the Phase 0
baseline). Below that, no LOD behavior changes anything (identical to feature 003).
Above it, the frontend's `lod_manager.js` hides/simplifies `InstancedMesh` instances
outside a distance threshold from the camera, using the same instance buffers
feature 003 already builds — no new geometry system, no backend changes, no
reduction in what `GET /collars/{id}` or any export returns.

**Rationale**: The spec (FR-014) requires no *data* degradation, only rendering
behavior — keeping the scene endpoint unchanged and doing distance-based instance
visibility toggling is the simplest technique that satisfies this, consistent with
Principle III. 20,000 is a deliberately round, conservative multiple of the Phase 0
target chosen because the spec doesn't pin an exact number ("well beyond... ~5,000");
it's a starting point tunable later based on real usage, not a hard architectural
commitment.

**Alternatives considered**: Server-side spatial tiling (paginated scene payloads by
bounding box) — rejected as premature complexity at this project's stated 1-3 user,
single-prospect scale (Principle III); a fixed hard cap on rendered intervals
regardless of distance — rejected, would arbitrarily hide near-camera data instead of
prioritizing what the user is actually looking at.

## Decision 5: RQD/core-recovery and QA/QC validation placement

**Decision**: Extend feature 003's existing `import_validation.py` with two more
rules — RQD/core-recovery values must be within 0-100%, and a standard sample's
assay value is flagged (not blocked) when it falls outside its configured QA/QC
Standard Reference range — rather than creating a separate validation module.

**Rationale**: `import_validation.py` is already "the place that answers 'what makes
an import valid'"; splitting validation logic across multiple files for what is
conceptually the same kind of check (per-row range/consistency rules) would work
against Principle III's maintainability goal.

**Alternatives considered**: A dedicated `qaqc_validation.py` — rejected, no clear
boundary from the existing validation rules that would justify a second file for a
solo maintainer to keep track of.

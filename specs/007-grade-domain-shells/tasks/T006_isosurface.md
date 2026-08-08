# T006 — Iso-surface Mesh Extraction

> Read `specs/007-grade-domain-shells/tasks.md` first.

| Field | Value |
|---|---|
| **Task ID** | T006 |
| **Priority** | P0 |
| **Dependencies** | T005 |
| **Complexity** | Medium |
| **Status** | **DONE — Q3 still open, and deliberately not implemented** |

> Implemented with **no minimum-width enforcement**, per the recommendation in
> Q3: enforcing one would turn a *grade* shell into a *mining* shape, which is a
> different object and exactly the conflation D3 exists to prevent. `min_volume`
> remains a volume filter and will not remove a thin, laterally extensive sheet
> — that is a known limitation, recorded rather than papered over.
>
> **D1 implemented**: `nan` becomes a sentinel strictly below the threshold, so
> the surface closes inward against unsampled ground.
>
> **One deviation from the specification below.** Requirement 8 said to return
> an empty result when all values are above the threshold. It does not: when
> every estimated node qualifies, the surface returned is the boundary of the
> estimated region. That is the truthful answer — the cut-off has selected
> everything sampled — and an implausibly large envelope makes a mis-set
> threshold obvious where an empty result would hide it. It is still not
> extrapolation: the envelope stops where the interpolant stopped. An empty
> result is returned when nothing was estimated, or when nothing reaches the
> threshold.

---

## Context

The grade shell is the iso-surface of the T005 grid at the chosen threshold.
Two details decide whether the result is usable: how `nan` nodes are handled at
the edge of the data, and whether the resulting mesh is closed.

`nan` means "unsampled". The surface must **close** against unsampled ground
rather than run off to the grid boundary — otherwise the shell claims
mineralisation continues into ground nobody has tested.

---

## Objective

Convert a `GradeGrid` and a threshold into a triangulated mesh in project world
coordinates, optionally split into separate connected solids, and write it as
OBJ text.

---

## Detailed Requirements

### Functional

1. **`nan` handling.** Before extraction, replace every `nan` with a sentinel
   strictly below the threshold (use `threshold - 1.0`, or the grid minimum
   minus 1.0, whichever is lower). This forces the surface to close inward
   against unsampled ground. Document this in the docstring — it is a
   geological decision, not an implementation detail.
2. **Padding.** Pad the value array with one layer of the sentinel on all six
   faces before extraction, then account for the offset when converting indices
   to world coordinates. Without this, a shell touching the grid edge extracts
   as an open surface.
3. **Extraction.** Use `skimage.measure.marching_cubes(volume, level=threshold)`.
   Take `verts` and `faces`. Do not implement marching cubes by hand.
4. **World coordinates.** Marching cubes returns vertices in **index space**.
   Convert with `world = origin + (index - 1) * cell_size` (the `-1` undoes the
   pad from step 2). Emit `(easting, northing, elevation)` — **no axis swap**.
5. **Connected components.** Optionally split the mesh into separate connected
   solids by shared vertices (union-find over face vertex indices). Discard
   components with volume below `min_volume` (default `0.0`, meaning keep all).
   This removes single-cell specks around isolated high assays.
6. **Volume.** Compute each component's volume by the signed-tetrahedron sum
   over its triangles, taking the absolute value. Report it.
7. **OBJ output.** Produce OBJ text with `v` lines in raw UTM order and
   1-indexed triangular `f` lines, matching what
   `backend/src/services/obj_geometry.py::parse_obj` reads and what
   `frontend/src/scene/wireframes.js` renders. Round-tripping through
   `parse_obj` must return an equivalent mesh — assert this.
8. **Empty result.** If no surface exists at the threshold (all values above or
   all below), return a result with zero components and empty OBJ text. Do not
   raise.

### File Location

- `backend/src/services/isosurface.py`
- `backend/tests/unit/test_isosurface.py`

### Dependencies

**This task adds `scikit-image` to `backend/requirements.txt`.** Nothing else.
`numpy` comes from T005.

---

## Interface Contract

```python
from dataclasses import dataclass
import numpy as np
from backend.src.services.grade_interpolant import GradeGrid

@dataclass(frozen=True)
class MeshComponent:
    vertices: list[tuple[float, float, float]]   # (easting, northing, elevation)
    faces: list[tuple[int, int, int]]            # 0-indexed into vertices
    volume: float                                # cubic metres

@dataclass(frozen=True)
class IsosurfaceResult:
    components: list[MeshComponent]
    threshold: float
    total_volume: float

def extract_isosurface(
    grid: GradeGrid,
    threshold: float,
    split_components: bool = True,
    min_volume: float = 0.0,
) -> IsosurfaceResult: ...

def mesh_to_obj(result: IsosurfaceResult, name: str = "grade_shell") -> str:
    """OBJ text; one `o <name>_<i>` group per component, shared vertex numbering."""
```

---

## Test Fixtures

**F1 — sphere volume.** Build a `GradeGrid` analytically: values
`10.0 - distance_from_centre` on a 40³ grid with `cell_size=1.0`, so the
iso-surface at `threshold=5.0` is a sphere of radius 5. Expect
`total_volume ≈ 4/3 π 5³ ≈ 523.6`, within **5%**. Marching cubes on a coarse
grid under-reports slightly; 5% is the correct tolerance, do not tighten it and
do not fudge the volume formula to hit it.

**F2 — watertight.** For F1's mesh, every edge must be shared by exactly two
triangles. Build the edge set as frozensets of vertex-index pairs and assert
every count is 2. **This is the single most important test in the task.**

**F3 — world coordinates.** Give the grid `origin=(500000, 4500000, 1000)` and
assert the mesh bounding box centre matches the sphere centre's world position
to within one `cell_size`. Assert the elevation range sits around `1000`, not
around `4500000` — that catches an axis swap.

**F4 — nan closes the surface.** Take F1's grid and set an outer shell of nodes
to `nan`. The mesh must remain watertight (rerun F2's check) and its volume
must not increase.

**F5 — two components.** Two separated spheres, `split_components=True` →
`len(components) == 2`, each watertight, `total_volume` equal to their sum.

**F6 — min_volume filter.** Add a single-cell blip to F5's grid; with
`min_volume` above the blip's volume, it is excluded and `total_volume` drops
accordingly.

**F7 — empty.** Grid entirely below threshold → zero components, empty OBJ,
no exception.

**F8 — OBJ round trip.** `parse_obj(mesh_to_obj(result))` returns the same
vertex count and face count, and vertex 0 matches to `1e-6`.

**F9 — OBJ indexing.** OBJ `f` indices are **1-based**. Assert the minimum
index in the emitted text is `1`, not `0`.

---

## Acceptance Criteria

| # | Priority | Criterion |
|---|---|---|
| AC-1 | P0 | F1–F9 pass |
| AC-2 | P0 | Mesh is watertight (F2, F4) — every edge shared by exactly two faces |
| AC-3 | P0 | `nan` is treated as below-threshold and closes the surface inward |
| AC-4 | P0 | Vertices are `(easting, northing, elevation)`; no Y-up swap |
| AC-5 | P0 | Index→world conversion accounts for the one-cell pad |
| AC-6 | P0 | OBJ is 1-indexed and round-trips through `parse_obj` |
| AC-7 | P1 | Component splitting and `min_volume` work as specified |
| AC-8 | P1 | Empty result returns cleanly rather than raising |

---

## Anti-Patterns to Avoid

- Replacing `nan` with `0.0` before extraction when the threshold is also near
  zero — the sentinel must be **strictly below** the threshold.
- Forgetting the pad, then wondering why shells that reach the grid edge render
  as open shells with visible interiors.
- Forgetting to subtract the pad when converting index → world, which shifts
  the entire shell by one cell. F3 catches it.
- Emitting 0-indexed OBJ faces. Every OBJ reader, including this project's,
  expects 1-indexed.
- Writing your own marching cubes. `skimage` is a dependency for exactly this.
- Reporting volume from a vertex-count heuristic instead of the tetrahedron sum.

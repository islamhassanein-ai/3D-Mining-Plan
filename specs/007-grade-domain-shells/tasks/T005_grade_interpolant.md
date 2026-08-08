# T005 — Anisotropic IDW Grid Interpolant

> Read `specs/007-grade-domain-shells/tasks.md` first.

| Field | Value |
|---|---|
| **Task ID** | T005 |
| **Priority** | P0 |
| **Dependencies** | T004 |
| **Complexity** | Large |
| **Status** | **DONE** |

> **Unblocked by D6 and D7**, both of which were design questions rather than
> value questions:
>
> - **D6** — FC is geometry-only. `sample_type_weights` is now a **required
>   argument** with no default; a type present in the data but absent from the
>   mapping raises. A forgotten type is a forgotten decision.
> - **D7** — `SearchEllipsoid` has **no default ranges and no default
>   orientation**. Every run states them.
> - **D1** — `min_samples` guard and `nan` output implemented as specified.
> - **D2** — `WeightKernel` protocol with `inverse_distance_kernel`; the kernel
>   is injectable and tested with a custom one.
>
> Adel's actual strike, dip and ranges are still needed to *run* this, and the
> TR weight is with the expert team — but neither blocks the implementation,
> since both are inputs.

---

## Context

To extract an iso-surface we first need a continuous grade field on a regular
grid. Inverse-distance weighting is the right choice here: it is transparent,
deterministic, needs no variogram, and — critically — it is honest about being
an interpolant rather than an estimator.

The anisotropy is not a nicety. Gold mineralisation is controlled by structure;
an isotropic interpolant produces spherical blobs around each hole that no
geologist will accept and that misrepresent continuity along strike. The search
ellipsoid must be orientable to the mineralisation's strike and dip.

Trench composites are dense and near-surface. Left untreated they dominate the
interpolant at surface and drag the shell upward. Hence the sample-type weight.

---

## Objective

A pure function that takes 3D composites and produces a regular 3D grid of
interpolated grade values, using an orientable anisotropic search ellipsoid.

---

## Detailed Requirements

### Functional

1. **Grid definition.** Build an axis-aligned regular grid over the composites'
   bounding box, expanded by `padding` (default `20.0` m) on all sides, with
   spacing `cell_size` (default `5.0` m). Grid axes are project east, north,
   elevation — no rotation of the grid itself.
2. **Anisotropic distance.** Rotate the vector from grid node to sample into
   the ellipsoid frame defined by `(strike_azimuth, dip, plunge=0)`, then scale
   each axis by its range, and take the Euclidean norm of the scaled vector:

   ```
   d_aniso = sqrt( (u/range_major)² + (v/range_semi)² + (w/range_minor)² )
   ```

   `u` is along strike, `v` along dip, `w` normal to the plane. `d_aniso <= 1.0`
   means "inside the search ellipsoid".
3. **Rotation convention.** Azimuth clockwise from north; dip degrees from
   horizontal, **downward negative** (project convention). Document the rotation
   matrix in the docstring with the axis order, and unit-test it (see F2).
4. **Weighting.** `w_i = sample_weight_i / (d_aniso_i ** power + epsilon)`,
   `power` default `2.0`, `epsilon = 1e-9`. Node value is
   `sum(w_i × grade_i) / sum(w_i)`.
5. **Sample-type weights.** `sample_type_weights: dict[str, float]`, default
   `{"DDH": 1.0, "TR": 0.5, "CH": 0.5, "FC": 0.5}`. An unlisted type defaults
   to `1.0`. Passing `{"TR": 0.0}` must effectively exclude trench data from
   grade values while leaving it available to callers for geometry.
6. **Search constraints.**
   - Only samples with `d_aniso <= 1.0` participate.
   - `max_samples` (default `16`) nearest by `d_aniso`.
   - `min_samples` (default `2`): a node with fewer contributing samples gets
     `nan`, not a value. **Do not extrapolate into unsampled ground.** This is
     the guard against inventing tonnes where nothing was drilled.
   - Exact hits (`d_aniso < 1e-9`) return that sample's grade directly.
7. **Output** is a `numpy` float array of shape `(nx, ny, nz)` with `nan` for
   unestimated nodes, plus the grid origin and spacing so T006 can map indices
   back to world coordinates.
8. **Determinism.** Same inputs → bitwise-identical output. No randomness, no
   set/dict iteration affecting results, no parallelism that reorders sums.
9. **Performance.** Grids may reach ~200³. A brute-force all-samples-per-node
   loop in pure Python will be far too slow. Vectorise with numpy over nodes,
   or bucket samples into a uniform spatial grid keyed by cell index. Target:
   a 100³ grid with 5,000 composites completes in under 30 s on one core. Add a
   test that asserts this on a 40³ grid with 500 composites in under 3 s.

10. **Replaceable engine (decision D2).** The weighting kernel is a separate,
    injectable callable — not inlined into the search loop:

    ```python
    from typing import Protocol
    import numpy as np

    class WeightKernel(Protocol):
        """Maps anisotropic distances to interpolation weights.

        d_aniso: (n_samples,) float array, already normalised so that 1.0 is
        the ellipsoid boundary. Returns (n_samples,) non-negative weights.
        """
        def __call__(self, d_aniso: np.ndarray) -> np.ndarray: ...

    def inverse_distance_kernel(power: float = 2.0) -> WeightKernel: ...
    ```

    `interpolate_grade_grid` takes `kernel: WeightKernel | None = None` and
    builds `inverse_distance_kernel(power)` when it is `None`, so the existing
    signature and behaviour are unchanged. An RBF engine is then a new kernel
    plus, if it needs one, its own solver — added without touching grid
    construction, the ellipsoid search, or the `nan` policy. Do not implement
    RBF now; only leave the seam.

### File Location

- `backend/src/services/grade_interpolant.py`
- `backend/tests/unit/test_grade_interpolant.py`

### Dependencies

**This task adds `numpy` to `backend/requirements.txt`.** Nothing else.

---

## Interface Contract

```python
from dataclasses import dataclass, field
import numpy as np
from backend.src.services.sample_type_comparison import TypedComposite

@dataclass(frozen=True)
class SearchEllipsoid:
    range_major: float          # along strike, metres
    range_semi: float           # along dip
    range_minor: float          # across the structure
    strike_azimuth: float = 0.0 # degrees clockwise from north
    dip: float = 0.0            # degrees from horizontal, downward negative

@dataclass(frozen=True)
class GradeGrid:
    values: np.ndarray          # (nx, ny, nz), float64, nan == unestimated
    origin: tuple[float, float, float]   # world coords of node [0,0,0]
    cell_size: float
    n_estimated: int
    n_total: int

def interpolate_grade_grid(
    composites: list[TypedComposite],
    ellipsoid: SearchEllipsoid,
    cell_size: float = 5.0,
    padding: float = 20.0,
    power: float = 2.0,
    max_samples: int = 16,
    min_samples: int = 2,
    sample_type_weights: dict[str, float] | None = None,
) -> GradeGrid:
    ...
```

World coordinate of node `(i, j, k)` is
`(origin[0] + i*cell_size, origin[1] + j*cell_size, origin[2] + k*cell_size)`.
T006 depends on exactly this; state it in the docstring.

---

## Test Fixtures (hand-computed)

**F1 — exact hit.** One composite grade `5.0` at a point that lands exactly on
a grid node (choose `cell_size` and coordinates so it does), `min_samples=1`.
That node's value is exactly `5.0`.

**F2 — anisotropy rotates correctly.** Ellipsoid `range_major=100`,
`range_semi=10`, `range_minor=10`, `strike_azimuth=90` (east–west),
`dip=0`. Two composites 50 m apart **along east**: both fall inside one
another's ellipsoid. Move them 50 m apart **along north** instead: neither is
inside the other's. Assert the estimated-node count is substantially higher in
the east–west case. *This test fails if you swap the sin/cos in the rotation —
which is the most common error in this task.*

**F3 — min_samples guard.** One single composite, `min_samples=2` →
`n_estimated == 0` and `values` is all-`nan`.

**F4 — no extrapolation.** Composites clustered in one corner of a large
bounding box. Assert nodes more than `range_major` away are `nan`.

**F5 — IDW midpoint.** Two composites, grades `0.0` and `10.0`, symmetric about
a node, equal weights, `power=2`, isotropic ranges large enough to include
both. That node is `5.0` to `1e-9`.

**F6 — power sharpens.** Same as F5 but move the node so it is twice as far
from the `10.0` sample as from the `0.0` sample. `power=1` gives
`(0/1 + 10/2)/(1/1 + 1/2) = 3.333…`; `power=2` gives
`(0/1 + 10/4)/(1 + 1/4) = 2.0`. Assert both exactly.

**F7 — sample-type weight.** Coincident DDH (`grade 1.0`) and TR (`grade 5.0`)
composites at equal distance from a node. With weights `{"DDH":1.0,"TR":1.0}`
the node is `3.0`; with `{"DDH":1.0,"TR":0.0}` it is `1.0`. Assert both.

**F8 — determinism.** Call twice on shuffled input lists; assert
`np.array_equal` treating `nan` as equal (`np.testing.assert_array_equal`).

**F9 — performance.** 40³ grid, 500 random-but-seeded composites, under 3 s.

---

## Acceptance Criteria

| # | Priority | Criterion |
|---|---|---|
| AC-1 | P0 | F1–F9 pass, with F6's `3.333…` and `2.0` exact |
| AC-2 | P0 | Nodes with fewer than `min_samples` are `nan` — never 0.0, never a fallback global mean |
| AC-3 | P0 | Anisotropy rotation verified by F2 |
| AC-4 | P0 | Output is deterministic regardless of input order |
| AC-5 | P0 | `sample_type_weights` of 0.0 fully excludes that type |
| AC-6 | P0 | Function is pure — no DB, no file I/O |
| AC-7 | P1 | Docstring states the node→world coordinate formula and the rotation matrix |
| AC-8 | P1 | Performance target met |
| AC-9 | P0 | Weighting kernel is injectable per D2; a test passes a custom kernel (e.g. constant weights, giving an unweighted mean) and asserts it is used |

---

## Anti-Patterns to Avoid

- Filling unestimated nodes with `0.0`. Zero grade is a *statement about the
  rock*; `nan` is "we don't know". T006 treats them completely differently, and
  a zero-fill will produce a shell that stops at an arbitrary rectangle.
- Falling back to a global mean when the search finds too few samples.
- Isotropic-only interpolation with the ellipsoid parameters accepted but
  ignored. F2 exists to catch this.
- Nested Python loops over (nodes × samples) for the full grid — correct but
  unusably slow; F9 will fail.
- `random` or unseeded ordering anywhere.

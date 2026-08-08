"""Anisotropic inverse-distance interpolation onto a regular grid.

An iso-surface needs a continuous grade field, and this builds one. Inverse
distance is the right tool for the job here: it is transparent, deterministic,
needs no variogram, and -- the part that matters most -- it does not pretend to
be an estimator. What comes out of this is an interpolant used to draw a domain
boundary, not a grade estimate, and nothing downstream may present it as one.

Three behaviours are geological decisions rather than implementation details.

**The search ellipsoid is orientable, and its orientation is required.** Gold
mineralisation is controlled by structure. An isotropic search produces spheres
around each hole -- blobs that misrepresent continuity along strike and that no
geologist will sign. ``SearchEllipsoid`` therefore has no default ranges and no
default orientation: a caller must state them every time. A shell built on an
unnoticed default looks entirely plausible and is rotated off the structure.
(Decision D7.)

**Unsampled ground stays unsampled.** A node that cannot find ``min_samples``
inside its ellipsoid is ``nan``, never zero and never a fallback global mean.
Zero is a claim about the rock; ``nan`` is an admission that nobody has looked.
The iso-surface treats the two completely differently, and filling ``nan`` with
a number is how a shell comes to extend into ground that was never drilled.
(Decision D1.)

**Sample types carry different weight, and the weights are required.** Face
channels at Adel read 23x the drill population because they are cut on exposed
mineralised faces; trench floors read 3x. ``sample_type_weights`` is a required
argument for the same reason the orientation is -- a silent default of 1.0 would
quietly overturn a decision someone made deliberately. A weight of ``0.0``
excludes a type from grade entirely while leaving it available to the caller for
geometry. (Decision D6.)

The weighting kernel is injectable so the engine can be replaced later --
radial basis functions being the obvious candidate -- without touching grid
construction, the ellipsoid search, or the ``nan`` policy. (Decision D2.)
"""
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

import numpy as np

from backend.src.services.sample_type_comparison import TypedComposite

# Distances are normalised so the ellipsoid boundary sits at 1.0.
_ELLIPSOID_BOUNDARY = 1.0

# Guards the reciprocal at a sample's own position. A node sitting exactly on a
# sample gets a weight around 1e9, which swamps every other contribution and
# reproduces that sample's grade to floating-point precision -- unless its type
# weight is 0.0, in which case it correctly contributes nothing.
_EPS = 1e-9

DEFAULT_CELL_SIZE = 5.0
DEFAULT_PADDING = 20.0
DEFAULT_POWER = 2.0
DEFAULT_MAX_SAMPLES = 16
DEFAULT_MIN_SAMPLES = 2

# Node budget per distance block. Keeps the node-by-sample matrix to a few tens
# of megabytes whatever the sample count.
_BLOCK_BUDGET = 4_000_000


class WeightKernel(Protocol):
    """Maps anisotropic distances to interpolation weights.

    ``d_aniso`` is a float array already normalised so that 1.0 is the
    ellipsoid boundary. Returns non-negative weights of the same shape.
    """

    def __call__(self, d_aniso: np.ndarray) -> np.ndarray:
        ...


def inverse_distance_kernel(power: float = DEFAULT_POWER) -> WeightKernel:
    """The default kernel: ``1 / (d ** power + eps)``."""
    if power <= 0:
        raise ValueError(f"power must be positive, got {power}")

    def kernel(d_aniso: np.ndarray) -> np.ndarray:
        return 1.0 / (np.power(d_aniso, power) + _EPS)

    return kernel


@dataclass(frozen=True)
class SearchEllipsoid:
    """Search ranges and orientation. No defaults, by decision D7.

    ``range_major`` runs along strike, ``range_semi`` down dip, ``range_minor``
    across the structure. ``strike_azimuth`` is degrees clockwise from north.
    ``dip`` is degrees from horizontal with **downward negative**, matching
    ``desurvey.compute_minimum_curvature_trace`` and every other angle in this
    application.

    Dip direction is taken as ``strike_azimuth + 90``. Stating that convention
    explicitly matters more than which one is chosen -- an unstated one is how a
    shell ends up rotated ninety degrees off the structure it is meant to follow.
    """

    range_major: float
    range_semi: float
    range_minor: float
    strike_azimuth: float
    dip: float

    def __post_init__(self):
        for name in ("range_major", "range_semi", "range_minor"):
            value = getattr(self, name)
            if value <= 0:
                raise ValueError(f"{name} must be positive, got {value}")

    @property
    def max_range(self) -> float:
        """Radius of the bounding sphere -- nothing outside it can be inside."""
        return max(self.range_major, self.range_semi, self.range_minor)

    def axes(self) -> np.ndarray:
        """Unit vectors ``[along-strike, down-dip, normal]`` in world axes.

        World axes are ``(easting, northing, elevation)``. Direction cosines use
        the same formula as the desurvey service, so the sign conventions cannot
        drift apart between the two.
        """
        def cosines(dip_deg: float, azimuth_deg: float) -> np.ndarray:
            inclination = math.radians(dip_deg)
            azimuth = math.radians(azimuth_deg)
            return np.array([
                math.cos(inclination) * math.sin(azimuth),
                math.cos(inclination) * math.cos(azimuth),
                math.sin(inclination),
            ])

        along_strike = cosines(0.0, self.strike_azimuth)
        down_dip = cosines(self.dip, self.strike_azimuth + 90.0)
        normal = np.cross(along_strike, down_dip)

        norm = np.linalg.norm(normal)
        if norm < _EPS:
            raise ValueError(
                "Degenerate ellipsoid orientation: the strike and dip vectors "
                "are parallel"
            )
        return np.vstack([along_strike, down_dip, normal / norm])


@dataclass(frozen=True)
class GradeGrid:
    """Interpolated grades on a regular grid.

    World coordinate of node ``(i, j, k)`` is
    ``origin + (i, j, k) * cell_size``, in ``(easting, northing, elevation)``.
    T006 relies on exactly this.

    ``nan`` marks a node with too few samples in range. It is not zero.
    """

    values: np.ndarray
    origin: Tuple[float, float, float]
    cell_size: float
    n_estimated: int
    n_total: int


def _grid_axes(
    positions: np.ndarray,
    cell_size: float,
    padding: float,
) -> Tuple[Tuple[float, float, float], Tuple[int, int, int]]:
    lower = positions.min(axis=0) - padding
    upper = positions.max(axis=0) + padding
    counts = np.maximum(
        np.ceil((upper - lower) / cell_size).astype(int) + 1, 1
    )
    return tuple(float(v) for v in lower), tuple(int(c) for c in counts)


def _blocks(counts: Sequence[int], budget: int):
    """Yield index ranges covering the grid in spatially compact blocks.

    Compactness is the point: a block's samples can be culled to those within
    ``max_range`` of the block's own bounding box, which is what keeps a large
    grid from comparing every node against every sample.
    """
    nx, ny, nz = counts
    side = max(1, int(round(budget ** (1.0 / 3.0))))
    for i0 in range(0, nx, side):
        for j0 in range(0, ny, side):
            for k0 in range(0, nz, side):
                yield (
                    (i0, min(i0 + side, nx)),
                    (j0, min(j0 + side, ny)),
                    (k0, min(k0 + side, nz)),
                )


def interpolate_grade_grid(
    composites: Sequence[TypedComposite],
    ellipsoid: SearchEllipsoid,
    sample_type_weights: Dict[str, float],
    cell_size: float = DEFAULT_CELL_SIZE,
    padding: float = DEFAULT_PADDING,
    power: float = DEFAULT_POWER,
    max_samples: int = DEFAULT_MAX_SAMPLES,
    min_samples: int = DEFAULT_MIN_SAMPLES,
    kernel: Optional[WeightKernel] = None,
) -> GradeGrid:
    """Interpolate composites onto a regular grid inside a search ellipsoid.

    ``ellipsoid`` and ``sample_type_weights`` are required: both encode
    geological decisions that must not be defaulted silently. A type absent from
    the mapping raises rather than assuming 1.0 -- a forgotten type is a
    forgotten decision.

    Determinism is guaranteed: composites are sorted before use, so the result
    does not depend on input order.
    """
    if cell_size <= 0:
        raise ValueError(f"cell_size must be positive, got {cell_size}")
    if padding < 0:
        raise ValueError(f"padding must not be negative, got {padding}")
    if min_samples < 1:
        raise ValueError(f"min_samples must be at least 1, got {min_samples}")
    if max_samples < min_samples:
        raise ValueError(
            f"max_samples ({max_samples}) must be at least min_samples "
            f"({min_samples})"
        )

    located = [c for c in composites
               if c.x is not None and c.y is not None and c.z is not None]
    missing = {c.sample_type for c in located} - set(sample_type_weights)
    if missing:
        raise ValueError(
            f"No weight given for sample type(s) {sorted(missing)}. State a "
            f"weight for every type present -- 0.0 excludes a type from grade "
            f"while leaving it available for geometry."
        )

    # Sorted so the result cannot depend on the order composites arrived in.
    located.sort(key=lambda c: (c.x, c.y, c.z, c.grade, c.sample_type))
    contributing = [c for c in located
                    if sample_type_weights[c.sample_type] > 0.0]

    if not located:
        empty = np.full((1, 1, 1), np.nan)
        return GradeGrid(empty, (0.0, 0.0, 0.0), cell_size, 0, 1)

    # The grid spans every located composite, including zero-weighted types:
    # they still describe where the deposit was sampled, and a grid that
    # stopped short of them would clip the domain on an arbitrary line.
    positions_all = np.array([[c.x, c.y, c.z] for c in located], dtype=float)
    origin, counts = _grid_axes(positions_all, cell_size, padding)
    values = np.full(counts, np.nan, dtype=float)
    n_total = int(np.prod(counts))

    if not contributing:
        return GradeGrid(values, origin, cell_size, 0, n_total)

    positions = np.array([[c.x, c.y, c.z] for c in contributing], dtype=float)
    grades = np.array([c.grade for c in contributing], dtype=float)
    type_weights = np.array(
        [sample_type_weights[c.sample_type] for c in contributing], dtype=float
    )

    axes = ellipsoid.axes()
    ranges = np.array([
        ellipsoid.range_major, ellipsoid.range_semi, ellipsoid.range_minor
    ], dtype=float)

    # Rotating into the ellipsoid frame and dividing by the ranges is a single
    # linear map, so the anisotropic distance is just the Euclidean distance in
    # transformed coordinates. That turns the search into a matrix product
    # instead of an (n_nodes, n_samples, 3) array of offsets -- the difference
    # between megabytes and gigabytes on a grid of any size.
    transform = axes.T / ranges
    sample_local = positions @ transform
    sample_sq = np.sum(sample_local ** 2, axis=1)

    weight_kernel = kernel if kernel is not None else inverse_distance_kernel(power)

    origin_array = np.array(origin, dtype=float)
    n_estimated = 0

    for (i0, i1), (j0, j1), (k0, k1) in _blocks(
        counts, max(1, _BLOCK_BUDGET // max(1, len(contributing)))
    ):
        gi = np.arange(i0, i1)
        gj = np.arange(j0, j1)
        gk = np.arange(k0, k1)
        block_shape = (len(gi), len(gj), len(gk))

        # Cull to samples that could reach this block at all.
        low = origin_array + np.array([i0, j0, k0]) * cell_size - ellipsoid.max_range
        high = (origin_array + np.array([i1 - 1, j1 - 1, k1 - 1]) * cell_size
                + ellipsoid.max_range)
        near = np.all((positions >= low) & (positions <= high), axis=1)
        if not near.any():
            continue

        near_grades = grades[near]
        near_type_weights = type_weights[near]
        near_local = sample_local[near]
        near_sq = sample_sq[near]

        mesh = np.stack(np.meshgrid(gi, gj, gk, indexing="ij"), axis=-1)
        node_positions = origin_array + mesh.reshape(-1, 3) * cell_size

        node_local = node_positions @ transform
        squared = (
            np.sum(node_local ** 2, axis=1)[:, None]
            + near_sq[None, :]
            - 2.0 * (node_local @ near_local.T)
        )
        # Cancellation can push a distance a hair below zero.
        d_aniso = np.sqrt(np.maximum(squared, 0.0))

        inside = d_aniso <= _ELLIPSOID_BOUNDARY
        if max_samples < inside.shape[1]:
            # Keep only the max_samples nearest per node; everything else is
            # pushed outside the ellipsoid so it cannot contribute.
            ranked = np.argpartition(
                np.where(inside, d_aniso, np.inf), max_samples - 1, axis=1
            )[:, :max_samples]
            keep = np.zeros_like(inside)
            np.put_along_axis(keep, ranked, True, axis=1)
            inside &= keep

        counts_per_node = inside.sum(axis=1)
        usable = counts_per_node >= min_samples

        weights = np.where(inside, weight_kernel(d_aniso), 0.0)
        weights *= near_type_weights[None, :]

        weight_sums = weights.sum(axis=1)
        usable &= weight_sums > 0.0

        block_values = np.full(len(node_positions), np.nan)
        if usable.any():
            block_values[usable] = (
                (weights[usable] * near_grades[None, :]).sum(axis=1)
                / weight_sums[usable]
            )
            n_estimated += int(usable.sum())

        values[i0:i1, j0:j1, k0:k1] = block_values.reshape(block_shape)

    return GradeGrid(
        values=values,
        origin=origin,
        cell_size=cell_size,
        n_estimated=n_estimated,
        n_total=n_total,
    )

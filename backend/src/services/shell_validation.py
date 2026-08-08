"""Geometric and statistical validation of a generated grade shell.

An unvalidated shell is a picture. Three numbers decide whether it is a domain.

**Watertight.** An open solid has no inside, so nothing downstream can flag a
block by it, and the fault is invisible in a screenshot.

**Metal capture.** The share of above-threshold metal that actually falls inside
the shell. Below roughly 90% the shell is leaving mineralisation outside, and
the usual cause is a search anisotropy pointed the wrong way.

**Internal dilution.** The share of enclosed sample length that sits *below*
threshold. Ten to twenty-five per cent is ordinary; much more means the shell has
smeared waste into the domain.

This module reports. It does not pass or fail a shell, and it returns no
``is_valid`` flag -- the competent person decides, with these numbers in front of
them. ``notes`` carries plain-language observations against the usual guidelines,
phrased as observations because that is what they are.

Statistics are broken out **by sample type** throughout. A shell that captures
core well and trench poorly is a specific, diagnosable problem, and pooling the
two hides exactly the thing worth seeing.
"""
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

from backend.src.services.isosurface import IsosurfaceResult, MeshComponent
from backend.src.services.sample_type_comparison import TypedComposite

_EPS = 1e-12
_AREA_EPS = 1e-9

# Guideline bands. These are conventional starting points for an open-pit gold
# domain, not thresholds this module enforces.
METAL_CAPTURE_GUIDELINE = 0.90
INTERNAL_DILUTION_GUIDELINE = 0.25

# A ray direction chosen to be awkward. A pure +x ray runs along the axis of
# every axis-aligned face a marching-cubes mesh is full of, and strikes shared
# edges and vertices often enough to return the wrong answer on real meshes.
_RAY_DIRECTION = np.array([1.0, 0.0013, 0.0007])
_RAY_DIRECTION = _RAY_DIRECTION / np.linalg.norm(_RAY_DIRECTION)


@dataclass(frozen=True)
class GeometryReport:
    is_watertight: bool
    n_boundary_edges: int
    n_nonmanifold_edges: int
    n_degenerate_faces: int
    n_duplicate_faces: int
    n_components: int
    total_volume: float
    bounding_box: Optional[Tuple[Tuple[float, float, float],
                                 Tuple[float, float, float]]]


@dataclass(frozen=True)
class TypeStats:
    sample_type: str
    n_inside: int
    n_outside: int
    length_inside: float
    mean_grade_inside: Optional[float]


@dataclass(frozen=True)
class StatisticsReport:
    threshold: float
    n_composites_inside: int
    n_composites_above_threshold: int
    metal_capture: Optional[float]
    internal_dilution: Optional[float]
    mean_grade_inside: Optional[float]
    by_sample_type: List[TypeStats]


@dataclass(frozen=True)
class ValidationReport:
    geometry: GeometryReport
    statistics: StatisticsReport
    notes: List[str] = field(default_factory=list)


def point_in_mesh(point: Sequence[float], component: MeshComponent) -> bool:
    """Ray casting: odd crossing count means inside.

    Uses a deliberately irrational direction (see ``_RAY_DIRECTION``) so the ray
    does not run along a face, through a shared edge, or through a vertex.
    """
    if not component.faces:
        return False

    vertices = np.asarray(component.vertices, dtype=float)
    faces = np.asarray(component.faces, dtype=int)
    origin = np.asarray(point, dtype=float)

    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]

    edge1 = v1 - v0
    edge2 = v2 - v0

    # Moller-Trumbore, vectorised over every triangle at once.
    h = np.cross(_RAY_DIRECTION, edge2)
    a = np.einsum("ij,ij->i", edge1, h)
    parallel = np.abs(a) < _AREA_EPS

    safe_a = np.where(parallel, 1.0, a)
    f = 1.0 / safe_a
    s = origin - v0
    u = f * np.einsum("ij,ij->i", s, h)

    q = np.cross(s, edge1)
    v = f * (q @ _RAY_DIRECTION)
    t = f * np.einsum("ij,ij->i", edge2, q)

    hit = (
        ~parallel
        & (u >= 0.0) & (u <= 1.0)
        & (v >= 0.0) & (u + v <= 1.0)
        & (t > _AREA_EPS)
    )
    return bool(np.count_nonzero(hit) % 2 == 1)


def _point_in_result(point: Sequence[float], result: IsosurfaceResult) -> bool:
    """Inside any component counts as inside the shell."""
    return any(point_in_mesh(point, c) for c in result.components)


def _geometry(result: IsosurfaceResult) -> GeometryReport:
    edge_counts: Counter = Counter()
    face_counts: Counter = Counter()
    n_degenerate = 0
    lows: List[np.ndarray] = []
    highs: List[np.ndarray] = []

    for component in result.components:
        vertices = np.asarray(component.vertices, dtype=float)
        if len(vertices):
            lows.append(vertices.min(axis=0))
            highs.append(vertices.max(axis=0))

        for face in component.faces:
            a, b, c = face
            if len({a, b, c}) < 3:
                n_degenerate += 1
                continue

            area = 0.5 * np.linalg.norm(np.cross(
                vertices[b] - vertices[a], vertices[c] - vertices[a]
            ))
            if area < _AREA_EPS:
                n_degenerate += 1
                continue

            # Keyed per component so two solids sharing a coordinate are not
            # mistaken for one another's neighbours.
            face_counts[(id(component), frozenset(face))] += 1
            for u, v in ((a, b), (b, c), (c, a)):
                edge_counts[(id(component), frozenset((u, v)))] += 1

    n_boundary = sum(1 for n in edge_counts.values() if n == 1)
    n_nonmanifold = sum(1 for n in edge_counts.values() if n > 2)
    n_duplicate = sum(n - 1 for n in face_counts.values() if n > 1)

    if lows:
        low = np.min(np.vstack(lows), axis=0)
        high = np.max(np.vstack(highs), axis=0)
        bounding_box = (
            (float(low[0]), float(low[1]), float(low[2])),
            (float(high[0]), float(high[1]), float(high[2])),
        )
    else:
        bounding_box = None

    return GeometryReport(
        is_watertight=bool(edge_counts) and n_boundary == 0 and n_nonmanifold == 0,
        n_boundary_edges=n_boundary,
        n_nonmanifold_edges=n_nonmanifold,
        n_degenerate_faces=n_degenerate,
        n_duplicate_faces=n_duplicate,
        n_components=len(result.components),
        total_volume=result.total_volume,
        bounding_box=bounding_box,
    )


def validate_shell(
    result: IsosurfaceResult,
    composites: Sequence[TypedComposite],
    threshold: float,
) -> ValidationReport:
    """Geometry and grade statistics for a shell against its own composites."""
    geometry = _geometry(result)

    located = [c for c in composites
               if c.x is not None and c.y is not None and c.z is not None]

    inside_flags = [
        _point_in_result((c.x, c.y, c.z), result) for c in located
    ]
    inside = [c for c, flag in zip(located, inside_flags) if flag]
    above = [c for c in located if c.grade >= threshold]

    metal_above_total = sum(c.grade * c.length for c in above)
    metal_inside = sum(c.grade * c.length for c in inside if c.grade >= threshold)

    # The denominator is every above-threshold composite anywhere, not just the
    # ones inside. Inside-over-inside is trivially 1.0 and says nothing.
    metal_capture = (
        metal_inside / metal_above_total if metal_above_total > _EPS else None
    )

    length_inside = sum(c.length for c in inside)
    waste_length_inside = sum(c.length for c in inside if c.grade < threshold)
    internal_dilution = (
        waste_length_inside / length_inside if length_inside > _EPS else None
    )

    mean_grade_inside = (
        sum(c.grade * c.length for c in inside) / length_inside
        if length_inside > _EPS else None
    )

    by_type: List[TypeStats] = []
    for sample_type in sorted({c.sample_type for c in located}):
        typed_inside = [c for c in inside if c.sample_type == sample_type]
        typed_all = [c for c in located if c.sample_type == sample_type]
        typed_length = sum(c.length for c in typed_inside)
        by_type.append(TypeStats(
            sample_type=sample_type,
            n_inside=len(typed_inside),
            n_outside=len(typed_all) - len(typed_inside),
            length_inside=typed_length,
            mean_grade_inside=(
                sum(c.grade * c.length for c in typed_inside) / typed_length
                if typed_length > _EPS else None
            ),
        ))

    statistics = StatisticsReport(
        threshold=threshold,
        n_composites_inside=len(inside),
        n_composites_above_threshold=len(above),
        metal_capture=metal_capture,
        internal_dilution=internal_dilution,
        mean_grade_inside=mean_grade_inside,
        by_sample_type=by_type,
    )

    return ValidationReport(
        geometry=geometry,
        statistics=statistics,
        notes=_notes(geometry, statistics),
    )


def _notes(geometry: GeometryReport, statistics: StatisticsReport) -> List[str]:
    """Observations against the usual guidelines. Never a verdict."""
    notes: List[str] = []

    if geometry.n_components == 0:
        notes.append("No shell was produced at this threshold.")
        return notes

    if not geometry.is_watertight:
        notes.append(
            "Shell is not closed: {} boundary edge(s) and {} non-manifold "
            "edge(s). Nothing downstream can reliably flag material inside "
            "an open solid.".format(
                geometry.n_boundary_edges, geometry.n_nonmanifold_edges)
        )

    if geometry.n_degenerate_faces:
        notes.append(
            "{} degenerate triangle(s) carrying no area.".format(
                geometry.n_degenerate_faces)
        )

    capture = statistics.metal_capture
    if capture is None:
        notes.append(
            "Metal capture is undefined: no composite reaches the threshold."
        )
    elif capture < METAL_CAPTURE_GUIDELINE:
        notes.append(
            "Metal capture {:.1%} is below the {:.0%} guideline -- the shell "
            "leaves above-threshold material outside it. A search anisotropy "
            "pointed away from the structure is the usual cause.".format(
                capture, METAL_CAPTURE_GUIDELINE)
        )

    dilution = statistics.internal_dilution
    if dilution is not None and dilution > INTERNAL_DILUTION_GUIDELINE:
        notes.append(
            "Internal dilution {:.1%} is above the {:.0%} guideline -- the "
            "shell encloses a large share of below-threshold ground.".format(
                dilution, INTERNAL_DILUTION_GUIDELINE)
        )

    for stats in statistics.by_sample_type:
        if stats.n_inside == 0 and stats.n_outside > 0:
            notes.append(
                "No {} composite falls inside the shell ({} outside).".format(
                    stats.sample_type, stats.n_outside)
            )

    return notes

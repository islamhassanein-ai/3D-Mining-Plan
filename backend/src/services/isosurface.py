"""Iso-surface extraction from an interpolated grade grid.

The grade shell is the surface of the interpolant at the chosen threshold. Two
details decide whether the result is usable, and both are geological rather
than incidental.

**Unsampled ground closes the surface inward.** ``nan`` from the interpolant
means nobody looked there, so before extraction every ``nan`` becomes a sentinel
strictly below the threshold. The surface then closes against unsampled ground
rather than running on to the edge of the grid. Without this a shell claims the
mineralisation continues into rock that has never been tested, which is how
tonnes appear in ground nobody drilled.

**The volume is padded before extraction.** A shell touching the grid boundary
would otherwise extract as an open sheet -- no inside, nothing to flag blocks
against, and a rendering with its guts showing. One layer of sentinel on all six
faces closes it, and the index-to-world conversion subtracts that layer again.

Vertices come out in raw project coordinates, ``(easting, northing, elevation)``,
with **no Y-up swap**. The swap belongs to the renderer at
``frontend/src/scene/wireframes.js``; applying it here as well mirrors the model.
``backend/src/services/obj_geometry.py`` carries the same warning for the same
reason.

What this produces is a *domain envelope* -- a geometric boundary drawn around
interpolated grade. It is not a resource, and its volume is a property of the
shell rather than a statement about contained metal.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from skimage import measure

from backend.src.services.grade_interpolant import GradeGrid

# One cell of sentinel on every face, so a shell reaching the grid edge still
# closes. Every index-to-world conversion subtracts it again.
_PAD = 1

_EPS = 1e-12


@dataclass(frozen=True)
class MeshComponent:
    """One connected solid, in project coordinates."""

    vertices: List[Tuple[float, float, float]]
    faces: List[Tuple[int, int, int]]
    volume: float


@dataclass(frozen=True)
class IsosurfaceResult:
    components: List[MeshComponent]
    threshold: float
    total_volume: float


def _component_volume(
    vertices: np.ndarray,
    faces: np.ndarray,
) -> float:
    """Absolute volume by the signed-tetrahedron sum over the triangles.

    Each triangle forms a tetrahedron with the origin; the signed volumes cancel
    everywhere except inside the closed surface. Taking the absolute value at
    the end makes the result independent of triangle winding.
    """
    if len(faces) == 0:
        return 0.0

    a = vertices[faces[:, 0]]
    b = vertices[faces[:, 1]]
    c = vertices[faces[:, 2]]
    return float(abs(np.sum(np.einsum("ij,ij->i", a, np.cross(b, c))) / 6.0))


def _connected_components(
    faces: np.ndarray,
    n_vertices: int,
) -> List[np.ndarray]:
    """Split faces into groups sharing vertices, by union-find."""
    parent = np.arange(n_vertices)

    def find(index: int) -> int:
        root = index
        while parent[root] != root:
            root = parent[root]
        while parent[index] != root:
            parent[index], index = root, parent[index]
        return root

    for face in faces:
        first = find(face[0])
        for other in face[1:]:
            second = find(other)
            if first != second:
                parent[second] = first

    groups: Dict[int, List[int]] = {}
    for face_index, face in enumerate(faces):
        groups.setdefault(find(face[0]), []).append(face_index)

    return [np.array(indices) for indices in groups.values()]


def extract_isosurface(
    grid: GradeGrid,
    threshold: float,
    split_components: bool = True,
    min_volume: float = 0.0,
) -> IsosurfaceResult:
    """Extract the surface of ``grid`` at ``threshold``.

    ``nan`` nodes are treated as below threshold so the surface closes against
    unsampled ground. Returns an empty result rather than raising when no
    surface exists -- "no material meets this threshold" is a legitimate
    geological answer, not an error.
    """
    values = np.asarray(grid.values, dtype=float)

    finite = values[np.isfinite(values)]
    floor = float(finite.min()) if finite.size else threshold
    sentinel = min(threshold, floor) - 1.0

    filled = np.where(np.isfinite(values), values, sentinel)
    padded = np.pad(filled, _PAD, mode="constant", constant_values=sentinel)

    if finite.size == 0 or finite.max() < threshold:
        # Nothing was estimated, or nothing estimated reaches the threshold.
        # "No material meets this cut-off" is a legitimate answer.
        return IsosurfaceResult(components=[], threshold=threshold,
                                total_volume=0.0)

    # Note the case that is deliberately NOT short-circuited: when every
    # estimated node is above the threshold, the surface returned is the
    # boundary of the estimated region itself. That is the truthful answer --
    # the cut-off has selected everything that was sampled -- and it is far
    # more use than an empty result, because an implausibly large envelope
    # makes a mis-set threshold obvious instead of silent. It is still not
    # extrapolation: the envelope stops where the interpolant stopped.

    try:
        verts, faces, _normals, _values = measure.marching_cubes(
            padded, level=threshold
        )
    except (ValueError, RuntimeError):
        return IsosurfaceResult(components=[], threshold=threshold,
                                total_volume=0.0)

    if len(faces) == 0:
        return IsosurfaceResult(components=[], threshold=threshold,
                                total_volume=0.0)

    # Index space -> world. The -_PAD undoes the pad added above; getting this
    # wrong shifts the entire shell by one cell, which is invisible unless you
    # check it against the collars.
    origin = np.asarray(grid.origin, dtype=float)
    world = origin + (verts - _PAD) * grid.cell_size

    if split_components:
        groups = _connected_components(faces, len(world))
    else:
        groups = [np.arange(len(faces))]

    components: List[MeshComponent] = []
    for face_indices in groups:
        group_faces = faces[face_indices]
        used = np.unique(group_faces)
        remap = np.full(len(world), -1, dtype=int)
        remap[used] = np.arange(len(used))

        local_vertices = world[used]
        local_faces = remap[group_faces]
        volume = _component_volume(local_vertices, local_faces)

        if volume < min_volume:
            continue

        components.append(MeshComponent(
            vertices=[tuple(float(c) for c in v) for v in local_vertices],
            faces=[tuple(int(i) for i in f) for f in local_faces],
            volume=volume,
        ))

    components.sort(key=lambda c: c.volume, reverse=True)

    return IsosurfaceResult(
        components=components,
        threshold=threshold,
        total_volume=float(sum(c.volume for c in components)),
    )


def mesh_to_obj(result: IsosurfaceResult, name: str = "grade_shell") -> str:
    """OBJ text for the whole result, one ``o`` group per component.

    Vertices are written in raw project order -- easting, northing, elevation --
    matching what ``obj_geometry.parse_obj`` reads and what the viewer renders.
    Face indices are 1-based, as every OBJ reader expects.
    """
    lines: List[str] = [
        "# Grade domain shell at {} (units: project CRS metres)".format(
            result.threshold
        ),
        "# Vertices are (easting, northing, elevation) -- no Y-up swap.",
    ]

    offset = 1
    for index, component in enumerate(result.components):
        lines.append("o {}_{}".format(name, index))
        for x, y, z in component.vertices:
            lines.append("v {:.6f} {:.6f} {:.6f}".format(x, y, z))
        for i, j, k in component.faces:
            lines.append("f {} {} {}".format(i + offset, j + offset, k + offset))
        offset += len(component.vertices)

    return "\n".join(lines) + "\n"

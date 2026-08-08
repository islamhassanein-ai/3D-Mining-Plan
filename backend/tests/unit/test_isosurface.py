"""Tests for iso-surface extraction.

The watertightness check is the most important test here: an open solid has no
inside, so nothing downstream can flag blocks by it, and the failure is not
visible in a screenshot. The world-coordinate test is next -- forgetting to
subtract the pad shifts the whole shell by one cell, which looks fine until
someone overlays the collars.
"""
import math
from collections import Counter

import numpy as np
import pytest

from backend.src.services.grade_interpolant import GradeGrid
from backend.src.services.isosurface import (
    IsosurfaceResult,
    extract_isosurface,
    mesh_to_obj,
)
from backend.src.services.obj_geometry import parse_obj


def _sphere_grid(size=40, cell=1.0, origin=(0.0, 0.0, 0.0), centre=None,
                 peak=10.0):
    """Values of ``peak - distance_from_centre``: the level set at ``peak - r``
    is a sphere of radius ``r``."""
    if centre is None:
        centre = (size / 2.0, size / 2.0, size / 2.0)
    i, j, k = np.meshgrid(
        np.arange(size), np.arange(size), np.arange(size), indexing="ij"
    )
    distance = np.sqrt(
        (i - centre[0]) ** 2 + (j - centre[1]) ** 2 + (k - centre[2]) ** 2
    )
    return GradeGrid(
        values=peak - distance,
        origin=origin,
        cell_size=cell,
        n_estimated=size ** 3,
        n_total=size ** 3,
    )


def _edge_counts(component):
    edges = Counter()
    for a, b, c in component.faces:
        for u, v in ((a, b), (b, c), (c, a)):
            edges[frozenset((u, v))] += 1
    return edges


# --- volume and closure ------------------------------------------------------

def test_sphere_volume_is_recovered_within_five_percent():
    # Level set at 5.0 is a sphere of radius 5: 4/3 pi 5^3 = 523.6
    result = extract_isosurface(_sphere_grid(), threshold=5.0)

    expected = 4.0 / 3.0 * math.pi * 125.0
    assert len(result.components) == 1
    # Marching cubes under-reports slightly on a coarse grid. 5% is the honest
    # tolerance; do not tighten it and do not adjust the volume formula to hit
    # a smaller one.
    assert abs(result.total_volume - expected) / expected < 0.05


def test_the_mesh_is_watertight():
    # Every edge shared by exactly two triangles. An open surface has no
    # inside, and nothing downstream can flag blocks against it.
    result = extract_isosurface(_sphere_grid(), threshold=5.0)

    for component in result.components:
        counts = _edge_counts(component)
        assert counts, "component has no edges"
        assert all(n == 2 for n in counts.values()), \
            "mesh is not watertight: {} boundary or non-manifold edge(s)".format(
                sum(1 for n in counts.values() if n != 2))


def test_nan_closes_the_surface_and_does_not_inflate_it():
    # Blank an outer shell of nodes: unsampled ground must close the surface
    # inward, never open it or grow it.
    grid = _sphere_grid()
    values = grid.values.copy()
    values[:4, :, :] = np.nan
    values[-4:, :, :] = np.nan
    blanked = GradeGrid(values, grid.origin, grid.cell_size,
                        grid.n_estimated, grid.n_total)

    intact = extract_isosurface(grid, threshold=5.0)
    result = extract_isosurface(blanked, threshold=5.0)

    for component in result.components:
        counts = _edge_counts(component)
        assert all(n == 2 for n in counts.values())
    assert result.total_volume <= intact.total_volume + 1e-6


def test_a_shell_reaching_the_grid_edge_still_closes():
    # Threshold low enough that the level set runs past the array boundary.
    # Without the sentinel pad this extracts as an open sheet.
    result = extract_isosurface(_sphere_grid(size=20), threshold=-5.0)

    assert result.components
    for component in result.components:
        counts = _edge_counts(component)
        assert all(n == 2 for n in counts.values())


# --- world coordinates -------------------------------------------------------

def test_vertices_are_in_project_coordinates_with_no_axis_swap():
    origin = (500000.0, 4500000.0, 1000.0)
    grid = _sphere_grid(size=40, cell=1.0, origin=origin)

    result = extract_isosurface(grid, threshold=5.0)
    vertices = np.array(result.components[0].vertices)

    centre = vertices.mean(axis=0)
    # Sphere centre is node (20,20,20) -> origin + 20 * cell
    assert abs(centre[0] - (origin[0] + 20.0)) < grid.cell_size
    assert abs(centre[1] - (origin[1] + 20.0)) < grid.cell_size
    assert abs(centre[2] - (origin[2] + 20.0)) < grid.cell_size

    # Elevation must sit around 1000, not around 4500000. A Y-up swap puts
    # northing into z and this fails by three orders of magnitude.
    assert 900.0 < centre[2] < 1100.0


def test_cell_size_scales_the_result():
    fine = extract_isosurface(_sphere_grid(size=40, cell=1.0), threshold=5.0)
    coarse = extract_isosurface(_sphere_grid(size=40, cell=2.0), threshold=5.0)

    # Doubling the cell size multiplies every length by two, so volume by eight.
    assert math.isclose(coarse.total_volume, fine.total_volume * 8.0, rel_tol=0.02)


# --- components --------------------------------------------------------------

def _two_spheres(separation=24, second_peak=10.0):
    """Two spheres. ``second_peak`` below 10.0 makes the second one smaller,
    which is what the min_volume filter needs to have something to choose."""
    size = 48
    i, j, k = np.meshgrid(
        np.arange(size), np.arange(size), np.arange(size), indexing="ij"
    )
    first = np.sqrt((i - 12) ** 2 + (j - 12) ** 2 + (k - 12) ** 2)
    second = np.sqrt(
        (i - (12 + separation)) ** 2 + (j - 12) ** 2 + (k - 12) ** 2
    )
    values = np.maximum(10.0 - first, second_peak - second)
    return GradeGrid(values, (0.0, 0.0, 0.0), 1.0, size ** 3, size ** 3)


def test_separated_bodies_split_into_components():
    result = extract_isosurface(_two_spheres(), threshold=5.0,
                                split_components=True)

    assert len(result.components) == 2
    for component in result.components:
        counts = _edge_counts(component)
        assert all(n == 2 for n in counts.values())
    assert math.isclose(
        result.total_volume,
        sum(c.volume for c in result.components),
        rel_tol=1e-9,
    )


def test_components_can_be_left_joined():
    result = extract_isosurface(_two_spheres(), threshold=5.0,
                                split_components=False)

    assert len(result.components) == 1


def test_min_volume_drops_the_small_body():
    # Radius 5 and radius 2.5 at threshold 5.0: volumes about 524 and 65.
    grid = _two_spheres(second_peak=7.5)
    everything = extract_isosurface(grid, threshold=5.0)
    volumes = sorted(c.volume for c in everything.components)

    assert len(everything.components) == 2
    assert volumes[0] < volumes[1] / 2.0, "fixture spheres are not distinct sizes"

    filtered = extract_isosurface(
        grid, threshold=5.0, min_volume=volumes[0] + 1.0
    )

    assert len(filtered.components) == 1
    assert math.isclose(filtered.total_volume, volumes[1], rel_tol=1e-9)


def test_components_are_ordered_largest_first():
    result = extract_isosurface(_two_spheres(separation=20), threshold=5.0)

    volumes = [c.volume for c in result.components]
    assert volumes == sorted(volumes, reverse=True)


# --- empty results -----------------------------------------------------------

def test_a_threshold_above_everything_yields_no_surface():
    result = extract_isosurface(_sphere_grid(), threshold=999.0)

    assert result.components == []
    assert result.total_volume == 0.0
    assert mesh_to_obj(result).strip().startswith("#")


def test_a_threshold_below_everything_returns_the_estimated_envelope():
    # Every estimated node qualifies, so the shell is the boundary of the
    # estimated region. That is the truthful answer and it makes a mis-set
    # cut-off obvious; an empty result would hide it. Still not extrapolation:
    # the envelope stops where the interpolant stopped.
    result = extract_isosurface(_sphere_grid(size=20), threshold=-999.0)

    assert len(result.components) == 1
    assert result.total_volume > 0.0
    counts = _edge_counts(result.components[0])
    assert all(n == 2 for n in counts.values())


def test_a_grid_with_nothing_above_the_threshold_yields_no_surface():
    result = extract_isosurface(_sphere_grid(), threshold=999.0)

    assert result.components == []
    assert result.total_volume == 0.0


def test_an_all_nan_grid_yields_no_surface():
    grid = GradeGrid(np.full((10, 10, 10), np.nan), (0.0, 0.0, 0.0), 1.0, 0, 1000)

    result = extract_isosurface(grid, threshold=1.0)

    assert result.components == []
    assert result.total_volume == 0.0


# --- OBJ output --------------------------------------------------------------

def test_obj_round_trips_through_the_projects_own_parser():
    result = extract_isosurface(_sphere_grid(), threshold=5.0)

    parsed = parse_obj(mesh_to_obj(result))

    assert len(parsed["vertices"]) == len(result.components[0].vertices)
    assert len(parsed["faces"]) == len(result.components[0].faces)
    for expected, actual in zip(result.components[0].vertices[0],
                                parsed["vertices"][0]):
        assert math.isclose(expected, actual, abs_tol=1e-6)


def test_obj_face_indices_are_one_based():
    result = extract_isosurface(_sphere_grid(size=20), threshold=5.0)

    indices = [
        int(token)
        for line in mesh_to_obj(result).splitlines() if line.startswith("f ")
        for token in line.split()[1:]
    ]

    assert min(indices) == 1


def test_obj_numbers_vertices_continuously_across_components():
    result = extract_isosurface(_two_spheres(), threshold=5.0)
    text = mesh_to_obj(result)

    n_vertices = sum(1 for line in text.splitlines() if line.startswith("v "))
    indices = [
        int(token)
        for line in text.splitlines() if line.startswith("f ")
        for token in line.split()[1:]
    ]

    assert max(indices) == n_vertices
    parsed = parse_obj(text)
    assert len(parsed["vertices"]) == n_vertices


def test_obj_of_an_empty_result_has_no_geometry():
    empty = IsosurfaceResult(components=[], threshold=1.0, total_volume=0.0)
    text = mesh_to_obj(empty)

    assert not [line for line in text.splitlines() if line.startswith(("v ", "f "))]
    assert parse_obj(text) == {"vertices": [], "faces": []}

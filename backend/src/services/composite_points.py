"""Database assay and trench records to 3D-located composites.

This is the only module in the grade-shell feature that touches the database.
Everything downstream consumes ``TypedComposite`` and knows nothing about
SQLAlchemy; everything upstream (``compositing``, ``sample_type_comparison``)
is pure. The transformation itself is kept pure too -- ``build_drillhole_composites``
and ``build_trench_composites`` take plain dicts and are unit-tested without a
database -- so that only the querying, which is mechanical, needs a session.

What is excluded, and why each exclusion matters:

* **Superseded records.** Both ``AssayInterval`` and ``Trench`` carry
  ``superseded_by``, pointing at the row that replaced them after a re-import.
  A superseded row is a previous version of corrected data. There are currently
  980 superseded trench rows in this database, so forgetting the filter would
  roughly double the trench population with stale duplicates.

* **Planned holes.** A collar with ``hole_status == 'planned'`` has not been
  drilled. Any interval hanging off it is a *target* -- the grade someone hopes
  to intersect -- not a result. Letting targets into a grade shell would
  manufacture mineralisation that has never been sampled, which is the most
  serious error available in this pipeline.

* **Unassayed ground.** ``grade_value IS NULL`` means logged but never assayed.
  ``compositing`` drops it without letting it dilute anything, and a genuine
  0.0 g/t is kept and composited normally.

* **Holes without surveys.** Without survey stations there is no trajectory,
  and a hole's samples cannot be placed in space. ``scene.py`` falls back to an
  assumed vertical hole so that something is *drawn*; that is right for a
  picture and wrong here, because a fabricated trajectory would put real assays
  at invented coordinates and those coordinates would go on to shape a shell.
  Such holes are skipped and reported.

Coordinate and geometry conventions are inherited, not re-derived. Drillhole
trajectories come from ``desurvey.compute_minimum_curvature_trace`` and are
extended and sampled with the existing ``downhole_log`` helpers, so the dip
sign convention (negative is downward) and the raw UTM axis order
``(easting, northing, elevation)`` are whatever the rest of the application
already does. Nothing here swaps an axis or re-implements a trace.

Trenches keep their own rule, taken from the combined-CSV import: ``dip`` and
``azimuth`` on a trench row describe the ground slope at the start point only,
never a trajectory, so a trench sample stays at the elevation its row states.
See ``combined_routing`` for why -- applying dip along a trench's length puts a
145 m trench 40 m in the air.

A trench sample is placed at the coordinates its own row carries, which are
accurate and authoritative and mark the **midpoint of the sample interval**.
That makes trench placement consistent with the drillhole path, where each
composite is also placed at its midpoint. Trench samples are not composited
along chainage; ``build_trench_composites`` documents why.
"""
import uuid as uuid_module
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from backend.src.models.assay_interval import AssayInterval
from backend.src.models.collar import Collar
from backend.src.models.survey import Survey
from backend.src.models.trench import Trench
from backend.src.services.compositing import (
    DEFAULT_COMPOSITE_LENGTH,
    RawInterval,
    composite_intervals,
)
from backend.src.services.desurvey import compute_minimum_curvature_trace
from backend.src.services.downhole_log import (
    compute_total_depth,
    extend_trace_to_depth,
    interpolate_trace_position,
)
from backend.src.services.sample_type_comparison import TypedComposite

# Collar-borne sample types. RC is reverse circulation -- a genuinely different
# sample support from diamond core, but both are drilling, and the reference
# population for the trench comparison is "drilled" as against "surface". RC
# hole counts are reported separately so the distinction stays visible.
DRILLHOLE_SAMPLE_TYPE = "DDH"

# Trench-borne sample types, matching combined_routing._TRENCH_TYPES.
TRENCH_SAMPLE_TYPES = {"TR", "CH", "FC"}
DEFAULT_TRENCH_SAMPLE_TYPE = "TR"

# hole_status values meaning "not yet drilled". NULL reads as drilled, matching
# the migration note on Collar.hole_status.
PLANNED_STATUS = "planned"

_EPS = 1e-9


@dataclass
class ExtractionReport:
    """Provenance for one extraction run.

    Every record that does not become a composite is accounted for here. A
    silent exclusion is indistinguishable from a bug, and both look like a
    smaller orebody.
    """

    n_ddh_composites: int = 0
    n_trench_composites: int = 0
    composites_by_type: Dict[str, int] = field(default_factory=dict)
    collars_by_hole_type: Dict[str, int] = field(default_factory=dict)
    n_collars_considered: int = 0
    n_trench_lines_considered: int = 0
    n_assay_intervals_read: int = 0
    n_trench_rows_read: int = 0
    n_unassayed_assay_intervals: int = 0
    n_unassayed_trench_rows: int = 0
    skipped: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    grade_unit: Optional[str] = None


@dataclass
class ExtractionResult:
    composites: List[TypedComposite]
    report: ExtractionReport


def _as_float(value: Any) -> Optional[float]:
    """Numeric columns arrive as ``Decimal``; ``None`` stays ``None``.

    The ``None`` passthrough is the whole point: it is what keeps unassayed
    ground distinguishable from a genuine 0.0 g/t all the way down.
    """
    return None if value is None else float(value)


# ---------------------------------------------------------------------------
# Pure transformations -- no database access below this line until the queries
# ---------------------------------------------------------------------------

def build_drillhole_composites(
    collar: Dict[str, Any],
    surveys: Sequence[Dict[str, float]],
    intervals: Sequence[RawInterval],
    composite_length: float = DEFAULT_COMPOSITE_LENGTH,
) -> tuple:
    """Composites for one hole, positioned along its desurveyed trace.

    ``collar`` needs ``hole_id``, ``easting``, ``northing``, ``elevation``.
    Returns ``(composites, warnings)``. A hole with no surveys returns no
    composites -- see the module docstring on why no vertical fallback is
    applied here.

    Each composite is placed at its **midpoint depth**, measured absolutely
    from the collar along the full trajectory, which is the convention
    ``downhole_log`` documents for every position in this application.
    """
    warnings: List[str] = []

    if not surveys:
        return [], warnings

    composites = composite_intervals(list(intervals), composite_length)
    if not composites:
        return [], warnings

    trace = compute_minimum_curvature_trace(
        collar["easting"], collar["northing"], collar["elevation"], list(surveys)
    )
    if not trace:
        return [], warnings

    # Survey stations routinely stop short of the deepest assay. Without
    # extending, every composite past the last station clamps onto the same
    # coordinate and stacks up in one spot.
    deepest = max(c.to_depth for c in composites)
    total_depth = compute_total_depth(trace, [deepest])
    trace = extend_trace_to_depth(trace, total_depth)

    surveyed_depth = max(s["depth"] for s in surveys)
    if deepest - surveyed_depth > _EPS:
        warnings.append(
            f"{collar['hole_id']}: assays reach {deepest:.1f} m but surveys stop "
            f"at {surveyed_depth:.1f} m; the tail is projected along the last "
            f"station's orientation"
        )

    located = []
    for composite in composites:
        midpoint = (composite.from_depth + composite.to_depth) / 2.0
        x, y, z = interpolate_trace_position(trace, midpoint)
        located.append(
            TypedComposite(
                grade=composite.grade,
                length=composite.length,
                sample_type=DRILLHOLE_SAMPLE_TYPE,
                x=x,
                y=y,
                z=z,
            )
        )

    return located, warnings


def build_trench_composites(
    points: Sequence[Dict[str, Any]],
    length_when_unspecified: Optional[float] = None,
) -> tuple:
    """Composites for one trench line, one per assayed sample row.

    ``points`` are the trench's rows in ``point_order``, each carrying
    ``easting``, ``northing``, ``elevation``, ``grade_value``, ``hole_type``,
    and optionally ``from_depth``/``to_depth``. Returns
    ``(composites, warnings, n_unassayed)``.

    Each row's stored coordinates are authoritative and mark the **midpoint of
    the sample interval**, so a sample needs no interpolation to be placed.

    **Why samples are not composited along chainage.** The specification for
    this task called for treating ``from_depth``/``to_depth`` as chainage along
    the trench floor, compositing along it, and interpolating each composite's
    position along the polyline. Beyond being unnecessary given authoritative
    coordinates, the database does not support it:

    1. **Chainage is not unique, so it cannot position a sample.** AAF002 and
       AAF004A carry pairs of samples sharing a chainage -- 0-1 m holds both
       5.86 and 2.82 g/t -- separated by only 0.15-0.49 m in plan but around a
       metre in elevation, with consecutive sample numbers. They are a face
       sampled at two heights, upper and lower channel. Chainage is a
       one-dimensional coordinate describing a two-dimensional face and cannot
       tell those apart; elevation can, and elevation lives only in the stored
       coordinates. In AAF004A the pair differs by 0.06 against 7.86 g/t, so
       collapsing them is not a rounding matter.

    2. **There is no stored polyline to interpolate along.** This table holds
       points; the polyline exists only as those points joined in point_order.
       Nothing in the schema records a surveyed centreline, so a "position along
       the polyline" can carry no information the coordinates do not already
       hold.

    3. **Chainage is sometimes absent.** The legacy trench uploaders record only
       a point and a grade, leaving ``from_depth``/``to_depth`` NULL.

    Chainage itself is sound where it exists -- in the real dataset it agrees
    with cumulative coordinate distance to about 1-2% -- and it is the right
    source for **sample length**. It is simply not a position in three
    dimensions.

    What each row does state unambiguously is its own position and its own
    grade, so that is what is used: one composite per assayed row, at the
    coordinates the row carries. Sample length comes from
    ``to_depth - from_depth`` where present. Where it is absent there is no
    length in the data, and ``length_when_unspecified`` decides: ``None`` (the
    default) excludes the row rather than inventing a support, or a stated
    number includes it under that assumption.
    """
    warnings: List[str] = []
    composites: List[TypedComposite] = []
    n_unassayed = 0

    for point in points:
        grade = _as_float(point.get("grade_value"))
        if grade is None:
            # Includes the generated far-end vertex of a single-row trench,
            # which exists to give the polyline a second point and was never
            # a sample.
            n_unassayed += 1
            continue

        easting = _as_float(point.get("easting"))
        northing = _as_float(point.get("northing"))
        elevation = _as_float(point.get("elevation"))
        if easting is None or northing is None or elevation is None:
            warnings.append(
                f"{point.get('trench_id')}: assayed row at point_order "
                f"{point.get('point_order')} has no complete position and "
                f"cannot be placed"
            )
            continue

        from_depth = _as_float(point.get("from_depth"))
        to_depth = _as_float(point.get("to_depth"))
        if from_depth is not None and to_depth is not None and to_depth > from_depth:
            length = to_depth - from_depth
        elif length_when_unspecified is not None:
            length = length_when_unspecified
        else:
            warnings.append(
                f"{point.get('trench_id')}: assayed row at point_order "
                f"{point.get('point_order')} states no sample length; excluded "
                f"(pass length_when_unspecified to include it under a stated "
                f"assumption)"
            )
            continue

        raw_type = point.get("hole_type")
        sample_type = (raw_type or "").strip().upper()
        if sample_type not in TRENCH_SAMPLE_TYPES:
            sample_type = DEFAULT_TRENCH_SAMPLE_TYPE

        composites.append(
            TypedComposite(
                grade=grade,
                length=length,
                sample_type=sample_type,
                x=easting,
                y=northing,
                z=elevation,
            )
        )

    return composites, warnings, n_unassayed


# ---------------------------------------------------------------------------
# Database access
# ---------------------------------------------------------------------------

def extract_composite_points(
    db: Session,
    project_id,
    composite_length: float = DEFAULT_COMPOSITE_LENGTH,
    trench_length_when_unspecified: Optional[float] = None,
) -> ExtractionResult:
    """Load one project's assayed data as 3D-located composites.

    Raises ``ValueError`` when the project's assays carry more than one grade
    unit. Converting between them would be a data decision made silently in the
    wrong layer -- ppm and g/t are numerically identical for gold, but a file
    that mixes them is a file whose provenance is not understood.
    """
    if isinstance(project_id, str):
        project_id = uuid_module.UUID(project_id)

    report = ExtractionReport()
    composites: List[TypedComposite] = []

    collars = db.query(Collar).filter(
        Collar.project_id == project_id,
        Collar.superseded_by.is_(None),
    ).order_by(Collar.hole_id).all()

    for collar in collars:
        hole_type = (collar.hole_type or "").strip().upper() or "UNSPECIFIED"
        report.collars_by_hole_type[hole_type] = (
            report.collars_by_hole_type.get(hole_type, 0) + 1
        )

    for collar in collars:
        if (collar.hole_status or "").strip().lower() == PLANNED_STATUS:
            report.skipped.append(
                f"{collar.hole_id}: planned hole -- its intervals are targets, "
                f"not assay results"
            )
            continue

        # Defensive: combined_routing only ever routes DD/RC to Collar, but a
        # trench-typed collar would otherwise be counted as drilling.
        if (collar.hole_type or "").strip().upper() in TRENCH_SAMPLE_TYPES:
            report.skipped.append(
                f"{collar.hole_id}: collar carries trench hole_type "
                f"{collar.hole_type!r}; not treated as drilling"
            )
            continue

        report.n_collars_considered += 1

        surveys = db.query(Survey).filter(
            Survey.collar_id == collar.id
        ).order_by(Survey.depth).all()

        assays = db.query(AssayInterval).filter(
            AssayInterval.collar_id == collar.id,
            AssayInterval.superseded_by.is_(None),
        ).order_by(AssayInterval.from_depth).all()

        report.n_assay_intervals_read += len(assays)
        report.n_unassayed_assay_intervals += sum(
            1 for a in assays if a.grade_value is None
        )

        for assay in assays:
            unit = (assay.grade_unit or "").strip()
            if not unit:
                continue
            if report.grade_unit is None:
                report.grade_unit = unit
            elif unit != report.grade_unit:
                raise ValueError(
                    f"Project carries mixed grade units: {report.grade_unit!r} "
                    f"and {unit!r} (hole {collar.hole_id}). Resolve the units "
                    f"at import; this service will not convert between them."
                )

        if not assays:
            continue

        if not surveys:
            report.skipped.append(
                f"{collar.hole_id}: no survey stations, so its {len(assays)} "
                f"assay intervals cannot be positioned"
            )
            continue

        try:
            located, warnings = build_drillhole_composites(
                {
                    "hole_id": collar.hole_id,
                    "easting": collar.easting,
                    "northing": collar.northing,
                    "elevation": collar.elevation,
                },
                [
                    {"depth": s.depth, "dip": s.dip, "azimuth": s.azimuth}
                    for s in surveys
                ],
                [
                    RawInterval(
                        from_depth=float(a.from_depth),
                        to_depth=float(a.to_depth),
                        grade=_as_float(a.grade_value),
                        sample_id=a.sample_id,
                    )
                    for a in assays
                ],
                composite_length,
            )
        except ValueError as exc:
            # Overlapping or inverted intervals are a data fault in one hole,
            # not a reason to abandon the project's other holes.
            report.skipped.append(f"{collar.hole_id}: {exc}")
            continue

        composites.extend(located)
        report.warnings.extend(warnings)
        report.n_ddh_composites += len(located)

    # Ordered explicitly so two extractions of the same project always return
    # composites in the same order. Legacy rows carry no point_order at all, so
    # without an ORDER BY their sequence is whatever the planner happens to
    # return. It changes nothing today -- every sample is placed at its own
    # coordinates -- but an unordered read is the kind of thing that quietly
    # becomes a correctness bug the moment anything reconstructs a line.
    # ``id`` breaks ties so the order is total, not merely stable-by-luck.
    trench_rows = db.query(Trench).filter(
        Trench.project_id == project_id,
        Trench.superseded_by.is_(None),
    ).order_by(Trench.trench_id, Trench.point_order, Trench.id).all()
    report.n_trench_rows_read = len(trench_rows)

    by_line: Dict[str, List[Trench]] = {}
    for row in trench_rows:
        by_line.setdefault(row.trench_id, []).append(row)

    for trench_id in sorted(by_line):
        # Legacy rows have no point_order at all; they keep their query order
        # behind any ordered rows rather than sorting against None.
        ordered = sorted(
            by_line[trench_id],
            key=lambda r: (r.point_order is None, r.point_order or 0),
        )
        report.n_trench_lines_considered += 1

        located, warnings, n_unassayed = build_trench_composites(
            [
                {
                    "trench_id": r.trench_id,
                    "point_order": r.point_order,
                    "easting": r.easting,
                    "northing": r.northing,
                    "elevation": r.elevation,
                    "grade_value": r.grade_value,
                    "hole_type": r.hole_type,
                    "from_depth": r.from_depth,
                    "to_depth": r.to_depth,
                }
                for r in ordered
            ],
            trench_length_when_unspecified,
        )

        composites.extend(located)
        report.warnings.extend(warnings)
        report.n_unassayed_trench_rows += n_unassayed
        report.n_trench_composites += len(located)

    for composite in composites:
        report.composites_by_type[composite.sample_type] = (
            report.composites_by_type.get(composite.sample_type, 0) + 1
        )

    return ExtractionResult(composites=composites, report=report)

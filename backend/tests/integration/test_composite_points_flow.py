"""Integration tests for composite extraction against a real session.

These cover the querying: the superseded filter, planned-hole exclusion, the
mixed-unit guard, and the provenance report. The geometry itself is covered by
backend/tests/unit/test_composite_points.py without a database.
"""
import math
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.db.session import Base
from backend.src.models.assay_interval import AssayInterval
from backend.src.models.collar import Collar
from backend.src.models.import_batch import ImportBatch
from backend.src.models.project import Project
from backend.src.models.survey import Survey
from backend.src.models.trench import Trench
from backend.src.models.user import User
from backend.src.services.composite_points import extract_composite_points

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def project(db):
    user = User(id=uuid.uuid4(), email=f"cp_{uuid.uuid4().hex}@example.com", role="owner")
    db.add(user)
    proj = Project(
        id=uuid.uuid4(),
        name=f"CP Test {uuid.uuid4().hex[:8]}",
        utm_zone="37N",
        owner_id=user.id,
    )
    db.commit()
    db.add(proj)
    db.commit()
    batch = ImportBatch(
        id=uuid.uuid4(),
        project_id=proj.id,
        source_file="composite_points_test.csv",
        status="committed",
    )
    db.add(batch)
    db.commit()
    return proj, batch


def _add_hole(
    db,
    project,
    batch,
    hole_id,
    intervals,
    hole_status=None,
    hole_type="DD",
    with_surveys=True,
    grade_unit="g/t",
    superseded_intervals=(),
):
    collar = Collar(
        id=uuid.uuid4(),
        project_id=project.id,
        hole_id=hole_id,
        easting=1000.0,
        northing=2000.0,
        elevation=500.0,
        utm_zone="37N",
        import_batch_id=batch.id,
        hole_type=hole_type,
        hole_status=hole_status,
    )
    db.add(collar)
    if with_surveys:
        for depth in (0.0, 100.0):
            db.add(Survey(
                id=uuid.uuid4(), collar_id=collar.id,
                depth=depth, dip=-90.0, azimuth=0.0,
                desurvey_method="minimum_curvature",
            ))
    live = []
    for from_depth, to_depth, grade in intervals:
        interval = AssayInterval(
            id=uuid.uuid4(), collar_id=collar.id,
            from_depth=from_depth, to_depth=to_depth, grade_value=grade,
            grade_unit=grade_unit, below_detection_limit=False,
            import_batch_id=batch.id,
        )
        db.add(interval)
        live.append(interval)
    db.commit()

    # superseded_by is a real FK to the row that replaced this one, so it has
    # to point at an interval that exists.
    for from_depth, to_depth, grade in superseded_intervals:
        db.add(AssayInterval(
            id=uuid.uuid4(), collar_id=collar.id,
            from_depth=from_depth, to_depth=to_depth, grade_value=grade,
            grade_unit=grade_unit, below_detection_limit=False,
            import_batch_id=batch.id, superseded_by=live[0].id,
        ))
    db.commit()
    return collar


def _add_trench_point(
    db, project, trench_id, order, grade,
    hole_type="TR", frm=None, to=None, superseded_by=None, elevation=300.0,
):
    row = Trench(
        id=uuid.uuid4(),
        project_id=project.id,
        trench_id=trench_id,
        easting=100.0 + order,
        northing=200.0,
        elevation=elevation,
        grade_value=grade,
        point_order=order,
        hole_type=hole_type,
        from_depth=frm,
        to_depth=to,
        superseded_by=superseded_by,
    )
    db.add(row)
    db.commit()
    return row


def test_drillhole_composites_are_extracted_and_positioned(db, project):
    proj, batch = project
    _add_hole(db, proj, batch, "DDH-001", [(0.0, 3.0, 2.0)])

    result = extract_composite_points(db, proj.id)

    assert result.report.n_ddh_composites == 3
    assert result.report.composites_by_type == {"DDH": 3}
    assert result.report.grade_unit == "g/t"
    # Vertical hole from elevation 500: midpoints at 0.5, 1.5, 2.5 m.
    assert [round(c.z, 6) for c in result.composites] == [499.5, 498.5, 497.5]


def test_superseded_assays_are_excluded(db, project):
    proj, batch = project
    _add_hole(
        db, proj, batch, "DDH-002",
        [(0.0, 1.0, 5.0)],
        superseded_intervals=[(1.0, 2.0, 99.0)],
    )

    result = extract_composite_points(db, proj.id)

    assert result.report.n_ddh_composites == 1
    assert math.isclose(result.composites[0].grade, 5.0)
    assert all(c.grade < 99.0 for c in result.composites)


def test_planned_holes_contribute_nothing(db, project):
    proj, batch = project
    _add_hole(db, proj, batch, "DDH-003", [(0.0, 2.0, 1.0)])
    _add_hole(db, proj, batch, "PL-001", [(0.0, 2.0, 50.0)], hole_status="planned")

    result = extract_composite_points(db, proj.id)

    assert result.report.n_ddh_composites == 2
    assert all(c.grade < 50.0 for c in result.composites)
    assert any("planned hole" in s for s in result.report.skipped)


def test_null_status_is_treated_as_drilled(db, project):
    proj, batch = project
    _add_hole(db, proj, batch, "DDH-004", [(0.0, 1.0, 1.0)], hole_status=None)

    result = extract_composite_points(db, proj.id)

    assert result.report.n_ddh_composites == 1


def test_hole_without_surveys_is_skipped_and_reported(db, project):
    proj, batch = project
    _add_hole(db, proj, batch, "DDH-005", [(0.0, 2.0, 1.0)], with_surveys=False)

    result = extract_composite_points(db, proj.id)

    assert result.report.n_ddh_composites == 0
    assert any("no survey stations" in s for s in result.report.skipped)


def test_unassayed_intervals_are_counted_and_excluded(db, project):
    proj, batch = project
    _add_hole(db, proj, batch, "DDH-006", [(0.0, 1.0, None), (1.0, 2.0, 4.0)])

    result = extract_composite_points(db, proj.id)

    assert result.report.n_assay_intervals_read == 2
    assert result.report.n_unassayed_assay_intervals == 1
    assert result.report.n_ddh_composites == 1
    assert math.isclose(result.composites[0].grade, 4.0)


def test_mixed_grade_units_raise(db, project):
    proj, batch = project
    _add_hole(db, proj, batch, "DDH-007", [(0.0, 1.0, 1.0)], grade_unit="g/t")
    _add_hole(db, proj, batch, "DDH-008", [(0.0, 1.0, 1.0)], grade_unit="ppm")

    with pytest.raises(ValueError, match="mixed grade units"):
        extract_composite_points(db, proj.id)


def test_superseded_trench_rows_are_excluded(db, project):
    proj, batch = project
    live = _add_trench_point(db, proj, "TR-A", 0, 2.0, frm=0.0, to=1.0)
    _add_trench_point(
        db, proj, "TR-A", 1, 99.0, frm=1.0, to=2.0, superseded_by=live.id
    )

    result = extract_composite_points(db, proj.id)

    assert result.report.n_trench_composites == 1
    assert math.isclose(result.composites[0].grade, 2.0)


def test_trench_sample_types_are_kept_separate(db, project):
    proj, batch = project
    _add_trench_point(db, proj, "TR-A", 0, 1.0, hole_type="TR", frm=0.0, to=1.0)
    _add_trench_point(db, proj, "CH-A", 0, 2.0, hole_type="CH", frm=0.0, to=1.0)
    _add_trench_point(db, proj, "FC-A", 0, 3.0, hole_type="FC", frm=0.0, to=1.0)

    result = extract_composite_points(db, proj.id)

    assert result.report.composites_by_type == {"TR": 1, "CH": 1, "FC": 1}


def test_trench_rows_without_length_excluded_by_default_and_reported(db, project):
    proj, batch = project
    _add_trench_point(db, proj, "TR-LEGACY", 0, 2.0)

    result = extract_composite_points(db, proj.id)

    assert result.report.n_trench_composites == 0
    assert any("states no sample length" in w for w in result.report.warnings)


def test_trench_rows_without_length_included_when_a_length_is_stated(db, project):
    proj, batch = project
    _add_trench_point(db, proj, "TR-LEGACY2", 0, 2.0)

    result = extract_composite_points(
        db, proj.id, trench_length_when_unspecified=1.0
    )

    assert result.report.n_trench_composites == 1
    assert math.isclose(result.composites[0].length, 1.0)


def test_report_accounts_for_every_record(db, project):
    proj, batch = project
    _add_hole(db, proj, batch, "DDH-009", [(0.0, 2.0, 1.0)])
    _add_trench_point(db, proj, "TR-B", 0, 3.0, frm=0.0, to=1.0)
    _add_trench_point(db, proj, "TR-B", 1, None)

    result = extract_composite_points(db, proj.id)

    report = result.report
    assert report.n_collars_considered == 1
    assert report.n_trench_lines_considered == 1
    assert report.n_trench_rows_read == 2
    assert report.n_unassayed_trench_rows == 1
    assert report.collars_by_hole_type == {"DD": 1}
    assert report.n_ddh_composites + report.n_trench_composites == len(result.composites)


def test_empty_project_returns_an_empty_result(db, project):
    proj, batch = project

    result = extract_composite_points(db, proj.id)

    assert result.composites == []
    assert result.report.n_ddh_composites == 0
    assert result.report.grade_unit is None


def test_project_id_accepts_a_string(db, project):
    proj, batch = project
    _add_hole(db, proj, batch, "DDH-010", [(0.0, 1.0, 1.0)])

    result = extract_composite_points(db, str(proj.id))

    assert result.report.n_ddh_composites == 1


def test_extraction_is_deterministic_including_rows_without_point_order(db, project):
    # Legacy trench rows carry no point_order, so without an explicit ORDER BY
    # their sequence is whatever the planner returns. Two extractions of the
    # same project must produce identical output.
    proj, batch = project
    _add_hole(db, proj, batch, "DDH-DET", [(0.0, 3.0, 1.0)])
    for i in range(6):
        row = Trench(
            id=uuid.uuid4(),
            project_id=proj.id,
            trench_id="TR-LEGACY-DET",
            easting=100.0 + i,
            northing=200.0,
            elevation=300.0,
            grade_value=float(i) + 1.0,
            point_order=None,
            hole_type=None,
        )
        db.add(row)
    db.commit()

    first = extract_composite_points(db, proj.id, trench_length_when_unspecified=1.0)
    second = extract_composite_points(db, proj.id, trench_length_when_unspecified=1.0)

    assert first.composites == second.composites
    assert [c.grade for c in first.composites] == [c.grade for c in second.composites]
    assert [(c.x, c.y, c.z) for c in first.composites] == \
           [(c.x, c.y, c.z) for c in second.composites]


def test_trench_lines_are_grouped_and_ordered(db, project):
    proj, batch = project
    # Inserted out of order on purpose.
    _add_trench_point(db, proj, "TR-Z", 1, 2.0, frm=1.0, to=2.0)
    _add_trench_point(db, proj, "TR-A", 1, 4.0, frm=1.0, to=2.0)
    _add_trench_point(db, proj, "TR-Z", 0, 1.0, frm=0.0, to=1.0)
    _add_trench_point(db, proj, "TR-A", 0, 3.0, frm=0.0, to=1.0)

    result = extract_composite_points(db, proj.id)

    # TR-A's two samples, then TR-Z's, each in point_order.
    assert [c.grade for c in result.composites] == [3.0, 4.0, 1.0, 2.0]


def test_output_feeds_compare_sample_types_directly(db, project):
    # The critical requirement for this task: what comes out must run through
    # T002 unchanged.
    from backend.src.services.sample_type_comparison import compare_sample_types

    proj, batch = project
    _add_hole(db, proj, batch, "DDH-011", [(0.0, 40.0, 1.0)])
    for i in range(40):
        _add_trench_point(db, proj, "TR-C", i, 2.0, frm=float(i), to=float(i + 1))

    result = extract_composite_points(db, proj.id)
    comparison = compare_sample_types(result.composites)

    assert comparison.by_type["DDH"].n == 40
    assert comparison.by_type["TR"].n == 40
    assert math.isclose(comparison.grade_ratio, 2.0)

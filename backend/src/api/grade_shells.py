"""Grade-domain analysis and shell generation endpoints.

Three routes. Two report evidence for choosing a threshold; one generates a
shell and stores it as a ``Wireframe`` so the existing scene, export and share
paths render it with no further work.

**What these endpoints produce is a grade-domain envelope, not a resource.**
No response describes the output as a resource or reserve, and none returns a
tonnage. Volume in cubic metres and metal *capture fraction* are geometry and
validation statistics -- they describe the shell, not the deposit. (Decision D3.)

Every geological input is required and none is defaulted: the threshold, the
search ellipsoid, and the sample-type weights all have to be stated on each
request. Defaults here would be recommendations wearing a disguise, and a shell
built on one nobody noticed is the specific failure D7 exists to prevent.
"""
import json
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.src.api.auth import get_current_user
from backend.src.api.project_access import get_owned_project_or_404
from backend.src.db.session import get_db
from backend.src.models.user import User
from backend.src.models.wireframe import Wireframe
from backend.src.services.composite_points import extract_composite_points
from backend.src.services.grade_interpolant import (
    SearchEllipsoid,
    estimate_node_count,
    interpolate_grade_grid,
)
from backend.src.services.isosurface import extract_isosurface, mesh_to_obj
from backend.src.services.sample_type_comparison import compare_sample_types
from backend.src.services.shell_validation import validate_shell
from backend.src.services.threshold_analysis import (
    contact_analysis,
    log_probability_points,
    metal_capture_curve,
)
from backend.src.storage.local_filesystem import LocalFilesystemStorage

router = APIRouter(prefix="/projects/{project_id}", tags=["grade-shells"])
storage = LocalFilesystemStorage()

GRADE_SHELL_SOLID_TYPE = "grade_shell"

# Above this a grid stops being slow and starts being fatal: a 1 m cell over a
# 3 km property is billions of nodes. Refused before anything is allocated.
MAX_GRID_NODES = 20_000_000

# Candidates for the capture curve when a caller states none. This describes
# the SHAPE of the curve across a plausible range and is not a recommendation
# about where to cut -- see decision D8.
CURVE_CANDIDATE_THRESHOLDS = [0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0, 2.0, 5.0]


class EllipsoidPayload(BaseModel):
    """Search ellipsoid. No defaults, by decision D7."""

    range_major: float = Field(..., gt=0, description="along strike, metres")
    range_semi: float = Field(..., gt=0, description="down dip, metres")
    range_minor: float = Field(..., gt=0, description="across the structure")
    strike_azimuth: float = Field(..., description="degrees clockwise from north")
    dip: float = Field(..., description="degrees from horizontal, downward negative")

    @field_validator("dip")
    @classmethod
    def _dip_in_range(cls, value: float) -> float:
        if not -90.0 <= value <= 90.0:
            raise ValueError("dip must be between -90 and 90 degrees")
        return value


class GradeShellRequest(BaseModel):
    name: str = Field(..., min_length=1)
    threshold: float = Field(..., gt=0)
    ellipsoid: EllipsoidPayload
    sample_type_weights: Dict[str, float] = Field(
        ...,
        description=(
            "Weight per sample type, e.g. {'DDH': 1.0, 'TR': 0.5, 'FC': 0.0}. "
            "Required: a silent default would overturn a decision someone made "
            "deliberately. 0.0 excludes a type from grade while leaving it "
            "available for geometry."
        ),
    )
    composite_length: float = Field(1.0, gt=0)
    cell_size: float = Field(..., gt=0)
    padding: float = Field(20.0, ge=0)
    power: float = Field(2.0, gt=0)
    max_samples: int = Field(16, ge=1)
    min_samples: int = Field(2, ge=1)
    min_volume: float = Field(0.0, ge=0)
    split_components: bool = True
    trench_length_when_unspecified: Optional[float] = Field(None, gt=0)

    @field_validator("sample_type_weights")
    @classmethod
    def _weights_are_sane(cls, value: Dict[str, float]) -> Dict[str, float]:
        if not value:
            raise ValueError("sample_type_weights must not be empty")
        for sample_type, weight in value.items():
            if weight < 0.0:
                raise ValueError(
                    f"weight for {sample_type} is negative ({weight})"
                )
        return value

    def check_sample_counts(self) -> None:
        if self.max_samples < self.min_samples:
            raise ValueError(
                f"max_samples ({self.max_samples}) must be at least "
                f"min_samples ({self.min_samples})"
            )


def _extract(db: Session, project_id, composite_length: float,
             trench_length: Optional[float] = None):
    try:
        return extract_composite_points(
            db, project_id,
            composite_length=composite_length,
            trench_length_when_unspecified=trench_length,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _report_payload(report) -> Dict:
    return {
        "grade_unit": report.grade_unit,
        "n_ddh_composites": report.n_ddh_composites,
        "n_trench_composites": report.n_trench_composites,
        "composites_by_type": report.composites_by_type,
        "collars_by_hole_type": report.collars_by_hole_type,
        "n_assay_intervals_read": report.n_assay_intervals_read,
        "n_unassayed_assay_intervals": report.n_unassayed_assay_intervals,
        "n_trench_rows_read": report.n_trench_rows_read,
        "n_unassayed_trench_rows": report.n_unassayed_trench_rows,
        "n_trench_intervals_merged": report.n_trench_intervals_merged,
        "n_trench_rows_absorbed": report.n_trench_rows_absorbed,
        "skipped": report.skipped,
        "warnings": report.warnings,
    }


def _population_payload(stats) -> Dict:
    return {
        "sample_type": stats.sample_type,
        "n": stats.n,
        "mean": stats.mean,
        "median": stats.median,
        "std": stats.std,
        "cv": stats.cv,
        "minimum": stats.minimum,
        "maximum": stats.maximum,
        "p10": stats.p10,
        "p25": stats.p25,
        "p75": stats.p75,
        "p90": stats.p90,
        "total_length": stats.total_length,
        "length_weighted_mean": stats.length_weighted_mean,
    }


@router.get("/grade-analysis")
def get_grade_analysis(
    project_id: str,
    composite_length: float = Query(1.0, gt=0),
    thresholds: Optional[List[float]] = Query(None),
    trench_length_when_unspecified: Optional[float] = Query(None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sample-type comparison, log-probability and metal-capture evidence.

    Nothing is generated and nothing is written. The threshold candidates shape
    the capture curve and carry no recommendation.
    """
    project = get_owned_project_or_404(project_id, db, current_user)
    result = _extract(db, project.id, composite_length,
                      trench_length_when_unspecified)

    candidates = thresholds if thresholds else CURVE_CANDIDATE_THRESHOLDS
    comparison = compare_sample_types(result.composites)
    log_prob = log_probability_points(result.composites)

    by_type: Dict[str, Dict] = {}
    for sample_type in sorted(comparison.by_type):
        subset = [c for c in result.composites if c.sample_type == sample_type]
        by_type[sample_type] = {
            "statistics": _population_payload(comparison.by_type[sample_type]),
            "metal_capture": [
                {
                    "threshold": row.threshold,
                    "n_above": row.n_above,
                    "length_above": row.length_above,
                    "length_fraction": row.length_fraction,
                    "metal_fraction": row.metal_fraction,
                    "mean_grade_above": row.mean_grade_above,
                }
                for row in metal_capture_curve(subset, candidates)
            ],
        }

    return {
        "extraction": _report_payload(result.report),
        "populations": by_type,
        "pooled": _population_payload(comparison.pooled),
        "comparison": {
            "grade_ratio": comparison.grade_ratio,
            "mean_ratio": comparison.mean_ratio,
            "comparable": comparison.comparable,
            "reasons": comparison.reasons,
            "qq_points": [
                {"reference": a, "other": b} for a, b in comparison.qq_points
            ],
            "note": (
                "comparable is a coarse screening flag, not a statistical "
                "test. It does not authorise pooling two populations."
            ),
        },
        "log_probability": {
            "points": [
                {"cumulative_probability": p.cumulative_probability,
                 "grade": p.grade}
                for p in log_prob.points
            ],
            "n_excluded_non_positive": log_prob.n_excluded_non_positive,
        },
        "metal_capture_all": [
            {
                "threshold": row.threshold,
                "n_above": row.n_above,
                "length_fraction": row.length_fraction,
                "metal_fraction": row.metal_fraction,
                "mean_grade_above": row.mean_grade_above,
            }
            for row in metal_capture_curve(result.composites, candidates)
        ],
        "thresholds_evaluated": candidates,
    }


@router.get("/grade-analysis/contact")
def get_contact_analysis(
    project_id: str,
    threshold: float = Query(..., gt=0),
    composite_length: float = Query(1.0, gt=0),
    bin_width: float = Query(10.0, gt=0),
    max_distance: float = Query(60.0, gt=0),
    sample_types: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mean grade against signed distance from the boundary a threshold implies.

    Per-threshold and more expensive than the analysis above, so it is its own
    route.
    """
    project = get_owned_project_or_404(project_id, db, current_user)
    result = _extract(db, project.id, composite_length)

    composites = result.composites
    if sample_types:
        wanted = {t.strip().upper() for t in sample_types}
        composites = [c for c in composites if c.sample_type in wanted]

    bins = contact_analysis(composites, threshold, bin_width, max_distance)

    return {
        "threshold": threshold,
        "sample_types": sorted({c.sample_type for c in composites}),
        "bins": [
            {
                "distance_bin_center": b.distance_bin_center,
                "n": b.n,
                "mean_grade": b.mean_grade,
                "length_weighted_mean_grade": b.length_weighted_mean_grade,
            }
            for b in bins
        ],
        "note": (
            "Membership of each side is defined by the grade being compared, "
            "so a step at zero is partly self-fulfilling. The informative part "
            "is the trend outside the boundary."
        ),
    }


@router.post("/grade-shells")
def create_grade_shell(
    project_id: str,
    request: GradeShellRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a grade-domain shell and store it as a wireframe.

    Returns 200 with ``wireframe: null`` when no material meets the threshold --
    a legitimate geological answer, not an error.
    """
    project = get_owned_project_or_404(project_id, db, current_user)

    try:
        request.check_sample_counts()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    result = _extract(db, project.id, request.composite_length,
                      request.trench_length_when_unspecified)
    if not result.composites:
        raise HTTPException(
            status_code=400,
            detail="No assayed intervals found for this project.",
        )

    present = {c.sample_type for c in result.composites}
    missing = present - set(request.sample_type_weights)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=(
                f"No weight given for sample type(s) {sorted(missing)}. State a "
                f"weight for every type present; 0.0 excludes a type from grade "
                f"while leaving it available for geometry."
            ),
        )

    # Refuse an impossible grid before allocating any of it.
    node_count = estimate_node_count(
        result.composites, request.cell_size, request.padding)
    if node_count > MAX_GRID_NODES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"A cell size of {request.cell_size} m over this project would "
                f"need {node_count:,} grid nodes, above the limit of "
                f"{MAX_GRID_NODES:,}. Increase cell_size."
            ),
        )

    ellipsoid = SearchEllipsoid(
        range_major=request.ellipsoid.range_major,
        range_semi=request.ellipsoid.range_semi,
        range_minor=request.ellipsoid.range_minor,
        strike_azimuth=request.ellipsoid.strike_azimuth,
        dip=request.ellipsoid.dip,
    )

    grid = interpolate_grade_grid(
        result.composites,
        ellipsoid,
        sample_type_weights=request.sample_type_weights,
        cell_size=request.cell_size,
        padding=request.padding,
        power=request.power,
        max_samples=request.max_samples,
        min_samples=request.min_samples,
    )

    surface = extract_isosurface(
        grid,
        threshold=request.threshold,
        split_components=request.split_components,
        min_volume=request.min_volume,
    )
    validation = validate_shell(surface, result.composites, request.threshold)

    parameters = {
        "threshold": request.threshold,
        "composite_length": request.composite_length,
        "cell_size": request.cell_size,
        "padding": request.padding,
        "power": request.power,
        "max_samples": request.max_samples,
        "min_samples": request.min_samples,
        "min_volume": request.min_volume,
        "split_components": request.split_components,
        "sample_type_weights": request.sample_type_weights,
        "trench_length_when_unspecified": request.trench_length_when_unspecified,
        "ellipsoid": request.ellipsoid.model_dump(),
        "grade_unit": result.report.grade_unit,
        "n_composites": len(result.composites),
        "composites_by_type": result.report.composites_by_type,
        "grid_nodes": grid.n_total,
        "grid_nodes_estimated": grid.n_estimated,
    }

    validation_payload = {
        "geometry": {
            "is_watertight": validation.geometry.is_watertight,
            "n_boundary_edges": validation.geometry.n_boundary_edges,
            "n_nonmanifold_edges": validation.geometry.n_nonmanifold_edges,
            "n_degenerate_faces": validation.geometry.n_degenerate_faces,
            "n_duplicate_faces": validation.geometry.n_duplicate_faces,
            "n_components": validation.geometry.n_components,
            "total_volume_m3": validation.geometry.total_volume,
            "bounding_box": validation.geometry.bounding_box,
        },
        "statistics": {
            "threshold": validation.statistics.threshold,
            "n_composites_inside": validation.statistics.n_composites_inside,
            "n_composites_above_threshold":
                validation.statistics.n_composites_above_threshold,
            "metal_capture": validation.statistics.metal_capture,
            "internal_dilution": validation.statistics.internal_dilution,
            "mean_grade_inside": validation.statistics.mean_grade_inside,
            "by_sample_type": [
                {
                    "sample_type": s.sample_type,
                    "n_inside": s.n_inside,
                    "n_outside": s.n_outside,
                    "length_inside": s.length_inside,
                    "mean_grade_inside": s.mean_grade_inside,
                }
                for s in validation.statistics.by_sample_type
            ],
        },
        "notes": validation.notes,
    }

    if not surface.components:
        # Nothing above the threshold. Not an error, and nothing is written.
        return {
            "wireframe": None,
            "message": (
                f"No material meets {request.threshold} "
                f"{result.report.grade_unit or 'g/t'} in this project."
            ),
            "parameters": parameters,
            "validation": validation_payload,
            "extraction": _report_payload(result.report),
        }

    safe_name = "".join(
        ch if ch.isalnum() or ch in "-_" else "_" for ch in request.name
    )[:40]
    file_ref = storage.save(
        mesh_to_obj(surface, name=safe_name or "grade_shell").encode("utf-8"),
        f"grade_shell_{uuid.uuid4().hex}_{safe_name or 'shell'}.obj",
    )

    wireframe = Wireframe(
        id=uuid.uuid4(),
        project_id=project.id,
        name=request.name,
        solid_type=GRADE_SHELL_SOLID_TYPE,
        file_ref=file_ref,
        parameters={**parameters, "validation": validation_payload},
    )
    db.add(wireframe)
    db.commit()
    db.refresh(wireframe)

    return {
        "wireframe": {
            "id": str(wireframe.id),
            "name": wireframe.name,
            "solid_type": wireframe.solid_type,
            "file_ref": wireframe.file_ref,
        },
        "parameters": parameters,
        "validation": validation_payload,
        "extraction": _report_payload(result.report),
    }


@router.get("/grade-shells")
def list_grade_shells(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generated shells for a project, with the parameters that produced them."""
    project = get_owned_project_or_404(project_id, db, current_user)
    shells = db.query(Wireframe).filter(
        Wireframe.project_id == project.id,
        Wireframe.solid_type == GRADE_SHELL_SOLID_TYPE,
    ).all()

    return {
        "grade_shells": [
            {
                "id": str(w.id),
                "name": w.name,
                "solid_type": w.solid_type,
                "file_ref": w.file_ref,
                "parameters": w.parameters,
            }
            for w in shells
        ]
    }

import uuid
import json
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from backend.src.db.session import get_db
from backend.src.api.auth import get_current_user
from backend.src.models.user import User
from backend.src.models.project import Project
from backend.src.models.import_batch import ImportBatch
from backend.src.models.collar import Collar
from backend.src.models.survey import Survey
from backend.src.models.assay_interval import AssayInterval
from backend.src.models.lithology_interval import LithologyInterval
from backend.src.models.qaqc_standard import QaqcStandard

from backend.src.storage.local_filesystem import LocalFilesystemStorage
from backend.src.services.csv_import import (
    parse_collar_csv,
    parse_survey_csv,
    parse_assay_csv,
    parse_lithology_csv,
    parse_combined_csv
)
from backend.src.services.import_validation import validate_import_batch
from backend.src.services.crs import detect_utm_zone
from backend.src.services.desurvey import compute_minimum_curvature_trace
from backend.src.services.combined_routing import (
    route_combined_rows,
    resolve_or_create_zone_projects,
    preview_zone_projects,
    _normalize_zone_key,
)
from backend.src.models.trench import Trench
from backend.src.api.project_access import get_owned_project_or_404 as get_project_or_404

router = APIRouter(prefix="/projects/{project_id}/imports", tags=["imports"])
storage = LocalFilesystemStorage()

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_import(
    project_id: str,
    collar_file: Optional[UploadFile] = File(None),
    survey_file: Optional[UploadFile] = File(None),
    assay_file: Optional[UploadFile] = File(None),
    lithology_file: Optional[UploadFile] = File(None),
    combined_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_project_or_404(project_id, db, current_user)

    collars, surveys, assays, lithologies = [], [], [], []
    trench_points = []
    issues = []
    import_mode = "four_file"

    # Helper to clean parsing issues. The combined parser emits advisory items
    # (missing Type column, unsampled trench gaps) with an explicit
    # "type": "warning" field; respect it so a warning does not become a
    # blocking parse error. The wording follows the severity too -- an audit-log
    # line reading "parse error" for a non-blocking warning sends people
    # hunting for a failure that never happened. The "parse_error" rule key is
    # deliberately left alone: it is a machine identifier that callers filter
    # on, and "type" already carries the severity.
    def add_parse_errors(errors: list, file_type: str):
        for err in errors:
            issue_type = err.get("type", "error")
            label = "parse warning" if issue_type == "warning" else "parse error"
            issues.append({
                "type": issue_type,
                "rule": "parse_error",
                "message": f"{file_type} CSV {label} on row {err['row']}: {err['error']}",
                "hole_id": err['raw_data'].get('hole_id', '') if isinstance(err['raw_data'], dict) else '',
                "row": err['row']
            })

    # Read and parse files
    source_files = []
    if collar_file:
        content = await collar_file.read()
        collars, c_errs = parse_collar_csv(content)
        add_parse_errors(c_errs, "Collar")
        source_files.append(collar_file.filename)
    if survey_file:
        content = await survey_file.read()
        surveys, s_errs = parse_survey_csv(content)
        add_parse_errors(s_errs, "Survey")
        source_files.append(survey_file.filename)
    if assay_file:
        content = await assay_file.read()
        assays, a_errs = parse_assay_csv(content)
        add_parse_errors(a_errs, "Assay")
        source_files.append(assay_file.filename)
    if lithology_file:
        content = await lithology_file.read()
        lithologies, l_errs = parse_lithology_csv(content)
        add_parse_errors(l_errs, "Lithology")
        source_files.append(lithology_file.filename)

    # Combined Master Reference CSV: one file mixes all hole types and zones.
    zones_preview = []
    if combined_file:
        # The combined CSV is a self-contained master reference. Supplying it
        # alongside any of the four legacy files silently discards their data
        # (the combined branch overwrites collars/surveys and hard-sets
        # assays=[] and lithologies=[]), so reject the mix with a 400 rather
        # than pretend the four-file data was applied.
        four_file_present = any([collar_file, survey_file, assay_file, lithology_file])
        if four_file_present:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Supply either a combined CSV OR the four separate files "
                    "(collar/survey/assay/lithology), not both. Mixing them "
                    "would silently discard the four-file data."
                )
            )
        import_mode = "combined"
        content = await combined_file.read()
        rows, p_errs = parse_combined_csv(content)
        add_parse_errors(p_errs, "Combined")
        source_files.append(combined_file.filename)

        routed = route_combined_rows(rows)
        collars = routed["collars"]
        surveys = routed["surveys"]
        trench_points = routed["trench_points"]
        assays = routed.get("assays", [])
        lithologies = []

        # Preview zone resolution -- READ ONLY. No projects are created at
        # preview; project_id is null for zones that would be newly created.
        zone_names = [r.get("zone") for r in rows]
        preview = preview_zone_projects(db, zone_names, current_user)

        # Build the zones breakdown. Rows with zone=None route to the URL
        # project (which already exists) -- surfaced as an "appended" entry.
        from collections import OrderedDict
        zone_groups = OrderedDict()  # normalized_key -> {zone, project_id, action, collars, trenches, types}
        for c in collars:
            _accumulate_zone_group(zone_groups, c.get("zone"), c.get("hole_type"),
                                   is_trench=False, project=project, preview=preview)
        for t in trench_points:
            _accumulate_zone_group(zone_groups, t.get("zone"), t.get("hole_type"),
                                   is_trench=True, project=project, preview=preview,
                                   trench_id=t.get("trench_id"))
        zones_preview = _build_zones_payload(zone_groups, project)

    # 1. Run geological validations
    db_standards = db.query(QaqcStandard).filter(QaqcStandard.project_id == project.id).all()
    qaqc_standards_list = [
        {
            "standard_name": s.standard_name,
            "expected_grade_min": s.expected_grade_min,
            "expected_grade_max": s.expected_grade_max,
            "grade_unit": s.grade_unit
        }
        for s in db_standards
    ]
    validation_res = validate_import_batch(
        collars, surveys, assays, lithologies, project.utm_zone, qaqc_standards_list,
        trenches=(trench_points if import_mode == "combined" else None)
    )
    issues.extend(validation_res["issues"])

    # Determine overall validity
    has_errors = any(issue["type"] == "error" for issue in issues)
    valid = not has_errors

    # 2. Auto-detect UTM zone (defaults to 37N when the project has none)
    detected_zone = detect_utm_zone(
        [c["easting"] for c in collars],
        [c["northing"] for c in collars],
        project.utm_zone or "37N"
    )

    # Create diff/validation payload
    payload = {
        "valid": valid,
        "detected_utm_zone": detected_zone,
        "issues": issues,
        "import_mode": import_mode,
        "data": {
            "collars": collars,
            "surveys": surveys,
            "assays": assays,
            "lithologies": lithologies
        },
        "summary": {
            "collar_count": len(collars),
            "survey_count": len(surveys),
            "assay_count": len(assays),
            "lithology_count": len(lithologies),
            "error_count": sum(1 for issue in issues if issue["type"] == "error"),
            "warning_count": sum(1 for issue in issues if issue["type"] == "warning")
        }
    }
    if import_mode == "combined":
        payload["data"]["trenches"] = trench_points
        payload["summary"]["trench_count"] = len(trench_points)
        payload["zones"] = zones_preview

    # 3. Store batch JSON payload in object storage
    payload_bytes = json.dumps(payload).encode("utf-8")
    source_filename = ", ".join(source_files) if source_files else "empty_batch"
    file_ref = storage.save(payload_bytes, f"{uuid.uuid4().hex}.json")

    # Create ImportBatch in database
    import_batch = ImportBatch(
        id=uuid.uuid4(),
        project_id=project.id,
        source_file=file_ref,
        status="pending_review",
        created_by=current_user.id
    )
    db.add(import_batch)
    db.commit()
    db.refresh(import_batch)

    return {
        "import_batch_id": str(import_batch.id),
        "status": import_batch.status,
        "validation": payload
    }


def _accumulate_zone_group(groups, zone, hole_type, is_trench, project, preview, trench_id=None):
    """Accumulate per-zone collar/trench counts for the preview payload.

    trench_count counts DISTINCT trench_id (one trench = N point rows), not
    point rows -- showing 44 for 22 trenches misrepresents the import.
    """
    key = "None" if zone is None else _normalize_zone_key(zone)
    if key not in groups:
        if zone is None:
            project_id = str(project.id)
            action = "appended"
        else:
            entry = preview.get(key)
            project_id = str(entry["project"].id) if entry and entry.get("project") else None
            action = entry["action"] if entry else "created"
        groups[key] = {
            "zone": zone,
            "project_id": project_id,
            "action": action,
            "collar_count": 0,
            "_trench_ids": set(),
            "hole_type_breakdown": {},
        }
    g = groups[key]
    if is_trench:
        # Count each trench once, not once per generated point row. Without
        # this the breakdown disagrees with trench_count -- 7 trenches would
        # report a breakdown summing to 14.
        if trench_id is None:
            import logging
            logging.getLogger(__name__).warning(
                "Trench point with trench_id=None dropped from preview summary"
            )
            return
        if trench_id in g["_trench_ids"]:
            return
        g["_trench_ids"].add(trench_id)
    else:
        g["collar_count"] += 1
    ht = hole_type or "DD"
    g["hole_type_breakdown"][ht] = g["hole_type_breakdown"].get(ht, 0) + 1


def _build_zones_payload(groups, project):
    return [
        {
            "zone": g["zone"],
            "project_id": g["project_id"],
            "action": g["action"],
            "collar_count": g["collar_count"],
            # Distinct trench count, NOT point count; this feature generates 2
            # rows per trench and showing 44 for 22 trenches misrepresents it.
            "trench_count": len(g["_trench_ids"]),
            "hole_type_breakdown": g["hole_type_breakdown"],
        }
        for g in groups.values()
    ]


@router.get("/{import_batch_id}")
def get_import(
    project_id: str,
    import_batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_project_or_404(project_id, db, current_user)
    try:
        b_uuid = uuid.UUID(import_batch_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Import batch not found")
        
    batch = db.query(ImportBatch).filter(
        ImportBatch.id == b_uuid,
        ImportBatch.project_id == project.id
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
        
    # Read the payload from storage
    try:
        payload_bytes = storage.load(batch.source_file)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="Could not load batch data from storage")
        
    return {
        "import_batch_id": str(batch.id),
        "status": batch.status,
        "validation": payload
    }

@router.post("/{import_batch_id}/commit")
def commit_import(
    project_id: str,
    import_batch_id: str,
    utm_zone_confirm: str = Query(...),  # User must confirm/select the UTM zone
    acknowledge_warnings: bool = Query(False),  # Must be explicitly set when
    # warning-level issues (e.g. overlapping/gapped intervals) are present
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_project_or_404(project_id, db, current_user)
    try:
        b_uuid = uuid.UUID(import_batch_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Import batch not found")
        
    batch = db.query(ImportBatch).filter(
        ImportBatch.id == b_uuid,
        ImportBatch.project_id == project.id
    ).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    if batch.status != "pending_review":
        raise HTTPException(status_code=400, detail=f"Cannot commit batch in status: {batch.status}")
        
    # Load parsed data from storage
    try:
        payload_bytes = storage.load(batch.source_file)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="Could not load batch data from storage")
        
    # Verify there are no blocking errors
    has_errors = any(issue["type"] == "error" for issue in payload["issues"])
    if has_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot commit import batch with unresolved validation errors"
        )

    # Warning-level issues (e.g. overlapping/gapped intervals) do not block a
    # commit outright, but per data-model.md and contracts/api.md they must be
    # explicitly acknowledged by the client before commit proceeds — silently
    # committing unreviewed overlaps/gaps would defeat the point of flagging them.
    has_warnings = any(issue["type"] == "warning" for issue in payload["issues"])
    if has_warnings and not acknowledge_warnings:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This batch has unacknowledged warnings (e.g. overlapping or "
                   "gapped intervals). Review them and resubmit with "
                   "acknowledge_warnings=true to commit anyway."
        )

    # Apply UTM zone confirmation to the URL project (fills a null zone only).
    if not project.utm_zone:
        project.utm_zone = utm_zone_confirm
        db.add(project)

    data = payload["data"]
    import_mode = payload.get("import_mode", "four_file")

    # hole_ids for which THIS batch supplies each child type. Used by the T012
    # data-loss fix: when an old collar is superseded, a child type is only
    # left on the old collar when the batch actually re-supplies rows for that
    # hole_id. "Supplies" means a matching hole_id row, not merely an uploaded
    # file -- a batch with an assay file that has no rows for DH01 must still
    # re-point DH01's existing assays.
    survey_hole_ids = {s["hole_id"] for s in data.get("surveys", [])}
    assay_hole_ids = {a["hole_id"] for a in data.get("assays", [])}
    lith_hole_ids = {l["hole_id"] for l in data.get("lithologies", [])}

    try:
        if import_mode == "combined":
            result = _commit_combined(
                db, project, batch, data, current_user, utm_zone_confirm,
                survey_hole_ids, assay_hole_ids, lith_hole_ids
            )
        else:
            _commit_four_file(
                db, project, batch, data, utm_zone_confirm,
                survey_hole_ids, assay_hole_ids, lith_hole_ids
            )
            result = {
                "message": "Import batch committed successfully",
                "import_batch_id": str(batch.id),
                "batches": [{
                    "project_id": str(project.id),
                    "project_name": project.name,
                    "import_batch_id": str(batch.id),
                    "action": "appended",
                    "collar_count": len(data["collars"]),
                    "trench_count": 0
                }]
            }

        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def _repoint_children_if_not_resupplied(db, old_collar, new_collar_id, hole_id,
                                         survey_hole_ids, assay_hole_ids, lith_hole_ids):
    """T012 data-loss fix. When a collar is superseded, each child type is
    re-pointed to the new collar ONLY IF this batch does not re-supply rows of
    that type for this hole_id. Per-child-type, keyed on hole_id presence:

    - Survey has NO superseded_by column; "active" = all surveys on the collar.
      Re-point = UPDATE collar_id.
    - AssayInterval / LithologyInterval re-point only their active
      (superseded_by IS NULL) rows; already-superseded intervals stay on the
      old collar as historical audit.

    When the batch DOES re-supply a type for this hole_id, the old rows stay on
    the old (now-superseded) collar and the new collar receives the new rows in
    the batch -- preserving the existing test contract and the combined
    re-import behaviour (inline survey stays with old collar, new collar gets
    the new inline survey; assays/lithologies, which the combined CSV never
    carries, are re-pointed to the new collar).
    """
    if hole_id not in survey_hole_ids:
        db.query(Survey).filter(Survey.collar_id == old_collar.id).update(
            {Survey.collar_id: new_collar_id}, synchronize_session=False
        )
    if hole_id not in assay_hole_ids:
        db.query(AssayInterval).filter(
            AssayInterval.collar_id == old_collar.id,
            AssayInterval.superseded_by.is_(None)
        ).update({AssayInterval.collar_id: new_collar_id}, synchronize_session=False)
    if hole_id not in lith_hole_ids:
        db.query(LithologyInterval).filter(
            LithologyInterval.collar_id == old_collar.id,
            LithologyInterval.superseded_by.is_(None)
        ).update({LithologyInterval.collar_id: new_collar_id}, synchronize_session=False)


def _apply_collar(db, project_id, batch_id, c_data, utm_zone_confirm,
                  survey_hole_ids, assay_hole_ids, lith_hole_ids):
    """Insert one collar (with supersede + T012 child re-point). Returns the
    new collar id. Shared by both commit paths.

    Statement ordering under PostgreSQL FK enforcement (root cause of Blockers
    1 & 3): Query.update() bypasses the unit of work and emits SQL immediately,
    while session.py sets autoflush=False, so pending INSERTs are NOT flushed
    before it runs. A supersede-UPDATE or child-repoint UPDATE referencing the
    new collar id therefore violates the FK because the new collar row does not
    exist yet. The fix is to INSERT and flush the new collar first, then do the
    dependent UPDATE(s).

    Step 1 (query old_collar) MUST stay before step 2 (add new_collar) -- the
    lookup filters `superseded_by IS NULL`, so inserting first would make the
    query find the NEW collar and supersede it against itself.
    """
    hole_id = c_data["hole_id"]
    # 1. Query old_collar FIRST (before the new collar exists in the session,
    #    so the `superseded_by IS NULL` filter does not match the new row).
    old_collar = db.query(Collar).filter(
        Collar.project_id == project_id,
        Collar.hole_id == hole_id,
        Collar.superseded_by.is_(None)
    ).first()

    new_collar_id = uuid.uuid4()

    # 2. INSERT the new collar and flush it so the row exists and the FKs
    #    referencing it (collar.superseded_by self-FK, survey/assay/lithology
    #    collar_id FKs) can be satisfied by the subsequent UPDATEs.
    new_collar = Collar(
        id=new_collar_id,
        project_id=project_id,
        hole_id=hole_id,
        easting=c_data["easting"],
        northing=c_data["northing"],
        elevation=c_data["elevation"],
        utm_zone=utm_zone_confirm,
        import_batch_id=batch_id,
        hole_type=c_data.get("hole_type"),
        hole_status=c_data.get("hole_status") or "drilled",
    )
    db.add(new_collar)
    db.flush()

    # 3. Supersede the old collar (self-referential FK collar.superseded_by ->
    #    collar.id). The new collar row now exists, so the FK is satisfiable.
    if old_collar:
        old_collar.superseded_by = new_collar_id
        db.add(old_collar)
        db.flush()

        # 4. T012: re-point the old collar's children to the new collar when the
        #    batch does not re-supply that child type for this hole_id. The new
        #    collar row exists (flushed in step 2), so survey/assay/lithology
        #    collar_id UPDATEs satisfy their FKs. Per-child-type, keyed on
        #    hole_id presence in the batch.
        _repoint_children_if_not_resupplied(
            db, old_collar, new_collar_id, hole_id,
            survey_hole_ids, assay_hole_ids, lith_hole_ids
        )

    return new_collar_id


def _apply_surveys_assays_liths(db, data, collar_id_map, batch_id):
    for s_data in data.get("surveys", []):
        h_id = s_data["hole_id"]
        collar_id = collar_id_map.get(h_id)
        if collar_id:
            db.add(Survey(
                id=uuid.uuid4(), collar_id=collar_id,
                depth=s_data["depth"], dip=s_data["dip"],
                azimuth=s_data["azimuth"], desurvey_method="minimum_curvature"
            ))
    for a_data in data.get("assays", []):
        h_id = a_data["hole_id"]
        collar_id = collar_id_map.get(h_id)
        if collar_id:
            db.add(AssayInterval(
                id=uuid.uuid4(), collar_id=collar_id,
                from_depth=a_data["from_depth"], to_depth=a_data["to_depth"],
                grade_value=a_data["grade_value"],
                grade_unit=a_data["grade_unit"] or "ppm",
                below_detection_limit=a_data["below_detection_limit"],
                qaqc_flag=a_data.get("qaqc_flag"),
                import_batch_id=batch_id
            ))
    for l_data in data.get("lithologies", []):
        h_id = l_data["hole_id"]
        collar_id = collar_id_map.get(h_id)
        if collar_id:
            db.add(LithologyInterval(
                id=uuid.uuid4(), collar_id=collar_id,
                from_depth=l_data["from_depth"], to_depth=l_data["to_depth"],
                lith_code=l_data["lith_code"],
                rqd_percent=l_data.get("rqd_percent"),
                core_recovery_percent=l_data.get("core_recovery_percent")
            ))


def _commit_four_file(db, project, batch, data, utm_zone_confirm,
                      survey_hole_ids, assay_hole_ids, lith_hole_ids):
    """Legacy four-file commit path, now with the T012 child re-point fix."""
    collar_id_map = {}
    for c_data in data["collars"]:
        collar_id_map[c_data["hole_id"]] = _apply_collar(
            db, project.id, batch.id, c_data, utm_zone_confirm,
            survey_hole_ids, assay_hole_ids, lith_hole_ids
        )
    _apply_surveys_assays_liths(db, data, collar_id_map, batch.id)
    batch.status = "committed"
    db.add(batch)


def _commit_combined(db, project, batch, data, current_user, utm_zone_confirm,
                     survey_hole_ids, assay_hole_ids, lith_hole_ids):
    """Combined-CSV commit path: per-project batch fan-out (T010), trench
    supersede (T011), and the T012 child re-point fix (shared with four-file)."""
    collars = data.get("collars", [])
    surveys = data.get("surveys", [])
    trench_points = data.get("trenches", [])

    # T007/T010: resolve (creating) one project per distinct non-null zone. The
    # URL project (zone=None rows) already exists. db.flush assigns ids without
    # a full commit so collars/trenches can FK the new projects' batches.
    zone_names = [c.get("zone") for c in collars] + [t.get("zone") for t in trench_points]
    resolved = resolve_or_create_zone_projects(
        db, zone_names, current_user, utm_zone_confirm, commodity="Gold"
    )

    def project_for_zone(zone):
        if zone is None:
            return project
        key = _normalize_zone_key(zone)
        return resolved[key]["project"]

    # One ImportBatch per resolved project, all sharing the preview batch's
    # source_file blob. The URL project reuses the preview batch; the rest are
    # created here. ImportBatch.project_id is NOT NULL -> one batch per project,
    # otherwise collars in project Adel would carry an import_batch_id whose
    # batch.project_id = Abo elmajd, misattributing provenance and breaking
    # delete_project (which deletes batches by project_id while collars in other
    # projects still reference them -> IntegrityError).
    batches = {str(project.id): batch}
    for key, info in resolved.items():
        p = info["project"]
        if str(p.id) in batches:
            continue
        new_b = ImportBatch(
            id=uuid.uuid4(),
            project_id=p.id,
            source_file=batch.source_file,
            status="pending_review",
            created_by=current_user.id,
        )
        db.add(new_b)
        db.flush()
        batches[str(p.id)] = new_b

    # Stamp utm_zone on any resolved project that has none (existing projects
    # with a zone keep it; the confirmed zone only fills a null).
    for p in [project] + [info["project"] for info in resolved.values()]:
        if not p.utm_zone:
            p.utm_zone = utm_zone_confirm
            db.add(p)

    # Collars (+ surveys/assays/lithologies -- combined carries only inline
    # surveys). Each row gets its own project's batch id.
    per_project_collar_map = {}  # project_id -> {hole_id: new_collar_id}
    for c_data in collars:
        p = project_for_zone(c_data.get("zone"))
        b = batches[str(p.id)]
        new_id = _apply_collar(
            db, p.id, b.id, c_data, utm_zone_confirm,
            survey_hole_ids, assay_hole_ids, lith_hole_ids
        )
        per_project_collar_map.setdefault(str(p.id), {})[c_data["hole_id"]] = new_id

    for s_data in surveys:
        # Find the new collar in the survey's project. A hole_id is unique
        # within a project; search the project's collar map.
        placed = False
        for pid, cmap in per_project_collar_map.items():
            if s_data["hole_id"] in cmap:
                b = batches[pid]
                db.add(Survey(
                    id=uuid.uuid4(), collar_id=cmap[s_data["hole_id"]],
                    depth=s_data["depth"], dip=s_data["dip"],
                    azimuth=s_data["azimuth"], desurvey_method="minimum_curvature"
                ))
                placed = True
                break
        if not placed:
            # No matching new collar for this survey; skip (validation already
            # flagged orphans for the four-file path; combined routing always
            # pairs surveys with a collar in the same project).
            continue

    # T011: trench supersede + insert. For each (project, trench_id), mark all
    # extant active rows as superseded, setting superseded_by to the new
    # point_order=0 row (the anchor), not a per-point counterpart -- point
    # counts change between imports. Reads only ever filter
    # superseded_by IS NULL; the FK serves audit lineage alone.
    #
    # BLOCKER 2 -- FK statement ordering under PostgreSQL: the previous code
    # ran the supersede UPDATE SET superseded_by = anchor_row_id BEFORE the
    # anchor row was inserted (Query.update() emits SQL immediately while
    # autoflush=False keeps pending INSERTs unflushed). The first import passed
    # (the UPDATE matched 0 rows); the SECOND import failed because the FK
    # superseded_by -> trench.id had no target row yet. The naive "move the
    # UPDATE after the inserts" is a TRAP: the filter
    # `superseded_by IS NULL` would then also match the freshly-inserted rows
    # and supersede them against their own anchor, leaving zero active rows.
    # Capture the old row ids FIRST, insert all new rows (anchor included),
    # flush, then UPDATE only the captured old ids.
    trench_groups = {}  # (project_id, trench_id) -> [(point_data, ...)]
    for tp in trench_points:
        p = project_for_zone(tp.get("zone"))
        key = (str(p.id), tp["trench_id"])
        trench_groups.setdefault(key, (p, []))[1].append(tp)

    anchor_ids = {}  # (project_id, trench_id) -> point_order=0 row id
    for key, (p, pts) in trench_groups.items():
        anchor = next((pt for pt in pts if pt["point_order"] == 0), None)
        if anchor is None:
            anchor = pts[0]
        anchor_row_id = uuid.uuid4()
        anchor_ids[key] = anchor_row_id

        # 1. Capture the ids of the EXISTING active rows for this
        #    (project, trench_id) BEFORE inserting any new rows. Only these
        #    rows should be superseded -- the new rows must stay active.
        old_ids = [r[0] for r in db.query(Trench.id).filter(
            Trench.project_id == p.id,
            Trench.trench_id == anchor["trench_id"],
            Trench.superseded_by.is_(None),
        ).all()]

        # 2. Insert ALL new rows for this trench, including the anchor, then
        #    flush so the anchor row exists and superseded_by -> trench.id is
        #    satisfiable.
        b = batches[str(p.id)]
        for pt in pts:
            db.add(Trench(
                id=(anchor_row_id if pt is anchor else uuid.uuid4()),
                project_id=p.id,
                trench_id=pt["trench_id"],
                easting=pt["easting"],
                northing=pt["northing"],
                elevation=pt["elevation"],
                grade_value=pt.get("grade_value"),
                point_order=pt["point_order"],
                hole_type=pt.get("hole_type"),
                import_batch_id=b.id,
                dip=pt.get("dip"),
                azimuth=pt.get("azimuth"),
                sample_id=pt.get("sample_id"),
                from_depth=pt.get("from_depth"),
                to_depth=pt.get("to_depth"),
                # New rows are never themselves superseded at insert time.
                superseded_by=None,
            ))
        db.flush()

        # 3. Supersede ONLY the old rows (captured in step 1). The anchor now
        #    exists, so the FK is satisfied; the new rows stay active because
        #    they are not in old_ids.
        if old_ids:
            db.query(Trench).filter(Trench.id.in_(old_ids)).update(
                {Trench.superseded_by: anchor_row_id}, synchronize_session=False
            )

    # Insert AssayInterval rows for DD/RC sample continuation rows from the
    # combined CSV.  The assay dicts carry hole_id (not collar_id); we resolve
    # to the new collar_id via per_project_collar_map, then look up the batch
    # for that project.
    combined_assays = data.get("assays", [])
    for a_data in combined_assays:
        hid = a_data.get("hole_id")
        collar_id = None
        batch_for_assay = None
        for pid, cmap in per_project_collar_map.items():
            if hid in cmap:
                collar_id = cmap[hid]
                batch_for_assay = batches[pid]
                break
        if collar_id is None:
            # No matching collar — skip; the parse/validation already guards this.
            continue
        db.add(AssayInterval(
            id=uuid.uuid4(),
            collar_id=collar_id,
            sample_id=a_data.get("sample_id"),
            from_depth=a_data.get("from_depth") or 0.0,
            to_depth=a_data.get("to_depth") or 0.0,
            # Preserve NULL: a blank Grade column means "not assayed", which
            # the grade scale renders as Unsampled. Coercing it to 0.0 would
            # make it indistinguishable from a genuine barren result.
            grade_value=a_data.get("grade_value"),
            grade_unit=a_data.get("grade_unit") or "g/t",
            below_detection_limit=False,
            qaqc_flag=None,
            import_batch_id=batch_for_assay.id,
        ))

    # Set every batch to committed.
    for b in batches.values():
        b.status = "committed"
        db.add(b)

    # Build the per-project commit summary, aggregating by resolved project
    # (not by zone) so a zone that resolves to the URL project is merged into
    # the URL project's row rather than appearing twice.
    project_info = {str(project.id): {"project": project, "action": "appended", "batch": batch}}
    for key, info in resolved.items():
        p = info["project"]
        pid = str(p.id)
        if pid in project_info:
            # Already known (URL project matched by name); keep "appended".
            continue
        project_info[pid] = {"project": p, "action": info["action"], "batch": batches[pid]}

    counts = {pid: {"collar_count": 0, "_trench_ids": set()} for pid in project_info}
    for c in collars:
        p = project_for_zone(c.get("zone"))
        counts[str(p.id)]["collar_count"] += 1
    for tp in trench_points:
        p = project_for_zone(tp.get("zone"))
        # trench_count counts DISTINCT trench_id (one trench = N point rows),
        # not point rows -- the commit summary shows trenches, not rows.
        counts[str(p.id)]["_trench_ids"].add(tp.get("trench_id"))

    batches_payload = [
        {
            "project_id": pid,
            "project_name": info["project"].name,
            "import_batch_id": str(info["batch"].id),
            "action": info["action"],
            "collar_count": counts[pid]["collar_count"],
            "trench_count": len(counts[pid]["_trench_ids"]),
        }
        for pid, info in project_info.items()
    ]

    return {
        "message": "Combined import committed successfully",
        "import_batch_id": str(batch.id),
        "batches": batches_payload,
    }

@router.post("/{import_batch_id}/reject")
def reject_import(
    project_id: str,
    import_batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_project_or_404(project_id, db, current_user)
    try:
        b_uuid = uuid.UUID(import_batch_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Import batch not found")
        
    batch = db.query(ImportBatch).filter(
        ImportBatch.id == b_uuid,
        ImportBatch.project_id == project.id
    ).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    if batch.status != "pending_review":
        raise HTTPException(status_code=400, detail=f"Cannot reject batch in status: {batch.status}")
        
    batch.status = "rejected"
    db.add(batch)
    db.commit()
    
    return {"message": "Import batch rejected successfully", "import_batch_id": str(batch.id)}

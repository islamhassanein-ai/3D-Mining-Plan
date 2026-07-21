import sys
import os
import uuid
import json

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.src.db.session import SessionLocal
from backend.src.models.user import User
from backend.src.models.project import Project
from backend.src.models.import_batch import ImportBatch
from backend.src.models.collar import Collar
from backend.src.models.survey import Survey
from backend.src.models.assay_interval import AssayInterval
from backend.src.models.lithology_interval import LithologyInterval
from backend.src.models.trench import Trench
from backend.src.storage.local_filesystem import LocalFilesystemStorage
from backend.src.services.csv_import import (
    parse_collar_csv,
    parse_survey_csv,
    parse_assay_csv,
    parse_lithology_csv
)
from backend.src.services.import_validation import validate_import_batch
from backend.src.services.crs import detect_utm_zone
import csv as csv_module

def seed():
    db = SessionLocal()
    storage = LocalFilesystemStorage()
    try:
        # 1. Get or create default user
        email = "geologist@monark.com"
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"Creating user {email}...")
            user = User(id=uuid.uuid4(), email=email, role="owner")
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            print(f"User {email} already exists.")

        # 2. Check if demo project already exists
        # Default demo project is seeded from the Abo Elmagd Hill reference
        # dataset (drillholes + trenches extracted from the Abo Elmagd Hill
        # 3D Design Pro reference viewer) rather than the old generic fixtures.
        proj_name = "Abo Elmagd Hill (Gold)"
        project = db.query(Project).filter(Project.name == proj_name, Project.owner_id == user.id).first()
        if project:
            print(f"Project '{proj_name}' already exists.")
            # Let's clean up existing data for this project to start fresh
            print("Cleaning up old project data...")
            db.query(LithologyInterval).filter(LithologyInterval.collar_id.in_(
                db.query(Collar.id).filter(Collar.project_id == project.id)
            )).delete(synchronize_session=False)
            db.query(AssayInterval).filter(AssayInterval.collar_id.in_(
                db.query(Collar.id).filter(Collar.project_id == project.id)
            )).delete(synchronize_session=False)
            db.query(Survey).filter(Survey.collar_id.in_(
                db.query(Collar.id).filter(Collar.project_id == project.id)
            )).delete(synchronize_session=False)
            db.query(Collar).filter(Collar.project_id == project.id).delete(synchronize_session=False)
            db.query(Trench).filter(Trench.project_id == project.id).delete(synchronize_session=False)
            db.query(ImportBatch).filter(ImportBatch.project_id == project.id).delete(synchronize_session=False)
            project.utm_zone = None
            db.commit()
        else:
            print(f"Creating project '{proj_name}'...")
            project = Project(
                id=uuid.uuid4(),
                name=proj_name,
                commodity="Gold",
                utm_zone=None,
                owner_id=user.id
            )
            db.add(project)
            db.commit()
            db.refresh(project)

        # 3. Read fixtures (Abo Elmagd Hill reference dataset)
        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures", "reference_project")
        with open(os.path.join(fixtures_dir, "collars.csv"), "rb") as f:
            collar_content = f.read()
        with open(os.path.join(fixtures_dir, "surveys.csv"), "rb") as f:
            survey_content = f.read()
        with open(os.path.join(fixtures_dir, "assays.csv"), "rb") as f:
            assay_content = f.read()
        with open(os.path.join(fixtures_dir, "trenches.csv"), "r", encoding="utf-8", newline="") as f:
            trench_rows = list(csv_module.DictReader(f))

        # Parse CSVs (reference dataset has no lithology data)
        collars, c_errs = parse_collar_csv(collar_content)
        surveys, s_errs = parse_survey_csv(survey_content)
        assays, a_errs = parse_assay_csv(assay_content)
        lithologies, l_errs = [], []

        if c_errs or s_errs or a_errs or l_errs:
            print("Errors parsing CSVs:")
            print("Collar errs:", c_errs)
            print("Survey errs:", s_errs)
            print("Assay errs:", a_errs)
            print("Lithology errs:", l_errs)
            return

        # Validate
        validation_res = validate_import_batch(collars, surveys, assays, lithologies, None, [])
        issues = validation_res["issues"]
        has_errors = any(issue["type"] == "error" for issue in issues)
        if has_errors:
            print("Validation errors detected:", issues)
            return

        # Abo Elmagd Hill is surveyed in UTM Zone 37N -- detect_utm_zone() is
        # metadata-only (it doesn't actually infer a zone from coordinates),
        # so the correct zone has to be supplied explicitly here rather than
        # falling back to the generic 36N default used elsewhere.
        detected_zone = detect_utm_zone(
            [c["easting"] for c in collars],
            [c["northing"] for c in collars],
            "37N"
        )
        print("Detected UTM Zone:", detected_zone)

        # Save batch file ref
        payload = {
            "valid": True,
            "detected_utm_zone": detected_zone,
            "issues": issues,
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
                "error_count": 0,
                "warning_count": len([i for i in issues if i["type"] == "warning"])
            }
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        file_ref = storage.save(payload_bytes, f"{uuid.uuid4().hex}.json")

        # Create ImportBatch
        batch = ImportBatch(
            id=uuid.uuid4(),
            project_id=project.id,
            source_file=file_ref,
            status="pending_review",
            created_by=user.id
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)
        print("Import batch created with ID:", batch.id)

        # Confirm UTM Zone & Commit batch
        project.utm_zone = detected_zone
        db.add(project)

        collar_id_map = {}
        for c_data in collars:
            hole_id = c_data["hole_id"]
            new_collar_id = uuid.uuid4()
            collar_id_map[hole_id] = new_collar_id
            
            new_collar = Collar(
                id=new_collar_id,
                project_id=project.id,
                hole_id=hole_id,
                easting=c_data["easting"],
                northing=c_data["northing"],
                elevation=c_data["elevation"],
                utm_zone=detected_zone,
                import_batch_id=batch.id
            )
            db.add(new_collar)
            
        for s_data in surveys:
            h_id = s_data["hole_id"]
            collar_id = collar_id_map.get(h_id)
            if collar_id:
                new_survey = Survey(
                    id=uuid.uuid4(),
                    collar_id=collar_id,
                    depth=s_data["depth"],
                    dip=s_data["dip"],
                    azimuth=s_data["azimuth"],
                    desurvey_method="minimum_curvature"
                )
                db.add(new_survey)
                
        for a_data in assays:
            h_id = a_data["hole_id"]
            collar_id = collar_id_map.get(h_id)
            if collar_id:
                new_assay = AssayInterval(
                    id=uuid.uuid4(),
                    collar_id=collar_id,
                    from_depth=a_data["from_depth"],
                    to_depth=a_data["to_depth"],
                    grade_value=a_data["grade_value"],
                    grade_unit=a_data["grade_unit"] or "ppm",
                    below_detection_limit=a_data["below_detection_limit"],
                    import_batch_id=batch.id
                )
                db.add(new_assay)
                
        for l_data in lithologies:
            h_id = l_data["hole_id"]
            collar_id = collar_id_map.get(h_id)
            if collar_id:
                new_lith = LithologyInterval(
                    id=uuid.uuid4(),
                    collar_id=collar_id,
                    from_depth=l_data["from_depth"],
                    to_depth=l_data["to_depth"],
                    lith_code=l_data["lith_code"]
                )
                db.add(new_lith)

        for t_data in trench_rows:
            new_trench = Trench(
                id=uuid.uuid4(),
                project_id=project.id,
                trench_id=t_data["trench_id"],
                easting=float(t_data["easting"]),
                northing=float(t_data["northing"]),
                elevation=float(t_data["elevation"]) if t_data.get("elevation") else None,
                grade_value=float(t_data["grade_value"]) if t_data.get("grade_value") else None
            )
            db.add(new_trench)

        batch.status = "committed"
        db.add(batch)
        db.commit()
        print(f"Demo project data seeded and committed successfully! ({len(collars)} holes, {len(trench_rows)} trench points)")
        
    except Exception as e:
        db.rollback()
        print("Error during seed:", e)
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed()

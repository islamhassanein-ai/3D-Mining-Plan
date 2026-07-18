import csv
import io
import zipfile
import json
from typing import List, Dict, Any


def export_collars_csv(collars: List[Dict[str, Any]], utm_zone: str) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["hole_id", "easting", "northing", "elevation", "utm_zone"])
    for c in collars:
        writer.writerow([c.get("hole_id"), c.get("easting"), c.get("northing"), c.get("elevation"), utm_zone])
    return buf.getvalue().encode("utf-8")


def export_surveys_csv(surveys: List[Dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["hole_id", "depth", "dip", "azimuth"])
    for s in surveys:
        writer.writerow([s.get("hole_id"), s.get("depth"), s.get("dip"), s.get("azimuth")])
    return buf.getvalue().encode("utf-8")


def export_assays_csv(assays: List[Dict[str, Any]]) -> bytes:
    # Same re-importable BDL-prefix encoding as the bundled ZIP export --
    # see the comment in export_drillholes_to_csv for why this matters.
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["hole_id", "from_depth", "to_depth", "grade_value", "grade_unit", "below_detection_limit"])
    for a in assays:
        grade_value = a.get("grade_value")
        if a.get("below_detection_limit") and grade_value is not None:
            grade_value = f"<{grade_value}"
        writer.writerow([
            a.get("hole_id"),
            a.get("from_depth"),
            a.get("to_depth"),
            grade_value,
            a.get("grade_unit"),
            a.get("below_detection_limit")
        ])
    return buf.getvalue().encode("utf-8")


def export_lithologies_csv(lithologies: List[Dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["hole_id", "from_depth", "to_depth", "lithology_code", "description", "rqd", "recovery"])
    for l in lithologies:
        writer.writerow([
            l.get("hole_id"),
            l.get("from_depth"),
            l.get("to_depth"),
            l.get("lithology_code"),
            l.get("description"),
            l.get("rqd"),
            l.get("recovery")
        ])
    return buf.getvalue().encode("utf-8")

def export_drillholes_to_csv(
    project_name: str,
    utm_zone: str,
    collars: List[Dict[str, Any]],
    surveys: List[Dict[str, Any]],
    assays: List[Dict[str, Any]],
    lithologies: List[Dict[str, Any]]
) -> bytes:
    """
    Compiles collars, surveys, assays, and lithologies into separate CSV sheets
    and bundles them into a ZIP archive, including a project metadata.json file.
    """
    buffer = io.BytesIO()
    
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # 1. collars.csv
        collars_io = io.StringIO()
        collars_writer = csv.writer(collars_io)
        collars_writer.writerow(["hole_id", "easting", "northing", "elevation", "utm_zone"])
        for c in collars:
            collars_writer.writerow([c.get("hole_id"), c.get("easting"), c.get("northing"), c.get("elevation"), utm_zone])
        zip_file.writestr("collars.csv", collars_io.getvalue())
        
        # 2. surveys.csv
        surveys_io = io.StringIO()
        surveys_writer = csv.writer(surveys_io)
        surveys_writer.writerow(["hole_id", "depth", "dip", "azimuth"])
        for s in surveys:
            surveys_writer.writerow([s.get("hole_id"), s.get("depth"), s.get("dip"), s.get("azimuth")])
        zip_file.writestr("surveys.csv", surveys_io.getvalue())
        
        # 3. assays.csv
        # grade_unit is included, and BDL rows are written with the "<" prefix
        # (e.g. "<0.01") the CSV import parser (parse_bdl_value) actually reads
        # to detect below-detection-limit status -- the parser does not read a
        # separate below_detection_limit column at all, it derives BDL purely
        # from this prefix. A below_detection_limit column is also included as
        # a human-readable cross-check, but grade_value's prefix is what makes
        # this export genuinely re-importable without losing BDL status
        # (constitution Principle I).
        assays_io = io.StringIO()
        assays_writer = csv.writer(assays_io)
        assays_writer.writerow(["hole_id", "from_depth", "to_depth", "grade_value", "grade_unit", "below_detection_limit"])
        for a in assays:
            grade_value = a.get("grade_value")
            if a.get("below_detection_limit") and grade_value is not None:
                grade_value = f"<{grade_value}"
            assays_writer.writerow([
                a.get("hole_id"),
                a.get("from_depth"),
                a.get("to_depth"),
                grade_value,
                a.get("grade_unit"),
                a.get("below_detection_limit")
            ])
        zip_file.writestr("assays.csv", assays_io.getvalue())
        
        # 4. lithologies.csv
        lith_io = io.StringIO()
        lith_writer = csv.writer(lith_io)
        lith_writer.writerow(["hole_id", "from_depth", "to_depth", "lithology_code", "description", "rqd", "recovery"])
        for l in lithologies:
            lith_writer.writerow([
                l.get("hole_id"),
                l.get("from_depth"),
                l.get("to_depth"),
                l.get("lithology_code"),
                l.get("description"),
                l.get("rqd"),
                l.get("recovery")
            ])
        zip_file.writestr("lithologies.csv", lith_io.getvalue())
        
        # 5. metadata.json
        metadata = {
            "project_name": project_name,
            "utm_zone": utm_zone,
            "counts": {
                "collars": len(collars),
                "surveys": len(surveys),
                "assays": len(assays),
                "lithologies": len(lithologies)
            }
        }
        zip_file.writestr("metadata.json", json.dumps(metadata, indent=2))
        
    buffer.seek(0)
    return buffer.getvalue()

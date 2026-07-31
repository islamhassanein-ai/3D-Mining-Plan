"""Repair survey dips that were imported in the "degrees below horizontal"
convention and are therefore desurveying upward.

Symptom: every assay interval in a hole plots ABOVE the collar, so samples
logged at 30-40 m appear stacked at the top of the hole. The depths are right;
the trajectory is inverted.

A project is repaired only when EVERY drilled (DD/RC) hole in it has all
positive dips -- surface drilling cannot go upward, so that is unambiguous.
Projects with mixed signs are already using the signed convention and are left
alone, as are trenches (TR/CH/FC), where a positive dip is a real uphill ground
slope.

    venv\\Scripts\\python.exe backend\\fix_dip_convention.py            # dry run
    venv\\Scripts\\python.exe backend\\fix_dip_convention.py --apply    # write
    venv\\Scripts\\python.exe backend\\fix_dip_convention.py --revert   # undo
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.src.db.session import SessionLocal
from backend.src.models.collar import Collar
from backend.src.models.project import Project
from backend.src.models.survey import Survey
from backend.src.services.dip_convention import POSITIVE_DOWN, detect_dip_convention

TRENCH_TYPES = {"TR", "CH", "FC"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the corrected dips")
    ap.add_argument("--revert", action="store_true",
                    help="flip corrected dips back to positive")
    args = ap.parse_args()

    db = SessionLocal()
    total = 0

    for project in db.query(Project).filter(Project.superseded_by.is_(None)).all():
        collars = db.query(Collar).filter(
            Collar.project_id == project.id,
            Collar.superseded_by.is_(None),
        ).all()
        if not collars:
            continue

        drilled = [c for c in collars if (c.hole_type or "DD").upper() not in TRENCH_TYPES]
        if not drilled:
            continue

        rows = []
        for c in drilled:
            rows.extend(db.query(Survey).filter(Survey.collar_id == c.id).all())
        if not rows:
            continue

        dips = [float(s.dip) for s in rows]

        if args.revert:
            # Undo: only touch projects that are now all-negative.
            non_zero = [d for d in dips if abs(d) > 1e-9]
            needs = bool(non_zero) and all(d < 0 for d in non_zero)
            action = "revert"
        else:
            needs = detect_dip_convention(dips, [None] * len(dips)) == POSITIVE_DOWN
            action = "fix"

        if not needs:
            print("  skip  %-28s (dips already look correct)" % project.name)
            continue

        sample = ", ".join("%.0f" % d for d in dips[:4])
        print("  %-5s %-28s %d holes, %d survey rows  [%s ...]"
              % (action.upper(), project.name, len(drilled), len(rows), sample))

        if args.apply:
            for s in rows:
                s.dip = abs(float(s.dip)) if args.revert else -abs(float(s.dip))
            total += len(rows)

    if args.apply:
        db.commit()
        print("\nUpdated %d survey rows." % total)
    else:
        print("\nDry run -- nothing written. Re-run with --apply to commit.")


if __name__ == "__main__":
    main()

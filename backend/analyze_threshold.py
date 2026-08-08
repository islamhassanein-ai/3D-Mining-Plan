"""Threshold evidence for a project: log-probability, metal capture, contacts.

Produces the three lines of evidence a grade-domain threshold has to be argued
from. It selects nothing and recommends nothing -- see
``specs/007-grade-domain-shells/OPEN_QUESTIONS.md`` decision D8.

Usage, from the repo root:

    venv\\Scripts\\python.exe -m backend.analyze_threshold "Adel"
    venv\\Scripts\\python.exe -m backend.analyze_threshold "Adel" --types DDH,TR

``--types`` restricts the population. Under decision D6 face channels are
geometry-only and cast no vote on grade, so ``DDH,TR`` is the population that
would actually drive an Adel shell; the default reports every type present, one
section each, plus that combination.
"""
import sys

from backend.src.db.session import SessionLocal
from backend.src.models.project import Project
from backend.src.services.composite_points import extract_composite_points
from backend.src.services.threshold_analysis import (
    contact_analysis,
    log_probability_points,
    metal_capture_curve,
)

CANDIDATES = [0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0, 2.0, 5.0]


def _fmt(value, spec=".3f"):
    return "n/a" if value is None else format(value, spec)


def _capture(composites, label):
    print("\n--- metal capture: {} (n={}) ---".format(label, len(composites)))
    if not composites:
        print("  (empty)")
        return
    print("  {:>7} {:>7} {:>10} {:>10} {:>12} {:>12}".format(
        "cutoff", "n", "length", "% length", "% metal", "mean above"))
    for row in metal_capture_curve(composites, CANDIDATES):
        print("  {:>7} {:>7} {:>10.1f} {:>10} {:>12} {:>12}".format(
            row.threshold, row.n_above, row.length_above,
            _fmt(row.length_fraction, ".1%"),
            _fmt(row.metal_fraction, ".1%"),
            _fmt(row.mean_grade_above, ".3f")))


def _logprob(composites, label):
    result = log_probability_points(composites)
    print("\n--- log-probability: {} ---".format(label))
    if not result.points:
        print("  (no positive grades)")
        return
    print("  {} point(s), {} non-positive excluded".format(
        len(result.points), result.n_excluded_non_positive))
    print("  {:>10} {:>12}   {}".format("cum prob", "grade", "break in slope?"))
    points = result.points
    # Sample the curve evenly; an inflection between two population is visible
    # as the grade jumping much faster over one step than its neighbours.
    step = max(1, len(points) // 20)
    sampled = points[::step]
    previous_ratio = None
    for i, p in enumerate(sampled):
        marker = ""
        if i and sampled[i - 1].grade > 0:
            ratio = p.grade / sampled[i - 1].grade
            if previous_ratio and previous_ratio > 0:
                if ratio > 2.5 * previous_ratio:
                    marker = "  <-- slope steepens sharply"
            previous_ratio = ratio
        print("  {:>10.3f} {:>12.4f}{}".format(
            p.cumulative_probability, p.grade, marker))


def _contacts(composites, label, thresholds):
    for threshold in thresholds:
        bins = contact_analysis(composites, threshold, bin_width=10.0,
                                max_distance=60.0)
        populated = [b for b in bins if b.n]
        if not populated:
            continue
        print("\n--- contact analysis: {} at {} g/t ---".format(label, threshold))
        print("  {:>10} {:>6} {:>12} {:>16}".format(
            "distance", "n", "mean", "length-wtd mean"))
        for b in populated:
            print("  {:>10.1f} {:>6} {:>12} {:>16}".format(
                b.distance_bin_center, b.n,
                _fmt(b.mean_grade), _fmt(b.length_weighted_mean_grade)))


def main(argv):
    types = None
    if "--types" in argv:
        index = argv.index("--types")
        types = [t.strip().upper() for t in argv[index + 1].split(",")]
        argv = argv[:index] + argv[index + 2:]

    names = [a for a in argv[1:] if not a.startswith("--")]
    if not names:
        print("Usage: python -m backend.analyze_threshold \"<project name>\"")
        return

    db = SessionLocal()
    try:
        for name in names:
            project = db.query(Project).filter(Project.name == name).first()
            if project is None:
                print("No project named {!r}".format(name))
                continue

            result = extract_composite_points(db, project.id)
            composites = result.composites
            print("=" * 78)
            print("THRESHOLD EVIDENCE: {}".format(project.name))
            print("=" * 78)
            print("This selects nothing. It reports what the data does under")
            print("each candidate cut-off; the threshold is a geological choice.")

            present = sorted({c.sample_type for c in composites})
            groups = []
            if types:
                groups.append((",".join(types),
                               [c for c in composites if c.sample_type in types]))
            else:
                for t in present:
                    groups.append((t, [c for c in composites
                                       if c.sample_type == t]))
                if "DDH" in present and "TR" in present:
                    groups.append((
                        "DDH+TR (the D6 modelling population)",
                        [c for c in composites
                         if c.sample_type in ("DDH", "TR")]))

            for label, subset in groups:
                _capture(subset, label)
                _logprob(subset, label)

            main_label, main_set = groups[-1]
            _contacts(main_set, main_label, [0.2, 0.3, 0.5])
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv)

"""Run the DDH vs TR/FC comparison against a real project in the database.

This is the evidence for the open trench-influence question (Q1 in
``specs/007-grade-domain-shells/OPEN_QUESTIONS.md``): whether trench and channel
samples should inform grade interpolation, be weighted down, or be used for
geometry only. It reports and stops -- no weighting is chosen here.

Usage, from the repo root:

    venv\\Scripts\\python.exe -m backend.analyze_sample_types
    venv\\Scripts\\python.exe -m backend.analyze_sample_types "Adel"
    venv\\Scripts\\python.exe -m backend.analyze_sample_types "Adel" --trench-length 1.0

With no project name, every project carrying both drilling and trenches is
listed. ``--trench-length`` includes trench rows that state no sample length,
under the length given; without it they are excluded and counted, because
inventing a sample length would silently set the support of the whole trench
population.
"""
import sys

from backend.src.db.session import SessionLocal
from backend.src.models.project import Project
from backend.src.services.composite_points import extract_composite_points
from backend.src.services.sample_type_comparison import compare_sample_types


def _fmt(value, spec=".3f"):
    return "n/a" if value is None else format(value, spec)


def _print_population(stats):
    print(
        "  {:<6} n={:<6} mean={:<9} lw_mean={:<9} cv={:<8} "
        "min={:<8} p25={:<8} median={:<8} p75={:<8} max={:<9} length={}".format(
            stats.sample_type,
            stats.n,
            _fmt(stats.mean),
            _fmt(stats.length_weighted_mean),
            _fmt(stats.cv),
            _fmt(stats.minimum),
            _fmt(stats.p25),
            _fmt(stats.median),
            _fmt(stats.p75),
            _fmt(stats.maximum),
            _fmt(stats.total_length, ".1f"),
        )
    )


def analyze(project_name, trench_length=None, composite_length=1.0):
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.name == project_name).first()
        if project is None:
            print("No project named {!r}".format(project_name))
            return None

        result = extract_composite_points(
            db,
            project.id,
            composite_length=composite_length,
            trench_length_when_unspecified=trench_length,
        )
        report = result.report

        print("=" * 78)
        print("PROJECT: {}".format(project.name))
        print("=" * 78)
        print("grade unit                : {}".format(report.grade_unit or "n/a"))
        print("collars by hole_type      : {}".format(report.collars_by_hole_type))
        print("collars considered        : {}".format(report.n_collars_considered))
        print("assay intervals read      : {} ({} unassayed)".format(
            report.n_assay_intervals_read, report.n_unassayed_assay_intervals))
        print("trench rows read          : {} ({} unassayed)".format(
            report.n_trench_rows_read, report.n_unassayed_trench_rows))
        print("trench lines considered   : {}".format(report.n_trench_lines_considered))
        print("composites by sample type : {}".format(report.composites_by_type))
        print("total composites          : {}".format(len(result.composites)))

        if report.skipped:
            print("\nSKIPPED ({}):".format(len(report.skipped)))
            for entry in report.skipped[:10]:
                print("  - {}".format(entry))
            if len(report.skipped) > 10:
                print("  ... and {} more".format(len(report.skipped) - 10))

        if report.warnings:
            print("\nWARNINGS ({}):".format(len(report.warnings)))
            for entry in report.warnings[:10]:
                print("  - {}".format(entry))
            if len(report.warnings) > 10:
                print("  ... and {} more".format(len(report.warnings) - 10))

        if not result.composites:
            print("\nNo composites -- nothing to compare.")
            return result

        comparison = compare_sample_types(result.composites)

        print("\nPOPULATIONS")
        for sample_type in sorted(comparison.by_type):
            _print_population(comparison.by_type[sample_type])
        _print_population(comparison.pooled)

        print("\nRATIOS (non-DDH vs DDH)")
        print("  length-weighted grade ratio : {}".format(_fmt(comparison.grade_ratio)))
        print("  plain mean ratio            : {}".format(_fmt(comparison.mean_ratio)))

        print("\nSCREENING (advisory -- not a statistical test)")
        print("  comparable: {}".format(comparison.comparable))
        for reason in comparison.reasons:
            print("    - {}".format(reason))

        points = comparison.qq_points
        if points:
            print("\nQ-Q (DDH grade -> non-DDH grade at the same quantile)")
            for index in (0, len(points) // 4, len(points) // 2,
                          3 * len(points) // 4, len(points) - 1):
                ddh, other = points[index]
                ratio = other / ddh if ddh > 0 else None
                print("    q{:>5.2f}  {:>9.3f} -> {:>9.3f}   ratio {}".format(
                    0.01 + index * (0.98 / (len(points) - 1)) if len(points) > 1 else 0.5,
                    ddh, other, _fmt(ratio, ".2f")))

        return result
    finally:
        db.close()


def main(argv):
    trench_length = None
    if "--trench-length" in argv:
        index = argv.index("--trench-length")
        trench_length = float(argv[index + 1])
        argv = argv[:index] + argv[index + 2:]

    names = [a for a in argv[1:] if not a.startswith("--")]
    if names:
        for name in names:
            analyze(name, trench_length)
            print()
        return

    db = SessionLocal()
    try:
        print("Projects in the database (pass a name to analyze one):")
        for project in db.query(Project).order_by(Project.name).all():
            print("  {}".format(project.name))
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv)

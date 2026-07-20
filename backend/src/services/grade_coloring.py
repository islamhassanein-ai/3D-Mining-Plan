# Six-bucket Au grade scale, brackets and colors copied verbatim from the
# Abo Elmagd Hill 3D Design Pro reference viewer so the legend and cylinder
# colors here match that source exactly.
GRADE_BUCKETS = [
    # (upper_bound_exclusive_or_None, hex_color, label)
    (0.01, "#7d8b8f", "0 - 0.01"),   # Background / waste
    (0.05, "#2b24eb", "0.01 - 0.05"),
    (0.1, "#27ea5b", "0.05 - 0.1"),
    (0.5, "#fef600", "0.1 - 0.5"),
    (1.0, "#f72809", "0.5 - 1.0"),
    (None, "#ff00ff", "> 1.0"),      # High grade
]


def get_grade_bucket_index(grade_value: float, grade_unit: str = "ppm") -> int:
    """Returns the 0-based bucket index (0 = background, 5 = high grade)."""
    val = float(grade_value)
    if grade_unit == "%":
        val = val * 10000.0  # 1% = 10,000 ppm

    for i, (upper, _color, _label) in enumerate(GRADE_BUCKETS):
        if upper is None or val < upper:
            return i
    return len(GRADE_BUCKETS) - 1


def get_grade_color(grade_value: float, grade_unit: str = "ppm") -> str:
    """Returns a hex color string for a given grade value.

    Uses the six-bucket Au grade scale from the reference 3D viewer:
    - < 0.01 ppm: Gray (background)
    - 0.01 - 0.05 ppm: Blue
    - 0.05 - 0.1 ppm: Green
    - 0.1 - 0.5 ppm: Yellow
    - 0.5 - 1.0 ppm: Red
    - >= 1.0 ppm: Magenta (high grade)
    """
    idx = get_grade_bucket_index(grade_value, grade_unit)
    return GRADE_BUCKETS[idx][1]

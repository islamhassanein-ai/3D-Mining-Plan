"""Canonical Au grade scale (g/t).

This module is the single source of truth for grade brackets, colors and
labels. ``frontend/src/scene/grade_scale.js`` mirrors it verbatim -- keep the
two diffable, and change both together.

The scale has six graded buckets plus a separate *Unsampled* category. The
unsampled category is NOT a bucket: it covers rows with a NULL assay or a
placeholder sample id ('Unsampled', 'NSR', 'NS', 'No Sample', 'No Samples'),
which must never be coerced to 0.0 g/t -- a barren-looking grey interval and
a "we never assayed this" gap mean very different things to a geologist.
"""
from typing import Optional

# (upper_bound_exclusive_or_None, hex_color, label)
#
# Shades are tuned for separation on the dark 3D viewport (#0d1524). The
# constraint that matters is perceptual distance between ADJACENT buckets --
# those are the ones that sit next to each other on a drill trace and have to
# be told apart at a glance. Worst adjacent pair is dE(CIE76) ~56; the previous
# orange/red boundary was ~35, which read as one colour under scene shading.
# Categories and hue order (grey -> blue -> green -> amber -> red -> magenta)
# are unchanged.
GRADE_BUCKETS = [
    (0.10, "#9aa7b8", "< 0.10"),        # Light neutral grey -- below background
    (0.30, "#2b7fff", "0.10 - 0.30"),   # Vivid blue
    (0.50, "#21d07a", "0.30 - 0.50"),   # Spring green
    (1.00, "#ffc233", "0.50 - 1.00"),   # Amber
    (3.00, "#ff5a1f", "1.00 - 3.00"),   # Orange-red
    (None, "#ff2bd6", ">= 3.00"),       # Magenta -- high grade
]

# Rendered for intervals with no assay result. Near-black rather than pure
# #000000 so the tube still catches scene lighting and reads as geometry
# instead of a hole in the depth buffer.
UNSAMPLED_COLOR = "#141414"
UNSAMPLED_LABEL = "No Sample"

# Sentinel index returned by get_grade_bucket_index for unsampled intervals.
UNSAMPLED_BUCKET_INDEX = -1

# Case-insensitive Sample_ID placeholders that mean "this interval was never
# assayed". Compared after strip() + casefold().
UNSAMPLED_SAMPLE_IDS = {
    "unsampled",
    "nsr",
    "ns",
    "no sample",
    "no samples",
}


def is_unsampled(grade_value, sample_id: Optional[str] = None) -> bool:
    """True when an interval carries no usable assay result.

    Covers NULL/None grades, non-numeric grades, and the placeholder
    ``Sample_ID`` values in ``UNSAMPLED_SAMPLE_IDS``. Never raises -- a bad
    value is treated as unsampled rather than propagating a ValueError into
    color lookup.
    """
    if sample_id is not None:
        if str(sample_id).strip().casefold() in UNSAMPLED_SAMPLE_IDS:
            return True

    if grade_value is None:
        return True

    try:
        val = float(grade_value)
    except (TypeError, ValueError):
        return True

    # NaN compares unequal to itself.
    return val != val


def get_grade_bucket_index(
    grade_value,
    grade_unit: str = "g/t",
    sample_id: Optional[str] = None,
) -> int:
    """0-based bucket index, or ``UNSAMPLED_BUCKET_INDEX`` (-1) if unsampled.

    Bucket 0 = ``< 0.10`` g/t, bucket 5 = ``>= 3.00`` g/t.
    """
    if is_unsampled(grade_value, sample_id):
        return UNSAMPLED_BUCKET_INDEX

    val = float(grade_value)
    if grade_unit == "%":
        val = val * 10000.0  # 1% = 10,000 ppm = 10,000 g/t

    for i, (upper, _color, _label) in enumerate(GRADE_BUCKETS):
        if upper is None or val < upper:
            return i
    return len(GRADE_BUCKETS) - 1


def get_grade_color(
    grade_value,
    grade_unit: str = "g/t",
    sample_id: Optional[str] = None,
) -> str:
    """Hex color for a grade value on the canonical Au scale.

    Returns ``UNSAMPLED_COLOR`` for NULL / NaN / placeholder-sample rows, so
    callers can pass raw database values without pre-filtering.
    """
    idx = get_grade_bucket_index(grade_value, grade_unit, sample_id)
    if idx == UNSAMPLED_BUCKET_INDEX:
        return UNSAMPLED_COLOR
    return GRADE_BUCKETS[idx][1]

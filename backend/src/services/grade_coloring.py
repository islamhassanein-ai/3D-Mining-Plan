def get_grade_color(grade_value: float, grade_unit: str = "ppm") -> str:
    """Returns a hex color string for a given grade value.
    
    Uses standard geological cutoff brackets suitable for gold exploration:
    - < 0.1 ppm: Gray (waste)
    - 0.1 - 0.5 ppm: Green (low grade)
    - 0.5 - 1.0 ppm: Blue (medium-low grade)
    - 1.0 - 5.0 ppm: Yellow/Orange (medium grade)
    - >= 5.0 ppm: Red (high grade)
    """
    # Convert value if needed (everything standardized to ppm/g_t for lookup)
    # 1 ppm = 1 g/t = 0.0001%
    val = float(grade_value)
    if grade_unit == "%":
        val = val * 10000.0  # Convert percent to ppm (1% = 10,000 ppm)
        
    if val < 0.1:
        return "#9ca3af"  # Gray
    elif val < 0.5:
        return "#34d399"  # Light Green
    elif val < 1.0:
        return "#60a5fa"  # Blue
    elif val < 5.0:
        return "#fbbf24"  # Yellow/Orange
    else:
        return "#f87171"  # Red

import io
import math
from typing import List, Dict, Any, Optional, Tuple
from reportlab.pdfgen import canvas
from reportlab.lib import colors

from backend.src.services.grade_coloring import GRADE_BUCKETS


def _plane_normal(plane_type: str, azimuth_deg: float) -> Tuple[float, float, float]:
    """Plane normal in Y-up space (X=Easting, Y=Elevation, Z=Northing), matching
    frontend/src/scene/slicing_plane.js's updatePlaneOrientation exactly."""
    if plane_type == "EW":
        return (1.0, 0.0, 0.0)
    if plane_type == "NS":
        return (0.0, 0.0, 1.0)
    rad = math.radians(azimuth_deg)
    return (math.cos(rad), 0.0, math.sin(rad))


def _distance_to_plane(point: Tuple[float, float, float], center: Tuple[float, float, float], offset: float, normal: Tuple[float, float, float]) -> float:
    origin = (center[0] + normal[0] * offset, center[1] + normal[1] * offset, center[2] + normal[2] * offset)
    diff = (point[0] - origin[0], point[1] - origin[1], point[2] - origin[2])
    return diff[0] * normal[0] + diff[1] * normal[1] + diff[2] * normal[2]


def _project_point_2d(point: Tuple[float, float, float], plane_type: str, azimuth_deg: float) -> Tuple[float, float]:
    """Matches frontend/src/scene/slicing_plane.js's projectPoint2D."""
    v = point[1]  # Elevation
    if plane_type == "EW":
        u = point[2]  # Northing
    elif plane_type == "NS":
        u = point[0]  # Easting
    else:
        rad = math.radians(azimuth_deg)
        tangent = (-math.sin(rad), 0.0, math.cos(rad))
        u = point[0] * tangent[0] + point[1] * tangent[1] + point[2] * tangent[2]
    return (u, v)


def compute_section_plane_view(
    collars: List[Dict[str, Any]],
    traces: List[Dict[str, Any]],
    plane_type: str = "EW",
    offset: float = 0.0,
    thickness: float = 20.0,
    azimuth: float = 0.0
) -> Dict[str, Any]:
    """Slices collars/traces by the given plane (same math as slicing_plane.js's
    sliceDrillholes), projecting the surviving points to 2D (u, v) so the PDF
    export matches whatever section is currently on screen (FR-006), instead of
    always rendering a fixed full-project view.

    Returns 2D collars/traces already projected, ready for direct plotting.
    """
    normal = _plane_normal(plane_type, azimuth)
    half_thick = thickness / 2.0

    # Center = bounding-box midpoint over all collar positions and trace
    # points, in Y-up space (X=Easting, Y=Elevation, Z=Northing) -- matches
    # frontend/src/components/section_view_panel.js's setDrillholes().
    all_points: List[Tuple[float, float, float]] = []
    for c in collars:
        all_points.append((c["easting"], c["elevation"], c["northing"]))
    for tr in traces:
        for p in tr.get("points", []):
            all_points.append((p["x"], p["z"], p["y"]))

    if all_points:
        xs = [p[0] for p in all_points]
        ys = [p[1] for p in all_points]
        zs = [p[2] for p in all_points]
        center = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0, (min(zs) + max(zs)) / 2.0)
    else:
        center = (0.0, 0.0, 0.0)

    sliced_collars = []
    for c in collars:
        pt = (c["easting"], c["elevation"], c["northing"])
        if abs(_distance_to_plane(pt, center, offset, normal)) <= half_thick:
            u, v = _project_point_2d(pt, plane_type, azimuth)
            sliced_collars.append({"hole_id": c.get("hole_id", "DH"), "u": u, "v": v})

    sliced_traces = []
    for tr in traces:
        points_2d = []
        for p in tr.get("points", []):
            pt = (p["x"], p["z"], p["y"])
            if abs(_distance_to_plane(pt, center, offset, normal)) <= half_thick:
                u, v = _project_point_2d(pt, plane_type, azimuth)
                points_2d.append((u, v))
        if len(points_2d) >= 2:
            sliced_traces.append({"hole_id": tr.get("hole_id", ""), "points": points_2d})

    return {"collars_2d": sliced_collars, "traces_2d": sliced_traces, "center": center}


def _slice_assay_segments(
    assay_segments: List[Dict[str, Any]],
    plane_type: str,
    offset: float,
    thickness: float,
    azimuth: float,
    center: Tuple[float, float, float]
) -> List[Dict[str, Any]]:
    """Slices assay intervals by the same plane as collars/traces, keeping a
    segment when its midpoint falls within the slab -- mirroring how
    slicing_plane.js treats assay intervals on screen (by their midpoint)."""
    normal = _plane_normal(plane_type, azimuth)
    half_thick = thickness / 2.0
    out = []
    for seg in assay_segments:
        s, e = seg["start"], seg["end"]
        # seg coords are stored (x=Easting, y=Northing, z=Elevation); the
        # plane math works in Y-up space (Easting, Elevation, Northing), so
        # remap here before projecting/slicing.
        sp = (s["x"], s["z"], s["y"])
        ep = (e["x"], e["z"], e["y"])
        mid = ((sp[0] + ep[0]) / 2.0, (sp[1] + ep[1]) / 2.0, (sp[2] + ep[2]) / 2.0)
        if abs(_distance_to_plane(mid, center, offset, normal)) <= half_thick:
            u0, v0 = _project_point_2d(sp, plane_type, azimuth)
            u1, v1 = _project_point_2d(ep, plane_type, azimuth)
            out.append({
                "hole_id": seg["hole_id"],
                "start": (u0, v0),
                "end": (u1, v1),
                "grade_value": seg["grade_value"],
                "grade_unit": seg.get("grade_unit", "ppm"),
                "color": seg["color"]
            })
    return out


def export_section_to_pdf(
    project_name: str,
    section_name: str,
    collars: List[Dict[str, Any]],
    traces: List[Dict[str, Any]],
    wireframe_intersects: List[Dict[str, Any]],
    plane_params: Optional[Dict[str, Any]] = None,
    assay_segments: Optional[List[Dict[str, Any]]] = None
) -> bytes:
    """
    Generates a scaled 2D cross-section PDF containing:
    - Collars (as circles with labels)
    - Drillhole traces (as lines)
    - Grade-colored assay intervals along each trace
    - Vein solid wireframe intersection profiles (as shaded polygons)
    - Coordinate grid system, grade-range legend, and section metadata.

    When `plane_params` is given (type/offset/thickness/azimuth), only the
    collars/traces/assays that intersect that slicing plane are plotted,
    matching the section currently visible in the frontend's 2D Vertical
    Cross-Section panel (FR-006). When omitted, falls back to a
    full-project projection (legacy behavior, e.g. for projects with no
    active slice), and assay intervals are plotted unsliced.
    """
    assay_segments = assay_segments or []
    sliced_assays: List[Dict[str, Any]] = []

    # With no active slice, fall back to a full-project EW section: an EW
    # plane through the data with effectively-infinite thickness passes
    # everything, so collars, traces AND assays go through the *same*
    # projection (u=Northing, v=Elevation) and stay in one consistent 2D
    # frame -- rather than each being projected on a different pair of axes.
    if plane_params is None:
        plane_params = {"type": "EW", "offset": 0.0, "thickness": 1.0e12, "azimuth": 0.0}

    sliced = compute_section_plane_view(
        collars, traces,
        plane_params.get("type", "EW"),
        plane_params.get("offset", 0.0),
        plane_params.get("thickness", 20.0),
        plane_params.get("azimuth", 0.0)
    )
    # Re-express as the (u, v) "x, z" pairs the drawing code plots --
    # u maps to the horizontal (section-distance) axis, v (elevation) to the
    # vertical axis.
    collars = [{"hole_id": c["hole_id"], "easting": c["u"], "elevation": c["v"]} for c in sliced["collars_2d"]]
    traces = [
        {"hole_id": tr["hole_id"], "points": [{"x": u, "y": 0.0, "z": v} for u, v in tr["points"]]}
        for tr in sliced["traces_2d"]
    ]
    wireframe_intersects = []  # wireframe 2D slicing is not implemented; omit rather than show unsliced 3D data

    # Reuse the exact same bounding-box center compute_section_plane_view
    # computed for collars/traces, so assay slicing is judged against the
    # identical plane origin (not a separately-derived one).
    sliced_assays = _slice_assay_segments(
        assay_segments,
        plane_params.get("type", "EW"),
        plane_params.get("offset", 0.0),
        plane_params.get("thickness", 20.0),
        plane_params.get("azimuth", 0.0),
        sliced["center"]
    )

    return _render_section_sheet(
        project_name, section_name, collars, traces,
        wireframe_intersects, sliced_assays
    )


def _nice_step(span: float, target_ticks: int = 6) -> float:
    """Rounds a raw axis interval up to a 1/2/5 x 10^n 'nice' number so grid
    labels land on readable round values."""
    if span <= 0:
        return 1.0
    raw = span / max(target_ticks, 1)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def _render_section_sheet(
    project_name: str,
    section_name: str,
    collars: List[Dict[str, Any]],
    traces: List[Dict[str, Any]],
    wireframe_intersects: List[Dict[str, Any]],
    sliced_assays: List[Dict[str, Any]],
) -> bytes:
    """Draws a print-ready, white-sheet geological cross-section: undistorted
    (equal H:V) scale with a stated ratio + scale bar, black axes labelled in
    RL (elevation) and section distance, grade-coloured assay intervals over
    the drill traces, a legend, and a drafting title block."""
    from datetime import datetime, timezone

    PAGE_W, PAGE_H = 792, 612  # Letter, landscape
    INK = colors.HexColor("#1f2937")
    SUBTLE = colors.HexColor("#6b7280")
    GRID = colors.HexColor("#e5e7eb")
    TRACE = colors.HexColor("#9ca3af")

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(PAGE_W, PAGE_H))

    # White sheet + outer drafting border
    c.setFillColor(colors.white)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=True, stroke=False)
    c.setStrokeColor(INK)
    c.setLineWidth(1.2)
    c.rect(20, 20, PAGE_W - 40, PAGE_H - 40, fill=False, stroke=True)

    # --- Title strip ---------------------------------------------------
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(34, PAGE_H - 44, f"{project_name}")
    c.setFont("Helvetica", 10)
    c.setFillColor(SUBTLE)
    c.drawString(34, PAGE_H - 58, "Geological Cross-Section")
    c.setFont("Helvetica-Oblique", 9)
    c.drawRightString(PAGE_W - 34, PAGE_H - 44, section_name)
    c.setStrokeColor(INK)
    c.setLineWidth(0.6)
    c.line(34, PAGE_H - 66, PAGE_W - 34, PAGE_H - 66)

    # --- Plot area geometry -------------------------------------------
    plot_x, plot_y, plot_w, plot_h = 62, 92, 500, 424

    # Data bounds
    all_x, all_z = [], []

    def _xz(pt):
        return (pt.get("x", 0.0), pt.get("z", 0.0)) if isinstance(pt, dict) else (pt[0], pt[2])

    for col in collars:
        all_x.append(col.get("easting", 0.0)); all_z.append(col.get("elevation", 0.0))
    for tr in traces:
        for pt in tr.get("points", []):
            x, z = _xz(pt); all_x.append(x); all_z.append(z)
    for seg in sliced_assays:
        all_x += [seg["start"][0], seg["end"][0]]
        all_z += [seg["start"][1], seg["end"][1]]

    min_x = min(all_x) if all_x else 0.0
    max_x = max(all_x) if all_x else 1000.0
    min_z = min(all_z) if all_z else 0.0
    max_z = max(all_z) if all_z else 1000.0
    range_x = max(max_x - min_x, 1.0)
    range_z = max(max_z - min_z, 1.0)
    pad = 0.08
    min_x -= range_x * pad; max_x += range_x * pad
    min_z -= range_z * pad; max_z += range_z * pad
    range_x = max_x - min_x
    range_z = max_z - min_z

    # Equal (undistorted) scale: one metres-per-point figure for both axes,
    # data centred in the frame -- geology is never stretched.
    sc = max(range_x / plot_w, range_z / plot_h)  # metres per point
    draw_w = range_x / sc
    draw_h = range_z / sc
    off_x = plot_x + (plot_w - draw_w) / 2.0
    off_y = plot_y + (plot_h - draw_h) / 2.0

    def to_pt(x, z):
        return (off_x + (x - min_x) / sc, off_y + (z - min_z) / sc)

    # Clip subsequent drawing to the plot frame
    c.saveState()
    p = c.beginPath()
    p.rect(plot_x, plot_y, plot_w, plot_h)
    c.clipPath(p, stroke=0, fill=0)

    # Grid at nice round intervals
    step_x = _nice_step(range_x)
    step_z = _nice_step(range_z)
    c.setStrokeColor(GRID)
    c.setLineWidth(0.5)
    gx = math.ceil(min_x / step_x) * step_x
    xticks = []
    while gx <= max_x:
        px, _ = to_pt(gx, min_z)
        c.line(px, plot_y, px, plot_y + plot_h)
        xticks.append((px, gx))
        gx += step_x
    gz = math.ceil(min_z / step_z) * step_z
    zticks = []
    while gz <= max_z:
        _, pz = to_pt(min_x, gz)
        c.line(plot_x, pz, plot_x + plot_w, pz)
        zticks.append((pz, gz))
        gz += step_z
    c.restoreState()

    # Plot frame
    c.setStrokeColor(INK)
    c.setLineWidth(1.0)
    c.rect(plot_x, plot_y, plot_w, plot_h, fill=False, stroke=True)

    # Axis tick labels
    c.setFont("Helvetica", 7.5)
    c.setFillColor(SUBTLE)
    for px, val in xticks:
        if plot_x - 2 <= px <= plot_x + plot_w + 2:
            c.drawCentredString(px, plot_y - 12, f"{val:,.0f}")
    for pz, val in zticks:
        if plot_y - 2 <= pz <= plot_y + plot_h + 2:
            c.drawRightString(plot_x - 6, pz - 2.5, f"{val:,.0f}")
    # Axis titles
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(INK)
    c.drawCentredString(plot_x + plot_w / 2, plot_y - 24, "Section distance (m)")
    c.saveState()
    c.translate(plot_x - 34, plot_y + plot_h / 2)
    c.rotate(90)
    c.drawCentredString(0, 0, "Elevation RL (m)")
    c.restoreState()

    # --- Geometry (clipped) -------------------------------------------
    c.saveState()
    p = c.beginPath()
    p.rect(plot_x, plot_y, plot_w, plot_h)
    c.clipPath(p, stroke=0, fill=0)

    # Vein-solid intersection profiles
    for wf in wireframe_intersects:
        pts = wf.get("points", [])
        if len(pts) >= 3:
            c.setStrokeColor(colors.HexColor("#be185d"))
            c.setFillColor(colors.Color(0.85, 0.10, 0.39, alpha=0.18))
            c.setLineWidth(1.0)
            path = c.beginPath()
            x0, z0 = _xz(pts[0]); px, pz = to_pt(x0, z0); path.moveTo(px, pz)
            for pt in pts[1:]:
                x, z = _xz(pt); px, pz = to_pt(x, z); path.lineTo(px, pz)
            path.close()
            c.drawPath(path, fill=True, stroke=True)

    # Drill traces (thin grey spine under the assay intervals)
    c.setStrokeColor(TRACE)
    c.setLineWidth(1.0)
    for tr in traces:
        pts = tr.get("points", [])
        if len(pts) >= 2:
            x0, z0 = _xz(pts[0]); px, pz = to_pt(x0, z0)
            for pt in pts[1:]:
                x, z = _xz(pt); nx, nz = to_pt(x, z)
                c.line(px, pz, nx, nz); px, pz = nx, nz

    # Grade-coloured assay intervals
    c.setLineWidth(3.4)
    c.setLineCap(1)
    for seg in sliced_assays:
        px, pz = to_pt(*seg["start"])
        nx, nz = to_pt(*seg["end"])
        c.setStrokeColor(colors.HexColor(seg["color"]))
        c.line(px, pz, nx, nz)
    c.restoreState()

    # Collars: open triangle at the top of each hole with an ID label
    c.setLineCap(0)
    for col in collars:
        px, pz = to_pt(col.get("easting", 0.0), col.get("elevation", 0.0))
        c.setFillColor(colors.white)
        c.setStrokeColor(INK)
        c.setLineWidth(0.9)
        tri = c.beginPath()
        tri.moveTo(px, pz + 5); tri.lineTo(px - 4, pz - 3); tri.lineTo(px + 4, pz - 3); tri.close()
        c.drawPath(tri, fill=True, stroke=True)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(px, pz + 9, col.get("hole_id", "DH"))

    # --- Scale bar -----------------------------------------------------
    bar_m = _nice_step(range_x, 4)
    bar_pts = bar_m / sc
    bx, by = plot_x, plot_y - 44
    c.setStrokeColor(INK); c.setFillColor(INK); c.setLineWidth(1.0)
    c.line(bx, by, bx + bar_pts, by)
    c.line(bx, by - 3, bx, by + 3)
    c.line(bx + bar_pts, by - 3, bx + bar_pts, by + 3)
    c.line(bx + bar_pts / 2, by - 2, bx + bar_pts / 2, by + 2)
    c.setFont("Helvetica", 7)
    c.drawString(bx, by - 11, "0")
    c.drawCentredString(bx + bar_pts, by - 11, f"{bar_m:,.0f} m")
    # Scale ratio (1 pt = 0.352778 mm on paper)
    denom = int(round(sc / 0.000352778))
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(bx + bar_pts + 16, by - 3, f"Scale  1:{denom:,}   (1:1 H:V, no vertical exaggeration)")

    # --- Legend + title block panel -----------------------------------
    lx, ly, lw, lh = 592, 92, 170, 424
    c.setFillColor(colors.HexColor("#f9fafb"))
    c.setStrokeColor(INK); c.setLineWidth(0.8)
    c.rect(lx, ly, lw, lh, fill=True, stroke=True)

    cur = ly + lh - 18
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 10)
    c.drawString(lx + 12, cur, "LEGEND")
    cur -= 20

    c.setFont("Helvetica", 8); c.setFillColor(INK)
    # Collar
    c.setFillColor(colors.white); c.setStrokeColor(INK); c.setLineWidth(0.9)
    tri = c.beginPath()
    tri.moveTo(lx + 20, cur + 5); tri.lineTo(lx + 16, cur - 3); tri.lineTo(lx + 24, cur - 3); tri.close()
    c.drawPath(tri, fill=True, stroke=True)
    c.setFillColor(INK); c.drawString(lx + 34, cur - 1, "Drill collar")
    cur -= 18
    # Trace
    c.setStrokeColor(TRACE); c.setLineWidth(1.2)
    c.line(lx + 14, cur + 1, lx + 26, cur + 1)
    c.setFillColor(INK); c.drawString(lx + 34, cur - 1, "Drillhole trace")
    cur -= 18
    # Vein
    c.setStrokeColor(colors.HexColor("#be185d")); c.setFillColor(colors.Color(0.85, 0.10, 0.39, alpha=0.25))
    c.setLineWidth(0.9); c.rect(lx + 14, cur - 3, 12, 9, fill=True, stroke=True)
    c.setFillColor(INK); c.drawString(lx + 34, cur - 1, "Vein solid intersect")
    cur -= 24

    # Au grade scale
    c.setFont("Helvetica-Bold", 8.5); c.setFillColor(INK)
    c.drawString(lx + 12, cur, "Au GRADE (g/t)")
    cur -= 16
    c.setFont("Helvetica", 8)
    for upper, color, label in reversed(GRADE_BUCKETS):
        c.setFillColor(colors.HexColor(color))
        c.setStrokeColor(colors.HexColor("#d1d5db")); c.setLineWidth(0.4)
        c.rect(lx + 14, cur - 3, 14, 9, fill=True, stroke=True)
        c.setFillColor(INK)
        c.drawString(lx + 34, cur - 1, f"{label}")
        cur -= 15

    # Title block (drafting-style, bottom of panel)
    tb_y = ly + 96
    c.setStrokeColor(INK); c.setLineWidth(0.6)
    c.line(lx, tb_y, lx + lw, tb_y)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = [
        ("Section", section_name if len(section_name) <= 26 else section_name[:24] + "…"),
        ("Collars", str(len(collars))),
        ("Assay intervals", str(len(sliced_assays))),
        ("Vein profiles", str(len(wireframe_intersects))),
        ("Date (UTC)", now),
        ("Sheet", "Letter / Landscape"),
    ]
    ry = tb_y - 14
    for k, v in rows:
        c.setFont("Helvetica", 7); c.setFillColor(SUBTLE)
        c.drawString(lx + 12, ry, k)
        c.setFont("Helvetica-Bold", 7.5); c.setFillColor(INK)
        c.drawRightString(lx + lw - 12, ry, v)
        ry -= 13

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()

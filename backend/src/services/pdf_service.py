import io
import math
from typing import List, Dict, Any, Optional, Tuple
from reportlab.pdfgen import canvas
from reportlab.lib import colors


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

    return {"collars_2d": sliced_collars, "traces_2d": sliced_traces}


def export_section_to_pdf(
    project_name: str,
    section_name: str,
    collars: List[Dict[str, Any]],
    traces: List[Dict[str, Any]],
    wireframe_intersects: List[Dict[str, Any]],
    plane_params: Optional[Dict[str, Any]] = None
) -> bytes:
    """
    Generates a scaled 2D cross-section PDF containing:
    - Collars (as circles with labels)
    - Drillhole traces (as lines)
    - Vein solid wireframe intersection profiles (as shaded polygons)
    - Coordinate grid system & legend.

    When `plane_params` is given (type/offset/thickness/azimuth), only the
    collars/traces that intersect that slicing plane are plotted, matching the
    section currently visible in the frontend's 2D Vertical Cross-Section
    panel (FR-006). When omitted, falls back to a full-project projection
    (legacy behavior, e.g. for projects with no active slice).
    """
    if plane_params is not None:
        sliced = compute_section_plane_view(
            collars, traces,
            plane_params.get("type", "EW"),
            plane_params.get("offset", 0.0),
            plane_params.get("thickness", 20.0),
            plane_params.get("azimuth", 0.0)
        )
        # Re-express as the (u, v) "x, z" pairs the rest of this function
        # already knows how to plot -- u maps to the horizontal axis (x),
        # v (elevation) maps to the vertical axis (z).
        collars = [{"hole_id": c["hole_id"], "easting": c["u"], "elevation": c["v"]} for c in sliced["collars_2d"]]
        traces = [
            {"hole_id": tr["hole_id"], "points": [{"x": u, "y": 0.0, "z": v} for u, v in tr["points"]]}
            for tr in sliced["traces_2d"]
        ]
        wireframe_intersects = []  # wireframe 2D slicing is not implemented; omit rather than show unsliced 3D data

    buffer = io.BytesIO()
    # Landscape Letter size: 792 x 612 points
    c = canvas.Canvas(buffer, pagesize=(792, 612))
    
    # 1. Sleek Techy Dark Background
    c.setFillColor(colors.HexColor("#0f172a"))
    c.rect(0, 0, 792, 612, fill=True, stroke=False)
    
    # 2. Header Banner
    c.setFillColor(colors.HexColor("#1e293b"))
    c.rect(0, 530, 792, 82, fill=True, stroke=False)
    
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(36, 575, f"{project_name} - Geological Cross Section")
    
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#94a3b8"))
    c.drawString(36, 550, f"Section: {section_name}")
    
    # 3. Main Plot Frame
    plot_x, plot_y, plot_w, plot_h = 50, 50, 520, 450
    c.setStrokeColor(colors.HexColor("#334155"))
    c.setLineWidth(1.5)
    c.setFillColor(colors.HexColor("#020617"))
    c.rect(plot_x, plot_y, plot_w, plot_h, fill=True, stroke=True)
    
    # Find bounding box for scaling
    all_x = []
    all_z = []
    for col in collars:
        all_x.append(col.get("easting", 0.0))
        all_z.append(col.get("elevation", 0.0))
    for tr in traces:
        for pt in tr.get("points", []):
            if isinstance(pt, dict):
                all_x.append(pt.get("x", 0.0))
                all_z.append(pt.get("z", 0.0))
            else:
                all_x.append(pt[0])
                all_z.append(pt[2])
    for wf in wireframe_intersects:
        for pt in wf.get("points", []):
            if isinstance(pt, dict):
                all_x.append(pt.get("x", 0.0))
                all_z.append(pt.get("z", 0.0))
            else:
                all_x.append(pt[0])
                all_z.append(pt[2])
            
    min_x = min(all_x) if all_x else 0.0
    max_x = max(all_x) if all_x else 1000.0
    min_z = min(all_z) if all_z else 0.0
    max_z = max(all_z) if all_z else 1000.0
    
    # Add 10% padding
    range_x = max(max_x - min_x, 1.0)
    range_z = max(max_z - min_z, 1.0)
    min_x -= range_x * 0.1
    max_x += range_x * 0.1
    min_z -= range_z * 0.1
    max_z += range_z * 0.1
    range_x = max_x - min_x
    range_z = max_z - min_z
    
    def to_plot_coords(x: float, z: float) -> tuple:
        px = plot_x + ((x - min_x) / range_x) * plot_w
        pz = plot_y + ((z - min_z) / range_z) * plot_h
        return px, pz

    # Draw coordinate grid lines & labels
    c.setStrokeColor(colors.HexColor("#1e293b"))
    c.setLineWidth(0.5)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#64748b"))
    
    # X Grid Lines (Easting)
    for i in range(1, 6):
        gx = plot_x + (plot_w / 6) * i
        c.line(gx, plot_y, gx, plot_y + plot_h)
        val_x = min_x + (range_x / 6) * i
        c.drawString(gx - 15, plot_y - 12, f"{val_x:.0f}mE")
        
    # Z Grid Lines (Elevation)
    for i in range(1, 6):
        gy = plot_y + (plot_h / 6) * i
        c.line(plot_x, gy, plot_x + plot_w, gy)
        val_z = min_z + (range_z / 6) * i
        c.drawString(plot_x - 45, gy - 3, f"{val_z:.0f}m")

    # 4. Draw Wireframe Intersects (Polygons)
    for wf in wireframe_intersects:
        c.setStrokeColor(colors.HexColor("#ec4899"))
        c.setFillColor(colors.HexColor("#db2777"))
        c.setLineWidth(1.5)
        pts = wf.get("points", [])
        if len(pts) >= 3:
            path = c.beginPath()
            first_pt = pts[0]
            if isinstance(first_pt, dict):
                px, pz = to_plot_coords(first_pt.get("x", 0.0), first_pt.get("z", 0.0))
                path.moveTo(px, pz)
                for pt in pts[1:]:
                    px, pz = to_plot_coords(pt.get("x", 0.0), pt.get("z", 0.0))
                    path.lineTo(px, pz)
            else:
                px, pz = to_plot_coords(first_pt[0], first_pt[2])
                path.moveTo(px, pz)
                for pt in pts[1:]:
                    px, pz = to_plot_coords(pt[0], pt[2])
                    path.lineTo(px, pz)
            path.close()
            c.drawPath(path, fill=True, stroke=True)

    # 5. Draw Drillhole Traces (Lines)
    c.setStrokeColor(colors.HexColor("#10b981"))
    c.setLineWidth(2.0)
    for tr in traces:
        pts = tr.get("points", [])
        if len(pts) >= 2:
            first_pt = pts[0]
            if isinstance(first_pt, dict):
                px, pz = to_plot_coords(first_pt.get("x", 0.0), first_pt.get("z", 0.0))
                for pt in pts[1:]:
                    nx, nz = to_plot_coords(pt.get("x", 0.0), pt.get("z", 0.0))
                    c.line(px, pz, nx, nz)
                    px, pz = nx, nz
            else:
                px, pz = to_plot_coords(first_pt[0], first_pt[2])
                for pt in pts[1:]:
                    nx, nz = to_plot_coords(pt[0], pt[2])
                    c.line(px, pz, nx, nz)
                    px, pz = nx, nz
                
    # 6. Draw Collars (Blue Circles)
    c.setStrokeColor(colors.white)
    c.setFillColor(colors.HexColor("#3b82f6"))
    c.setLineWidth(1.0)
    for col in collars:
        px, pz = to_plot_coords(col.get("easting", 0.0), col.get("elevation", 0.0))
        c.circle(px, pz, 4, fill=True, stroke=True)
        # Label
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.white)
        c.drawString(px + 6, pz + 4, col.get("hole_id", "DH"))

    # 7. Draw Legend Box
    legend_x, legend_y, legend_w, legend_h = 590, 50, 172, 450
    c.setFillColor(colors.HexColor("#1e293b"))
    c.rect(legend_x, legend_y, legend_w, legend_h, fill=True, stroke=False)
    
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(legend_x + 12, legend_y + legend_h - 24, "LEGEND")
    
    # Collar Legend Item
    c.setFillColor(colors.HexColor("#3b82f6"))
    c.circle(legend_x + 24, legend_y + legend_h - 58, 4, fill=True, stroke=True)
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 9)
    c.drawString(legend_x + 40, legend_y + legend_h - 61, "Collar Location")
    
    # Drillhole Trace Legend Item
    c.setStrokeColor(colors.HexColor("#10b981"))
    c.setLineWidth(2.5)
    c.line(legend_x + 16, legend_y + legend_h - 96, legend_x + 32, legend_y + legend_h - 96)
    c.setFillColor(colors.white)
    c.drawString(legend_x + 40, legend_y + legend_h - 99, "Drillhole Trace")
    
    # Vein Solid Intersect Legend Item
    c.setFillColor(colors.HexColor("#db2777"))
    c.setStrokeColor(colors.HexColor("#ec4899"))
    c.setLineWidth(1.0)
    c.rect(legend_x + 16, legend_y + legend_h - 138, 16, 12, fill=True, stroke=True)
    c.setFillColor(colors.white)
    c.drawString(legend_x + 40, legend_y + legend_h - 136, "Vein Solid Intersect")
    
    # Metadata info
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#94a3b8"))
    c.drawString(legend_x + 12, legend_y + 80, "PROJECT METADATA")
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#cbd5e1"))
    c.drawString(legend_x + 12, legend_y + 60, f"Collars Plotted: {len(collars)}")
    c.drawString(legend_x + 12, legend_y + 45, f"Vein Profiles: {len(wireframe_intersects)}")
    c.drawString(legend_x + 12, legend_y + 30, f"Format: Letter Landscape")
    
    c.showPage()
    c.save()
    
    buffer.seek(0)
    return buffer.getvalue()

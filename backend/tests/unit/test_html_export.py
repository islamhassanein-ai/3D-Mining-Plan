"""
T020 — Topography decimation tests
T021 — OBJ parser tests
T022 — HTML assembly / escaping / budget tests
T023 — Static-bundle purity test
"""
import json
import os
import re
import pytest

from backend.src.services.html_export import (
    build_standalone_html,
    encode_payload,
    ExportTooLargeError,
    MAX_EXPORT_BYTES,
    MAX_TOPO_POINTS,
    parse_topography_csv,
    decimate_topography,
)
from backend.src.services.obj_geometry import parse_obj


# ── T020 — Topography decimation ─────────────────────────────────────────

class TestDecimation:
    def _grid(self, cols, rows, origin=(0, 0), step=10):
        """Generate a regular grid of (e, n, el) points."""
        oe, on_ = origin
        return [[oe + c * step, on_ + r * step, 100.0]
                for r in range(rows) for c in range(cols)]

    def test_below_cap_unchanged(self):
        pts = self._grid(10, 10)  # 100 points
        assert len(pts) <= MAX_TOPO_POINTS
        result = decimate_topography(pts, max_points=MAX_TOPO_POINTS)
        assert len(result) == len(pts)
        assert result == pts

    def test_below_explicit_cap_unchanged(self):
        pts = self._grid(5, 5)  # 25 points
        result = decimate_topography(pts, max_points=50)
        assert result == pts

    def test_above_cap_respects_limit(self):
        pts = self._grid(200, 200)  # 40 000 points
        result = decimate_topography(pts, max_points=500)
        # Grid-bin targets ≈ max_points; allow a small overshoot from boundary cells
        assert len(result) < len(pts)
        assert len(result) <= int(500 * 1.15)

    def test_deterministic(self):
        pts = self._grid(100, 100)  # 10 000 points
        r1 = decimate_topography(pts, max_points=100)
        r2 = decimate_topography(pts, max_points=100)
        assert r1 == r2

    def test_bounding_box_preserved(self):
        pts = self._grid(100, 100, step=5)
        result = decimate_topography(pts, max_points=100)
        # At least one point near each corner
        min_e = min(p[0] for p in result)
        max_e = max(p[0] for p in result)
        min_n = min(p[1] for p in result)
        max_n = max(p[1] for p in result)
        cell = 5 * 100 / 10  # approx one cell width
        assert min_e <= cell
        assert max_e >= 5 * 99 - cell
        assert min_n <= cell
        assert max_n >= 5 * 99 - cell

    def test_identical_points_no_error(self):
        pts = [[350000.0, 2800000.0, 100.0]] * 1000
        result = decimate_topography(pts, max_points=10)
        assert len(result) >= 1

    def test_collinear_points_no_error(self):
        pts = [[float(i), 2800000.0, 100.0] for i in range(1000)]
        result = decimate_topography(pts, max_points=10)
        assert len(result) >= 1

    def test_single_point_no_error(self):
        pts = [[350000.0, 2800000.0, 100.0]]
        result = decimate_topography(pts, max_points=10)
        assert result == pts

    def test_csv_east_north_z_headers(self):
        csv = "easting,northing,z\n350000,2800000,100\n350010,2800010,101\n"
        pts = parse_topography_csv(csv)
        assert len(pts) == 2
        assert pts[0] == [350000.0, 2800000.0, 100.0]

    def test_csv_elevation_alias(self):
        csv = "East,North,Elevation\n1,2,3\n"
        pts = parse_topography_csv(csv)
        assert len(pts) == 1

    def test_csv_alt_alias(self):
        csv = "easting,northing,altitude\n1,2,3\n"
        pts = parse_topography_csv(csv)
        assert len(pts) == 1

    def test_csv_skips_non_numeric(self):
        csv = "easting,northing,z\nno,data,here\n1,2,3\n"
        pts = parse_topography_csv(csv)
        assert len(pts) == 1

    def test_csv_crlf_line_endings(self):
        csv = "easting,northing,z\r\n1,2,3\r\n4,5,6\r\n"
        pts = parse_topography_csv(csv)
        assert len(pts) == 2

    def test_csv_trailing_blank_line(self):
        csv = "easting,northing,z\n1,2,3\n\n"
        pts = parse_topography_csv(csv)
        assert len(pts) == 1

    def test_csv_missing_z_column(self):
        csv = "easting,northing\n1,2\n"
        pts = parse_topography_csv(csv)
        assert pts == []

    def test_csv_zone_column_not_matched_as_z(self):
        # 'zone' contains 'z' as a substring but is not an exact match — must not match
        csv = "easting,northing,zone,z\n1,2,36,100\n"
        pts = parse_topography_csv(csv)
        assert len(pts) == 1
        assert pts[0][2] == 100.0  # the 'z' column, not 'zone'


# ── T021 — OBJ parser ────────────────────────────────────────────────────

class TestObjGeometry:
    def test_triangle(self):
        obj = "v 1 2 3\nv 4 5 6\nv 7 8 9\nf 1 2 3\n"
        r = parse_obj(obj)
        assert r["vertices"] == [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        assert r["faces"] == [[0, 1, 2]]

    def test_quad_becomes_two_triangles(self):
        obj = "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 4\n"
        r = parse_obj(obj)
        assert len(r["faces"]) == 2
        assert r["faces"][0] == [0, 1, 2]
        assert r["faces"][1] == [0, 2, 3]

    def test_comments_and_blanks_ignored(self):
        obj = "# a comment\n\nv 1 2 3\n# another\nv 4 5 6\nv 7 8 9\nf 1 2 3\n"
        r = parse_obj(obj)
        assert len(r["vertices"]) == 3
        assert len(r["faces"]) == 1

    def test_slash_index_forms(self):
        obj = "v 1 0 0\nv 0 1 0\nv 0 0 1\nf 1/1/1 2/2/2 3/3/3\n"
        r = parse_obj(obj)
        assert r["faces"] == [[0, 1, 2]]

    def test_malformed_gives_empty(self):
        r = parse_obj("this is not obj data at all")
        assert r == {"vertices": [], "faces": []}

    def test_vertex_order_is_raw_utm(self):
        # Vertices must be stored as (easting, northing, elevation) — no Y-up swap
        obj = "v 350000 2800000 100\nv 350100 2800000 100\nv 350050 2800050 150\nf 1 2 3\n"
        r = parse_obj(obj)
        assert r["vertices"][0] == [350000.0, 2800000.0, 100.0]
        assert r["vertices"][1] == [350100.0, 2800000.0, 100.0]


# ── Helpers shared by T022 / T023 ────────────────────────────────────────

def _minimal_payload(name="Test Project"):
    return {
        "format_version": 1,
        "project": {"name": name, "utm_zone": "36N"},
        "scene": {"drillholes": [], "trenches": [], "wireframes": [],
                  "structural_readings": [], "topography_ref": None},
        "collar_details": {},
        "topography": {"included": False, "point_count": 0, "points": []},
        "wireframes": [],
        "export_meta": {"exported_at": "2024-01-01T00:00:00Z",
                        "exported_by": "test@example.com", "notices": []},
    }


def _assemble(payload=None, bundle="// bundle", css="/* css */", shell="<div id='app'></div>"):
    if payload is None:
        payload = _minimal_payload()
    return build_standalone_html(payload, shell, css, bundle)


# ── T022 — Assembly / escaping / budget tests ────────────────────────────

class TestAssembly:
    def test_self_containment_no_external_src(self):
        doc = _assemble().decode()
        assert 'src="http' not in doc
        assert 'href="http' not in doc
        assert '@import' not in doc
        assert '//fonts.' not in doc
        assert 'url(http' not in doc

    def test_no_credentials_in_document(self):
        doc = _assemble().decode()
        assert 'mining_session_token' not in doc
        assert 'localStorage' not in doc
        assert 'Bearer' not in doc
        assert '/auth/' not in doc

    def test_xss_project_name_escaped(self):
        payload = _minimal_payload(name='</script><img src=x onerror=alert(1)>')
        doc = _assemble(payload).decode()
        # The raw </script> tag must not appear unescaped in the document
        assert '</script><img' not in doc
        # The JSON island must be parseable and round-trip the name intact
        match = re.search(
            r'<script type="application/json" id="monark-scene-data">(.*?)</script>',
            doc, re.DOTALL
        )
        assert match, "JSON island not found"
        recovered = json.loads(match.group(1))
        assert recovered["project"]["name"] == '</script><img src=x onerror=alert(1)>'

    def test_hole_id_xss_roundtrip(self):
        payload = _minimal_payload()
        payload["collar_details"]['"><script>'] = {"hole_id": '"><script>'}
        doc = _assemble(payload).decode()
        match = re.search(
            r'<script type="application/json" id="monark-scene-data">(.*?)</script>',
            doc, re.DOTALL
        )
        assert match
        recovered = json.loads(match.group(1))
        assert '"><script>' in recovered["collar_details"]

    def test_sentinel_injection_project_name(self):
        """A project named <!--MONARK_BUNDLE--> must not cause double-substitution."""
        payload = _minimal_payload(name="<!--MONARK_BUNDLE-->")
        bundle = "// real bundle code"
        doc = _assemble(payload, bundle=bundle).decode()
        # The bundle appears exactly once
        assert doc.count("// real bundle code") == 1

    def test_sentinel_injection_css(self):
        payload = _minimal_payload(name="<!--MONARK_DATA-->")
        doc = _assemble(payload).decode()
        # The data sentinel must not appear literally in the finished doc
        assert "<!--MONARK_DATA-->" not in doc

    def test_budget_raises_too_large(self):
        # Pass an oversized bundle_js to push the assembled document over MAX_EXPORT_BYTES.
        # This is faster than generating millions of topography points and directly tests
        # the size-check code path.
        big_bundle = "x" * (MAX_EXPORT_BYTES + 1)
        with pytest.raises(ExportTooLargeError):
            build_standalone_html(_minimal_payload(), "<div></div>", "/* css */", big_bundle)

    def test_budget_413_returns_no_partial_content(self):
        big_bundle = "x" * (MAX_EXPORT_BYTES + 1)
        try:
            build_standalone_html(_minimal_payload(), "<div></div>", "/* css */", big_bundle)
            pytest.fail("ExportTooLargeError not raised")
        except ExportTooLargeError as exc:
            assert exc.size > MAX_EXPORT_BYTES
            assert exc.largest_contributor  # non-empty description

    def test_payload_validity_format_version(self):
        doc = _assemble().decode()
        match = re.search(
            r'<script type="application/json" id="monark-scene-data">(.*?)</script>',
            doc, re.DOTALL
        )
        assert match
        data = json.loads(match.group(1))
        assert data.get("format_version") == 1
        for key in ("project", "scene", "collar_details", "topography",
                    "wireframes", "export_meta"):
            assert key in data, f"missing top-level key: {key}"

    def test_five_char_escapes(self):
        payload = _minimal_payload(name="A")
        payload["collar_details"] = {
            "key": {"lt": "<", "gt": ">", "amp": "&",
                    "ls": " ", "ps": " "}
        }
        doc = _assemble(payload).decode()
        # None of the raw chars should appear inside the JSON island
        match = re.search(
            r'<script type="application/json" id="monark-scene-data">(.*?)</script>',
            doc, re.DOTALL
        )
        island = match.group(1)
        assert '<' not in island
        assert '>' not in island
        assert '&' not in island
        assert ' ' not in island
        assert ' ' not in island

    def test_html_structure(self):
        doc = _assemble().decode()
        assert doc.startswith("<!DOCTYPE html>")
        assert "<html" in doc
        assert "<title>" in doc
        assert "Content-Security-Policy" in doc

    def test_opens_in_the_dark_theme(self):
        """The document must carry a theme before any script runs.

        The viewer can switch themes, but it cannot do so until the bundle
        parses -- and a document with no data-theme paints unstyled first.
        Serving the attribute in the markup is what avoids that flash.
        """
        doc = _assemble().decode()
        assert '<html lang="en" data-theme="dark">' in doc


# ── T023 — Static-bundle purity test ─────────────────────────────────────

BUNDLE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)
    )))),
    "frontend", "dist", "export_viewer.js"
)

@pytest.mark.skipif(
    not os.path.exists(BUNDLE_PATH),
    reason="export_viewer.js not built; run 'npm run build:export' in frontend/"
)
class TestBundlePurity:
    @pytest.fixture(autouse=True)
    def load_bundle(self):
        with open(BUNDLE_PATH, "r", encoding="utf-8") as fh:
            self.bundle = fh.read()

    def test_no_session_token(self):
        assert "mining_session_token" not in self.bundle

    def test_no_localstorage(self):
        assert "localStorage" not in self.bundle

    def test_no_auth_magic_link(self):
        assert "/auth/magic-link" not in self.bundle

    def test_no_workspace_projects(self):
        assert "/workspace/projects" not in self.bundle

    def test_no_share_links(self):
        assert "share-links" not in self.bundle

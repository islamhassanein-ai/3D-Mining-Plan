"""
HTML assembly service for standalone export bundles.

DB-free and dependency-free so it is unit-testable without a running
database (T022).
"""
import base64
import html
import json
import logging
import math
import mimetypes
import os

logger = logging.getLogger(__name__)

MAX_TOPO_POINTS  = 60_000
MAX_EXPORT_BYTES = 60 * 1024 ** 2
SIZE_WARN_BYTES  = 15 * 1024 ** 2

APP_TITLE = "MALLOGRIM GOLD MINE"

# Project logo, relative to the repo's frontend/ directory. Embedded as a
# base64 data URI because the export's CSP allows `img-src data: blob:` only.
LOGO_RELATIVE_PATH = os.path.join("assets", "MGM.jpeg")


def load_logo_data_uri(frontend_dir: str) -> str:
    """base64 data URI for the project logo, or '' when it isn't present.

    An empty string leaves the <img> with an unresolvable src, which trips its
    onerror handler and reveals the inline SVG fallback -- so a missing logo
    file degrades to the generic mark instead of breaking the export.
    """
    path = os.path.join(frontend_dir, LOGO_RELATIVE_PATH)
    if not os.path.isfile(path):
        logger.info('Project logo not found at %s; export uses the fallback mark', path)
        return ''
    try:
        with open(path, 'rb') as fh:
            raw = fh.read()
    except OSError as exc:
        logger.warning('Could not read project logo %s: %s', path, exc)
        return ''

    mime = mimetypes.guess_type(path)[0] or 'image/jpeg'
    return f'data:{mime};base64,' + base64.b64encode(raw).decode('ascii')

# Sentinel-based template per contracts/api.md §3.  Substitution is always
# done in the order listed here; the payload and bundle come last so a
# project name containing a sentinel string cannot inject content.
_HTML_TEMPLATE = (
    '<!DOCTYPE html>\n'
    '<html lang="en">\n'
    '<head>\n'
    '  <meta charset="UTF-8">\n'
    '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    '  <meta http-equiv="Content-Security-Policy"\n'
    '        content="default-src \'none\'; script-src \'unsafe-inline\';'
    ' style-src \'unsafe-inline\';\n'
    '                 img-src data: blob:; connect-src \'none\';'
    ' base-uri \'none\'; form-action \'none\'">\n'
    '  <title><!--MONARK_TITLE--></title>\n'
    '  <style>/*--MONARK_CSS--*/</style>\n'
    '</head>\n'
    '<body>\n'
    '  <!--MONARK_SHELL-->\n'
    '  <script type="application/json" id="monark-scene-data"><!--MONARK_DATA--></script>\n'
    '  <script><!--MONARK_BUNDLE--></script>\n'
    '</body>\n'
    '</html>'
)


class ExportTooLargeError(Exception):
    """Raised when the assembled document exceeds MAX_EXPORT_BYTES."""

    def __init__(self, size: int, largest_contributor: str):
        self.size = size
        self.largest_contributor = largest_contributor
        super().__init__(
            f"Export is {size / 1024**2:.1f} MB, above the "
            f"{MAX_EXPORT_BYTES / 1024**2:.0f} MB limit. "
            f"Largest contributor: {largest_contributor}. "
            f"Retry with include_topography=false, or re-upload a coarser topography survey."
        )


def parse_topography_csv(text: str) -> list:
    """Parse topography CSV text into [[easting, northing, elevation], ...].

    Header matching mirrors topography.js (post D2 fix): case-insensitive
    substring 'east'/'north'/'elev'/'alt', plus exact match 'z' for elevation.
    Returns [] for missing headers or fully invalid input.
    """
    lines = text.splitlines()
    if len(lines) < 2:
        return []

    headers = [h.strip().lower() for h in lines[0].split(',')]

    e_idx  = next((i for i, h in enumerate(headers) if 'east'  in h), -1)
    n_idx  = next((i for i, h in enumerate(headers) if 'north' in h), -1)
    el_idx = next((i for i, h in enumerate(headers)
                   if 'elev' in h or h == 'z' or 'alt' in h), -1)

    if e_idx == -1 or n_idx == -1 or el_idx == -1:
        return []

    max_col = max(e_idx, n_idx, el_idx)
    points = []
    for line in lines[1:]:
        cols = line.strip().split(',')
        if len(cols) <= max_col:
            continue
        try:
            points.append([float(cols[e_idx]), float(cols[n_idx]), float(cols[el_idx])])
        except ValueError:
            continue

    return points


def decimate_topography(points: list, max_points: int = MAX_TOPO_POINTS) -> list:
    """Grid-bin topography to at most max_points samples.

    Cell size is chosen so that the number of grid cells ≈ max_points.
    For each occupied cell, the sample nearest the cell centre is kept.
    Output order is deterministic (sorted by cell key) so the same input
    always produces the same output.  Degenerate extents (all points
    collinear or identical) never cause a division by zero.
    """
    if len(points) <= max_points:
        return list(points)

    min_e = min(p[0] for p in points)
    max_e = max(p[0] for p in points)
    min_n = min(p[1] for p in points)
    max_n = max(p[1] for p in points)

    # Clamp to at least 1 m² so cell_size is never zero
    area = max(max_e - min_e, 1.0) * max(max_n - min_n, 1.0)
    cell_size = math.sqrt(area / max_points)

    cells: dict = {}
    for p in points:
        col = int((p[0] - min_e) / cell_size)
        row = int((p[1] - min_n) / cell_size)
        cx = min_e + (col + 0.5) * cell_size
        cy = min_n + (row + 0.5) * cell_size
        dist2 = (p[0] - cx) ** 2 + (p[1] - cy) ** 2
        key = (col, row)
        if key not in cells or dist2 < cells[key][0]:
            cells[key] = (dist2, p)

    return [v[1] for _, v in sorted(cells.items())]


def encode_payload(payload: dict) -> str:
    """JSON-serialise payload and escape the five characters that can break
    a <script> element or the JS parser.

    All five substitutions are lossless inside JSON string literals.
    """
    text = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    # r'\uXXXX' is a raw-string literal (6 chars), NOT the Unicode codepoint.
    text = text.replace('<',      r'\u003c')
    text = text.replace('>',      r'\u003e')
    text = text.replace('&',      r'\u0026')
    text = text.replace('\u2028', r'\u2028')
    text = text.replace('\u2029', r'\u2029')
    return text


def build_standalone_html(
    payload:    dict,
    shell_html: str,
    css_text:   str,
    bundle_js:  str,
    logo_data_uri: str = '',
) -> bytes:
    """Assemble the standalone HTML document.

    Sentinels are substituted once, in a fixed order (title → css → shell →
    logo → data → bundle).  The data and bundle are last so a project name
    that happens to contain a sentinel string is already in the document as
    HTML-escaped text and cannot be re-matched.  The logo substitution happens
    after the shell is inserted, since the sentinel lives inside the shell.

    Raises ExportTooLargeError if len(result) > MAX_EXPORT_BYTES.
    """
    project_name = payload.get('project', {}).get('name', '')
    title = html.escape(
        f'{APP_TITLE} — {project_name}' if project_name else APP_TITLE,
        quote=True,
    )
    encoded_data = encode_payload(payload)

    doc = _HTML_TEMPLATE
    doc = doc.replace('<!--MONARK_TITLE-->', title,        1)
    doc = doc.replace('/*--MONARK_CSS--*/',  css_text,     1)
    doc = doc.replace('<!--MONARK_SHELL-->', shell_html,   1)
    doc = doc.replace('<!--MONARK_LOGO_SRC-->', logo_data_uri, 1)
    doc = doc.replace('<!--MONARK_DATA-->',  encoded_data, 1)
    doc = doc.replace('<!--MONARK_BUNDLE-->', bundle_js,   1)

    html_bytes = doc.encode('utf-8')
    size = len(html_bytes)

    if size > SIZE_WARN_BYTES:
        logger.warning(
            'Standalone export %.1f MB exceeds warning threshold %.0f MB',
            size / 1024 ** 2, SIZE_WARN_BYTES / 1024 ** 2,
        )

    if size > MAX_EXPORT_BYTES:
        topo_points = payload.get('topography', {}).get('point_count', 0)
        topo_bytes  = len(json.dumps(
            payload.get('topography', {}), separators=(',', ':')
        ).encode())
        bundle_bytes = len(bundle_js.encode())
        collar_bytes = len(json.dumps(
            payload.get('collar_details', {}), separators=(',', ':')
        ).encode())

        if topo_bytes >= bundle_bytes and topo_bytes >= collar_bytes:
            contributor = f'topography ({topo_points:,} points)'
        elif bundle_bytes >= collar_bytes:
            contributor = 'viewer bundle'
        else:
            contributor = 'collar details'

        raise ExportTooLargeError(size, contributor)

    return html_bytes

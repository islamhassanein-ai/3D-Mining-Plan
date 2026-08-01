# Contracts: Standalone HTML Export

Additive to `specs/004-*/contracts/api.md` and `specs/005-*/contracts/api.md`.

---

## 1. HTTP Endpoint

### `GET /projects/{project_id}/export/standalone.html`

Registered on the existing router in `backend/src/api/export.py`
(`prefix="/projects/{project_id}/export"`).

**Auth**: `Depends(get_current_user)` + `get_owned_project_or_404(project_id, db, current_user)`.
Owner-only. No share-token equivalent in v1.

**Query parameters**

| Name | Type | Default | Meaning |
|---|---|---|---|
| `include_topography` | bool | `true` | Embed the topography surface. `false` yields a smaller file for grade-only reviews. |
| `include_author` | bool | `true` | When `false`, `generator.exported_by` is `null` and no email appears anywhere in the artifact. |

**Responses**

| Status | Body | Condition |
|---|---|---|
| `200` | `text/html` document | Success |
| `404` | `{"detail": "Project not found"}` | Unknown project, or requester is not the owner (existing guard's behaviour — non-owners must not be able to distinguish the two) |
| `413` | `{"detail": "Export is <N> MB, above the <M> MB limit. Largest contributor: topography (<K> points). Retry with include_topography=false, or re-upload a coarser topography survey."}` | Assembled document exceeds `MAX_EXPORT_BYTES` |
| `503` | `{"detail": "Standalone viewer bundle not built. Run: npm --prefix frontend run build"}` | `frontend/dist/export_viewer.js` missing or empty |

**Success headers**

```
Content-Type: text/html; charset=utf-8
Content-Disposition: attachment; filename="Monark_Gold_Prospect_3D_Viewer_20260728.html";
                     filename*=UTF-8''Monark%20Gold%20Prospect_3D_Viewer_20260728.html
Cache-Control: no-store
```

`filename` is ASCII-sanitised (non-`[A-Za-z0-9._-]` → `_`, runs collapsed);
`filename*` (RFC 5987) carries the true name. Follows the existing pattern in
`export.py:71,128,143,264`, extended for non-ASCII project names.

**Constants** (`backend/src/services/html_export.py`)

```python
MAX_TOPO_POINTS  = 60_000       # ADR-006
MAX_EXPORT_BYTES = 60 * 1024**2 # FR-018
SIZE_WARN_BYTES  = 15 * 1024**2 # NFR-003; logged, not enforced
```

---

## 2. Embedded Payload — `MONARK_EXPORT` v1

Carried in the document as:

```html
<script type="application/json" id="monark-scene-data">{ ...escaped JSON... }</script>
```

`application/json` is inert — the browser will not execute it. Escaping per
`plan.md` §6. Read at boot with
`JSON.parse(document.getElementById('monark-scene-data').textContent)`.

### Top level

```jsonc
{
  "format_version": 1,

  "generator": {
    "app": "Monark 3D Mining Plan",
    "viewer_bundle_built_at": "2026-07-28T09:12:44Z",  // mtime of dist/export_viewer.js (R3)
    "exported_at": "2026-07-28T21:15:03Z",             // UTC, ISO 8601, 'Z'
    "exported_by": "geologist@monark.com"              // null when include_author=false
  },

  "project": {
    "id": "b1f0...-uuid",
    "name": "Monark Gold Prospect",
    "commodity": "Gold",
    "utm_zone": "36N"
  },

  "scene": { /* §2.1 */ },
  "topography": { /* §2.2 */ },
  "collar_details": { /* §2.3 */ },
  "notices": [ /* §2.4 */ ]
}
```

### 2.1 `scene`

**Byte-identical to `GET /projects/{project_id}/scene`** (`scene.py:223–232`) with
two deltas:

- `topography_ref` is **removed** (its content is resolved into `topography`).
- Every `wireframes[]` entry has `file_ref` **removed** and `vertices` + `faces`
  **guaranteed present** (FR-005). Wireframes that cannot be resolved are omitted
  and reported in `notices`.

```jsonc
"scene": {
  "project_id": "b1f0...",
  "name": "Monark Gold Prospect",
  "utm_zone": "36N",

  "drillholes": [{
    "collar_id": "uuid", "hole_id": "ARDD001",
    "easting": 208319.0, "northing": 2467942.0, "elevation": 301.67,
    "trace": [{ "depth": 0.0, "x": 208319.0, "y": 2467942.0, "z": 301.67 }],
    "assays": [{
      "id": "uuid", "from_depth": 0.0, "to_depth": 2.5,
      "grade_value": 10.83, "grade_unit": "ppm",
      "below_detection_limit": false, "qaqc_flag": null,
      "color": "#ff00ff",
      "start_pos": [208319.0, 2467942.0, 301.67],   // [easting, northing, elevation]
      "end_pos":   [208320.1, 2467940.8, 299.5]
    }],
    "lithologies": [{
      "id": "uuid", "from_depth": 0.0, "to_depth": 12.0,
      "lith_code": "QZV", "rqd_percent": 82.0, "core_recovery_percent": 96.0,
      "start_pos": [...], "end_pos": [...]
    }]
  }],

  "trenches": [{ "id": "uuid", "trench_id": "TR-01",
                 "easting": 0.0, "northing": 0.0, "elevation": 0.0,
                 "grade_value": 0.42 }],

  "wireframes": [{ "id": "uuid", "name": "Main_Vein_Solid", "solid_type": "vein",
                   "vertices": [[e, n, z]], "faces": [[i, j, k]] }],

  "structural_readings": [{ "id": "uuid", "reading_type": "bedding",
                            "easting": 0.0, "northing": 0.0, "elevation": 0.0,
                            "dip": 62.0, "strike": 310.0 }]
}
```

> **Axis convention** — unchanged from the live app and load-bearing for correctness.
> Payload/UTM order is `(easting, northing, elevation)`. Three.js is Y-up, so
> renderers map `X = easting, Y = elevation, Z = northing` — see
> `assay_intervals.js:43-44`, `wireframes.js:68`, `topography.js:102`,
> `scene_loader.js:97,102`. The exported viewer reuses those renderers, so it
> inherits the mapping; **no re-mapping may be introduced in the export path.**

### 2.2 `topography`

```jsonc
"topography": {
  "included": true,
  "point_count": 18432,          // points actually embedded
  "source_point_count": 18432,   // points in the source file before decimation
  "decimated": false,
  "points": [[208300.0, 2467900.0, 298.4]]   // [easting, northing, elevation]
}
```

- `included: false` when the project has no topography, or `include_topography=false`;
  `points` is then `[]`.
- Compact triple arrays, not objects — roughly 40 % smaller than
  `{"e":…,"n":…,"el":…}` at this volume. `StaticDataSource.getTopographyPoints()`
  expands them to the `{e, n, el}` shape `topography.js` already consumes.
- Parsing rules match `topography.js:62–85` exactly (case-insensitive header match:
  `east*`, `north*`, `elev*`/`z`/`alt*`; non-numeric rows skipped).

### 2.3 `collar_details`

Map of `collar_id` → the exact body of `GET /collars/{collar_id}`
(`collars.py:98–139`), for every non-superseded collar:

```jsonc
"collar_details": {
  "uuid": {
    "id": "uuid", "hole_id": "ARDD001",
    "easting": 208319.0, "northing": 2467942.0, "elevation": 301.67,
    "utm_zone": "36N",
    "surveys":     [{ "id": "uuid", "depth": 0.0, "dip": -60.0, "azimuth": 135.0 }],
    "assays":      [ /* as collars.py:114-126 */ ],
    "lithologies": [ /* as collars.py:127-137 */ ],
    "merged_intervals": [ /* as collars.py:72-96, sorted by (from_depth, to_depth) */ ]
  }
}
```

`surveys` is what `true_thickness.js` interpolates against — it is required, not
decorative.

### 2.4 `notices`

Machine-readable record of everything degraded during assembly. Rendered in the
footer where `severity: "warning"`.

```jsonc
"notices": [
  { "code": "TOPOGRAPHY_DECIMATED", "severity": "info",
    "message": "Topography reduced from 214,880 to 60,000 points for file size.",
    "detail": { "from": 214880, "to": 60000 } },
  { "code": "WIREFRAME_UNRESOLVED", "severity": "warning",
    "message": "Wireframe 'Fault_A' could not be embedded and is not shown.",
    "detail": { "name": "Fault_A", "reason": "source file missing" } },
  { "code": "TOPOGRAPHY_EXCLUDED", "severity": "info",
    "message": "Topography excluded at export time." }
]
```

Codes: `TOPOGRAPHY_DECIMATED`, `TOPOGRAPHY_EXCLUDED`, `TOPOGRAPHY_UNREADABLE`,
`WIREFRAME_UNRESOLVED`.

---

## 3. Document Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline';
                 img-src data: blob:; connect-src 'none'; base-uri 'none'; form-action 'none'">
  <title><!--MONARK_TITLE--></title>          <!-- HTML-escaped project name -->
  <style>/*--MONARK_CSS--*/</style>           <!-- frontend/styles/app.css, verbatim -->
</head>
<body>
  <!--MONARK_SHELL-->                         <!-- frontend/src/export/shell.html -->
  <script type="application/json" id="monark-scene-data"><!--MONARK_DATA--></script>
  <script><!--MONARK_BUNDLE--></script>       <!-- frontend/dist/export_viewer.js (IIFE) -->
</body>
</html>
```

**Sentinel substitution is one-directional and order-sensitive.** Substitute the
JSON payload and the JS bundle **last**, and never re-scan the assembled document
for sentinels — otherwise a project named `<!--MONARK_BUNDLE-->` becomes a code
injection. `test_html_export.py` covers exactly this case.

`<title>` is the only place a user string is HTML-interpolated; it is
`html.escape(name, quote=True)`. Everything else in the shell is static, with
user-facing text assigned at runtime from the payload via `textContent`.

---

## 4. Frontend Interface — `SceneDataSource`

> **Superseded (2026-08-01): `getTrueThickness` no longer exists.** The True
> Thickness Calculator was removed from the inspector, leaving the whole path
> — the `GET /collars/{id}/true-thickness` and
> `GET /share/{token}/collars/{id}/true-thickness` endpoints, the JS/Python
> implementations, the parity fixture and its two test suites — with no
> caller, so all of it was deleted. `SceneDataSource` is now the four methods
> `getScene`, `getCollarDetails`, `getTopographyPoints` and
> `getWireframeGeometry`, plus `isStatic`; `StaticDataSource` has no imports
> at all. Section 5 below describes a fixture that no longer exists. The rest
> of this section is left as the record of what feature 006 delivered — do not
> implement `getTrueThickness` from it.

`ApiDataSource` and `ShareTokenDataSource` live in
`frontend/src/services/data_source.js`.
`StaticDataSource` lives in `frontend/src/services/static_data_source.js` and
imports **only** `./true_thickness.js` — this isolation ensures that
`viewer_main.js` (Phase 3, T017) can import `StaticDataSource` without pulling
`api_client.js`, `window.location`, or any API base URL literal into the export
bundle (required by T022/T023). Do **not** re-export `StaticDataSource` from
`data_source.js`.

All methods are `async` regardless of implementation, so callers never branch on
which source they hold.

```js
/**
 * @typedef {Object} SceneDataSource
 * @property {() => Promise<SceneDTO>} getScene
 * @property {(collarId: string) => Promise<CollarDetailDTO>} getCollarDetails
 * @property {(collarId: string, intervalId: string, dipDirection: number, dip: number)
 *            => Promise<TrueThicknessDTO>} getTrueThickness
 * @property {(topographyRef: string|null) => Promise<Array<{e:number,n:number,el:number}>|null>} getTopographyPoints
 * @property {(wireframe: object) => Promise<{vertices:number[], indices:number[]}|null>} getWireframeGeometry
 * @property {boolean} isStatic   // true only for StaticDataSource; drives provenance UI, never rendering
 */
```

| Implementation | `getScene` | `getCollarDetails` | `getTrueThickness` | `getTopographyPoints` | `getWireframeGeometry` |
|---|---|---|---|---|---|
| `ApiDataSource` | `ApiClient.getProjectScene(projectId)` | `ApiClient.getCollarDetails` | `ApiClient.getTrueThickness` | `fetch('/uploads/{ref}')` + parse | `fetch('/uploads/{ref}')` + `parseOBJ` |
| `ShareTokenDataSource` | `ApiClient.getSharedScene(token)` | `ApiClient.getSharedCollar` | `ApiClient.getSharedTrueThickness` | same | same |
| `StaticDataSource` | `payload.scene` | `payload.collar_details[id]` | `computeTrueThickness(...)` (local) | `payload.topography.points` expanded | `w.vertices`/`w.faces` → buffers, else `null` |

`StaticDataSource` throws a descriptive `Error` on an unknown `collarId` rather than
returning `undefined` — a missing collar means a malformed payload, and it must
surface at the point of failure.

`TrueThicknessDTO` matches `collars.py:239–249` field-for-field:
`{collar_id, interval_id, apparent_thickness, true_thickness, hole_dip,
hole_azimuth, vein_dip_direction, vein_dip, intersection_angle_deg}`.
`inspector_panel.js:452–456` reads `true_thickness`, `apparent_thickness`,
`hole_dip`, `hole_azimuth` — all four must be populated by the client-side path.

---

## 5. True-Thickness Parity Fixture *(removed — see the note in section 4)*

`specs/006-standalone-html-export/fixtures/true_thickness_vectors.json` — consumed
unchanged by `backend/tests/unit/test_true_thickness_vectors.py` and
`frontend/tests/true_thickness_parity.test.mjs`.

```jsonc
{
  "tolerance": 1e-9,
  "cases": [
    {
      "name": "vertical hole through horizontal vein",
      "surveys": [{ "depth": 0, "dip": -90, "azimuth": 0 },
                  { "depth": 100, "dip": -90, "azimuth": 0 }],
      "from_depth": 10.0, "to_depth": 12.0,
      "dip_direction": 0.0, "vein_dip": 0.0,
      "expected": { "apparent_thickness": 2.0, "true_thickness": 2.0,
                    "hole_dip": -90.0, "hole_azimuth": 0.0 }
    }
  ]
}
```

Required coverage — these are the cases where a naive port goes wrong:

1. Vertical hole / horizontal vein → true == apparent.
2. Vertical hole / vertical vein → true ≈ 0 (grazing intersection).
3. Inclined hole, vein at 60° — a hand-checkable general case.
4. **Azimuth interpolation across 350° → 010°** — must interpolate on the unit
   circle (`collars.py:211–215`), not linearly; a linear port yields 180° and a
   silently wrong thickness. This is the single highest-value case in the fixture.
5. Mid-depth **below** the first and **above** the last survey station (clamping,
   `collars.py:192–197`).
6. Single survey station, and zero survey stations (defaults `-90.0` / `0.0`,
   `collars.py:181–186`).
7. Negative/obtuse `cos θ` → `abs()` applied (`collars.py:237`).

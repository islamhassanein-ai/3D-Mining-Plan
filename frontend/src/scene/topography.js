import * as THREE from 'three';
import Delaunator from 'delaunator';

// Elevation -> colour, using the "Earth" ramp from the reference viewer:
// brown lowlands through cream mid-slopes to teal-blue highs. The previous
// all-brown ramp had every stop in one hue family, so relief only read as a
// lightness change and the surface competed with the warm end of the grade
// scale. Earth spends its top half in cool hues instead, which the grade
// palette (grey/blue/green/yellow/red/magenta) never reaches at the same
// lightness -- the ground stays legible as ground.
const EARTH_STOPS = [
  [0.0000, 0xa16928],
  [0.1667, 0xbd925a],
  [0.3333, 0xd6bd8d],
  [0.5000, 0xedeac2],
  [0.6667, 0xb5c8b8],
  [0.8333, 0x79a7ac],
  [1.0000, 0x2887a1],
];

function elevationColor(t) {
  const clamped = Math.min(1, Math.max(0, t));
  for (let i = 1; i < EARTH_STOPS.length; i++) {
    if (clamped <= EARTH_STOPS[i][0]) {
      const [t0, c0] = EARTH_STOPS[i - 1];
      const [t1, c1] = EARTH_STOPS[i];
      const localT = t1 === t0 ? 0 : (clamped - t0) / (t1 - t0);
      return new THREE.Color(c0).lerp(new THREE.Color(c1), localT);
    }
  }
  return new THREE.Color(EARTH_STOPS[EARTH_STOPS.length - 1][1]);
}

// Surface opacity, matching the reference viewer. Slightly translucent so a
// collar or trench that sits a hair below the interpolated ground still shows
// through instead of disappearing.
const SURFACE_OPACITY = 0.78;

// Roughly how many contour bands to draw across the full elevation range.
// The actual interval is snapped to a 1/2/5 x 10^n step so the labels a
// geologist reads off them are round numbers.
const TARGET_CONTOUR_COUNT = 14;

// A surface interpolated from collars/trenches is a guess, so it renders
// noticeably more transparent than a surveyed one -- the difference is
// visible side by side, and the legend says "derived" as well.
const DERIVED_SURFACE_OPACITY = 0.45;

// Contour interval snapped to the 1-2-5 series.
function niceContourInterval(range) {
  const raw = range / TARGET_CONTOUR_COUNT;
  if (!(raw > 0)) return 0;
  const magnitude = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / magnitude;
  const step = norm <= 1.5 ? 1 : norm <= 3.5 ? 2 : norm <= 7.5 ? 5 : 10;
  return step * magnitude;
}

/**
 * Iso-elevation polylines over a triangulated surface.
 *
 * For each triangle and each contour level, the plane y = level cuts the
 * triangle in a single segment whenever exactly one vertex sits on the
 * opposite side of the level from the other two. Collecting those segments
 * gives the contour set directly -- no grid resampling, so the lines follow
 * the actual triangulation and stay correct on irregular survey coverage.
 */
function buildContourSegments(positions, indices, minEl, maxEl, interval) {
  const segments = [];
  if (!(interval > 0)) return segments;

  const first = Math.ceil(minEl / interval) * interval;

  for (let t = 0; t < indices.length; t += 3) {
    const vi = [indices[t], indices[t + 1], indices[t + 2]];
    const ys = vi.map(i => positions[3 * i + 1]);
    const triMin = Math.min(ys[0], ys[1], ys[2]);
    const triMax = Math.max(ys[0], ys[1], ys[2]);

    for (let level = Math.ceil(triMin / interval) * interval;
         level <= triMax; level += interval) {
      if (level < first || level > maxEl) continue;

      // Interpolate along each edge that straddles the level.
      const crossings = [];
      for (let e = 0; e < 3; e++) {
        const a = vi[e];
        const b = vi[(e + 1) % 3];
        const ya = positions[3 * a + 1];
        const yb = positions[3 * b + 1];
        if ((ya < level && yb < level) || (ya > level && yb > level)) continue;
        if (ya === yb) continue; // edge lies in the plane; the other two carry it
        const f = (level - ya) / (yb - ya);
        if (f < 0 || f > 1) continue;
        crossings.push([
          positions[3 * a] + f * (positions[3 * b] - positions[3 * a]),
          level,
          positions[3 * a + 2] + f * (positions[3 * b + 2] - positions[3 * a + 2]),
        ]);
      }

      if (crossings.length >= 2) {
        segments.push(...crossings[0], ...crossings[1]);
      }
    }
  }

  return segments;
}

// Exported so ApiDataSource and the Python-side service share identical parsing rules.
export function parseTopographyCSV(csvText) {
  const lines = csvText.split('\n');
  if (lines.length < 2) return [];
  const headers = lines[0].trim().toLowerCase().split(',');
  const eIdx = headers.findIndex(h => h.includes('east'));
  const nIdx = headers.findIndex(h => h.includes('north'));
  const elIdx = headers.findIndex(h => h.includes('elev') || h === 'z' || h.includes('alt'));
  if (eIdx === -1 || nIdx === -1 || elIdx === -1) return [];
  const points = [];
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const cols = line.split(',');
    const e = parseFloat(cols[eIdx]);
    const n = parseFloat(cols[nIdx]);
    const el = parseFloat(cols[elIdx]);
    if (!isNaN(e) && !isNaN(n) && !isNaN(el)) {
      points.push({ e, n, el });
    }
  }
  return points;
}

export class TopographyRenderer {
  constructor(scene) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.name = 'topography-surface';
    this.scene.add(this.group);

    this.meshObject = null;
    this.pointsObject = null;
    this.contourObject = null;
    this.contourInterval = null;
    this.displayMode = 'mesh'; // 'mesh' | 'points'

    // True when the surface was interpolated from collars/trench samples
    // instead of an uploaded topography survey. It renders more transparently
    // so it never passes for measured ground -- see renderDerived().
    this.derived = false;
  }

  async loadAndRender(fileRef) {
    this.clear();
    if (!fileRef) return;

    try {
      // Fetch the topography CSV file content
      const API_BASE_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') ? 'http://localhost:8000' : '';
      const response = await fetch(`${API_BASE_URL}/uploads/${fileRef}`);
      if (!response.ok) throw new Error('Failed to download topography file');

      const text = await response.text();
      this.renderCSVPoints(text);
    } catch (err) {
      console.error('Failed to render topography:', err);
    }
  }

  /**
   * Interpolates a ground surface from whatever surveyed points the project
   * does have -- drill collars, trench channel samples, structural stations --
   * for projects with no uploaded topography at all. Without this the scene
   * has no ground plane, and a drill trace hanging in empty space gives no
   * sense of relief or of where surface sampling sits relative to it.
   *
   * It is an interpolation between sparse control points, NOT a survey: the
   * result is drawn more transparently, without the point cloud (there is no
   * measured cloud to show), and the legend relabels it "Surface (derived)".
   * Three non-collinear points is the minimum Delaunay can trianglate.
   */
  renderDerived(points) {
    this.clear();
    if (!points || points.length < 3) return false;
    this.derived = true;
    this._buildTriangulatedMesh(points);
    if (!this.meshObject) return false;
    this._applyDisplayMode();
    return true;
  }

  renderPoints(points) {
    if (!points || points.length === 0) return;
    this.derived = false;
    this._buildPointCloud(points);
    if (points.length >= 3) this._buildTriangulatedMesh(points);
    this._applyDisplayMode();

    // Bounding wireframe boundary for context
    const box = new THREE.Box3().setFromPoints(
      points.map(p => new THREE.Vector3(p.e, p.el, p.n))
    );
    const helper = new THREE.Box3Helper(box, 0x1e3a8a);
    this.group.add(helper);
  }

  renderCSVPoints(csvText) {
    const points = parseTopographyCSV(csvText);
    if (!points.length) {
      console.warn('Topography CSV headers must contain Easting, Northing, and Elevation');
      return;
    }
    this.renderPoints(points);
  }

  _buildPointCloud(points) {
    const vecs = points.map(p => new THREE.Vector3(p.e, p.el, p.n));
    const geometry = new THREE.BufferGeometry().setFromPoints(vecs);
    const material = new THREE.PointsMaterial({
      color: 0x3b82f6,
      size: 4.0,
      transparent: true,
      opacity: 0.6,
      sizeAttenuation: true
    });

    this.pointsObject = new THREE.Points(geometry, material);
    this.pointsObject.userData = { type: 'topography_points' };
    this.group.add(this.pointsObject);
  }

  // Builds a continuous shaded terrain surface via 2D Delaunay
  // triangulation (Easting/Northing plane), lifting each vertex to its
  // sampled elevation -- a proper terrain mesh instead of a flat point
  // cloud, so the ground reads as a surface from any angle.
  _buildTriangulatedMesh(points) {
    const coords = new Float64Array(points.length * 2);
    for (let i = 0; i < points.length; i++) {
      coords[2 * i] = points[i].e;
      coords[2 * i + 1] = points[i].n;
    }

    const delaunay = new Delaunator(coords);
    const triangles = delaunay.triangles;

    const positions = new Float32Array(points.length * 3);
    const colors = new Float32Array(points.length * 3);
    let minEl = Infinity, maxEl = -Infinity;
    for (const p of points) {
      if (p.el < minEl) minEl = p.el;
      if (p.el > maxEl) maxEl = p.el;
    }
    const elRange = Math.max(maxEl - minEl, 1e-6);

    for (let i = 0; i < points.length; i++) {
      const p = points[i];
      positions[3 * i] = p.e;
      positions[3 * i + 1] = p.el;
      positions[3 * i + 2] = p.n;

      const c = elevationColor((p.el - minEl) / elRange);
      colors[3 * i] = c.r;
      colors[3 * i + 1] = c.g;
      colors[3 * i + 2] = c.b;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.setIndex(new THREE.BufferAttribute(triangles, 1));
    geometry.computeVertexNormals();

    const material = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.68,
      metalness: 0.0,
      side: THREE.DoubleSide,
      flatShading: false,
      transparent: true,
      opacity: this.derived ? DERIVED_SURFACE_OPACITY : SURFACE_OPACITY,
      // Without this the translucent ground writes depth and clips the assay
      // tubes that pass through it.
      depthWrite: false,
    });

    this.meshObject = new THREE.Mesh(geometry, material);
    this.meshObject.userData = { type: 'topography_mesh' };
    this.meshObject.renderOrder = -1;
    this.group.add(this.meshObject);

    this._buildContours(positions, triangles, minEl, maxEl);
  }

  // Contour lines lifted a hair above the surface so they don't z-fight with
  // the triangles they were cut from. White at low opacity reads as a survey
  // overlay on every band of the Earth ramp, warm or cool.
  _buildContours(positions, indices, minEl, maxEl) {
    const interval = niceContourInterval(maxEl - minEl);
    const segments = buildContourSegments(
      positions, indices, minEl, maxEl, interval
    );
    if (!segments.length) return;

    const lift = Math.max((maxEl - minEl) * 0.002, 0.05);
    for (let i = 1; i < segments.length; i += 3) segments[i] += lift;

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      'position', new THREE.Float32BufferAttribute(segments, 3)
    );

    const material = new THREE.LineBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.34,
      depthWrite: false,
    });

    this.contourObject = new THREE.LineSegments(geometry, material);
    this.contourObject.userData = { type: 'topography_contours', excludeFromFit: true };
    this.contourObject.renderOrder = 0;
    this.contourObject.raycast = () => {};
    this.contourInterval = interval;
    this.group.add(this.contourObject);
  }

  // Toggles between the shaded continuous terrain mesh and the raw point
  // cloud it was triangulated from -- useful for sanity-checking sample
  // coverage/density against the interpolated surface.
  setDisplayMode(mode) {
    this.displayMode = mode === 'points' ? 'points' : 'mesh';
    this._applyDisplayMode();
  }

  _applyDisplayMode() {
    if (this.meshObject) this.meshObject.visible = this.displayMode === 'mesh';
    if (this.contourObject) this.contourObject.visible = this.displayMode === 'mesh';
    // A derived surface has no measured point cloud behind it, so point mode
    // would show an empty viewport -- keep the mesh up instead.
    if (this.pointsObject) {
      this.pointsObject.visible = this.displayMode === 'points';
    } else if (this.meshObject) {
      this.meshObject.visible = true;
      if (this.contourObject) this.contourObject.visible = true;
    }
  }

  clear() {
    this.group.traverse((child) => {
      if (child.geometry) child.geometry.dispose();
      if (child.material) {
        if (Array.isArray(child.material)) {
          child.material.forEach(m => m.dispose());
        } else {
          child.material.dispose();
        }
      }
    });
    while (this.group.children.length > 0) {
      this.group.remove(this.group.children[0]);
    }
    this.meshObject = null;
    this.pointsObject = null;
    this.contourObject = null;
    this.contourInterval = null;
    this.derived = false;
  }
}

import * as THREE from 'three';
import Delaunator from 'delaunator';

// Elevation -> color ramp (low = deep brown, high = pale tan/white), giving
// the shaded terrain mesh a readable sense of relief instead of a single
// flat color.
function elevationColor(t) {
  const stops = [
    [0.0, 0x3f2a14],
    [0.35, 0x6b4a25],
    [0.6, 0x9c7a4a],
    [0.8, 0xc9b183],
    [1.0, 0xe8ddc0]
  ];
  for (let i = 1; i < stops.length; i++) {
    if (t <= stops[i][0]) {
      const [t0, c0] = stops[i - 1];
      const [t1, c1] = stops[i];
      const localT = t1 === t0 ? 0 : (t - t0) / (t1 - t0);
      const a = new THREE.Color(c0);
      const b = new THREE.Color(c1);
      return a.lerp(b, localT);
    }
  }
  return new THREE.Color(stops[stops.length - 1][1]);
}

export class TopographyRenderer {
  constructor(scene) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.name = 'topography-surface';
    this.scene.add(this.group);

    this.meshObject = null;
    this.pointsObject = null;
    this.displayMode = 'mesh'; // 'mesh' | 'points'
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

  renderCSVPoints(csvText) {
    const lines = csvText.split('\n');
    if (lines.length < 2) return;

    // Parse headers
    const headers = lines[0].trim().toLowerCase().split(',');
    const eIdx = headers.findIndex(h => h.includes('east'));
    const nIdx = headers.findIndex(h => h.includes('north'));
    const elIdx = headers.findIndex(h => h.includes('elev') || h.includes('z') || h.includes('alt'));

    if (eIdx === -1 || nIdx === -1 || elIdx === -1) {
      console.warn('Topography CSV headers must contain Easting, Northing, and Elevation');
      return;
    }

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

    if (points.length === 0) return;

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
      roughness: 0.85,
      metalness: 0.0,
      side: THREE.DoubleSide,
      flatShading: false
    });

    this.meshObject = new THREE.Mesh(geometry, material);
    this.meshObject.userData = { type: 'topography_mesh' };
    this.group.add(this.meshObject);
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
    if (this.pointsObject) this.pointsObject.visible = this.displayMode === 'points';
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
  }
}

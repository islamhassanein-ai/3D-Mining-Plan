import * as THREE from 'three';

import { GRADE_BUCKETS, getGradeBucketIndex, TRENCH_HEIGHT_BY_BUCKET } from './grade_scale.js';

// Reconstructs the sample-taking order along a trench from unordered
// easting/northing points via greedy nearest-neighbor chaining. The API
// doesn't guarantee row order, but trench channel samples are taken
// sequentially along a roughly straight line, so nearest-neighbor from an
// endpoint reliably recovers the walking order.
function orderTrenchPoints(points) {
  if (points.length <= 2) return points;

  // Start from whichever point is farthest from the group's centroid --
  // that's very likely one of the two ends of the line.
  const cx = points.reduce((s, p) => s + p.easting, 0) / points.length;
  const cy = points.reduce((s, p) => s + p.northing, 0) / points.length;
  let startIdx = 0;
  let maxDist = -1;
  points.forEach((p, i) => {
    const d = Math.hypot(p.easting - cx, p.northing - cy);
    if (d > maxDist) { maxDist = d; startIdx = i; }
  });

  const remaining = points.slice();
  const ordered = [remaining.splice(startIdx, 1)[0]];
  while (remaining.length) {
    const last = ordered[ordered.length - 1];
    let nearestIdx = 0;
    let nearestDist = Infinity;
    remaining.forEach((p, i) => {
      const d = Math.hypot(p.easting - last.easting, p.northing - last.northing);
      if (d < nearestDist) { nearestDist = d; nearestIdx = i; }
    });
    ordered.push(remaining.splice(nearestIdx, 1)[0]);
  }
  return ordered;
}

function newAcc() {
  return { positions: [], indices: [] };
}

// Appends a vertical ribbon quad standing on the ground between p0 and p1,
// extruded straight up by `height`. Two triangles, no caps needed since
// it's an open (double-sided) surface rather than a closed volume.
function appendRibbonSegment(acc, p0, p1, height) {
  const base = acc.positions.length / 3;
  acc.positions.push(p0.x, p0.y, p0.z);
  acc.positions.push(p0.x, p0.y + height, p0.z);
  acc.positions.push(p1.x, p1.y, p1.z);
  acc.positions.push(p1.x, p1.y + height, p1.z);
  acc.indices.push(base, base + 2, base + 1);
  acc.indices.push(base + 1, base + 2, base + 3);
}

export class TrenchesRenderer {
  constructor(scene) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.name = 'trench-fences';
    this.scene.add(this.group);
  }

  // Trenches are shallow surface channel samples, not round drill core --
  // rendering them as round tubes (like drillholes) made the two feel
  // visually interchangeable at a glance. Instead each trench is drawn as
  // a vertical "grade profile fence" standing along the walked line, with
  // fence height (not tube radius) encoding the grade bucket. This is the
  // standard way channel-sample results are shown in exploration grade
  // profile diagrams, and it reads unambiguously as "surface line", not
  // "borehole", from any camera angle.
  render(trenches, drillholes) {
    this.clear();
    if (!trenches || trenches.length === 0) return;

    // Baseline elevation fallback for legacy trench rows uploaded before
    // elevation was captured -- average collar elevation keeps them roughly
    // at surface level instead of collapsing to 0.
    let baselineElevation = 0.0;
    if (drillholes && drillholes.length > 0) {
      const sum = drillholes.reduce((s, dh) => s + dh.elevation, 0);
      baselineElevation = sum / drillholes.length;
    }

    const groups = new Map();
    for (const t of trenches) {
      if (t.easting == null || t.northing == null) continue;
      if (!groups.has(t.trench_id)) groups.set(t.trench_id, []);
      groups.get(t.trench_id).push({
        easting: t.easting,
        northing: t.northing,
        elevation: t.elevation != null ? t.elevation : baselineElevation,
        grade: t.grade_value
      });
    }

    const accsByBucket = Array.from({ length: GRADE_BUCKETS.length }, () => newAcc());

    for (const points of groups.values()) {
      const ordered = orderTrenchPoints(points);
      for (let i = 0; i < ordered.length - 1; i++) {
        const a = ordered[i], b = ordered[i + 1];
        const p0 = new THREE.Vector3(a.easting, a.elevation, a.northing);
        const p1 = new THREE.Vector3(b.easting, b.elevation, b.northing);
        if (p0.distanceTo(p1) < 1e-6) continue;

        const grade = b.grade != null ? b.grade : (a.grade != null ? a.grade : 0);
        const bucketIdx = getGradeBucketIndex(grade);
        appendRibbonSegment(accsByBucket[bucketIdx], p0, p1, TRENCH_HEIGHT_BY_BUCKET[bucketIdx]);
      }
    }

    for (let b = 0; b < GRADE_BUCKETS.length; b++) {
      const acc = accsByBucket[b];
      if (acc.positions.length === 0) continue;

      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(acc.positions), 3));
      geometry.setIndex(acc.indices);
      geometry.computeVertexNormals();

      const material = new THREE.MeshStandardMaterial({
        color: GRADE_BUCKETS[b].color,
        roughness: 0.6,
        metalness: 0.05,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.92
      });

      const mesh = new THREE.Mesh(geometry, material);
      mesh.userData = { type: 'trench_fence', bucket: b };
      this.group.add(mesh);
    }
  }

  clear() {
    this.group.traverse((child) => {
      if (child.isMesh) {
        if (child.geometry) child.geometry.dispose();
        if (child.material) child.material.dispose();
      }
    });
    while (this.group.children.length > 0) {
      this.group.remove(this.group.children[0]);
    }
  }
}

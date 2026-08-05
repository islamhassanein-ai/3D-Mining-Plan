import * as THREE from 'three';

import {
  GRADE_BUCKETS,
  getGradeBucketIndex,
  TRENCH_HEIGHT_BY_BUCKET,
  TRENCH_UNSAMPLED_HEIGHT,
  UNSAMPLED_BUCKET_INDEX,
  UNSAMPLED_COLOR,
} from './grade_scale.js';

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
  return { positions: [], indices: [], grades: [] };
}

// Appends a vertical ribbon quad standing on the ground between p0 and p1,
// extruded straight up by `height`. Two triangles, no caps needed since
// it's an open (double-sided) surface rather than a closed volume.
//
// `grade` is stamped on all four vertices so the GPU cutoff can discard the
// segment; an unsampled segment carries 0, matching Number(null) in the
// drillhole tube builder, so both drop out at any cutoff above zero.
function appendRibbonSegment(acc, p0, p1, height, grade) {
  const base = acc.positions.length / 3;
  acc.positions.push(p0.x, p0.y, p0.z);
  acc.positions.push(p0.x, p0.y + height, p0.z);
  acc.positions.push(p1.x, p1.y, p1.z);
  acc.positions.push(p1.x, p1.y + height, p1.z);
  const g = Number(grade);
  acc.grades.push(g, g, g, g);
  acc.indices.push(base, base + 2, base + 1);
  acc.indices.push(base + 1, base + 2, base + 3);
}

export class TrenchesRenderer {
  constructor(scene) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.name = 'trench-fences';
    this.scene.add(this.group);

    // The grade cutoff applies to trench channel samples exactly as it does to
    // drillhole assays -- a cutoff that silently spared TR fences made the
    // scene read as though the trenches were all above it.
    this.currentCutoff = 0.0;
    this.materials = [];
  }

  // Same trick as the assay tubes: per-vertex grade compared against one
  // uniform in the fragment shader, so moving the slider costs a uniform
  // write rather than a geometry rebuild.
  _buildMaterial(color) {
    const material = new THREE.MeshStandardMaterial({
      color,
      roughness: 0.6,
      metalness: 0.05,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.92
    });

    material.onBeforeCompile = (shader) => {
      shader.uniforms.uCutoff = { value: this.currentCutoff };

      shader.vertexShader = shader.vertexShader
        .replace('#include <common>',
                 'attribute float aGrade;\nvarying float vGrade;\n#include <common>')
        .replace('#include <begin_vertex>',
                 '#include <begin_vertex>\nvGrade = aGrade;');

      shader.fragmentShader = shader.fragmentShader
        .replace('#include <common>',
                 'uniform float uCutoff;\nvarying float vGrade;\n#include <common>')
        .replace('#include <clipping_planes_fragment>',
                 '#include <clipping_planes_fragment>\nif (vGrade < uCutoff) discard;');

      material.userData.shader = shader;
    };
    material.customProgramCacheKey = () => 'trench-fence';

    return material;
  }

  setGradeCutoff(cutoffValue) {
    this.currentCutoff = Number(cutoffValue);
    for (const material of this.materials) {
      if (material.userData.shader) {
        material.userData.shader.uniforms.uCutoff.value = this.currentCutoff;
      }
    }
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
        grade: t.grade_value,
        sample_id: t.sample_id,
        point_order: t.point_order
      });
    }

    // One accumulator per grade bucket, plus a trailing slot for unsampled
    // segments (bucket index -1 maps to GRADE_BUCKETS.length).
    const UNSAMPLED_SLOT = GRADE_BUCKETS.length;
    const accsByBucket = Array.from({ length: GRADE_BUCKETS.length + 1 }, () => newAcc());

    for (const points of groups.values()) {
      // When every point in the group carries a point_order (the combined-CSV
      // import stamps 0..N), order is authoritative -- use it directly. Legacy
      // trench rows have point_order = null and must keep falling back to the
      // nearest-neighbour chaining in orderTrenchPoints (which itself returns
      // early for length <= 2). Do NOT delete orderTrenchPoints.
      let ordered;
      if (points.length > 0 && points.every(p => p.point_order !== null && p.point_order !== undefined)) {
        ordered = points.slice().sort((a, b) => a.point_order - b.point_order);
      } else {
        ordered = orderTrenchPoints(points);
      }
      for (let i = 0; i < ordered.length - 1; i++) {
        const a = ordered[i], b = ordered[i + 1];
        const p0 = new THREE.Vector3(a.easting, a.elevation, a.northing);
        const p1 = new THREE.Vector3(b.easting, b.elevation, b.northing);
        if (p0.distanceTo(p1) < 1e-6) continue;

        // Carry the sample id alongside the grade so a placeholder id
        // ('NSR', 'No Sample', ...) routes to the unsampled slot instead of
        // being read as a 0 g/t result.
        const useB = b.grade != null || a.grade == null;
        const grade = useB ? b.grade : a.grade;
        const sampleId = useB ? b.sample_id : a.sample_id;

        const bucketIdx = getGradeBucketIndex(grade, 'g/t', sampleId);
        const slot = bucketIdx === UNSAMPLED_BUCKET_INDEX ? UNSAMPLED_SLOT : bucketIdx;
        const height = bucketIdx === UNSAMPLED_BUCKET_INDEX
          ? TRENCH_UNSAMPLED_HEIGHT
          : TRENCH_HEIGHT_BY_BUCKET[bucketIdx];
        // An unsampled segment has no result to compare against the cutoff,
        // so it goes in at 0 -- the same value an unsampled drillhole interval
        // carries -- rather than whatever placeholder grade came with it.
        const cutoffGrade = bucketIdx === UNSAMPLED_BUCKET_INDEX ? 0 : Number(grade);
        appendRibbonSegment(accsByBucket[slot], p0, p1, height, cutoffGrade);
      }
    }

    for (let b = 0; b < accsByBucket.length; b++) {
      const acc = accsByBucket[b];
      if (acc.positions.length === 0) continue;
      const isUnsampledSlot = b === UNSAMPLED_SLOT;

      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(acc.positions), 3));
      geometry.setAttribute('aGrade', new THREE.BufferAttribute(new Float32Array(acc.grades), 1));
      geometry.setIndex(acc.indices);
      geometry.computeVertexNormals();

      const material = this._buildMaterial(
        isUnsampledSlot ? UNSAMPLED_COLOR : GRADE_BUCKETS[b].color
      );
      this.materials.push(material);

      const mesh = new THREE.Mesh(geometry, material);
      mesh.userData = {
        type: 'trench_fence',
        bucket: isUnsampledSlot ? UNSAMPLED_BUCKET_INDEX : b,
      };
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
    // Disposed above with their meshes; drop the cutoff's handles on them so
    // setGradeCutoff doesn't keep writing uniforms into dead materials.
    this.materials = [];
  }
}

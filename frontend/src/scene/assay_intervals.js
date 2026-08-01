import * as THREE from 'three';
import {
  isUnsampled,
  getGradeBucketIndex,
  DRILL_TUBE_RADIUS,
  DRILL_TUBE_RADIUS_BY_BUCKET,
  DRILL_TUBE_RADIUS_UNSAMPLED,
  DRILL_TUBE_RADIAL_SEGMENTS,
  UNSAMPLED_BUCKET_INDEX,
} from './grade_scale.js';
import { buildHoleTube } from './tube_builder.js';
import { interpolateTracePosition } from './trace_geometry.js';

// QA/QC-flagged samples (duplicate/blank/standard) are exploration-control
// samples, not ore intervals -- so they're rendered in a distinct color
// instead of the grade-cutoff color, making them "visibly distinguishable...
// wherever assay data is displayed" per spec SC-005, rather than blending in
// with regular grade coloring.
const QAQC_COLORS = {
  duplicate: '#60a5fa',
  blank: '#94a3b8',
  standard: '#34d399',
  standard_failed: '#f87171',
  unconfigured: '#fbbf24'
};

// Planned holes carry target intervals, not measured results. They render at
// reduced opacity over the same geometry so they read as "proposed" at a
// glance without changing the shape language of the scene.
const PLANNED_OPACITY = 0.38;

export class AssayIntervals {
  constructor(scene) {
    this.scene = scene;

    // One mesh per hole, held in two groups by status. Per-hole meshes (rather
    // than one merged buffer) are what make the LOD manager cheap: hiding a
    // distant hole removes its draw call outright.
    this.group = new THREE.Group();
    this.group.name = 'assay-intervals';
    this.plannedGroup = new THREE.Group();
    this.plannedGroup.name = 'assay-intervals-planned';
    this.scene.add(this.group);
    this.scene.add(this.plannedGroup);

    this.holeMeshes = new Map(); // collar_id -> THREE.Mesh
    this.intervalsData = [];     // every rendered interval, for the histogram etc.
    // interval id -> { position, radius } in world space, so selecting a row
    // in the downhole log can point at that sample in 3D. Built during render
    // from the desurveyed trace, which is the only place the mapping from an
    // absolute depth to a position exists.
    this.intervalAnchors = new Map();
    // Set by the viewport; see highlightInterval.
    this.focusHighlight = null;
    this.currentCutoff = 0.0;
    this.lodStates = null;       // Map<collar_id, boolean>; null = LOD inactive

    // 'uniform' (default, Leapfrog convention -- grade is colour only) or
    // 'grade' (diameter also steps with the grade bucket). Switching modes
    // rebuilds the tube geometry, so the last rendered drillholes are kept
    // to replay the build without a round trip to the API.
    this.thicknessMode = 'uniform';
    this.lastDrillholes = null;

    this.materials = [];
    // `mesh` / `plannedMesh` are kept as aliases so the layer panel and any
    // other consumer that expects a single toggleable object still works.
    this.mesh = this.group;
    this.plannedMesh = this.plannedGroup;
  }

  render(drillholes) {
    this.clear();
    this.lastDrillholes = drillholes;

    const radius = this._radiusResolver();
    const drilledMaterial = this._buildMaterial(false);
    const plannedMaterial = this._buildMaterial(true);
    this.materials = [drilledMaterial, plannedMaterial];

    for (const dh of drillholes) {
      const isPlanned = dh.hole_status === 'planned';
      const trace = dh.trace || [];

      // Absolute from/to depths drive every ring position, so an interval
      // logged at 37 m sits 37 m along the desurveyed curve no matter how much
      // of the hole above it went unsampled. Unsampled intervals are dropped
      // entirely: those depths show the bare trace line, which is what "no
      // sample" should look like.
      const sampled = dh.assays
        .filter(a => !(a.unsampled || isUnsampled(a.grade_value, a.sample_id)))
        .map(a => ({
          id: a.id,
          hole_id: dh.hole_id,
          collar_id: dh.collar_id,
          hole_status: isPlanned ? 'planned' : 'drilled',
          sample_id: a.sample_id || null,
          from_depth: a.from_depth,
          to_depth: a.to_depth,
          grade_value: a.grade_value,
          grade_unit: a.grade_unit,
          qaqc_flag: a.qaqc_flag || null,
          // QA/QC control samples override the grade colour.
          color: (a.qaqc_flag && QAQC_COLORS[a.qaqc_flag]) || a.color,
        }))
        .sort((x, y) => x.from_depth - y.from_depth);

      if (!sampled.length) continue;
      this.intervalsData.push(...sampled);

      for (const interval of sampled) {
        const midDepth = (interval.from_depth + interval.to_depth) / 2;
        const start = interpolateTracePosition(trace, interval.from_depth);
        const end = interpolateTracePosition(trace, interval.to_depth);
        this.intervalAnchors.set(interval.id, {
          position: interpolateTracePosition(trace, midDepth),
          // Half the interval's own length, floored so a 0.5 m sample still
          // gets a ring big enough to see.
          radius: Math.max(start.distanceTo(end) / 2, 1.2),
        });
      }

      const built = buildHoleTube(
        trace, sampled, radius, DRILL_TUBE_RADIAL_SEGMENTS
      );
      if (!built) continue;

      const mesh = new THREE.Mesh(
        built.geometry, isPlanned ? plannedMaterial : drilledMaterial
      );
      mesh.name = `assay-tube-${dh.hole_id}`;
      if (isPlanned) mesh.renderOrder = 2;
      mesh.userData = {
        type: 'assay_intervals',
        collar_id: dh.collar_id,
        hole_id: dh.hole_id,
        hole_status: isPlanned ? 'planned' : 'drilled',
        // Vertex index -> interval, for resolving a raycast hit to a sample.
        intervalRefs: built.intervalRefs,
      };

      (isPlanned ? this.plannedGroup : this.group).add(mesh);
      this.holeMeshes.set(dh.collar_id, mesh);
    }

    this.applyLodStates();
  }

  // A constant in 'uniform' mode, a per-interval lookup in 'grade' mode.
  // buildHoleTube accepts either form.
  _radiusResolver() {
    if (this.thicknessMode !== 'grade') return DRILL_TUBE_RADIUS;
    return (interval) => {
      const idx = getGradeBucketIndex(
        interval.grade_value, interval.grade_unit, interval.sample_id
      );
      if (idx === UNSAMPLED_BUCKET_INDEX) return DRILL_TUBE_RADIUS_UNSAMPLED;
      return DRILL_TUBE_RADIUS_BY_BUCKET[idx];
    };
  }

  // 'uniform' | 'grade'. Rebuilds from the last rendered drillholes, so it is
  // safe to call before any data has loaded (it becomes a no-op).
  setThicknessMode(mode) {
    const next = mode === 'grade' ? 'grade' : 'uniform';
    if (next === this.thicknessMode) return;
    this.thicknessMode = next;
    if (this.lastDrillholes) {
      const cutoff = this.currentCutoff;
      this.render(this.lastDrillholes);
      this.setGradeCutoff(cutoff);
    }
  }

  _buildMaterial(planned) {
    const material = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.38,
      metalness: 0.08,
      flatShading: false,
      transparent: planned,
      opacity: planned ? PLANNED_OPACITY : 1.0,
      depthWrite: !planned,
    });

    // Per-vertex grade consumed on the GPU, so the cutoff slider only updates
    // one uniform -- no CPU-side rebuild, independent of interval count.
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
    material.customProgramCacheKey = () =>
      planned ? 'assay-tube-planned' : 'assay-tube-drilled';

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

  /**
   * Points the 3D view at one sampled interval, by id.
   *
   * index.html has called this from the inspector's row-selection callback
   * since the panel was written, but the method never existed -- so clicking a
   * row threw a TypeError and nothing happened in the scene. Passing a null or
   * unknown id clears the highlight, which is what deselecting should do.
   */
  highlightInterval(intervalId) {
    if (!this.focusHighlight) return;
    const anchor = intervalId ? this.intervalAnchors.get(intervalId) : null;
    if (!anchor) {
      this.focusHighlight.clear();
      return;
    }
    this.focusHighlight.focusOn(anchor.position, anchor.radius);
  }

  setLodStates(lodStates) {
    this.lodStates = lodStates;
    this.applyLodStates();
  }

  // Hiding a whole hole mesh drops its draw call, which is the point of LOD.
  applyLodStates() {
    if (!this.lodStates) return;
    for (const [collarId, mesh] of this.holeMeshes) {
      mesh.visible = this.lodStates.get(collarId) !== false;
    }
  }

  // Visibility hook for the "Planned Boreholes" layer toggle.
  setPlannedVisible(visible) {
    this.plannedGroup.visible = visible;
  }

  clear() {
    for (const group of [this.group, this.plannedGroup]) {
      for (const child of [...group.children]) {
        if (child.geometry) child.geometry.dispose();
        group.remove(child);
      }
    }
    // Materials are shared across every hole in a render pass.
    for (const material of this.materials) material.dispose();
    this.materials = [];
    this.holeMeshes.clear();
    this.intervalsData = [];
    this.intervalAnchors.clear();
  }
}

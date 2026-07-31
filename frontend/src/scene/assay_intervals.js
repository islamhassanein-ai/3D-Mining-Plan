import * as THREE from 'three';
import {
  isUnsampled,
  DRILL_TUBE_RADIUS,
  DRILL_TUBE_RADIAL_SEGMENTS,
} from './grade_scale.js';
import { subdivideIntervalAlongTrace } from './trace_geometry.js';

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
    // One InstancedMesh per hole status: drilled intervals are opaque,
    // planned target intervals translucent. Kept as separate meshes because a
    // single InstancedMesh cannot mix opacity per instance.
    this.mesh = null;         // drilled
    this.plannedMesh = null;  // planned
    this.intervalsData = [];         // drilled, one entry per rendered instance
    this.plannedIntervalsData = [];  // planned, one entry per rendered instance
    this.currentCutoff = 0.0;
    this.lodStates = null; // Map<collar_id, boolean> from LodManager; null = LOD inactive
  }

  render(drillholes) {
    this.clear();

    // 1. Flatten every assay interval into straight tube segments that follow
    //    the desurveyed trace.
    //
    //    Positions come from the hole's own trace at the interval's ABSOLUTE
    //    from/to depths, so an interval logged at 37 m - 38 m sits 37 m down
    //    the trajectory regardless of how much of the hole above it went
    //    unsampled. Unsampled intervals get no tube at all -- those depths
    //    show the bare trace line, which is what "no sample" should look like.
    this.intervalsData = [];
    this.plannedIntervalsData = [];

    for (const dh of drillholes) {
      const isPlanned = dh.hole_status === 'planned';
      const bucket = isPlanned ? this.plannedIntervalsData : this.intervalsData;
      const trace = dh.trace || [];

      for (const assay of dh.assays) {
        if (assay.unsampled || isUnsampled(assay.grade_value, assay.sample_id)) continue;

        const segments = trace.length >= 2
          ? subdivideIntervalAlongTrace(trace, assay.from_depth, assay.to_depth)
          : [{
              start: new THREE.Vector3(assay.start_pos[0], assay.start_pos[2], assay.start_pos[1]),
              end: new THREE.Vector3(assay.end_pos[0], assay.end_pos[2], assay.end_pos[1])
            }];

        for (const seg of segments) {
          bucket.push({
            id: assay.id,
            hole_id: dh.hole_id,
            collar_id: dh.collar_id,
            hole_status: isPlanned ? 'planned' : 'drilled',
            sample_id: assay.sample_id || null,
            from_depth: assay.from_depth,
            to_depth: assay.to_depth,
            grade_value: assay.grade_value,
            grade_unit: assay.grade_unit,
            color: assay.color,
            qaqc_flag: assay.qaqc_flag || null,
            start: seg.start,
            end: seg.end
          });
        }
      }
    }

    this.mesh = this._buildMesh(this.intervalsData, false);
    this.plannedMesh = this._buildMesh(this.plannedIntervalsData, true);

    this.updateMeshMatrices();

    if (this.mesh) this.scene.add(this.mesh);
    if (this.plannedMesh) this.scene.add(this.plannedMesh);
  }

  _buildMesh(intervals, planned) {
    if (intervals.length === 0) return null;

    // Unit-radius, unit-height cylinder along Y. Per-instance scale sets the
    // segment length; X/Z scale stays at DRILL_TUBE_RADIUS for every instance
    // so the whole hole reads as one continuous pipe of constant diameter.
    // radialSegments = 16 (was 8) removes the faceted silhouette at
    // inspection zoom; the side normals are smooth by construction, and the
    // flat end caps sit perpendicular to the segment axis so adjacent
    // intervals meet flush.
    const geometry = new THREE.CylinderGeometry(
      1.0, 1.0, 1.0, DRILL_TUBE_RADIAL_SEGMENTS, 1, false
    );

    // Per-instance grade, consumed on the GPU (see material.onBeforeCompile
    // below) so the cutoff slider never has to touch CPU-side matrices --
    // moving the cutoff only updates a single shader uniform, independent
    // of interval count, for filtering that stays at render framerate no
    // matter how many holes/intervals are loaded.
    const gradeArray = new Float32Array(intervals.length);
    for (let i = 0; i < intervals.length; i++) {
      gradeArray[i] = Number(intervals[i].grade_value);
    }
    geometry.setAttribute('aGrade', new THREE.InstancedBufferAttribute(gradeArray, 1));

    const material = new THREE.MeshStandardMaterial({
      roughness: 0.38,
      metalness: 0.08,
      flatShading: false,
      transparent: planned,
      opacity: planned ? PLANNED_OPACITY : 1.0,
      depthWrite: !planned
    });
    material.onBeforeCompile = (shader) => {
      shader.uniforms.uCutoff = { value: this.currentCutoff };

      shader.vertexShader = shader.vertexShader
        .replace(
          '#include <common>',
          `attribute float aGrade;\nvarying float vGrade;\n#include <common>`
        )
        .replace(
          '#include <begin_vertex>',
          `#include <begin_vertex>\nvGrade = aGrade;`
        );

      shader.fragmentShader = shader.fragmentShader
        .replace(
          '#include <common>',
          `uniform float uCutoff;\nvarying float vGrade;\n#include <common>`
        )
        .replace(
          '#include <clipping_planes_fragment>',
          `#include <clipping_planes_fragment>\nif (vGrade < uCutoff) discard;`
        );

      material.userData.shader = shader;
    };
    // Force WebGL program recompilation once so onBeforeCompile actually
    // runs before the first setGradeCutoff() call needs shader.uniforms.
    // The key differs per status so the two materials get separate programs.
    material.customProgramCacheKey = () =>
      planned ? 'assay-cutoff-shader-planned' : 'assay-cutoff-shader';

    const mesh = new THREE.InstancedMesh(geometry, material, intervals.length);
    mesh.name = planned ? 'assay-intervals-planned' : 'assay-intervals-instanced';
    if (planned) mesh.renderOrder = 2;

    // Store references on the mesh for selection raycasting
    mesh.userData = {
      type: 'assay_intervals',
      hole_status: planned ? 'planned' : 'drilled',
      intervals
    };

    return mesh;
  }

  updateMeshMatrices() {
    this._updateMatricesFor(this.mesh, this.intervalsData);
    this._updateMatricesFor(this.plannedMesh, this.plannedIntervalsData);
  }

  _updateMatricesFor(mesh, intervals) {
    if (!mesh) return;

    const position = new THREE.Vector3();
    const quaternion = new THREE.Quaternion();
    const scale = new THREE.Vector3();
    const matrix = new THREE.Matrix4();
    const alignVector = new THREE.Vector3(0, 1, 0); // Y-axis is cylinder's axis

    for (let i = 0; i < intervals.length; i++) {
      const data = intervals[i];
      const effectiveColor = (data.qaqc_flag && QAQC_COLORS[data.qaqc_flag]) || data.color;
      const colorObj = new THREE.Color(effectiveColor);

      // Direction along the local tangent of the trace for this sub-segment.
      const direction = new THREE.Vector3().subVectors(data.end, data.start);
      const length = direction.length();

      // Midpoint
      position.addVectors(data.start, data.end).multiplyScalar(0.5);

      // Rotation: align the cylinder's Y axis with the segment direction, so
      // the tube runs along the trajectory and its caps stay perpendicular
      // to it.
      if (length > 0) {
        const dirNormalized = direction.clone().normalize();
        quaternion.setFromUnitVectors(alignVector, dirNormalized);
      } else {
        quaternion.identity();
      }

      // Grade cutoff is applied on the GPU via the uCutoff/aGrade shader
      // uniform+attribute (fragment discard), not here -- only LOD
      // visibility (which changes rarely, on camera movement) still
      // touches the CPU-side instance matrix.
      const hiddenByLod = this.lodStates ? this.lodStates.get(data.collar_id) === false : false;
      if (hiddenByLod || length <= 0) {
        scale.set(0, 0, 0);
      } else {
        // Uniform radius for every interval: grade is communicated by colour
        // alone. Varying the radius per grade bucket (the previous
        // behaviour) made adjacent intervals meet at mismatched diameters,
        // which is what produced the stepped, blocky joints along the hole.
        scale.set(DRILL_TUBE_RADIUS, length, DRILL_TUBE_RADIUS);
      }

      matrix.compose(position, quaternion, scale);
      mesh.setMatrixAt(i, matrix);
      mesh.setColorAt(i, colorObj);
    }

    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.computeBoundingSphere();
  }

  setGradeCutoff(cutoffValue) {
    this.currentCutoff = Number(cutoffValue);
    for (const mesh of [this.mesh, this.plannedMesh]) {
      if (mesh && mesh.material.userData.shader) {
        // GPU-side update only -- no per-instance CPU work, so this stays
        // instant (same-frame) regardless of how many intervals are loaded.
        mesh.material.userData.shader.uniforms.uCutoff.value = this.currentCutoff;
      }
    }
  }

  setLodStates(lodStates) {
    this.lodStates = lodStates;
    this.updateMeshMatrices();
  }

  // Visibility hook for the "Planned Boreholes" layer toggle.
  setPlannedVisible(visible) {
    if (this.plannedMesh) this.plannedMesh.visible = visible;
  }

  clear() {
    for (const mesh of [this.mesh, this.plannedMesh]) {
      if (!mesh) continue;
      this.scene.remove(mesh);
      if (mesh.geometry) mesh.geometry.dispose();
      if (mesh.material) mesh.material.dispose();
    }
    this.mesh = null;
    this.plannedMesh = null;
    this.intervalsData = [];
    this.plannedIntervalsData = [];
  }
}

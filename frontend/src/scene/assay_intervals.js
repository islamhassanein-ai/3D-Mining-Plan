import * as THREE from 'three';
import { getGradeBucketIndex, DRILL_RADIUS_BY_BUCKET } from './grade_scale.js';

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

export class AssayIntervals {
  constructor(scene) {
    this.scene = scene;
    this.mesh = null;
    this.intervalsData = [];
    this.currentCutoff = 0.0;
    this.lodStates = null; // Map<collar_id, boolean> from LodManager; null = LOD inactive
  }

  render(drillholes) {
    this.clear();

    // 1. Collect all assay intervals
    this.intervalsData = [];
    for (const dh of drillholes) {
      for (const assay of dh.assays) {
        this.intervalsData.push({
          id: assay.id,
          hole_id: dh.hole_id,
          collar_id: dh.collar_id,
          from_depth: assay.from_depth,
          to_depth: assay.to_depth,
          grade_value: assay.grade_value,
          grade_unit: assay.grade_unit,
          color: assay.color,
          qaqc_flag: assay.qaqc_flag || null,
          start: new THREE.Vector3(assay.start_pos[0], assay.start_pos[2], assay.start_pos[1]),
          end: new THREE.Vector3(assay.end_pos[0], assay.end_pos[2], assay.end_pos[1])
        });
      }
    }

    if (this.intervalsData.length === 0) return;

    // 2. Create InstancedMesh
    // Unit-radius cylinder along Y axis; per-instance X/Z scale drives the
    // actual radius so grade buckets can render at different thicknesses
    // (see updateMeshMatrices -- higher grade renders visibly thicker).
    const geometry = new THREE.CylinderGeometry(1.0, 1.0, 1.0, 8);

    // Per-instance grade, consumed on the GPU (see material.onBeforeCompile
    // below) so the cutoff slider never has to touch CPU-side matrices --
    // moving the cutoff only updates a single shader uniform, independent
    // of interval count, for filtering that stays at render framerate no
    // matter how many holes/intervals are loaded.
    const gradeArray = new Float32Array(this.intervalsData.length);
    for (let i = 0; i < this.intervalsData.length; i++) {
      gradeArray[i] = this.intervalsData[i].grade_value;
    }
    geometry.setAttribute('aGrade', new THREE.InstancedBufferAttribute(gradeArray, 1));

    const material = new THREE.MeshStandardMaterial({
      roughness: 0.4,
      metalness: 0.1
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
    material.customProgramCacheKey = () => 'assay-cutoff-shader';

    this.mesh = new THREE.InstancedMesh(geometry, material, this.intervalsData.length);
    this.mesh.name = 'assay-intervals-instanced';

    // Store references on the mesh for selection raycasting
    this.mesh.userData = {
      type: 'assay_intervals',
      intervals: this.intervalsData
    };

    // Calculate matrices and colors
    this.updateMeshMatrices();

    this.scene.add(this.mesh);
  }

  updateMeshMatrices() {
    if (!this.mesh) return;

    const position = new THREE.Vector3();
    const quaternion = new THREE.Quaternion();
    const scale = new THREE.Vector3();
    const matrix = new THREE.Matrix4();
    const alignVector = new THREE.Vector3(0, 1, 0); // Y-axis is cylinder's axis

    for (let i = 0; i < this.intervalsData.length; i++) {
      const data = this.intervalsData[i];
      const effectiveColor = (data.qaqc_flag && QAQC_COLORS[data.qaqc_flag]) || data.color;
      const colorObj = new THREE.Color(effectiveColor);

      // Calculate length and direction
      const direction = new THREE.Vector3().subVectors(data.end, data.start);
      const length = direction.length();

      // Midpoint
      position.addVectors(data.start, data.end).multiplyScalar(0.5);

      // Rotation
      if (length > 0) {
        const dirNormalized = direction.clone().normalize();
        quaternion.setFromUnitVectors(alignVector, dirNormalized);
      } else {
        quaternion.setIdentity();
      }

      // Grade cutoff is applied on the GPU via the uCutoff/aGrade shader
      // uniform+attribute (fragment discard), not here -- only LOD
      // visibility (which changes rarely, on camera movement) still
      // touches the CPU-side instance matrix.
      const hiddenByLod = this.lodStates ? this.lodStates.get(data.collar_id) === false : false;
      if (hiddenByLod) {
        scale.set(0, 0, 0);
      } else {
        // Radius scales with grade bucket so higher-grade intervals render
        // visibly thicker along the drill core, per the reference viewer's
        // thickness-as-grade-cue convention.
        const bucketIdx = getGradeBucketIndex(data.grade_value, data.grade_unit);
        const radius = DRILL_RADIUS_BY_BUCKET[bucketIdx];
        scale.set(radius, length, radius);
      }

      matrix.compose(position, quaternion, scale);
      this.mesh.setMatrixAt(i, matrix);
      this.mesh.setColorAt(i, colorObj);
    }

    this.mesh.instanceMatrix.needsUpdate = true;
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true;
  }

  setGradeCutoff(cutoffValue) {
    this.currentCutoff = Number(cutoffValue);
    if (this.mesh && this.mesh.material.userData.shader) {
      // GPU-side update only -- no per-instance CPU work, so this stays
      // instant (same-frame) regardless of how many intervals are loaded.
      this.mesh.material.userData.shader.uniforms.uCutoff.value = this.currentCutoff;
    }
  }

  setLodStates(lodStates) {
    this.lodStates = lodStates;
    this.updateMeshMatrices();
  }

  clear() {
    if (this.mesh) {
      this.scene.remove(this.mesh);
      if (this.mesh.geometry) this.mesh.geometry.dispose();
      if (this.mesh.material) this.mesh.material.dispose();
      this.mesh = null;
    }
    this.intervalsData = [];
  }
}

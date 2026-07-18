import * as THREE from 'three';

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
    // Cylinder geometry along Y axis, unit height, 0.3 radius
    const radius = 0.25;
    const geometry = new THREE.CylinderGeometry(radius, radius, 1.0, 8);
    // Move geometry origin to bottom so positioning is easier, or leave at center
    // Let's keep it centered which matches compose(mid, quaternion, scale)
    const material = new THREE.MeshStandardMaterial({
      roughness: 0.4,
      metalness: 0.1
    });

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

      // Hide the instance if it's below the grade cutoff, or if LOD has
      // determined its drillhole is far from the camera (rendered as a
      // simplified trace line instead, per research.md Decision 4).
      const hiddenByCutoff = data.grade_value < this.currentCutoff;
      const hiddenByLod = this.lodStates ? this.lodStates.get(data.collar_id) === false : false;
      if (hiddenByCutoff || hiddenByLod) {
        scale.set(0, 0, 0);
      } else {
        scale.set(1.0, length, 1.0); // Scale Y by length, X & Z stay default
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
    this.updateMeshMatrices();
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

import * as THREE from 'three';

const LITHOLOGY_COLORS = {
  SND: '#fef08a', // Yellow (Sandstone/Sand)
  LST: '#a5f3fc', // Cyan (Limestone)
  QRT: '#fbcfe8', // Pink (Quartzite)
  SHL: '#d97706', // Brown (Shale)
  GRN: '#86efac', // Green (Granite)
  BAS: '#4b5563', // Dark Gray (Basalt)
  CLY: '#f59e0b', // Amber (Clay)
};

export function getLithologyColor(code) {
  const normalized = code.trim().toUpperCase();
  if (LITHOLOGY_COLORS[normalized]) {
    return LITHOLOGY_COLORS[normalized];
  }
  
  // Hash fallback to generate a consistent color for unknown lithologies
  let hash = 0;
  for (let i = 0; i < normalized.length; i++) {
    hash = normalized.charCodeAt(i) + ((hash << 5) - hash);
  }
  const c = (hash & 0x00FFFFFF).toString(16).toUpperCase();
  return '#' + '00000'.substring(0, 6 - c.length) + c;
}

export class LithologyIntervals {
  constructor(scene) {
    this.scene = scene;
    this.mesh = null;
    this.intervalsData = [];
    this.lodStates = null; // Map<collar_id, boolean> from LodManager; null = LOD inactive
  }

  render(drillholes) {
    this.clear();

    this.intervalsData = [];
    for (const dh of drillholes) {
      for (const lith of dh.lithologies) {
        this.intervalsData.push({
          id: lith.id,
          hole_id: dh.hole_id,
          collar_id: dh.collar_id,
          from_depth: lith.from_depth,
          to_depth: lith.to_depth,
          lith_code: lith.lith_code,
          rqd_percent: lith.rqd_percent,
          core_recovery_percent: lith.core_recovery_percent,
          color: getLithologyColor(lith.lith_code),
          start: new THREE.Vector3(lith.start_pos[0], lith.start_pos[2], lith.start_pos[1]),
          end: new THREE.Vector3(lith.end_pos[0], lith.end_pos[2], lith.end_pos[1])
        });
      }
    }

    if (this.intervalsData.length === 0) return;

    // Radius slightly larger than assay to prevent z-fighting if they overlap,
    // e.g. 0.26 vs 0.25, or we can keep them the same. Let's make it 0.26.
    const radius = 0.26;
    const geometry = new THREE.CylinderGeometry(radius, radius, 1.0, 8);
    const material = new THREE.MeshStandardMaterial({
      roughness: 0.5,
      metalness: 0.0
    });

    this.mesh = new THREE.InstancedMesh(geometry, material, this.intervalsData.length);
    this.mesh.name = 'lithology-intervals-instanced';

    this.mesh.userData = {
      type: 'lithology_intervals',
      intervals: this.intervalsData
    };

    this.updateMeshMatrices();

    this.scene.add(this.mesh);
  }

  updateMeshMatrices() {
    if (!this.mesh) return;

    const position = new THREE.Vector3();
    const quaternion = new THREE.Quaternion();
    const scale = new THREE.Vector3();
    const matrix = new THREE.Matrix4();
    const alignVector = new THREE.Vector3(0, 1, 0);

    for (let i = 0; i < this.intervalsData.length; i++) {
      const data = this.intervalsData[i];
      const colorObj = new THREE.Color(data.color);

      const direction = new THREE.Vector3().subVectors(data.end, data.start);
      const length = direction.length();

      position.addVectors(data.start, data.end).multiplyScalar(0.5);

      if (length > 0) {
        const dirNormalized = direction.clone().normalize();
        quaternion.setFromUnitVectors(alignVector, dirNormalized);
      } else {
        quaternion.setIdentity();
      }

      // Hidden when LOD has determined its drillhole is far from the camera
      // (rendered as a simplified trace line instead, per research.md
      // Decision 4).
      const hiddenByLod = this.lodStates ? this.lodStates.get(data.collar_id) === false : false;
      if (hiddenByLod) {
        scale.set(0, 0, 0);
      } else {
        scale.set(1.0, length, 1.0);
      }

      matrix.compose(position, quaternion, scale);
      this.mesh.setMatrixAt(i, matrix);
      this.mesh.setColorAt(i, colorObj);
    }

    this.mesh.instanceMatrix.needsUpdate = true;
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true;
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

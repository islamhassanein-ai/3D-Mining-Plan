import * as THREE from 'three';

import { GRADE_BUCKETS, getGradeBucketIndex, TRENCH_RADIUS_BY_BUCKET } from './grade_scale.js';

// Six-bucket Au grade scale matching the backend (backend/src/services/grade_coloring.py)
function getTrenchGradeColor(grade) {
  if (grade === null || grade === undefined) return GRADE_BUCKETS[0].color;
  return GRADE_BUCKETS[getGradeBucketIndex(grade)].color;
}

export class TrenchesRenderer {
  constructor(scene) {
    this.scene = scene;
    this.mesh = null;
    this.group = new THREE.Group();
    this.group.name = 'trench-markers';
    this.scene.add(this.group);
  }

  render(trenches, drillholes) {
    this.clear();
    if (!trenches || trenches.length === 0) return;

    // Determine baseline elevation for trenches (average collar elevation)
    let baselineElevation = 0.0;
    if (drillholes && drillholes.length > 0) {
      const sum = drillholes.reduce((s, dh) => s + dh.elevation, 0);
      baselineElevation = sum / drillholes.length;
    }

    // Unit-radius sphere; per-instance scale drives actual radius so
    // higher-grade trench samples render visibly larger (matching the
    // drill-interval thickness-as-grade-cue convention).
    const sphereGeom = new THREE.SphereGeometry(1.0, 8, 8);
    const material = new THREE.MeshStandardMaterial({ roughness: 0.5, metalness: 0.1 });

    this.mesh = new THREE.InstancedMesh(sphereGeom, material, trenches.length);
    this.mesh.name = 'trenches-instanced';

    const position = new THREE.Vector3();
    const quaternion = new THREE.Quaternion();
    const scale = new THREE.Vector3(1, 1, 1);
    const matrix = new THREE.Matrix4();

    for (let i = 0; i < trenches.length; i++) {
      const t = trenches[i];
      // Map to Three.js Y-up (Easting -> X, Elevation -> Y, Northing -> Z)
      position.set(t.easting, baselineElevation, t.northing);

      const bucketIdx = getGradeBucketIndex(t.grade_value ?? 0);
      const radius = TRENCH_RADIUS_BY_BUCKET[bucketIdx];
      scale.set(radius, radius, radius);

      matrix.compose(position, quaternion, scale);
      this.mesh.setMatrixAt(i, matrix);

      const color = new THREE.Color(getTrenchGradeColor(t.grade_value));
      this.mesh.setColorAt(i, color);
    }

    this.mesh.instanceMatrix.needsUpdate = true;
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true;
    
    this.mesh.userData = {
      type: 'trenches',
      data: trenches
    };

    this.group.add(this.mesh);
  }

  clear() {
    if (this.mesh) {
      this.group.remove(this.mesh);
      if (this.mesh.geometry) this.mesh.geometry.dispose();
      if (this.mesh.material) this.mesh.material.dispose();
      this.mesh = null;
    }
  }
}

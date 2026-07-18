import * as THREE from 'three';

// Standard grade colors matching backend
function getTrenchGradeColor(grade) {
  if (grade === null || grade === undefined) return '#9ca3af'; // Gray
  if (grade < 0.1) return '#9ca3af';
  if (grade < 0.5) return '#34d399';
  if (grade < 1.0) return '#60a5fa';
  if (grade < 5.0) return '#fbbf24';
  return '#f87171';
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

    const sphereGeom = new THREE.SphereGeometry(1.5, 8, 8);
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

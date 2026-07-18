import * as THREE from 'three';

export class DrillholeTraces {
  constructor(scene) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.name = 'drillhole-traces';
    this.scene.add(this.group);
    
    // Map to store trace meshes: collar_id -> line mesh
    this.tracesMap = new Map();
  }

  render(drillholes) {
    this.clear();

    const material = new THREE.LineBasicMaterial({
      color: 0x9ca3af, // gray trace lines
      linewidth: 2,    // only works on some platforms, standard is 1
      transparent: true,
      opacity: 0.8
    });

    for (const dh of drillholes) {
      const points = [];
      for (const p of dh.trace) {
        // Map Easting -> X, Elevation -> Y, Northing -> Z (Y-up convention)
        points.push(new THREE.Vector3(p.x, p.z, p.y));
      }

      if (points.length < 2) continue;

      const geometry = new THREE.BufferGeometry().setFromPoints(points);
      const line = new THREE.Line(geometry, material);
      
      // Store reference data on the mesh for click selection
      line.userData = {
        collar_id: dh.collar_id,
        hole_id: dh.hole_id,
        type: 'drillhole_trace'
      };

      this.group.add(line);
      this.tracesMap.set(dh.collar_id, line);
    }
  }

  clear() {
    // Traverse and dispose geometries
    this.group.traverse((child) => {
      if (child.isLine) {
        if (child.geometry) child.geometry.dispose();
      }
    });
    // Remove all children
    while (this.group.children.length > 0) {
      this.group.remove(this.group.children[0]);
    }
    this.tracesMap.clear();
  }
}

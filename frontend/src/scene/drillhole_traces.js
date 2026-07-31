import * as THREE from 'three';

export class DrillholeTraces {
  constructor(scene) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.name = 'drillhole-traces';
    this.scene.add(this.group);

    // Planned holes live in their own group so the layer panel can toggle
    // them independently of the drilled ones.
    this.plannedGroup = new THREE.Group();
    this.plannedGroup.name = 'drillhole-traces-planned';
    this.scene.add(this.plannedGroup);

    // Map to store trace meshes: collar_id -> line mesh
    this.tracesMap = new Map();

    this.materials = [];
  }

  render(drillholes) {
    this.clear();

    // Drilled holes: solid grey.
    const drilledMaterial = new THREE.LineBasicMaterial({
      color: 0x9ca3af, // gray trace lines
      linewidth: 2,    // only works on some platforms, standard is 1
      transparent: true,
      opacity: 0.8
    });

    // Planned holes: dashed and cooler-toned, so a proposed trajectory is
    // never mistaken for a hole that has actually been drilled. Dashes need
    // computeLineDistances() on the geometry (below) to show up at all.
    const plannedMaterial = new THREE.LineDashedMaterial({
      color: 0x67e8f9,
      linewidth: 2,
      transparent: true,
      opacity: 0.85,
      dashSize: 3.0,
      gapSize: 2.0
    });

    this.materials = [drilledMaterial, plannedMaterial];

    for (const dh of drillholes) {
      const points = [];
      for (const p of dh.trace) {
        // Map Easting -> X, Elevation -> Y, Northing -> Z (Y-up convention)
        points.push(new THREE.Vector3(p.x, p.z, p.y));
      }

      if (points.length < 2) continue;

      const isPlanned = dh.hole_status === 'planned';
      const geometry = new THREE.BufferGeometry().setFromPoints(points);
      const line = new THREE.Line(geometry, isPlanned ? plannedMaterial : drilledMaterial);
      if (isPlanned) line.computeLineDistances();

      // Store reference data on the mesh for click selection
      line.userData = {
        collar_id: dh.collar_id,
        hole_id: dh.hole_id,
        hole_status: isPlanned ? 'planned' : 'drilled',
        type: 'drillhole_trace'
      };

      (isPlanned ? this.plannedGroup : this.group).add(line);
      this.tracesMap.set(dh.collar_id, line);
    }
  }

  // Visibility hook for the "Planned Boreholes" layer toggle.
  setPlannedVisible(visible) {
    this.plannedGroup.visible = visible;
  }

  clear() {
    for (const group of [this.group, this.plannedGroup]) {
      // Traverse and dispose geometries
      group.traverse((child) => {
        if (child.isLine) {
          if (child.geometry) child.geometry.dispose();
        }
      });
      // Remove all children
      while (group.children.length > 0) {
        group.remove(group.children[0]);
      }
    }
    // Materials are shared across every line in a render pass, so they are
    // disposed once here rather than per-child in the traversal above.
    for (const material of this.materials) material.dispose();
    this.materials = [];
    this.tracesMap.clear();
  }
}

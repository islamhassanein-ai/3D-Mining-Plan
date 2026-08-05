import * as THREE from 'three';

// A planned hole is a proposal, not a result, and the two must never be
// confused at a glance. Two signals separate them, and each works on its own:
// shape at the collar, and line style down the trace.
//
//   drilled -- square collar, solid warm-ochre trace
//   planned -- round collar, dashed muted-teal trace
//
// Shape is the primary cue because it survives the colour-blind case and
// greyscale printing; the colours are the secondary one. Neither palette
// borrows from the grade buckets (grey/blue/green/yellow/red/magenta), so a
// collar marker can never be misread as a measured grade -- the mistake a
// *planned* hole must never invite.
const DRILLED_COLLAR_COLOR = 0xc49a6c;  // sand tan
const DRILLED_TRACE_COLOR = 0x9b6b43;   // warm ochre brown
const PLANNED_COLLAR_COLOR = 0x78b7b7;  // muted teal
const PLANNED_TRACE_COLOR = 0x78b7b7;

// A slightly larger back-face-only copy behind each marker, which silhouettes
// it against pale terrain without needing a second render pass.
const COLLAR_RIM_COLOR = 0x0f172a;
const COLLAR_RIM_SCALE = 1.28;

// Collar marker half-size in metres. Small enough not to swallow its
// neighbours on a tight pattern, large enough to spot from the default
// framing. The square uses the same figure so the two read as one family.
const COLLAR_RADIUS = 1.0;

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

    // Drilled holes: solid warm ochre.
    const drilledMaterial = new THREE.LineBasicMaterial({
      color: DRILLED_TRACE_COLOR,
      linewidth: 2,    // only works on some platforms, standard is 1
      transparent: true,
      opacity: 0.9
    });

    // Planned holes: dashed teal trace. Dashes need computeLineDistances()
    // on the geometry (below) to show up at all.
    const plannedMaterial = new THREE.LineDashedMaterial({
      color: PLANNED_TRACE_COLOR,
      linewidth: 2,
      dashSize: 3.0,
      gapSize: 2.0
    });
    const drilledCollarMaterial = new THREE.MeshBasicMaterial({
      color: DRILLED_COLLAR_COLOR
    });
    const plannedCollarMaterial = new THREE.MeshBasicMaterial({
      color: PLANNED_COLLAR_COLOR
    });
    const collarRimMaterial = new THREE.MeshBasicMaterial({
      color: COLLAR_RIM_COLOR,
      side: THREE.BackSide
    });

    this.materials = [
      drilledMaterial, plannedMaterial,
      drilledCollarMaterial, plannedCollarMaterial, collarRimMaterial
    ];

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

      const target = isPlanned ? this.plannedGroup : this.group;

      line.renderOrder = 1;

      const markerData = {
        collar_id: dh.collar_id,
        hole_id: dh.hole_id,
        hole_status: isPlanned ? 'planned' : 'drilled',
        type: 'drillhole_trace'
      };

      // Round collar for planned, square for drilled. The cube reads as a
      // square from the plan-view framing the scene opens on, and still as a
      // distinctly non-round block from any oblique angle.
      const markerGeometry = isPlanned
        ? new THREE.SphereGeometry(COLLAR_RADIUS, 16, 12)
        : new THREE.BoxGeometry(COLLAR_RADIUS * 2, COLLAR_RADIUS * 2, COLLAR_RADIUS * 2);

      const rim = new THREE.Mesh(
        markerGeometry.clone().scale(COLLAR_RIM_SCALE, COLLAR_RIM_SCALE, COLLAR_RIM_SCALE),
        collarRimMaterial
      );
      rim.position.copy(points[0]);
      rim.renderOrder = 2;
      // Decorative only: it must not intercept picking, and it must not widen
      // the camera fit beyond the marker it silhouettes.
      rim.raycast = () => {};
      rim.userData = { ...markerData, excludeFromFit: true };
      target.add(rim);

      const collar = new THREE.Mesh(
        markerGeometry,
        isPlanned ? plannedCollarMaterial : drilledCollarMaterial
      );
      collar.position.copy(points[0]);
      collar.renderOrder = 3;
      collar.userData = markerData;
      target.add(collar);

      target.add(line);
      this.tracesMap.set(dh.collar_id, line);
    }
  }

  // Visibility hook for the "Planned Boreholes" layer toggle.
  setPlannedVisible(visible) {
    this.plannedGroup.visible = visible;
  }

  clear() {
    for (const group of [this.group, this.plannedGroup]) {
      // Traverse and dispose geometries (lines, halo clones, collar spheres)
      group.traverse((child) => {
        if (child.geometry) child.geometry.dispose();
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

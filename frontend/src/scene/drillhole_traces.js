import * as THREE from 'three';

// A planned hole is a proposal, not a result, and the two must never be
// confused at a glance. The signal is a ball sitting on the collar --
// the only sphere in the scene -- with a near-black dashed trace beneath it.
//
// The ball is white, not red. Red was too close to the 1.00-3.00 g/t bucket
// (#f5222d): a red marker on a trace whose samples are also red reads as a
// grade result, which is the one thing a *planned* hole must never look like.
// White is the only high-contrast colour the data palette never uses -- the
// six grade buckets run grey/blue/green/yellow/red/magenta and the terrain
// ramp is brown-to-teal -- so it cannot be misread as a measurement. The dark
// rim below keeps it readable on the light themes too.
const PLANNED_COLLAR_COLOR = 0xffffff;
const PLANNED_COLLAR_RIM_COLOR = 0x0f172a;
const PLANNED_TRACE_COLOR = 0x0a0a0a;

// Pure black would vanish against the #0b0f19 viewport, so the dash is drawn
// twice: an unlit near-black core over a slightly wider, faint light halo.
// The pair reads as "a black dashed line" while staying legible on the dark
// background, and the halo also keeps it visible where the trace crosses the
// dark underside of the topography surface.
const PLANNED_HALO_COLOR = 0xc8d2e0;

// Collar sphere radius in metres. Small enough not to swallow nearby drilled
// collars on a tight pattern, large enough to spot from the default framing.
const PLANNED_COLLAR_RADIUS = 1.0;

// The rim is a slightly larger back-face-only sphere behind the marker, which
// silhouettes it against a pale background without needing a second pass.
const PLANNED_COLLAR_RIM_SCALE = 1.28;

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

    // Planned holes: black dashed trace. Dashes need computeLineDistances()
    // on the geometry (below) to show up at all.
    const plannedMaterial = new THREE.LineDashedMaterial({
      color: PLANNED_TRACE_COLOR,
      linewidth: 2,
      dashSize: 3.0,
      gapSize: 2.0
    });
    // Drawn first and slightly out of phase so it peeks out around the black
    // core rather than being hidden underneath it.
    const plannedHaloMaterial = new THREE.LineDashedMaterial({
      color: PLANNED_HALO_COLOR,
      transparent: true,
      opacity: 0.45,
      dashSize: 3.6,
      gapSize: 1.4
    });
    const plannedCollarMaterial = new THREE.MeshBasicMaterial({
      color: PLANNED_COLLAR_COLOR
    });
    const plannedCollarRimMaterial = new THREE.MeshBasicMaterial({
      color: PLANNED_COLLAR_RIM_COLOR,
      side: THREE.BackSide
    });

    this.materials = [
      drilledMaterial, plannedMaterial, plannedHaloMaterial,
      plannedCollarMaterial, plannedCollarRimMaterial
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

      if (isPlanned) {
        const halo = new THREE.Line(geometry.clone(), plannedHaloMaterial);
        halo.computeLineDistances();
        halo.renderOrder = 0;
        // Purely decorative: it must not intercept picking, and it must not
        // widen the camera fit beyond the trace it traces.
        halo.raycast = () => {};
        halo.userData = { excludeFromFit: true };
        target.add(halo);
        line.renderOrder = 1;

        const markerData = {
          collar_id: dh.collar_id,
          hole_id: dh.hole_id,
          hole_status: 'planned',
          type: 'drillhole_trace'
        };

        const rim = new THREE.Mesh(
          new THREE.SphereGeometry(PLANNED_COLLAR_RADIUS * PLANNED_COLLAR_RIM_SCALE, 16, 12),
          plannedCollarRimMaterial
        );
        rim.position.copy(points[0]);
        rim.renderOrder = 2;
        rim.userData = { ...markerData, excludeFromFit: true };
        target.add(rim);

        const collar = new THREE.Mesh(
          new THREE.SphereGeometry(PLANNED_COLLAR_RADIUS, 16, 12),
          plannedCollarMaterial
        );
        collar.position.copy(points[0]);
        collar.renderOrder = 3;
        collar.userData = markerData;
        target.add(collar);
      }

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

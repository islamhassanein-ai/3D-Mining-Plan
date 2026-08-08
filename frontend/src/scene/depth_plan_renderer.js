import * as THREE from 'three';
import { makeLabelSprite, updateBillboardScale } from './label_sprite.js';
import {
  planeNormal, holeDirection, toVec, strikeVector, downDipVector
} from '../services/depth_planner.js';

// The picture that goes with the Depth Planner: a proposed hole punching
// through a dipping zone, with the intersection depths called out on the trace.
//
// Everything here is a PROPOSAL, not a measurement, and it has to read that way
// at a glance -- otherwise a planned intersection sitting next to real assay
// intervals is indistinguishable from a result. Hence dashed lines, translucent
// surfaces, and the cyan that drillhole_traces.js already reserves for planned
// holes.
//
// Coordinate mapping: the planner works in (e, n, u); three.js is X = Easting,
// Y = Elevation, Z = Northing. `toThree()` is the only place that conversion
// happens.

const ZONE_COLOR = 0xdc2626;      // the red zone slab
const PLANNED_COLOR = 0x78b7b7;   // matches the planned-borehole layer
const MARKER_COLOR = 0xf97316;    // depth call-outs
const ENVELOPE_COLOR = 0xfbbf24;  // uncertainty sleeve

/** (e, n, u) -> three.js (X = E, Y = Up, Z = N). */
function toThree(v) {
  return new THREE.Vector3(v.e, v.u, v.n);
}

export class DepthPlanRenderer {
  constructor(scene) {
    this.scene = scene;

    this.group = new THREE.Group();
    this.group.name = 'depth-plan';
    this.scene.add(this.group);

    // Labels live in their own child group so the per-frame billboard resize
    // can walk just the sprites, the way BoreholeLabels does.
    this.labelGroup = new THREE.Group();
    this.labelGroup.name = 'depth-plan-labels';
    this.group.add(this.labelGroup);

    this.plan = null;
  }

  /**
   * @param plan  the object returned by depth_planner.computePlan(), plus
   *              `top`/`base` anchor records. Passing null clears the scene.
   */
  render(plan, options = {}) {
    this.clear();
    this.plan = plan;
    if (!plan || !plan.plane || !plan.collar) return;

    const collar = toVec(plan.collar);
    const dir = holeDirection(plan.hole.dip, plan.hole.azimuth);
    const nrm = planeNormal(plan.plane.dip, plan.plane.dipDirection);

    // How far the drawing extends. Scaled to the collar-to-zone distance so a
    // 60 m step-out and a 600 m one both frame sensibly.
    const reach = Math.abs(plan.top && plan.top.depth ? plan.top.depth : 100);
    const halfSize = options.slabSize ?? Math.max(60, reach * 1.2);

    this._buildZoneSlab(plan, nrm, halfSize);
    this._buildUncertaintyBand(plan, collar, dir);
    this._buildPatternHoles(plan, dir);
    this._buildPlannedHole(plan, collar, dir);
    this._buildDepthMarkers(plan, collar, dir);
  }

  /**
   * The rest of the programme: every other hole in the grid.
   *
   * Drawn thinner and dimmer than the reference hole, and with a dot at each
   * target rather than a labelled ring. A twelve-hole pattern with twelve sets
   * of call-outs is unreadable, and the individual depths are in the table --
   * what the 3D view has to show is the SHAPE of the programme: how the fan
   * spreads along strike and how far down-dip it steps.
   */
  _buildPatternHoles(plan, dir) {
    const pattern = plan.pattern;
    if (!pattern || !pattern.holes.length) return;

    const lineMaterial = new THREE.LineDashedMaterial({
      color: PLANNED_COLOR, dashSize: 2.5, gapSize: 2.5, transparent: true, opacity: 0.5
    });
    const badMaterial = new THREE.LineDashedMaterial({
      color: 0xef4444, dashSize: 2.5, gapSize: 2.5, transparent: true, opacity: 0.5
    });
    const targetMaterial = new THREE.MeshBasicMaterial({
      color: MARKER_COLOR, transparent: true, opacity: 0.85
    });

    for (const h of pattern.holes) {
      // The reference hole is drawn in full by _buildPlannedHole; drawing it
      // twice would double-darken one hole in the middle of the fan.
      if (h.col === (pattern.cols - 1) / 2 && h.row === 0) continue;

      const start = toThree({ e: h.collar.easting, n: h.collar.northing, u: h.collar.elevation });
      const end = toThree({
        e: h.collar.easting + dir.e * h.eoh,
        n: h.collar.northing + dir.n * h.eoh,
        u: h.collar.elevation + dir.u * h.eoh
      });

      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([start, end]),
        h.ok ? lineMaterial : badMaterial
      );
      line.computeLineDistances();
      line.userData = { type: 'depth_plan_pattern', hole_id: h.id, eoh: h.eoh };
      this.group.add(line);

      const dot = new THREE.Mesh(new THREE.SphereGeometry(1.1, 10, 8), targetMaterial);
      dot.position.copy(toThree(h.target));
      dot.userData = { type: 'depth_plan_pattern_target', hole_id: h.id };
      this.group.add(dot);
    }
  }

  /**
   * The zone as a closed slab between two parallel planes: the surface through
   * the top anchor and the one through the base anchor. Drawing it as a solid
   * -- rather than two loose sheets -- is what makes the hole visibly enter and
   * exit something with thickness.
   */
  _buildZoneSlab(plan, nrm, halfSize) {
    if (!plan.top || !plan.top.point) return;

    const anchorTop = toVec(plan.topAnchor || plan.collar);
    if (!plan.topAnchor) return;

    const { dip, dipDirection } = plan.plane;
    const s = strikeVector(dipDirection);
    const d = downDipVector(dip, dipDirection);

    // Offset from the top plane to the base plane, measured along the normal.
    let offset = 0;
    if (plan.baseAnchor) {
      const b = toVec(plan.baseAnchor);
      offset = (b.e - anchorTop.e) * nrm.e
             + (b.n - anchorTop.n) * nrm.n
             + (b.u - anchorTop.u) * nrm.u;
    }

    // Centre the sheet on the intersection point rather than the trench
    // anchor, so the slab stays around the hole instead of trailing off toward
    // the outcrop.
    const hit = plan.top.point;
    const centre = {
      e: (hit.e + anchorTop.e) / 2,
      n: (hit.n + anchorTop.n) / 2,
      u: (hit.u + anchorTop.u) / 2
    };

    const corner = (su, dv, push) => ({
      e: centre.e + s.e * su + d.e * dv + nrm.e * push,
      n: centre.n + s.n * su + d.n * dv + nrm.n * push,
      u: centre.u + s.u * su + d.u * dv + nrm.u * push
    });

    const combos = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
    const topFace = combos.map(([a, b]) => corner(a * halfSize, b * halfSize, 0));
    const baseFace = combos.map(([a, b]) => corner(a * halfSize, b * halfSize, offset));

    // Two translucent sheets plus the four sides, so the slab is closed and
    // reads as a volume from any angle.
    const positions = [];
    const pushTri = (p, q, r) => {
      for (const v of [p, q, r]) positions.push(v.e, v.u, v.n);
    };
    const pushQuad = (a, b, c, d2) => { pushTri(a, b, c); pushTri(a, c, d2); };

    pushQuad(topFace[0], topFace[1], topFace[2], topFace[3]);
    pushQuad(baseFace[3], baseFace[2], baseFace[1], baseFace[0]);
    for (let i = 0; i < 4; i++) {
      const j = (i + 1) % 4;
      pushQuad(topFace[i], baseFace[i], baseFace[j], topFace[j]);
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.computeVertexNormals();
    geometry.computeBoundingSphere();

    const material = new THREE.MeshStandardMaterial({
      color: ZONE_COLOR,
      transparent: true,
      opacity: 0.28,
      side: THREE.DoubleSide,
      depthWrite: false,
      roughness: 0.6,
      metalness: 0.0
    });

    const mesh = new THREE.Mesh(geometry, material);
    // The slab is sized for legibility, not surveyed -- letting it drive the
    // camera fit would frame the project around an arbitrary drawing choice.
    // scene_loader.js:visibleBounds() honours this flag.
    mesh.userData.excludeFromFit = true;
    mesh.userData.type = 'depth_plan_zone';
    mesh.renderOrder = 1;
    this.group.add(mesh);

    // Bright outlines on both bounding surfaces: without them the slab is a
    // wash of colour with no readable orientation.
    for (const face of [topFace, baseFace]) {
      const pts = [...face, face[0]].map(toThree);
      const edge = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(pts),
        new THREE.LineBasicMaterial({ color: ZONE_COLOR, transparent: true, opacity: 0.9 })
      );
      edge.userData.excludeFromFit = true;
      this.group.add(edge);
    }
  }

  /**
   * The pessimistic-to-optimistic depth range, drawn as a fat translucent
   * sleeve on the hole. This is the part a driller actually reads: "the zone is
   * somewhere in here".
   */
  _buildUncertaintyBand(plan, collar, dir) {
    const env = plan.envelope;
    if (!env || !Number.isFinite(env.min) || !Number.isFinite(env.max)) return;

    const from = Math.max(0, env.min);
    const to = env.max;
    if (to - from < 1e-3) return;

    const mesh = this._cylinderAlong(collar, dir, from, to, 2.4, new THREE.MeshStandardMaterial({
      color: ENVELOPE_COLOR,
      transparent: true,
      opacity: 0.16,
      depthWrite: false,
      roughness: 0.9
    }));
    mesh.userData.type = 'depth_plan_envelope';
    mesh.userData.excludeFromFit = true;
    mesh.renderOrder = 2;
    this.group.add(mesh);
  }

  /** The proposed trajectory: dashed centreline plus a faint tube around it. */
  _buildPlannedHole(plan, collar, dir) {
    const eoh = plan.proposal ? plan.proposal.eoh : (plan.top.depth || 0) * 1.3;
    if (!Number.isFinite(eoh) || eoh <= 0) return;

    const start = toThree(collar);
    const end = toThree({
      e: collar.e + dir.e * eoh,
      n: collar.n + dir.n * eoh,
      u: collar.u + dir.u * eoh
    });

    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([start, end]),
      new THREE.LineDashedMaterial({
        color: PLANNED_COLOR, dashSize: 3, gapSize: 2, transparent: true, opacity: 0.95
      })
    );
    // Dashes are computed from vertex distances; without this the material
    // silently renders as a solid line.
    line.computeLineDistances();
    line.userData.type = 'depth_plan_hole';
    this.group.add(line);

    const tube = this._cylinderAlong(collar, dir, 0, eoh, 0.7, new THREE.MeshStandardMaterial({
      color: PLANNED_COLOR,
      transparent: true,
      opacity: 0.30,
      depthWrite: false,
      roughness: 0.4
    }));
    tube.userData.type = 'depth_plan_hole';
    this.group.add(tube);

    // Collar marker, matching the planned-hole collar sphere in
    // drillhole_traces.js so the two read as the same kind of object.
    const collarMark = new THREE.Mesh(
      new THREE.SphereGeometry(1.6, 16, 12),
      new THREE.MeshBasicMaterial({ color: PLANNED_COLOR })
    );
    collarMark.position.copy(start);
    this.group.add(collarMark);

    this._addLabel(start, `${plan.holeId || 'PLANNED'}  ${Math.round(plan.hole.azimuth)}°/${Math.round(Math.abs(plan.hole.dip))}°`, PLANNED_COLOR, 6);
  }

  /** A ring and a labelled pill at each depth worth calling out. */
  _buildDepthMarkers(plan, collar, dir) {
    const marks = [];
    if (plan.proposal && Number.isFinite(plan.proposal.startLogging)) {
      marks.push({ depth: plan.proposal.startLogging, text: `Start logging ${plan.proposal.startLogging} m`, color: 0x94a3b8 });
    }
    if (plan.top && Number.isFinite(plan.top.depth)) {
      marks.push({ depth: plan.top.depth, text: `Zone top ${plan.top.depth.toFixed(1)} m`, color: MARKER_COLOR });
    }
    if (plan.base && Number.isFinite(plan.base.depth)) {
      marks.push({ depth: plan.base.depth, text: `Zone base ${plan.base.depth.toFixed(1)} m`, color: MARKER_COLOR });
    }
    if (plan.proposal && Number.isFinite(plan.proposal.eoh)) {
      marks.push({ depth: plan.proposal.eoh, text: `EOH ${plan.proposal.eoh} m`, color: 0x94a3b8 });
    }

    for (const mark of marks) {
      if (mark.depth <= 0) continue;
      const at = {
        e: collar.e + dir.e * mark.depth,
        n: collar.n + dir.n * mark.depth,
        u: collar.u + dir.u * mark.depth
      };
      const pos = toThree(at);

      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(2.0, 0.35, 10, 28),
        new THREE.MeshBasicMaterial({ color: mark.color })
      );
      ring.position.copy(pos);
      // Stand the ring perpendicular to the hole, so it reads as a depth tick
      // around the core rather than a disc floating beside it.
      ring.quaternion.setFromUnitVectors(
        new THREE.Vector3(0, 0, 1),
        toThree(dir).normalize()
      );
      this.group.add(ring);

      this._addLabel(pos, mark.text, `#${mark.color.toString(16).padStart(6, '0')}`, 10);
    }
  }

  /**
   * A label pill offset from its anchor, with a leader line back to it.
   * Reuses makeLabelSprite so planner call-outs match hole and trench tags.
   */
  _addLabel(position, text, accent, offsetUp) {
    const accentColor = typeof accent === 'number'
      ? `#${accent.toString(16).padStart(6, '0')}`
      : accent;

    const sprite = makeLabelSprite(text, accentColor);
    const anchored = position.clone().add(new THREE.Vector3(0, offsetUp, 0));
    sprite.position.copy(anchored);
    sprite.userData.excludeFromFit = true;
    this.labelGroup.add(sprite);

    const leader = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([position, anchored]),
      new THREE.LineBasicMaterial({ color: accentColor, transparent: true, opacity: 0.55 })
    );
    leader.userData.excludeFromFit = true;
    this.group.add(leader);
  }

  /** A capped cylinder from `from` to `to` metres along the hole. */
  _cylinderAlong(collar, dir, from, to, radius, material) {
    const length = to - from;
    const geometry = new THREE.CylinderGeometry(radius, radius, length, 20, 1, false);
    const mesh = new THREE.Mesh(geometry, material);

    const mid = from + length / 2;
    mesh.position.copy(toThree({
      e: collar.e + dir.e * mid,
      n: collar.n + dir.n * mid,
      u: collar.u + dir.u * mid
    }));
    // CylinderGeometry runs along +Y; rotate that onto the hole direction.
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), toThree(dir).normalize());
    return mesh;
  }

  /** Per-frame billboard sizing, called from the scene render loop. */
  update(camera) {
    if (this.labelGroup.children.length) updateBillboardScale(this.labelGroup, camera);
  }

  setVisible(visible) {
    this.group.visible = visible;
  }

  clear() {
    const disposeIn = (root) => {
      root.traverse((child) => {
        if (child.geometry) child.geometry.dispose();
        if (child.material) {
          const mats = Array.isArray(child.material) ? child.material : [child.material];
          for (const m of mats) {
            if (m.map) m.map.dispose();
            m.dispose();
          }
        }
      });
    };

    disposeIn(this.labelGroup);
    while (this.labelGroup.children.length) this.labelGroup.remove(this.labelGroup.children[0]);

    for (let i = this.group.children.length - 1; i >= 0; i--) {
      const child = this.group.children[i];
      if (child === this.labelGroup) continue;
      disposeIn(child);
      this.group.remove(child);
    }

    this.plan = null;
  }
}

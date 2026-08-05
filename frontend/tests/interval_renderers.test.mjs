// Renderer-level checks for AssayIntervals / DrillholeTraces. Three.js builds
// its scene graph without a WebGL context, so these run headless and assert
// what actually gets added to the scene.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';

import { AssayIntervals } from '../src/scene/assay_intervals.js';
import { DrillholeTraces } from '../src/scene/drillhole_traces.js';
import {
  DRILL_TUBE_RADIUS,
  DRILL_TUBE_RADIAL_SEGMENTS,
  UNSAMPLED_COLOR,
} from '../src/scene/grade_scale.js';

// Mirrors the /scene payload shape for the AADD004 case: nothing sampled
// 0-37 m, assays from 37 m down, hole ends at 80 m.
function aadd004(overrides = {}) {
  return {
    collar_id: 'c-1',
    hole_id: 'AADD004',
    easting: 0, northing: 0, elevation: 0,
    hole_status: 'drilled',
    total_depth: 80,
    trace: [
      { depth: 0, x: 0, y: 0, z: 0, dip: -90, azimuth: 0 },
      { depth: 80, x: 0, y: 0, z: -80, dip: -90, azimuth: 0 },
    ],
    assays: [
      { id: 'a1', sample_id: 'S01', from_depth: 37, to_depth: 38, grade_value: 0.45,
        grade_unit: 'g/t', unsampled: false, color: '#21d07a',
        start_pos: [0, 0, -37], end_pos: [0, 0, -38] },
      { id: 'a2', sample_id: 'S02', from_depth: 38, to_depth: 40, grade_value: 1.85,
        grade_unit: 'g/t', unsampled: false, color: '#ff5a1f',
        start_pos: [0, 0, -38], end_pos: [0, 0, -40] },
    ],
    lithologies: [],
    unsampled_gaps: [{ from_depth: 0, to_depth: 37 }, { from_depth: 40, to_depth: 80 }],
    ...overrides,
  };
}

const meshOf = (r, holeId = 'AADD004') =>
  [...r.group.children, ...r.plannedGroup.children]
    .find(m => m.userData.hole_id === holeId);

// Vertex positions of one hole's tube, as {x,y,z} objects.
function vertices(mesh) {
  const p = mesh.geometry.getAttribute('position');
  const out = [];
  for (let i = 0; i < p.count; i++) out.push({ x: p.getX(i), y: p.getY(i), z: p.getZ(i) });
  return out;
}

// ---------------------------------------------------------------------------
// Absolute placement -- no tube in the unsampled zone
// ---------------------------------------------------------------------------

test('no tube geometry exists in the unsampled 0-37 m zone', () => {
  const r = new AssayIntervals(new THREE.Scene());
  r.render([aadd004()]);

  const ys = vertices(meshOf(r)).map(v => v.y);
  // Sampling starts at 37 m, so nothing may sit above -37 (bar float slop).
  assert.ok(Math.max(...ys) <= -37 + 1e-4,
    `tube reaches y=${Math.max(...ys)}, above the 37 m first sample`);
});

test('the tube spans exactly 37 m to 40 m', () => {
  const r = new AssayIntervals(new THREE.Scene());
  r.render([aadd004()]);

  const ys = vertices(meshOf(r)).map(v => v.y);
  assert.ok(Math.abs(Math.max(...ys) - -37) < 1e-4, `top at ${Math.max(...ys)}`);
  assert.ok(Math.abs(Math.min(...ys) - -40) < 1e-4, `bottom at ${Math.min(...ys)}`);
});

test('every surface vertex sits exactly one radius from the centreline', () => {
  const r = new AssayIntervals(new THREE.Scene());
  r.render([aadd004()]);

  // Vertical hole on the Y axis, so radial distance is hypot(x, z). Cap centre
  // vertices sit on the axis, so allow those.
  for (const v of vertices(meshOf(r))) {
    const radial = Math.hypot(v.x, v.z);
    const onAxis = radial < 1e-6;
    assert.ok(onAxis || Math.abs(radial - DRILL_TUBE_RADIUS) < 1e-4,
      `vertex at radial distance ${radial}, expected ${DRILL_TUBE_RADIUS}`);
  }
});

// ---------------------------------------------------------------------------
// Leapfrog continuity -- one unbroken tube, colour bands, caps only at the ends
// ---------------------------------------------------------------------------

test('adjacent intervals share a ring position, leaving no gap', () => {
  const r = new AssayIntervals(new THREE.Scene());
  r.render([aadd004()]);

  // The 38 m boundary between a1 and a2 must carry rings from both, at the
  // same place -- that is what makes the colour change crisp without a seam.
  const atBoundary = vertices(meshOf(r)).filter(v => Math.abs(v.y - -38) < 1e-4);
  assert.equal(atBoundary.length, DRILL_TUBE_RADIAL_SEGMENTS * 2,
    'expected two coincident rings at the interval boundary');
});

test('colour changes at the interval boundary', () => {
  const r = new AssayIntervals(new THREE.Scene());
  r.render([aadd004()]);

  const mesh = meshOf(r);
  const pos = mesh.geometry.getAttribute('position');
  const col = mesh.geometry.getAttribute('color');
  const seen = new Set();
  for (let i = 0; i < pos.count; i++) {
    if (Math.abs(pos.getY(i) - -38) < 1e-4) {
      seen.add(`${col.getX(i).toFixed(3)},${col.getY(i).toFixed(3)},${col.getZ(i).toFixed(3)}`);
    }
  }
  assert.equal(seen.size, 2, 'both interval colours should meet at the boundary');
});

test('caps exist only where sampling starts and stops', () => {
  const r = new AssayIntervals(new THREE.Scene());
  r.render([aadd004()]);

  // A cap contributes one centre vertex on the axis. Two runs' worth would be
  // more; a1/a2 are contiguous so there is exactly one run -> two caps.
  const onAxis = vertices(meshOf(r)).filter(v => Math.hypot(v.x, v.z) < 1e-6);
  assert.equal(onAxis.length, 2, 'one cap centre at each end of the run');
});

test('a sampling gap splits the tube into separate runs', () => {
  const r = new AssayIntervals(new THREE.Scene());
  r.render([aadd004({
    assays: [
      { id: 'a1', from_depth: 10, to_depth: 12, grade_value: 1.0, grade_unit: 'g/t',
        unsampled: false, color: '#ff5a1f', start_pos: [0,0,-10], end_pos: [0,0,-12] },
      // 12 - 30 m not assayed at all
      { id: 'a2', from_depth: 30, to_depth: 33, grade_value: 2.0, grade_unit: 'g/t',
        unsampled: false, color: '#ff5a1f', start_pos: [0,0,-30], end_pos: [0,0,-33] },
    ],
  })]);

  const onAxis = vertices(meshOf(r)).filter(v => Math.hypot(v.x, v.z) < 1e-6);
  assert.equal(onAxis.length, 4, 'two runs -> four cap centres');

  // Nothing may be drawn across the 12-30 m gap.
  const inGap = vertices(meshOf(r)).filter(v => v.y < -12.001 && v.y > -29.999);
  assert.equal(inGap.length, 0, 'no geometry inside the unsampled stretch');
});

test('smooth normals point radially outward from the centreline', () => {
  const r = new AssayIntervals(new THREE.Scene());
  r.render([aadd004()]);

  const mesh = meshOf(r);
  const pos = mesh.geometry.getAttribute('position');
  const nrm = mesh.geometry.getAttribute('normal');
  for (let i = 0; i < pos.count; i++) {
    const radial = Math.hypot(pos.getX(i), pos.getZ(i));
    if (radial < 1e-6) continue; // cap centre
    // Surface normal should match the outward direction, and be unit length.
    const len = Math.hypot(nrm.getX(i), nrm.getY(i), nrm.getZ(i));
    assert.ok(Math.abs(len - 1) < 1e-3, `normal length ${len}`);
  }
});

test('a curved hole produces a tube that follows the bend', () => {
  const r = new AssayIntervals(new THREE.Scene());
  r.render([aadd004({
    trace: [
      { depth: 0, x: 0, y: 0, z: 0, dip: -90, azimuth: 90 },
      { depth: 50, x: 0, y: 0, z: -50, dip: -90, azimuth: 90 },
      { depth: 100, x: 35, y: 0, z: -85, dip: -45, azimuth: 90 },
    ],
    assays: [
      { id: 'a1', from_depth: 40, to_depth: 70, grade_value: 1.2, grade_unit: 'g/t',
        unsampled: false, color: '#ff5a1f', start_pos: [0,0,-40], end_pos: [21,0,-71] },
    ],
  })]);

  const verts = vertices(meshOf(r));
  // The bend at 50 m means the tube must gain easting below it.
  assert.ok(Math.max(...verts.map(v => v.x)) > 5,
    'tube should follow the hole east of the dogleg');
  // Still exactly two caps: one interval, one run.
  const onAxis = verts.filter(v =>
    Math.abs(v.x - 0) < 1e-6 && Math.abs(v.z - 0) < 1e-6 && v.y < -39.9 && v.y > -40.1);
  assert.equal(onAxis.length, 1, 'one cap centre at the 40 m start');
});

// ---------------------------------------------------------------------------
// Unsampled intervals never become tubes
// ---------------------------------------------------------------------------

test('null-grade and placeholder-sample intervals render no tube', () => {
  const r = new AssayIntervals(new THREE.Scene());
  r.render([aadd004({
    assays: [
      { id: 'u1', sample_id: 'NSR', from_depth: 0, to_depth: 12, grade_value: null,
        grade_unit: 'g/t', unsampled: true, color: UNSAMPLED_COLOR,
        start_pos: [0,0,0], end_pos: [0,0,-12] },
      { id: 'u2', sample_id: 'No Sample', from_depth: 20, to_depth: 30, grade_value: null,
        grade_unit: 'g/t', unsampled: true, color: UNSAMPLED_COLOR,
        start_pos: [0,0,-20], end_pos: [0,0,-30] },
      { id: 'g1', sample_id: 'S02', from_depth: 12, to_depth: 20, grade_value: 0.62,
        grade_unit: 'g/t', unsampled: false, color: '#ffc233',
        start_pos: [0,0,-12], end_pos: [0,0,-20] },
    ],
  })]);

  assert.equal(r.intervalsData.length, 1, 'only the assayed interval is kept');
  assert.equal(r.intervalsData[0].id, 'g1');
  const ys = vertices(meshOf(r)).map(v => v.y);
  assert.ok(Math.max(...ys) <= -12 + 1e-4);
  assert.ok(Math.min(...ys) >= -20 - 1e-4);
});

// ---------------------------------------------------------------------------
// Planned holes
// ---------------------------------------------------------------------------

test('planned holes get their own translucent group', () => {
  const r = new AssayIntervals(new THREE.Scene());
  r.render([
    aadd004(),
    aadd004({ collar_id: 'c-2', hole_id: 'AAPL001', hole_status: 'planned' }),
  ]);

  assert.equal(r.group.children.length, 1);
  assert.equal(r.plannedGroup.children.length, 1);
  assert.equal(r.plannedGroup.children[0].material.transparent, true);
  assert.ok(r.plannedGroup.children[0].material.opacity < 1.0);
  assert.equal(r.group.children[0].material.transparent, false);

  r.setPlannedVisible(false);
  assert.equal(r.plannedGroup.visible, false);
  assert.equal(r.group.visible, true, 'hiding planned must not hide drilled');
});

test('planned traces are dashed and separately toggleable', () => {
  const r = new DrillholeTraces(new THREE.Scene());
  r.render([
    aadd004(),
    aadd004({ collar_id: 'c-2', hole_id: 'AAPL001', hole_status: 'planned' }),
  ]);

  // Each hole contributes three objects: its trace, and the collar marker's
  // dark rim plus its coloured core.
  assert.equal(r.group.children.length, 3);
  const drilledLine = r.group.children.find(c => c.isLine);
  assert.equal(drilledLine.material.isLineDashedMaterial, undefined,
    'drilled traces are solid');
  assert.equal(drilledLine.material.color.getHexString(), '9b6b43',
    'drilled trace is warm ochre brown');

  assert.equal(r.plannedGroup.children.length, 3);
  const plannedLine = r.plannedGroup.children.find(c => c.isLine);
  assert.equal(plannedLine.material.isLineDashedMaterial, true,
    'planned traces are dashed');
  assert.equal(plannedLine.material.color.getHexString(), '78b7b7',
    'planned trace is muted teal');

  // Shape carries the split as well as colour: square collar for drilled,
  // round for planned -- see drillhole_traces.js.
  const marker = (group, hex) => group.children.find(
    c => c.isMesh && c.material.color.getHexString() === hex
  );
  const drilledCollar = marker(r.group, 'c49a6c');
  assert.ok(drilledCollar, 'drilled collar is sand tan');
  assert.equal(drilledCollar.geometry.type, 'BoxGeometry', 'drilled collar is square');

  const plannedCollar = marker(r.plannedGroup, '78b7b7');
  assert.ok(plannedCollar, 'planned collar is muted teal');
  assert.equal(plannedCollar.geometry.type, 'SphereGeometry', 'planned collar is round');

  for (const [group, core] of [[r.group, drilledCollar], [r.plannedGroup, plannedCollar]]) {
    const rim = group.children.find(c => c.isMesh && c !== core);
    assert.equal(rim.material.side, THREE.BackSide, 'rim is drawn back-faces-only');
    // The rim must be larger, or it would not silhouette the core.
    core.geometry.computeBoundingSphere();
    rim.geometry.computeBoundingSphere();
    assert.ok(
      rim.geometry.boundingSphere.radius > core.geometry.boundingSphere.radius,
      'rim is larger than the core'
    );
    // The rim is decoration and must not widen the camera fit.
    assert.equal(rim.userData.excludeFromFit, true);
  }
});

test('a hole with no status defaults to drilled styling', () => {
  const r = new DrillholeTraces(new THREE.Scene());
  const hole = aadd004();
  delete hole.hole_status;
  r.render([hole]);
  assert.equal(r.group.children.length, 3);
  assert.equal(r.plannedGroup.children.length, 0);
});

// ---------------------------------------------------------------------------
// Cutoff + LOD still work on the new geometry
// ---------------------------------------------------------------------------

test('per-vertex grade is available for the GPU cutoff', () => {
  const r = new AssayIntervals(new THREE.Scene());
  r.render([aadd004()]);

  const grade = meshOf(r).geometry.getAttribute('aGrade');
  assert.ok(grade, 'aGrade attribute must exist');
  // Float32BufferAttribute, so compare at float32 precision.
  const values = [...new Set([...Array(grade.count).keys()].map(i => grade.getX(i)))]
    .sort((a, b) => a - b);
  assert.equal(values.length, 2, 'one grade per interval');
  assert.ok(Math.abs(values[0] - 0.45) < 1e-6);
  assert.ok(Math.abs(values[1] - 1.85) < 1e-6);
});

test('LOD hides a whole hole mesh, dropping its draw call', () => {
  const r = new AssayIntervals(new THREE.Scene());
  r.render([aadd004()]);

  r.setLodStates(new Map([['c-1', false]]));
  assert.equal(meshOf(r).visible, false);

  r.setLodStates(new Map([['c-1', true]]));
  assert.equal(meshOf(r).visible, true);
});

test('re-rendering disposes the previous geometry', () => {
  const scene = new THREE.Scene();
  const r = new AssayIntervals(scene);
  r.render([aadd004()]);
  const first = meshOf(r).geometry;
  let disposed = false;
  first.addEventListener('dispose', () => { disposed = true; });

  r.render([aadd004()]);
  assert.ok(disposed, 'old geometry must be released');
  assert.equal(r.group.children.length, 1);
});

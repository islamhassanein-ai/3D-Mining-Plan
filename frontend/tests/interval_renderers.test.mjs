// Renderer-level checks for AssayIntervals / DrillholeTraces. Three.js builds
// its scene graph without a WebGL context, so these run headless and assert
// what actually gets added to the scene.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';

import { AssayIntervals } from '../src/scene/assay_intervals.js';
import { DrillholeTraces } from '../src/scene/drillhole_traces.js';
import { DRILL_TUBE_RADIUS, UNSAMPLED_COLOR } from '../src/scene/grade_scale.js';

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

const matrixOf = (mesh, i) => {
  const m = new THREE.Matrix4();
  mesh.getMatrixAt(i, m);
  const pos = new THREE.Vector3();
  const quat = new THREE.Quaternion();
  const scale = new THREE.Vector3();
  m.decompose(pos, quat, scale);
  return { pos, quat, scale };
};

// ---------------------------------------------------------------------------
// Task 1 -- absolute placement, no tubes in unsampled zones
// ---------------------------------------------------------------------------

test('no interval tube is rendered in the unsampled 0-37 m zone', () => {
  const scene = new THREE.Scene();
  const r = new AssayIntervals(scene);
  r.render([aadd004()]);

  // Every rendered instance must sit at or below 37 m (y <= -37 + half length).
  for (let i = 0; i < r.mesh.count; i++) {
    const { pos, scale } = matrixOf(r.mesh, i);
    const topY = pos.y + scale.y / 2;
    assert.ok(topY <= -37 + 1e-6,
      `instance ${i} extends to y=${topY}, above the 37 m first sample`);
  }
});

test('the first tube starts exactly 37 m down the trace', () => {
  const scene = new THREE.Scene();
  const r = new AssayIntervals(scene);
  r.render([aadd004()]);

  const { pos, scale } = matrixOf(r.mesh, 0);
  assert.ok(Math.abs((pos.y + scale.y / 2) - -37) < 1e-6);
  assert.ok(Math.abs((pos.y - scale.y / 2) - -38) < 1e-6);
});

// ---------------------------------------------------------------------------
// Task 2 -- uniform radius, smooth tubes, flush joints
// ---------------------------------------------------------------------------

test('every tube uses the same radius regardless of grade', () => {
  const scene = new THREE.Scene();
  const r = new AssayIntervals(scene);
  r.render([aadd004()]);

  // InstancedMesh stores matrices in a Float32Array, so compare at float32
  // precision rather than double.
  for (let i = 0; i < r.mesh.count; i++) {
    const { scale } = matrixOf(r.mesh, i);
    assert.ok(Math.abs(scale.x - DRILL_TUBE_RADIUS) < 1e-6, `x radius on ${i}`);
    assert.ok(Math.abs(scale.z - DRILL_TUBE_RADIUS) < 1e-6, `z radius on ${i}`);
  }
});

test('tube geometry is smooth-shaded with a high radial segment count', () => {
  const scene = new THREE.Scene();
  const r = new AssayIntervals(scene);
  r.render([aadd004()]);

  assert.equal(r.mesh.geometry.parameters.radialSegments, 20);
  assert.equal(r.mesh.material.flatShading, false);
});

test('adjacent intervals meet flush with no gap or overlap', () => {
  const scene = new THREE.Scene();
  const r = new AssayIntervals(scene);
  r.render([aadd004()]);

  // a1 ends at 38 m, a2 starts at 38 m -- the caps must coincide.
  const first = matrixOf(r.mesh, 0);
  const second = matrixOf(r.mesh, 1);
  const firstBottom = first.pos.y - first.scale.y / 2;
  const secondTop = second.pos.y + second.scale.y / 2;
  assert.ok(Math.abs(firstBottom - secondTop) < 1e-6,
    `joint gap of ${Math.abs(firstBottom - secondTop)} m`);
});

// ---------------------------------------------------------------------------
// Task 3 -- unsampled intervals never become tubes
// ---------------------------------------------------------------------------

test('null-grade and placeholder-sample intervals render no tube', () => {
  const scene = new THREE.Scene();
  const r = new AssayIntervals(scene);
  r.render([aadd004({
    assays: [
      { id: 'u1', sample_id: 'NSR', from_depth: 0, to_depth: 12, grade_value: null,
        grade_unit: 'g/t', unsampled: true, color: UNSAMPLED_COLOR,
        start_pos: [0, 0, 0], end_pos: [0, 0, -12] },
      { id: 'u2', sample_id: 'No Sample', from_depth: 20, to_depth: 30, grade_value: null,
        grade_unit: 'g/t', unsampled: true, color: UNSAMPLED_COLOR,
        start_pos: [0, 0, -20], end_pos: [0, 0, -30] },
      { id: 'g1', sample_id: 'S02', from_depth: 12, to_depth: 20, grade_value: 0.62,
        grade_unit: 'g/t', unsampled: false, color: '#ffc233',
        start_pos: [0, 0, -12], end_pos: [0, 0, -20] },
    ],
  })]);

  assert.equal(r.mesh.count, 1, 'only the one assayed interval should render');
  assert.equal(r.intervalsData[0].id, 'g1');
});

// ---------------------------------------------------------------------------
// Task 4 -- planned holes styled distinctly and separately toggleable
// ---------------------------------------------------------------------------

test('planned holes get their own translucent interval mesh', () => {
  const scene = new THREE.Scene();
  const r = new AssayIntervals(scene);
  r.render([
    aadd004(),
    aadd004({ collar_id: 'c-2', hole_id: 'AAPL001', hole_status: 'planned' }),
  ]);

  assert.ok(r.plannedMesh, 'planned mesh should exist');
  assert.equal(r.plannedMesh.material.transparent, true);
  assert.ok(r.plannedMesh.material.opacity < 1.0);
  // Drilled intervals stay fully opaque.
  assert.equal(r.mesh.material.transparent, false);
  assert.equal(r.mesh.material.opacity, 1.0);
});

test('planned traces are dashed and live in a separately toggleable group', () => {
  const scene = new THREE.Scene();
  const r = new DrillholeTraces(scene);
  r.render([
    aadd004(),
    aadd004({ collar_id: 'c-2', hole_id: 'AAPL001', hole_status: 'planned' }),
  ]);

  assert.equal(r.group.children.length, 1, 'one drilled trace');
  assert.equal(r.plannedGroup.children.length, 1, 'one planned trace');
  assert.equal(r.plannedGroup.children[0].material.isLineDashedMaterial, true);
  assert.equal(r.group.children[0].material.isLineDashedMaterial, undefined);

  r.setPlannedVisible(false);
  assert.equal(r.plannedGroup.visible, false);
  assert.equal(r.group.visible, true, 'hiding planned must not hide drilled');
});

test('a hole with no status defaults to drilled styling', () => {
  const scene = new THREE.Scene();
  const r = new DrillholeTraces(scene);
  const hole = aadd004();
  delete hole.hole_status;
  r.render([hole]);
  assert.equal(r.group.children.length, 1);
  assert.equal(r.plannedGroup.children.length, 0);
});

// ---------------------------------------------------------------------------
// Curved holes
// ---------------------------------------------------------------------------

test('an interval spanning a dogleg renders as multiple chained tubes', () => {
  const scene = new THREE.Scene();
  const r = new AssayIntervals(scene);
  r.render([aadd004({
    trace: [
      { depth: 0, x: 0, y: 0, z: 0, dip: -90, azimuth: 90 },
      { depth: 50, x: 0, y: 0, z: -50, dip: -90, azimuth: 90 },
      { depth: 100, x: 35, y: 0, z: -85, dip: -45, azimuth: 90 },
    ],
    assays: [
      { id: 'a1', sample_id: 'S01', from_depth: 40, to_depth: 70, grade_value: 1.2,
        grade_unit: 'g/t', unsampled: false, color: '#ff5a1f',
        start_pos: [0, 0, -40], end_pos: [21, 0, -71] },
    ],
  })]);

  assert.equal(r.mesh.count, 2, 'should split at the 50 m station');
  // Both sub-segments belong to the same source interval.
  assert.equal(r.intervalsData[0].id, 'a1');
  assert.equal(r.intervalsData[1].id, 'a1');
});

// ---------------------------------------------------------------------------
// Mesh shape -- dogleg joints
// ---------------------------------------------------------------------------

test('sub-segments of one interval overlap so a bend has no notch', () => {
  const scene = new THREE.Scene();
  const r = new AssayIntervals(scene);
  r.render([aadd004({
    trace: [
      { depth: 0, x: 0, y: 0, z: 0, dip: -90, azimuth: 90 },
      { depth: 50, x: 0, y: 0, z: -50, dip: -90, azimuth: 90 },
      { depth: 100, x: 35, y: 0, z: -85, dip: -45, azimuth: 90 },
    ],
    assays: [
      { id: 'a1', sample_id: 'S01', from_depth: 40, to_depth: 70, grade_value: 1.2,
        grade_unit: 'g/t', unsampled: false, color: '#ff5a1f',
        start_pos: [0, 0, -40], end_pos: [21, 0, -71] },
    ],
  })]);

  assert.equal(r.mesh.count, 2);
  // Each sub-segment is longer than its own chord, because the shared interior
  // joint is grown on both sides.
  const chordA = r.intervalsData[0].start.distanceTo(r.intervalsData[0].end);
  const chordB = r.intervalsData[1].start.distanceTo(r.intervalsData[1].end);
  assert.ok(matrixOf(r.mesh, 0).scale.y > chordA, 'first segment should grow at its inner end');
  assert.ok(matrixOf(r.mesh, 1).scale.y > chordB, 'second segment should grow at its inner end');

  // Only the interior joint grows -- the interval's own ends stay put.
  assert.equal(r.intervalsData[0].joinStart, false);
  assert.equal(r.intervalsData[0].joinEnd, true);
  assert.equal(r.intervalsData[1].joinStart, true);
  assert.equal(r.intervalsData[1].joinEnd, false);
});

test('a single-segment interval is never grown', () => {
  const scene = new THREE.Scene();
  const r = new AssayIntervals(scene);
  r.render([aadd004()]);

  // 37-38 m on a straight trace: one segment, exactly 1 m, no overlap.
  assert.ok(Math.abs(matrixOf(r.mesh, 0).scale.y - 1.0) < 1e-6);
  assert.equal(r.intervalsData[0].joinStart, false);
  assert.equal(r.intervalsData[0].joinEnd, false);
});

test('grown segments still produce a finite matrix', () => {
  const scene = new THREE.Scene();
  const r = new AssayIntervals(scene);
  r.render([aadd004()]);
  for (let i = 0; i < r.mesh.count; i++) {
    const { pos, scale } = matrixOf(r.mesh, i);
    for (const v of [pos.x, pos.y, pos.z, scale.x, scale.y, scale.z]) {
      assert.ok(Number.isFinite(v), 'matrix must not contain NaN');
    }
  }
});

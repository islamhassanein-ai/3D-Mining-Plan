import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  interpolateTracePosition,
  subdivideIntervalAlongTrace,
} from '../src/scene/trace_geometry.js';
import {
  getGradeBucketIndex,
  getGradeColor,
  isUnsampled,
  UNSAMPLED_BUCKET_INDEX,
  UNSAMPLED_COLOR,
} from '../src/scene/grade_scale.js';

// Scene mapping is Easting -> X, Elevation -> Y, Northing -> Z, so a vertical
// hole's depth shows up as a drop in `.y`.
const verticalTrace = (total = 100) => ([
  { depth: 0, x: 0, y: 0, z: 0, dip: -90, azimuth: 0 },
  { depth: total, x: 0, y: 0, z: -total, dip: -90, azimuth: 0 },
]);

const CLOSE = 1e-9;

// ---------------------------------------------------------------------------
// Absolute depth placement -- the AADD004 regression
// ---------------------------------------------------------------------------

test('first assay under an unsampled top zone plots at its own depth', () => {
  // AADD004: nothing sampled 0 - 37 m, first assay 37 - 38 m.
  const trace = verticalTrace(100);
  const start = interpolateTracePosition(trace, 37);
  const end = interpolateTracePosition(trace, 38);

  assert.ok(Math.abs(start.y - -37) < CLOSE, `expected y=-37, got ${start.y}`);
  assert.ok(Math.abs(end.y - -38) < CLOSE, `expected y=-38, got ${end.y}`);

  // Emphatically NOT at the collar.
  const collar = interpolateTracePosition(trace, 0);
  assert.notEqual(start.y, collar.y);
});

test('position depends only on absolute depth, not on interval ordering', () => {
  const trace = verticalTrace(100);
  const a = interpolateTracePosition(trace, 37);
  const b = interpolateTracePosition(trace, 37);
  assert.deepEqual([a.x, a.y, a.z], [b.x, b.y, b.z]);
});

test('depths outside the trace clamp to its endpoints', () => {
  const trace = verticalTrace(100);
  assert.equal(interpolateTracePosition(trace, -5).y, 0);
  assert.equal(interpolateTracePosition(trace, 500).y, -100);
});

// ---------------------------------------------------------------------------
// Tube sub-division along the trajectory
// ---------------------------------------------------------------------------

test('a straight interval stays a single segment', () => {
  const segments = subdivideIntervalAlongTrace(verticalTrace(100), 37, 38);
  assert.equal(segments.length, 1);
  assert.ok(Math.abs(segments[0].start.y - -37) < CLOSE);
  assert.ok(Math.abs(segments[0].end.y - -38) < CLOSE);
});

test('an interval spanning a dogleg splits at the intervening station', () => {
  // Vertical to 50 m, then bending East. Trace stations are in backend
  // coordinates: x = easting, y = northing, z = elevation.
  const trace = [
    { depth: 0, x: 0, y: 0, z: 0, dip: -90, azimuth: 90 },
    { depth: 50, x: 0, y: 0, z: -50, dip: -90, azimuth: 90 },
    { depth: 100, x: 35, y: 0, z: -85, dip: -45, azimuth: 90 },
  ];
  const segments = subdivideIntervalAlongTrace(trace, 40, 70);
  assert.equal(segments.length, 2, 'should split at the 50 m station');
  // The split point is the station itself, so the tube tracks the bend
  // instead of cutting the corner.
  assert.ok(Math.abs(segments[0].end.y - -50) < CLOSE);
  assert.ok(Math.abs(segments[0].end.x - 0) < CLOSE);
});

test('sub-segments form an unbroken chain', () => {
  const trace = [
    { depth: 0, x: 0, y: 0, z: 0, dip: -90, azimuth: 0 },
    { depth: 30, x: 5, y: 0, z: -29, dip: -80, azimuth: 0 },
    { depth: 60, x: 14, y: 0, z: -57, dip: -70, azimuth: 0 },
  ];
  const segments = subdivideIntervalAlongTrace(trace, 10, 55);
  for (let i = 1; i < segments.length; i++) {
    assert.ok(
      segments[i - 1].end.distanceTo(segments[i].start) < CLOSE,
      'segment ends must coincide with the next segment start',
    );
  }
});

test('adjacent intervals meet flush at a shared depth boundary', () => {
  // The joint between 0-2 and 2-10 must be the exact same point, otherwise
  // the tube caps leave a gap or overlap.
  const trace = verticalTrace(100);
  const upper = subdivideIntervalAlongTrace(trace, 0, 2);
  const lower = subdivideIntervalAlongTrace(trace, 2, 10);
  const joint = upper[upper.length - 1].end;
  assert.ok(joint.distanceTo(lower[0].start) < CLOSE);
});

test('a zero-length interval degenerates safely to one segment', () => {
  const segments = subdivideIntervalAlongTrace(verticalTrace(100), 20, 20);
  assert.equal(segments.length, 1);
});

// ---------------------------------------------------------------------------
// Grade scale parity with backend/src/services/grade_coloring.py
// ---------------------------------------------------------------------------

test('grade brackets match the canonical scale', () => {
  const cases = [
    [0.0, '#94a3b8'], [0.09, '#94a3b8'],
    [0.10, '#1f6fff'], [0.29, '#1f6fff'],
    [0.30, '#00e57a'], [0.49, '#00e57a'],
    [0.50, '#ffd21e'], [0.99, '#ffd21e'],
    [1.00, '#f5222d'], [2.99, '#f5222d'],
    [3.00, '#e838ff'], [150, '#e838ff'],
  ];
  for (const [grade, expected] of cases) {
    assert.equal(getGradeColor(grade, 'g/t'), expected, `grade ${grade}`);
  }
});

test('placeholder sample ids and null grades read as unsampled', () => {
  for (const id of ['Unsampled', 'NSR', 'NS', 'No Sample', 'No Samples', ' no sample ']) {
    assert.equal(isUnsampled(1.5, id), true, `sample id ${id}`);
    assert.equal(getGradeColor(1.5, 'g/t', id), UNSAMPLED_COLOR);
  }
  for (const g of [null, undefined, NaN, '']) {
    assert.equal(isUnsampled(g), true, `grade ${g}`);
    assert.equal(getGradeBucketIndex(g), UNSAMPLED_BUCKET_INDEX);
    assert.equal(getGradeColor(g), UNSAMPLED_COLOR);
  }
});

test('a genuine 0.0 g/t assay is not unsampled', () => {
  assert.equal(isUnsampled(0.0), false);
  assert.notEqual(getGradeColor(0.0), UNSAMPLED_COLOR);
  assert.equal(getGradeBucketIndex(0.0), 0);
});

import test from 'node:test';
import assert from 'node:assert';

import {
  planeNormal,
  holeDirection,
  normalToPlane,
  dipDirectionFromStrike,
  signedDip,
  meanPlane,
  intersectDepth,
  intersectionAngleDeg,
  trueThickness,
  elevationSensitivity,
  planZone,
  sensitivity,
  projectTrenchSamples,
  calibrate,
  drillingProposal,
  computePlan,
  dot
} from '../src/services/depth_planner.js';

// ---------------------------------------------------------------------------
// The AAT002 / AADD010 case. Every expected value below was worked through by
// hand from the two field readings before any of this code existed, so the
// suite is a check on the implementation rather than a recording of it.
//
//   Trench AAT002, shear zone, two structural readings:
//     m13.0  208740.219 / 2467844.566 / 293.104   strike 299  dip 38  dd 209
//     m16.5  208743.126 / 2467847.349 / 292.843   strike 276  dip 44  dd 186
//   Zone assumed 12-25 m along the trench:
//     m12    208739.479 / 2467843.974 / 293.120
//     m25    208747.242 / 2467852.584 / 290.958
//   Proposed hole AADD010: collar 208720.3 / 2467784.8 / 313, azi 030, dip 60
// ---------------------------------------------------------------------------

const READING_13 = { dip: 38, dipDirection: 209, label: 'm13 (299/38)' };
const READING_165 = { dip: 44, dipDirection: 186, label: 'm16.5 (276/44)' };

const TOP = { easting: 208739.479, northing: 2467843.974, elevation: 293.120 };
const BASE = { easting: 208747.242, northing: 2467852.584, elevation: 290.958 };

const COLLAR = { easting: 208720.3, northing: 2467784.8, elevation: 313 };
const HOLE = { azimuth: 30, dip: signedDip(60) };

const MEAN = meanPlane([READING_13, READING_165]);

const near = (actual, expected, tol, what) =>
  assert.ok(
    Math.abs(actual - expected) <= tol,
    `${what}: expected ~${expected} (+/-${tol}), got ${actual}`
  );

// --- conventions ------------------------------------------------------------

test('plane normal is a unit vector leaning down-dip', () => {
  const n = planeNormal(45, 90); // dips east
  near(Math.sqrt(dot(n, n)), 1, 1e-12, 'length');
  assert.ok(n.e > 0, 'a plane dipping east has a normal leaning east');
  near(n.n, 0, 1e-12, 'no northing component');
  assert.ok(n.u > 0, 'upward hemisphere');
});

test('a horizontal plane has a vertical normal', () => {
  const n = planeNormal(0, 137);
  near(n.e, 0, 1e-12, 'e');
  near(n.n, 0, 1e-12, 'n');
  near(n.u, 1, 1e-12, 'u');
});

test('normalToPlane inverts planeNormal', () => {
  for (const [dip, dd] of [[38, 209], [44, 186], [12, 5], [71, 350], [40, 197]]) {
    const round = normalToPlane(planeNormal(dip, dd));
    near(round.dip, dip, 1e-9, `dip ${dip}`);
    near(round.dipDirection, dd, 1e-9, `dip dir ${dd}`);
  }
});

test('hole direction: a 60-degree hole toward 030 heads NNE and down', () => {
  const d = holeDirection(signedDip(60), 30);
  near(Math.sqrt(dot(d, d)), 1, 1e-12, 'length');
  near(d.e, 0.25, 1e-6, 'easting');
  near(d.n, 0.4330127, 1e-6, 'northing');
  near(d.u, -0.8660254, 1e-6, 'up (negative = down)');
});

test('field data uses strike - 90 for dip direction', () => {
  assert.equal(dipDirectionFromStrike(299), 209);
  assert.equal(dipDirectionFromStrike(276), 186);
  assert.equal(dipDirectionFromStrike(299, 'plus90'), 29);
  // Wrap-around must not produce a negative bearing.
  assert.equal(dipDirectionFromStrike(45), 315);
});

// --- vector mean of the two readings ---------------------------------------

test('two shear readings average to 40.4 / 196.8 (strike 287)', () => {
  near(MEAN.dip, 40.42, 0.05, 'mean dip');
  near(MEAN.dipDirection, 196.80, 0.05, 'mean dip direction');
  near(MEAN.strike, 286.80, 0.05, 'mean strike');
  assert.equal(MEAN.count, 2);
  // The two poles are ~9 degrees apart -- an undulating zone, not a conflict.
  assert.ok(MEAN.spreadDeg > 3 && MEAN.spreadDeg < 15, `spread ${MEAN.spreadDeg}`);
});

test('mean of one reading is that reading', () => {
  const m = meanPlane([READING_13]);
  assert.equal(m.dip, 38);
  assert.equal(m.dipDirection, 209);
  assert.equal(m.count, 1);
});

test('a pole logged in the opposite hemisphere still averages correctly', () => {
  // Same plane, dip direction flipped 180 and dip complemented -- a plausible
  // logging slip. Folding poles into one hemisphere must absorb it.
  const a = { dip: 40, dipDirection: 197 };
  const mean = meanPlane([a, a]);
  near(mean.dip, 40, 1e-6, 'dip');
  near(mean.dipDirection, 197, 1e-6, 'dip direction');
});

// --- the intersection itself ------------------------------------------------

test('hole meets the mean plane at 77 degrees', () => {
  near(intersectionAngleDeg(HOLE, MEAN), 77.06, 0.1, 'intersection angle');
});

test('zone top (trench m12) lands at 56.9 m downhole', () => {
  const hit = intersectDepth({ collar: COLLAR, hole: HOLE, anchor: TOP, plane: MEAN });
  near(hit.depth, 56.89, 0.05, 'downhole depth');
  near(hit.verticalDepth, 49.3, 0.1, 'vertical depth');
  assert.equal(hit.parallel, false);
  assert.equal(hit.behindCollar, false);
  // Intersection point, from the same hand-worked run.
  near(hit.point.e, 208734.5, 0.2, 'easting');
  near(hit.point.n, 2467809.4, 0.2, 'northing');
  near(hit.point.u, 263.7, 0.2, 'elevation');
});

test('zone base (trench m25) lands at 65.6 m, giving 8.7 m of core', () => {
  const plan = planZone({ collar: COLLAR, hole: HOLE, plane: MEAN, top: TOP, base: BASE });
  near(plan.top.depth, 56.89, 0.05, 'top');
  near(plan.base.depth, 65.55, 0.05, 'base');
  near(plan.coreLength, 8.66, 0.05, 'core length');
  // Near-perpendicular intersection, so true thickness barely differs from the
  // downhole length -- which is the whole reason this hole orientation is good.
  near(plan.trueThickness, 8.44, 0.05, 'true thickness');
  assert.ok(plan.trueThickness < plan.coreLength, 'true thickness never exceeds downhole length');
});

test('true thickness collapses to zero for a hole running in the plane', () => {
  near(trueThickness(10, 90), 10, 1e-9, 'perpendicular');
  near(trueThickness(10, 0), 0, 1e-9, 'parallel');
  near(trueThickness(10, 30), 5, 1e-9, '30 degrees');
});

test('a hole parallel to the plane never intersects', () => {
  // Drill along strike, horizontally, in a vertical plane.
  const vertical = { dip: 90, dipDirection: 90 };
  const along = { azimuth: 0, dip: 0 };
  const hit = intersectDepth({ collar: COLLAR, hole: along, anchor: TOP, plane: vertical });
  assert.equal(hit.parallel, true);
  assert.equal(hit.depth, null);
});

test('a zone that outcrops above the collar reports a depth behind it', () => {
  // Flat zone 50 m above the collar; drilling down can only move away from it.
  const above = { easting: COLLAR.easting, northing: COLLAR.northing, elevation: COLLAR.elevation + 50 };
  const flat = { dip: 0, dipDirection: 0 };
  const hit = intersectDepth({ collar: COLLAR, hole: HOLE, anchor: above, plane: flat });
  assert.equal(hit.behindCollar, true);
  near(hit.depth, -50 / Math.sin(60 * Math.PI / 180), 1e-9, 'depth behind the collar');
});

test('this collar sits 73 m above the zone, so azimuth alone cannot miss it', () => {
  // Worth pinning: the zone plane is unbounded, and the collar is high above
  // it, so even drilling directly away down-dip still intersects. "Did I aim
  // the right way" is answered by the intersection ANGLE and by whether the
  // hit lands inside the mapped zone -- never by the sign of the depth.
  const away = { azimuth: 210, dip: signedDip(60) };
  const hit = intersectDepth({ collar: COLLAR, hole: away, anchor: TOP, plane: MEAN });
  assert.equal(hit.behindCollar, false);
  assert.ok(hit.depth > 0, `expected a positive depth, got ${hit.depth}`);
  // Far shallower than the real hole, and at a much worse angle.
  assert.ok(intersectionAngleDeg(away, MEAN) < intersectionAngleDeg(HOLE, MEAN));
});

// --- sensitivity ------------------------------------------------------------

test('collar elevation moves the intersection 0.78 m per metre', () => {
  near(elevationSensitivity(HOLE, MEAN), 0.781, 0.002, 'dL/dCz');

  // The analytic slope must match a finite difference of the real thing.
  const up = intersectDepth({
    collar: { ...COLLAR, elevation: COLLAR.elevation + 1 }, hole: HOLE, anchor: TOP, plane: MEAN
  }).depth;
  const down = intersectDepth({
    collar: { ...COLLAR, elevation: COLLAR.elevation - 1 }, hole: HOLE, anchor: TOP, plane: MEAN
  }).depth;
  near((up - down) / 2, elevationSensitivity(HOLE, MEAN), 1e-9, 'finite difference');
});

test('+/-5 degrees of dip opens the envelope to 52.9 - 70.4 m', () => {
  const env = sensitivity({
    collar: COLLAR, hole: HOLE, plane: MEAN, top: TOP, base: BASE,
    readings: [READING_13, READING_165]
  });

  near(env.min, 52.88, 0.1, 'shallowest');
  near(env.max, 70.44, 0.1, 'deepest');

  // Dip is the control; dip direction barely matters because the hole is
  // nearly normal to the plane. This ordering is the actionable conclusion:
  // re-measuring dip is worth a trip back to the trench, dip direction is not.
  near(env.driver.dip, 8.14, 0.1, 'dip drives ~8 m of spread');
  near(env.driver.dipDirection, 1.0, 0.3, 'dip direction drives ~1 m');
  assert.ok(
    env.driver.dip > env.driver.dipDirection * 3,
    `dip (${env.driver.dip}) should dominate dip direction (${env.driver.dipDirection})`
  );

  const base = env.rows.find(r => r.group === 'base');
  near(base.topDepth, 56.89, 0.05, 'base-case row matches planZone');

  // Each individual reading gets its own row, labelled.
  const readingRows = env.rows.filter(r => r.group === 'reading');
  assert.equal(readingRows.length, 2);
  assert.ok(readingRows.some(r => r.label.includes('m13')));
});

test('the envelope always contains the base case', () => {
  const plan = planZone({ collar: COLLAR, hole: HOLE, plane: MEAN, top: TOP, base: BASE });
  const env = sensitivity({ collar: COLLAR, hole: HOLE, plane: MEAN, top: TOP, base: BASE });
  assert.ok(env.min <= plan.top.depth, 'min brackets top');
  assert.ok(env.max >= plan.base.depth, 'max brackets base');
});

// --- trench metre -> downhole depth ----------------------------------------

test('trench samples project onto equivalent downhole depths', () => {
  const samples = [
    { from_depth: 12, easting: 208739.479, northing: 2467843.974, elevation: 293.120, grade_value: 0.25 },
    { from_depth: 13, easting: 208740.219, northing: 2467844.566, elevation: 293.104, grade_value: 0.76, sample_id: '10214' },
    { from_depth: 16.5, easting: 208743.126, northing: 2467847.349, elevation: 292.843, grade_value: 1.76 },
    { from_depth: 25, easting: 208747.242, northing: 2467852.584, elevation: 290.958, grade_value: 0.11 }
  ];

  const projected = projectTrenchSamples({ samples, collar: COLLAR, hole: HOLE, plane: MEAN });

  assert.equal(projected.length, 4);
  // Sorted by depth, and carrying grade through for the sampling plan.
  assert.deepEqual(projected.map(p => p.meter), [12, 13, 16.5, 25]);
  near(projected[0].depth, 56.89, 0.05, 'm12');
  near(projected[1].depth, 57.4, 0.1, 'm13');
  near(projected[2].depth, 60.0, 0.1, 'm16.5');
  near(projected[3].depth, 65.55, 0.05, 'm25');
  assert.equal(projected[1].grade, 0.76);
  assert.equal(projected[1].sample_id, '10214');

  // 13 trench metres compress into ~8.7 m of core: the trench cuts the zone
  // obliquely while the hole is nearly normal to it.
  const span = projected[3].depth - projected[0].depth;
  near(span / 13, 0.67, 0.02, 'metres of core per trench metre');
});

test('samples with unusable coordinates are dropped, not crashed on', () => {
  const projected = projectTrenchSamples({
    samples: [
      { from_depth: 1, easting: null, northing: 2467843, elevation: 293 },
      { from_depth: 2, easting: 208739, northing: 2467843, elevation: 293 }
    ],
    collar: COLLAR, hole: HOLE, plane: MEAN
  });
  assert.equal(projected.length, 1);
  assert.equal(projected[0].meter, 2);
});

// --- post-drill calibration -------------------------------------------------

test('an intersection 3.3 m shallow calibrates the collar to 308.8 m', () => {
  const predicted = intersectDepth({ collar: COLLAR, hole: HOLE, anchor: TOP, plane: MEAN }).depth;
  const cal = calibrate({
    observedDepth: predicted - 3.3, collar: COLLAR, hole: HOLE, plane: MEAN, anchor: TOP
  });

  near(cal.residual, -3.3, 1e-9, 'residual');
  near(cal.elevationBranch.collarElevation, 308.77, 0.05, 'calibrated collar elevation');
  near(cal.elevationBranch.shift, -4.23, 0.05, 'elevation shift');
});

test('the same miss can instead be explained by a shallower dip', () => {
  const predicted = intersectDepth({ collar: COLLAR, hole: HOLE, anchor: TOP, plane: MEAN }).depth;
  const observed = predicted - 3.3;
  const cal = calibrate({ observedDepth: observed, collar: COLLAR, hole: HOLE, plane: MEAN, anchor: TOP });

  assert.ok(cal.dipBranch, 'a dip solution exists');
  assert.ok(
    cal.dipBranch.dip > 33 && cal.dipBranch.dip < 39,
    `expected a dip near 36, got ${cal.dipBranch.dip}`
  );

  // Whatever it found must actually reproduce the observation.
  const check = intersectDepth({
    collar: COLLAR, hole: HOLE, anchor: TOP, plane: { ...MEAN, dip: cal.dipBranch.dip }
  }).depth;
  near(check, observed, 0.01, 'calibrated dip reproduces the observed depth');
});

test('calibration against the true prediction is a no-op', () => {
  const predicted = intersectDepth({ collar: COLLAR, hole: HOLE, anchor: TOP, plane: MEAN }).depth;
  const cal = calibrate({ observedDepth: predicted, collar: COLLAR, hole: HOLE, plane: MEAN, anchor: TOP });
  near(cal.residual, 0, 1e-9, 'residual');
  near(cal.elevationBranch.collarElevation, 313, 1e-6, 'collar unchanged');
  near(cal.dipBranch.dip, MEAN.dip, 0.02, 'dip unchanged');
});

// --- the drilling proposal --------------------------------------------------

test('proposal: log from 48 m, target 57-66 m, EOH 85 m', () => {
  const plan = planZone({ collar: COLLAR, hole: HOLE, plane: MEAN, top: TOP, base: BASE });
  const env = sensitivity({
    collar: COLLAR, hole: HOLE, plane: MEAN, top: TOP, base: BASE,
    readings: [READING_13, READING_165]
  });
  const proposal = drillingProposal(plan, env);

  assert.equal(proposal.startLogging, 48);
  assert.equal(proposal.eoh, 85);
  near(proposal.targetFrom, 56.89, 0.05, 'target from');
  near(proposal.targetTo, 65.55, 0.05, 'target to');
  assert.ok(proposal.eoh > proposal.envelopeTo, 'EOH clears the deepest estimate');
});

test('EOH margin is measured from the deepest estimate, not the base case', () => {
  const plan = planZone({ collar: COLLAR, hole: HOLE, plane: MEAN, top: TOP, base: BASE });
  const env = sensitivity({ collar: COLLAR, hole: HOLE, plane: MEAN, top: TOP, base: BASE });
  const proposal = drillingProposal(plan, env, { eohMargin: 20 });
  near(proposal.eoh, env.max + 20, 0.51, 'EOH tracks the envelope');
});

// --- the whole chain --------------------------------------------------------

test('computePlan runs the full chain in one call', () => {
  const result = computePlan({
    collar: COLLAR,
    hole: HOLE,
    plane: MEAN,
    top: TOP,
    base: BASE,
    readings: [READING_13, READING_165],
    trenchSamples: [
      { from_depth: 13, easting: 208740.219, northing: 2467844.566, elevation: 293.104, grade_value: 0.76 }
    ],
    observedDepth: 53
  });

  near(result.top.depth, 56.89, 0.05, 'top');
  near(result.base.depth, 65.55, 0.05, 'base');
  near(result.intersectionAngleDeg, 77.06, 0.1, 'angle');
  assert.equal(result.proposal.eoh, 85);
  assert.equal(result.projected.length, 1);
  assert.ok(result.calibration, 'calibration ran because observedDepth was given');
  near(result.calibration.observed, 53, 1e-9, 'observed carried through');
});

test('computePlan skips calibration when no depth was observed', () => {
  const result = computePlan({
    collar: COLLAR, hole: HOLE, plane: MEAN, top: TOP, base: BASE
  });
  assert.equal(result.calibration, null);
  assert.equal(result.projected.length, 0);
});

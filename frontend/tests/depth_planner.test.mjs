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
  perpendicularOrientation,
  suggestHoles,
  generateDrillPattern,
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

// --- suggested holes --------------------------------------------------------

test('the perpendicular orientation is drill back up-dip at 90 minus the zone dip', () => {
  const ideal = perpendicularOrientation(MEAN);
  // Zone dips 40.4 toward 196.8, so cut it dead-on by drilling toward 16.8
  // at 49.6 below horizontal.
  near(ideal.azimuth, 16.80, 0.05, 'azimuth is dip direction + 180');
  near(ideal.dip, 49.58, 0.05, 'dip is 90 - zone dip');

  // And it must actually achieve 90 degrees.
  const angle = intersectionAngleDeg({ azimuth: ideal.azimuth, dip: signedDip(ideal.dip) }, MEAN);
  near(angle, 90, 1e-6, 'a dead-on cut');
});

test('a perpendicular cut makes core length equal true thickness', () => {
  const ideal = perpendicularOrientation(MEAN);
  const plan = planZone({
    collar: COLLAR,
    hole: { azimuth: ideal.azimuth, dip: signedDip(ideal.dip) },
    plane: MEAN, top: TOP, base: BASE
  });
  near(plan.trueThickness, plan.coreLength, 1e-6, 'no oblique inflation');
});

test('suggestions beat the hole the geologist typed in', () => {
  const s = suggestHoles({
    collar: COLLAR, plane: MEAN, top: TOP, base: BASE, currentAzimuth: 30
  });

  assert.ok(s.candidates.length >= 2, `expected candidates, got ${s.candidates.length}`);
  assert.ok(s.searched > 100, 'the grid was actually searched');

  // For this zone one orientation wins outright -- 017/50 is simultaneously the
  // perpendicular cut, the shallowest, and the balanced pick -- so those
  // objectives collapse into a single row rather than repeating the same hole.
  const best = s.candidates[0];
  near(best.azimuth, 16.80, 0.05, 'best azimuth');
  near(best.dip, 49.58, 0.05, 'best dip');
  near(best.angle, 90, 1e-6, 'a dead-on cut');
  assert.ok(best.label.includes('Perpendicular') && best.label.includes('Shallowest'),
    `objectives should merge onto one row: "${best.label}"`);

  // It beats the 030/60 hole the geologist proposed, on angle AND on depth.
  const proposed = planZone({ collar: COLLAR, hole: HOLE, plane: MEAN, top: TOP, base: BASE });
  assert.ok(best.angle > proposed.intersectionAngleDeg, 'better cut than 030/60');
  assert.ok(best.topDepth < proposed.top.depth, 'and reaches the zone sooner');

  // Access constraints are respected as their own option.
  const onAzimuth = s.candidates.find(c => c.label.includes('current azimuth'));
  assert.ok(onAzimuth, 'an option that keeps azimuth 030');
  near(onAzimuth.azimuth, 30, 1e-9, 'keeps the planned azimuth');
  assert.ok(onAzimuth.dip < 60, `dip should flatten from 60 to ~50, got ${onAzimuth.dip}`);
  assert.ok(onAzimuth.angle > proposed.intersectionAngleDeg, 'still better than 030/60');

  // Every candidate must be a real, usable hole.
  for (const c of s.candidates) {
    assert.ok(c.topDepth > 0, `${c.label}: zone must be ahead of the collar`);
    assert.ok(Number.isFinite(c.eoh) && c.eoh > c.topDepth, `${c.label}: EOH past the zone`);
    assert.ok(c.envelope && c.envelope.max >= c.envelope.min, `${c.label}: has an envelope`);
    assert.ok(c.label.length > 0 && typeof c.note === 'string');
  }
});

test('every objective is represented, and duplicates merge rather than repeat', () => {
  const s = suggestHoles({
    collar: COLLAR, plane: MEAN, top: TOP, base: BASE, currentAzimuth: 30
  });
  const labels = s.candidates.map(c => c.label).join(' | ');
  for (const objective of ['Perpendicular cut', 'Shallowest', 'Balanced']) {
    assert.ok(labels.includes(objective), `${objective} missing from: ${labels}`);
  }
  // Orientations are unique -- two objectives landing on one hole share a row.
  const keys = s.candidates.map(c => `${Math.round(c.azimuth)}/${Math.round(c.dip)}`);
  assert.equal(new Set(keys).size, keys.length, 'no duplicate orientations');
});

test('the shallowest candidate really is the shallowest', () => {
  const s = suggestHoles({ collar: COLLAR, plane: MEAN, top: TOP, base: BASE });
  const shallow = s.candidates.find(c => c.label.includes('Shallowest'));
  assert.ok(shallow);
  for (const c of s.candidates) {
    assert.ok(shallow.deepest <= c.deepest + 1e-9,
      `${c.label} (${c.deepest.toFixed(1)} m) is shallower than Shallowest (${shallow.deepest.toFixed(1)} m)`);
  }
});

test('drillability bounds are enforced, and the ideal is flagged when it breaks them', () => {
  // A steep zone demands a flat hole: 75-degree zone -> 15-degree ideal, which
  // no surface rig will drill straight.
  const steep = { dip: 75, dipDirection: 200 };
  const ideal = perpendicularOrientation(steep);
  near(ideal.dip, 15, 1e-9, 'ideal dip for a steep zone');

  const s = suggestHoles({ collar: COLLAR, plane: steep, top: TOP, base: BASE });
  assert.equal(s.ideal.drillable, false, 'a 15-degree hole is not drillable');

  const perp = s.candidates.find(c => c.label.includes('Perpendicular'));
  assert.ok(perp && perp.drillable === false, 'the perpendicular row is flagged undrillable');
  assert.ok(/drillable band/.test(perp.note), `note should explain why: "${perp.note}"`);

  // Everything else stays inside the band.
  for (const c of s.candidates) {
    if (c.label.includes('Perpendicular')) continue;
    assert.ok(c.dip >= 45 && c.dip <= 85, `${c.label} dip ${c.dip} outside 45-85`);
  }
});

test('candidates never fall below the minimum intersection angle', () => {
  const s = suggestHoles({
    collar: COLLAR, plane: MEAN, top: TOP, base: BASE, options: { minAngle: 60 }
  });
  for (const c of s.candidates) {
    if (c.label.includes('Perpendicular')) continue; // the ideal is exempt by design
    assert.ok(c.angle >= 60, `${c.label} cuts at only ${c.angle.toFixed(1)}°`);
  }
});

test('a depth budget removes the holes that would blow it', () => {
  const generous = suggestHoles({ collar: COLLAR, plane: MEAN, top: TOP, base: BASE });
  const tight = suggestHoles({
    collar: COLLAR, plane: MEAN, top: TOP, base: BASE, options: { maxEoh: 80 }
  });
  assert.ok(tight.searched < generous.searched, 'a tighter budget searches fewer valid holes');
  for (const c of tight.candidates) {
    if (c.label.includes('Perpendicular')) continue;
    assert.ok(c.eoh <= 80 + 1, `${c.label} EOH ${c.eoh} exceeds the 80 m budget`);
  }
});

test('computePlan attaches suggestions, and honours opting out', () => {
  const withSuggestions = computePlan({
    collar: COLLAR, hole: HOLE, plane: MEAN, top: TOP, base: BASE
  });
  assert.ok(withSuggestions.suggestions, 'suggestions are on by default');
  assert.ok(withSuggestions.suggestions.candidates.length > 0);

  const without = computePlan({
    collar: COLLAR, hole: HOLE, plane: MEAN, top: TOP, base: BASE,
    options: { suggest: false }
  });
  assert.equal(without.suggestions, null);
});

// --- drill patterns ---------------------------------------------------------

const PLAN = planZone({ collar: COLLAR, hole: HOLE, plane: MEAN, top: TOP, base: BASE });
const ORIGIN = {
  easting: PLAN.top.point.e, northing: PLAN.top.point.n, elevation: PLAN.top.point.u
};

const pattern = (over = {}) => generateDrillPattern({
  origin: ORIGIN, baseAnchor: BASE, plane: MEAN, hole: HOLE,
  collarElevation: 313, spacingStrike: 20, spacingDip: 20,
  countStrike: 3, countDip: 2, ...over
});

test('a 3 x 2 pattern produces six holes on a flat collar pad', () => {
  const p = pattern();
  assert.equal(p.totalHoles, 6);
  assert.equal(p.rows, 2);
  assert.equal(p.cols, 3);
  for (const h of p.holes) {
    near(h.collar.elevation, 313, 1e-9, `${h.id} sits on the pad`);
    assert.ok(h.depthToTop > 0, `${h.id} drills downward to its target`);
  }
});

test('spacing is measured on the zone plane, not on the ground', () => {
  const p = pattern();
  const at = (col, row) => p.holes.find(h => h.col === col && h.row === row);
  const dist = (a, b) => Math.hypot(
    a.target.e - b.target.e, a.target.n - b.target.n, a.target.u - b.target.u
  );

  // Neighbours along strike are exactly one strike spacing apart...
  near(dist(at(0, 0), at(1, 0)), 20, 1e-6, 'along strike');
  near(dist(at(1, 0), at(2, 0)), 20, 1e-6, 'along strike again');
  // ...and down dip, one dip spacing.
  near(dist(at(1, 0), at(1, 1)), 20, 1e-6, 'down dip');

  // Every target must actually lie ON the plane, or "spacing on the plane"
  // is a fiction. Distance from the plane through the origin must be zero.
  const n = planeNormal(MEAN.dip, MEAN.dipDirection);
  for (const h of p.holes) {
    const d = (h.target.e - ORIGIN.easting) * n.e
            + (h.target.n - ORIGIN.northing) * n.n
            + (h.target.u - ORIGIN.elevation) * n.u;
    near(d, 0, 1e-6, `${h.id} lies on the zone plane`);
  }
});

test('the pattern steps down-dip only, never up into the outcrop', () => {
  const p = pattern();
  const row0 = p.holes.filter(h => h.row === 0);
  const row1 = p.holes.filter(h => h.row === 1);
  const avg = (list) => list.reduce((s, h) => s + h.target.u, 0) / list.length;
  assert.ok(avg(row1) < avg(row0), 'the second row is deeper, not shallower');

  // And deeper targets mean longer holes.
  const mid0 = p.holes.find(h => h.col === 1 && h.row === 0);
  const mid1 = p.holes.find(h => h.col === 1 && h.row === 1);
  assert.ok(mid1.depthToTop > mid0.depthToTop, 'down-dip holes are longer');
});

test('the strike fan is centred, so the reference hole keeps its place', () => {
  const p = pattern();
  const centre = p.holes.find(h => h.col === 1 && h.row === 0);
  // Middle column, first row = the intersection the pattern was anchored to.
  near(centre.alongStrike, 0, 1e-9, 'centre column has no strike offset');
  near(centre.target.e, ORIGIN.easting, 1e-6, 'easting');
  near(centre.target.n, ORIGIN.northing, 1e-6, 'northing');
  near(centre.target.u, ORIGIN.elevation, 1e-6, 'elevation');
  near(centre.depthToTop, PLAN.top.depth, 1e-6, 'and it reproduces the original hole');

  const offsets = p.holes.filter(h => h.row === 0).map(h => h.alongStrike).sort((a, b) => a - b);
  assert.deepEqual(offsets, [-20, 0, 20]);
});

test('an even column count straddles the centre line', () => {
  const p = pattern({ countStrike: 2, countDip: 1 });
  const offsets = p.holes.map(h => h.alongStrike).sort((a, b) => a - b);
  assert.deepEqual(offsets, [-10, 10]);
});

test('each hole gets a unique id, and totals add up', () => {
  const p = pattern();
  const ids = p.holes.map(h => h.id);
  assert.equal(new Set(ids).size, ids.length, 'ids are unique');
  assert.ok(ids.includes('PLAN_01A') && ids.includes('PLAN_02C'));

  const expected = p.holes.filter(h => h.ok).reduce((s, h) => s + h.eoh, 0);
  assert.equal(p.totalMetres, expected, 'total metres is the sum of drillable EOHs');
  assert.ok(p.totalMetres > 0);
  assert.equal(p.deepestHole, Math.max(...p.holes.filter(h => h.ok).map(h => h.eoh)));
});

test('every hole stops below the zone it was drilled for', () => {
  const p = pattern();
  for (const h of p.holes) {
    assert.ok(Number.isFinite(h.depthToBase), `${h.id} has a base intersection`);
    assert.ok(h.eoh > h.depthToBase, `${h.id} EOH ${h.eoh} must clear its base ${h.depthToBase}`);
    // Core length stays close to the true thickness for this near-normal cut.
    assert.ok(h.coreLength > 8 && h.coreLength < 9.5, `${h.id} core ${h.coreLength}`);
  }
});

test('holes that break the depth budget are flagged, not silently included', () => {
  const p = pattern({ countDip: 6, options: { maxEoh: 100 } });
  const bad = p.holes.filter(h => !h.ok);
  assert.ok(bad.length > 0, 'deep down-dip holes should exceed a 100 m budget');
  for (const h of bad) assert.ok(/exceeds/.test(h.note), `expected a reason: "${h.note}"`);
  assert.ok(p.warnings.length > 0, 'and the pattern says so overall');
  // Excluded from the metres total, so a budget figure is never inflated by
  // holes the same call just declared undrillable.
  const okMetres = p.holes.filter(h => h.ok).reduce((s, h) => s + h.eoh, 0);
  assert.equal(p.totalMetres, okMetres);
  assert.equal(p.drillableHoles, p.holes.filter(h => h.ok).length);
});

test('tightening the spacing raises hole count and metres together', () => {
  const coarse = pattern({ spacingStrike: 40, spacingDip: 40, countStrike: 2, countDip: 2 });
  const fine = pattern({ spacingStrike: 20, spacingDip: 20, countStrike: 4, countDip: 4 });
  assert.ok(fine.totalHoles > coarse.totalHoles);
  assert.ok(fine.totalMetres > coarse.totalMetres);
});

test('a horizontal hole can never surface, so no pattern is returned', () => {
  assert.equal(pattern({ hole: { azimuth: 30, dip: 0 } }), null);
});

test('computePlan builds a pattern only when asked', () => {
  const off = computePlan({ collar: COLLAR, hole: HOLE, plane: MEAN, top: TOP, base: BASE });
  assert.equal(off.pattern, null);

  const on = computePlan({
    collar: COLLAR, hole: HOLE, plane: MEAN, top: TOP, base: BASE,
    options: { pattern: { spacingStrike: 25, spacingDip: 25, countStrike: 3, countDip: 2 } }
  });
  assert.ok(on.pattern);
  assert.equal(on.pattern.totalHoles, 6);
  assert.equal(on.pattern.spacingStrike, 25);
  // Anchored to where this very hole cuts the zone.
  const centre = on.pattern.holes.find(h => h.col === 1 && h.row === 0);
  near(centre.depthToTop, on.top.depth, 1e-6, 'centre hole is the reference hole');
});

test('computePlan skips calibration when no depth was observed', () => {
  const result = computePlan({
    collar: COLLAR, hole: HOLE, plane: MEAN, top: TOP, base: BASE
  });
  assert.equal(result.calibration, null);
  assert.equal(result.projected.length, 0);
});

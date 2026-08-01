// Drillhole depth planning: where does a proposed hole cut a dipping zone?
//
// A geologist has a structural measurement on a zone exposed at surface (a
// trench sample point with strike/dip/dip direction) and wants the downhole
// depth at which a proposed hole will intersect that zone at depth. Doing it
// by hand means projecting the plane down-dip, intersecting it with the
// trajectory, and then -- the part that actually matters -- working out how
// wrong the answer could be.
//
// Deliberately dependency-free (no three.js, no api_client), for the same
// reason the true-thickness port was: it has to run under `node --test` and
// inside the standalone HTML export, neither of which has a scene.
//
// ---------------------------------------------------------------------------
// Conventions -- every one of these has a plausible-looking wrong version.
//
// Vectors are (e, n, u): Easting, Northing, Up. NOT three.js order.
//
// A plane is (dip d, dip direction a). Its UPWARD unit normal is
//
//     n = (sin d * sin a,  sin d * cos a,  cos d)
//
// The horizontal part points DOWN-dip, not up-dip: a plane descending to the
// east has a normal leaning east, the same way a hillside's normal leans
// downhill. Getting this backwards yields a plane mirrored about the
// horizontal, which still looks plausible in 3D and puts the hole on the
// wrong side of the zone. (backend/src/api/collars.py used the downward form
// of this same normal before it was deleted in 33b1bec; same plane, sign
// flipped, and the sign cancels everywhere it is used here.)
//
// A hole is (dip, azimuth) with dip SIGNED: -60 means 60 degrees below
// horizontal. Callers taking a geologist's "dip 60" from a form must pass it
// through signedDip() first -- see backend/src/services/dip_convention.py for
// why this convention keeps biting.
//
//     d = (cos I * sin A,  cos I * cos A,  sin I)
//
// "Intersection angle" here is the angle between the hole axis and the plane
// SURFACE (90 degrees = the hole punches straight through). The deleted
// true-thickness code used the same name for the complementary angle measured
// from the normal, so an 82-degree intersection was reported as 8. Both are
// defensible; only one matches how the number gets quoted in a drilling
// proposal.
// ---------------------------------------------------------------------------

const DEG = Math.PI / 180;

// Below this, the hole runs parallel to the plane and never meets it.
const PARALLEL_EPS = 1e-6;

/**
 * Strict numeric coercion. Plain `Number()` turns null, '' and false into 0,
 * so a missing collar elevation or an unmeasured sample coordinate would sail
 * through `Number.isFinite` as a perfectly good zero -- and zero is a valid
 * elevation. Everything here that reads user or database input goes through
 * this instead.
 */
function num(v) {
  if (v === null || v === undefined || v === '') return NaN;
  if (typeof v === 'boolean') return NaN;
  return Number(v);
}

/** True only for a value that was genuinely supplied and is a real number. */
export function isNum(v) {
  return Number.isFinite(num(v));
}

/** Geologist's "dip 60" (below horizontal) -> the signed -60 the math wants. */
export function signedDip(dipDeg) {
  return -Math.abs(num(dipDeg));
}

/** Dip direction from strike. Their field data uses strike - 90; the
 *  right-hand rule uses strike + 90. Neither is inferable from the numbers
 *  alone, so the caller states which. */
export function dipDirectionFromStrike(strikeDeg, convention = 'minus90') {
  const offset = convention === 'plus90' ? 90 : -90;
  return ((num(strikeDeg) + offset) % 360 + 360) % 360;
}

export function strikeFromDipDirection(dipDirDeg, convention = 'minus90') {
  const offset = convention === 'plus90' ? -90 : 90;
  return ((num(dipDirDeg) + offset) % 360 + 360) % 360;
}

/** Upward unit normal of a plane. */
export function planeNormal(dipDeg, dipDirDeg) {
  const d = dipDeg * DEG;
  const a = dipDirDeg * DEG;
  return {
    e: Math.sin(d) * Math.sin(a),
    n: Math.sin(d) * Math.cos(a),
    u: Math.cos(d)
  };
}

/** Unit direction of a straight hole. `dipDeg` is signed (negative = down). */
export function holeDirection(dipDeg, azimuthDeg) {
  const i = dipDeg * DEG;
  const a = azimuthDeg * DEG;
  return {
    e: Math.cos(i) * Math.sin(a),
    n: Math.cos(i) * Math.cos(a),
    u: Math.sin(i)
  };
}

/** Inverse of planeNormal: a unit normal back to (dip, dipDirection). */
export function normalToPlane(vec) {
  const v = normalize(vec);
  // Force the upward hemisphere so dip lands in [0, 90].
  const up = v.u < 0 ? scale(v, -1) : v;
  const dip = Math.acos(clamp(up.u, -1, 1)) / DEG;
  let dipDirection = Math.atan2(up.e, up.n) / DEG;
  dipDirection = (dipDirection % 360 + 360) % 360;
  return { dip, dipDirection, strike: strikeFromDipDirection(dipDirection) };
}

export function dot(a, b) { return a.e * b.e + a.n * b.n + a.u * b.u; }
function scale(v, k) { return { e: v.e * k, n: v.n * k, u: v.u * k }; }
function add(a, b) { return { e: a.e + b.e, n: a.n + b.n, u: a.u + b.u }; }
function sub(a, b) { return { e: a.e - b.e, n: a.n - b.n, u: a.u - b.u }; }
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function normalize(v) {
  const len = Math.sqrt(dot(v, v));
  return len < 1e-12 ? { e: 0, n: 0, u: 1 } : scale(v, 1 / len);
}

/** A point record ({easting, northing, elevation}) as an (e, n, u) vector. */
export function toVec(p) {
  return { e: num(p.easting), n: num(p.northing), u: num(p.elevation) };
}

/**
 * Vector mean of several plane measurements, averaging POLES rather than
 * angles. Averaging dip directions numerically breaks across 0/360 and, worse,
 * treats two planes 180 degrees apart in dip direction as unrelated when they
 * are the same surface flipped. Normals are folded into a common hemisphere
 * first, so a reading logged with the opposite dip-direction convention still
 * pulls the mean the right way.
 *
 * @param {Array<{dip:number, dipDirection:number}>} readings
 */
export function meanPlane(readings) {
  const list = (readings || []).filter(
    r => Number.isFinite(num(r.dip)) && Number.isFinite(num(r.dipDirection))
  );
  if (list.length === 0) return null;
  if (list.length === 1) {
    const only = list[0];
    return {
      dip: num(only.dip),
      dipDirection: num(only.dipDirection),
      strike: strikeFromDipDirection(num(only.dipDirection)),
      count: 1,
      spreadDeg: 0
    };
  }

  const normals = list.map(r => planeNormal(num(r.dip), num(r.dipDirection)));
  const reference = normals[0];
  let sum = { e: 0, n: 0, u: 0 };
  for (const nrm of normals) {
    sum = add(sum, dot(nrm, reference) < 0 ? scale(nrm, -1) : nrm);
  }

  const mean = normalize(sum);
  const plane = normalToPlane(mean);

  // Angular spread: the widest departure of any pole from the mean pole. This
  // is the honest measure of "do these readings agree", and it belongs next to
  // the mean wherever the mean is shown.
  let spreadDeg = 0;
  for (const nrm of normals) {
    const aligned = dot(nrm, reference) < 0 ? scale(nrm, -1) : nrm;
    spreadDeg = Math.max(spreadDeg, Math.acos(clamp(Math.abs(dot(aligned, mean)), -1, 1)) / DEG);
  }

  return { ...plane, count: list.length, spreadDeg };
}

/**
 * Depth along the hole at which it crosses the plane through `anchor`.
 *
 *     L = ((Q - C) . n) / (d . n)
 *
 * A negative L means the plane lies BEHIND the collar -- the hole is drilled
 * away from the zone. That is a real, reportable answer, not an error, so it
 * is returned as-is with `behindCollar` set.
 */
export function intersectDepth({ collar, hole, anchor, plane }) {
  const c = toVec(collar);
  const q = toVec(anchor);
  const nrm = planeNormal(plane.dip, plane.dipDirection);
  const dir = holeDirection(hole.dip, hole.azimuth);

  const denom = dot(dir, nrm);
  if (Math.abs(denom) < PARALLEL_EPS) {
    return { depth: null, parallel: true, behindCollar: false, point: null, verticalDepth: null };
  }

  const depth = dot(sub(q, c), nrm) / denom;
  const point = add(c, scale(dir, depth));

  return {
    depth,
    parallel: false,
    behindCollar: depth < 0,
    point,
    verticalDepth: c.u - point.u
  };
}

/** Angle between the hole axis and the plane surface, in degrees (0-90). */
export function intersectionAngleDeg(hole, plane) {
  const nrm = planeNormal(plane.dip, plane.dipDirection);
  const dir = holeDirection(hole.dip, hole.azimuth);
  return Math.asin(clamp(Math.abs(dot(dir, nrm)), 0, 1)) / DEG;
}

/** True thickness from the length measured along the hole. */
export function trueThickness(apparentLength, angleDeg) {
  return Math.abs(apparentLength) * Math.sin(angleDeg * DEG);
}

/**
 * How far the intersection depth moves per metre of collar elevation:
 * dL/dCz = -n_u / (d . n). The single most useful number in the whole tool,
 * because collar elevation is usually the least trustworthy input.
 */
export function elevationSensitivity(hole, plane) {
  const nrm = planeNormal(plane.dip, plane.dipDirection);
  const dir = holeDirection(hole.dip, hole.azimuth);
  const denom = dot(dir, nrm);
  if (Math.abs(denom) < PARALLEL_EPS) return null;
  return -nrm.u / denom;
}

/**
 * The base case: where a zone bounded by `top` and `base` anchor points lands
 * on the hole.
 */
export function planZone({ collar, hole, plane, top, base }) {
  const angle = intersectionAngleDeg(hole, plane);
  const topHit = intersectDepth({ collar, hole, anchor: top, plane });
  const baseHit = base ? intersectDepth({ collar, hole, anchor: base, plane }) : null;

  const coreLength =
    baseHit && topHit.depth !== null && baseHit.depth !== null
      ? Math.abs(baseHit.depth - topHit.depth)
      : null;

  return {
    plane,
    hole,
    collar,
    intersectionAngleDeg: angle,
    elevationSensitivity: elevationSensitivity(hole, plane),
    top: topHit,
    base: baseHit,
    coreLength,
    trueThickness: coreLength === null ? null : trueThickness(coreLength, angle)
  };
}

/**
 * How much the answer moves when the inputs are wrong.
 *
 * Every row re-runs the whole intersection under one perturbed assumption --
 * no linearisation -- so the envelope stays honest at shallow intersection
 * angles where the depth blows up non-linearly. Individual readings are
 * included as their own rows because a mean of two readings 20 degrees apart
 * hides exactly the disagreement a driller needs to see.
 */
export function sensitivity({ collar, hole, plane, top, base, readings }, options = {}) {
  const dipDelta = options.dipDelta ?? 5;
  const dipDirDelta = options.dipDirDelta ?? 10;
  const collarZDelta = options.collarZDelta ?? 2;

  const rows = [];
  const push = (label, group, over) => {
    const result = planZone({
      collar: over.collar || collar,
      hole,
      plane: over.plane || plane,
      top,
      base
    });
    rows.push({
      label,
      group,
      topDepth: result.top.depth,
      baseDepth: result.base ? result.base.depth : null,
      dip: (over.plane || plane).dip,
      dipDirection: (over.plane || plane).dipDirection,
      collarElevation: (over.collar || collar).elevation
    });
  };

  push('Base case', 'base', {});

  push(`Dip ${fmtSigned(-dipDelta)}°`, 'dip', {
    plane: { ...plane, dip: clamp(plane.dip - dipDelta, 0, 90) }
  });
  push(`Dip ${fmtSigned(+dipDelta)}°`, 'dip', {
    plane: { ...plane, dip: clamp(plane.dip + dipDelta, 0, 90) }
  });

  push(`Dip dir ${fmtSigned(-dipDirDelta)}°`, 'dipDir', {
    plane: { ...plane, dipDirection: plane.dipDirection - dipDirDelta }
  });
  push(`Dip dir ${fmtSigned(+dipDirDelta)}°`, 'dipDir', {
    plane: { ...plane, dipDirection: plane.dipDirection + dipDirDelta }
  });

  push(`Collar Z ${fmtSigned(-collarZDelta)} m`, 'collarZ', {
    collar: { ...collar, elevation: num(collar.elevation) - collarZDelta }
  });
  push(`Collar Z ${fmtSigned(+collarZDelta)} m`, 'collarZ', {
    collar: { ...collar, elevation: num(collar.elevation) + collarZDelta }
  });

  for (const r of (readings || [])) {
    if (!Number.isFinite(num(r.dip)) || !Number.isFinite(num(r.dipDirection))) continue;
    push(
      r.label || `Reading ${Math.round(r.dip)}/${Math.round(r.dipDirection)}`,
      'reading',
      { plane: { dip: num(r.dip), dipDirection: num(r.dipDirection) } }
    );
  }

  const depths = [];
  for (const row of rows) {
    if (Number.isFinite(row.topDepth)) depths.push(row.topDepth);
    if (Number.isFinite(row.baseDepth)) depths.push(row.baseDepth);
  }

  // Which input actually drives the answer -- reported so the geologist knows
  // which measurement is worth re-taking before spending a rig on it.
  //
  // Measured on the ZONE TOP alone. Spanning top-to-base instead would fold the
  // zone's own thickness into every group equally, which is not an uncertainty
  // at all and swamps the differences between groups.
  const widthOf = (group) => {
    const vals = rows.filter(r => r.group === group || r.group === 'base')
      .map(r => r.topDepth)
      .filter(Number.isFinite);
    return vals.length ? Math.max(...vals) - Math.min(...vals) : 0;
  };

  return {
    rows,
    min: depths.length ? Math.min(...depths) : null,
    max: depths.length ? Math.max(...depths) : null,
    driver: {
      dip: widthOf('dip'),
      dipDirection: widthOf('dipDir'),
      collarElevation: widthOf('collarZ'),
      readingSpread: widthOf('reading')
    }
  };
}

function fmtSigned(v) {
  return v >= 0 ? `+${v}` : `${v}`;
}

/**
 * Every trench sample projected onto its equivalent downhole depth, by
 * intersecting the hole with a plane PARALLEL to the zone through that
 * sample's own coordinates.
 *
 * This is what turns "the zone is at 57 m" into "metre 14 of the trench, the
 * 5.91 g/t sample, is at 58.1 m" -- which is the number that actually governs
 * where sampling starts.
 */
export function projectTrenchSamples({ samples, collar, hole, plane }) {
  const out = [];
  for (const s of (samples || [])) {
    if (!Number.isFinite(num(s.easting)) ||
        !Number.isFinite(num(s.northing)) ||
        !Number.isFinite(num(s.elevation))) continue;

    const hit = intersectDepth({ collar, hole, anchor: s, plane });
    if (hit.depth === null) continue;

    out.push({
      sample_id: s.sample_id ?? null,
      trench_id: s.trench_id ?? null,
      meter: Number.isFinite(num(s.from_depth)) ? num(s.from_depth) : null,
      grade: Number.isFinite(num(s.grade_value)) ? num(s.grade_value) : null,
      easting: num(s.easting),
      northing: num(s.northing),
      elevation: num(s.elevation),
      depth: hit.depth,
      point: hit.point
    });
  }
  out.sort((a, b) => a.depth - b.depth);
  return out;
}

/**
 * The hole was drilled and the zone showed up at `observedDepth`. Which
 * assumption was wrong?
 *
 * Two candidates are solved independently, because in practice they are
 * indistinguishable from a single intersection -- collar elevation and dip
 * trade off almost one-for-one over the range that matters. Returning both,
 * rather than picking one, is the honest output; only core logging or a second
 * intersection can choose between them.
 */
export function calibrate({ observedDepth, collar, hole, plane, anchor }) {
  const observed = num(observedDepth);
  const predicted = intersectDepth({ collar, hole, anchor, plane }).depth;
  if (!Number.isFinite(observed) || !Number.isFinite(predicted)) return null;

  const residual = observed - predicted;

  // Collar elevation: L is exactly linear in it, so this is closed form.
  const slope = elevationSensitivity(hole, plane);
  const elevationBranch = slope
    ? {
        collarElevation: num(collar.elevation) + residual / slope,
        shift: residual / slope,
        metresPerMetre: slope
      }
    : null;

  // Dip: not linear, so scan for a bracketing pair then bisect. Scanning
  // first matters -- L(dip) can be non-monotonic across the full 0-90 range,
  // and a blind bisection would converge on whichever root it stumbled into
  // rather than the one nearest the measured dip.
  const dipBranch = solveForDip({ observed, collar, hole, plane, anchor });

  return { predicted, observed, residual, elevationBranch, dipBranch };
}

function solveForDip({ observed, collar, hole, plane, anchor }) {
  const depthAt = (dip) =>
    intersectDepth({ collar, hole, anchor, plane: { ...plane, dip } }).depth;

  const f = (dip) => {
    const d = depthAt(dip);
    return Number.isFinite(d) ? d - observed : NaN;
  };

  const STEP = 0.25;
  let best = null;
  let prevDip = 0.5;
  let prevVal = f(prevDip);

  for (let dip = 0.5 + STEP; dip <= 89.5; dip += STEP) {
    const val = f(dip);
    if (Number.isFinite(prevVal) && Number.isFinite(val) && prevVal * val <= 0) {
      // Bisect this bracket.
      let lo = prevDip, hi = dip, loVal = prevVal;
      for (let i = 0; i < 60; i++) {
        const mid = (lo + hi) / 2;
        const midVal = f(mid);
        if (!Number.isFinite(midVal)) break;
        if (loVal * midVal <= 0) { hi = mid; } else { lo = mid; loVal = midVal; }
      }
      const root = (lo + hi) / 2;
      // Keep the root closest to the dip actually measured.
      if (best === null || Math.abs(root - plane.dip) < Math.abs(best - plane.dip)) {
        best = root;
      }
    }
    prevDip = dip;
    prevVal = val;
  }

  if (best === null) return null;
  return { dip: best, shift: best - plane.dip };
}

/**
 * Turn the uncertainty envelope into the three numbers that go on a drill
 * instruction: where to start logging closely, the primary target window, and
 * where to stop.
 *
 * EOH sits a full margin below the DEEPEST estimate rather than below the base
 * case -- a hole stopped at the base case has a coin-flip chance of ending
 * inside the zone it was drilled to test, and a footwall splay is invisible
 * either way.
 */
export function drillingProposal(plan, envelope, options = {}) {
  const startMargin = options.startMargin ?? 5;
  const eohMargin = options.eohMargin ?? 15;

  const min = envelope && Number.isFinite(envelope.min) ? envelope.min : plan.top.depth;
  const max = envelope && Number.isFinite(envelope.max)
    ? envelope.max
    : (plan.base ? plan.base.depth : plan.top.depth);

  if (!Number.isFinite(min) || !Number.isFinite(max)) return null;

  return {
    startLogging: Math.max(0, Math.round(min - startMargin)),
    targetFrom: plan.top.depth,
    targetTo: plan.base ? plan.base.depth : plan.top.depth,
    envelopeFrom: min,
    envelopeTo: max,
    eoh: Math.round(max + eohMargin),
    startMargin,
    eohMargin
  };
}

/**
 * One call that runs the whole chain, so the panel and any test drive exactly
 * the same path.
 */
export function computePlan({
  collar, hole, plane, top, base,
  readings = [], trenchSamples = [], observedDepth = null, options = {}
}) {
  const plan = planZone({ collar, hole, plane, top, base });
  const envelope = sensitivity({ collar, hole, plane, top, base, readings }, options);
  const proposal = drillingProposal(plan, envelope, options);
  const projected = projectTrenchSamples({ samples: trenchSamples, collar, hole, plane });
  const calibration = Number.isFinite(num(observedDepth))
    ? calibrate({ observedDepth, collar, hole, plane, anchor: top })
    : null;

  return { ...plan, envelope, proposal, projected, calibration };
}

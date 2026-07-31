import * as THREE from 'three';

// Absolute-depth geometry helpers, mirroring
// backend/src/services/downhole_log.py.
//
// Every position here is derived from an absolute downhole distance measured
// from the collar (0.0 m) along the full desurveyed trajectory -- never from
// a relative offset or a running index over the intervals that happen to
// exist. A hole whose first assay is 37 m - 38 m must draw that tube 37 m
// down the curve, not at the collar.

const DEPTH_EPSILON = 1e-6;

// Scene convention (matches drillhole_traces.js): Easting -> X,
// Elevation -> Y, Northing -> Z.
export function tracePointToVector3(p) {
  return new THREE.Vector3(p.x, p.z, p.y);
}

/**
 * 3D position at an absolute downhole `depth`, linearly interpolated between
 * the bracketing trace stations. Clamps at both ends.
 */
export function interpolateTracePosition(trace, depth) {
  if (!trace || trace.length === 0) return new THREE.Vector3();

  if (depth <= trace[0].depth) return tracePointToVector3(trace[0]);
  const last = trace[trace.length - 1];
  if (depth >= last.depth) return tracePointToVector3(last);

  for (let i = 1; i < trace.length; i++) {
    const p1 = trace[i - 1];
    const p2 = trace[i];
    if (p1.depth <= depth && depth <= p2.depth) {
      const span = p2.depth - p1.depth;
      if (Math.abs(span) < 1e-9) return tracePointToVector3(p1);
      const t = (depth - p1.depth) / span;
      return tracePointToVector3(p1).lerp(tracePointToVector3(p2), t);
    }
  }
  return tracePointToVector3(last);
}

/**
 * Splits the absolute depth range [fromDepth, toDepth] at every trace station
 * that falls strictly inside it, returning
 * `[{ start: Vector3, end: Vector3 }, ...]`.
 *
 * Each returned sub-segment is straight and follows the local tangent of the
 * desurveyed curve, so an interval spanning a dogleg renders as a chain of
 * flush-jointed tube sections tracking the curve rather than one straight
 * cylinder cutting the corner. Adjacent intervals sharing a depth boundary
 * produce the exact same point there, so their end caps meet without a gap or
 * an overlap.
 */
export function subdivideIntervalAlongTrace(trace, fromDepth, toDepth) {
  const start = interpolateTracePosition(trace, fromDepth);
  const end = interpolateTracePosition(trace, toDepth);

  if (!trace || trace.length < 2 || toDepth - fromDepth <= DEPTH_EPSILON) {
    return [{ start, end }];
  }

  // Interior station depths, strictly between the interval's own bounds.
  const cuts = [];
  for (const station of trace) {
    if (station.depth > fromDepth + DEPTH_EPSILON &&
        station.depth < toDepth - DEPTH_EPSILON) {
      cuts.push(station.depth);
    }
  }
  if (cuts.length === 0) return [{ start, end }];

  const segments = [];
  let prevPoint = start;
  for (const depth of cuts) {
    const point = interpolateTracePosition(trace, depth);
    segments.push({ start: prevPoint, end: point });
    prevPoint = point;
  }
  segments.push({ start: prevPoint, end });
  return segments;
}

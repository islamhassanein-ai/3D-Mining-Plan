import * as THREE from 'three';
import { interpolateTracePosition } from './trace_geometry.js';

// Leapfrog-style continuous drillhole tube.
//
// The previous approach gave every assay interval its own capped cylinder.
// On a curved hole that shows a seam at EVERY interval boundary -- often one
// per metre -- because two cylinders meeting at an angle leave a wedge gap on
// the outside of the bend and their flat caps catch the light. It reads as a
// chain of beads rather than a length of core.
//
// Here the whole hole is one swept tube instead. Rings of vertices are carried
// along the desurveyed centreline with a parallel-transport frame, and colour
// is applied per vertex. Interval boundaries duplicate a ring in place: two
// rings at identical positions with different colours, so the colour changes
// crisply while the surface stays unbroken. There is no geometry between
// intervals to leave a gap, and end caps exist only where sampling actually
// starts and stops.

const EPS = 1e-6;

/**
 * A parallel-transport frame avoids the twisting that a naive
 * "up-vector" frame produces when a hole turns through vertical: each frame is
 * the previous one rotated by the minimal rotation between consecutive
 * tangents, so the tube never spins about its own axis.
 */
function buildFrames(points) {
  const tangents = [];
  for (let i = 0; i < points.length; i++) {
    const prev = points[Math.max(0, i - 1)];
    const next = points[Math.min(points.length - 1, i + 1)];
    const t = new THREE.Vector3().subVectors(next, prev);
    if (t.lengthSq() < EPS) t.set(0, -1, 0);
    tangents.push(t.normalize());
  }

  // Seed normal: any axis not parallel to the first tangent.
  const seed = Math.abs(tangents[0].y) > 0.9
    ? new THREE.Vector3(1, 0, 0)
    : new THREE.Vector3(0, 1, 0);
  const normals = [new THREE.Vector3().crossVectors(tangents[0], seed).normalize()];

  const rotation = new THREE.Quaternion();
  for (let i = 1; i < tangents.length; i++) {
    rotation.setFromUnitVectors(tangents[i - 1], tangents[i]);
    normals.push(normals[i - 1].clone().applyQuaternion(rotation).normalize());
  }

  return { tangents, normals };
}

/**
 * Group intervals into runs of continuous sampling. A gap between two
 * intervals means the core was not assayed there, so the tube must stop and
 * restart -- that bare stretch shows the trace line instead.
 */
function groupIntoRuns(intervals) {
  const runs = [];
  let current = null;
  for (const iv of intervals) {
    if (current && Math.abs(iv.from_depth - current[current.length - 1].to_depth) < 1e-4) {
      current.push(iv);
    } else {
      current = [iv];
      runs.push(current);
    }
  }
  return runs;
}

/** Depths at which a ring is needed inside one interval: its own bounds, plus
 *  every survey station in between so the tube tracks the trajectory. */
function ringDepths(trace, from, to) {
  const depths = [from];
  for (const station of trace) {
    if (station.depth > from + EPS && station.depth < to - EPS) depths.push(station.depth);
  }
  depths.push(to);
  return depths;
}

/**
 * Build one hole's tube.
 *
 * `intervals` must already be filtered to sampled intervals and sorted by
 * from_depth. Returns null when there is nothing to draw.
 *
 * The returned geometry carries:
 *   position, normal, color  -- standard shaded surface
 *   aGrade                   -- per-vertex grade, for the GPU cutoff discard
 * plus `intervalRefs`, mapping vertex index -> the interval it belongs to, so
 * a raycast hit can be resolved back to a sample.
 */
export function buildHoleTube(trace, intervals, radius, radialSegments) {
  if (!trace || trace.length < 2 || !intervals.length) return null;

  const positions = [];
  const normals = [];
  const colors = [];
  const grades = [];
  const indices = [];
  const intervalRefs = [];

  const colour = new THREE.Color();
  const centre = new THREE.Vector3();
  const binormal = new THREE.Vector3();
  const offset = new THREE.Vector3();

  for (const run of groupIntoRuns(intervals)) {
    // One frame chain for the whole run, so rings stay aligned across the
    // interval boundaries inside it.
    const runDepths = [];
    for (const iv of run) {
      const d = ringDepths(trace, iv.from_depth, iv.to_depth);
      // Boundary depths are shared between neighbours; keep both copies so the
      // colour can change without the surface breaking.
      for (const depth of d) runDepths.push({ depth, interval: iv });
    }
    if (runDepths.length < 2) continue;

    const points = runDepths.map(r => interpolateTracePosition(trace, r.depth));
    const { tangents, normals: frameNormals } = buildFrames(points);

    const ringStart = [];
    for (let i = 0; i < points.length; i++) {
      ringStart.push(positions.length / 3);
      centre.copy(points[i]);
      binormal.crossVectors(tangents[i], frameNormals[i]).normalize();
      colour.set(runDepths[i].interval.color);

      for (let j = 0; j < radialSegments; j++) {
        const theta = (j / radialSegments) * Math.PI * 2;
        offset.copy(frameNormals[i]).multiplyScalar(Math.cos(theta))
          .addScaledVector(binormal, Math.sin(theta));
        positions.push(centre.x + offset.x * radius,
                       centre.y + offset.y * radius,
                       centre.z + offset.z * radius);
        // Tube normal points straight out from the centreline: smooth by
        // construction, no normal averaging needed.
        normals.push(offset.x, offset.y, offset.z);
        colors.push(colour.r, colour.g, colour.b);
        grades.push(Number(runDepths[i].interval.grade_value));
        intervalRefs.push(runDepths[i].interval);
      }
    }

    // Stitch consecutive rings. Rings that belong to different intervals but
    // sit at the same depth produce zero-area quads, which cost nothing and
    // keep the colour break exactly at the boundary.
    for (let i = 0; i < points.length - 1; i++) {
      const a = ringStart[i];
      const b = ringStart[i + 1];
      for (let j = 0; j < radialSegments; j++) {
        const jn = (j + 1) % radialSegments;
        indices.push(a + j, b + j, a + jn);
        indices.push(a + jn, b + j, b + jn);
      }
    }

    // Flat caps, only where sampling genuinely begins and ends.
    for (const [ringIdx, flip] of [[0, true], [points.length - 1, false]]) {
      const base = positions.length / 3;
      const iv = runDepths[ringIdx].interval;
      colour.set(iv.color);
      centre.copy(points[ringIdx]);
      const capNormal = tangents[ringIdx].clone().multiplyScalar(flip ? -1 : 1);

      positions.push(centre.x, centre.y, centre.z);
      normals.push(capNormal.x, capNormal.y, capNormal.z);
      colors.push(colour.r, colour.g, colour.b);
      grades.push(Number(iv.grade_value));
      intervalRefs.push(iv);

      const rim = ringStart[ringIdx];
      for (let j = 0; j < radialSegments; j++) {
        const src = (rim + j) * 3;
        positions.push(positions[src], positions[src + 1], positions[src + 2]);
        normals.push(capNormal.x, capNormal.y, capNormal.z);
        colors.push(colour.r, colour.g, colour.b);
        grades.push(Number(iv.grade_value));
        intervalRefs.push(iv);
      }
      for (let j = 0; j < radialSegments; j++) {
        const jn = (j + 1) % radialSegments;
        if (flip) indices.push(base, base + 1 + jn, base + 1 + j);
        else indices.push(base, base + 1 + j, base + 1 + jn);
      }
    }
  }

  if (!indices.length) return null;

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  geometry.setAttribute('aGrade', new THREE.Float32BufferAttribute(grades, 1));
  geometry.setIndex(indices);
  geometry.computeBoundingSphere();

  return { geometry, intervalRefs };
}

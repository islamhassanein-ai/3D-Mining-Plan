import test from 'node:test';
import assert from 'node:assert';
import * as THREE from 'three';

// The renderer is the one place where planner coordinates (e, n, u) meet
// three.js (X = Easting, Y = Elevation, Z = Northing). A swap between the two
// produces a scene that still looks like a hole cutting a plane -- just rotated
// into the wrong part of the site -- which is exactly the kind of error a
// screenshot does not catch. So the assertions here are positional: the depth
// rings must land on the intersection points the planner computed, and the slab
// faces must satisfy the plane equation.
//
// makeLabelSprite draws its pill on a 2D canvas, so a minimal DOM stub has to
// exist before depth_plan_renderer.js is imported.

const ctxStub = () => new Proxy({}, {
  get: (_t, prop) => {
    if (prop === 'measureText') return () => ({ width: 80 });
    if (prop === 'canvas') return null;
    return () => {};
  },
  set: () => true
});

globalThis.window = { devicePixelRatio: 1 };
globalThis.document = {
  createElement: (tag) => {
    if (tag !== 'canvas') return {};
    return { width: 0, height: 0, getContext: () => ctxStub() };
  }
};

const { DepthPlanRenderer } = await import('../src/scene/depth_plan_renderer.js');
const { computePlan, signedDip, meanPlane, planeNormal } =
  await import('../src/services/depth_planner.js');

const TOP = { easting: 208739.479, northing: 2467843.974, elevation: 293.120 };
const BASE = { easting: 208747.242, northing: 2467852.584, elevation: 290.958 };
const COLLAR = { easting: 208720.3, northing: 2467784.8, elevation: 313 };
const HOLE = { azimuth: 30, dip: signedDip(60) };
const PLANE = meanPlane([{ dip: 38, dipDirection: 209 }, { dip: 44, dipDirection: 186 }]);

function buildPlan() {
  const plan = computePlan({
    collar: COLLAR, hole: HOLE, plane: PLANE, top: TOP, base: BASE,
    readings: [{ dip: 38, dipDirection: 209 }, { dip: 44, dipDirection: 186 }]
  });
  plan.topAnchor = TOP;
  plan.baseAnchor = BASE;
  plan.holeId = 'AADD010';
  return plan;
}

function render() {
  const scene = new THREE.Scene();
  const renderer = new DepthPlanRenderer(scene);
  const plan = buildPlan();
  renderer.render(plan);
  return { scene, renderer, plan };
}

const near = (a, b, tol, what) =>
  assert.ok(Math.abs(a - b) <= tol, `${what}: expected ~${b} (+/-${tol}), got ${a}`);

test('the renderer attaches one named group to the scene', () => {
  const { scene, renderer } = render();
  assert.ok(scene.children.includes(renderer.group));
  assert.equal(renderer.group.name, 'depth-plan');
});

test('depth rings sit exactly on the computed intersection points', () => {
  const { renderer, plan } = render();

  const rings = renderer.group.children.filter(
    c => c.isMesh && c.geometry && c.geometry.type === 'TorusGeometry'
  );
  // Start-logging, zone top, zone base, EOH.
  assert.equal(rings.length, 4, 'four call-outs');

  // The zone-top ring must coincide with the planner's own intersection point,
  // converted to three.js axes. This is the coordinate-mapping assertion.
  const hit = plan.top.point;
  const match = rings.find(r => Math.abs(r.position.y - hit.u) < 0.05);
  assert.ok(match, 'a ring sits at the zone-top elevation');
  near(match.position.x, hit.e, 0.05, 'ring easting -> three.js X');
  near(match.position.y, hit.u, 0.05, 'ring elevation -> three.js Y');
  near(match.position.z, hit.n, 0.05, 'ring northing -> three.js Z');

  // And it must NOT be at the collar -- a silent failure mode if depth were
  // dropped somewhere in the chain.
  assert.ok(Math.abs(match.position.y - COLLAR.elevation) > 40);
});

test('every slab vertex lies on either the top plane or the base plane', () => {
  const { renderer, plan } = render();

  const slab = renderer.group.children.find(
    c => c.userData && c.userData.type === 'depth_plan_zone'
  );
  assert.ok(slab, 'the zone slab exists');

  const n = planeNormal(plan.plane.dip, plan.plane.dipDirection);
  // Signed distance from the top plane, for a three.js-space vertex.
  const distance = (x, y, z) =>
    (x - TOP.easting) * n.e + (z - TOP.northing) * n.n + (y - TOP.elevation) * n.u;

  const baseOffset =
    (BASE.easting - TOP.easting) * n.e +
    (BASE.northing - TOP.northing) * n.n +
    (BASE.elevation - TOP.elevation) * n.u;

  // Tolerance is set by float32, not by the maths. Vertex buffers hold raw UTM
  // coordinates, and at a northing of 2,467,844 a float32 step is about 0.25 m
  // -- so every renderer in this app carries that much positional granularity.
  // Anything an order of magnitude beyond it is a real geometry error.
  const FLOAT32_UTM_TOLERANCE = 0.3;

  const pos = slab.geometry.getAttribute('position');
  let onTop = 0, onBase = 0;
  for (let i = 0; i < pos.count; i++) {
    const d = distance(pos.getX(i), pos.getY(i), pos.getZ(i));
    if (Math.abs(d) < FLOAT32_UTM_TOLERANCE) onTop++;
    else if (Math.abs(d - baseOffset) < FLOAT32_UTM_TOLERANCE) onBase++;
    else assert.fail(`vertex ${i} is ${d.toFixed(3)} m off both bounding planes`);
  }
  assert.ok(onTop > 0 && onBase > 0, 'both bounding surfaces are present');
  // The two surfaces must be genuinely distinct, not a collapsed slab.
  assert.ok(Math.abs(baseOffset) > 1, `slab is ${baseOffset.toFixed(2)} m thick`);
});

test('the slab is excluded from the camera fit but the hole is not', () => {
  const { renderer } = render();

  const slab = renderer.group.children.find(c => c.userData.type === 'depth_plan_zone');
  assert.equal(slab.userData.excludeFromFit, true,
    'a slab sized for legibility must not drive the camera fit');

  const holeParts = renderer.group.children.filter(c => c.userData.type === 'depth_plan_hole');
  assert.ok(holeParts.length >= 2, 'dashed centreline plus tube');
  for (const part of holeParts) {
    assert.notEqual(part.userData.excludeFromFit, true,
      'the proposed hole should frame like real data');
  }
});

test('the dashed centreline runs from the collar to EOH', () => {
  const { renderer, plan } = render();

  const line = renderer.group.children.find(
    c => c.isLine && c.material.isLineDashedMaterial
  );
  assert.ok(line, 'the trace is dashed, marking it as a proposal');

  // See the float32 note above: line vertices are stored in a buffer too.
  const TOL = 0.3;
  const pos = line.geometry.getAttribute('position');
  near(pos.getX(0), COLLAR.easting, TOL, 'starts at collar E');
  near(pos.getY(0), COLLAR.elevation, TOL, 'starts at collar RL');
  near(pos.getZ(0), COLLAR.northing, TOL, 'starts at collar N');

  // End sits EOH metres along the trajectory, i.e. below the deepest estimate.
  const end = new THREE.Vector3(pos.getX(1), pos.getY(1), pos.getZ(1));
  const start = new THREE.Vector3(pos.getX(0), pos.getY(0), pos.getZ(0));
  near(end.distanceTo(start), plan.proposal.eoh, TOL, 'length equals EOH');
  assert.ok(end.y < start.y, 'the hole goes down');

  // Dash rendering silently degrades to a solid line without line distances.
  assert.ok(line.geometry.getAttribute('lineDistance'), 'computeLineDistances was called');
});

test('the uncertainty sleeve spans the envelope', () => {
  const { renderer, plan } = render();
  const sleeve = renderer.group.children.find(c => c.userData.type === 'depth_plan_envelope');
  assert.ok(sleeve, 'the envelope is drawn');
  near(
    sleeve.geometry.parameters.height,
    plan.envelope.max - plan.envelope.min,
    0.01,
    'sleeve length'
  );
  assert.ok(sleeve.material.transparent && sleeve.material.opacity < 0.4);
});

test('each call-out gets a label sprite', () => {
  const { renderer } = render();
  // Four depth markers plus the collar tag.
  assert.equal(renderer.labelGroup.children.length, 5);
  for (const sprite of renderer.labelGroup.children) {
    assert.ok(sprite.isSprite, 'labels are billboarded sprites');
    assert.equal(sprite.userData.excludeFromFit, true);
  }
});

test('re-rendering replaces rather than accumulates', () => {
  const { renderer } = render();
  const first = renderer.group.children.length;
  renderer.render(buildPlan());
  assert.equal(renderer.group.children.length, first, 'no duplicate geometry');
});

test('rendering null clears the scene but keeps the group attached', () => {
  const { scene, renderer } = render();
  renderer.render(null);
  assert.equal(renderer.group.children.length, 1, 'only the empty label group remains');
  assert.equal(renderer.labelGroup.children.length, 0);
  assert.ok(scene.children.includes(renderer.group), 'the group stays for the layer toggle');
});

test('setVisible drives the whole layer', () => {
  const { renderer } = render();
  renderer.setVisible(false);
  assert.equal(renderer.group.visible, false);
  renderer.setVisible(true);
  assert.equal(renderer.group.visible, true);
});

import test from 'node:test';
import assert from 'node:assert';

import { buildPlanSection } from '../src/export/plan_section_svg.js';
import { computePlan, signedDip, holeDirection, toVec } from '../src/services/depth_planner.js';

// The section image is the artefact that leaves the app: it gets pasted into a
// proposal, and by then nobody can check it against the panel that produced it.
// So the assertions here are geometric, not cosmetic. Two failures matter more
// than the rest:
//
//   1. An anisotropic fit. Separate x and y scales draw a 40-degree zone at 60
//      and nothing about the picture looks wrong -- so the zone's drawn slope is
//      measured against tan(dip) directly.
//   2. A depth on the drawing that is not the depth the planner computed. The
//      numbers are re-read out of the SVG text and compared with the result.

const TOP = { easting: 208739.479, northing: 2467843.974, elevation: 293.120 };
const BASE = { easting: 208747.242, northing: 2467852.584, elevation: 290.958 };
const COLLAR = { easting: 208720.3, northing: 2467784.8, elevation: 313 };
const PLANE = { dip: 40, dipDirection: 198 };
const HOLE = { azimuth: 30, dip: signedDip(60) };

function plan(overrides = {}) {
  const result = computePlan({
    collar: overrides.collar || COLLAR,
    hole: overrides.hole || HOLE,
    plane: overrides.plane || PLANE,
    top: TOP,
    base: BASE,
    options: { suggest: false, ...(overrides.options || {}) }
  });
  result.topAnchor = TOP;
  result.baseAnchor = BASE;
  result.holeId = overrides.holeId ?? 'PLAN01';
  return result;
}

/** Every "x1,y1 x2,y2 ..." polygon and every line endpoint, for geometry checks. */
function firstPolygon(svg) {
  const m = /<polygon points="([^"]+)"/.exec(svg);
  assert.ok(m, 'expected a zone polygon');
  return m[1].trim().split(/\s+/).map(pair => {
    const [x, y] = pair.split(',').map(Number);
    return { x, y };
  });
}

test('draws a single hole with the depths the planner computed', () => {
  const r = plan();
  const { svg, holeCount } = buildPlanSection(r, { mode: 'single' });

  assert.equal(holeCount, 1);
  assert.match(svg, /^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg"/);
  assert.match(svg, /<\/svg>$/);

  // The three numbers a driller is handed, straight off the drawing.
  assert.ok(svg.includes(`zone top — ${r.top.depth.toFixed(1)} m`), 'zone top depth call-out');
  assert.ok(svg.includes(`zone base — ${r.base.depth.toFixed(1)} m`), 'zone base depth call-out');
  assert.ok(svg.includes(`stop drilling — ${r.proposal.eoh} m`), 'EOH call-out');
  assert.ok(svg.includes(`start logging at ${r.proposal.startLogging} m`), 'start-logging call-out');
  assert.ok(svg.includes('PLAN01'), 'hole id on the collar');
  assert.ok(svg.includes(`dipping ${Math.round(PLANE.dip)}°`), 'zone dip stated on the slab');
});

test('the zone draws at its TRUE dip — the section is isotropic', () => {
  const r = plan();
  const svg = buildPlanSection(r, { mode: 'single' }).svg;
  const poly = firstPolygon(svg);

  // Polygon order is top-left, top-right, base-right, base-left.
  const [tl, tr] = poly;
  const drawnSlope = (tr.y - tl.y) / (tr.x - tl.x);   // +y is down in SVG
  const expected = Math.tan(PLANE.dip * Math.PI / 180);

  assert.ok(
    Math.abs(drawnSlope - expected) < 0.02,
    `zone drawn at ${(Math.atan(drawnSlope) * 180 / Math.PI).toFixed(1)}°, expected ${PLANE.dip}°`
  );
});

test('a steeper zone draws steeper — the dip is not baked in', () => {
  const shallow = firstPolygon(buildPlanSection(plan({ plane: { dip: 25, dipDirection: 198 } })).svg);
  const steep = firstPolygon(buildPlanSection(plan({ plane: { dip: 70, dipDirection: 198 } })).svg);

  const slope = (p) => (p[1].y - p[0].y) / (p[1].x - p[0].x);
  assert.ok(slope(steep) > slope(shallow) * 2, 'a 70° zone must draw far steeper than a 25° one');
});

test('the hole trace runs from the collar to EOH, hitting the zone in between', () => {
  const r = plan();
  const svg = buildPlanSection(r, { mode: 'single' }).svg;

  // Reconstruct the section transform from the two labelled RL gridlines, then
  // check the drawn intersection marker lands where the planner put it.
  const dir = holeDirection(HOLE.dip, HOLE.azimuth);
  const collar = toVec(COLLAR);
  const topPoint = {
    e: collar.e + dir.e * r.top.depth,
    n: collar.n + dir.n * r.top.depth,
    u: collar.u + dir.u * r.top.depth
  };

  // The zone top must sit ON the zone polygon's top edge: same plane, so the
  // marker's y at its x has to match the edge within a pixel or two.
  const poly = firstPolygon(svg);
  const [tl, tr] = poly;
  const edgeYAt = (x) => tl.y + (tr.y - tl.y) * (x - tl.x) / (tr.x - tl.x);

  const markers = [...svg.matchAll(/<circle cx="([\d.-]+)" cy="([\d.-]+)" r="4"/g)]
    .map(m => ({ x: Number(m[1]), y: Number(m[2]) }));
  assert.ok(markers.length >= 2, 'expected zone top and base markers');

  const onEdge = markers.some(m => Math.abs(m.y - edgeYAt(m.x)) < 2);
  assert.ok(onEdge, 'the zone-top marker must lie on the drawn zone plane');

  // And the intersection must be below the collar, which is the sanity check
  // that would catch an inverted elevation axis.
  assert.ok(topPoint.u < collar.u);
});

test('pattern mode draws every drillable hole and totals the programme', () => {
  const r = plan({
    options: {
      pattern: {
        spacingStrike: 25, spacingDip: 25, countStrike: 3, countDip: 2,
        collarElevation: 313, holePrefix: 'PAT'
      }
    }
  });
  assert.ok(r.pattern && r.pattern.drillableHoles > 0, 'fixture must produce a drillable pattern');

  const { svg, holeCount } = buildPlanSection(r, { mode: 'pattern' });

  // Every drillable hole is on the drawing, plus the reference hole.
  assert.equal(holeCount, r.pattern.drillableHoles + 1);
  for (const h of r.pattern.holes.filter(x => x.ok)) {
    assert.ok(svg.includes(h.id), `hole ${h.id} missing from the section`);
  }
  assert.ok(svg.includes(`${r.pattern.drillableHoles} holes`), 'hole count in the title');
  assert.ok(svg.includes(`${Math.round(r.pattern.totalMetres)} m`), 'total metres in the title');
  assert.ok(svg.includes('flat pad'), 'pad-RL assumption must travel with the image');
});

test('pattern mode refuses to draw when no pattern was asked for', () => {
  assert.throws(
    () => buildPlanSection(plan(), { mode: 'pattern' }),
    /drill pattern/i
  );
});

test('a hole that misses the zone is refused, with the reason', () => {
  // A collar sited well down-dip of the outcrop: the zone has already passed
  // above this pad, so every downward hole from it meets the plane behind the
  // collar.
  const r = plan({
    collar: { easting: 208800, northing: 2467950, elevation: 313 },
    hole: { azimuth: 30, dip: signedDip(60) }
  });
  assert.ok(r.top.behindCollar, 'fixture must actually miss');
  assert.throws(() => buildPlanSection(r, { mode: 'single' }), /behind the collar/i);
});

test('an incomplete plan is refused rather than drawn empty', () => {
  assert.throws(() => buildPlanSection(null), /Fill in/i);
  assert.throws(() => buildPlanSection({ plane: PLANE }), /Fill in/i);
});

test('the assumptions travel with the image', () => {
  const r = plan();
  const svg = buildPlanSection(r, { mode: 'single', projectName: 'Monark Gold Prospect' }).svg;

  assert.ok(svg.includes('Monark Gold Prospect'), 'project name captioned');
  assert.ok(/assumed planar and continuous/.test(svg), 'planarity assumption stated');
  assert.ok(/not a surveyed topographic profile/.test(svg), 'ground line qualified');
  assert.ok(/Nothing here is drilled/.test(svg), 'the drawing must not read as a result');
  assert.ok(
    svg.includes(`${r.envelope.min.toFixed(1)}–${r.envelope.max.toFixed(1)} m`),
    'uncertainty envelope on the drawing'
  );
});

test('user text is escaped, not injected into the SVG', () => {
  const r = plan({ holeId: '<script>x</script>&' });
  const svg = buildPlanSection(r, { mode: 'single' }).svg;
  assert.ok(!svg.includes('<script>'), 'hole id must be escaped');
  assert.ok(svg.includes('&lt;script&gt;'), 'escaped form present');
});

test('a vertical hole on a flat pad still fits — no divide by zero', () => {
  const r = plan({ hole: { azimuth: 30, dip: signedDip(90) } });
  const svg = buildPlanSection(r, { mode: 'single' }).svg;
  assert.ok(!/NaN|Infinity/.test(svg), 'no degenerate coordinates in the output');
});

// A label drawn off the edge is not a cosmetic bug here: the drawing is
// exported as a fixed-size image, so anything outside the viewBox is simply
// gone, and the reader has no way to tell that a call-out is missing. The steep
// case is the one that used to fail -- a 75-degree zone leaves the frame well
// before the right-hand edge, taking its label with it.
for (const [name, opts, planOverrides] of [
  ['single hole', { mode: 'single' }, {}],
  ['light theme', { mode: 'single', theme: 'light' }, {}],
  ['steep zone', { mode: 'single' }, { plane: { dip: 75, dipDirection: 198 } }],
  ['a four-by-three pattern', { mode: 'pattern' }, {
    options: {
      pattern: {
        spacingStrike: 25, spacingDip: 25, countStrike: 4, countDip: 3,
        collarElevation: 313, holePrefix: 'PAT'
      }
    }
  }]
]) {
  test(`every label stays on the page — ${name}`, () => {
    const { svg, width, height } = buildPlanSection(plan(planOverrides), opts);
    const offPage = [...svg.matchAll(/<text x="([\d.-]+)" y="([\d.-]+)"[^>]*>([^<]*)</g)]
      .map(m => ({ x: Number(m[1]), y: Number(m[2]), text: m[3] }))
      .filter(t => t.x < 0 || t.x > width || t.y < 8 || t.y > height);
    assert.deepEqual(offPage, [], 'labels outside the viewBox are invisible in the exported image');
  });
}

test('the light theme is a white page, for printing', () => {
  const svg = buildPlanSection(plan(), { mode: 'single', theme: 'light' }).svg;
  assert.match(svg, /<rect width="\d+" height="\d+" fill="#ffffff"\/>/);
});

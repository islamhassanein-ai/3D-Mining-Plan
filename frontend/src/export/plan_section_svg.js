// The Depth Planner as a picture you can put in a drilling proposal.
//
// A vertical section through the zone, looking along strike: the collar, the
// ground, the dipping zone as a slab, the proposed hole as a dashed trace, and
// the three numbers a driller is actually given -- where the zone starts, where
// it ends, and where to stop. One hole, or a whole pattern on the same section.
//
// Written as a string-building module with no DOM and no three.js, for the same
// reason depth_planner.js is dependency-free: it runs under `node --test`, and
// it has to work inside the standalone HTML export, which has neither a scene
// nor a server to render on.
//
// ---------------------------------------------------------------------------
// The section plane
//
// The view looks ALONG STRIKE, i.e. the horizontal axis runs down the zone's
// dip direction. That choice is not cosmetic: it is the only azimuth on which
// the zone shows its TRUE dip, so the 40 degrees written on the drawing is the
// 40 degrees that was measured. On any other section the slab would draw at an
// apparent dip and the picture would quietly disagree with its own caption.
//
// The cost is that holes offset along strike collapse onto the section -- two
// collars 40 m apart along strike plot on top of each other. That is ordinary
// section behaviour, and the caption says so rather than hiding it.
//
// Section coordinates are (h, v): h metres along the dip direction from the
// reference collar, v = elevation (RL). Both are metres, and the transform to
// pixels is deliberately ISOTROPIC -- one scale for both axes. A section with
// separate x and y scales shows a 40-degree zone at 60 degrees, which is the
// one error in a drill-section drawing nobody catches by eye.
// ---------------------------------------------------------------------------

import { holeDirection, toVec, isNum } from '../services/depth_planner.js';

const DEG = Math.PI / 180;

const THEMES = {
  dark: {
    bg: '#191919',
    ink: '#e8edf5',
    muted: '#9aa6b8',
    faint: '#6b7787',
    grid: 'rgba(255,255,255,0.07)',
    surface: '#c9d2e0',
    zoneLine: '#dc2626',
    zoneFill: 'rgba(220,38,38,0.22)',
    hole: '#2f6fe0',
    holeOther: '#5b8fd6',
    marker: '#f97316',
    eoh: '#9aa3ad',
    accent: '#d4af37'
  },
  light: {
    bg: '#ffffff',
    ink: '#14181f',
    muted: '#59636f',
    faint: '#8a94a2',
    grid: 'rgba(0,0,0,0.08)',
    surface: '#4a5260',
    zoneLine: '#c62828',
    zoneFill: 'rgba(198,40,40,0.16)',
    hole: '#1d4ed8',
    holeOther: '#5b7fc7',
    marker: '#c2410c',
    eoh: '#5b6472',
    accent: '#8a6d1f'
  }
};

/**
 * Build the section drawing.
 *
 * @param result  the object depth_planner.computePlan() returns, with the
 *                `topAnchor` / `baseAnchor` / `holeId` the panel adds.
 * @param options mode: 'single' (the reference hole alone) or 'pattern'
 *                (every drillable hole in result.pattern, reference picked out);
 *                theme, width, height, title, subtitle, projectName.
 * @returns {{svg:string, width:number, height:number, holeCount:number}}
 * @throws  Error with a message meant to be shown to the user when the plan
 *          cannot be drawn -- a missed zone has no section.
 */
export function buildPlanSection(result, options = {}) {
  const mode = options.mode === 'pattern' ? 'pattern' : 'single';
  const theme = THEMES[options.theme === 'light' ? 'light' : 'dark'];
  const width = Math.max(640, Math.round(options.width ?? 1100));
  const height = Math.max(420, Math.round(options.height ?? 720));

  requireDrawable(result, mode);

  const frame = sectionFrame(result);
  const holes = collectHoles(result, mode, frame);
  if (!holes.length) throw new Error('No drillable hole in this plan to draw.');

  const zone = zoneLines(result, frame);
  const view = fitView({ holes, zone, frame, width, height, mode });

  const parts = [];
  parts.push(`<rect width="${width}" height="${height}" fill="${theme.bg}"/>`);
  parts.push(depthGrid(view, theme));
  parts.push(zoneBand(zone, view, theme, result));
  parts.push(surfaceLine(result, frame, view, holes, theme));
  parts.push(holeTraces(holes, view, theme, mode));

  const callouts = mode === 'single'
    ? singleCallouts(result, holes[0], view, theme)
    : patternCallouts(holes, view, theme);
  parts.push(callouts);

  parts.push(scaleBar(view, theme));
  parts.push(titleBlock(result, options, theme, width, mode, holes));
  parts.push(footer(result, frame, theme, width, height, mode, holes));

  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" ` +
    `viewBox="0 0 ${width} ${height}" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">` +
    parts.filter(Boolean).join('') +
    `</svg>`;

  return { svg, width, height, holeCount: holes.length };
}

/** A drawing of a hole that misses would be a drawing of nothing. Say why. */
function requireDrawable(result, mode) {
  if (!result || !result.plane || !result.collar || !result.top) {
    throw new Error('Fill in the zone, the structure and the collar first.');
  }
  if (result.top.parallel) {
    throw new Error('The hole runs parallel to the zone — there is no intersection to draw.');
  }
  if (!Number.isFinite(result.top.depth)) {
    throw new Error('The intersection depth is not defined for this plan.');
  }
  if (result.top.behindCollar) {
    throw new Error('The zone sits behind the collar — this hole is drilled away from it.');
  }
  if (mode === 'pattern' && (!result.pattern || !result.pattern.holes.some(h => h.ok))) {
    throw new Error('No drillable pattern holes to draw. Switch on the drill pattern first.');
  }
}

/**
 * The section frame: origin at the reference collar, horizontal axis running
 * down the zone's dip direction.
 */
function sectionFrame(result) {
  const a = Number(result.plane.dipDirection) * DEG;
  const origin = toVec(result.collar);
  return {
    origin,
    // Unit horizontal vector along the dip direction.
    s: { e: Math.sin(a), n: Math.cos(a) },
    dip: Number(result.plane.dip),
    dipDirection: Number(result.plane.dipDirection)
  };
}

/** (e, n, u) -> section (h, v) in metres. */
function project(frame, p) {
  return {
    h: (p.e - frame.origin.e) * frame.s.e + (p.n - frame.origin.n) * frame.s.n,
    v: p.u
  };
}

function projectRecord(frame, rec) {
  return project(frame, toVec(rec));
}

/**
 * Every hole to draw, already reduced to the four points that matter: collar,
 * zone top, zone base, end of hole.
 *
 * Pattern holes carry their own collar and depths from generateDrillPattern();
 * the reference hole is rebuilt from the plan so the single-hole drawing and
 * the pattern drawing use one code path below.
 */
function collectHoles(result, mode, frame) {
  const out = [];

  const push = (spec) => {
    const dir = holeDirection(-Math.abs(spec.dip), spec.azimuth);
    const collar = toVec(spec.collar);
    const at = (len) => project(frame, {
      e: collar.e + dir.e * len,
      n: collar.n + dir.n * len,
      u: collar.u + dir.u * len
    });
    if (!Number.isFinite(spec.depthToTop) || !Number.isFinite(spec.eoh)) return;
    out.push({
      id: spec.id,
      azimuth: spec.azimuth,
      dip: Math.abs(spec.dip),
      collarRL: collar.u,
      depthToTop: spec.depthToTop,
      depthToBase: Number.isFinite(spec.depthToBase) ? spec.depthToBase : null,
      eoh: spec.eoh,
      startLogging: spec.startLogging ?? null,
      reference: !!spec.reference,
      p: {
        collar: at(0),
        top: at(spec.depthToTop),
        base: Number.isFinite(spec.depthToBase) ? at(spec.depthToBase) : null,
        eoh: at(spec.eoh)
      }
    });
  };

  const reference = {
    id: result.holeId || 'proposed hole',
    collar: result.collar,
    azimuth: Number(result.hole.azimuth),
    dip: Math.abs(Number(result.hole.dip)),
    depthToTop: result.top.depth,
    depthToBase: result.base && Number.isFinite(result.base.depth) ? result.base.depth : null,
    eoh: result.proposal ? result.proposal.eoh : result.top.depth,
    startLogging: result.proposal ? result.proposal.startLogging : null,
    reference: true
  };

  if (mode === 'single') {
    push(reference);
    return out;
  }

  for (const h of result.pattern.holes) {
    if (!h.ok) continue;               // the panel already flags these; drawing
    push({                             // an impossible hole would contradict it
      id: h.id,
      collar: h.collar,
      azimuth: h.azimuth,
      dip: h.dip,
      depthToTop: h.depthToTop,
      depthToBase: h.depthToBase,
      eoh: h.eoh
    });
  }
  // The hole the pattern grew out of, drawn on top so the section still shows
  // which section it is.
  push(reference);
  return out;
}

/**
 * The zone in section: two parallel lines at the true dip, through the top and
 * base anchors. Returned as (h, v) anchor + slope, extended to the plot edges
 * only once the view is known.
 */
function zoneLines(result, frame) {
  // Down the dip direction the elevation drops by tan(dip) per metre. This is
  // the whole reason the section is cut along the dip direction.
  const slope = -Math.tan(Number(result.plane.dip) * DEG);
  const top = projectRecord(frame, result.topAnchor || pointRecord(result.top.point));
  const base = result.baseAnchor
    ? projectRecord(frame, result.baseAnchor)
    : (result.base && result.base.point ? project(frame, result.base.point) : null);
  return { slope, top, base, dip: Number(result.plane.dip) };
}

function pointRecord(p) {
  return { easting: p.e, northing: p.n, elevation: p.u };
}

function lineV(anchor, slope, h) {
  return anchor.v + slope * (h - anchor.h);
}

/**
 * Metres -> pixels, one scale for both axes, with the label gutter reserved
 * before the fit rather than after, so a long call-out can never push the
 * drawing off its own page.
 */
function fitView({ holes, zone, frame, width, height, mode }) {
  const pad = {
    left: 58,
    right: mode === 'single' ? 300 : 150,
    top: 92,
    bottom: 86
  };
  const plot = {
    x: pad.left,
    y: pad.top,
    w: width - pad.left - pad.right,
    h: height - pad.top - pad.bottom
  };

  const pts = [];
  for (const hole of holes) {
    for (const key of ['collar', 'top', 'base', 'eoh']) {
      if (hole.p[key]) pts.push(hole.p[key]);
    }
  }
  pts.push(zone.top);
  if (zone.base) pts.push(zone.base);

  let hMin = Math.min(...pts.map(p => p.h));
  let hMax = Math.max(...pts.map(p => p.h));
  let vMin = Math.min(...pts.map(p => p.v));
  let vMax = Math.max(...pts.map(p => p.v));

  // A pattern of vertical holes on one pad has zero width; a single hole drilled
  // straight down has zero horizontal extent. Give both a real span so the fit
  // does not divide by zero.
  const spanH = Math.max(hMax - hMin, 20);
  const spanV = Math.max(vMax - vMin, 20);
  const midH = (hMin + hMax) / 2;
  const midV = (vMin + vMax) / 2;

  const margin = 1.12;                 // breathing room around the extremes
  const scale = Math.min(plot.w / (spanH * margin), plot.h / (spanV * margin));

  const cx = plot.x + plot.w / 2;
  const cy = plot.y + plot.h / 2;

  const view = {
    plot,
    scale,
    x: (h) => cx + (h - midH) * scale,
    y: (v) => cy - (v - midV) * scale,
    hAt: (px) => midH + (px - cx) / scale,
    vAt: (py) => midV - (py - cy) / scale
  };
  view.hLeft = view.hAt(plot.x);
  view.hRight = view.hAt(plot.x + plot.w);
  view.vTop = view.vAt(plot.y);
  view.vBottom = view.vAt(plot.y + plot.h);
  return view;
}

/** Faint RL lines, so a depth on the drawing can be read as an elevation. */
function depthGrid(view, theme) {
  const span = view.vTop - view.vBottom;
  const step = niceStep(span / 5);
  const first = Math.ceil(view.vBottom / step) * step;
  const out = [];
  for (let rl = first; rl <= view.vTop; rl += step) {
    const y = view.y(rl);
    out.push(
      `<line x1="${view.plot.x}" y1="${f(y)}" x2="${f(view.plot.x + view.plot.w)}" y2="${f(y)}" ` +
      `stroke="${theme.grid}" stroke-width="1"/>` +
      `<text x="${view.plot.x - 8}" y="${f(y + 3.5)}" text-anchor="end" font-size="10" ` +
      `fill="${theme.faint}">${Math.round(rl)}</text>`
    );
  }
  out.push(
    `<text x="${view.plot.x - 8}" y="${f(view.plot.y - 10)}" text-anchor="end" font-size="9" ` +
    `fill="${theme.faint}" letter-spacing="0.08em">RL m</text>`
  );
  return out.join('');
}

function niceStep(raw) {
  if (!Number.isFinite(raw) || raw <= 0) return 10;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const step = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10;
  return step * mag;
}

/** The zone: a filled slab between the two anchor planes, at its true dip. */
function zoneBand(zone, view, theme, result) {
  const x1 = view.plot.x;
  const x2 = view.plot.x + view.plot.w;
  const h1 = view.hLeft;
  const h2 = view.hRight;

  const topA = { x: x1, y: view.y(lineV(zone.top, zone.slope, h1)) };
  const topB = { x: x2, y: view.y(lineV(zone.top, zone.slope, h2)) };

  // The label rides the top of the slab, but a steep zone leaves the frame long
  // before the right-hand edge -- so it is placed where the slab is still ON the
  // page, walking back up the line until it is.
  const yTarget = clampPx(topB.y - 10, view.plot.y + 14, view.plot.y + view.plot.h - 10);
  const labelX = Math.abs(topB.y - topA.y) < 0.5
    ? x2 - 6
    : clampPx(x1 + (x2 - x1) * (yTarget + 10 - topA.y) / (topB.y - topA.y), x1 + 90, x2 - 6);

  const label =
    `<text x="${f(labelX)}" y="${f(yTarget)}" text-anchor="end" font-size="12" ` +
    `font-weight="600" fill="${theme.zoneLine}">the zone, dipping ${Math.round(zone.dip)}°</text>`;

  if (!zone.base) {
    // No base anchor: one surface, not a slab. Drawing a thickness nobody
    // measured would invent data.
    return (
      `<line x1="${f(topA.x)}" y1="${f(topA.y)}" x2="${f(topB.x)}" y2="${f(topB.y)}" ` +
      `stroke="${theme.zoneLine}" stroke-width="2.5"/>` + label
    );
  }

  const baseA = { x: x1, y: view.y(lineV(zone.base, zone.slope, h1)) };
  const baseB = { x: x2, y: view.y(lineV(zone.base, zone.slope, h2)) };

  return (
    `<polygon points="${f(topA.x)},${f(topA.y)} ${f(topB.x)},${f(topB.y)} ` +
    `${f(baseB.x)},${f(baseB.y)} ${f(baseA.x)},${f(baseA.y)}" ` +
    `fill="${theme.zoneFill}" stroke="${theme.zoneLine}" stroke-width="2"/>` + label
  );
}

/**
 * The ground: a line through the collars, extended to the outcrop anchor when
 * the zone was picked up in a trench.
 *
 * Explicitly NOT a topographic profile -- the planner has no surface model, and
 * a smooth curve here would read as one. It is the pad line plus the outcrop,
 * which is exactly what the plan assumes, and the footer says so.
 */
function surfaceLine(result, frame, view, holes, theme) {
  const pts = holes.map(h => h.p.collar);
  const outcrop = result.topAnchor ? projectRecord(frame, result.topAnchor) : null;
  if (outcrop) pts.push(outcrop);
  pts.sort((a, b) => a.h - b.h);

  const path = pts.map((p, i) => `${i ? 'L' : 'M'}${f(view.x(p.h))},${f(view.y(p.v))}`).join(' ');

  const trenchMark = outcrop
    ? `<circle cx="${f(view.x(outcrop.h))}" cy="${f(view.y(outcrop.v))}" r="5" fill="${theme.zoneLine}"/>` +
      `<text x="${f(view.x(outcrop.h))}" y="${f(view.y(outcrop.v) - 12)}" text-anchor="middle" ` +
      `font-size="12" font-weight="700" fill="${theme.ink}">trench / outcrop</text>`
    : '';

  return (
    `<path d="${path}" fill="none" stroke="${theme.surface}" stroke-width="1.4" opacity="0.85"/>` +
    trenchMark
  );
}

/** Every hole as a dashed trace -- dashed because none of this is drilled yet. */
function holeTraces(holes, view, theme, mode) {
  return holes.map(hole => {
    const colour = hole.reference ? theme.hole : theme.holeOther;
    const wide = hole.reference && mode === 'pattern';
    const c = hole.p.collar;
    const e = hole.p.eoh;

    const parts = [
      `<line x1="${f(view.x(c.h))}" y1="${f(view.y(c.v))}" x2="${f(view.x(e.h))}" y2="${f(view.y(e.v))}" ` +
      `stroke="${colour}" stroke-width="${wide ? 3 : hole.reference ? 2.6 : 1.8}" ` +
      `stroke-dasharray="7 5" opacity="${hole.reference ? 1 : 0.85}"/>`,
      `<circle cx="${f(view.x(c.h))}" cy="${f(view.y(c.v))}" r="${hole.reference ? 5 : 3.5}" fill="${colour}"/>`,
      `<circle cx="${f(view.x(e.h))}" cy="${f(view.y(e.v))}" r="3.5" fill="${theme.eoh}"/>`
    ];

    // The cored interval: the one stretch of the trace that is solid, because it
    // is the only part being drilled FOR something.
    if (hole.p.base) {
      parts.push(
        `<line x1="${f(view.x(hole.p.top.h))}" y1="${f(view.y(hole.p.top.v))}" ` +
        `x2="${f(view.x(hole.p.base.h))}" y2="${f(view.y(hole.p.base.v))}" ` +
        `stroke="${theme.marker}" stroke-width="${hole.reference ? 4.5 : 3}" stroke-linecap="round"/>`
      );
    }
    parts.push(
      `<circle cx="${f(view.x(hole.p.top.h))}" cy="${f(view.y(hole.p.top.v))}" r="4" fill="${theme.marker}"/>`
    );
    if (hole.p.base) {
      parts.push(
        `<circle cx="${f(view.x(hole.p.base.h))}" cy="${f(view.y(hole.p.base.v))}" r="4" fill="${theme.marker}"/>`
      );
    }
    return parts.join('');
  }).join('');
}

/**
 * The single-hole call-outs: the numbers that go on the drill instruction,
 * each on a leader line from the point it describes.
 *
 * Labels are stacked in the right-hand gutter and pushed apart until none
 * overlap, so a shallow zone in a deep hole does not print three lines of text
 * on top of each other.
 */
function singleCallouts(result, hole, view, theme) {
  const gutterX = view.plot.x + view.plot.w + 26;

  const items = [
    {
      at: hole.p.collar,
      title: `collar${hole.id ? ` — ${hole.id}` : ''}`,
      sub: `${fmt(hole.collarRL, 0)} m RL, azi ${Math.round(hole.azimuth)
        .toString().padStart(3, '0')}, dip ${Math.round(hole.dip)}°`,
      colour: theme.ink,
      side: 'left'
    },
    {
      at: hole.p.top,
      title: `zone top — ${fmt(hole.depthToTop, 1)} m`,
      sub: hole.startLogging !== null
        ? `start logging at ${hole.startLogging} m`
        : 'start sampling here',
      colour: theme.marker
    }
  ];

  if (hole.p.base) {
    items.push({
      at: hole.p.base,
      title: `zone base — ${fmt(hole.depthToBase, 1)} m`,
      sub: result.coreLength !== null && Number.isFinite(result.coreLength)
        ? `${fmt(result.coreLength, 1)} m of core (${fmt(result.trueThickness, 1)} m true)`
        : '',
      colour: theme.marker
    });
  }

  items.push({
    at: hole.p.eoh,
    title: `stop drilling — ${hole.eoh} m`,
    sub: result.proposal ? `${result.proposal.eohMargin} m below the deepest estimate` : 'margin for error',
    colour: theme.eoh
  });

  // Collar label goes left of the trace; everything else stacks on the right.
  const left = items.filter(i => i.side === 'left');
  const right = items.filter(i => i.side !== 'left');

  right.sort((a, b) => view.y(a.at.v) - view.y(b.at.v));
  const GAP = 42;
  let cursor = -Infinity;
  for (const item of right) {
    item.labelY = Math.max(view.y(item.at.v), cursor + GAP);
    cursor = item.labelY;
  }
  // If the stack ran off the bottom, slide the whole column back up together --
  // keeping the order rather than clipping the last call-out.
  const overflow = (right.length ? right[right.length - 1].labelY : 0) - (view.plot.y + view.plot.h + 24);
  if (overflow > 0) for (const item of right) item.labelY -= overflow;

  const rightSvg = right.map(item => {
    const px = view.x(item.at.h);
    const py = view.y(item.at.v);
    return (
      `<path d="M${f(px + 6)},${f(py)} L${f(gutterX - 10)},${f(item.labelY)}" fill="none" ` +
      `stroke="${item.colour}" stroke-width="1" opacity="0.75"/>` +
      `<text x="${f(gutterX)}" y="${f(item.labelY + 4)}" font-size="13" font-weight="700" ` +
      `fill="${theme.ink}">${esc(item.title)}</text>` +
      (item.sub
        ? `<text x="${f(gutterX)}" y="${f(item.labelY + 19)}" font-size="11" fill="${item.colour}">${esc(item.sub)}</text>`
        : '')
    );
  }).join('');

  const leftSvg = left.map(item => {
    const px = view.x(item.at.h);
    const py = view.y(item.at.v);
    return (
      `<text x="${f(px)}" y="${f(py - 22)}" text-anchor="middle" font-size="13" font-weight="700" ` +
      `fill="${theme.ink}">${esc(item.title)}</text>` +
      `<text x="${f(px)}" y="${f(py - 8)}" text-anchor="middle" font-size="11" ` +
      `fill="${theme.muted}">${esc(item.sub)}</text>`
    );
  }).join('');

  return leftSvg + rightSvg;
}

/**
 * Pattern call-outs: hole ID over each collar, depths underneath.
 *
 * Twelve holes with four call-outs each is unreadable, so each hole gets one
 * two-line tag and the per-hole detail stays in the panel's table. Tags are
 * lifted in steps where collars crowd together, which happens as soon as the
 * along-strike holes project onto the same section.
 */
function patternCallouts(holes, view, theme) {
  const sorted = holes.slice().sort((a, b) => view.x(a.p.collar.h) - view.x(b.p.collar.h));
  const MIN_GAP = 96;
  let lastX = -Infinity;
  let tier = 0;

  return sorted.map(hole => {
    const px = view.x(hole.p.collar.h);
    const py = view.y(hole.p.collar.v);
    if (px - lastX < MIN_GAP) tier = (tier + 1) % 3;
    else tier = 0;
    lastX = px;

    const top = py - 16 - tier * 30;
    return (
      `<line x1="${f(px)}" y1="${f(py - 6)}" x2="${f(px)}" y2="${f(top + 4)}" stroke="${theme.faint}" ` +
      `stroke-width="1" opacity="0.6"/>` +
      `<text x="${f(px)}" y="${f(top)}" text-anchor="middle" font-size="11.5" font-weight="700" ` +
      `fill="${hole.reference ? theme.hole : theme.ink}">${esc(hole.id)}</text>` +
      `<text x="${f(px)}" y="${f(top - 13)}" text-anchor="middle" font-size="10" fill="${theme.muted}">` +
      `zone ${fmt(hole.depthToTop, 0)} m · EOH ${hole.eoh} m</text>`
    );
  }).join('');
}

/** A bar in metres, because the drawing will be resized in someone's report. */
function scaleBar(view, theme) {
  const target = view.plot.w * 0.18;
  const metres = niceStep(target / view.scale);
  const px = metres * view.scale;
  const x = view.plot.x;
  const y = view.plot.y + view.plot.h + 26;
  return (
    `<line x1="${f(x)}" y1="${f(y)}" x2="${f(x + px)}" y2="${f(y)}" stroke="${theme.muted}" stroke-width="2"/>` +
    `<line x1="${f(x)}" y1="${f(y - 4)}" x2="${f(x)}" y2="${f(y + 4)}" stroke="${theme.muted}" stroke-width="2"/>` +
    `<line x1="${f(x + px)}" y1="${f(y - 4)}" x2="${f(x + px)}" y2="${f(y + 4)}" stroke="${theme.muted}" stroke-width="2"/>` +
    `<text x="${f(x + px + 8)}" y="${f(y + 4)}" font-size="11" fill="${theme.muted}">${metres} m</text>`
  );
}

function titleBlock(result, options, theme, width, mode, holes) {
  const name = options.title || (mode === 'pattern'
    ? 'Planned drill pattern — section'
    : `Planned hole${result.holeId ? ` ${result.holeId}` : ''} — section`);

  const totals = mode === 'pattern' && result.pattern
    ? `${result.pattern.drillableHoles} holes · ${Math.round(result.pattern.totalMetres)} m · ` +
      `${result.pattern.spacingStrike} × ${result.pattern.spacingDip} m on the zone plane`
    : `zone ${fmt(result.top.depth, 1)}–${result.base ? fmt(result.base.depth, 1) : '?'} m · ` +
      `EOH ${result.proposal ? result.proposal.eoh : '—'} m · cuts at ${Math.round(result.intersectionAngleDeg)}°`;

  const sub = options.subtitle || totals;
  const project = options.projectName ? `${esc(options.projectName)} · ` : '';

  return (
    `<text x="34" y="40" font-size="19" font-weight="700" fill="${theme.ink}">${esc(name)}</text>` +
    `<text x="34" y="60" font-size="12" fill="${theme.accent}">${project}${esc(sub)}</text>` +
    `<text x="${width - 34}" y="40" text-anchor="end" font-size="11" fill="${theme.muted}">` +
    `Section looking along strike (${Math.round(((result.plane.dipDirection + 90) % 360 + 360) % 360)}°/` +
    `${Math.round(((result.plane.dipDirection + 270) % 360 + 360) % 360)}°)</text>` +
    `<text x="${width - 34}" y="58" text-anchor="end" font-size="11" fill="${theme.muted}">` +
    `true dip shown · ${holes.length} hole${holes.length === 1 ? '' : 's'} projected</text>`
  );
}

/**
 * What the picture assumes.
 *
 * A section like this is persuasive out of proportion to what is behind it --
 * one strike/dip reading drawn as a solid red slab looks like a mapped orebody.
 * So the assumptions travel WITH the image, not just in the panel that made it,
 * because the image is what gets pasted into the proposal.
 */
function footer(result, frame, theme, width, height, mode, holes) {
  const y = height - 44;
  const env = result.envelope;

  const line1 =
    `Zone plane ${fmt(result.plane.dip, 0)}° toward ${fmt(result.plane.dipDirection, 0)}° ` +
    `(assumed planar and continuous between the anchors). ` +
    (env && Number.isFinite(env.min)
      ? `Uncertainty envelope ${fmt(env.min, 1)}–${fmt(env.max, 1)} m downhole. `
      : '') +
    (Number.isFinite(result.elevationSensitivity)
      ? `Collar RL moves the target ${Math.abs(result.elevationSensitivity).toFixed(2)} m per metre.`
      : '');

  const line2 = mode === 'pattern'
    ? `Collars sit on a flat pad at ${fmt(result.pattern.collarElevation, 1)} m RL and are not reconciled ` +
      `with topography. Holes offset along strike project onto this section. Nothing here is drilled.`
    : `The ground line joins the collar to the outcrop — it is not a surveyed topographic profile. ` +
      `Nothing here is drilled: every depth is a projection from the structure above.`;

  return (
    `<line x1="34" y1="${f(y - 16)}" x2="${width - 34}" y2="${f(y - 16)}" stroke="${theme.grid}" stroke-width="1"/>` +
    `<text x="34" y="${f(y)}" font-size="10.5" fill="${theme.muted}">${esc(line1)}</text>` +
    `<text x="34" y="${f(y + 15)}" font-size="10.5" fill="${theme.faint}">${esc(line2)}</text>`
  );
}

function clampPx(v, lo, hi) {
  return Number.isFinite(v) ? Math.max(lo, Math.min(hi, v)) : lo;
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function fmt(v, dp = 1) {
  return isNum(v) ? Number(v).toFixed(dp) : '—';
}

/** Pixel coordinates rounded -- SVG files here are read by humans in diffs. */
function f(v) {
  return Number.isFinite(v) ? Math.round(v * 100) / 100 : 0;
}

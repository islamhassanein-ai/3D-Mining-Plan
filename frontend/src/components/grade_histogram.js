import {
  GRADE_BUCKETS,
  getGradeBucketIndex,
  formatBucketRange,
  UNSAMPLED_BUCKET_INDEX,
} from '../scene/grade_scale.js';

// Grade-distribution histogram bound to the cutoff slider. Shows the assay
// grade population split across the six canonical grade buckets, marks
// where the current cutoff falls, and reports how many intervals -- and how
// many drilled meters -- survive the cutoff. This is core grade-control
// decision support: it lets a geologist see the shape of the population and
// justify a defensible cutoff instead of guessing.
//
// Gold assay populations are heavily right-skewed (mostly background), so
// bar heights use a square-root scale -- otherwise the sparse high-grade
// buckets that actually matter would be invisible next to the background
// spike. The readout counts stay linear/exact.
//
// Drillhole and trench samples get a row each rather than one merged
// population. The cutoff hides both in the 3D view, so both belong here --
// but a channel sample walked along surface and a metre of core are not the
// same measurement, and averaging them into one bar would invite reading a
// trench-driven high-grade tail as downhole continuity. Each row is scaled
// against its own maximum, so the shape of a sparse TR population stays
// readable next to a much larger DD one; compare shapes, not bar heights.
export class GradeHistogram {
  constructor(container) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.intervals = [];     // drillhole assays: { grade, unit, sampleId, meters }
    this.trenchSamples = []; // trench channel samples: { grade, unit, sampleId }
    this.cutoff = 0.0;
    this.injectStyles();
    this.render();
  }

  injectStyles() {
    if (document.getElementById('grade-histogram-styles')) return;
    const style = document.createElement('style');
    style.id = 'grade-histogram-styles';
    style.textContent = `
      .gh-wrap { display: flex; flex-direction: column; gap: 6px; width: 100%; }
      /* A fixed gutter column carries the DD/TR row label, and the axis below
         repeats it as an empty cell so the bucket columns stay aligned with
         their bounds no matter which rows are present. */
      .gh-bars {
        display: grid;
        grid-template-columns: 17px repeat(6, 1fr);
        gap: 3px;
        align-items: end;
        height: 46px;
        padding-top: 2px;
      }
      .gh-row-label {
        align-self: center;
        font-size: 8.5px;
        font-weight: 700;
        letter-spacing: 0.3px;
        color: var(--text-faint, #5f7091);
      }
      .gh-col { display: flex; flex-direction: column; justify-content: flex-end; height: 100%; }
      .gh-bar {
        width: 100%;
        min-height: 2px;
        border-radius: 2px 2px 0 0;
        transition: opacity 0.12s ease;
      }
      .gh-bar.below { opacity: 0.22; }
      /* Explicit From-To bounds under each bar. A single number per column was
         ambiguous -- it read as the value the bar counts rather than the edge
         of its bracket. Stacked so "0.10" over "0.30" stays legible in the
         narrow sidebar column instead of being clipped. */
      .gh-axis {
        display: grid;
        grid-template-columns: 17px repeat(6, 1fr);
        gap: 3px;
        font-size: 8px;
        line-height: 1.25;
        color: var(--text-faint, #5f7091);
        text-align: center;
      }
      .gh-axis .gh-range {
        display: flex;
        flex-direction: column;
        align-items: center;
        white-space: nowrap;
      }
      .gh-axis .gh-range .gh-to { color: var(--text-muted, #93a2ba); }
      .gh-axis .gh-range .gh-dash { opacity: 0.55; line-height: 0.8; }
      .gh-readout {
        display: flex;
        justify-content: space-between;
        font-size: 10.5px;
        color: var(--text-muted, #93a2ba);
        border-top: 1px solid var(--border-light, #223049);
        padding-top: 6px;
        margin-top: 2px;
      }
      /* Two readout lines stacked: only the first carries the rule, or the
         pair reads as two unrelated blocks. */
      .gh-readout + .gh-readout {
        border-top: none;
        padding-top: 0;
        margin-top: -4px;
      }
      .gh-readout b { color: var(--gold, #d4af37); font-weight: 700; }
      .gh-empty { font-size: 10.5px; color: var(--text-faint, #5f7091); }
    `;
    document.head.appendChild(style);
  }

  // Feeds the histogram this project's samples. Call on scene load.
  // `trenches` is optional -- a project may have none, and older callers
  // passed drillholes alone.
  setData(drillholes, trenches) {
    this.intervals = [];
    for (const dh of (drillholes || [])) {
      for (const a of dh.assays) {
        const meters = Math.max(0, (a.to_depth - a.from_depth));
        this.intervals.push({
          grade: a.grade_value,
          unit: a.grade_unit,
          sampleId: a.sample_id || null,
          meters,
        });
      }
    }

    // Trench rows are one channel sample each. They carry no grade_unit --
    // the scene API doesn't return one -- so they are read as g/t, the same
    // assumption trenches.js makes when it colours the fences. No metres:
    // a channel sample has no downhole length to sum.
    this.trenchSamples = [];
    for (const t of (trenches || [])) {
      this.trenchSamples.push({
        grade: t.grade_value,
        unit: 'g/t',
        sampleId: t.sample_id || null,
      });
    }
    this.render();
  }

  setCutoff(cutoff) {
    this.cutoff = Number(cutoff);
    this.render();
  }

  // Bins one population across the grade buckets. Unsampled entries (bucket
  // index -1) are excluded from the profile entirely rather than binned as
  // 0 g/t -- they carry no assay result to profile.
  _bin(samples) {
    const counts = new Array(GRADE_BUCKETS.length).fill(0);
    let aboveCount = 0, aboveMeters = 0, totalMeters = 0, sampledCount = 0;
    for (const s of samples) {
      const idx = getGradeBucketIndex(s.grade, s.unit, s.sampleId);
      if (idx === UNSAMPLED_BUCKET_INDEX) continue;
      counts[idx]++;
      sampledCount++;
      totalMeters += s.meters || 0;
      if (Number(s.grade) >= this.cutoff) {
        aboveCount++;
        aboveMeters += s.meters || 0;
      }
    }
    return { counts, aboveCount, aboveMeters, totalMeters, sampledCount };
  }

  // One row of bars, scaled against its own busiest bucket.
  _barRow(label, counts, noun) {
    const maxCount = Math.max(...counts, 1);
    const cols = GRADE_BUCKETS.map((b, i) => {
      const hPct = Math.sqrt(counts[i] / maxCount) * 100;
      // A bucket is "below cutoff" when its entire upper bound is under the
      // cutoff (upper === null is the open-ended high bucket, never below).
      const below = b.upper !== null && b.upper <= this.cutoff;
      return `<div class="gh-col" title="${formatBucketRange(b)} g/t: ${counts[i]} ${noun}">
        <div class="gh-bar ${below ? 'below' : ''}" style="height:${hPct}%;background:${b.color}"></div>
      </div>`;
    }).join('');
    return `<div class="gh-bars"><span class="gh-row-label">${label}</span>${cols}</div>`;
  }

  render() {
    if (!this.container) return;

    if (this.intervals.length === 0 && this.trenchSamples.length === 0) {
      this.container.innerHTML = `<div class="gh-empty">No assay intervals to profile.</div>`;
      return;
    }

    const dd = this._bin(this.intervals);
    const tr = this._bin(this.trenchSamples);

    if (dd.sampledCount === 0 && tr.sampledCount === 0) {
      this.container.innerHTML = `<div class="gh-empty">No assayed intervals to profile.</div>`;
      return;
    }

    // A row only appears when that population exists, so a drillhole-only
    // project looks exactly as it did before trenches were profiled.
    const rows = [
      dd.sampledCount > 0 ? this._barRow('DD', dd.counts, 'intervals') : '',
      tr.sampledCount > 0 ? this._barRow('TR', tr.counts, 'samples') : '',
    ].join('');

    // Explicit From-To bounds per bucket rather than a single edge number.
    const axis = GRADE_BUCKETS.map(b => {
      if (b.to === null) {
        return `<span class="gh-range"><span class="gh-to">≥ ${b.from.toFixed(2)}</span></span>`;
      }
      return `<span class="gh-range">
        <span>${b.from.toFixed(2)}</span>
        <span class="gh-dash">–</span>
        <span class="gh-to">${b.to.toFixed(2)}</span>
      </span>`;
    }).join('');

    const pctMeters = dd.totalMeters > 0 ? (dd.aboveMeters / dd.totalMeters * 100) : 0;

    // Metres only on the DD line: trench channel samples have no downhole
    // length, so a TR metre figure would be an invention. The trench line
    // reports the share of samples surviving the cutoff instead.
    const ddReadout = dd.sampledCount > 0 ? `
      <div class="gh-readout">
        <span><b>${dd.aboveCount}</b> / ${dd.sampledCount} DD intervals</span>
        <span><b>${dd.aboveMeters.toFixed(1)} m</b> (${pctMeters.toFixed(0)}%) &ge; cutoff</span>
      </div>` : '';
    const pctTrench = tr.sampledCount > 0 ? (tr.aboveCount / tr.sampledCount * 100) : 0;
    const trReadout = tr.sampledCount > 0 ? `
      <div class="gh-readout">
        <span><b>${tr.aboveCount}</b> / ${tr.sampledCount} TR samples</span>
        <span>(${pctTrench.toFixed(0)}%) &ge; cutoff</span>
      </div>` : '';

    this.container.innerHTML = `
      <div class="gh-wrap">
        ${rows}
        <div class="gh-axis"><span></span>${axis}</div>
        ${ddReadout}
        ${trReadout}
      </div>
    `;
  }
}

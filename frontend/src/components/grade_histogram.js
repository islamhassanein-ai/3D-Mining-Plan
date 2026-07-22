import { GRADE_BUCKETS, getGradeBucketIndex } from '../scene/grade_scale.js';

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
export class GradeHistogram {
  constructor(container) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.intervals = []; // { grade, meters }
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
      .gh-bars {
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 3px;
        align-items: end;
        height: 56px;
        padding-top: 2px;
      }
      .gh-col { display: flex; flex-direction: column; justify-content: flex-end; height: 100%; }
      .gh-bar {
        width: 100%;
        min-height: 2px;
        border-radius: 2px 2px 0 0;
        transition: opacity 0.12s ease;
      }
      .gh-bar.below { opacity: 0.22; }
      .gh-axis {
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 3px;
        font-size: 7.5px;
        color: var(--text-faint, #5f7091);
        text-align: center;
      }
      .gh-readout {
        display: flex;
        justify-content: space-between;
        font-size: 10.5px;
        color: var(--text-muted, #93a2ba);
        border-top: 1px solid var(--border-light, #223049);
        padding-top: 6px;
        margin-top: 2px;
      }
      .gh-readout b { color: var(--gold, #d4af37); font-weight: 700; }
      .gh-empty { font-size: 10.5px; color: var(--text-faint, #5f7091); }
    `;
    document.head.appendChild(style);
  }

  // Feeds the histogram this project's assay intervals. Call on scene load.
  setData(drillholes) {
    this.intervals = [];
    for (const dh of (drillholes || [])) {
      for (const a of dh.assays) {
        const meters = Math.max(0, (a.to_depth - a.from_depth));
        this.intervals.push({ grade: a.grade_value, unit: a.grade_unit, meters });
      }
    }
    this.render();
  }

  setCutoff(cutoff) {
    this.cutoff = Number(cutoff);
    this.render();
  }

  render() {
    if (!this.container) return;

    if (this.intervals.length === 0) {
      this.container.innerHTML = `<div class="gh-empty">No assay intervals to profile.</div>`;
      return;
    }

    // Bin counts per grade bucket.
    const counts = new Array(GRADE_BUCKETS.length).fill(0);
    let aboveCount = 0, aboveMeters = 0, totalMeters = 0;
    for (const iv of this.intervals) {
      counts[getGradeBucketIndex(iv.grade, iv.unit)]++;
      totalMeters += iv.meters;
      if (iv.grade >= this.cutoff) {
        aboveCount++;
        aboveMeters += iv.meters;
      }
    }

    const maxCount = Math.max(...counts, 1);
    const bars = GRADE_BUCKETS.map((b, i) => {
      const hPct = Math.sqrt(counts[i] / maxCount) * 100;
      // A bucket is "below cutoff" when its entire upper bound is under the
      // cutoff (upper === null is the open-ended high bucket, never below).
      const below = b.upper !== null && b.upper <= this.cutoff;
      return `<div class="gh-col" title="${b.label} g/t: ${counts[i]} intervals">
        <div class="gh-bar ${below ? 'below' : ''}" style="height:${hPct}%;background:${b.color}"></div>
      </div>`;
    }).join('');

    // Compact axis labels (bucket upper edges), skipping some to avoid clutter.
    const axis = ['.01', '.05', '.1', '.5', '1', '1+']
      .map(l => `<span>${l}</span>`).join('');

    const pctMeters = totalMeters > 0 ? (aboveMeters / totalMeters * 100) : 0;

    this.container.innerHTML = `
      <div class="gh-wrap">
        <div class="gh-bars">${bars}</div>
        <div class="gh-axis">${axis}</div>
        <div class="gh-readout">
          <span><b>${aboveCount}</b> / ${this.intervals.length} intervals</span>
          <span><b>${aboveMeters.toFixed(1)} m</b> (${pctMeters.toFixed(0)}%) &ge; cutoff</span>
        </div>
      </div>
    `;
  }
}

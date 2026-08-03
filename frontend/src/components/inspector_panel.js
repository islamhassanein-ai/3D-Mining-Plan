
export class InspectorPanel {
  constructor(container, options = {}) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.collarId = null;
    this.data = null;
    this.loading = false;
    this.error = null;
    this.highlightedIntervalId = null; // To highlight a specific interval if clicked in 3D
    this.dataSource = options.dataSource || null;
    // Fired when a downhole-log row is selected, so the 3D view can point at
    // that sample. index.html has always passed this in, but the panel never
    // stored it and never called it -- selecting a row highlighted the table
    // row and did nothing in the scene.
    this.onIntervalSelected = options.onIntervalSelected || null;

    this.init();
  }

  init() {
    this.injectStyles();
    this.render();
  }

  injectStyles() {
    if (document.getElementById('inspector-panel-styles')) return;
    const style = document.createElement('style');
    style.id = 'inspector-panel-styles';
    style.textContent = `
      .inspector-container {
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        color: #e2e8f0;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(12px);
        height: 100%;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }
      .inspector-placeholder {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: #64748b;
        text-align: center;
        font-size: 0.875rem;
        gap: 12px;
      }
      .inspector-header {
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        padding-bottom: 16px;
        margin-bottom: 16px;
      }
      .inspector-hole-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #f8fafc;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .inspector-meta-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px;
        margin-top: 12px;
      }
      .meta-box {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 6px;
        padding: 8px;
        text-align: center;
      }
      .meta-lbl {
        font-size: 0.65rem;
        color: #64748b;
        text-transform: uppercase;
      }
      .meta-val {
        font-size: 0.8125rem;
        font-weight: 600;
        color: #cbd5e1;
        margin-top: 2px;
      }
      .inspector-tabs {
        display: flex;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 12px;
      }
      .inspector-tab {
        background: transparent;
        color: #64748b;
        border: none;
        border-bottom: 2px solid transparent;
        padding: 8px 16px;
        cursor: pointer;
        font-size: 0.875rem;
        font-weight: 600;
        transition: all 0.2s ease;
      }
      .inspector-tab:hover {
        color: #cbd5e1;
      }
      .inspector-tab.active {
        color: #3b82f6;
        border-bottom-color: #3b82f6;
      }
      .tab-content {
        flex: 1;
        overflow-y: auto;
        padding-right: 4px;
      }
      .table-container {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.8125rem;
      }
      .table-container th {
        text-align: left;
        padding: 8px 10px;
        background: rgba(255, 255, 255, 0.03);
        color: #94a3b8;
        font-weight: 600;
        position: sticky;
        top: 0;
        z-index: 10;
      }
      .table-container td {
        padding: 8px 10px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      }
      .table-container tr:hover td {
        background: rgba(255, 255, 255, 0.02);
      }
      /* The selected row drives the marker in the 3D view, so it has to be
         findable after scrolling back to it. Gold rather than blue: it matches
         the ring drawn on the sample in the scene, which is what ties the two
         together. */
      .table-container tr.highlighted td {
        background: rgba(212, 175, 55, 0.18) !important;
        box-shadow: inset 0 0 0 9999px rgba(212, 175, 55, 0.04);
      }
      .table-container tr.highlighted td:first-child {
        border-left: 3px solid var(--gold, #d4af37);
      }
      .table-container tbody tr { cursor: pointer; }
      .table-container tbody tr:hover td { background: rgba(255, 255, 255, 0.04); }
      /* Row tooltip. The Sample ID is not a column -- it would crowd a narrow
         panel, and most rows are read by depth anyway -- so hovering is how
         you get the name of the sample you are looking at. */
      .log-tooltip {
        position: fixed;
        z-index: 1000;
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.1s ease;
        background: rgba(13, 21, 36, 0.97);
        border: 1px solid rgba(212, 175, 55, 0.55);
        border-radius: 7px;
        padding: 7px 10px;
        font-size: 11.5px;
        color: #e8edf5;
        white-space: nowrap;
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.5);
      }
      .log-tooltip .lt-name {
        font-weight: 800;
        color: var(--gold-soft, #e8c76b);
        margin-bottom: 3px;
      }
      .log-tooltip .lt-name.lt-unnamed { color: var(--text-muted, #93a2ba); font-style: italic; }
      .log-tooltip .lt-row { color: var(--text-muted, #93a2ba); }
      .log-tooltip .lt-row b { color: #e8edf5; font-weight: 600; }
      .badge-assay {
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 0.75rem;
      }
      .badge-lith {
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.75rem;
        background: rgba(255, 255, 255, 0.08);
      }
      .color-block {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 2px;
        margin-right: 6px;
        vertical-align: middle;
      }
      /* Unsampled rows must be unmistakable. "Never assayed" and "assayed at
         zero" are completely different geological statements, and the previous
         treatment -- grey text over a barely-visible hatch -- made a gap read
         as just another quiet row while scrolling. It now carries its own
         amber tint and a left bar, so a gap is legible as a gap at a glance
         without shouting louder than the grade values themselves. */
      .table-container tr.row-unsampled td {
        color: #b9a06a;
        background: rgba(212, 175, 55, 0.055);
      }
      .table-container tr.row-unsampled td:first-child {
        border-left: 3px solid rgba(212, 175, 55, 0.6);
      }
      .badge-unsampled {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 800;
        font-size: 0.72rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: #e8c76b;
        background: rgba(212, 175, 55, 0.16);
        border: 1px dashed rgba(212, 175, 55, 0.65);
      }
      /* A small hollow square reads as "nothing here" next to the solid colour
         chips the assay rows use. */
      .badge-unsampled::before {
        content: '';
        width: 7px;
        height: 7px;
        border: 1.5px solid currentColor;
        border-radius: 2px;
        opacity: 0.9;
      }
      .badge-status {
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }
      /* The two statuses were #34d399 and #67e8f9 -- a green and a cyan, but
         both light teals, so at badge size on a dark panel they read as the
         same colour. They are now a true green against a near-white, which no
         one can confuse, and the pairing matches the 3D view: a drilled hole
         is solid, a planned one is a white marker on a dashed black trace. */
      .badge-status.drilled {
        color: #22c55e;
        background: rgba(34, 197, 94, 0.14);
        border: 1px solid rgba(34, 197, 94, 0.55);
      }
      .badge-status.planned {
        color: #f1f5f9;
        background: rgba(241, 245, 249, 0.1);
        border: 1px dashed rgba(241, 245, 249, 0.7);
      }
    `;
    document.head.appendChild(style);
  }

  // One tooltip element reused by every row, created lazily and parked on
  // <body> so it is never clipped by the panel's own overflow.
  ensureTooltip() {
    if (this.tooltipEl && this.tooltipEl.isConnected) return this.tooltipEl;
    const el = document.createElement('div');
    el.className = 'log-tooltip';
    document.body.appendChild(el);
    this.tooltipEl = el;
    return el;
  }

  bindRowTooltips() {
    const tip = this.ensureTooltip();
    const hide = () => { tip.style.opacity = '0'; };

    this.container.querySelectorAll('tr[data-tip]').forEach(row => {
      row.addEventListener('mouseenter', () => {
        let payload;
        try { payload = JSON.parse(row.dataset.tip); } catch { return; }
        tip.innerHTML =
          `<div class="lt-name ${payload.named ? '' : 'lt-unnamed'}">${payload.name}</div>` +
          payload.rows.map(([k, v]) =>
            `<div class="lt-row">${k}: <b>${v}</b></div>`).join('');
        tip.style.opacity = '1';
      });
      row.addEventListener('mousemove', (e) => {
        // Flip to the other side of the cursor near the viewport edges, so the
        // tooltip is never cut off against the window.
        const rect = tip.getBoundingClientRect();
        const x = e.clientX + 14;
        const y = e.clientY + 14;
        tip.style.left = (x + rect.width > window.innerWidth ? e.clientX - rect.width - 14 : x) + 'px';
        tip.style.top = (y + rect.height > window.innerHeight ? e.clientY - rect.height - 14 : y) + 'px';
      });
      row.addEventListener('mouseleave', hide);
    });

    // A re-render replaces the rows mid-hover, which would strand the tooltip.
    hide();
  }

  async loadCollar(collarId, highlightedIntervalId = null) {
    this.collarId = collarId;
    this.highlightedIntervalId = highlightedIntervalId;
    this.loading = true;
    this.error = null;
    this.render();

    try {
      this.data = await this.dataSource.getCollarDetails(collarId);
      this.loading = false;
      this.activeTab = 'logs'; // Default tab
      this.render();
      
      // Auto scroll to highlighted row if exists
      if (this.highlightedIntervalId) {
        setTimeout(() => {
          const row = this.container.querySelector(`[data-interval-id="${this.highlightedIntervalId}"]`);
          if (row) {
            row.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        }, 100);
      }
    } catch (err) {
      this.loading = false;
      this.error = err.message || 'Failed to fetch drillhole details';
      this.render();
    }
  }

  render() {
    if (this.loading) {
      this.container.innerHTML = `
        <div class="inspector-container">
          <div class="inspector-placeholder">
            <div class="loading-spinner" style="width:24px;height:24px"></div>
            Loading drillhole logs...
          </div>
        </div>
      `;
      return;
    }

    if (this.error) {
      this.container.innerHTML = `
        <div class="inspector-container">
          <div class="inspector-placeholder" style="color:#ef4444">
            <svg style="width:36px;height:36px" viewBox="0 0 24 24"><path fill="currentColor" d="M13 14H11V9H13M13 18H11V16H13M1 21H23L12 2L1 21Z"/></svg>
            ${this.error}
          </div>
        </div>
      `;
      return;
    }

    if (!this.data) {
      this.container.innerHTML = `
        <div class="inspector-container">
          <div class="inspector-placeholder">
            <svg style="width:48px;height:48px;color:#475569" viewBox="0 0 24 24"><path fill="currentColor" d="M9.5,3A6.5,6.5 0 0,1 16,9.5C16,11.11 15.41,12.59 14.44,13.73L14.71,14H15.5L20.5,19L19,20.5L14,15.5V14.71L13.73,14.44C12.59,15.41 11.11,16 9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3M9.5,5C7,5 5,7 5,9.5C5,12 7,14 9.5,14C12,14 14,12 14,9.5C14,7 12,5 9.5,5Z"/></svg>
            Click a drillhole trace or cylinder interval in the 3D viewer to inspect downhole geological records.
          </div>
        </div>
      `;
      return;
    }

    const d = this.data;
    this.container.innerHTML = `
      <div class="inspector-container">
        <div class="inspector-header">
          <div class="inspector-hole-title">
            <svg style="width:24px;height:24px;color:#3b82f6" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2A10 10 0 0,0 2 12A10 10 0 0,0 12 22A10 10 0 0,0 22 12A10 10 0 0,0 12 2M12 4A8 8 0 0,1 20 12A8 8 0 0,1 12 20A8 8 0 0,1 4 12A8 8 0 0,1 12 4M12 6A6 6 0 0,0 6 12A6 6 0 0,0 12 18A6 6 0 0,0 18 12A6 6 0 0,0 12 6Z"/></svg>
            Hole ID: ${d.hole_id}
            <span class="badge-status ${d.hole_status === 'planned' ? 'planned' : 'drilled'}">
              Status: ${d.hole_status === 'planned' ? 'Planned' : 'Drilled'}
            </span>
          </div>
          <div class="inspector-meta-grid">
            <div class="meta-box">
              <div class="meta-lbl">Easting</div>
              <div class="meta-val">${d.easting.toFixed(2)}m</div>
            </div>
            <div class="meta-box">
              <div class="meta-lbl">Northing</div>
              <div class="meta-val">${d.northing.toFixed(2)}m</div>
            </div>
            <div class="meta-box">
              <div class="meta-lbl">Elevation</div>
              <div class="meta-val">${d.elevation.toFixed(2)}m</div>
            </div>
          </div>
          <div style="font-size:0.75rem;color:#64748b;margin-top:8px;">
            Projection UTM Zone: ${d.utm_zone || 'N/A'}
            ${d.total_depth != null ? ` &bull; End of hole: ${d.total_depth.toFixed(2)} m` : ''}
            ${d.hole_type ? ` &bull; Type: ${d.hole_type}` : ''}
          </div>
        </div>

        <div class="inspector-tabs">
          <button class="inspector-tab ${this.activeTab === 'logs' ? 'active' : ''}" id="tab-logs">Downhole Logs</button>
          <button class="inspector-tab ${this.activeTab === 'surveys' ? 'active' : ''}" id="tab-surveys">Survey Stations</button>
        </div>

        <div class="tab-content" style="flex: 1; overflow-y: auto; margin-bottom: 12px;">
          ${this.activeTab === 'logs' ? this.renderLogsTable() : this.renderSurveysTable()}
        </div>

      </div>
    `;

    this.bindEvents();
  }

  renderLogsTable() {
    const intervals = this.data.merged_intervals;
    if (intervals.length === 0) {
      return `<div style="text-align:center;padding:24px;color:#64748b;">No logs available for this hole.</div>`;
    }

    return `
      <table class="table-container">
        <thead>
          <tr>
            <th>From (m)</th>
            <th>To (m)</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          ${intervals.map(int => {
            const isHighlighted = int.interval_id && int.interval_id === this.highlightedIntervalId;
            return `
              <tr class="${isHighlighted ? 'highlighted' : ''} ${int.type === 'unsampled' ? 'row-unsampled' : ''}"
                  data-interval-id="${int.interval_id || ''}"
                  data-tip="${escapeAttr(this.tooltipFor(int))}">
                <td style="font-weight:600">${int.from_depth.toFixed(2)}</td>
                <td>${int.to_depth.toFixed(2)}</td>
                <td>${this.renderIntervalValue(int)}</td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    `;
  }

  /**
   * Tooltip payload for one log row, as a JSON blob on the element.
   *
   * The Sample ID has no column of its own -- it would crowd a narrow panel,
   * and rows are usually read by depth -- so this is where the name of a
   * sample is available. Rows with no Sample ID say so rather than showing an
   * empty heading; plenty of projects carry no such column at all.
   */
  tooltipFor(int) {
    const method = (this.data && this.data.hole_type) || null;
    const holeId = (this.data && this.data.hole_id) || '';
    const depths = `${int.from_depth.toFixed(2)} - ${int.to_depth.toFixed(2)} m`;

    let name;
    let named = true;
    if (int.type === 'unsampled') {
      name = int.label || 'No Sample';
      named = false;
    } else if (int.sample_id) {
      name = int.sample_id;
    } else if (int.type === 'lithology') {
      name = int.lith_code || 'Lithology';
    } else {
      name = 'Unnamed sample';
      named = false;
    }

    const rows = [['Hole', method ? `${holeId} (${method})` : holeId], ['Depth', depths]];
    if (int.type === 'assay' && int.value != null && !int.unsampled) {
      rows.push(['Assay', `${int.below_dl ? '< ' : ''}${int.value.toFixed(3)} ${int.unit || ''}`.trim()]);
    }
    if (int.type === 'lithology' && int.lith_code) rows.push(['Code', int.lith_code]);
    if (int.qaqc_flag) rows.push(['QA/QC', String(int.qaqc_flag).replace(/_/g, ' ')]);
    rows.push(['Length', `${(int.to_depth - int.from_depth).toFixed(2)} m`]);

    return JSON.stringify({ name, named, rows });
  }

  // Value cell for one downhole-log row. Unsampled rows are their own case:
  // they carry no grade at all, so they must never fall through to
  // `value.toFixed(...)` -- and showing "0.000 g/t" for a zone that was never
  // assayed would be a false geological statement.
  renderIntervalValue(int) {
    if (int.type === 'unsampled') {
      return `<span class="badge-unsampled">${int.label || 'No Sample'}</span>
              <span style="font-size:0.7rem;color:#64748b;margin-left:6px;">${(int.to_depth - int.from_depth).toFixed(2)} m</span>`;
    }

    if (int.type === 'assay') {
      // An assay row can still be unsampled: a NULL grade, or a placeholder
      // Sample_ID such as 'NSR' / 'No Sample'.
      if (int.unsampled || int.value === null || int.value === undefined) {
        return `<span class="badge-unsampled">No Sample</span>
                ${int.sample_id ? `<br><span style="font-size:0.7rem;color:#64748b">${int.sample_id}</span>` : ''}`;
      }
      return `
        <span class="badge-assay" style="background:${int.color}22;color:${int.color}">
          ${int.below_dl ? '< ' : ''}${int.value.toFixed(3)} ${int.unit || ''}
        </span>
        ${this.renderQaqcBadge(int.qaqc_flag)}
      `;
    }

    return `
      <span class="badge-lith">
        <span class="color-block" style="background:${this.getLithologyColor(int.lith_code)}"></span>
        <strong>${int.lith_code}</strong>
        ${int.rqd_percent !== undefined && int.rqd_percent !== null ? `<br><span style="font-size:0.7rem;color:#94a3b8">RQD: ${int.rqd_percent}%</span>` : ''}
        ${int.core_recovery_percent !== undefined && int.core_recovery_percent !== null ? `<br><span style="font-size:0.7rem;color:#94a3b8">Recovery: ${int.core_recovery_percent}%</span>` : ''}
      </span>
    `;
  }

  renderSurveysTable() {
    const surveys = this.data.surveys;
    if (surveys.length === 0) {
      return `<div style="text-align:center;padding:24px;color:#64748b;">No surveys recorded. Assume straight down hole.</div>`;
    }

    return `
      <table class="table-container">
        <thead>
          <tr>
            <th>Depth (m)</th>
            <th>Dip (°)</th>
            <th>Azimuth (°)</th>
          </tr>
        </thead>
        <tbody>
          ${surveys.map(s => `
            <tr>
              <td style="font-weight:600">${s.depth.toFixed(2)}</td>
              <td style="color:${s.dip < 0 ? '#f87171' : '#34d399'}">${s.dip.toFixed(2)}</td>
              <td>${s.azimuth.toFixed(2)}°</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }

  getLithologyColor(code) {
    // Import and reuse color map logic
    const LITHOLOGY_COLORS = {
      SND: '#fef08a',
      LST: '#a5f3fc',
      QRT: '#fbcfe8',
      SHL: '#d97706',
      GRN: '#86efac',
      BAS: '#4b5563',
      CLY: '#f59e0b',
    };
    return LITHOLOGY_COLORS[code.toUpperCase()] || '#cbd5e1';
  }

  renderQaqcBadge(flag) {
    if (!flag) return '';
    const QAQC_STYLES = {
      duplicate: { label: 'DUPLICATE', color: '#60a5fa' },
      blank: { label: 'BLANK', color: '#94a3b8' },
      standard: { label: 'STANDARD OK', color: '#34d399' },
      standard_failed: { label: 'STANDARD FAILED', color: '#f87171' },
      unconfigured: { label: 'STD UNCONFIGURED', color: '#fbbf24' }
    };
    const style = QAQC_STYLES[flag] || { label: flag.toUpperCase(), color: '#cbd5e1' };
    return `<br><span class="badge-qaqc" style="display:inline-block;margin-top:3px;padding:1px 6px;border-radius:4px;font-size:0.6rem;font-weight:700;letter-spacing:0.02em;background:${style.color}22;color:${style.color};border:1px solid ${style.color}55;">${style.label}</span>`;
  }

  bindEvents() {
    const tabLogs = this.container.querySelector('#tab-logs');
    const tabSurveys = this.container.querySelector('#tab-surveys');

    if (tabLogs) {
      tabLogs.addEventListener('click', () => {
        this.activeTab = 'logs';
        this.render();
      });
    }

    if (tabSurveys) {
      tabSurveys.addEventListener('click', () => {
        this.activeTab = 'surveys';
        this.render();
      });
    }

    // 3b. Row hover tooltip -- names the sample under the cursor.
    this.bindRowTooltips();

    // 3. Row click selection inside logs table
    const rows = this.container.querySelectorAll('.table-container tbody tr');
    rows.forEach(row => {
      row.addEventListener('click', () => {
        const intId = row.getAttribute('data-interval-id');
        if (!intId) return;
        // Clicking the selected row again deselects it, which is the only way
        // to clear the 3D marker without picking some other sample.
        const next = this.highlightedIntervalId === intId ? null : intId;
        this.highlightedIntervalId = next;
        this.render();
        if (this.onIntervalSelected) this.onIntervalSelected(next);
      });
    });

  }
}

// Row tooltips carry their payload in a data attribute, so quotes and angle
// brackets in a sample id must not be able to break out of it.
function escapeAttr(value) {
  return String(value).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

import { ApiClient } from '../services/api_client.js';

export class InspectorPanel {
  constructor(container, options = {}) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.collarId = null;
    this.data = null;
    this.loading = false;
    this.error = null;
    this.highlightedIntervalId = null; // To highlight a specific interval if clicked in 3D
    this.shareToken = options.shareToken || null;

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
      .table-container tr.highlighted td {
        background: rgba(59, 130, 246, 0.15) !important;
        border-left: 2px solid #3b82f6;
      }
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
    `;
    document.head.appendChild(style);
  }

  async loadCollar(collarId, highlightedIntervalId = null) {
    this.collarId = collarId;
    this.highlightedIntervalId = highlightedIntervalId;
    this.loading = true;
    this.error = null;
    this.render();

    try {
      if (this.shareToken) {
        this.data = await ApiClient.getSharedCollar(this.shareToken, collarId);
      } else {
        this.data = await ApiClient.getCollarDetails(collarId);
      }
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
          <div style="font-size:0.75rem;color:#64748b;margin-top:8px;">Projection UTM Zone: ${d.utm_zone || 'N/A'}</div>
        </div>

        <div class="inspector-tabs">
          <button class="inspector-tab ${this.activeTab === 'logs' ? 'active' : ''}" id="tab-logs">Downhole Logs</button>
          <button class="inspector-tab ${this.activeTab === 'surveys' ? 'active' : ''}" id="tab-surveys">Survey Stations</button>
        </div>

        <div class="tab-content" style="flex: 1; overflow-y: auto; margin-bottom: 12px;">
          ${this.activeTab === 'logs' ? this.renderLogsTable() : this.renderSurveysTable()}
        </div>

        ${this.activeTab === 'logs' && this.highlightedIntervalId ? `
          <div class="true-thickness-calculator" style="margin-top:auto;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:12px;">
            <div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;color:#94a3b8;margin-bottom:8px;display:flex;align-items:center;gap:6px;">
              <svg style="width:16px;height:16px;color:#10b981" viewBox="0 0 24 24"><path fill="currentColor" d="M17,12V15H16V17H13V16H11V17H8V15H7V12H8V10H11V11H13V10H16V12H17M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2Z"/></svg>
              True Thickness Calculator
            </div>
            <div style="display:flex;gap:12px;margin-bottom:10px;">
              <div style="flex:1;display:flex;flex-direction:column;gap:4px;">
                <label style="font-size:0.65rem;color:#64748b;">Vein Dip Direction (°)</label>
                <input type="number" id="vein-dip-dir" value="90" min="0" max="360" style="background:black;border:1px solid rgba(255,255,255,0.2);color:white;padding:4px;border-radius:4px;font-size:0.75rem;width:100%;">
              </div>
              <div style="flex:1;display:flex;flex-direction:column;gap:4px;">
                <label style="font-size:0.65rem;color:#64748b;">Vein Dip Angle (°)</label>
                <input type="number" id="vein-dip-angle" value="45" min="0" max="90" style="background:black;border:1px solid rgba(255,255,255,0.2);color:white;padding:4px;border-radius:4px;font-size:0.75rem;width:100%;">
              </div>
            </div>
            <button class="btn-primary" id="calc-tt-btn" style="padding:6px;font-size:0.75rem;">Calculate True Thickness</button>
            <div id="tt-result" style="margin-top:10px;font-size:0.8125rem;color:#34d399;font-weight:600;display:none;"></div>
          </div>
        ` : ''}
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
            <th>Type</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          ${intervals.map(int => {
            const isHighlighted = int.interval_id === this.highlightedIntervalId;
            return `
              <tr class="${isHighlighted ? 'highlighted' : ''}" data-interval-id="${int.interval_id || ''}">
                <td style="font-weight:600">${int.from_depth.toFixed(2)}</td>
                <td>${int.to_depth.toFixed(2)}</td>
                <td style="text-transform:capitalize;color:#94a3b8">${int.type}</td>
                <td>
                  ${int.type === 'assay' ? `
                    <span class="badge-assay" style="background:${int.color}22;color:${int.color}">
                      ${int.below_dl ? '< ' : ''}${int.value.toFixed(3)} ${int.unit}
                    </span>
                    ${this.renderQaqcBadge(int.qaqc_flag)}
                  ` : `
                    <span class="badge-lith">
                      <span class="color-block" style="background:${this.getLithologyColor(int.lith_code)}"></span>
                      <strong>${int.lith_code}</strong>
                      ${int.rqd_percent !== undefined && int.rqd_percent !== null ? `<br><span style="font-size:0.7rem;color:#94a3b8">RQD: ${int.rqd_percent}%</span>` : ''}
                      ${int.core_recovery_percent !== undefined && int.core_recovery_percent !== null ? `<br><span style="font-size:0.7rem;color:#94a3b8">Recovery: ${int.core_recovery_percent}%</span>` : ''}
                    </span>
                  `}
                </td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
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

    // 3. Row click selection inside logs table
    const rows = this.container.querySelectorAll('.table-container tbody tr');
    rows.forEach(row => {
      row.addEventListener('click', () => {
        const intId = row.getAttribute('data-interval-id');
        if (intId) {
          this.highlightedIntervalId = intId;
          this.render();
        }
      });
    });

    // 4. Calculate True Thickness Button
    const calcBtn = this.container.querySelector('#calc-tt-btn');
    if (calcBtn) {
      calcBtn.addEventListener('click', async () => {
        const dipDirInput = this.container.querySelector('#vein-dip-dir');
        const dipInput = this.container.querySelector('#vein-dip-angle');
        const resDiv = this.container.querySelector('#tt-result');
        
        if (!dipDirInput || !dipInput || !resDiv) return;
        
        const dipDir = Number(dipDirInput.value);
        const dip = Number(dipInput.value);
        
        resDiv.style.display = 'block';
        resDiv.innerHTML = '<span style="color:#64748b">Calculating...</span>';
        
        try {
          let res;
          if (this.shareToken) {
            res = await ApiClient.getSharedTrueThickness(this.shareToken, this.collarId, this.highlightedIntervalId, dipDir, dip);
          } else {
            res = await ApiClient.getTrueThickness(this.collarId, this.highlightedIntervalId, dipDir, dip);
          }
          resDiv.innerHTML = `
            <div>✓ True Thickness: <strong style="color:white;font-size:0.95rem">${res.true_thickness.toFixed(2)}m</strong></div>
            <div style="font-size:0.7rem;color:#94a3b8;font-weight:normal;margin-top:2px;">
              Apparent: ${res.apparent_thickness.toFixed(2)}m | 
              Hole: ${res.hole_dip.toFixed(0)}° / ${res.hole_azimuth.toFixed(0)}° | 
              Angle: ${res.intersection_angle_deg.toFixed(0)}°
            </div>
          `;
        } catch (err) {
          resDiv.innerHTML = `<span style="color:#ef4444">Error: ${err.message}</span>`;
        }
      });
    }
  }
}

import { ApiClient } from '../services/api_client.js';

export class HistoryPanel {
  constructor(container, projectId) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.projectId = projectId;
    this.historyData = null;
    this.loading = false;
    this.error = null;
    
    // For tracing a record
    this.traceEntityId = '';
    this.traceEntityType = 'collar';
    this.traceResult = null;
    this.tracing = false;

    this.init();
  }

  init() {
    this.injectStyles();
    this.loadHistory();
  }

  injectStyles() {
    if (document.getElementById('history-panel-styles')) return;
    const style = document.createElement('style');
    style.id = 'history-panel-styles';
    style.textContent = `
      .history-card {
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        color: #e2e8f0;
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      .history-section-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #f8fafc;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        padding-bottom: 6px;
        margin-bottom: 8px;
      }
      .batch-list {
        display: flex;
        flex-direction: column;
        gap: 10px;
        max-height: 200px;
        overflow-y: auto;
      }
      .batch-item {
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 6px;
        padding: 10px;
        font-size: 0.8rem;
      }
      .batch-meta {
        display: flex;
        justify-content: space-between;
        color: #94a3b8;
        font-size: 0.75rem;
        margin-bottom: 4px;
      }
      .batch-file {
        font-weight: 600;
        color: #3b82f6;
        word-break: break-all;
      }
      
      .trace-form {
        display: flex;
        flex-direction: column;
        gap: 8px;
        background: rgba(0, 0, 0, 0.2);
        padding: 10px;
        border-radius: 6px;
      }
      .trace-input-group {
        display: flex;
        gap: 8px;
      }
      .trace-results {
        margin-top: 8px;
        font-size: 0.8rem;
      }
      .chain-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
        position: relative;
        padding-left: 14px;
        margin-top: 8px;
      }
      .chain-list::before {
        content: '';
        position: absolute;
        left: 4px;
        top: 6px;
        bottom: 6px;
        width: 2px;
        background: #3b82f6;
      }
      .chain-node {
        position: relative;
        padding: 4px 0;
      }
      .chain-node::before {
        content: '';
        position: absolute;
        left: -14px;
        top: 8px;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #3b82f6;
        border: 2px solid var(--bg-darker);
      }
      .chain-node-active {
        font-weight: 700;
        color: #10b981;
      }
      .chain-node-active::before {
        background: #10b981;
      }
    `;
    document.head.appendChild(style);
  }

  async loadHistory() {
    this.loading = true;
    this.render();
    try {
      this.historyData = await ApiClient.getProjectHistory(this.projectId);
    } catch (err) {
      this.error = err.message;
    } finally {
      this.loading = false;
      this.render();
    }
  }

  async runTrace() {
    if (!this.traceEntityId) return alert("Please enter an Entity UUID to trace");
    this.tracing = true;
    this.render();
    try {
      const res = await ApiClient.getProjectHistory(this.projectId, this.traceEntityId, this.traceEntityType);
      this.traceResult = res.supersession_chain;
    } catch (err) {
      alert("Trace failed: " + err.message);
    } finally {
      this.tracing = false;
      this.render();
    }
  }

  render() {
    if (this.loading) {
      this.container.innerHTML = `
        <div class="history-card" style="text-align:center;">
          <div class="loading-spinner" style="width:20px;height:20px;margin:0 auto 10px;"></div>
          Loading audit trail history...
        </div>
      `;
      return;
    }

    if (this.error) {
      this.container.innerHTML = `
        <div class="history-card">
          <div style="color:#ef4444;font-size:0.8rem;text-align:center;">
            Failed to load history: ${this.error}
          </div>
        </div>
      `;
      return;
    }

    const batches = this.historyData ? this.historyData.import_batches : [];

    this.container.innerHTML = `
      <div class="history-card">
        <div>
          <div class="history-section-title">Audit Trail & Imports</div>
          <div class="batch-list">
            ${batches.length === 0 ? `
              <div style="font-size:0.75rem;color:#94a3b8;text-align:center;padding:12px 0;">
                No import logs recorded for this prospect.
              </div>
            ` : batches.map(b => `
              <div class="batch-item">
                <div class="batch-meta">
                  <span>${new Date(b.import_date).toLocaleString()}</span>
                  <span style="color:#10b981;font-weight:600;">${b.status}</span>
                </div>
                <div class="batch-file" title="${b.source_file}">${b.source_file}</div>
                <div style="font-size:0.7rem;color:#94a3b8;margin-top:4px;">Uploader: ${b.importing_user}</div>
              </div>
            `).join('')}
          </div>
        </div>

        <div>
          <div class="history-section-title">Trace Supersession Chain</div>
          <div class="trace-form">
            <div class="trace-input-group">
              <select id="trace-type-select" class="styled-select" style="padding:6px;max-width:110px;">
                <option value="collar" ${this.traceEntityType === 'collar' ? 'selected' : ''}>Drillhole</option>
                <option value="assay" ${this.traceEntityType === 'assay' ? 'selected' : ''}>Assay</option>
                <option value="lithology" ${this.traceEntityType === 'lithology' ? 'selected' : ''}>Lithology</option>
              </select>
              <input type="text" id="trace-id-input" value="${this.traceEntityId}" placeholder="Enter record UUID..." style="flex:1;background:rgba(0,0,0,0.4);border:1px solid rgba(255,255,255,0.1);color:white;padding:6px;border-radius:4px;font-size:0.8rem;">
            </div>
            <button id="trace-submit-btn" class="btn-primary" style="width:100%;padding:6px;font-size:0.8rem;">
              ${this.tracing ? 'Tracing Chain...' : 'Trace Forward'}
            </button>
          </div>
          
          ${this.traceResult ? `
            <div class="trace-results">
              <div style="font-weight:600;color:#94a3b8;font-size:0.75rem;">Supersession Chain:</div>
              ${this.traceResult.length === 0 ? `
                <div style="color:#f59e0b;font-size:0.75rem;margin-top:4px;">Record not found or has no history chain.</div>
              ` : `
                <div class="chain-list">
                  ${this.traceResult.map((n, idx) => `
                    <div class="chain-node ${n.status === 'active' ? 'chain-node-active' : ''}">
                      <div>${n.label || `Record ${idx + 1}`}</div>
                      <div style="font-size:0.65rem;color:#94a3b8;font-family:monospace;">ID: ${n.id} (${n.status})</div>
                    </div>
                  `).join('')}
                </div>
              `}
            </div>
          ` : ''}
        </div>
      </div>
    `;

    // Bind event handlers
    const typeSelect = this.container.querySelector('#trace-type-select');
    if (typeSelect) {
      typeSelect.onchange = (e) => { this.traceEntityType = e.target.value; };
    }

    const idInput = this.container.querySelector('#trace-id-input');
    if (idInput) {
      idInput.oninput = (e) => { this.traceEntityId = e.target.value.trim(); };
    }

    const traceBtn = this.container.querySelector('#trace-submit-btn');
    if (traceBtn) {
      traceBtn.onclick = () => this.runTrace();
    }
  }
}

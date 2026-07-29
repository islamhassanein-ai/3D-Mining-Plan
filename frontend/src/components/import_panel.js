import { ApiClient } from '../services/api_client.js';

export class ImportPanel {
  constructor(container, projectId, onCommit) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.projectId = projectId;
    this.onCommit = onCommit;
    this.selectedFiles = {
      collar_file: null,
      survey_file: null,
      assay_file: null,
      lithology_file: null,
      combined_file: null
    };
    this.batchId = null;
    this.validationData = null;
    this.loading = false;
    this.error = null;
    
    this.init();
  }

  init() {
    this.injectStyles();
    this.render();
  }

  injectStyles() {
    if (document.getElementById('import-panel-styles')) return;
    const style = document.createElement('style');
    style.id = 'import-panel-styles';
    style.textContent = `
      .import-container {
        background: rgba(17, 24, 39, 0.95);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 24px;
        color: #e2e8f0;
        max-width: 600px;
        margin: 20px auto;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(10px);
      }
      .import-title {
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 8px;
        color: #f3f4f6;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .import-subtitle {
        font-size: 0.875rem;
        color: #9ca3af;
        margin-bottom: 24px;
      }
      /* ── Combined (primary) dropzone ── */
      .combined-dropzone-wrap {
        margin-bottom: 20px;
      }
      .combined-label-row {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
      }
      .combined-badge {
        background: linear-gradient(135deg, #3b82f6, #1d4ed8);
        color: white;
        font-size: 0.65rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 2px 8px;
        border-radius: 9999px;
      }
      .combined-label-text {
        font-size: 0.875rem;
        font-weight: 700;
        color: #f3f4f6;
      }
      .combined-hint {
        font-size: 0.75rem;
        color: #6b7280;
        margin-top: 4px;
      }
      .combined-dropzone {
        border: 2px dashed rgba(59, 130, 246, 0.4);
        border-radius: 10px;
        padding: 28px 20px;
        text-align: center;
        cursor: pointer;
        background: rgba(59, 130, 246, 0.04);
        transition: all 0.2s ease;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
      }
      .combined-dropzone:hover {
        border-color: #3b82f6;
        background: rgba(59, 130, 246, 0.09);
      }
      .combined-dropzone.has-file {
        border-color: #10b981;
        background: rgba(16, 185, 129, 0.05);
      }
      .combined-dropzone input {
        display: none;
      }
      /* ── Divider ── */
      .or-divider {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 20px 0 16px;
        color: #4b5563;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }
      .or-divider::before, .or-divider::after {
        content: '';
        flex: 1;
        height: 1px;
        background: rgba(255,255,255,0.08);
      }
      /* ── Legacy four-file grid ── */
      .file-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        margin-bottom: 24px;
      }
      .file-dropzone {
        border: 2px dashed rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 12px;
        text-align: center;
        cursor: pointer;
        background: rgba(255, 255, 255, 0.02);
        transition: all 0.2s ease;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 6px;
      }
      .file-dropzone:hover {
        border-color: #6366f1;
        background: rgba(99, 102, 241, 0.05);
      }
      .file-dropzone.has-file {
        border-color: #10b981;
        background: rgba(16, 185, 129, 0.05);
      }
      .file-dropzone input {
        display: none;
      }
      .file-label {
        font-size: 0.875rem;
        font-weight: 600;
        color: #f3f4f6;
      }
      .file-status {
        font-size: 0.75rem;
        color: #9ca3af;
        word-break: break-all;
      }
      .btn-primary {
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        color: white;
        border: none;
        border-radius: 6px;
        padding: 10px 20px;
        font-weight: 600;
        cursor: pointer;
        transition: transform 0.1s ease, box-shadow 0.2s ease;
        width: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 8px;
      }
      .btn-primary:hover:not(:disabled) {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
      }
      .btn-primary:active:not(:disabled) {
        transform: translateY(0);
      }
      .btn-primary:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .btn-secondary {
        background: transparent;
        color: #d1d5db;
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 6px;
        padding: 10px 20px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
      }
      .btn-secondary:hover {
        background: rgba(255, 255, 255, 0.05);
        color: white;
      }
      .btn-danger {
        background: #ef4444;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 10px 20px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
      }
      .btn-danger:hover {
        background: #dc2626;
      }
      .validation-section {
        border-top: 1px solid rgba(255, 255, 255, 0.1);
        margin-top: 24px;
        padding-top: 24px;
      }
      .status-pill {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 16px;
      }
      .status-pill.success {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
      }
      .status-pill.error {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
      }
      .stats-summary {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
        margin-bottom: 20px;
      }
      .stat-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 6px;
        padding: 10px;
        text-align: center;
      }
      .stat-val {
        font-size: 1.25rem;
        font-weight: 700;
        color: #f3f4f6;
      }
      .stat-lbl {
        font-size: 0.65rem;
        color: #9ca3af;
        text-transform: uppercase;
      }
      .issues-list {
        max-height: 200px;
        overflow-y: auto;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        padding: 8px 12px;
        margin-bottom: 20px;
        background: rgba(0, 0, 0, 0.15);
      }
      .issue-item {
        display: flex;
        gap: 8px;
        font-size: 0.8125rem;
        padding: 6px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      }
      .issue-item:last-child {
        border-bottom: none;
      }
      .issue-badge {
        font-size: 0.65rem;
        font-weight: 700;
        text-transform: uppercase;
        padding: 2px 6px;
        border-radius: 4px;
        height: fit-content;
      }
      .issue-badge.error {
        background: rgba(239, 68, 68, 0.2);
        color: #f87171;
      }
      .issue-badge.warning {
        background: rgba(245, 158, 11, 0.2);
        color: #fbbf24;
      }
      .issue-desc {
        color: #d1d5db;
        line-height: 1.4;
      }
      .utm-confirm-box {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 20px;
        background: rgba(59, 130, 246, 0.05);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 6px;
        padding: 12px;
      }
      .utm-confirm-box label {
        font-size: 0.875rem;
        font-weight: 600;
        color: #93c5fd;
      }
      .utm-confirm-box input {
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.2);
        color: white;
        border-radius: 4px;
        padding: 6px 12px;
        font-size: 0.875rem;
        font-weight: 700;
        width: 80px;
        text-align: center;
      }
      .action-row {
        display: flex;
        justify-content: flex-end;
        gap: 12px;
      }
      .loading-spinner {
        border: 2px solid rgba(255,255,255,0.1);
        border-top: 2px solid #3b82f6;
        border-radius: 50%;
        width: 16px;
        height: 16px;
        animation: spin 1s linear infinite;
        display: inline-block;
      }
      @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }
    `;
    document.head.appendChild(style);
  }

  render() {
    this.container.innerHTML = `
      <div class="import-container">
        <div class="import-title">
          <svg style="width:24px;height:24px" viewBox="0 0 24 24"><path fill="currentColor" d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,20H18A2,2 0 0,0 20,18V8L14,2M12,18L7,13H10V9H14V13H17L12,18M14,9V3.5L18.5,8H14Z"/></svg>
          Import Exploration Data
        </div>
        <div class="import-subtitle">Upload CSV files to preview and validate geological traces.</div>
        
        <div class="combined-dropzone-wrap">
          <div class="combined-label-row">
            <span class="combined-badge">Recommended</span>
            <span class="combined-label-text">Combined Master CSV</span>
          </div>
          ${this.renderCombinedDropzone()}
          <div class="combined-hint">One file for all hole types (DD / RC / TR / CH / FC) across all zones</div>
        </div>

        <div class="or-divider">or use four separate files</div>

        <div class="file-grid">
          ${this.renderDropzone('collar_file', 'Collar CSV')}
          ${this.renderDropzone('survey_file', 'Survey CSV')}
          ${this.renderDropzone('assay_file', 'Assay CSV')}
          ${this.renderDropzone('lithology_file', 'Lithology CSV')}
        </div>

        <button id="upload-btn" class="btn-primary" ${this.hasFiles() ? '' : 'disabled'}>
          ${this.loading ? '<div class="loading-spinner"></div> Processing...' : 'Validate Upload'}
        </button>

        ${this.error ? `<div style="color:#ef4444;margin-top:16px;font-size:0.875rem;">${this.error}</div>` : ''}

        <div id="validation-view" class="validation-section" style="display: none;"></div>
      </div>
    `;

    this.bindEvents();
  }

  renderCombinedDropzone() {
    const file = this.selectedFiles['combined_file'];
    const hasFile = !!file;
    return `
      <div id="zone-combined_file" class="combined-dropzone ${hasFile ? 'has-file' : ''}" data-key="combined_file">
        <input type="file" id="input-combined_file" accept=".csv">
        <svg style="width:36px;height:36px;color:${hasFile ? '#10b981' : '#3b82f6'}" viewBox="0 0 24 24">
          <path fill="currentColor" d="M9,16V10H5L12,3L19,10H15V16H9M5,20V18H19V20H5Z"/>
        </svg>
        <span style="font-size:0.9375rem;font-weight:700;color:${hasFile ? '#34d399' : '#f3f4f6'}">
          ${hasFile ? file.name : 'Drop Combined CSV here or click to browse'}
        </span>
        ${hasFile ? '' : '<span style="font-size:0.75rem;color:#6b7280">Accepts files exported from Excel (BOM encoding supported)</span>'}
      </div>
    `;
  }

  renderDropzone(key, label) {
    const file = this.selectedFiles[key];
    const isHasFile = !!file;
    return `
      <div id="zone-${key}" class="file-dropzone ${isHasFile ? 'has-file' : ''}" data-key="${key}">
        <input type="file" id="input-${key}" accept=".csv">
        <svg style="width:22px;height:22px;color:${isHasFile ? '#10b981' : '#6b7280'}" viewBox="0 0 24 24"><path fill="currentColor" d="M9,16V10H5L12,3L19,10H15V16H9M5,20V18H19V20H5Z"/></svg>
        <span class="file-label">${label}</span>
        <span class="file-status">${file ? file.name : 'Click to select'}</span>
      </div>
    `;
  }

  hasFiles() {
    return Object.values(this.selectedFiles).some(f => f !== null);
  }

  bindEvents() {
    const zones = this.container.querySelectorAll('.file-dropzone, .combined-dropzone');
    zones.forEach(zone => {
      const key = zone.getAttribute('data-key');
      const input = zone.querySelector('input');

      zone.addEventListener('click', () => input.click());

      zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.style.borderColor = '#3b82f6';
      });

      zone.addEventListener('dragleave', () => {
        zone.style.borderColor = '';
      });

      zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.style.borderColor = '';
        if (e.dataTransfer.files.length > 0) {
          this.selectedFiles[key] = e.dataTransfer.files[0];
          this.render();
        }
      });

      input.addEventListener('change', () => {
        if (input.files.length > 0) {
          this.selectedFiles[key] = input.files[0];
          this.render();
        }
      });
    });

    const uploadBtn = this.container.querySelector('#upload-btn');
    if (uploadBtn) {
      uploadBtn.addEventListener('click', () => this.handleUpload());
    }
  }

  async handleUpload() {
    this.loading = true;
    this.error = null;
    this.render();
    
    try {
      const res = await ApiClient.uploadImports(this.projectId, this.selectedFiles);
      this.batchId = res.import_batch_id;
      this.validationData = res.validation;
      this.loading = false;
      this.render();
      this.showValidationResult();
    } catch (err) {
      this.loading = false;
      this.error = err.message || 'An error occurred during upload';
      this.render();
    }
  }

  showValidationResult() {
    const view = this.container.querySelector('#validation-view');
    if (!view || !this.validationData) return;
    
    const v = this.validationData;
    view.style.display = 'block';
    
    const stats = v.summary;
    const isSuccess = v.valid;
    const hasWarnings = v.issues.some(issue => issue.type === 'warning');

    view.innerHTML = `
      <div class="status-pill ${isSuccess ? 'success' : 'error'}">
        ${isSuccess ? 'READY FOR COMMIT' : 'VALIDATION BLOCKED'}
      </div>

      <div class="stats-summary">
        <div class="stat-card">
          <div class="stat-val">${stats.collar_count}</div>
          <div class="stat-lbl">Collars</div>
        </div>
        <div class="stat-card">
          <div class="stat-val">${stats.survey_count}</div>
          <div class="stat-lbl">Surveys</div>
        </div>
        <div class="stat-card">
          <div class="stat-val">${stats.assay_count}</div>
          <div class="stat-lbl">Assays</div>
        </div>
        <div class="stat-card">
          <div class="stat-val">${stats.lithology_count}</div>
          <div class="stat-lbl">Lithology</div>
        </div>
        ${stats.trench_count !== undefined ? `
        <div class="stat-card">
          <div class="stat-val">${stats.trench_count}</div>
          <div class="stat-lbl">Trench pts</div>
        </div>` : ''}
      </div>

      ${v.zones && v.zones.length > 0 ? this.renderZonesBreakdown(v.zones) : ''}

      ${v.issues.length > 0 ? `
        <div style="font-size:0.875rem;font-weight:600;margin-bottom:8px;color:#f3f4f6;">Geological Audit Log:</div>
        <div class="issues-list">
          ${v.issues.map(issue => `
            <div class="issue-item">
              <span class="issue-badge ${issue.type}">${issue.type}</span>
              <div class="issue-desc">
                ${issue.hole_id ? `<strong>[Hole ${issue.hole_id}${issue.row ? `, Row ${issue.row}` : ''}]</strong> ` : ''}
                ${issue.message}
              </div>
            </div>
          `).join('')}
        </div>
      ` : '<div style="color:#10b981;font-size:0.875rem;margin-bottom:20px;">✓ Passed all geological constraints with 0 errors/warnings.</div>'}

      <div class="utm-confirm-box">
        <label for="utm-zone-confirm">Confirm Projection UTM Zone:</label>
        <input type="text" id="utm-zone-confirm" value="${v.detected_utm_zone || '37N'}">
      </div>

      ${hasWarnings ? `
        <label class="acknowledge-warnings-row" style="display:flex;align-items:center;gap:8px;margin:12px 0;font-size:0.875rem;">
          <input type="checkbox" id="acknowledge-warnings-checkbox">
          I have reviewed the flagged warnings above (e.g. overlapping/gapped intervals) and want to commit anyway.
        </label>
      ` : ''}

      <div class="action-row">
        <button id="reject-btn" class="btn-secondary">Reject Batch</button>
        <button id="commit-btn" class="btn-primary" style="width:auto" ${isSuccess ? '' : 'disabled'}>Commit Data</button>
      </div>
    `;

    // Bind commit/reject buttons
    view.querySelector('#reject-btn').addEventListener('click', () => this.handleReject());
    view.querySelector('#commit-btn').addEventListener('click', () => this.handleCommit());
  }

  async handleCommit() {
    const utmZone = this.container.querySelector('#utm-zone-confirm').value.trim();
    if (!utmZone) {
      alert('Please enter a valid UTM zone to commit (e.g., 37N).');
      return;
    }

    const hasWarnings = this.validationData.issues.some(issue => issue.type === 'warning');
    const ackCheckbox = this.container.querySelector('#acknowledge-warnings-checkbox');
    if (hasWarnings && (!ackCheckbox || !ackCheckbox.checked)) {
      alert('Please check the acknowledgment box confirming you reviewed the flagged warnings before committing.');
      return;
    }
    const acknowledgeWarnings = hasWarnings && ackCheckbox.checked;

    this.loading = true;
    this.render();

    try {
      const commitResult = await ApiClient.commitImport(this.projectId, this.batchId, utmZone, acknowledgeWarnings);
      // Multi-project combined imports produce a `batches` summary. A single
      // four-file import still returns one batch row (the URL project). Show
      // the result so creating four new projects is not an invisible side
      // effect of clicking Commit, then reload the scene for the current
      // project (the others are linked from the summary).
      this._renderCommitResult(commitResult);
      this.validationData = null;
      this.batchId = null;
      this.selectedFiles = {
        collar_file: null, survey_file: null, assay_file: null,
        lithology_file: null, combined_file: null
      };
      this.loading = false;
      this.render();
      if (this.onCommit) this.onCommit();
    } catch (err) {
      this.loading = false;
      this.render();
      alert(`Commit failed: ${err.message}`);
    }
  }

  renderZonesBreakdown(zones) {
    // Preview of which projects will be created vs appended BEFORE commit, so
    // the user can reject rather than blindly create four new projects.
    const rows = zones.map(z => {
      const label = z.zone === null || z.zone === undefined
        ? '<em>(no zone — current project)</em>'
        : this._esc(z.zone || '');
      const actionPill = z.action === 'created'
        ? '<span style="color:#fbbf24">will CREATE</span>'
        : '<span style="color:#34d399">APPEND</span>';
      const types = Object.entries(z.hole_type_breakdown || {})
        .map(([t, n]) => `${this._esc(t)}:${n}`).join(', ');
      const pid = z.project_id ? `<code>${z.project_id.slice(0,8)}…</code>` : '<em>new</em>';
      return `<tr>
        <td>${label}</td>
        <td>${actionPill}</td>
        <td>${pid}</td>
        <td>${z.collar_count}</td>
        <td>${z.trench_count}</td>
        <td>${types}</td>
      </tr>`;
    }).join('');
    const styles = `
      .zones-table{width:100%;border-collapse:collapse;font-size:0.78rem;margin-bottom:16px}
      .zones-table th,.zones-table td{padding:5px 8px;border-bottom:1px solid rgba(255,255,255,0.08);text-align:left}
      .zones-table th{color:#9ca3af;font-weight:600;text-transform:uppercase;font-size:0.62rem}
      .zones-title{font-size:0.875rem;font-weight:600;margin:8px 0;color:#f3f4f6}
    `;
    if (!document.getElementById('import-zones-styles')) {
      const s = document.createElement('style'); s.id = 'import-zones-styles'; s.textContent = styles; document.head.appendChild(s);
    }
    return `
      <div class="zones-title">Zone routing preview (projects ${this._hasCreation(zones) ? 'to CREATE &amp; APPEND' : 'to APPEND'})</div>
      <table class="zones-table">
        <thead><tr><th>Zone</th><th>Action</th><th>Project</th><th>Collars</th><th>Trench pts</th><th>Types</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  _hasCreation(zones) { return zones.some(z => z.action === 'created'); }

  _esc(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  _renderCommitResult(commitResult) {
    // Surface the per-project batches after commit so a multi-project import
    // is not invisible (handleCommit previously only reloaded the current
    // project's scene). Logged to console and shown as a dismissible toast;
    // each created/appended project is listed with its id for navigation.
    try {
      const batches = (commitResult && commitResult.batches) || [];
      if (batches.length) {
        const created = batches.filter(b => b.action === 'created');
        const appended = batches.filter(b => b.action === 'appended');
        console.log('Import committed · created', created.length, 'appended', appended.length, batches);
        const lines = batches.map(b =>
          `${this._esc(b.action === 'created' ? 'Created' : 'Appended')} project "${this._esc(b.project_name)}" (${b.collar_count} collars, ${b.trench_count} trench pts) id=${b.project_id}`
        ).join('\n');
        this._toast(`Import committed (${created.length} created, ${appended.length} appended):\n${lines}`);
      }
    } catch (e) { /* non-fatal UI */ }
  }

  _toast(message) {
    const t = document.createElement('div');
    t.className = 'import-commit-toast';
    t.style.cssText = 'position:fixed;right:16px;bottom:16px;max-width:420px;white-space:pre-line;background:rgba(17,24,39,0.97);border:1px solid rgba(16,185,129,0.4);color:#e2e8f0;padding:12px 14px;border-radius:8px;font-size:0.8rem;z-index:9999;box-shadow:0 8px 24px rgba(0,0,0,0.4)';
    t.textContent = message;
    document.body.appendChild(t);
    setTimeout(() => { t.style.transition='opacity 0.4s'; t.style.opacity='0'; setTimeout(()=>t.remove(), 400); }, 7000);
  }

  async handleReject() {
    if (!confirm('Are you sure you want to reject and discard this import batch?')) return;
    
    this.loading = true;
    this.render();
    
    try {
      await ApiClient.rejectImport(this.projectId, this.batchId);
      this.validationData = null;
      this.batchId = null;
      this.loading = false;
      this.render();
    } catch (err) {
      this.loading = false;
      this.render();
      alert(`Reject failed: ${err.message}`);
    }
  }
}

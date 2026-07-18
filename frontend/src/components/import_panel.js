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
      lithology_file: null
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
      .file-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
        margin-bottom: 24px;
      }
      .file-dropzone {
        border: 2px dashed rgba(255, 255, 255, 0.15);
        border-radius: 8px;
        padding: 16px;
        text-align: center;
        cursor: pointer;
        background: rgba(255, 255, 255, 0.02);
        transition: all 0.2s ease;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
      }
      .file-dropzone:hover {
        border-color: #3b82f6;
        background: rgba(59, 130, 246, 0.05);
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

  renderDropzone(key, label) {
    const file = this.selectedFiles[key];
    const isHasFile = !!file;
    return `
      <div id="zone-${key}" class="file-dropzone ${isHasFile ? 'has-file' : ''}" data-key="${key}">
        <input type="file" id="input-${key}" accept=".csv">
        <svg style="width:28px;height:28px;color:${isHasFile ? '#10b981' : '#9ca3af'}" viewBox="0 0 24 24"><path fill="currentColor" d="M9,16V10H5L12,3L19,10H15V16H9M5,20V18H19V20H5Z"/></svg>
        <span class="file-label">${label}</span>
        <span class="file-status">${file ? file.name : 'Drag & drop or click'}</span>
      </div>
    `;
  }

  hasFiles() {
    return Object.values(this.selectedFiles).some(f => f !== null);
  }

  bindEvents() {
    const zones = this.container.querySelectorAll('.file-dropzone');
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
      </div>

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
        <input type="text" id="utm-zone-confirm" value="${v.detected_utm_zone || '36N'}">
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
      alert('Please enter a valid UTM zone to commit (e.g., 36N).');
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
      await ApiClient.commitImport(this.projectId, this.batchId, utmZone, acknowledgeWarnings);
      this.validationData = null;
      this.batchId = null;
      this.selectedFiles = { collar_file: null, survey_file: null, assay_file: null, lithology_file: null };
      this.loading = false;
      this.render();
      if (this.onCommit) this.onCommit();
    } catch (err) {
      this.loading = false;
      this.render();
      alert(`Commit failed: ${err.message}`);
    }
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

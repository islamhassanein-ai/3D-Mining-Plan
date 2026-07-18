export class ExportPanel {
  constructor(container, projectId, sectionPanelRef = null) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.projectId = projectId;
    this.sectionPanelRef = sectionPanelRef;
    this.statusMessage = '';
    this.statusType = ''; // 'info', 'success', 'error'
    this.loading = {
      csv: false,
      pdf: false,
      dxf: false
    };

    this.init();
  }

  init() {
    this.injectStyles();
    this.render();
  }

  injectStyles() {
    if (document.getElementById('export-panel-styles')) return;
    const style = document.createElement('style');
    style.id = 'export-panel-styles';
    style.textContent = `
      .export-panel-card {
        background: rgba(15, 23, 42, 0.95);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 24px;
        color: #e2e8f0;
        display: flex;
        flex-direction: column;
        gap: 20px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
      }
      .export-header {
        margin-bottom: 8px;
      }
      .export-header h3 {
        margin: 0 0 6px 0;
        font-size: 1.25rem;
        font-weight: 700;
        color: #f8fafc;
        background: linear-gradient(135deg, #3b82f6, #60a5fa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
      }
      .export-header p {
        margin: 0;
        font-size: 0.85rem;
        color: #94a3b8;
        line-height: 1.4;
      }
      .export-grid {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      .export-option-row {
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 16px;
        display: flex;
        align-items: center;
        gap: 16px;
        transition: all 0.2s ease-in-out;
      }
      .export-option-row:hover {
        background: rgba(30, 41, 59, 0.7);
        border-color: rgba(59, 130, 246, 0.3);
        transform: translateY(-1px);
      }
      .export-icon-container {
        width: 48px;
        height: 48px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }
      .icon-csv {
        background: rgba(16, 185, 129, 0.15);
        color: #10b981;
      }
      .icon-pdf {
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
      }
      .icon-dxf {
        background: rgba(59, 130, 246, 0.15);
        color: #3b82f6;
      }
      .export-details {
        flex: 1;
      }
      .export-title {
        font-weight: 600;
        font-size: 0.95rem;
        color: #f8fafc;
        margin-bottom: 4px;
      }
      .export-desc {
        font-size: 0.75rem;
        color: #94a3b8;
        line-height: 1.3;
      }
      .btn-export-download {
        background: #1e293b;
        color: #f8fafc;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 0.8rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.15s ease;
        display: flex;
        align-items: center;
        gap: 6px;
        white-space: nowrap;
      }
      .btn-export-download:hover:not(:disabled) {
        background: #3b82f6;
        border-color: #3b82f6;
        color: white;
      }
      .btn-export-download:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .export-status-banner {
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 0.8rem;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 8px;
        animation: fadeIn 0.2s ease-out;
      }
      .status-info {
        background: rgba(59, 130, 246, 0.1);
        border: 1px solid rgba(59, 130, 246, 0.2);
        color: #60a5fa;
      }
      .status-success {
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.2);
        color: #34d399;
      }
      .status-error {
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.2);
        color: #f87171;
      }
      @keyframes fadeIn {
        from { opacity: 0; transform: translateY(4px); }
        to { opacity: 1; transform: translateY(0); }
      }
      .spinner-small {
        width: 14px;
        height: 14px;
        border: 2px solid rgba(255, 255, 255, 0.2);
        border-top-color: currentColor;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
        display: inline-block;
      }
      @keyframes spin {
        to { transform: rotate(360deg); }
      }
    `;
    document.head.appendChild(style);
  }

  getApiBaseUrl() {
    return (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') ? 'http://localhost:8000' : '';
  }

  getHeaders() {
    const token = localStorage.getItem('mining_session_token');
    const headers = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  async handleDownload(format) {
    const apiBase = this.getApiBaseUrl();
    const headers = this.getHeaders();
    
    this.loading[format] = true;
    this.statusMessage = `Preparing ${format.toUpperCase()} export...`;
    this.statusType = 'info';
    this.render();

    try {
      let query = '';
      if (format === 'csv') {
        const entitySelect = this.container.querySelector('#export-csv-entity');
        const entity = entitySelect ? entitySelect.value : '';
        if (entity) query = `?entity=${encodeURIComponent(entity)}`;
      }
      if (format === 'pdf' && this.sectionPanelRef && this.sectionPanelRef.active) {
        const p = this.sectionPanelRef;
        const params = new URLSearchParams({
          plane_type: p.type,
          offset: String(p.offset),
          thickness: String(p.thickness),
          azimuth: String(p.azimuth)
        });
        query = `?${params.toString()}`;
      }

      const routePaths = { csv: 'data.csv', pdf: 'section.pdf', dxf: 'wireframes.dxf' };
      const res = await fetch(`${apiBase}/projects/${this.projectId}/export/${routePaths[format]}${query}`, {
        headers
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Failed to export ${format.toUpperCase()}`);
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;

      const csvEntity = query.includes('entity=') ? query.split('entity=')[1] : null;
      let filename = `project_${this.projectId}_export.${format}`;
      if (format === 'csv') filename = csvEntity ? `project_${this.projectId}_${csvEntity}.csv` : `project_${this.projectId}_drillholes.zip`;
      else if (format === 'pdf') filename = `project_${this.projectId}_section.pdf`;
      else if (format === 'dxf') filename = `project_${this.projectId}_wireframes.dxf`;

      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      this.statusMessage = `${format.toUpperCase()} downloaded successfully!`;
      this.statusType = 'success';
    } catch (err) {
      this.statusMessage = err.message;
      this.statusType = 'error';
    } finally {
      this.loading[format] = false;
      this.render();
    }
  }

  render() {
    this.container.innerHTML = `
      <div class="export-panel-card">
        <div class="export-header">
          <h3>Export Project Workspace</h3>
          <p>Download geological models, sections, and interval database records in industry-standard formats.</p>
        </div>

        <div class="export-grid">
          <!-- CSV (ZIP) Drillholes -->
          <div class="export-option-row">
            <div class="export-icon-container icon-csv">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
              </svg>
            </div>
            <div class="export-details">
              <div class="export-title">Drillhole Data (CSV)</div>
              <div class="export-desc">Includes Collars, Surveys, Assays, and Lithologies formatted for re-import or external database loads.</div>
              <select id="export-csv-entity" style="margin-top:8px;background:#0f172a;color:#e2e8f0;border:1px solid rgba(255,255,255,0.1);border-radius:6px;padding:4px 8px;font-size:0.75rem;">
                <option value="">All entities (ZIP)</option>
                <option value="collars">Collars only</option>
                <option value="surveys">Surveys only</option>
                <option value="assays">Assays only</option>
                <option value="lithologies">Lithologies only</option>
              </select>
            </div>
            <button class="btn-export-download" id="export-csv-download" ${this.loading.csv ? 'disabled' : ''}>
              ${this.loading.csv ? '<span class="spinner-small"></span> Exporting...' : 'Download'}
            </button>
          </div>

          <!-- Section View PDF -->
          <div class="export-option-row">
            <div class="export-icon-container icon-pdf">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
              </svg>
            </div>
            <div class="export-details">
              <div class="export-title">Cross-Section Report (PDF)</div>
              <div class="export-desc">Central cross-section view sheet highlighting drillhole paths, assays, and geological wireframe intercepts.</div>
            </div>
            <button class="btn-export-download" id="export-pdf-download" ${this.loading.pdf ? 'disabled' : ''}>
              ${this.loading.pdf ? '<span class="spinner-small"></span> Exporting...' : 'Download PDF'}
            </button>
          </div>

          <!-- DXF Wireframes -->
          <div class="export-option-row">
            <div class="export-icon-container icon-dxf">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                <polyline points="2 17 12 22 22 17"></polyline>
                <polyline points="2 12 12 17 22 12"></polyline>
              </svg>
            </div>
            <div class="export-details">
              <div class="export-title">3D solids & Surfaces (DXF)</div>
              <div class="export-desc">CAD-compatible format containing vein solids, fault meshes, and geological boundary surfaces.</div>
            </div>
            <button class="btn-export-download" id="export-dxf-download" ${this.loading.dxf ? 'disabled' : ''}>
              ${this.loading.dxf ? '<span class="spinner-small"></span> Exporting...' : 'Download DXF'}
            </button>
          </div>
        </div>

        <!-- Status banner -->
        ${this.statusMessage ? `
          <div class="export-status-banner status-${this.statusType}">
            ${this.statusType === 'info' ? '<span class="spinner-small"></span>' : ''}
            <span>${this.statusMessage}</span>
          </div>
        ` : ''}
      </div>
    `;

    // Add event listeners
    const csvBtn = this.container.querySelector('#export-csv-download');
    if (csvBtn) {
      csvBtn.onclick = () => this.handleDownload('csv');
    }

    const pdfBtn = this.container.querySelector('#export-pdf-download');
    if (pdfBtn) {
      pdfBtn.onclick = () => this.handleDownload('pdf');
    }

    const dxfBtn = this.container.querySelector('#export-dxf-download');
    if (dxfBtn) {
      dxfBtn.onclick = () => this.handleDownload('dxf');
    }
  }
}

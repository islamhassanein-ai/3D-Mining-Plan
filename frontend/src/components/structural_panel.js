import { ApiClient } from '../services/api_client.js';

export class StructuralPanel {
  constructor(container, projectId, onDataChanged = null) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.projectId = projectId;
    this.onDataChanged = onDataChanged;
    this.render();
  }

  render() {
    this.container.innerHTML = `
      <div class="modal-body" style="padding: 16px; color: var(--text-light);">
        <div style="margin-bottom: 20px;">
          <div style="display:flex; align-items:center; justify-content:space-between;">
            <h4 style="margin:0;">Existing Readings</h4>
            <button id="struct-delete-all-btn" class="btn-small" style="color:#f87171;">Remove all</button>
          </div>
          <div id="struct-list-container" style="max-height: 150px; overflow-y: auto; background: rgba(0,0,0,0.2); border-radius: 6px; padding: 8px; border: 1px solid var(--border-light); font-size: 0.8rem;">
            Loading readings...
          </div>
        </div>

        <hr style="border: 0; border-top: 1px solid var(--border-light); margin: 20px 0;">

        <div style="margin-bottom: 20px;">
          <h4>Add Single Reading</h4>
          <form id="single-struct-form" style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.8rem;">
            <div>
              <label>Reading Type</label>
              <select id="struct-type" style="width:100%; background:black; color:white; border: 1px solid var(--border-light); padding: 4px; border-radius: 4px;">
                <option value="fault_trace">Fault Trace</option>
                <option value="dip_strike">Dip/Strike Measurement</option>
              </select>
            </div>
            <div>
              <label>Easting</label>
              <input type="number" id="struct-east" step="any" required style="width:100%; background:black; color:white; border: 1px solid var(--border-light); padding: 4px; border-radius: 4px;">
            </div>
            <div>
              <label>Northing</label>
              <input type="number" id="struct-north" step="any" required style="width:100%; background:black; color:white; border: 1px solid var(--border-light); padding: 4px; border-radius: 4px;">
            </div>
            <div>
              <label>Elevation</label>
              <input type="number" id="struct-elev" step="any" required style="width:100%; background:black; color:white; border: 1px solid var(--border-light); padding: 4px; border-radius: 4px;">
            </div>
            <div>
              <label>Dip (0 - 90°)</label>
              <input type="number" id="struct-dip" min="0" max="90" step="any" style="width:100%; background:black; color:white; border: 1px solid var(--border-light); padding: 4px; border-radius: 4px;">
            </div>
            <div>
              <label>Strike (0 - 360°)</label>
              <input type="number" id="struct-strike" min="0" max="360" step="any" style="width:100%; background:black; color:white; border: 1px solid var(--border-light); padding: 4px; border-radius: 4px;">
            </div>
            <div style="grid-column: span 2; margin-top: 8px;">
              <button type="submit" class="btn-small" style="width: 100%;">Create Reading</button>
            </div>
          </form>
        </div>

        <hr style="border: 0; border-top: 1px solid var(--border-light); margin: 20px 0;">

        <div>
          <h4>Bulk Import CSV</h4>
          <p style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 8px;">CSV Columns: reading_type, easting, northing, elevation, dip, strike</p>
          <div style="display: flex; gap: 8px;">
            <input type="file" id="struct-file-input" accept=".csv" style="font-size: 0.8rem; flex-grow: 1;">
            <button id="import-struct-btn" class="btn-small">Import CSV</button>
          </div>
          <!-- Structural readings have no natural key to match on (no hole_id
               or trench_id), so a re-import cannot tell a correction from a
               genuinely new reading. This checkbox is how the geologist says
               which one it is. -->
          <label style="display:flex; align-items:center; gap:6px; margin-top:8px; font-size:0.75rem; color:var(--text-muted); cursor:pointer;">
            <input type="checkbox" id="struct-replace-mode">
            Replace existing readings (use this when re-importing a corrected file)
          </label>
        </div>

        <div id="struct-modal-status" style="margin-top:12px; font-size:0.8rem; font-weight:600; text-align:center;"></div>
      </div>
    `;

    this.listContainer = this.container.querySelector('#struct-list-container');
    this.statusDiv = this.container.querySelector('#struct-modal-status');

    this.loadReadings();
    this.bindEvents();
  }

  async loadReadings() {
    try {
      const data = await ApiClient.getStructuralReadings(this.projectId);
      if (data.length === 0) {
        this.listContainer.textContent = "No structural readings recorded.";
        return;
      }
      this.listContainer.innerHTML = `
        <table style="width: 100%; border-collapse: collapse; text-align: left;">
          <thead>
            <tr style="border-bottom: 1px solid var(--border-light);">
              <th style="padding: 4px;">Type</th>
              <th style="padding: 4px;">Easting</th>
              <th style="padding: 4px;">Northing</th>
              <th style="padding: 4px;">Elev</th>
              <th style="padding: 4px;">Dip/Strike</th>
              <th style="padding: 4px;"></th>
            </tr>
          </thead>
          <tbody>
            ${data.map(r => `
              <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td style="padding: 4px; color: ${r.reading_type === 'fault_trace' ? '#ef4444' : '#eab308'}">${r.reading_type}</td>
                <td style="padding: 4px;">${r.easting.toFixed(1)}</td>
                <td style="padding: 4px;">${r.northing.toFixed(1)}</td>
                <td style="padding: 4px;">${r.elevation.toFixed(1)}</td>
                <td style="padding: 4px;">${r.dip !== null ? r.dip.toFixed(0) : '-'}° / ${r.strike !== null ? r.strike.toFixed(0) : '-'}°</td>
                <td style="padding: 4px; text-align: right;">
                  <button class="struct-del-btn" data-reading-id="${r.id}" title="Delete this reading"
                          style="background:none; border:none; color:var(--text-muted); cursor:pointer; padding:0 2px; font-size:0.95rem; line-height:1;">&times;</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
      this.bindDeleteButtons();
    } catch (err) {
      this.listContainer.textContent = "Error loading readings: " + err.message;
    }
  }

  // Re-bound on every loadReadings(), since the rows are rebuilt each time.
  bindDeleteButtons() {
    this.listContainer.querySelectorAll('.struct-del-btn').forEach(btn => {
      btn.onclick = async () => {
        const id = btn.dataset.readingId;
        if (!confirm('Delete this structural reading? It leaves the 3D scene and the Depth Planner immediately.')) return;
        this.statusDiv.textContent = 'Deleting reading...';
        try {
          await ApiClient.deleteStructuralReading(this.projectId, id);
          this.statusDiv.innerHTML = '<span style="color:var(--accent-green)">✓ Reading deleted.</span>';
          await this.loadReadings();
          if (this.onDataChanged) await this.onDataChanged();
        } catch (err) {
          this.statusDiv.innerHTML = `<span style="color:#f87171">Error: ${err.message}</span>`;
        }
      };
    });
  }

  bindEvents() {
    this.container.querySelector('#single-struct-form').onsubmit = async (e) => {
      e.preventDefault();
      this.statusDiv.textContent = "Creating reading...";
      const reading_type = this.container.querySelector('#struct-type').value;
      const easting = parseFloat(this.container.querySelector('#struct-east').value);
      const northing = parseFloat(this.container.querySelector('#struct-north').value);
      const elevation = parseFloat(this.container.querySelector('#struct-elev').value);

      const dipVal = this.container.querySelector('#struct-dip').value;
      const strikeVal = this.container.querySelector('#struct-strike').value;

      const dip = dipVal ? parseFloat(dipVal) : null;
      const strike = strikeVal ? parseFloat(strikeVal) : null;

      try {
        await ApiClient.createStructuralReading(this.projectId, { reading_type, easting, northing, elevation, dip, strike });
        this.statusDiv.innerHTML = '<span style="color:var(--accent-green)">✓ Reading added successfully!</span>';
        await this.loadReadings();
        if (this.onDataChanged) await this.onDataChanged();
      } catch (err) {
        this.statusDiv.innerHTML = `<span style="color:#f87171">Error: ${err.message}</span>`;
      }
    };

    this.container.querySelector('#struct-delete-all-btn').onclick = async () => {
      if (!confirm('Remove every structural reading in this project? Use this to clear duplicates before re-importing a corrected CSV.')) return;
      this.statusDiv.textContent = 'Removing readings...';
      try {
        const result = await ApiClient.deleteAllStructuralReadings(this.projectId);
        this.statusDiv.innerHTML = `<span style="color:var(--accent-green)">✓ ${result.message}</span>`;
        await this.loadReadings();
        if (this.onDataChanged) await this.onDataChanged();
      } catch (err) {
        this.statusDiv.innerHTML = `<span style="color:#f87171">Error: ${err.message}</span>`;
      }
    };

    this.container.querySelector('#import-struct-btn').onclick = async () => {
      const file = this.container.querySelector('#struct-file-input').files[0];
      if (!file) return alert("Select CSV file first");

      const replace = this.container.querySelector('#struct-replace-mode').checked;
      if (replace && !confirm('Replace mode: every existing structural reading in this project will be retired and only the rows in this CSV will remain. Continue?')) return;

      this.statusDiv.textContent = "Importing CSV...";
      try {
        const result = await ApiClient.importStructuralCsv(this.projectId, file, replace ? 'replace' : 'append');
        this.statusDiv.innerHTML = `<span style="color:var(--accent-green)">✓ ${result.message}</span>`;
        await this.loadReadings();
        if (this.onDataChanged) await this.onDataChanged();
      } catch (err) {
        this.statusDiv.innerHTML = `<span style="color:#f87171">Error: ${err.message}</span>`;
      }
    };
  }
}

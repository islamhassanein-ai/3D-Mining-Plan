import { ApiClient } from '../services/api_client.js';

export class QaqcPanel {
  constructor(container, projectId) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.projectId = projectId;
    this.render();
  }

  render() {
    this.container.innerHTML = `
      <div class="modal-body" style="padding: 16px; color: var(--text-light);">
        <div style="margin-bottom: 20px;">
          <h4>Registered Standards</h4>
          <div id="qaqc-list-container" style="max-height: 150px; overflow-y: auto; background: rgba(0,0,0,0.2); border-radius: 6px; padding: 8px; border: 1px solid var(--border-light); font-size: 0.8rem;">
            Loading standards...
          </div>
        </div>

        <hr style="border: 0; border-top: 1px solid var(--border-light); margin: 20px 0;">

        <div>
          <h4>Add Reference Standard</h4>
          <form id="qaqc-standard-form" style="display: flex; flex-direction: column; gap: 8px; font-size: 0.8rem;">
            <div>
              <label>Standard Name (matches qaqc_standard in CSV)</label>
              <input type="text" id="qaqc-name" required placeholder="e.g. STD_GOLD_01" style="width:100%; background:black; color:white; border: 1px solid var(--border-light); padding: 4px; border-radius: 4px;">
            </div>
            <div style="display: flex; gap: 8px;">
              <div style="flex: 1;">
                <label>Expected Min</label>
                <input type="number" id="qaqc-min" step="any" required placeholder="1.2" style="width:100%; background:black; color:white; border: 1px solid var(--border-light); padding: 4px; border-radius: 4px;">
              </div>
              <div style="flex: 1;">
                <label>Expected Max</label>
                <input type="number" id="qaqc-max" step="any" required placeholder="1.5" style="width:100%; background:black; color:white; border: 1px solid var(--border-light); padding: 4px; border-radius: 4px;">
              </div>
              <div style="flex: 1;">
                <label>Grade Unit</label>
                <input type="text" id="qaqc-unit" required placeholder="ppm" style="width:100%; background:black; color:white; border: 1px solid var(--border-light); padding: 4px; border-radius: 4px;">
              </div>
            </div>
            <button type="submit" class="btn-small" style="margin-top: 8px; width: 100%;">Add Standard</button>
          </form>
        </div>

        <div id="qaqc-modal-status" style="margin-top:12px; font-size:0.8rem; font-weight:600; text-align:center;"></div>
      </div>
    `;

    this.listContainer = this.container.querySelector('#qaqc-list-container');
    this.statusDiv = this.container.querySelector('#qaqc-modal-status');

    this.loadStandards();
    this.bindEvents();
  }

  async loadStandards() {
    try {
      const data = await ApiClient.getQaqcStandards(this.projectId);
      if (data.length === 0) {
        this.listContainer.textContent = "No reference standards registered yet.";
        return;
      }
      this.listContainer.innerHTML = `
        <table style="width: 100%; border-collapse: collapse; text-align: left;">
          <thead>
            <tr style="border-bottom: 1px solid var(--border-light);">
              <th style="padding: 4px;">Standard Name</th>
              <th style="padding: 4px;">Expected Range</th>
              <th style="padding: 4px;">Unit</th>
            </tr>
          </thead>
          <tbody>
            ${data.map(s => `
              <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td style="padding: 4px; font-weight: 600;">${s.standard_name}</td>
                <td style="padding: 4px;">${s.expected_grade_min.toFixed(2)} - ${s.expected_grade_max.toFixed(2)}</td>
                <td style="padding: 4px; color: var(--accent-green);">${s.grade_unit}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (err) {
      this.listContainer.textContent = "Error loading standards: " + err.message;
    }
  }

  bindEvents() {
    this.container.querySelector('#qaqc-standard-form').onsubmit = async (e) => {
      e.preventDefault();
      this.statusDiv.textContent = "Adding standard...";
      const standard_name = this.container.querySelector('#qaqc-name').value;
      const expected_grade_min = parseFloat(this.container.querySelector('#qaqc-min').value);
      const expected_grade_max = parseFloat(this.container.querySelector('#qaqc-max').value);
      const grade_unit = this.container.querySelector('#qaqc-unit').value;

      try {
        await ApiClient.createQaqcStandard(this.projectId, { standard_name, expected_grade_min, expected_grade_max, grade_unit });
        this.statusDiv.innerHTML = '<span style="color:var(--accent-green)">✓ Standard added successfully!</span>';
        await this.loadStandards();
      } catch (err) {
        this.statusDiv.innerHTML = `<span style="color:#f87171">Error: ${err.message}</span>`;
      }
    };
  }
}

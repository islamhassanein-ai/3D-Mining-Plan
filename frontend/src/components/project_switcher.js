import { ApiClient } from '../services/api_client.js';

export class ProjectSwitcher {
  constructor(selectElement, onSelectCallback) {
    this.select = typeof selectElement === 'string' ? document.getElementById(selectElement) : selectElement;
    this.onSelect = onSelectCallback;
    this.bindEvents();
  }

  async loadProjects() {
    try {
      const projects = await ApiClient.getWorkspaceProjects();
      this.render(projects);
      return projects;
    } catch (err) {
      console.error('Failed to load workspace projects:', err);
      return [];
    }
  }

  render(projects) {
    // Preserve current selection if it still exists in the new list
    const currentVal = this.select.value;
    
    this.select.innerHTML = '<option value="">Select Project...</option>';
    projects.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.name} (${p.commodity || 'Gold'})`;
      this.select.appendChild(opt);
    });
    
    if (currentVal && projects.some(p => p.id === currentVal)) {
      this.select.value = currentVal;
    }
  }

  bindEvents() {
    this.select.addEventListener('change', (e) => {
      const pid = e.target.value;
      if (this.onSelect) {
        this.onSelect(pid);
      }
    });
  }
}

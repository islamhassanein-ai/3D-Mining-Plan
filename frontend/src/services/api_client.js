const API_BASE_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') ? 'http://localhost:8000' : '';

function getHeaders() {
  const token = localStorage.getItem('mining_session_token');
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export const ApiClient = {
  // Authentication
  async loginMagicLink(email) {
    const res = await fetch(`${API_BASE_URL}/auth/magic-link`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    if (!res.ok) throw new Error('Failed to request magic link');
    return res.json();
  },

  async verifyMagicLink(token) {
    const res = await fetch(`${API_BASE_URL}/auth/verify?token=${encodeURIComponent(token)}`);
    if (!res.ok) throw new Error('Verification failed');
    const data = await res.json();
    localStorage.setItem('mining_session_token', data.access_token);
    return data;
  },

  logout() {
    localStorage.removeItem('mining_session_token');
  },

  isLoggedIn() {
    return !!localStorage.getItem('mining_session_token');
  },

  async getWorkspaceProjects() {
    const res = await fetch(`${API_BASE_URL}/workspace/projects`, {
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch workspace projects');
    return res.json();
  },

  // Projects
  async createProject(name, commodity) {
    const res = await fetch(`${API_BASE_URL}/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getHeaders()
      },
      body: JSON.stringify({ name, commodity })
    });
    if (!res.ok) throw new Error('Failed to create project');
    return res.json();
  },

  async getProject(projectId) {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}`, {
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch project');
    return res.json();
  },

  async deleteProject(projectId) {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to delete project' }));
      throw new Error(err.detail || 'Failed to delete project');
    }
    return true;
  },

  async updateProject(projectId, fields) {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...getHeaders()
      },
      body: JSON.stringify(fields)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to update project' }));
      throw new Error(err.detail || 'Failed to update project');
    }
    return res.json();
  },

  // Imports
  async uploadImports(projectId, files) {
    const formData = new FormData();
    if (files.collar_file) formData.append('collar_file', files.collar_file);
    if (files.survey_file) formData.append('survey_file', files.survey_file);
    if (files.assay_file) formData.append('assay_file', files.assay_file);
    if (files.lithology_file) formData.append('lithology_file', files.lithology_file);

    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/imports`, {
      method: 'POST',
      headers: getHeaders(),
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },

  async getImportBatch(projectId, batchId) {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/imports/${batchId}`, {
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Failed to get import batch details');
    return res.json();
  },

  async commitImport(projectId, batchId, utmZoneConfirm, acknowledgeWarnings = false) {
    const params = new URLSearchParams({
      utm_zone_confirm: utmZoneConfirm,
      acknowledge_warnings: acknowledgeWarnings ? 'true' : 'false'
    });
    const res = await fetch(
      `${API_BASE_URL}/projects/${projectId}/imports/${batchId}/commit?${params.toString()}`,
      {
        method: 'POST',
        headers: getHeaders()
      }
    );
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to commit import');
    }
    return res.json();
  },

  async rejectImport(projectId, batchId) {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/imports/${batchId}/reject`, {
      method: 'POST',
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Failed to reject import');
    return res.json();
  },

  // Scene & Geometries
  async getProjectScene(projectId) {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/scene`, {
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch scene data');
    return res.json();
  },

  // Collars
  async getCollarDetails(collarId) {
    const res = await fetch(`${API_BASE_URL}/collars/${collarId}`, {
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch collar details');
    return res.json();
  },

  async getTrueThickness(collarId, intervalId, dipDirection, dip) {
    const params = new URLSearchParams({
      interval_id: intervalId,
      dip_direction: dipDirection,
      dip: dip
    });
    const res = await fetch(
      `${API_BASE_URL}/collars/${collarId}/true-thickness?${params.toString()}`,
      {
        headers: getHeaders()
      }
    );
    if (!res.ok) throw new Error('Failed to fetch true thickness');
    return res.json();
  },

  // Share Links (Owner Management)
  async createShareLink(projectId) {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/share-links`, {
      method: 'POST',
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Failed to create share link');
    return res.json();
  },

  async listShareLinks(projectId) {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/share-links`, {
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Failed to list share links');
    return res.json();
  },

  async revokeShareLink(projectId, linkId) {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/share-links/${linkId}/revoke`, {
      method: 'POST',
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Failed to revoke share link');
    return res.json();
  },

  async renewShareLink(projectId, linkId) {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/share-links/${linkId}/renew`, {
      method: 'POST',
      headers: getHeaders()
    });
    if (!res.ok) {
      if (res.status === 409) {
        const err = await res.json();
        throw new Error(err.detail || 'Link is already revoked or expired');
      }
      throw new Error('Failed to renew share link');
    }
    return res.json();
  },

  // Token-Authenticated Colleague Viewer Routes (No JWT needed)
  async getSharedScene(token) {
    const res = await fetch(`${API_BASE_URL}/share/${token}/scene`);
    if (!res.ok) {
      if (res.status === 410) {
        throw new Error('GONG_EXPIRED'); // flag to show access-ended warning UI
      }
      throw new Error('Failed to fetch shared scene');
    }
    return res.json();
  },

  async getSharedCollar(token, collarId) {
    const res = await fetch(`${API_BASE_URL}/share/${token}/collars/${collarId}`);
    if (!res.ok) throw new Error('Failed to fetch shared collar details');
    return res.json();
  },

  async getSharedTrueThickness(token, collarId, intervalId, dipDirection, dip) {
    const params = new URLSearchParams({
      interval_id: intervalId,
      dip_direction: dipDirection,
      dip: dip
    });
    const res = await fetch(
      `${API_BASE_URL}/share/${token}/collars/${collarId}/true-thickness?${params.toString()}`
    );
    if (!res.ok) throw new Error('Failed to calculate true thickness');
    return res.json();
  },

  async getProjectHistory(projectId, entityId = null, entityType = null) {
    const params = new URLSearchParams();
    if (entityId) params.append('entity_id', entityId);
    if (entityType) params.append('entity_type', entityType);

    const url = `${API_BASE_URL}/projects/${projectId}/history${params.toString() ? '?' + params.toString() : ''}`;
    const res = await fetch(url, {
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Failed to fetch project history');
    return res.json();
  },

  // Structural Readings
  async getStructuralReadings(projectId) {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/structural`, {
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Failed to load structural readings');
    return res.json();
  },

  async createStructuralReading(projectId, reading) {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/structural`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getHeaders()
      },
      body: JSON.stringify(reading)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Creation failed' }));
      throw new Error(err.detail || 'Creation failed');
    }
    return res.json();
  },

  async importStructuralCsv(projectId, file) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/structural/import`, {
      method: 'POST',
      headers: getHeaders(),
      body: formData
    });
    if (!res.ok) throw new Error('Import failed');
    return res.json();
  },

  // QA/QC Standards
  async getQaqcStandards(projectId) {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/qaqc`, {
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Failed to load QA/QC standards');
    return res.json();
  },

  async createQaqcStandard(projectId, standard) {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/qaqc`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getHeaders()
      },
      body: JSON.stringify(standard)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Addition failed' }));
      throw new Error(err.detail || 'Addition failed');
    }
    return res.json();
  }
};

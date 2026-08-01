// SceneDataSource implementations per contracts/api.md §4.
// All methods are async so callers never branch on which source they hold.

import { ApiClient } from './api_client.js';
import { parseOBJ } from '../scene/wireframes.js';
import { parseTopographyCSV } from '../scene/topography.js';

const API_BASE_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://localhost:8000' : '';

async function _fetchTopographyPoints(topographyRef) {
  if (!topographyRef) return null;
  const response = await fetch(`${API_BASE_URL}/uploads/${topographyRef}`);
  if (!response.ok) throw new Error('Failed to download topography file');
  const text = await response.text();
  return parseTopographyCSV(text);
}

async function _fetchWireframeGeometry(wireframe) {
  if (!wireframe.file_ref) return null;
  const response = await fetch(`${API_BASE_URL}/uploads/${wireframe.file_ref}`);
  if (!response.ok) throw new Error(`Failed to load wireframe file: ${wireframe.file_ref}`);
  const text = await response.text();
  const parsed = parseOBJ(text);
  return { vertices: parsed.vertices, indices: parsed.indices };
}

export class ApiDataSource {
  constructor(projectId) {
    this.projectId = projectId;
    this.isStatic = false;
  }
  async getScene() { return ApiClient.getProjectScene(this.projectId); }
  async getCollarDetails(collarId) { return ApiClient.getCollarDetails(collarId); }
  async getTopographyPoints(topographyRef) { return _fetchTopographyPoints(topographyRef); }
  async getWireframeGeometry(wireframe) { return _fetchWireframeGeometry(wireframe); }
}

export class ShareTokenDataSource {
  constructor(token) {
    this.token = token;
    this.isStatic = false;
  }
  async getScene() { return ApiClient.getSharedScene(this.token); }
  async getCollarDetails(collarId) { return ApiClient.getSharedCollar(this.token, collarId); }
  async getTopographyPoints(topographyRef) { return _fetchTopographyPoints(topographyRef); }
  async getWireframeGeometry(wireframe) { return _fetchWireframeGeometry(wireframe); }
}


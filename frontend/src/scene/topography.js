import * as THREE from 'three';

export class TopographyRenderer {
  constructor(scene) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.name = 'topography-surface';
    this.scene.add(this.group);
  }

  async loadAndRender(fileRef) {
    this.clear();
    if (!fileRef) return;

    try {
      // Fetch the topography CSV file content
      const API_BASE_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') ? 'http://localhost:8000' : '';
      const response = await fetch(`${API_BASE_URL}/uploads/${fileRef}`);
      if (!response.ok) throw new Error('Failed to download topography file');
      
      const text = await response.text();
      this.renderCSVPoints(text);
    } catch (err) {
      console.error('Failed to render topography:', err);
    }
  }

  renderCSVPoints(csvText) {
    const lines = csvText.split('\n');
    if (lines.length < 2) return;

    // Parse headers
    const headers = lines[0].strip ? lines[0].strip().toLowerCase().split(',') : lines[0].toLowerCase().split(',');
    const eIdx = headers.findIndex(h => h.includes('east'));
    const nIdx = headers.findIndex(h => h.includes('north'));
    const elIdx = headers.findIndex(h => h.includes('elev') || h.includes('z') || h.includes('alt'));

    if (eIdx === -1 || nIdx === -1 || elIdx === -1) {
      console.warn('Topography CSV headers must contain Easting, Northing, and Elevation');
      return;
    }

    const points = [];
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;
      
      const cols = line.split(',');
      const e = parseFloat(cols[eIdx]);
      const n = parseFloat(cols[nIdx]);
      const el = parseFloat(cols[elIdx]);

      if (!isNaN(e) && !isNaN(n) && !isNaN(el)) {
        // Map to Three.js Y-up (Easting -> X, Elevation -> Y, Northing -> Z)
        points.push(new THREE.Vector3(e, el, n));
      }
    }

    if (points.length === 0) return;

    // Render as a techy semi-transparent point cloud
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.PointsMaterial({
      color: 0x3b82f6, // techy blue
      size: 4.0,
      transparent: true,
      opacity: 0.6,
      sizeAttenuation: true
    });

    const pointCloud = new THREE.Points(geometry, material);
    pointCloud.userData = { type: 'topography_points' };
    this.group.add(pointCloud);

    // Also draw a bounding wireframe boundary for context
    const box = new THREE.Box3().setFromPoints(points);
    const helper = new THREE.Box3Helper(box, 0x1e3a8a);
    this.group.add(helper);
  }

  clear() {
    this.group.traverse((child) => {
      if (child.geometry) child.geometry.dispose();
      if (child.material) {
        if (Array.isArray(child.material)) {
          child.material.forEach(m => m.dispose());
        } else {
          child.material.dispose();
        }
      }
    });
    while (this.group.children.length > 0) {
      this.group.remove(this.group.children[0]);
    }
  }
}

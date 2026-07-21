import * as THREE from 'three';
import { ApiClient } from '../services/api_client.js';

export class SceneLoader {
  constructor(scene, controls, tracesRenderer, assaysRenderer, lithologiesRenderer, topographyRenderer, trenchesRenderer, wireframesRenderer, structuralRenderer, lodManager, boreholeLabelsRenderer) {
    this.scene = scene;
    this.controls = controls;
    this.tracesRenderer = tracesRenderer;
    this.assaysRenderer = assaysRenderer;
    this.lithologiesRenderer = lithologiesRenderer;
    this.topographyRenderer = topographyRenderer;
    this.trenchesRenderer = trenchesRenderer;
    this.wireframesRenderer = wireframesRenderer;
    this.structuralRenderer = structuralRenderer;
    this.lodManager = lodManager;
    this.boreholeLabelsRenderer = boreholeLabelsRenderer;
    this.loading = false;
  }

  async loadProject(projectId) {
    if (this.loading) return;
    this.loading = true;
    
    try {
      const data = await ApiClient.getProjectScene(projectId);
      
      // 1. Render elements
      this.tracesRenderer.render(data.drillholes);
      this.assaysRenderer.render(data.drillholes);
      this.lithologiesRenderer.render(data.drillholes);
      
      if (this.topographyRenderer) await this.topographyRenderer.loadAndRender(data.topography_ref);
      if (this.trenchesRenderer) this.trenchesRenderer.render(data.trenches, data.drillholes);
      if (this.wireframesRenderer) await this.wireframesRenderer.render(data.wireframes);
      if (this.structuralRenderer) this.structuralRenderer.render(data.structural_readings);
      if (this.boreholeLabelsRenderer) this.boreholeLabelsRenderer.render(data.drillholes);

      // 2. Feed LOD manager with drillhole collar positions
      if (this.lodManager) this.lodManager.setDrillholes(data.drillholes);
      
      // 3. Adjust camera to fit data
      this.fitCameraToData(data.drillholes);
      
      this.loading = false;
      return data;
    } catch (err) {
      this.loading = false;
      console.error('Failed to load project scene:', err);
      throw err;
    }
  }

  async loadSharedProject(token) {
    if (this.loading) return;
    this.loading = true;
    
    try {
      const data = await ApiClient.getSharedScene(token);
      
      // 1. Render elements
      this.tracesRenderer.render(data.drillholes);
      this.assaysRenderer.render(data.drillholes);
      this.lithologiesRenderer.render(data.drillholes);
      
      if (this.topographyRenderer) await this.topographyRenderer.loadAndRender(data.topography_ref);
      if (this.trenchesRenderer) this.trenchesRenderer.render(data.trenches, data.drillholes);
      if (this.wireframesRenderer) await this.wireframesRenderer.render(data.wireframes);
      if (this.structuralRenderer) this.structuralRenderer.render(data.structural_readings);
      if (this.boreholeLabelsRenderer) this.boreholeLabelsRenderer.render(data.drillholes);

      // 2. Feed LOD manager with drillhole collar positions
      if (this.lodManager) this.lodManager.setDrillholes(data.drillholes);
      
      // 3. Adjust camera to fit data
      this.fitCameraToData(data.drillholes);
      
      this.loading = false;
      return data;
    } catch (err) {
      this.loading = false;
      console.error('Failed to load shared project scene:', err);
      throw err;
    }
  }

  fitCameraToData(drillholes) {
    if (!drillholes || drillholes.length === 0) return;
    
    const bbox = new THREE.Box3();
    let hasPoints = false;
    
    for (const dh of drillholes) {
      // Add collar position (Easting -> X, Elevation -> Y, Northing -> Z)
      bbox.expandByPoint(new THREE.Vector3(dh.easting, dh.elevation, dh.northing));
      hasPoints = true;
      
      // Add trace points
      for (const p of dh.trace) {
        bbox.expandByPoint(new THREE.Vector3(p.x, p.z, p.y));
      }
    }
    
    if (!hasPoints) return;
    
    const center = new THREE.Vector3();
    bbox.getCenter(center);
    
    const size = new THREE.Vector3();
    bbox.getSize(size);
    
    const maxDim = Math.max(size.x, size.y, size.z);
    const fov = this.controls.camera.fov * (Math.PI / 180);
    
    // Calculate appropriate camera distance
    let cameraDistance = Math.abs(maxDim / (2 * Math.tan(fov / 2)));
    // Add some padding
    cameraDistance *= 1.5;
    
    // Default to at least 100 units away if project is tiny or point-like
    if (cameraDistance < 100) cameraDistance = 100;
    
    // Position camera looking at center from an isometric-like angle
    const cameraPosition = new THREE.Vector3()
      .copy(center)
      .add(new THREE.Vector3(cameraDistance * 0.7, cameraDistance * 0.7, cameraDistance * 0.7));
      
    this.controls.camera.position.copy(cameraPosition);
    this.controls.setTarget(center);
    this.controls.update();
  }
}

import * as THREE from 'three';

export class MeasurementTool {
  constructor(viewportInstance, onResultCallback) {
    this.viewport = viewportInstance; // init3DViewport result
    this.onResult = onResultCallback; // Callback when distance is calculated

    this.active = false;
    
    this.pointA = null;
    this.pointB = null;
    
    this.markers = []; // [sphereA, sphereB]
    this.line = null;  // THREE.Line connecting points
    
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();

    this.onPointerDown = this.onPointerDown.bind(this);
    this.onPointerMove = this.onPointerMove.bind(this);
  }

  setActive(active) {
    this.active = !!active;
    this.reset();
    
    if (this.active) {
      this.viewport.renderer.domElement.addEventListener('pointerdown', this.onPointerDown);
      this.viewport.renderer.domElement.addEventListener('pointermove', this.onPointerMove);
      this.viewport.renderer.domElement.style.cursor = 'crosshair';
    } else {
      this.viewport.renderer.domElement.removeEventListener('pointerdown', this.onPointerDown);
      this.viewport.renderer.domElement.removeEventListener('pointermove', this.onPointerMove);
      this.viewport.renderer.domElement.style.cursor = '';
    }
  }

  reset() {
    this.pointA = null;
    this.pointB = null;
    
    // Clear meshes from scene
    for (const marker of this.markers) {
      this.viewport.scene.remove(marker);
      if (marker.geometry) marker.geometry.dispose();
      if (marker.material) marker.material.dispose();
    }
    this.markers = [];
    
    if (this.line) {
      this.viewport.scene.remove(this.line);
      if (this.line.geometry) this.line.geometry.dispose();
      if (this.line.material) this.line.material.dispose();
      this.line = null;
    }
    
    if (this.onResult) this.onResult(null);
  }

  getIntersectionPoint(event) {
    const rect = this.viewport.renderer.domElement.getBoundingClientRect();
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.pointer, this.viewport.camera);
    
    // Intersect objects in the scene
    const intersects = this.raycaster.intersectObjects(this.viewport.scene.children, true);
    // Ignore measurement markers & lines in intersection
    const valid = intersects.filter(hit => 
      hit.object !== this.line && 
      !this.markers.includes(hit.object) &&
      hit.object.name !== 'slicing-plane-helper'
    );
    
    if (valid.length > 0) {
      return valid[0].point;
    }
    return null;
  }

  createMarker(position, color = 0xef4444) {
    const geometry = new THREE.SphereGeometry(1.5, 16, 16);
    const material = new THREE.MeshBasicMaterial({ color, depthTest: false, depthWrite: false });
    const sphere = new THREE.Mesh(geometry, material);
    sphere.position.copy(position);
    sphere.renderOrder = 999; // Render on top
    this.viewport.scene.add(sphere);
    this.markers.push(sphere);
  }

  onPointerDown(event) {
    if (event.button !== 0) return; // Left click only
    
    const hitPoint = this.getIntersectionPoint(event);
    if (!hitPoint) return;

    if (!this.pointA) {
      // Set Point A
      this.pointA = hitPoint.clone();
      this.createMarker(this.pointA, 0x3b82f6); // Blue marker
    } else if (!this.pointB) {
      // Set Point B
      this.pointB = hitPoint.clone();
      this.createMarker(this.pointB, 0xef4444); // Red marker
      
      // Compute final measurements
      this.calculateMeasurements();
      
      // Remove listeners so it locks the measurement
      this.viewport.renderer.domElement.removeEventListener('pointermove', this.onPointerMove);
    } else {
      // Third click resets and starts new measurement
      this.reset();
      this.pointA = hitPoint.clone();
      this.createMarker(this.pointA, 0x3b82f6);
      this.viewport.renderer.domElement.addEventListener('pointermove', this.onPointerMove);
    }
  }

  onPointerMove(event) {
    if (!this.pointA || this.pointB) return;
    
    const hitPoint = this.getIntersectionPoint(event);
    if (!hitPoint) return;
    
    // Draw/update temporary dashed line
    if (this.line) {
      this.viewport.scene.remove(this.line);
      this.line.geometry.dispose();
    }
    
    const geometry = new THREE.BufferGeometry().setFromPoints([this.pointA, hitPoint]);
    const material = new THREE.LineDashedMaterial({
      color: 0x60a5fa,
      dashSize: 3,
      gapSize: 2,
      depthTest: false,
      depthWrite: false
    });
    
    this.line = new THREE.Line(geometry, material);
    this.line.computeLineDistances();
    this.line.renderOrder = 998;
    this.viewport.scene.add(this.line);

    // Calculate real-time temporary measurements
    this.calculateRealtimeMeasurements(hitPoint);
  }

  calculateRealtimeMeasurements(currentPoint) {
    const distance = this.pointA.distanceTo(currentPoint);
    
    // Map coords back to geology space (x=Easting, y=Elevation, z=Northing)
    const dx = Math.abs(currentPoint.x - this.pointA.x);
    const dy = Math.abs(currentPoint.z - this.pointA.z); // Northing is Z in Y-up Three.js
    const dz = Math.abs(currentPoint.y - this.pointA.y); // Elevation is Y in Y-up Three.js
    
    if (this.onResult) {
      this.onResult({
        distance,
        dx,
        dy,
        dz,
        completed: false
      });
    }
  }

  calculateMeasurements() {
    const distance = this.pointA.distanceTo(this.pointB);
    
    const dx = Math.abs(this.pointB.x - this.pointA.x);
    const dy = Math.abs(this.pointB.z - this.pointA.z); // Northing
    const dz = Math.abs(this.pointB.y - this.pointA.y); // Elevation
    
    // Draw solid line
    if (this.line) {
      this.viewport.scene.remove(this.line);
      this.line.geometry.dispose();
    }
    
    const geometry = new THREE.BufferGeometry().setFromPoints([this.pointA, this.pointB]);
    const material = new THREE.LineBasicMaterial({
      color: 0x10b981, // solid green
      linewidth: 3,
      depthTest: false,
      depthWrite: false
    });
    
    this.line = new THREE.Line(geometry, material);
    this.line.renderOrder = 998;
    this.viewport.scene.add(this.line);
    
    if (this.onResult) {
      this.onResult({
        distance,
        dx,
        dy,
        dz,
        completed: true
      });
    }
  }
}

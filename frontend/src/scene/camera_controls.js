import * as THREE from 'three';

export class DampedCameraControls {
  constructor(camera, domElement, scene) {
    this.camera = camera;
    this.domElement = domElement;
    this.scene = scene;

    // Target point to orbit around
    this.target = new THREE.Vector3(0, 0, 0);

    // Spherical coordinates relative to target
    this.spherical = new THREE.Spherical();
    this.sphericalTarget = new THREE.Spherical();
    this.updateSphericalFromCamera();

    // Damping factor (0 to 1, higher = faster, lower = smoother)
    this.dampingFactor = 0.1;

    // State
    this.state = 'NONE'; // 'NONE', 'ROTATE', 'PAN', 'ZOOM'
    
    // Rotation speeds
    this.rotateSpeed = 1.0;
    this.panSpeed = 1.0;
    this.zoomSpeed = 1.5;

    // Raycaster for cursor target picking
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();

    // Event listeners
    this.onPointerDown = this.onPointerDown.bind(this);
    this.onPointerMove = this.onPointerMove.bind(this);
    this.onPointerUp = this.onPointerUp.bind(this);
    this.onWheel = this.onWheel.bind(this);
    this.onContextMenu = this.onContextMenu.bind(this);

    this.domElement.addEventListener('pointerdown', this.onPointerDown);
    this.domElement.addEventListener('pointermove', this.onPointerMove);
    this.domElement.addEventListener('pointerup', this.onPointerUp);
    this.domElement.addEventListener('wheel', this.onWheel);
    this.domElement.addEventListener('contextmenu', this.onContextMenu);

    // Screen dimensions
    this.width = this.domElement.clientWidth;
    this.height = this.domElement.clientHeight;
  }

  updateSphericalFromCamera() {
    const offset = new THREE.Vector3().copy(this.camera.position).sub(this.target);
    this.spherical.setFromVector3(offset);
    this.sphericalTarget.copy(this.spherical);
  }

  setTarget(newTarget) {
    this.target.copy(newTarget);
    this.updateSphericalFromCamera();
  }

  update() {
    // Damping spherical coordinates
    this.spherical.theta += (this.sphericalTarget.theta - this.spherical.theta) * this.dampingFactor;
    this.spherical.phi += (this.sphericalTarget.phi - this.spherical.phi) * this.dampingFactor;
    this.spherical.radius += (this.sphericalTarget.radius - this.spherical.radius) * this.dampingFactor;

    // Prevent gimbal lock
    this.spherical.makeSafe();

    // Reconstruct camera position
    const offset = new THREE.Vector3().setFromSpherical(this.spherical);
    this.camera.position.copy(this.target).add(offset);
    this.camera.lookAt(this.target);
  }

  pickTargetUnderCursor(clientX, clientY) {
    const rect = this.domElement.getBoundingClientRect();
    this.pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.pointer, this.camera);
    
    // Only intersect visible meshes/objects
    const intersects = this.raycaster.intersectObjects(this.scene.children, true);
    if (intersects.length > 0) {
      const hitPoint = intersects[0].point;
      // Recenter target without shifting camera view
      const oldOffset = new THREE.Vector3().copy(this.camera.position).sub(this.target);
      this.target.copy(hitPoint);
      
      // Keep camera in same spot but adjust target
      const newOffset = new THREE.Vector3().copy(this.camera.position).sub(this.target);
      this.sphericalTarget.setFromVector3(newOffset);
      this.spherical.copy(this.sphericalTarget);
      return true;
    }
    return false;
  }

  setPreset(preset) {
    const radius = this.sphericalTarget.radius;
    if (preset === 'plan') {
      // Top down view (phi close to 0 to prevent gimbal lock jitter)
      this.sphericalTarget.set(radius, 0.001, 0);
    } else if (preset === 'section_ns') {
      // Looking North-South (phi = PI/2, theta = 0)
      this.sphericalTarget.set(radius, Math.PI / 2, 0);
    } else if (preset === 'section_ew') {
      // Looking East-West (phi = PI/2, theta = PI/2)
      this.sphericalTarget.set(radius, Math.PI / 2, Math.PI / 2);
    } else if (preset === 'isometric') {
      // Tilted isometric view (phi = PI/4, theta = PI/4)
      this.sphericalTarget.set(radius, Math.PI / 4, Math.PI / 4);
    }
  }

  // Re-centers the orbit target on a UTM coordinate (Easting/Northing/
  // Elevation), keeping the current viewing angle and distance so the user
  // doesn't lose their orientation when jumping across the site.
  goToCoordinate(easting, northing, elevation) {
    const target = new THREE.Vector3(easting, elevation, northing);
    this.target.copy(target);
    const offset = new THREE.Vector3().setFromSpherical(this.sphericalTarget);
    this.camera.position.copy(target).add(offset);
    this.updateSphericalFromCamera();
  }

  onPointerDown(event) {
    event.preventDefault();

    if (event.button === 0) { // Left click: Rotate
      this.state = 'ROTATE';
      // Attempt to set orbit pivot under cursor
      this.pickTargetUnderCursor(event.clientX, event.clientY);
    } else if (event.button === 2) { // Right click: Pan
      this.state = 'PAN';
    } else if (event.button === 1) { // Middle click: Zoom
      this.state = 'ZOOM';
    }

    this.prevX = event.clientX;
    this.prevY = event.clientY;
    this.domElement.setPointerCapture(event.pointerId);
  }

  onPointerMove(event) {
    if (this.state === 'NONE') return;
    event.preventDefault();

    const deltaX = event.clientX - this.prevX;
    const deltaY = event.clientY - this.prevY;
    
    this.prevX = event.clientX;
    this.prevY = event.clientY;

    if (this.state === 'ROTATE') {
      const thetaDelta = -(2 * Math.PI * deltaX / this.domElement.clientWidth) * this.rotateSpeed;
      const phiDelta = -(2 * Math.PI * deltaY / this.domElement.clientHeight) * this.rotateSpeed;
      
      this.sphericalTarget.theta += thetaDelta;
      this.sphericalTarget.phi += phiDelta;
    } else if (this.state === 'PAN') {
      // Pan camera in local plane
      const offset = new THREE.Vector3().copy(this.camera.position).sub(this.target);
      const distance = offset.length();
      
      // Calculate pan factor based on distance
      const factorX = 2 * distance * Math.tan((this.camera.fov * Math.PI / 360)) * (this.domElement.clientWidth / this.domElement.clientHeight) / this.domElement.clientWidth;
      const factorY = 2 * distance * Math.tan((this.camera.fov * Math.PI / 360)) / this.domElement.clientHeight;

      const vecX = new THREE.Vector3().setFromMatrixColumn(this.camera.matrix, 0).multiplyScalar(-deltaX * factorX * this.panSpeed);
      const vecY = new THREE.Vector3().setFromMatrixColumn(this.camera.matrix, 1).multiplyScalar(deltaY * factorY * this.panSpeed);
      
      const panVector = vecX.add(vecY);
      this.target.add(panVector);
      this.camera.position.add(panVector);
    } else if (this.state === 'ZOOM') {
      const zoomFactor = 1.0 + (deltaY / this.domElement.clientHeight) * this.zoomSpeed;
      this.sphericalTarget.radius *= zoomFactor;
    }
  }

  onPointerUp(event) {
    this.state = 'NONE';
    try {
      this.domElement.releasePointerCapture(event.pointerId);
    } catch (e) {}
  }

  onWheel(event) {
    event.preventDefault();
    const zoomFactor = 1.0 + (event.deltaY * 0.001) * this.zoomSpeed;
    // Set zoom target
    this.sphericalTarget.radius *= zoomFactor;
    // Lower radius limit to prevent going past target
    this.sphericalTarget.radius = Math.max(1.0, this.sphericalTarget.radius);
  }

  onContextMenu(event) {
    event.preventDefault();
  }

  dispose() {
    this.domElement.removeEventListener('pointerdown', this.onPointerDown);
    this.domElement.removeEventListener('pointermove', this.onPointerMove);
    this.domElement.removeEventListener('pointerup', this.onPointerUp);
    this.domElement.removeEventListener('wheel', this.onWheel);
    this.domElement.removeEventListener('contextmenu', this.onContextMenu);
  }
}

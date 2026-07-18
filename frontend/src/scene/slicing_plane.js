import * as THREE from 'three';

export class SlicingPlane {
  constructor(scene) {
    this.scene = scene;
    
    // Default settings
    this.type = 'EW'; // 'NS', 'EW', 'AZIMUTH'
    this.normal = new THREE.Vector3(1, 0, 0); // Default EW normal (along Easting/X axis)
    this.offset = 0.0; // Offset along normal from the center
    this.thickness = 20.0; // Envelope thickness (meters)
    this.azimuth = 0.0; // For arbitrary rotation (degrees)
    
    this.center = new THREE.Vector3(0, 0, 0);
    this.visible = false;
    
    // Plane helper elements
    this.helperMesh = null;
    this.initHelper();
  }

  initHelper() {
    const geometry = new THREE.PlaneGeometry(1000, 1000);
    const material = new THREE.MeshBasicMaterial({
      color: 0x3b82f6,
      transparent: true,
      opacity: 0.15,
      side: THREE.DoubleSide,
      depthWrite: false
    });
    
    this.helperMesh = new THREE.Mesh(geometry, material);
    this.helperMesh.name = 'slicing-plane-helper';
    this.helperMesh.visible = this.visible;
    this.scene.add(this.helperMesh);
    
    // Add a dashed border line around the plane for visibility
    const edges = new THREE.EdgesGeometry(geometry);
    const lineMat = new THREE.LineBasicMaterial({ color: 0x60a5fa, transparent: true, opacity: 0.5 });
    const line = new THREE.LineSegments(edges, lineMat);
    this.helperMesh.add(line);
    
    this.updateHelper();
  }

  setCenter(newCenter) {
    this.center.copy(newCenter);
    this.updateHelper();
  }

  updatePlaneOrientation() {
    if (this.type === 'EW') {
      this.normal.set(1, 0, 0); // slice parallel to Y-Z (Elevation-Northing)
    } else if (this.type === 'NS') {
      this.normal.set(0, 0, 1); // slice parallel to X-Y (Easting-Elevation)
    } else {
      // Arbitrary Azimuth (angle around vertical Y axis)
      const rad = (this.azimuth * Math.PI) / 180;
      this.normal.set(Math.cos(rad), 0, Math.sin(rad));
    }
  }

  updateHelper() {
    if (!this.helperMesh) return;
    
    this.updatePlaneOrientation();
    
    // Set helper position = center + normal * offset
    const pos = new THREE.Vector3()
      .copy(this.normal)
      .multiplyScalar(this.offset)
      .add(this.center);
      
    this.helperMesh.position.copy(pos);
    
    // Rotate plane helper to face the normal vector
    // PlaneGeometry faces +Z by default
    const alignVector = new THREE.Vector3(0, 0, 1);
    const quaternion = new THREE.Quaternion().setFromUnitVectors(alignVector, this.normal);
    this.helperMesh.quaternion.copy(quaternion);
  }

  setVisible(visible) {
    this.visible = !!visible;
    if (this.helperMesh) this.helperMesh.visible = this.visible;
  }

  setParams(type, offset, thickness, azimuth = 0) {
    this.type = type;
    this.offset = Number(offset);
    this.thickness = Number(thickness);
    this.azimuth = Number(azimuth);
    
    this.updateHelper();
  }

  getDistanceToPlane(point) {
    // Distance from point to plane: d = (point - plane_origin) . normal
    const planeOrigin = new THREE.Vector3()
      .copy(this.normal)
      .multiplyScalar(this.offset)
      .add(this.center);
      
    const diff = new THREE.Vector3().subVectors(point, planeOrigin);
    return diff.dot(this.normal);
  }

  projectPoint2D(point) {
    // Project 3D coordinate (Easting, Elevation, Northing) in Y-up space to 2D (u, v) on the slice plane
    // v is always the vertical Y axis (Elevation)
    // u is the horizontal direction perpendicular to normal on the plane
    
    const v = point.y; // Elevation
    
    let u = 0;
    if (this.type === 'EW') {
      u = point.z; // Northing along horizontal axis
    } else if (this.type === 'NS') {
      u = point.x; // Easting along horizontal axis
    } else {
      // Horizontal axis perpendicular to normal: tangent = (-sin(azimuth), 0, cos(azimuth))
      const rad = (this.azimuth * Math.PI) / 180;
      const tangent = new THREE.Vector3(-Math.sin(rad), 0, Math.cos(rad));
      u = point.dot(tangent);
    }
    
    return { u, v };
  }

  sliceDrillholes(drillholes) {
    // Returns sliced 2D lines and intervals that lie within the thickness envelope
    const slicedTraces = [];
    const slicedAssays = [];
    const slicedLiths = [];
    
    const halfThick = this.thickness / 2;

    for (const dh of drillholes) {
      // 1. Process traces
      const currentSegments = [];
      let lastPointInside = null;
      let lastPoint2D = null;
      
      for (const p of dh.trace) {
        // Map trace coords back to Three.js Y-up for calculations
        const p3d = new THREE.Vector3(p.x, p.z, p.y);
        const dist = this.getDistanceToPlane(p3d);
        
        if (Math.abs(dist) <= halfThick) {
          const pt2D = this.projectPoint2D(p3d);
          
          if (lastPointInside) {
            currentSegments.push({
              start: lastPoint2D,
              end: pt2D,
              hole_id: dh.hole_id
            });
          }
          lastPointInside = p3d;
          lastPoint2D = pt2D;
        } else {
          lastPointInside = null;
          lastPoint2D = null;
        }
      }
      
      if (currentSegments.length > 0) {
        slicedTraces.push({
          hole_id: dh.hole_id,
          segments: currentSegments
        });
      }

      // 2. Process assays
      for (const assay of dh.assays) {
        const start3D = new THREE.Vector3(assay.start_pos[0], assay.start_pos[2], assay.start_pos[1]);
        const end3D = new THREE.Vector3(assay.end_pos[0], assay.end_pos[2], assay.end_pos[1]);
        
        const midPoint = new THREE.Vector3().addVectors(start3D, end3D).multiplyScalar(0.5);
        const dist = this.getDistanceToPlane(midPoint);
        
        if (Math.abs(dist) <= halfThick) {
          slicedAssays.push({
            hole_id: dh.hole_id,
            grade_value: assay.grade_value,
            color: assay.color,
            start: this.projectPoint2D(start3D),
            end: this.projectPoint2D(end3D)
          });
        }
      }

      // 3. Process lithologies
      for (const lith of dh.lithologies) {
        const start3D = new THREE.Vector3(lith.start_pos[0], lith.start_pos[2], lith.start_pos[1]);
        const end3D = new THREE.Vector3(lith.end_pos[0], lith.end_pos[2], lith.end_pos[1]);
        
        const midPoint = new THREE.Vector3().addVectors(start3D, end3D).multiplyScalar(0.5);
        const dist = this.getDistanceToPlane(midPoint);
        
        if (Math.abs(dist) <= halfThick) {
          slicedLiths.push({
            hole_id: dh.hole_id,
            lith_code: lith.lith_code,
            start: this.projectPoint2D(start3D),
            end: this.projectPoint2D(end3D)
          });
        }
      }
    }

    return {
      traces: slicedTraces,
      assays: slicedAssays,
      lithologies: slicedLiths,
      limits: this.calculateSlicedLimits(slicedTraces)
    };
  }

  calculateSlicedLimits(slicedTraces) {
    // Calculates bounding box limits for the 2D canvas view
    let minU = Infinity, maxU = -Infinity;
    let minV = Infinity, maxV = -Infinity;
    
    for (const dh of slicedTraces) {
      for (const seg of dh.segments) {
        minU = Math.min(minU, seg.start.u, seg.end.u);
        maxU = Math.max(maxU, seg.start.u, seg.end.u);
        minV = Math.min(minV, seg.start.v, seg.end.v);
        maxV = Math.max(maxV, seg.start.v, seg.end.v);
      }
    }
    
    if (minU === Infinity) {
      return { minU: -100, maxU: 100, minV: -100, maxV: 100 };
    }
    
    // Add 10% padding
    const padU = (maxU - minU) * 0.1 || 20;
    const padV = (maxV - minV) * 0.1 || 20;
    
    return {
      minU: minU - padU,
      maxU: maxU + padU,
      minV: minV - padV,
      maxV: maxV + padV
    };
  }

  dispose() {
    if (this.helperMesh) {
      this.scene.remove(this.helperMesh);
      this.helperMesh.geometry.dispose();
      this.helperMesh.material.dispose();
      this.helperMesh = null;
    }
  }
}

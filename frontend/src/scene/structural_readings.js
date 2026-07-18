import * as THREE from 'three';

export class StructuralReadingsRenderer {
  constructor(scene) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.name = 'structural-readings';
    this.scene.add(this.group);
  }

  render(readings) {
    this.clear();
    if (!readings || readings.length === 0) return;

    for (const r of readings) {
      try {
        const easting = parseFloat(r.easting);
        const northing = parseFloat(r.northing);
        const elevation = parseFloat(r.elevation);
        const dip = r.dip !== null ? parseFloat(r.dip) : 0.0;
        const strike = r.strike !== null ? parseFloat(r.strike) : 0.0;

        if (isNaN(easting) || isNaN(northing) || isNaN(elevation)) continue;

        // Choose color based on reading type
        let color = 0xeab308; // Yellow for dip_strike / bedding
        if (r.reading_type === 'fault_trace') {
          color = 0xef4444; // Red for fault trace
        }

        // Create a disc representing the measurement plane
        const radius = 8.0;
        const geometry = new THREE.CircleGeometry(radius, 32);

        // Premium translucent double-sided material
        const material = new THREE.MeshStandardMaterial({
          color: color,
          transparent: true,
          opacity: 0.75,
          side: THREE.DoubleSide,
          roughness: 0.4,
          metalness: 0.1
        });

        const mesh = new THREE.Mesh(geometry, material);

        // Position the disc at UTM (Three.js coordinates: X = Easting, Y = Elevation, Z = Northing)
        mesh.position.set(easting, elevation, northing);

        // Orient the disc normal [0, 0, 1] to match the dip/strike plane normal
        const strikeRad = (strike * Math.PI) / 180;
        const dipRad = (dip * Math.PI) / 180;

        const normal = new THREE.Vector3(
          -Math.sin(dipRad) * Math.sin(strikeRad),
          Math.cos(dipRad),
          -Math.sin(dipRad) * Math.cos(strikeRad)
        ).normalize();

        const defaultNormal = new THREE.Vector3(0, 0, 1);
        const quaternion = new THREE.Quaternion().setFromUnitVectors(defaultNormal, normal);
        mesh.setRotationFromQuaternion(quaternion);

        // Add user data for inspection
        mesh.userData = {
          id: r.id,
          type: 'structural_reading',
          reading_type: r.reading_type,
          easting: easting,
          northing: northing,
          elevation: elevation,
          dip: dip,
          strike: strike
        };

        // Draw a small directional tick/line representing the dip direction
        // Dip direction is S + 90 degrees.
        const tickLength = 12.0;
        const tickGeom = new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(0, 0, 0),
          new THREE.Vector3(0, tickLength, 0) // Point pointing outward along plane
        ]);
        const tickMat = new THREE.LineBasicMaterial({ color: 0xffffff, linewidth: 2 });
        const tickLine = new THREE.Line(tickGeom, tickMat);
        // Ticks are perpendicular to strike (along maximum dip direction)
        mesh.add(tickLine);

        this.group.add(mesh);
      } catch (err) {
        console.error('Error rendering structural reading:', err);
      }
    }
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

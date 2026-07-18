import * as THREE from 'three';

export class OrientationGizmo {
  constructor(camera, renderer, domContainer) {
    this.mainCamera = camera;
    this.renderer = renderer;
    this.domContainer = domContainer;
    
    this.scene = new THREE.Scene();
    
    this.camera = new THREE.PerspectiveCamera(50, 1, 1, 1000);
    this.camera.up.set(0, 1, 0); // Elevation is vertical Y
    
    this.size = 100; // Viewport size in pixels
    this.margin = 16;
    
    this.init();
  }

  init() {
    // 1. Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    this.scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
    dirLight.position.set(1, 2, 1).normalize();
    this.scene.add(dirLight);

    // 2. Build coordinate system axes
    this.createAxes();
  }

  createAxes() {
    const axisLength = 26;
    const cylinderRadius = 1.0;
    const coneRadius = 2.5;
    const coneHeight = 6.0;

    // Define axes: name, direction vector, primary hex color, label text
    const axesConfig = [
      { 
        dir: new THREE.Vector3(1, 0, 0), 
        color: 0xef4444, // Red
        label: 'E',
        labelColor: '#ef4444',
        isPositive: true
      },
      { 
        dir: new THREE.Vector3(0, 1, 0), 
        color: 0x10b981, // Green
        label: 'Up',
        labelColor: '#10b981',
        isPositive: true
      },
      { 
        dir: new THREE.Vector3(0, 0, 1), 
        color: 0x3b82f6, // Blue
        label: 'N',
        labelColor: '#3b82f6',
        isPositive: true
      },
      { 
        dir: new THREE.Vector3(-1, 0, 0), 
        color: 0xef4444,
        label: 'W',
        labelColor: '#fca5a5',
        isPositive: false
      },
      { 
        dir: new THREE.Vector3(0, -1, 0), 
        color: 0x10b981,
        label: 'Dn',
        labelColor: '#86efac',
        isPositive: false
      },
      { 
        dir: new THREE.Vector3(0, 0, -1), 
        color: 0x3b82f6,
        label: 'S',
        labelColor: '#93c5fd',
        isPositive: false
      }
    ];

    axesConfig.forEach(cfg => {
      // 1. Create Arrow Shaft (Cylinder)
      // Standard cylinder is Y-up, we align it to the configuration vector
      const shaftLength = cfg.isPositive ? axisLength : axisLength * 0.7;
      const geometry = new THREE.CylinderGeometry(cylinderRadius, cylinderRadius, shaftLength, 8);
      const material = new THREE.MeshStandardMaterial({
        color: cfg.color,
        roughness: 0.3,
        metalness: 0.2,
        transparent: !cfg.isPositive,
        opacity: cfg.isPositive ? 1.0 : 0.45
      });
      const shaft = new THREE.Mesh(geometry, material);

      // Position shaft center at half of shaftLength along direction
      const position = cfg.dir.clone().multiplyScalar(shaftLength / 2);
      shaft.position.copy(position);

      // Rotate shaft to align with direction
      const alignAxis = new THREE.Vector3(0, 1, 0); // cylinder default
      shaft.quaternion.setFromUnitVectors(alignAxis, cfg.dir);
      this.scene.add(shaft);

      // 2. Create Arrow Tip (Cone) for positive axes
      if (cfg.isPositive) {
        const coneGeometry = new THREE.ConeGeometry(coneRadius, coneHeight, 8);
        const coneMaterial = new THREE.MeshStandardMaterial({
          color: cfg.color,
          roughness: 0.3,
          metalness: 0.2
        });
        const cone = new THREE.Mesh(coneGeometry, coneMaterial);
        
        // Position cone at the tip
        cone.position.copy(cfg.dir).multiplyScalar(axisLength);
        cone.quaternion.setFromUnitVectors(alignAxis, cfg.dir);
        this.scene.add(cone);
      }

      // 3. Create Label Sprite
      const labelPos = cfg.dir.clone().multiplyScalar(cfg.isPositive ? axisLength + 9 : axisLength * 0.7 + 9);
      const labelSprite = this.createLabelSprite(cfg.label, cfg.labelColor);
      labelSprite.position.copy(labelPos);
      this.scene.add(labelSprite);
    });

    // Add a central anchor sphere
    const sphereGeo = new THREE.SphereGeometry(2.5, 16, 16);
    const sphereMat = new THREE.MeshStandardMaterial({
      color: 0x334155,
      roughness: 0.4,
      metalness: 0.1
    });
    const centerSphere = new THREE.Mesh(sphereGeo, sphereMat);
    this.scene.add(centerSphere);
  }

  createLabelSprite(text, color) {
    const canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');

    // Draw high-contrast text with background stroke
    ctx.font = 'bold 26px system-ui, -apple-system, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // Black stroke border for legibility against active model layers
    ctx.strokeStyle = '#090d16';
    ctx.lineWidth = 5;
    ctx.strokeText(text, 32, 32);

    ctx.fillStyle = color;
    ctx.fillText(text, 32, 32);

    const texture = new THREE.CanvasTexture(canvas);
    const material = new THREE.SpriteMaterial({ 
      map: texture, 
      depthTest: false,
      depthWrite: false
    });
    
    const sprite = new THREE.Sprite(material);
    // Control scale size in rendering camera viewport
    sprite.scale.set(15, 15, 1);
    return sprite;
  }

  update() {
    // Lock the orientation camera's rotation to mirror the main viewport camera
    const dist = 100;
    const direction = new THREE.Vector3(0, 0, -1).applyQuaternion(this.mainCamera.quaternion);
    this.camera.position.copy(direction).multiplyScalar(-dist);
    this.camera.lookAt(0, 0, 0);
  }

  render() {
    this.update();

    const width = this.domContainer.clientWidth;
    const height = this.domContainer.clientHeight;

    // Render inside a scissor box at the bottom-right corner
    this.renderer.setViewport(width - this.size - this.margin, this.margin, this.size, this.size);
    this.renderer.setScissor(width - this.size - this.margin, this.margin, this.size, this.size);
    
    this.renderer.clearDepth();
    this.renderer.render(this.scene, this.camera);
  }
}

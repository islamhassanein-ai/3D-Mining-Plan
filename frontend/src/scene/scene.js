import * as THREE from 'three';
import { DampedCameraControls } from './camera_controls.js';
import { DrillholeTraces } from './drillhole_traces.js';
import { AssayIntervals } from './assay_intervals.js';
import { LithologyIntervals } from './lithology_intervals.js';
import { SceneLoader } from './scene_loader.js';
import { SceneToolbar } from '../components/toolbar.js';
import { SceneSelection } from './selection.js';
import { InspectorPanel } from '../components/inspector_panel.js';
import { CutoffSlider } from '../components/cutoff_slider.js';
import { SectionViewPanel } from '../components/section_view_panel.js';
import { MeasurementTool } from './measurement.js';
import { TopographyRenderer } from './topography.js';
import { TrenchesRenderer } from './trenches.js';
import { WireframesRenderer } from './wireframes.js';
import { StructuralReadingsRenderer } from './structural_readings.js';
import { LodManager } from './lod_manager.js';
import { OrientationGizmo } from './orientation_gizmo.js';
import { CoordinateFlag } from './coordinate_flag.js';
import { BoreholeLabels } from './borehole_labels.js';
import { TrenchLabels } from './trench_labels.js';
import { ImportPanel } from '../components/import_panel.js';
import { ProjectSwitcher } from '../components/project_switcher.js';
import { SharePanel } from '../components/share_panel.js';
import { HistoryPanel } from '../components/history_panel.js';
import { ExportPanel } from '../components/export_panel.js';
import { StructuralPanel } from '../components/structural_panel.js';
import { QaqcPanel } from '../components/qaqc_panel.js';
import { LayerTogglePanel } from '../components/layer_toggles.js';
import { ApiClient } from '../services/api_client.js';

let scene = null;
let camera = null;
let renderer = null;
let controls = null;

let tracesRenderer = null;
let assaysRenderer = null;
let lithologiesRenderer = null;
let sceneLoader = null;

export function init3DViewport(container, options = {}) {
  // If container is string, fetch element
  const domContainer = typeof container === 'string' ? document.getElementById(container) : container;
  if (!domContainer) {
    console.error("3D Viewport container not found");
    return null;
  }

  // 1. Create Scene
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b0f19); // Dark blue-black theme

  // 2. Create Camera (Y-Up by default in Three.js)
  camera = new THREE.PerspectiveCamera(45, domContainer.clientWidth / domContainer.clientHeight, 1, 100000);
  camera.position.set(200, 200, 200);

  // 3. Create WebGL Renderer
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(domContainer.clientWidth, domContainer.clientHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = false; // No need for heavy real-time shadows for CAD traces
  renderer.setScissorTest(true); // Required for viewport rendering split
  domContainer.appendChild(renderer.domElement);

  // 4. Lights
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
  scene.add(ambientLight);

  const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
  dirLight1.position.set(1, 2, 1).normalize();
  scene.add(dirLight1);

  const dirLight2 = new THREE.DirectionalLight(0x3b82f6, 0.3); // Subtle blue fill light
  dirLight2.position.set(-1, -1, -1).normalize();
  scene.add(dirLight2);

  // 5. Grid and Axis helpers (Y-up grid on X-Z plane)
  const gridHelper = new THREE.GridHelper(5000, 100, 0x374151, 0x1f2937);
  gridHelper.position.y = 0; // standard ground
  scene.add(gridHelper);

  const axesHelper = new THREE.AxesHelper(100);
  scene.add(axesHelper);

  // 6. Setup Custom Damped Controls
  controls = new DampedCameraControls(camera, renderer.domElement, scene);
  controls.setTarget(new THREE.Vector3(0, 0, 0));

  // 7. Instantiate sub-renderers
  tracesRenderer = new DrillholeTraces(scene);
  assaysRenderer = new AssayIntervals(scene);
  lithologiesRenderer = new LithologyIntervals(scene);
  const topographyRenderer = new TopographyRenderer(scene);
  const trenchesRenderer = new TrenchesRenderer(scene);
  const wireframesRenderer = new WireframesRenderer(scene);
  const structuralReadingsRenderer = new StructuralReadingsRenderer(scene);
  const coordinateFlag = new CoordinateFlag(scene);
  const boreholeLabelsRenderer = new BoreholeLabels(scene);
  const trenchLabelsRenderer = new TrenchLabels(scene);

  // 8. LOD Manager for performance at scale
  const lodManager = new LodManager(camera, tracesRenderer, assaysRenderer, lithologiesRenderer);

  // 9. Instantiate Scene Loader
  sceneLoader = new SceneLoader(
    scene, controls,
    tracesRenderer, assaysRenderer, lithologiesRenderer,
    topographyRenderer, trenchesRenderer, wireframesRenderer,
    structuralReadingsRenderer, lodManager, boreholeLabelsRenderer, trenchLabelsRenderer
  );

  // 9. Resize Handling
  const resizeObserver = new ResizeObserver(() => {
    if (!domContainer.clientWidth || !domContainer.clientHeight) return;
    camera.aspect = domContainer.clientWidth / domContainer.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(domContainer.clientWidth, domContainer.clientHeight);
  });
  resizeObserver.observe(domContainer);

  // 10. Keybind Shortcuts for Presets
  const handleKeydown = (e) => {
    const key = e.key.toLowerCase();
    if (key === 'p') {
      controls.setPreset('plan');
    } else if (key === 'n') {
      controls.setPreset('section_ns');
    } else if (key === 'e') {
      controls.setPreset('section_ew');
    } else if (key === 'i') {
      controls.setPreset('isometric');
    }
  };
  window.addEventListener('keydown', handleKeydown);

  // 11. CAD orientation corner gizmo setup
  const orientationGizmo = new OrientationGizmo(camera, renderer, domContainer);

  // 12. Animation render loop
  let animationFrameId = null;
  function animate() {
    animationFrameId = requestAnimationFrame(animate);
    controls.update();
    lodManager.update();
    boreholeLabelsRenderer.update(camera);
    trenchLabelsRenderer.update(camera);

    // Main render pass
    renderer.setViewport(0, 0, domContainer.clientWidth, domContainer.clientHeight);
    renderer.setScissor(0, 0, domContainer.clientWidth, domContainer.clientHeight);
    renderer.render(scene, camera);
    
    // CAD corner axes rendering pass
    orientationGizmo.render();
  }
  animate();

  // Return API object to control scene state externally
  const viewport = {
    scene,
    camera,
    renderer,
    controls,
    tracesRenderer,
    assaysRenderer,
    lithologiesRenderer,
    topographyRenderer,
    trenchesRenderer,
    wireframesRenderer,
    structuralReadingsRenderer,
    coordinateFlag,
    boreholeLabelsRenderer,
    trenchLabelsRenderer,
    sceneLoader,
    lodManager,
    destroy() {
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
      resizeObserver.disconnect();
      window.removeEventListener('keydown', handleKeydown);
      if (this.selection) this.selection.dispose();
      controls.dispose();
      tracesRenderer.clear();
      assaysRenderer.clear();
      lithologiesRenderer.clear();
      topographyRenderer.clear();
      trenchesRenderer.clear();
      wireframesRenderer.clear();
      structuralReadingsRenderer.clear();
      coordinateFlag.dispose();
      boreholeLabelsRenderer.clear();
      trenchLabelsRenderer.clear();
      renderer.dispose();
      if (renderer.domElement && renderer.domElement.parentNode) {
        renderer.domElement.parentNode.removeChild(renderer.domElement);
      }
    }
  };

  if (options.onSelect) {
    viewport.selection = new SceneSelection(viewport, options.onSelect);
  }

  return viewport;
}

window.init3DViewport = init3DViewport;
window.SceneToolbar = SceneToolbar;
window.SceneSelection = SceneSelection;
window.InspectorPanel = InspectorPanel;
window.CutoffSlider = CutoffSlider;
window.SectionViewPanel = SectionViewPanel;
window.MeasurementTool = MeasurementTool;
window.TopographyRenderer = TopographyRenderer;
window.TrenchesRenderer = TrenchesRenderer;
window.WireframesRenderer = WireframesRenderer;
window.ImportPanel = ImportPanel;
window.ProjectSwitcher = ProjectSwitcher;
window.SharePanel = SharePanel;
window.HistoryPanel = HistoryPanel;
window.StructuralPanel = StructuralPanel;
window.QaqcPanel = QaqcPanel;
window.LayerTogglePanel = LayerTogglePanel;
window.ApiClient = ApiClient;
window.ExportPanel = ExportPanel;

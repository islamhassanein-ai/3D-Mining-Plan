import * as THREE from 'three';
import { DampedCameraControls } from './camera_controls.js';
import { DrillholeTraces } from './drillhole_traces.js';
import { AssayIntervals } from './assay_intervals.js';
import { LithologyIntervals } from './lithology_intervals.js';
import { SceneLoader } from './scene_loader.js';
import { SceneToolbar } from '../components/toolbar.js';
import { SceneSelection } from './selection.js';
import { SceneHover } from './hover.js';
import { InspectorPanel } from '../components/inspector_panel.js';
import { CutoffSlider } from '../components/cutoff_slider.js';
import { GradeHistogram } from '../components/grade_histogram.js';
import { toast } from '../components/toast.js';
import { SectionViewPanel } from '../components/section_view_panel.js';
import { MeasurementTool } from './measurement.js';
import { TopographyRenderer } from './topography.js';
import { TrenchesRenderer } from './trenches.js';
import { WireframesRenderer } from './wireframes.js';
import { StructuralReadingsRenderer } from './structural_readings.js';
import { LodManager } from './lod_manager.js';
import { OrientationGizmo } from './orientation_gizmo.js';
import { CoordinateFlag } from './coordinate_flag.js';
import { FocusHighlight } from './focus_highlight.js';
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
import { SceneLegend } from '../components/scene_legend.js';
import { SearchBar } from '../components/search_bar.js';
import { ApiClient } from '../services/api_client.js';
import { computeProjectSummary } from '../services/project_summary.js';
import { ApiDataSource, ShareTokenDataSource } from '../services/data_source.js';

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
  let gridHelper = new THREE.GridHelper(5000, 100, 0x374151, 0x1f2937);
  gridHelper.position.y = 0; // standard ground
  gridHelper.userData.excludeFromFit = true;
  scene.add(gridHelper);

  const axesHelper = new THREE.AxesHelper(100);
  // The grid and axes are a reference frame, not data -- they must never
  // influence the camera fit, or every project would be framed to the 5 km
  // grid instead of to the drilling.
  axesHelper.userData.excludeFromFit = true;
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
  const focusHighlight = new FocusHighlight(scene);
  // Lets the inspector's row selection point at a sample in 3D.
  assaysRenderer.focusHighlight = focusHighlight;
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
    // Never steal a keystroke that's going into a form field.
    const tag = (e.target && e.target.tagName) || '';
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(tag) || (e.target && e.target.isContentEditable)) return;
    const key = e.key.toLowerCase();
    if (key === 'r') {
      if (!controls.resetToHome()) sceneLoader.fitCameraToData();
    } else if (key === 'p') {
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
  let hover = null;
  let lastFrameTime = performance.now();
  function animate() {
    animationFrameId = requestAnimationFrame(animate);
    const now = performance.now();
    // Clamped: a backgrounded tab resumes with a huge gap, which would skip
    // the focus animation straight to its end.
    const delta = Math.min((now - lastFrameTime) / 1000, 0.05);
    lastFrameTime = now;

    controls.update();
    focusHighlight.update(delta, camera);
    lodManager.update();
    boreholeLabelsRenderer.update(camera);
    trenchLabelsRenderer.update(camera);
    if (hover) hover.update();

    // Main render pass
    renderer.setViewport(0, 0, domContainer.clientWidth, domContainer.clientHeight);
    renderer.setScissor(0, 0, domContainer.clientWidth, domContainer.clientHeight);
    renderer.render(scene, camera);
    
    // CAD corner axes rendering pass
    orientationGizmo.render();
  }
  animate();

  // Scene-side half of the light/dark switch. The DOM half is pure CSS
  // variables, but the WebGL viewport has no cascade -- background, fill
  // light and grid have to be set explicitly. Grade colours are deliberately
  // untouched: they encode data and must not shift with the theme.
  const SCENE_THEMES = {
    dark:     { bg: 0x0b0f19, ambient: 0.60, fill: 0x3b82f6, fillIntensity: 0.30, grid: [0x374151, 0x1f2937] },
    light:    { bg: 0xe6ecf4, ambient: 0.85, fill: 0x3b82f6, fillIntensity: 0.12, grid: [0x94a3b8, 0xcbd5e1] },
    // Neutral charcoal with a white fill light instead of a blue one: any
    // tint in the fill lands on every grade colour at once and shifts how it
    // reads, which defeats the point of a reference-grade view.
    graphite: { bg: 0x17171a, ambient: 0.66, fill: 0xffffff, fillIntensity: 0.14, grid: [0x3f4046, 0x2a2b2f] },
  };

  function setTheme(theme) {
    const cfg = SCENE_THEMES[theme] || SCENE_THEMES.dark;
    scene.background = new THREE.Color(cfg.bg);
    // On a pale background the cool fill light muddies the surface, and the
    // ambient has to come down or everything flattens out.
    ambientLight.intensity = cfg.ambient;
    dirLight2.color.setHex(cfg.fill);
    dirLight2.intensity = cfg.fillIntensity;

    const wasVisible = gridHelper.visible;
    scene.remove(gridHelper);
    gridHelper.geometry.dispose();
    gridHelper.material.dispose();
    gridHelper = new THREE.GridHelper(5000, 100, cfg.grid[0], cfg.grid[1]);
    gridHelper.position.y = 0;
    gridHelper.visible = wasVisible;
    gridHelper.userData.excludeFromFit = true;
    scene.add(gridHelper);
  }

  // Return API object to control scene state externally
  const viewport = {
    setTheme,
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
    focusHighlight,
    boreholeLabelsRenderer,
    trenchLabelsRenderer,
    sceneLoader,
    lodManager,
    destroy() {
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
      resizeObserver.disconnect();
      window.removeEventListener('keydown', handleKeydown);
      if (this.selection) this.selection.dispose();
      if (this.hover) this.hover.dispose();
      controls.dispose();
      tracesRenderer.clear();
      assaysRenderer.clear();
      lithologiesRenderer.clear();
      topographyRenderer.clear();
      trenchesRenderer.clear();
      wireframesRenderer.clear();
      structuralReadingsRenderer.clear();
      coordinateFlag.dispose();
      focusHighlight.dispose();
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

  // Hover feedback (gold glow sleeve + tooltip). Assigned to the closure
  // `hover` so the render loop eases its fade each frame.
  hover = new SceneHover(viewport);
  viewport.hover = hover;
  viewport.hoverRenderer = hover; // consistent naming for scene_loader

  return viewport;
}

window.init3DViewport = init3DViewport;
window.SceneToolbar = SceneToolbar;
window.SceneSelection = SceneSelection;
window.InspectorPanel = InspectorPanel;
window.CutoffSlider = CutoffSlider;
window.GradeHistogram = GradeHistogram;
window.toast = toast;
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
window.SceneLegend = SceneLegend;
window.SearchBar = SearchBar;
window.ApiClient = ApiClient;
window.ExportPanel = ExportPanel;
window.computeProjectSummary = computeProjectSummary;
window.ApiDataSource = ApiDataSource;
window.ShareTokenDataSource = ShareTokenDataSource;

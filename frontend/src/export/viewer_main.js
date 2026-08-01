// Standalone export viewer entry point.
// All imports are from direct module files — never window.* globals,
// never data_source.js (which would pull ApiClient into the bundle).

import * as THREE from 'three';
import { DampedCameraControls } from '../scene/camera_controls.js';
import { DrillholeTraces } from '../scene/drillhole_traces.js';
import { AssayIntervals } from '../scene/assay_intervals.js';
import { LithologyIntervals } from '../scene/lithology_intervals.js';
import { SceneLoader } from '../scene/scene_loader.js';
import { SceneToolbar } from '../components/toolbar.js';
import { SceneSelection } from '../scene/selection.js';
import { SceneHover } from '../scene/hover.js';
import { InspectorPanel } from '../components/inspector_panel.js';
import { CutoffSlider } from '../components/cutoff_slider.js';
import { GradeHistogram } from '../components/grade_histogram.js';
import { toast } from '../components/toast.js';
import { SectionViewPanel } from '../components/section_view_panel.js';
import { MeasurementTool } from '../scene/measurement.js';
import { TopographyRenderer } from '../scene/topography.js';
import { TrenchesRenderer } from '../scene/trenches.js';
import { WireframesRenderer } from '../scene/wireframes.js';
import { StructuralReadingsRenderer } from '../scene/structural_readings.js';
import { LodManager } from '../scene/lod_manager.js';
import { OrientationGizmo } from '../scene/orientation_gizmo.js';
import { CoordinateFlag } from '../scene/coordinate_flag.js';
import { BoreholeLabels } from '../scene/borehole_labels.js';
import { TrenchLabels } from '../scene/trench_labels.js';
import { LayerTogglePanel } from '../components/layer_toggles.js';
import { SceneLegend } from '../components/scene_legend.js';
import { computeProjectSummary } from '../services/project_summary.js';
import { StaticDataSource } from '../services/static_data_source.js';

// ── Keyboard shortcut overlay ─────────────────────────────────────────────
// shell.html uses inline onclick="hideShortcutHelp()" so these must live on window.
window.showShortcutHelp = function () {
  const el = document.getElementById('shortcut-help-overlay');
  if (el) el.style.display = 'block';
};
window.hideShortcutHelp = function () {
  const el = document.getElementById('shortcut-help-overlay');
  if (el) el.style.display = 'none';
};

// ── Entry point ───────────────────────────────────────────────────────────
async function initStaticViewer() {
  // 1. Parse embedded payload
  const payloadEl = document.getElementById('monark-scene-data');
  if (!payloadEl) { console.error('monark-scene-data element not found'); return; }
  const payload = JSON.parse(payloadEl.textContent);
  const dataSource = new StaticDataSource(payload);

  // 2. Show loading overlay
  const loadingOverlay = document.getElementById('global-loading');
  const loadingMsg     = document.getElementById('loading-msg');
  if (loadingOverlay) loadingOverlay.style.display = 'flex';
  if (loadingMsg)     loadingMsg.textContent = 'Loading 3D geological scene…';

  try {
    // 3. Bootstrap Three.js scene
    const domContainer = document.getElementById('viewport-3d');

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b0f19);

    const camera = new THREE.PerspectiveCamera(
      45, domContainer.clientWidth / domContainer.clientHeight, 1, 100000
    );
    camera.position.set(200, 200, 200);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(domContainer.clientWidth, domContainer.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = false;
    renderer.setScissorTest(true);
    domContainer.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight1.position.set(1, 2, 1).normalize();
    scene.add(dirLight1);
    const dirLight2 = new THREE.DirectionalLight(0x3b82f6, 0.3);
    dirLight2.position.set(-1, -1, -1).normalize();
    scene.add(dirLight2);
    // Reference geometry, tagged so the camera fit ignores it -- the grid
    // spans 5 km and would otherwise dominate the framing. (visibleBounds
    // also rejects these by type, belt and braces.)
    const gridHelper = new THREE.GridHelper(5000, 100, 0x374151, 0x1f2937);
    gridHelper.userData.excludeFromFit = true;
    scene.add(gridHelper);
    const axesHelper = new THREE.AxesHelper(100);
    axesHelper.userData.excludeFromFit = true;
    scene.add(axesHelper);

    const controls = new DampedCameraControls(camera, renderer.domElement, scene);
    controls.setTarget(new THREE.Vector3(0, 0, 0));

    // 4. Sub-renderers (property names match the viewport shape expected by UI components)
    const tracesRenderer             = new DrillholeTraces(scene);
    const assaysRenderer             = new AssayIntervals(scene);
    const lithologiesRenderer        = new LithologyIntervals(scene);
    const topographyRenderer         = new TopographyRenderer(scene);
    const trenchesRenderer           = new TrenchesRenderer(scene);
    const wireframesRenderer         = new WireframesRenderer(scene);
    const structuralReadingsRenderer = new StructuralReadingsRenderer(scene);
    const coordinateFlag             = new CoordinateFlag(scene);
    const boreholeLabelsRenderer     = new BoreholeLabels(scene);
    const trenchLabelsRenderer       = new TrenchLabels(scene);
    const lodManager = new LodManager(camera, tracesRenderer, assaysRenderer, lithologiesRenderer);

    // 5. SceneLoader
    const sceneLoader = new SceneLoader(
      scene, controls,
      tracesRenderer, assaysRenderer, lithologiesRenderer,
      topographyRenderer, trenchesRenderer, wireframesRenderer,
      structuralReadingsRenderer, lodManager, boreholeLabelsRenderer, trenchLabelsRenderer
    );

    // 6. Viewport object — property names must match what UI components expect
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
    };

    // A standalone export is a single file that gets emailed around and opened
    // who-knows-where. Exposing the viewport gives whoever receives a "it's
    // blank on my machine" report something to inspect from the console --
    // there is no dev server or source map to fall back on.
    window.__miningViewport = viewport;

    // 7. Resize observer
    new ResizeObserver(() => {
      if (!domContainer.clientWidth || !domContainer.clientHeight) return;
      camera.aspect = domContainer.clientWidth / domContainer.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(domContainer.clientWidth, domContainer.clientHeight);
    }).observe(domContainer);

    // 8. Camera keyboard shortcuts + shortcut overlay toggle
    window.addEventListener('keydown', (e) => {
      const key = e.key.toLowerCase();
      if      (key === 'p')      controls.setPreset('plan');
      else if (key === 'n')      controls.setPreset('section_ns');
      else if (key === 'e')      controls.setPreset('section_ew');
      else if (key === 'i')      controls.setPreset('isometric');
      else if (key === '?')      window.showShortcutHelp();
      else if (key === 'escape') window.hideShortcutHelp();
    });

    // 9. Corner gizmo + animation loop
    const orientationGizmo = new OrientationGizmo(camera, renderer, domContainer);
    let hover = null;

    (function animate() {
      requestAnimationFrame(animate);
      controls.update();
      lodManager.update();
      boreholeLabelsRenderer.update(camera);
      trenchLabelsRenderer.update(camera);
      if (hover) hover.update();
      renderer.setViewport(0, 0, domContainer.clientWidth, domContainer.clientHeight);
      renderer.setScissor(0, 0, domContainer.clientWidth, domContainer.clientHeight);
      renderer.render(scene, camera);
      orientationGizmo.render();
    })();

    // 10. Inspector (uses StaticDataSource — no API calls leave the browser)
    let inspector = null;
    const inspectorEl = document.getElementById('inspector-container');
    if (inspectorEl) {
      inspector = new InspectorPanel('inspector-container', {
        dataSource,
        onIntervalSelected: (intervalId) => assaysRenderer.highlightInterval(intervalId),
      });
    }

    // 11. SceneSelection — wires click → inspector
    viewport.selection = new SceneSelection(viewport, (type, selData) => {
      if (!inspector) return;
      if (type === 'interval') inspector.loadCollar(selData.collarId, selData.intervalId);
      else if (type === 'trace') inspector.loadCollar(selData.collarId);
    });

    // 12. SceneHover — adds overlay group to scene immediately
    hover = new SceneHover(viewport);
    viewport.hover = hover;
    viewport.hoverRenderer = hover;

    // 13. Toolbar
    let toolbar = null;
    const toolbarContainer = document.getElementById('toolbar-3d-container');
    if (toolbarContainer) {
      toolbarContainer.innerHTML = '';
      toolbar = new SceneToolbar(toolbarContainer, viewport);
    }

    // 14. Load scene from static payload
    const data = await sceneLoader.load(dataSource);

    // 15. Hide loading overlay, reveal sidebar controls
    if (loadingOverlay) loadingOverlay.style.display = 'none';
    const visualizerControls = document.getElementById('visualizer-controls');
    if (visualizerControls) visualizerControls.style.display = '';
    const headerStats = document.getElementById('header-stats');
    if (headerStats) headerStats.style.display = '';

    // 16. Camera preset buttons + reset
    document.querySelectorAll('.vbtn[data-preset]').forEach(btn => {
      btn.onclick = () => controls.setPreset(btn.dataset.preset);
    });
    document.getElementById('reset-camera-btn')?.addEventListener('click', () => {
      if (toolbar) toolbar.resetCamera();
      else if (!controls.resetToHome()) sceneLoader.fitCameraToData();
    });

    // 17. Go-to-coordinate
    document.getElementById('goto-btn')?.addEventListener('click', () => {
      const e  = parseFloat(document.getElementById('goto-easting').value);
      const n  = parseFloat(document.getElementById('goto-northing').value);
      const el = parseFloat(document.getElementById('goto-elevation').value) || 0;
      if (!isNaN(e) && !isNaN(n)) controls.setTarget(new THREE.Vector3(e, el, n));
    });

    // 18. Topography mode toggle
    document.getElementById('topo-mode-mesh')?.addEventListener('click', function () {
      if (topographyRenderer.setMode) topographyRenderer.setMode('mesh');
      document.querySelectorAll('#visualizer-controls .view-btns .vbtn')
        .forEach(b => b.classList.remove('active'));
      this.classList.add('active');
    });
    document.getElementById('topo-mode-points')?.addEventListener('click', function () {
      if (topographyRenderer.setMode) topographyRenderer.setMode('points');
      document.querySelectorAll('#visualizer-controls .view-btns .vbtn')
        .forEach(b => b.classList.remove('active'));
      this.classList.add('active');
    });

    // 19. Layer toggles
    // Layer toggles in the sidebar and the floating scene legend are two
    // views of one visibility state, so each pushes its changes into the
    // other -- same arrangement as the live app.
    const LEGEND_TO_LAYERS = {
      trenches:   ['trenches'],
      drillholes: ['traces', 'assays', 'lithology'],
      planned:    ['planned'],
      topography: ['topography'],
    };
    const layerContainer = document.getElementById('layer-toggles-container');
    const legendContainer = document.getElementById('scene-legend-container');
    if (layerContainer) {
      layerContainer.innerHTML = '';
      let legend = null;
      const layers = new LayerTogglePanel(layerContainer, viewport, {
        onChange: (key) => {
          if (!legend) return;
          for (const [legendKey, layerKeys] of Object.entries(LEGEND_TO_LAYERS)) {
            if (!layerKeys.includes(key)) continue;
            legend.setVisible(legendKey, layerKeys.some(k => layers.state[k]), { silent: true });
          }
        }
      });
      if (legendContainer) {
        legendContainer.innerHTML = '';
        legend = new SceneLegend(legendContainer, viewport, {
          onToggle: (key, visible) => {
            for (const layerKey of (LEGEND_TO_LAYERS[key] || [])) {
              layers.setVisible(layerKey, visible);
            }
          }
        });
        legend.setSurfaceDerived(!!sceneLoader.surfaceDerived);
        Object.entries(LEGEND_TO_LAYERS).forEach(([legendKey, layerKeys]) => {
          legend.setVisible(legendKey, layerKeys.some(k => layers.state[k]), { silent: true });
        });
      }
    }

    // 20. Cutoff slider + grade histogram
    const histoContainer = document.getElementById('grade-histogram-container');
    const gradeHistogram = histoContainer ? new GradeHistogram(histoContainer) : null;
    if (gradeHistogram) gradeHistogram.setData(data.drillholes);
    const sliderContainer = document.getElementById('cutoff-slider-container');
    if (sliderContainer) {
      new CutoffSlider(sliderContainer, (val) => {
        assaysRenderer.setGradeCutoff(val);
        if (gradeHistogram) gradeHistogram.setCutoff(val);
      });
    }

    // 21. 2D section panel
    const sectionContainer = document.getElementById('section-view-container');
    if (sectionContainer) {
      const sectionPanel = new SectionViewPanel(sectionContainer, viewport);
      sectionPanel.setDrillholes(data.drillholes);
    }

    // 22. Ruler measurement tool
    const rulerBtn     = document.getElementById('toggle-ruler-btn');
    const rulerResults = document.getElementById('ruler-results');
    if (rulerBtn) {
      const rulerTool = new MeasurementTool(viewport, (res) => {
        if (!rulerResults) return;
        if (!res) { rulerResults.style.display = 'none'; return; }
        rulerResults.style.display = 'block';
        document.getElementById('ruler-distance-val').textContent = `${res.distance.toFixed(2)}m`;
        document.getElementById('ruler-dx-val').textContent       = `${res.dx.toFixed(1)}m`;
        document.getElementById('ruler-dy-val').textContent       = `${res.dy.toFixed(1)}m`;
        document.getElementById('ruler-dz-val').textContent       = `${res.dz.toFixed(1)}m`;
        if (res.completed) {
          rulerBtn.classList.remove('active');
          rulerBtn.textContent = 'Activate';
        }
      });
      rulerTool.setCollars(data.drillholes);
      hover.setData(data.drillholes);
      rulerBtn.onclick = () => {
        const isActive = rulerBtn.classList.toggle('active');
        rulerBtn.textContent = isActive ? 'Ruler Active' : 'Activate';
        rulerTool.setActive(isActive);
      };
    }

    // 23. Hint card + shortcut help button
    document.getElementById('hint-close-btn')?.addEventListener('click', () => {
      const card = document.getElementById('viewport-hint-card');
      if (card) card.style.display = 'none';
    });
    document.getElementById('shortcut-help-btn')?.addEventListener('click', window.showShortcutHelp);

    // 24. Header stats
    const summary = computeProjectSummary(data);
    const setText = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    setText('header-project-name', payload.project.name || '');
    setText('dd-sum-holes',   summary.drillholes.holes);
    setText('dd-sum-meters',  summary.drillholes.meters.toFixed(0));
    setText('dd-sum-avg',     summary.drillholes.avgGrade.toFixed(2));
    setText('dd-sum-peak',    summary.drillholes.peakGrade.toFixed(2));
    setText('tr-sum-count',   summary.trenches.count);
    setText('tr-sum-samples', summary.trenches.samples);
    setText('tr-sum-avg',     summary.trenches.avgGrade.toFixed(2));
    setText('tr-sum-peak',    summary.trenches.peakGrade.toFixed(2));

    // 25. Export footer — textContent only, never innerHTML (FR-015)
    const meta = payload.export_meta || {};
    setText('export-project-name', payload.project.name || '');
    setText('export-utm-zone', payload.project.utm_zone ? `UTM ${payload.project.utm_zone}` : '');
    if (meta.exported_at) {
      const d = new Date(meta.exported_at);
      setText('export-timestamp',
        `Exported ${d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })} ` +
        `${d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}`
      );
    }
    setText('export-by', meta.exported_by ? `by ${meta.exported_by}` : '');
    setText('export-holes-count',  `${summary.drillholes.holes} holes`);
    setText('export-meters-count', `${summary.drillholes.meters.toFixed(0)} m drilled`);

    const noticesEl = document.getElementById('export-notices');
    if (noticesEl && Array.isArray(meta.notices)) {
      for (const notice of meta.notices) {
        const div = document.createElement('div');
        div.className = 'export-notice-info';
        div.textContent = notice;
        noticesEl.appendChild(div);
      }
    }

    // 25b. Panel collapse tabs
    const appBody = document.getElementById('app-body');
    const leftTab  = document.getElementById('left-edge-tab');
    const rightTab = document.getElementById('right-edge-tab');
    if (leftTab && appBody) {
      leftTab.onclick = () => appBody.classList.toggle('hide-left');
    }
    if (rightTab && appBody) {
      rightTab.onclick = () => appBody.classList.toggle('hide-right');
    }

    // 26. Draggable modal support
    function makeDraggable(card) {
      if (card.dataset.draggable) return;
      const header = card.querySelector('.modal-header');
      if (!header) return;
      card.dataset.draggable = '1';
      let dragging = false, ox = 0, oy = 0;
      header.addEventListener('mousedown', (e) => {
        if (e.target.closest('.modal-close')) return;
        const rect = card.getBoundingClientRect();
        card.style.position = 'fixed';
        card.style.margin   = '0';
        card.style.right    = '';
        card.style.bottom   = '';
        card.style.left     = rect.left + 'px';
        card.style.top      = rect.top  + 'px';
        ox = e.clientX - rect.left;
        oy = e.clientY - rect.top;
        dragging = true;
        e.preventDefault();
      });
      window.addEventListener('mousemove', (e) => {
        if (!dragging) return;
        card.style.left = Math.max(0, Math.min(window.innerWidth  - card.offsetWidth,  e.clientX - ox)) + 'px';
        card.style.top  = Math.max(0, Math.min(window.innerHeight - card.offsetHeight, e.clientY - oy)) + 'px';
      });
      window.addEventListener('mouseup', () => { dragging = false; });
    }
    // Wire up cards already in DOM (e.g. shortcut help overlay)
    document.querySelectorAll('.modal-card').forEach(makeDraggable);
    // Wire up cards injected dynamically into #modal-container
    const modalContainer = document.getElementById('modal-container');
    if (modalContainer) {
      new MutationObserver(() => {
        modalContainer.querySelectorAll('.modal-card').forEach(makeDraggable);
      }).observe(modalContainer, { childList: true, subtree: true });
    }

  } catch (err) {
    console.error('Static viewer initialization failed:', err);
    if (loadingOverlay) loadingOverlay.style.display = 'none';
    toast('Failed to initialize viewer. See browser console for details.', 'error');
  }
}

initStaticViewer();

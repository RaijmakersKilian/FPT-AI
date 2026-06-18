import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js';

const _az = window.AZURE_CONFIG || {};
const _base = `https://${_az.account || 'fptstorageai'}.blob.core.windows.net/${_az.modelsContainer || '3dmodels'}`;
const _sas  = _az.modelsSasToken ? `?${_az.modelsSasToken}` : '';

const DEFAULT_MODEL = `${_base}/glb/KCPT_Ki_centered.glb${_sas}`;
const COVERAGE_PLY  = `${_base}/coverage/coverage_colored.ply${_sas}`;

const container = document.getElementById('bim-viewport');
const canvas    = document.getElementById('bim-canvas');

if (container && canvas) initViewer();

async function initViewer() {
  const w = container.clientWidth  || 600;
  const h = container.clientHeight || 400;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0c1124);

  const camera = new THREE.PerspectiveCamera(60, w / h, 0.01, 10000);
  camera.position.set(0, 50, 200);

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  // Expose snapshot for PDF export
  window.getBimSnapshot = () => canvas.toDataURL('image/png');

  scene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const sun = new THREE.DirectionalLight(0xffffff, 1.4);
  sun.position.set(200, 400, 300);
  scene.add(sun);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.minDistance   = 1;
  controls.maxDistance   = 10000;

  const gltfLoader = new GLTFLoader();
  const plyLoader  = new PLYLoader();

  let coveragePoints  = null;
  let currentModel    = null;
  let showModel       = false;   // GLB hidden by default; coverage PLY is primary view
  // ── Coverage PLY ─────────────────────────────────────────────────────────────

  async function loadCoveragePLY(url) {
    if (coveragePoints) {
      scene.remove(coveragePoints);
      coveragePoints.geometry.dispose();
      coveragePoints = null;
    }
    hidePlaceholder();
    setLoading(true);
    try {
      const geometry = await new Promise((resolve, reject) => {
        plyLoader.load(url, resolve, undefined, reject);
      });
      const hasColor = geometry.hasAttribute('color');
      const material = new THREE.PointsMaterial({
        size:            1.0,
        vertexColors:    hasColor,
        color:           hasColor ? undefined : 0x00cc44,
        sizeAttenuation: true,
      });
      coveragePoints = new THREE.Points(geometry, material);
      coveragePoints.rotation.x = -Math.PI / 2;
      scene.add(coveragePoints);
      fitCamera(coveragePoints, camera, controls);
    } catch (err) {
      console.error('Coverage PLY laden mislukt:', err);
      showPlaceholder();
    } finally {
      setLoading(false);
    }
  }

  // Expose for thumbnails.js
  window.loadCoverage = (dateKey) => loadCoveragePLY(`${_base}/coverage/coverage_${dateKey}.ply${_sas}`);

  hidePlaceholder();
  setLoading(true);

  try {
    const geometry = await new Promise((resolve, reject) => {
      plyLoader.load(COVERAGE_PLY, resolve, undefined, reject);
    });

    // PLYLoader sets a 'color' attribute from red/green/blue in the PLY
    const hasColor = geometry.hasAttribute('color');
    const material = new THREE.PointsMaterial({
      size:           1.0,
      vertexColors:   hasColor,
      color:          hasColor ? undefined : 0x00cc44,
      sizeAttenuation: true,
    });

    coveragePoints = new THREE.Points(geometry, material);
    // Open3D writes Z-up; rotate to Y-up to match Three.js convention
    coveragePoints.rotation.x = -Math.PI / 2;
    scene.add(coveragePoints);
    fitCamera(coveragePoints, camera, controls);
  } catch (err) {
    console.error('coverage_result.ply laden mislukt:', err);
    // Fallback: load the GLB model instead
    showModel = true;
    loadGLB(DEFAULT_MODEL);
  }

  setLoading(false);

  // ── GLB model (toggled via button, hidden by default) ────────────────────────

  async function loadGLB(url, revokeAfter = false) {
    setLoading(true);
    try {
      const gltf = await gltfLoader.loadAsync(url);
      if (currentModel) scene.remove(currentModel);
      currentModel = gltf.scene;
      currentModel.rotation.x = -Math.PI / 2;
      currentModel.visible = showModel;
      scene.add(currentModel);
      if (showModel) fitCamera(currentModel, camera, controls);
    } catch (err) {
      console.error('Model laden mislukt:', err);
      showPlaceholder();
    } finally {
      if (revokeAfter) URL.revokeObjectURL(url);
      setLoading(false);
    }
  }

  // Load GLB silently in background (for toggle use)
  loadGLB(DEFAULT_MODEL);

  // ── File input (load custom GLB/GLTF) ────────────────────────────────────────

  const fileInput = document.getElementById('ifc-file-input');
  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;
      showModel = true;
      loadGLB(URL.createObjectURL(file), true);
      fileInput.value = '';
    });
  }

  // ── Render loop ──────────────────────────────────────────────────────────────

  (function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  })();

  new ResizeObserver(() => {
    const nw = container.clientWidth;
    const nh = container.clientHeight;
    if (!nw || !nh) return;
    camera.aspect = nw / nh;
    camera.updateProjectionMatrix();
    renderer.setSize(nw, nh);
  }).observe(container);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fitCamera(object, camera, controls) {
  const box    = new THREE.Box3().setFromObject(object);
  const center = box.getCenter(new THREE.Vector3());
  const size   = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z);
  camera.position.set(
    center.x,
    center.y + maxDim * 0.5,
    center.z + maxDim * 1.2
  );
  controls.target.copy(center);
  controls.update();
}

function setLoading(on) {
  const el = document.getElementById('bim-loading');
  if (el) el.style.display = on ? 'flex' : 'none';
}
function hidePlaceholder() {
  const el = document.getElementById('bim-placeholder');
  if (el) el.style.display = 'none';
}
function showPlaceholder() {
  const el = document.getElementById('bim-placeholder');
  if (el) el.style.display = 'flex';
}

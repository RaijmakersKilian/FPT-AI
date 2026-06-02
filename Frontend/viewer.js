import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const DEFAULT_MODEL = 'KCPT_Ki_centered.glb';

const container = document.getElementById('bim-viewport');
const canvas = document.getElementById('bim-canvas');

if (container && canvas) {
  initViewer();
}

async function initViewer() {
  const w = container.clientWidth || 600;
  const h = container.clientHeight || 400;

  // Scene
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0c1124);

  // Camera
  const camera = new THREE.PerspectiveCamera(60, w / h, 0.01, 2000);
  camera.position.set(20, 15, 20);

  // Renderer
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;

  // Lighting
  scene.add(new THREE.AmbientLight(0xffffff, 0.7));
  const sun = new THREE.DirectionalLight(0xffffff, 1.2);
  sun.position.set(60, 100, 60);
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0x8ab4f8, 0.4);
  fill.position.set(-40, 20, -30);
  scene.add(fill);


  // Controls
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.minDistance = 0.5;
  controls.maxDistance = 1000;

  const gltfLoader = new GLTFLoader();
  let currentModel = null;

  async function loadModel(url, revokeAfter = false) {
    setLoading(true);
    hidePlaceholder();
    try {
      const gltf = await gltfLoader.loadAsync(url);
      if (currentModel) scene.remove(currentModel);
      currentModel = gltf.scene;
      // Corrigeer Z-up exportoriëntatie naar Y-up (Three.js standaard)
      currentModel.rotation.x = -Math.PI / 2;
      scene.add(currentModel);
      fitCamera(currentModel, camera, controls);
    } catch (err) {
      console.error('Fout bij laden model:', err);
      showPlaceholder();
    } finally {
      if (revokeAfter) URL.revokeObjectURL(url);
      setLoading(false);
    }
  }

  // Laad standaard model
  loadModel(DEFAULT_MODEL);

  // File input — .glb / .gltf
  const fileInput = document.getElementById('ifc-file-input');
  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;
      loadModel(URL.createObjectURL(file), true);
      fileInput.value = '';
    });
  }

  // Render loop
  (function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  })();

  // Resize
  new ResizeObserver(() => {
    const nw = container.clientWidth;
    const nh = container.clientHeight;
    if (!nw || !nh) return;
    camera.aspect = nw / nh;
    camera.updateProjectionMatrix();
    renderer.setSize(nw, nh);
  }).observe(container);
}

function fitCamera(model, camera, controls) {
  const box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z);
  camera.position.set(
    center.x + maxDim * 1.5,
    center.y + maxDim,
    center.z + maxDim * 1.5
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

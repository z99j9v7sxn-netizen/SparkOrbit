import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js';
import { FilmGrainPass } from './postprocessing/film-grain-pass';

export interface RenderPipeline {
  renderer: THREE.WebGLRenderer;
  composer: EffectComposer;
  bloom: UnrealBloomPass;
  filmGrain: FilmGrainPass;
  /** DOM 标签层（CSS2D）；仅在 enableLabels 时创建 */
  labelRenderer: CSS2DRenderer | null;
}

export interface RenderPipelineOptions {
  lowPower?: boolean;
  enableFilmGrain?: boolean;
  /** bloom 亮度阈值；调低可让背景星云/银河微光参与泛光 */
  bloomThreshold?: number;
  /** 启用 CSS2D DOM 标签层（中文文本清晰、可承载富信息芯片） */
  enableLabels?: boolean;
}

export function createRenderPipeline(
  container: HTMLElement,
  scene: THREE.Scene,
  camera: THREE.PerspectiveCamera,
  options: RenderPipelineOptions = {},
): RenderPipeline {
  const { lowPower = false, enableFilmGrain = true, bloomThreshold = 0.45, enableLabels = false } = options;
  const w = container.clientWidth;
  const h = container.clientHeight;
  const dpr = Math.min(window.devicePixelRatio, lowPower ? 1.5 : 2);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(dpr);
  renderer.setSize(w, h);
  renderer.setClearColor(0x050818, 1);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.95;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  container.appendChild(renderer.domElement);

  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));

  const bloomStrength = lowPower ? 0.4 : 0.85;
  const bloom = new UnrealBloomPass(new THREE.Vector2(w, h), bloomStrength, 0.65, bloomThreshold);
  composer.addPass(bloom);

  const filmGrain = new FilmGrainPass(lowPower ? 0 : 0.05);
  filmGrain.enabled = enableFilmGrain && !lowPower;
  composer.addPass(filmGrain);

  let labelRenderer: CSS2DRenderer | null = null;
  if (enableLabels) {
    labelRenderer = new CSS2DRenderer();
    labelRenderer.setSize(w, h);
    const el = labelRenderer.domElement;
    el.style.position = 'absolute';
    el.style.top = '0';
    el.style.left = '0';
    el.style.pointerEvents = 'none';
    container.appendChild(el);
  }

  return { renderer, composer, bloom, filmGrain, labelRenderer };
}

export function resizeRenderPipeline(
  pipeline: RenderPipeline,
  camera: THREE.PerspectiveCamera,
  w: number,
  h: number,
): void {
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  pipeline.renderer.setSize(w, h);
  pipeline.composer.setSize(w, h);
  pipeline.labelRenderer?.setSize(w, h);
}

export function disposeRenderPipeline(pipeline: RenderPipeline | null): void {
  if (!pipeline) return;
  pipeline.filmGrain.dispose();
  pipeline.composer.dispose();
  pipeline.renderer.dispose();
  pipeline.labelRenderer?.domElement.remove();
}

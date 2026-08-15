<script setup lang="ts">
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js';
import gsap from 'gsap';
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';
import {
  fetchGalaxies,
  fetchGalaxyDetail,
  fetchConstellations,
  type Constellation,
  type Galaxy,
  type GalaxyDetail,
  type Planet,
  type PlanetStatus,
} from '../api/orbit';
import { useOrbitStore } from '../stores/orbit';
import { createRenderPipeline, disposeRenderPipeline, resizeRenderPipeline, type RenderPipeline } from '../three/create-renderer';
import { createPlanetMesh, setPlanetSunLight, tickPlanetVisuals, updatePlanetBodyVisuals } from '../three/create-planet-mesh';
import { buildDependencyLines, type DependencyLines } from '../three/dependency-lines';
import { disposeObject3D } from '../three/dispose';
import { playSupernovaOnMesh, spawnBurst, spawnMeteorImpact, spawnShockwave, updateBurstFx, type BurstFx } from '../three/effects/supernova';
import { buildParticleOrbitRing, buildStarCore, type StarCore } from '../three/galaxy-node';
import { buildNebulaBackground, disposeNebulaBackground, type NebulaBackground } from '../three/nebula-background';
import { buildNebulaCore, disposeNebulaCore, type NebulaCore } from '../three/nebula-core';
import { buildParticleField, disposeParticleField, type ParticleField } from '../three/particle-field';
import { PlanetInteractionController } from '../three/planet-interaction';
import { buildDistantGalaxies, type DistantGalaxies } from '../three/distant-galaxies';
import { buildShootingStars, type ShootingStars } from '../three/shooting-stars';
import { buildSkyDome, type SkyDome } from '../three/sky-dome';
import { createSpiralGalaxy, type SpiralGalaxyNode } from '../three/spiral-galaxy';
import { fitCameraDistance, galaxyPointBudget, layoutGalaxies } from '../three/universe-layout';

const props = withDefaults(
  defineProps<{ active?: boolean; interactive?: boolean; slim?: boolean }>(),
  { active: true, interactive: true, slim: false },
);

const emit = defineEmits<{
  (e: 'select-planet', planet: Planet, galaxy: GalaxyDetail): void;
  (e: 'supernova', pos: { x: number; y: number }): void;
  (e: 'enter-galaxy', slug: string, name: string): void;
}>();

const orbitStore = useOrbitStore();
const isActive = computed(() => props.active);
const isInteractive = computed(() => props.interactive !== false);

function applyCanvasInteractivity(on: boolean) {
  if (!pipeline?.renderer?.domElement) return;
  pipeline.renderer.domElement.style.pointerEvents = on ? 'auto' : 'none';
  if (controls) controls.enabled = on;
}

watch(isInteractive, (on) => applyCanvasInteractivity(on));

const container = ref<HTMLDivElement | null>(null);
const loading = ref(true);
const view = ref<'universe' | 'galaxy'>('universe');
const currentGalaxy = shallowRef<GalaxyDetail | null>(null);
const galaxyList = ref<Galaxy[]>([]);
const tooltip = ref({ visible: false, text: '', sub: '', x: 0, y: 0, missing: [] as string[], score: -1 });
const hintText = ref('拖拽旋转 · 滚轮缩放 · 点击星系进入');
const searchQuery = ref('');
const searchOpen = ref(false);

const reduceMotion = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const IDLE_SPIN_DELAY = 10000;

let pipeline: RenderPipeline | null = null;
let scene: THREE.Scene;
let camera: THREE.PerspectiveCamera;
let controls: OrbitControls;
let raycaster: THREE.Raycaster;
const pointer = new THREE.Vector2();
let frameId = 0;
let frameCount = 0;
let contentGroup: THREE.Group;
let interactionRoot: THREE.Group;
let nebulaBg: NebulaBackground | null = null;
let nebulaCore: NebulaCore | null = null;
let particleField: ParticleField | null = null;
let skyDome: SkyDome | null = null;
let shootingStars: ShootingStars | null = null;
let distantGalaxies: DistantGalaxies | null = null;
let starCore: StarCore | null = null;
let interactionController: PlanetInteractionController | null = null;
const pickables: THREE.Object3D[] = [];
const planetMeshes: Record<string, THREE.Mesh> = {};
const planetLocalPos = new Map<string, THREE.Vector3>();
const spiralNodes: SpiralGalaxyNode[] = [];
let depLines: DependencyLines | null = null;
let reticle: THREE.Group | null = null;
const burstFxList: BurstFx[] = [];
let hovered: THREE.Object3D | null = null;
let galaxyCache: Galaxy[] = [];
let constellations: Constellation[] = [];
let cameraTweening = false;
let pointerDirty = true;
let activeTweens: gsap.core.Animation[] = [];
let lowPowerMode = false;
let pointerOffset = { x: 0, y: 0 };
let lastInteraction = typeof performance !== 'undefined' ? performance.now() : 0;

function markInteraction(): void {
  lastInteraction = performance.now();
}

// ---------------- CSS2D 标签 ----------------

interface LabelMeta {
  obj: CSS2DObject;
  el: HTMLElement;
  kind: 'galaxy' | 'planet' | 'star' | 'title';
  slug?: string;
  lod: string;
}

const labelMeta: LabelMeta[] = [];
const lodTmp = new THREE.Vector3();
// 星系标签 LOD 阈值随宇宙布局半径缩放（10+ 星系时布局更大，阈值同步放宽）
let galaxyLodMid = 44;
let galaxyLodFar = 68;

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] ?? c
  ));
}

function registerLabel(el: HTMLElement, kind: LabelMeta['kind'], slug?: string): CSS2DObject {
  const obj = new CSS2DObject(el);
  labelMeta.push({ obj, el, kind, slug, lod: '' });
  return obj;
}

function difficultyText(d: Planet['difficulty']): string {
  return d === 'hard' ? '挑战' : d === 'medium' ? '进阶' : '基础';
}

function makePlanetLabel(planet: Planet): CSS2DObject {
  const el = document.createElement('div');
  const statusCls = planet.is_permanent ? 'lit' : planet.status;
  el.className = `orbit-label planet st-${statusCls}`;
  const score = Math.max(0, Math.min(100, Math.round(planet.score ?? 0)));
  el.innerHTML = `
    <span class="dot"></span>
    <span class="name">${escapeHtml(planet.name)}</span>
    <span class="badge">${difficultyText(planet.difficulty)}</span>
    <span class="bar"><i style="width:${score}%"></i></span>
  `;
  return registerLabel(el, 'planet', planet.slug);
}

function makeGalaxyLabel(galaxy: Galaxy): CSS2DObject {
  const el = document.createElement('div');
  el.className = 'orbit-label galaxy';
  const pct = galaxy.planet_count > 0 ? Math.round((galaxy.lit_count / galaxy.planet_count) * 100) : 0;
  el.innerHTML = `
    <span class="name">${escapeHtml(galaxy.name)}</span>
    <span class="sub">${galaxy.lit_count}/${galaxy.planet_count} 已点亮</span>
    <span class="bar"><i style="width:${pct}%"></i></span>
  `;
  return registerLabel(el, 'galaxy', galaxy.slug);
}

function makeTextLabel(text: string, kind: 'star' | 'title'): CSS2DObject {
  const el = document.createElement('div');
  el.className = `orbit-label ${kind}`;
  el.innerHTML = `<span class="name">${escapeHtml(text)}</span>`;
  return registerLabel(el, kind);
}

function clearLabels(): void {
  for (const meta of labelMeta) {
    meta.obj.removeFromParent();
    meta.el.remove();
  }
  labelMeta.length = 0;
}

function setLabelState(slug: string | null, cls: 'is-active' | 'is-dimmed', on: boolean): void {
  for (const meta of labelMeta) {
    if (meta.kind !== 'planet') continue;
    if (slug === null || meta.slug === slug) meta.el.classList.toggle(cls, on);
  }
}

function updateLabelLod(): void {
  if (!camera) return;
  for (const meta of labelMeta) {
    if (meta.kind === 'title' || meta.kind === 'star') continue;
    meta.obj.getWorldPosition(lodTmp);
    const d = camera.position.distanceTo(lodTmp);
    let cls: string;
    if (meta.kind === 'planet') {
      cls = d > 40 ? 'lod-far' : d > 22 ? 'lod-mid' : 'lod-near';
    } else {
      cls = d > galaxyLodFar ? 'lod-far' : d > galaxyLodMid ? 'lod-mid' : 'lod-near';
    }
    if (meta.lod !== cls) {
      if (meta.lod) meta.el.classList.remove(meta.lod);
      meta.el.classList.add(cls);
      meta.lod = cls;
    }
  }
}

// ---------------- 场景内容 ----------------

function clearContent(): void {
  interactionController?.setHover(null);
  removeSelectionFx(false);
  pickables.length = 0;
  hovered = null;
  clearLabels();
  spiralNodes.length = 0;
  if (depLines) {
    depLines.dispose();
    depLines = null;
  }
  planetLocalPos.clear();
  for (const k of Object.keys(planetMeshes)) delete planetMeshes[k];
  if (nebulaCore) {
    disposeNebulaCore(nebulaCore);
    nebulaCore = null;
  }
  starCore = null;
  if (!interactionRoot) {
    interactionRoot = new THREE.Group();
    contentGroup.add(interactionRoot);
  } else {
    disposeObject3D(interactionRoot);
    while (interactionRoot.children.length) {
      interactionRoot.remove(interactionRoot.children[0]);
    }
    interactionRoot.rotation.set(0, 0, 0);
  }
}

/** 视图渲染令牌：宇宙/星系渲染是异步的，后发起的渲染要能作废先前未完成的 */
let renderToken = 0;

async function renderUniverse(): Promise<void> {
  const token = ++renderToken;
  loading.value = true;
  view.value = 'universe';
  orbitStore.enterUniverseView();
  currentGalaxy.value = null;
  searchQuery.value = '';
  hintText.value = '拖拽旋转 · 滚轮缩放 · 点击星系进入';
  const galaxies = await fetchGalaxies();
  if (token !== renderToken) return;
  galaxyCache = galaxies;
  galaxyList.value = galaxyCache;
  clearContent();

  nebulaCore = buildNebulaCore(0x38bdf8, lowPowerMode);
  interactionRoot.add(nebulaCore.root);

  const titleLabel = makeTextLabel('SparkOrbit · 知识宇宙', 'title');
  titleLabel.position.set(0, 8.5, 0);
  interactionRoot.add(titleLabel);

  // 黄金角螺旋布局（N ≤ 6 退化为单环）+ 全局粒子预算，10+ 星系也能摆下且帧率不线性劣化
  const layout = layoutGalaxies(galaxyCache);
  const budget = galaxyPointBudget(galaxyCache.length, lowPowerMode);
  layout.placements.forEach(({ galaxy: g, position, size }) => {
    const node = createSpiralGalaxy(g, position, size, lowPowerMode, { pointBudget: budget });
    interactionRoot.add(node.root);
    pickables.push(node.pickMesh);
    spiralNodes.push(node);

    const label = makeGalaxyLabel(g);
    node.labelAnchor.add(label);
  });

  // 标签 LOD 阈值与相机取景随布局半径自适应（盘径放大后基准同步放宽）
  const lodScale = THREE.MathUtils.clamp(layout.boundRadius / 26, 1, 3);
  galaxyLodMid = 44 * lodScale;
  galaxyLodFar = 68 * lodScale;
  const dist = fitCameraDistance(layout.boundRadius + 4, camera.fov, camera.aspect);
  controls.maxDistance = Math.max(90, dist * 1.7);

  interactionController?.setPaused(true);
  const tl = gsap.timeline({
    onComplete: () => interactionController?.setPaused(false),
  });
  activeTweens.push(tl);
  tl.to(camera.position, { x: 0, y: dist * 0.47, z: dist * 0.88, duration: 1.4, ease: 'power2.out', onUpdate: () => controls.update() })
    .to(controls.target, { x: 0, y: 0, z: 0, duration: 1.4, ease: 'power2.out', onUpdate: () => controls.update() }, 0);
  loading.value = false;
}

function drawConstellationLines(detail: GalaxyDetail): void {
  for (const c of constellations) {
    if (!c.completed) continue;
    const positions: THREE.Vector3[] = c.planet_slugs
      .map((s) => planetLocalPos.get(s))
      .filter(Boolean) as THREE.Vector3[];
    if (positions.length < 2) continue;
    for (let i = 0; i < positions.length - 1; i++) {
      const geo = new THREE.BufferGeometry().setFromPoints([positions[i], positions[i + 1]]);
      interactionRoot.add(new THREE.Line(geo, new THREE.LineBasicMaterial({ color: 0xfbbf24, transparent: true, opacity: 0.7 })));
    }
  }
}

/** 依赖深度（BFS）：无前置 = 0，其余 = max(前置深度)+1；用于逐层 bloom 入场 */
function computeDepths(planets: Planet[]): Map<string, number> {
  const bySlug = new Map(planets.map((p) => [p.slug, p]));
  const depth = new Map<string, number>();
  const visiting = new Set<string>();
  function resolve(slug: string): number {
    if (depth.has(slug)) return depth.get(slug)!;
    if (visiting.has(slug)) return 0;
    visiting.add(slug);
    const p = bySlug.get(slug);
    let v = 0;
    if (p?.prerequisites?.length) {
      for (const q of p.prerequisites) {
        if (bySlug.has(q)) v = Math.max(v, resolve(q) + 1);
      }
    }
    visiting.delete(slug);
    depth.set(slug, v);
    return v;
  }
  planets.forEach((p) => resolve(p.slug));
  return depth;
}

async function enterGalaxy(slug: string): Promise<void> {
  const token = ++renderToken;
  loading.value = true;
  const detail = await fetchGalaxyDetail(slug);
  if (token !== renderToken) return;
  searchQuery.value = '';
  currentGalaxy.value = detail;
  view.value = 'galaxy';
  orbitStore.enterGalaxyView(detail);
  hintText.value = `${detail.name} · 点击暗淡行星发起挑战（锁定行星需先点亮前置）`;
  clearContent();

  const base = new THREE.Color(detail.color);
  // 星系视图尺度固定，缩放范围复位（宇宙视图可能被自适应放宽过）
  controls.maxDistance = 90;
  // 星系中心的恒星即星球光源：昼夜面朝向由它决定
  setPlanetSunLight(base, new THREE.Vector3(0, 0, 0));
  starCore = buildStarCore(base, lowPowerMode);
  interactionRoot.add(starCore.root);
  interactionRoot.add(new THREE.AmbientLight(0x334466, 0.38));
  const starLabel = makeTextLabel(detail.name, 'star');
  starLabel.position.set(0, 5.8, 0);
  interactionRoot.add(starLabel);

  const maxOrbit = Math.max(1, ...detail.planets.map((p) => p.orbit_index));
  for (let o = 1; o <= maxOrbit; o++) {
    interactionRoot.add(buildParticleOrbitRing(4 + o * 2.6, base.getHex(), lowPowerMode ? 60 : 140));
  }

  const depths = computeDepths(detail.planets);
  const layerCounters = new Map<number, number>();
  const enterTargets: { group: THREE.Group; delay: number }[] = [];

  detail.planets.forEach((p) => {
    const radius = 4 + p.orbit_index * 2.6 + p.radius_offset;
    const angle = (p.angle_deg * Math.PI) / 180;
    const x = Math.cos(angle) * radius;
    const z = Math.sin(angle) * radius;
    const y = p.radius_offset * 0.8;
    const size = p.difficulty === 'hard' ? 0.9 : p.difficulty === 'medium' ? 0.75 : 0.62;
    const group = createPlanetMesh(p, base, lowPowerMode);
    group.root.position.set(x, y, z);
    group.body.userData.type = 'planet';
    group.body.userData.planet = p;
    interactionRoot.add(group.root);
    pickables.push(group.body);
    planetMeshes[p.slug] = group.body;
    planetLocalPos.set(p.slug, new THREE.Vector3(x, y, z));

    const depth = depths.get(p.slug) ?? 0;
    const idxInLayer = layerCounters.get(depth) ?? 0;
    layerCounters.set(depth, idxInLayer + 1);
    enterTargets.push({ group: group.root, delay: 0.15 + depth * 0.26 + idxInLayer * 0.055 });

    const label = makePlanetLabel(p);
    label.position.set(x, y + size + 1.0, z);
    interactionRoot.add(label);
  });

  // 依赖上游 → 下游逐层 bloom 浮现；reduced-motion 时跳过
  if (enterTargets.length && !reduceMotion) {
    enterTargets.forEach(({ group: rootGroup, delay }) => {
      const target = rootGroup.scale.clone();
      rootGroup.scale.setScalar(0.001);
      activeTweens.push(
        gsap.to(rootGroup.scale, {
          x: target.x,
          y: target.y,
          z: target.z,
          duration: 0.55,
          delay,
          ease: 'back.out(1.9)',
        }),
      );
    });
  }

  depLines = buildDependencyLines(detail.planets, planetLocalPos);
  interactionRoot.add(depLines.group);
  drawConstellationLines(detail);

  interactionController?.setPaused(true);
  const tl = gsap.timeline({
    onComplete: () => interactionController?.setPaused(false),
  });
  activeTweens.push(tl);
  tl.fromTo(
    camera.position,
    { x: 0, y: 34, z: 48 },
    { x: 0, y: 16, z: 30, duration: 1.4, ease: 'power2.out', onUpdate: () => controls.update() }
  ).to(controls.target, { x: 0, y: 0, z: 0, duration: 1.4, ease: 'power2.out', onUpdate: () => controls.update() }, 0);
  loading.value = false;

  // 重载星系后（如点亮刷新）保持选中星球的视觉状态
  const selected = orbitStore.selectedPlanet;
  if (selected && planetMeshes[selected.slug]) {
    applySelectionFx(selected.slug);
  }
}

// ---------------- 选中反馈：reticle + 其余降亮 ----------------

function buildReticle(radius: number): THREE.Group {
  const color = new THREE.Color(0x7dd3fc);
  const group = new THREE.Group();
  const mkArc = (r1: number, r2: number, arc: number, opacity: number) => new THREE.Mesh(
    new THREE.RingGeometry(r1, r2, 64, 1, 0, arc),
    new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity,
      side: THREE.DoubleSide,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  const a = mkArc(radius * 1.75, radius * 1.86, Math.PI * 1.5, 0.8);
  const b = mkArc(radius * 2.12, radius * 2.18, Math.PI * 0.9, 0.4);
  a.rotation.x = -Math.PI / 2;
  b.rotation.x = -Math.PI / 2;
  group.add(a, b);
  group.userData.arcA = a;
  group.userData.arcB = b;
  return group;
}

function applySelectionFx(slug: string): void {
  removeSelectionFx(true);
  const mesh = planetMeshes[slug];
  const pos = planetLocalPos.get(slug);
  if (!mesh || !pos || !currentGalaxy.value) return;

  const planet = mesh.userData.planet as Planet;
  const size = planet.difficulty === 'hard' ? 0.9 : planet.difficulty === 'medium' ? 0.75 : 0.62;
  reticle = buildReticle(size);
  reticle.position.copy(pos);
  interactionRoot.add(reticle);

  for (const s of Object.keys(planetMeshes)) {
    if (s === slug) continue;
    const m = planetMeshes[s];
    const mat = m.material as THREE.ShaderMaterial;
    if (mat.uniforms?.uSaturation) {
      activeTweens.push(gsap.to(mat.uniforms.uSaturation, { value: mat.uniforms.uSaturation.value * 0.3, duration: 0.5, ease: 'power2.out' }));
    }
    if (mat.uniforms?.uGlow) {
      activeTweens.push(gsap.to(mat.uniforms.uGlow, { value: 0, duration: 0.5, ease: 'power2.out' }));
    }
    const atmo = m.userData.fresnel as THREE.Mesh | undefined;
    const atmoMat = atmo?.material as THREE.ShaderMaterial | undefined;
    if (atmoMat?.uniforms?.uIntensity) {
      activeTweens.push(gsap.to(atmoMat.uniforms.uIntensity, { value: 0.06, duration: 0.5, ease: 'power2.out' }));
    }
    setLabelState(s, 'is-dimmed', true);
  }
  setLabelState(slug, 'is-active', true);
}

function removeSelectionFx(restore: boolean): void {
  if (reticle) {
    disposeObject3D(reticle);
    reticle.removeFromParent();
    reticle = null;
  }
  setLabelState(null, 'is-dimmed', false);
  setLabelState(null, 'is-active', false);
  if (!restore || !currentGalaxy.value) return;
  const base = new THREE.Color(currentGalaxy.value.color);
  for (const s of Object.keys(planetMeshes)) {
    const m = planetMeshes[s];
    const planet = m.userData.planet as Planet | undefined;
    if (planet) updatePlanetBodyVisuals(m, planet, base);
  }
}

watch(() => orbitStore.selectedPlanet, (p) => {
  if (view.value !== 'galaxy') return;
  if (p) applySelectionFx(p.slug);
  else removeSelectionFx(true);
});

// ---------------- 镜头 ----------------

/** 电影化 fly-to：距离自适应弧线（远则拉高再俯冲，近则平滑推近），时长随距离伸缩 */
function flyCameraTo(targetCam: THREE.Vector3, targetLook: THREE.Vector3, onComplete?: () => void): void {
  const startCam = camera.position.clone();
  const startLook = controls.target.clone();
  const dist = startCam.distanceTo(targetCam);
  const duration = reduceMotion ? 0 : THREE.MathUtils.clamp(0.7 + dist * 0.035, 0.9, 2.2);
  const mid = startCam.clone().lerp(targetCam, 0.5);
  mid.y += Math.min(4 + dist * 0.22, 13);
  const curve = new THREE.QuadraticBezierCurve3(startCam, mid, targetCam);
  const proxy = { t: 0 };
  cameraTweening = true;
  interactionController?.setPaused(true);
  const tween = gsap.to(proxy, {
    t: 1,
    duration: Math.max(duration, 0.01),
    ease: 'power2.inOut',
    onUpdate: () => {
      camera.position.copy(curve.getPoint(proxy.t));
      controls.target.lerpVectors(startLook, targetLook, proxy.t);
      controls.update();
    },
    onComplete: () => {
      cameraTweening = false;
      interactionController?.setPaused(false);
      onComplete?.();
    },
  });
  activeTweens.push(tween);
}

function flyToPlanet(mesh: THREE.Mesh, onComplete: () => void): void {
  const worldPos = mesh.getWorldPosition(new THREE.Vector3());
  const targetCam = worldPos.clone().add(new THREE.Vector3(0, 2.5, 6));
  flyCameraTo(targetCam, worldPos, onComplete);
}

// ---------------- 指针与拾取 ----------------

function onPointerLeave(): void {
  interactionController?.setPointer(0, 0);
  pointerOffset = { x: 0, y: 0 };
  pointerDirty = true;
}

function onPointerMove(event: PointerEvent): void {
  if (!pipeline) return;
  markInteraction();
  const rect = pipeline.renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  pointerOffset = { x: pointer.x, y: pointer.y };
  tooltip.value.x = event.clientX - rect.left;
  tooltip.value.y = event.clientY - rect.top;
  interactionController?.setPointer(pointer.x, pointer.y);
  pointerDirty = true;
}

function selectPlanetTarget(planet: Planet, mesh: THREE.Mesh): void {
  if (planet.status === 'locked') {
    hintText.value = `「${planet.name}」尚被锁定，请先点亮其前置行星。`;
    orbitStore.pushNotification('行星锁定', hintText.value, 'warning');
    return;
  }
  if (!currentGalaxy.value) return;
  flyToPlanet(mesh, () => {
    orbitStore.selectPlanet(planet, currentGalaxy.value!);
    emit('select-planet', planet, currentGalaxy.value!);
  });
}

function onClick(): void {
  if (cameraTweening || !pipeline) return;
  markInteraction();
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(pickables, false);
  if (!hits.length) return;
  const obj = hits[0].object;
  const data = obj.userData;
  if (data.type === 'galaxy') {
    emit('enter-galaxy', data.slug, data.name);
    void enterGalaxy(data.slug);
  } else if (data.type === 'planet') {
    selectPlanetTarget(data.planet as Planet, obj as THREE.Mesh);
  }
}

function missingPrereqNames(planet: Planet): string[] {
  const g = currentGalaxy.value;
  if (!g || !planet.prerequisites?.length) return [];
  const names: string[] = [];
  for (const slug of planet.prerequisites) {
    const q = g.planets.find((x) => x.slug === slug);
    if (q && !(q.status === 'lit' || q.is_permanent)) names.push(q.name);
  }
  return names;
}

function updateHover(): void {
  if (cameraTweening || !pipeline) return;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(pickables, false);
  if (hits.length) {
    const obj = hits[0].object;
    if (hovered !== obj) {
      (hovered?.userData.onHover as ((on: boolean) => void) | undefined)?.(false);
      if (hovered?.userData.type === 'planet' && hovered.userData.planet) {
        setLabelState((hovered.userData.planet as Planet).slug, 'is-active', false);
      }
      interactionController?.setHover(obj as THREE.Mesh);
      (obj.userData.onHover as ((on: boolean) => void) | undefined)?.(true);
      hovered = obj;
    }
    const d = obj.userData;
    if (d.type === 'galaxy') {
      tooltip.value = { ...tooltip.value, visible: true, text: d.name, sub: d.sub, missing: [], score: -1 };
      orbitStore.setHoveredPlanet(null);
    } else if (d.type === 'planet') {
      const p = d.planet as Planet;
      orbitStore.setHoveredPlanet(p);
      setLabelState(p.slug, 'is-active', true);
      const statusText = p.is_permanent ? '永久恒星' : p.status === 'lit' ? '已点亮' : p.status === 'meteor' ? '陨石危机·需复习' : p.status === 'fading' ? '记忆衰减中' : p.status === 'locked' ? '锁定（前置未完成）' : '可挑战';
      tooltip.value = {
        ...tooltip.value,
        visible: true,
        text: p.name,
        sub: `${difficultyText(p.difficulty)} · ${statusText}`,
        missing: p.status === 'locked' ? missingPrereqNames(p) : [],
        score: p.attempts > 0 || p.status === 'lit' || p.is_permanent ? Math.round(p.score ?? 0) : -1,
      };
    }
    pipeline.renderer.domElement.style.cursor = 'pointer';
  } else {
    (hovered?.userData.onHover as ((on: boolean) => void) | undefined)?.(false);
    if (hovered?.userData.type === 'planet' && hovered.userData.planet) {
      const slug = (hovered.userData.planet as Planet).slug;
      if (orbitStore.selectedPlanet?.slug !== slug) setLabelState(slug, 'is-active', false);
    }
    interactionController?.setHover(null);
    hovered = null;
    orbitStore.setHoveredPlanet(null);
    tooltip.value.visible = false;
    pipeline.renderer.domElement.style.cursor = 'grab';
  }
}

// ---------------- 帧循环 ----------------

function animate(): void {
  frameId = requestAnimationFrame(animate);
  if (!isActive.value || document.hidden || !pipeline) return;

  const now = performance.now();
  frameCount++;

  // 默认静止；空闲 10 秒后缓慢自转，任何交互立即停止
  if (contentGroup && !reduceMotion) {
    const idle = now - lastInteraction;
    if (idle > IDLE_SPIN_DELAY) {
      const ramp = Math.min((idle - IDLE_SPIN_DELAY) / 6000, 1);
      contentGroup.rotation.y += ramp * (view.value === 'universe' ? 0.0005 : 0.0008);
    }
  }
  nebulaBg?.layers.forEach(({ group, speed }) => { group.rotation.y += speed; });
  nebulaBg?.tick(now);
  nebulaCore?.tick(now);
  skyDome?.tick(now);
  shootingStars?.tick(now);
  particleField?.tick(now, pointerOffset);
  tickPlanetVisuals(now);
  starCore?.tick(now);
  spiralNodes.forEach((node) => node.tick(now));
  depLines?.tick(now);

  if (reticle) {
    (reticle.userData.arcA as THREE.Mesh).rotation.z += 0.012;
    (reticle.userData.arcB as THREE.Mesh).rotation.z -= 0.02;
  }

  // 星球自转；云层与本体同步旋转，云的流动交给 shader，这样地表云影才能对齐
  for (const slug of Object.keys(planetMeshes)) {
    const body = planetMeshes[slug];
    const spin = (body.userData.spinSpeed as number) || 0;
    if (spin) {
      body.rotation.y += spin;
      const clouds = body.userData.clouds as THREE.Mesh | undefined;
      if (clouds) clouds.rotation.y = body.rotation.y;
    }
  }

  for (let i = burstFxList.length - 1; i >= 0; i--) {
    if (updateBurstFx(scene, burstFxList[i])) burstFxList.splice(i, 1);
  }

  interactionController?.tick();
  controls.update();
  if (pointerDirty) { updateHover(); pointerDirty = false; }
  if (frameCount % 6 === 0) updateLabelLod();
  pipeline.composer.render();
  pipeline.labelRenderer?.render(scene, camera);
}

function onResize(): void {
  if (!container.value || !pipeline) return;
  const w = container.value.clientWidth;
  const h = container.value.clientHeight;
  if (w <= 0 || h <= 0) return;
  resizeRenderPipeline(pipeline, camera, w, h);
}

let needsReactivate = false;

async function reactivate(): Promise<void> {
  if (!container.value || !pipeline) return;
  onResize();
  if (needsReactivate || container.value.clientWidth > 0) {
    needsReactivate = false;
    await renderUniverse();
  }
}

function triggerSupernova(slug: string): void {
  const mesh = planetMeshes[slug];
  if (!mesh || !pipeline) return;
  const worldPos = mesh.getWorldPosition(new THREE.Vector3());
  const color = (mesh.userData.baseColor as THREE.Color | undefined)?.clone() ?? new THREE.Color(0xffffff);
  activeTweens.push(playSupernovaOnMesh(mesh));
  spawnShockwave(scene, camera, worldPos);
  burstFxList.push(spawnBurst(scene, worldPos, color));

  const v = worldPos.clone().project(camera);
  const rect = pipeline.renderer.domElement.getBoundingClientRect();
  emit('supernova', { x: rect.left + (v.x * 0.5 + 0.5) * rect.width, y: rect.top + (-v.y * 0.5 + 0.5) * rect.height });
}

function updatePlanetMaterial(slug: string, status: PlanetStatus): void {
  const mesh = planetMeshes[slug];
  if (!mesh || !currentGalaxy.value) return;
  const planet = mesh.userData.planet as Planet;
  const updated = { ...planet, status };
  mesh.userData.planet = updated;
  updatePlanetBodyVisuals(mesh, updated, new THREE.Color(currentGalaxy.value.color));
}

function reloadCurrentGalaxy(): void {
  if (view.value === 'galaxy' && currentGalaxy.value) void enterGalaxy(currentGalaxy.value.slug);
}

function backToUniverse(): void {
  if (view.value === 'universe') return;
  orbitStore.clearSelection();
  void renderUniverse();
}

watch(() => orbitStore.materialChangeQueue, (change) => {
  if (!change) return;
  updatePlanetMaterial(change.slug, change.status);
  const mesh = planetMeshes[change.slug];
  const name = mesh ? (mesh.userData.planet as Planet).name : change.slug;
  orbitStore.ackMaterialChange();
  orbitStore.pushNotification('掌握度变化', `「${name}」状态已更新`, change.status === 'lit' ? 'success' : 'warning');
});

function spawnMeteorFx(isHit: boolean): void {
  if (!pipeline) return;
  const worldPos = new THREE.Vector3(0, 0, 0);
  const fx = spawnMeteorImpact(scene, camera, worldPos, isHit);
  if (fx) burstFxList.push(fx);
}

let focusMode = false;
function setFocusMode(active: boolean): void {
  if (!camera || !interactionRoot || focusMode === active) return;
  focusMode = active;
  const duration = reduceMotion ? 0 : 0.72;
  activeTweens.push(
    gsap.to(interactionRoot.scale, {
      x: active ? 0.72 : 1,
      y: active ? 0.72 : 1,
      z: active ? 0.72 : 1,
      duration,
      ease: 'power3.inOut',
      overwrite: 'auto',
    }),
  );
  activeTweens.push(
    gsap.to(camera, {
      fov: active ? 66 : 55,
      duration,
      ease: 'power3.inOut',
      overwrite: 'auto',
      onUpdate: () => camera.updateProjectionMatrix(),
    }),
  );
}

async function focusGalaxy(slug: string): Promise<void> {
  await enterGalaxy(slug);
}

async function focusPlanet(galaxySlug: string, planetSlug: string): Promise<void> {
  if (currentGalaxy.value?.slug !== galaxySlug || view.value !== 'galaxy') {
    await enterGalaxy(galaxySlug);
  }
  const mesh = planetMeshes[planetSlug];
  const planet = currentGalaxy.value?.planets.find((item) => item.slug === planetSlug);
  if (!mesh || !planet || !currentGalaxy.value) return;
  flyToPlanet(mesh, () => {
    orbitStore.selectPlanet(planet, currentGalaxy.value!);
    emit('select-planet', planet, currentGalaxy.value!);
  });
}

defineExpose({
  reloadCurrentGalaxy,
  backToUniverse,
  triggerSupernova,
  updatePlanetMaterial,
  reactivate,
  spawnMeteorFx,
  setFocusMode,
  focusGalaxy,
  focusPlanet,
});

// ---------------- HUD：面包屑 / 搜索 / 图例 / 进度 ----------------

const selectedPlanetName = computed(() => orbitStore.selectedPlanet?.name ?? '');

const galaxyProgress = computed(() => {
  const g = currentGalaxy.value;
  if (!g?.planets?.length) return { lit: 0, total: 0, pct: 0 };
  const lit = g.planets.filter((p) => p.status === 'lit' || p.is_permanent).length;
  return { lit, total: g.planets.length, pct: Math.round((lit / g.planets.length) * 100) };
});

const PROGRESS_R = 16;
const PROGRESS_C = 2 * Math.PI * PROGRESS_R;

const searchResults = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q || !currentGalaxy.value) return [];
  return currentGalaxy.value.planets
    .filter((p) => p.name.toLowerCase().includes(q) || p.slug.toLowerCase().includes(q))
    .slice(0, 6);
});

const galaxySearchResults = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return [];
  return galaxyList.value
    .filter((g) => g.name.toLowerCase().includes(q) || g.slug.toLowerCase().includes(q))
    .slice(0, 6);
});

function pickSearchResult(planet: Planet): void {
  searchQuery.value = '';
  searchOpen.value = false;
  const mesh = planetMeshes[planet.slug];
  if (mesh) selectPlanetTarget(planet, mesh);
}

function pickGalaxyResult(g: Galaxy): void {
  searchQuery.value = '';
  searchOpen.value = false;
  jumpToGalaxy(g);
}

function onSearchEnter(): void {
  if (view.value === 'universe') {
    if (galaxySearchResults.value.length) pickGalaxyResult(galaxySearchResults.value[0]);
  } else if (searchResults.value.length) {
    pickSearchResult(searchResults.value[0]);
  }
}

function jumpToGalaxy(g: Galaxy): void {
  emit('enter-galaxy', g.slug, g.name);
  void enterGalaxy(g.slug);
}

const stripRef = ref<HTMLDivElement | null>(null);
function onStripWheel(e: WheelEvent): void {
  if (stripRef.value) stripRef.value.scrollLeft += e.deltaY;
}

function crumbGalaxy(): void {
  // 回到星系全景：清除选中并复位镜头
  orbitStore.clearSelection();
  flyCameraTo(new THREE.Vector3(0, 16, 30), new THREE.Vector3(0, 0, 0));
}

const LEGEND_ITEMS = [
  { key: 'locked', label: '锁定', color: '#64748b' },
  { key: 'dim', label: '可挑战', color: '#7dd3fc' },
  { key: 'lit', label: '已点亮', color: '#fbbf24' },
  { key: 'fading', label: '衰减中', color: '#fb923c' },
  { key: 'meteor', label: '陨石危机', color: '#f87171' },
];

// ---------------- 生命周期 ----------------

onMounted(async () => {
  if (!container.value) return;
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x050818);
  scene.fog = new THREE.FogExp2(0x050818, 0.003);
  const w = container.value.clientWidth;
  const h = container.value.clientHeight;
  const aspect = w > 0 && h > 0 ? w / h : 16 / 9;
  camera = new THREE.PerspectiveCamera(55, aspect, 0.1, 1000);
  camera.position.set(0, 20, 38);

  if (container.value.clientWidth <= 0 || container.value.clientHeight <= 0) {
    needsReactivate = true;
  }
  lowPowerMode = window.devicePixelRatio > 1.5 || container.value.clientWidth < 900;
  pipeline = createRenderPipeline(container.value, scene, camera, { lowPower: lowPowerMode, enableLabels: true });
  controls = new OrbitControls(camera, pipeline.renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = 8;
  controls.maxDistance = 90;
  controls.enablePan = false;
  controls.zoomSpeed = 0.85;
  controls.addEventListener('start', markInteraction);

  raycaster = new THREE.Raycaster();
  scene.add(new THREE.AmbientLight(0x445577, 0.32));
  scene.add(new THREE.HemisphereLight(0x6366f1, 0x050818, 0.25));
  // 主方向光：给星球日夜明暗与高光，形成体积感
  const keyLight = new THREE.DirectionalLight(0xfff4e0, 1.35);
  keyLight.position.set(18, 24, 14);
  scene.add(keyLight);
  const rimLight = new THREE.DirectionalLight(0x7dd3fc, 0.35);
  rimLight.position.set(-20, -8, -16);
  scene.add(rimLight);
  skyDome = buildSkyDome(scene, lowPowerMode);
  distantGalaxies = buildDistantGalaxies(scene, lowPowerMode);
  if (!lowPowerMode && !reduceMotion) shootingStars = buildShootingStars(scene);
  nebulaBg = buildNebulaBackground(scene, lowPowerMode);
  particleField = buildParticleField(scene, lowPowerMode);
  contentGroup = new THREE.Group();
  scene.add(contentGroup);
  interactionRoot = new THREE.Group();
  contentGroup.add(interactionRoot);
  interactionController = new PlanetInteractionController({
    interactionRoot,
    parallax: nebulaBg,
    controls,
    lowPower: lowPowerMode,
  });

  pipeline.renderer.domElement.addEventListener('pointermove', onPointerMove);
  pipeline.renderer.domElement.addEventListener('pointerleave', onPointerLeave);
  pipeline.renderer.domElement.addEventListener('click', onClick);
  window.addEventListener('resize', onResize);
  applyCanvasInteractivity(isInteractive.value);

  try { constellations = await fetchConstellations(); } catch { constellations = []; }
  await renderUniverse();
  animate();
});

onBeforeUnmount(() => {
  cancelAnimationFrame(frameId);
  activeTweens.forEach((t) => t.kill());
  activeTweens.length = 0;
  clearLabels();
  depLines?.dispose();
  depLines = null;
  window.removeEventListener('resize', onResize);
  controls?.removeEventListener('start', markInteraction);
  pipeline?.renderer.domElement.removeEventListener('pointermove', onPointerMove);
  pipeline?.renderer.domElement.removeEventListener('pointerleave', onPointerLeave);
  pipeline?.renderer.domElement.removeEventListener('click', onClick);
  controls?.dispose();
  interactionController?.dispose();
  interactionController = null;
  disposeObject3D(contentGroup);
  disposeNebulaBackground(nebulaBg);
  disposeParticleField(particleField);
  particleField = null;
  skyDome?.dispose();
  skyDome = null;
  shootingStars?.dispose();
  shootingStars = null;
  distantGalaxies?.dispose();
  distantGalaxies = null;
  disposeNebulaCore(nebulaCore);
  burstFxList.forEach((fx) => {
    scene?.remove(fx.points);
    fx.points.geometry.dispose();
    (fx.points.material as THREE.Material).dispose();
  });
  disposeRenderPipeline(pipeline);
  pipeline = null;
});
</script>

<template>
  <div class="relative h-full w-full overflow-hidden bg-black">
    <div ref="container" class="h-full w-full"></div>
    <!-- 暗角：画面向中央聚焦，零 GPU 成本 -->
    <div class="vignette-overlay pointer-events-none absolute inset-0 z-[1]"></div>

    <!-- 面包屑：宇宙 › 星系 › 星球 -->
    <div class="pointer-events-auto absolute left-1/2 top-20 z-10 -translate-x-1/2">
      <div class="cosmic-nav-btn flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs">
        <button
          class="transition"
          :class="view === 'universe' ? 'cursor-default font-semibold text-sky-100' : 'text-sky-300/80 hover:text-sky-100'"
          @click="backToUniverse"
        >知识宇宙</button>
        <template v-if="view === 'galaxy' && currentGalaxy">
          <span class="text-slate-500">›</span>
          <button
            class="transition"
            :class="selectedPlanetName ? 'text-sky-300/80 hover:text-sky-100' : 'cursor-default font-semibold text-sky-100'"
            @click="crumbGalaxy"
          >{{ currentGalaxy.name }}</button>
        </template>
        <template v-if="selectedPlanetName">
          <span class="text-slate-500">›</span>
          <span class="font-semibold text-amber-200">{{ selectedPlanetName }}</span>
        </template>
      </div>
    </div>

    <!-- 快速跳转：宇宙层星系搜索 + 可横滚 chips / 星系层星球搜索 -->
    <div class="pointer-events-auto absolute left-1/2 top-[7.6rem] z-10 flex -translate-x-1/2 flex-col items-center gap-1.5">
      <div v-if="view === 'universe' && galaxyList.length" class="relative">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索星系名，回车飞入…"
          class="cosmic-nav-btn w-56 rounded-full bg-transparent px-4 py-1.5 text-xs text-sky-100 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-400/50"
          @focus="searchOpen = true"
          @blur="searchOpen = false"
          @keydown.enter.prevent="onSearchEnter"
        />
        <div
          v-if="(searchOpen || searchQuery) && galaxySearchResults.length"
          class="absolute left-0 top-full z-20 mt-1.5 w-full overflow-hidden rounded-2xl border border-white/10 bg-[#0a1228]/95 shadow-xl backdrop-blur"
        >
          <button
            v-for="g in galaxySearchResults"
            :key="g.slug"
            class="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-slate-200 transition hover:bg-white/5"
            @mousedown.prevent="pickGalaxyResult(g)"
          >
            <span class="h-2 w-2 shrink-0 rounded-full" :style="{ background: g.color }"></span>
            <span class="flex-1 truncate">{{ g.name }}</span>
            <span class="text-[10px] text-slate-500">{{ g.lit_count }}/{{ g.planet_count }}</span>
          </button>
        </div>
      </div>
      <div
        v-if="view === 'universe' && galaxyList.length"
        ref="stripRef"
        class="quickjump-strip flex max-w-[min(760px,92vw)] items-center gap-1.5 overflow-x-auto"
        @wheel.prevent="onStripWheel"
      >
        <button
          v-for="g in galaxyList"
          :key="g.slug"
          class="cosmic-nav-btn shrink-0 whitespace-nowrap rounded-full px-3 py-1 text-[11px] text-sky-100 transition hover:bg-white/10"
          @click="jumpToGalaxy(g)"
        >
          <span :style="{ color: g.color }">●</span>
          {{ g.name }}
          <span class="ml-1 text-[10px] text-slate-400">{{ g.lit_count }}/{{ g.planet_count }}</span>
        </button>
      </div>
      <div v-else-if="view === 'galaxy'" class="relative">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索星球名，回车跃迁…"
          class="cosmic-nav-btn w-64 rounded-full bg-transparent px-4 py-1.5 text-xs text-sky-100 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-400/50"
          @focus="searchOpen = true"
          @blur="searchOpen = false"
          @keydown.enter.prevent="onSearchEnter"
        />
        <div
          v-if="(searchOpen || searchQuery) && searchResults.length"
          class="absolute left-0 top-full z-20 mt-1.5 w-full overflow-hidden rounded-2xl border border-white/10 bg-[#0a1228]/95 shadow-xl backdrop-blur"
        >
          <button
            v-for="p in searchResults"
            :key="p.slug"
            class="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-slate-200 transition hover:bg-white/5"
            @mousedown.prevent="pickSearchResult(p)"
          >
            <span
              class="h-2 w-2 shrink-0 rounded-full"
              :style="{ background: p.is_permanent || p.status === 'lit' ? '#fbbf24' : p.status === 'locked' ? '#64748b' : p.status === 'meteor' ? '#f87171' : p.status === 'fading' ? '#fb923c' : '#7dd3fc' }"
            ></span>
            <span class="flex-1 truncate">{{ p.name }}</span>
            <span class="text-[10px] text-slate-500">{{ p.status === 'locked' ? '锁定' : p.is_permanent || p.status === 'lit' ? '已点亮' : '可挑战' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 星系进度环 -->
    <div v-if="view === 'galaxy' && galaxyProgress.total" class="pointer-events-none absolute right-5 top-20 z-10">
      <div class="cosmic-nav-btn flex items-center gap-2.5 rounded-full px-3 py-1.5">
        <svg width="40" height="40" viewBox="0 0 40 40" class="-rotate-90">
          <circle cx="20" cy="20" :r="PROGRESS_R" fill="none" stroke="rgba(148,197,255,0.15)" stroke-width="3.5" />
          <circle
            cx="20" cy="20" :r="PROGRESS_R" fill="none" stroke="#fbbf24" stroke-width="3.5" stroke-linecap="round"
            :stroke-dasharray="PROGRESS_C"
            :stroke-dashoffset="PROGRESS_C * (1 - galaxyProgress.pct / 100)"
            style="transition: stroke-dashoffset 0.6s ease"
          />
        </svg>
        <div class="text-[10px] leading-tight text-slate-300">
          <p class="font-semibold text-sky-100">{{ currentGalaxy?.name }}</p>
          <p>已点亮 <span class="font-semibold text-amber-200">{{ galaxyProgress.lit }}/{{ galaxyProgress.total }}</span></p>
        </div>
      </div>
    </div>

    <!-- 五态图例 -->
    <div v-if="view === 'galaxy' && !props.slim" class="pointer-events-none absolute bottom-5 left-5 z-10">
      <div class="cosmic-nav-btn flex items-center gap-3 rounded-full px-4 py-1.5">
        <span v-for="item in LEGEND_ITEMS" :key="item.key" class="flex items-center gap-1.5 text-[10px] text-slate-300">
          <span class="h-2 w-2 rounded-full" :style="{ background: item.color, boxShadow: `0 0 6px ${item.color}` }"></span>
          {{ item.label }}
        </span>
      </div>
    </div>

    <div class="cosmic-hint pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full px-4 py-1.5 text-[11px] text-slate-200">{{ hintText }}</div>
    <div v-if="loading" class="pointer-events-none absolute inset-0 flex items-center justify-center">
      <div class="cosmic-nav-btn rounded-2xl px-6 py-3 text-sm text-sky-200 animate-pulse-ring">星图加载中…</div>
    </div>
    <transition name="tooltip-fade">
      <div v-if="tooltip.visible" class="cosmic-tooltip pointer-events-none absolute z-10 -translate-y-full rounded-lg px-3 py-1.5 text-xs text-white" :style="{ left: `${tooltip.x + 12}px`, top: `${tooltip.y - 8}px` }">
        <p class="font-semibold tracking-wide">{{ tooltip.text }}</p>
        <p class="text-[10px] text-sky-300">{{ tooltip.sub }}</p>
        <p v-if="tooltip.score >= 0" class="text-[10px] text-amber-200">掌握度 {{ tooltip.score }}%</p>
        <p v-if="tooltip.missing.length" class="max-w-[220px] text-[10px] text-rose-300">
          待点亮前置：{{ tooltip.missing.join('、') }}
        </p>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.tooltip-fade-enter-active,
.tooltip-fade-leave-active {
  transition: opacity 0.16s ease, transform 0.16s ease;
}
.tooltip-fade-enter-from,
.tooltip-fade-leave-to {
  opacity: 0;
  transform: translateY(calc(-100% + 4px));
}

.vignette-overlay {
  background: radial-gradient(ellipse 78% 68% at 50% 46%, transparent 58%, rgba(2, 6, 20, 0.36) 86%, rgba(1, 3, 12, 0.62) 100%);
}

/* 星系数量多时 chips 可横滚：隐藏滚动条 + 两端渐隐遮罩 */
.quickjump-strip {
  scrollbar-width: none;
  mask-image: linear-gradient(90deg, transparent, #000 20px, #000 calc(100% - 20px), transparent);
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 20px, #000 calc(100% - 20px), transparent);
}
.quickjump-strip::-webkit-scrollbar {
  display: none;
}
</style>

<!-- CSS2D 标签由 renderer 动态插入 DOM，需全局样式 -->
<style>
.orbit-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(8, 13, 32, 0.72);
  border: 1px solid rgba(125, 211, 252, 0.18);
  color: #dbeafe;
  font-size: 12px;
  line-height: 1.3;
  white-space: nowrap;
  backdrop-filter: blur(4px);
  user-select: none;
  transform: translateY(-6px);
  transition: opacity 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
}
.orbit-label .name {
  font-weight: 600;
  letter-spacing: 0.02em;
}
.orbit-label .sub {
  font-size: 10px;
  color: #94a3b8;
}
.orbit-label .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.orbit-label .badge {
  font-size: 10px;
  padding: 0 6px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  color: #cbd5e1;
}
.orbit-label .bar {
  width: 34px;
  height: 4px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.25);
  overflow: hidden;
}
.orbit-label .bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #38bdf8, #fbbf24);
}

/* 状态配色 */
.orbit-label.st-locked { color: #94a3b8; border-color: rgba(100, 116, 139, 0.3); }
.orbit-label.st-locked .dot { background: #64748b; }
.orbit-label.st-dim .dot { background: #7dd3fc; box-shadow: 0 0 6px rgba(125, 211, 252, 0.8); }
.orbit-label.st-lit { border-color: rgba(251, 191, 36, 0.4); }
.orbit-label.st-lit .dot { background: #fbbf24; box-shadow: 0 0 8px rgba(251, 191, 36, 0.9); }
.orbit-label.st-fading { border-color: rgba(251, 146, 60, 0.4); }
.orbit-label.st-fading .dot { background: #fb923c; box-shadow: 0 0 6px rgba(251, 146, 60, 0.8); }
.orbit-label.st-meteor { border-color: rgba(248, 113, 113, 0.45); }
.orbit-label.st-meteor .dot { background: #f87171; box-shadow: 0 0 8px rgba(248, 113, 113, 0.9); }

/* 星系 / 恒星 / 标题标签 */
.orbit-label.galaxy {
  flex-direction: column;
  gap: 2px;
  padding: 4px 14px;
  border-radius: 14px;
}
.orbit-label.galaxy .bar {
  width: 56px;
}
.orbit-label.star,
.orbit-label.title {
  background: transparent;
  border-color: transparent;
  backdrop-filter: none;
  color: rgba(203, 225, 255, 0.92);
  text-shadow: 0 2px 8px rgba(5, 8, 24, 0.8);
}
.orbit-label.title .name {
  font-size: 14px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: rgba(203, 225, 255, 0.85);
}

/* 距离 LOD：远处隐藏，中距只留状态点 + 名称，近距完整芯片 */
.orbit-label.lod-far { opacity: 0; }
.orbit-label.lod-mid .badge,
.orbit-label.lod-mid .bar,
.orbit-label.lod-mid .sub { display: none; }

/* 选中 / 悬停 / 降亮 */
.orbit-label.is-dimmed { opacity: 0.15; }
.orbit-label.is-active {
  opacity: 1 !important;
  border-color: rgba(125, 211, 252, 0.7);
  box-shadow: 0 0 18px rgba(56, 189, 248, 0.35);
}
.orbit-label.is-active .badge,
.orbit-label.is-active .bar { display: inline-flex !important; }
</style>

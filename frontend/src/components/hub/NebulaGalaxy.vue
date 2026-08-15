<script setup lang="ts">
import * as THREE from 'three';
import gsap from 'gsap';
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import {
  createRenderPipeline,
  disposeRenderPipeline,
  resizeRenderPipeline,
  type RenderPipeline,
} from '../../three/create-renderer';
import { createNebulaSimulation, type NebulaSimulation } from '../../three/gpgpu/nebula-simulation';
import { createCameraDirector, type CameraDirector } from '../../three/galaxy/camera-director';
import { buildClusterGlows, type ClusterGlows } from '../../three/galaxy/cluster-glows';
import {
  buildNebulaBackground,
  disposeNebulaBackground,
  type NebulaBackground,
} from '../../three/nebula-background';
import {
  CLUSTERS,
  clusterByKey,
  type GalaxyZoneKey,
  type ZoneAnchor,
} from '../../three/galaxy/cluster-layout';

const props = withDefaults(defineProps<{ dimmed?: boolean }>(), { dimmed: false });
const emit = defineEmits<{ (e: 'fallback'): void }>();

const container = ref<HTMLDivElement | null>(null);

/** 粒子分档：纹理边长²=粒子数（高 36864 / 中 16384 / 低 8100） */
const TIERS = [90, 128, 192] as const;
type TierIndex = 0 | 1 | 2;

// 跨挂载记忆：从 learn/study/domain 返回时走快速入场，且沿用已降过的档位
let hasPlayedIntro = false;
let cachedTier: TierIndex | null = null;

let pipeline: RenderPipeline | null = null;
let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let sim: NebulaSimulation | null = null;
let director: CameraDirector | null = null;
let glows: ClusterGlows | null = null;
let nebulaBg: NebulaBackground | null = null;
let frameId = 0;
let tier: TierIndex = 2;
let failed = false;
let awayFromHome = false;
let flyBusy = false;

const anchors = reactive<ZoneAnchor[]>(
  CLUSTERS.map((c) => ({ key: c.key, x: 0, y: 0, depth: 0.5, visible: false, hovered: false })),
);

const pointerNdc = new THREE.Vector2(0, 0);
const pointerPx = { x: -1e4, y: -1e4 };
let pointerInside = false;
const raycaster = new THREE.Raycaster();
const galaxyPlane = new THREE.Plane();
const tmpWorld = new THREE.Vector3();
const tmpProject = new THREE.Vector3();
const tmpDir = new THREE.Vector3();

let externalHover: GalaxyZoneKey | null = null;
let currentHoverId = -1;

// FPS 看门狗
let fpsFrames = 0;
let fpsWindowStart = 0;
let lowFpsStrikes = 0;

function pickInitialTier(): TierIndex {
  if (cachedTier !== null) return cachedTier;
  const w = window.innerWidth;
  const cores = navigator.hardwareConcurrency ?? 8;
  if (w < 700 || cores <= 2) return 0;
  if (window.devicePixelRatio > 1.5 || w < 1100 || cores <= 4) return 1;
  return 2;
}

function fail(): void {
  failed = true;
  cancelAnimationFrame(frameId);
  teardownScene();
  emit('fallback');
}

function buildSim(nextTier: TierIndex): boolean {
  if (!pipeline || !scene) return false;
  const prevFade = sim?.globalFade.value ?? 0;
  const prevFormation = sim?.formation.value ?? 0;
  if (sim) {
    sim.dispose();
    sim = null;
  }
  const created = createNebulaSimulation(pipeline.renderer, TIERS[nextTier]);
  if (!created) return false;
  sim = created;
  sim.globalFade.value = prevFade;
  sim.formation.value = prevFormation;
  scene.add(sim.points);
  tier = nextTier;
  cachedTier = nextTier;
  return true;
}

function onPointerMove(ev: PointerEvent): void {
  if (!container.value) return;
  const rect = container.value.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return;
  pointerPx.x = ev.clientX - rect.left;
  pointerPx.y = ev.clientY - rect.top;
  pointerNdc.set((pointerPx.x / rect.width) * 2 - 1, -(pointerPx.y / rect.height) * 2 + 1);
  pointerInside = pointerPx.x >= 0 && pointerPx.y >= 0 && pointerPx.x <= rect.width && pointerPx.y <= rect.height;
}

function onPointerLeaveWindow(): void {
  pointerInside = false;
}

/** 鼠标射线与「过原点、垂直视线」平面的交点 → 世界坐标力场中心 */
function updatePointerForce(): void {
  if (!sim || !camera) return;
  if (!pointerInside || props.dimmed || flyBusy) return;
  camera.getWorldDirection(tmpDir);
  galaxyPlane.setFromNormalAndCoplanarPoint(tmpDir, tmpWorld.set(0, 0, 0));
  raycaster.setFromCamera(pointerNdc, camera);
  const hit = raycaster.ray.intersectPlane(galaxyPlane, tmpWorld);
  if (hit) sim.setPointer(hit);
}

function updateAnchorsAndHover(): void {
  if (!camera || !container.value) return;
  const w = container.value.clientWidth;
  const h = container.value.clientHeight;
  // 星系基本成形后标签才浮现，入场层次与 BlueYard 一致
  const formed = (sim?.formation.value ?? 0) > 0.55;
  const labelsActive = formed && !props.dimmed && !flyBusy;

  let nearestId = -1;
  let nearestKey: GalaxyZoneKey | null = null;
  // 归一化距离（d / 命中半径），< 1 才算命中；重叠时取比值最小者
  let nearestNorm = 1;
  const tanHalfFov = Math.tan(THREE.MathUtils.degToRad(camera.fov * 0.5));

  for (let i = 0; i < CLUSTERS.length; i++) {
    const spec = CLUSTERS[i];
    tmpProject.copy(spec.position).project(camera);
    const sx = (tmpProject.x * 0.5 + 0.5) * w;
    const sy = (-tmpProject.y * 0.5 + 0.5) * h;
    const anchor = anchors[i];
    anchor.x = sx;
    anchor.y = sy;
    anchor.depth = THREE.MathUtils.clamp((tmpProject.z + 1) * 0.5, 0, 1);
    anchor.visible = labelsActive && tmpProject.z < 1 && sx > -60 && sx < w + 60 && sy > -60 && sy < h + 60;

    if (labelsActive && pointerInside && anchor.visible) {
      // 命中半径 = 簇世界半径的屏幕投影，整个可见圆圈都可悬停/点击
      const dist = camera.position.distanceTo(spec.position);
      const pxRadius = (spec.radius * (h * 0.5)) / (dist * tanHalfFov);
      const hitRadius = Math.max(130, pxRadius * 1.05);
      const norm = Math.hypot(pointerPx.x - sx, pointerPx.y - sy) / hitRadius;
      if (norm < nearestNorm) {
        nearestNorm = norm;
        nearestId = spec.id;
        nearestKey = spec.key;
      }
    }
  }

  // 外部（DOM 标签）悬停优先于投影距离判定
  if (externalHover) {
    const spec = clusterByKey(externalHover);
    nearestId = spec.id;
    nearestKey = spec.key;
  }
  if (!labelsActive) {
    nearestId = -1;
    nearestKey = null;
  }

  if (nearestId !== currentHoverId) {
    currentHoverId = nearestId;
    sim?.setHoverCluster(nearestId);
  }
  for (const anchor of anchors) anchor.hovered = anchor.key === nearestKey;
}

function watchFps(nowMs: number): void {
  if (fpsWindowStart === 0) fpsWindowStart = nowMs;
  fpsFrames++;
  const elapsed = nowMs - fpsWindowStart;
  if (elapsed < 1500) return;
  const fps = (fpsFrames * 1000) / elapsed;
  fpsFrames = 0;
  fpsWindowStart = nowMs;
  if (fps >= 40) {
    lowFpsStrikes = 0;
    return;
  }
  lowFpsStrikes++;
  if (lowFpsStrikes < 2) return;
  lowFpsStrikes = 0;
  if (tier > 0) {
    buildSim((tier - 1) as TierIndex);
  } else if (pipeline) {
    // 已是最低档：关胶片颗粒、压低 bloom
    pipeline.filmGrain.enabled = false;
    pipeline.bloom.strength = Math.min(pipeline.bloom.strength, 0.35);
  }
}

function animate(): void {
  frameId = requestAnimationFrame(animate);
  if (document.hidden || !pipeline || !sim || !camera || !director) return;
  const now = performance.now();

  updatePointerForce();
  sim.update(now);
  director.update(now, {
    x: pointerInside && !props.dimmed ? pointerNdc.x : 0,
    y: pointerInside && !props.dimmed ? pointerNdc.y : 0,
  });
  updateAnchorsAndHover();
  glows?.tick(now, currentHoverId, sim.globalFade.value);
  nebulaBg?.layers.forEach(({ group, speed }) => {
    group.rotation.y += speed * 0.6;
  });
  nebulaBg?.tick(now);
  pipeline.composer.render();
  watchFps(now);
}

function onResize(): void {
  if (!container.value || !pipeline || !camera) return;
  resizeRenderPipeline(pipeline, camera, container.value.clientWidth, container.value.clientHeight);
}

function teardownScene(): void {
  sim?.dispose();
  sim = null;
  glows?.dispose();
  glows = null;
  disposeNebulaBackground(nebulaBg);
  nebulaBg = null;
  director?.dispose();
  director = null;
  disposeRenderPipeline(pipeline);
  if (pipeline && container.value?.contains(pipeline.renderer.domElement)) {
    container.value.removeChild(pipeline.renderer.domElement);
  }
  pipeline = null;
  scene = null;
  camera = null;
}

/** 飞入簇心；resolve 后由父级切换 zone */
async function flyToZone(key: GalaxyZoneKey): Promise<void> {
  if (failed || flyBusy || !sim || !director) return;
  flyBusy = true;
  externalHover = null;
  currentHoverId = -1;
  sim.setHoverCluster(-1);
  for (const anchor of anchors) {
    anchor.hovered = false;
    anchor.visible = false;
  }

  const spec = clusterByKey(key);
  // 尾迹方向：粒子相对镜头行进方向逆向流动
  tmpDir.copy(spec.position).sub(camera!.position).normalize();
  sim.warpDir.value.copy(tmpDir).negate();

  gsap.timeline()
    .to(sim.warp, { value: 1, duration: 0.75, ease: 'power2.in', overwrite: 'auto' })
    .to(sim.warp, { value: 0, duration: 0.7, ease: 'power2.out' });
  gsap.to(sim.pointerStrength, { value: 0, duration: 0.3, overwrite: 'auto' });
  // 穿越簇心时整体淡出，给上层分区 UI 让位
  gsap.to(sim.globalFade, { value: 0.3, duration: 0.7, delay: 0.75, ease: 'power1.in', overwrite: 'auto' });

  try {
    await director.flyTo(spec.position);
    awayFromHome = true;
  } finally {
    flyBusy = false;
  }
}

/** DOM 标签悬停同步（触屏/键盘可达性路径） */
function notifyHover(key: GalaxyZoneKey | null): void {
  externalHover = key;
}

function returnToHub(): void {
  if (failed || !sim || !director) return;
  gsap.to(sim.globalFade, { value: 1, duration: 1.0, ease: 'power1.out', overwrite: 'auto' });
  gsap.to(sim.pointerStrength, { value: 1, duration: 0.6, delay: 0.4, overwrite: 'auto' });
  if (awayFromHome) {
    awayFromHome = false;
    void director.flyBack();
  }
}

watch(
  () => props.dimmed,
  (dimmed) => {
    if (failed || !sim) return;
    if (dimmed) {
      gsap.to(sim.globalFade, { value: 0.3, duration: 0.8, ease: 'power1.inOut', overwrite: 'auto' });
      gsap.to(sim.pointerStrength, { value: 0, duration: 0.3, overwrite: 'auto' });
    } else {
      returnToHub();
    }
  },
);

onMounted(() => {
  if (!container.value) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    failed = true;
    emit('fallback');
    return;
  }

  try {
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050818);
    camera = new THREE.PerspectiveCamera(
      50,
      container.value.clientWidth / Math.max(1, container.value.clientHeight),
      0.1,
      800,
    );
    camera.position.set(0, 5, 26);
    camera.lookAt(0, 0.4, 0);
    const lowPower = pickInitialTier() === 0;
    pipeline = createRenderPipeline(container.value, scene, camera, {
      lowPower,
      enableFilmGrain: !lowPower,
    });
    // 数万加色粒子叠加下默认 bloom 会过曝，本场景单独收敛
    pipeline.bloom.strength = lowPower ? 0.4 : 0.65;
    pipeline.bloom.threshold = 0.5;
  } catch {
    teardownScene();
    failed = true;
    emit('fallback');
    return;
  }

  if (!buildSim(pickInitialTier())) {
    teardownScene();
    failed = true;
    emit('fallback');
    return;
  }

  // 旧背景语言移植：簇心辉光「心脏」+ 色带/散景/远星景深层
  glows = buildClusterGlows(scene);
  nebulaBg = buildNebulaBackground(scene, pickInitialTier() === 0);

  director = createCameraDirector(camera);
  const short = hasPlayedIntro;
  hasPlayedIntro = true;
  director.playIntro(short);
  // 入场：粒子从弥散汇聚成星系 + 整体亮度浮现
  gsap.to(sim!.formation, { value: 1, duration: short ? 1.6 : 3.0, ease: 'power2.inOut' });
  gsap.to(sim!.globalFade, {
    value: props.dimmed ? 0.3 : 1,
    duration: short ? 1.0 : 1.8,
    ease: 'power1.out',
  });
  gsap.to(sim!.pointerStrength, { value: props.dimmed ? 0 : 1, duration: 0.8, delay: short ? 0.4 : 1.4 });

  window.addEventListener('resize', onResize);
  window.addEventListener('pointermove', onPointerMove);
  document.documentElement.addEventListener('mouseleave', onPointerLeaveWindow);
  window.addEventListener('blur', onPointerLeaveWindow);
  animate();
});

onBeforeUnmount(() => {
  cancelAnimationFrame(frameId);
  window.removeEventListener('resize', onResize);
  window.removeEventListener('pointermove', onPointerMove);
  document.documentElement.removeEventListener('mouseleave', onPointerLeaveWindow);
  window.removeEventListener('blur', onPointerLeaveWindow);
  teardownScene();
});

defineExpose({ anchors, flyToZone, notifyHover });
</script>

<template>
  <div ref="container" class="absolute inset-0 z-0"></div>
</template>

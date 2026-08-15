<script setup lang="ts">
import gsap from 'gsap';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import {
  createRenderPipeline,
  disposeRenderPipeline,
  resizeRenderPipeline,
  type RenderPipeline,
} from '../../three/create-renderer';
import { disposeObject3D } from '../../three/dispose';
import { buildParticleField, disposeParticleField, type ParticleField } from '../../three/particle-field';
import {
  buildConstellationVisual,
  type ConstellationVisual,
} from '../../three/constellation-particles';
import { buildAstrolabeRing, type AstrolabeRing } from '../../three/astrolabe-ring';
import { buildNebulaBackdrop, type NebulaBackdrop } from '../../three/nebula-backdrop';
import { buildZodiacLineArt, type ZodiacLineArt } from '../../three/zodiac-lineart';
import {
  ZODIAC_CONSTELLATIONS,
  ZODIAC_ELEMENT_META,
  constellationCenter,
  type ZodiacConstellation,
} from '../../three/zodiac-data';
import {
  fetchStudyConstellations,
  fetchStudyRooms,
  type StudyConstellation,
  type StudyRoom,
} from '../../api/study';
import ConstellationInfoCard from './ConstellationInfoCard.vue';
import ZodiacWheelNav from './ZodiacWheelNav.vue';

const props = defineProps<{ active?: boolean; dimmed?: boolean }>();
const emit = defineEmits<{
  (e: 'select-constellation', slug: string, name: string): void;
  (e: 'select-room', room: StudyRoom): void;
  (e: 'depth-change', label: string | null): void;
}>();

const container = ref<HTMLDivElement | null>(null);
const hint = ref('拖动旋转黄道带 · 点击星座进入');
const view = ref<'ring' | 'constellation'>('ring');
const current = ref<ZodiacConstellation | null>(null);
const rooms = ref<StudyRoom[]>([]);

let pipeline: RenderPipeline | null = null;
let scene: THREE.Scene;
let camera: THREE.PerspectiveCamera;
let controls: OrbitControls;
let particleField: ParticleField | null = null;
let astrolabe: AstrolabeRing | null = null;
let nebula: NebulaBackdrop | null = null;
let lineArt: ZodiacLineArt | null = null;
let content: THREE.Group;
let roomLayer: THREE.Group;
let raycaster: THREE.Raycaster;
let frameId = 0;
let pointer = new THREE.Vector2();
let parallax = { x: 0, y: 0 };
let hoveredSlug = '';
let focusedSlug = '';
let myZodiac = '';
let lowPower = false;

const constellationVisuals = new Map<string, ConstellationVisual>();
const roomMeshes: THREE.Group[] = [];
let roomConnections: THREE.LineSegments | null = null;
const worldCenter = new THREE.Vector3();
const hoveredRoom = ref<StudyRoom | null>(null);
const hoveredRoomId = ref('');
const hoverTip = ref('');
const hoverPos = reactive({ x: 0, y: 0 });

const hoveredConstellation = ref<ZodiacConstellation | null>(null);
const wheelHovered = ref('');
const myZodiacRef = ref('');
const constellationStats = ref<Record<string, StudyConstellation>>({});
const cometActive = ref(false);
let cometTimer = 0;

const currentElementMeta = computed(() =>
  current.value ? ZODIAC_ELEMENT_META[current.value.element] : null,
);

const infoCardStyle = computed(() => {
  const el = container.value;
  const w = el?.clientWidth ?? 1200;
  const flip = hoverPos.x > w - 300;
  return {
    left: flip ? `${hoverPos.x - 276}px` : `${hoverPos.x + 18}px`,
    top: `${Math.max(12, hoverPos.y - 60)}px`,
  };
});

// --- 共享星点纹理（模块内只生成一次） ---
let sharedStarTex: THREE.CanvasTexture | null = null;
function getStarTexture(): THREE.CanvasTexture {
  if (sharedStarTex) return sharedStarTex;
  const canvas = document.createElement('canvas');
  canvas.width = 64;
  canvas.height = 64;
  const ctx = canvas.getContext('2d')!;
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(0.2, 'rgba(253,248,231,0.9)');
  g.addColorStop(0.55, 'rgba(212,175,55,0.35)');
  g.addColorStop(1, 'rgba(212,175,55,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 64, 64);
  sharedStarTex = new THREE.CanvasTexture(canvas);
  return sharedStarTex;
}

function buildStarRoom(room: StudyRoom): THREE.Group {
  const group = new THREE.Group();
  const isLarge = room.size === 'large';
  const isFull = room.is_full;
  const coreColor = isFull ? 0x8a744a : isLarge ? 0xf5d76e : 0xf3e5b8;
  const coreSize = isLarge ? 1.05 : 0.76;

  const core = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: getStarTexture(),
      color: coreColor,
      transparent: true,
      opacity: isFull ? 0.6 : 0.98,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  core.scale.set(coreSize, coreSize, 1);
  core.userData = { type: 'room', room };
  group.add(core);

  const rayLength = isLarge ? 0.92 : 0.64;
  const rayPositions = new Float32Array([
    -rayLength, 0, 0, rayLength, 0, 0,
    0, -rayLength, 0, 0, rayLength, 0,
    -rayLength * 0.55, -rayLength * 0.55, 0, rayLength * 0.55, rayLength * 0.55, 0,
    -rayLength * 0.55, rayLength * 0.55, 0, rayLength * 0.55, -rayLength * 0.55, 0,
  ]);
  const raysGeometry = new THREE.BufferGeometry();
  raysGeometry.setAttribute('position', new THREE.BufferAttribute(rayPositions, 3));
  const rays = new THREE.LineSegments(
    raysGeometry,
    new THREE.LineBasicMaterial({
      color: coreColor,
      transparent: true,
      opacity: isFull ? 0.2 : 0.7,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  rays.userData = { skipRaycast: true, starRays: true };
  group.add(rays);

  const glow = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: getStarTexture(),
      color: isFull ? 0x8a744a : 0xd4af37,
      transparent: true,
      opacity: isFull ? 0.4 : 0.55,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  glow.scale.set(isLarge ? 2.2 : 1.55, isLarge ? 2.2 : 1.55, 1);
  glow.userData = { skipRaycast: true, starGlow: true };
  group.add(glow);

  if (isFull) {
    // 满员锁形刻度环：细环 + 放射刻度
    const lockGroup = new THREE.Group();
    const halo = new THREE.Mesh(
      new THREE.RingGeometry(coreSize * 0.56, coreSize * 0.64, 40),
      new THREE.MeshBasicMaterial({ color: 0xd4af37, transparent: true, opacity: 0.4, side: THREE.DoubleSide }),
    );
    lockGroup.add(halo);
    const tickPositions: number[] = [];
    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2;
      tickPositions.push(
        Math.cos(a) * coreSize * 0.66, Math.sin(a) * coreSize * 0.66, 0,
        Math.cos(a) * coreSize * 0.82, Math.sin(a) * coreSize * 0.82, 0,
      );
    }
    const tickGeo = new THREE.BufferGeometry();
    tickGeo.setAttribute('position', new THREE.Float32BufferAttribute(tickPositions, 3));
    lockGroup.add(
      new THREE.LineSegments(
        tickGeo,
        new THREE.LineBasicMaterial({ color: 0xd4af37, transparent: true, opacity: 0.5 }),
      ),
    );
    lockGroup.userData = { skipRaycast: true, lockRing: true };
    group.add(lockGroup);
  }

  const label = makeRoomLabel(`${room.name}\n${room.occupancy}/${room.capacity}`, isLarge ? 2.2 : 1.8);
  label.position.set(0, isLarge ? 1.05 : 0.75, 0);
  label.userData = { skipRaycast: true };
  group.add(label);

  group.userData = { type: 'room', room, pulse: Math.random() * Math.PI * 2, hoverBoost: 0 };
  return group;
}

function makeRoomLabel(text: string, scale = 1.8): THREE.Sprite {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 128;
  const ctx = canvas.getContext('2d')!;
  ctx.clearRect(0, 0, 512, 128);
  ctx.font = '600 28px "Noto Serif SC", sans-serif';
  ctx.fillStyle = 'rgba(243, 229, 184, 0.94)';
  ctx.shadowColor = 'rgba(212, 175, 55, 0.5)';
  ctx.shadowBlur = 8;
  ctx.textAlign = 'center';
  const lines = text.split('\n');
  lines.forEach((line, i) => ctx.fillText(line, 256, 48 + i * 34));
  const tex = new THREE.CanvasTexture(canvas);
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: true });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(scale, scale * 0.25, 1);
  return sprite;
}

function clearRoomMeshes() {
  if (roomConnections) {
    roomLayer.remove(roomConnections);
    roomConnections.geometry.dispose();
    (roomConnections.material as THREE.Material).dispose();
    roomConnections = null;
  }
  roomMeshes.forEach((group) => {
    roomLayer.remove(group);
    group.traverse((child) => {
      if (child instanceof THREE.Mesh || child instanceof THREE.Sprite) {
        child.geometry?.dispose();
        const mat = child.material as THREE.Material | THREE.Material[];
        if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
        else mat?.dispose();
        if (child instanceof THREE.Sprite) {
          const map = (child.material as THREE.SpriteMaterial).map;
          if (map && map !== sharedStarTex) map.dispose();
        }
      }
    });
  });
  roomMeshes.length = 0;
}

function layoutRoomsAroundCenter(center: THREE.Vector3) {
  clearRoomMeshes();
  roomLayer.position.copy(center);
  const constellation = current.value;
  if (!constellation) return;
  const layoutScale = 4.8;
  const localPositions: THREE.Vector3[] = [];

  rooms.value.forEach((room, i) => {
    const source = constellation.stars[i % constellation.stars.length];
    const cycle = Math.floor(i / constellation.stars.length);
    const offset = cycle ? cycle * 0.34 : 0;
    const position = new THREE.Vector3(
      source.x * layoutScale + offset,
      source.y * layoutScale - offset * 0.5,
      cycle * 0.2,
    );
    const star = buildStarRoom(room);
    star.position.copy(position);
    roomLayer.add(star);
    roomMeshes.push(star);
    localPositions.push(position);
  });

  const linePositions: number[] = [];
  constellation.edges.forEach(([from, to]) => {
    const a = localPositions[from];
    const b = localPositions[to];
    if (!a || !b) return;
    linePositions.push(a.x, a.y, a.z, b.x, b.y, b.z);
  });
  if (linePositions.length) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));
    roomConnections = new THREE.LineSegments(
      geometry,
      new THREE.LineBasicMaterial({
        color: 0xd4af37,
        transparent: true,
        opacity: 0.42,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    roomConnections.userData = { constellationConnections: true };
    roomLayer.add(roomConnections);
  }
}

function getConstellationWorldCenter(slug: string): THREE.Vector3 {
  const c = ZODIAC_CONSTELLATIONS.find((x) => x.slug === slug);
  if (!c) return new THREE.Vector3();
  const [cx, cy, cz] = constellationCenter(c);
  content.updateMatrixWorld();
  return new THREE.Vector3(cx, cy, cz).applyMatrix4(content.matrixWorld);
}

function setHover(slug: string, showCard = true) {
  if (hoveredSlug === slug) {
    if (!showCard) hoveredConstellation.value = null;
    return;
  }
  if (hoveredSlug) {
    constellationVisuals.get(hoveredSlug)?.setHighlight(hoveredSlug === myZodiac);
    astrolabe?.setMedallionHighlight(hoveredSlug, false);
  }
  hoveredSlug = slug;
  wheelHovered.value = slug;
  hoveredConstellation.value =
    slug && showCard ? ZODIAC_CONSTELLATIONS.find((c) => c.slug === slug) ?? null : null;
  if (slug) {
    constellationVisuals.get(slug)?.setHighlight(true);
    astrolabe?.setMedallionHighlight(slug, true);
  }
  if (view.value === 'ring') {
    lineArt?.setActive(slug || null);
    astrolabe?.setBeam(slug || null);
  }
}

function triggerComet() {
  cometActive.value = false;
  window.clearTimeout(cometTimer);
  requestAnimationFrame(() => {
    cometActive.value = true;
    cometTimer = window.setTimeout(() => {
      cometActive.value = false;
    }, 1400);
  });
}

async function refreshStats() {
  try {
    const items = await fetchStudyConstellations();
    const map: Record<string, StudyConstellation> = {};
    items.forEach((item) => {
      map[item.slug] = item;
    });
    constellationStats.value = map;
  } catch {
    /* 静默失败：信息卡仅少显示人数 */
  }
}

/** 轮盘点击：相机对准星座；再次点击同一扇区进入 */
function focusConstellation(slug: string) {
  if (view.value !== 'ring') return;
  if (focusedSlug === slug) {
    triggerComet();
    void enterConstellation(slug);
    return;
  }
  focusedSlug = slug;
  setHover(slug);
  const center = getConstellationWorldCenter(slug);
  const dir = new THREE.Vector3(center.x, 0, center.z).normalize();
  gsap.to(camera.position, {
    x: dir.x * 30,
    y: 9,
    z: dir.z * 30,
    duration: 1.2,
    ease: 'power3.inOut',
  });
  gsap.to(controls.target, { x: 0, y: 0, z: 0, duration: 1.2, ease: 'power3.inOut' });
}

async function enterConstellation(slug: string) {
  const c = ZODIAC_CONSTELLATIONS.find((x) => x.slug === slug);
  if (!c) return;
  current.value = c;
  view.value = 'constellation';
  focusedSlug = '';
  hint.value = '点击星星或右侧列表进入自习室';
  emit('depth-change', '返回黄道十二宫');
  emit('select-constellation', c.slug, c.name);
  setHover('');
  nebula?.setElementTint(c.element);
  astrolabe?.setBeam(null);
  lineArt?.setActive(null);
  if (lineArt) lineArt.root.visible = false;

  constellationVisuals.forEach((v, key) => {
    v.root.visible = key === slug;
  });

  const center = getConstellationWorldCenter(slug);
  worldCenter.copy(center);

  gsap.to(camera.position, {
    x: center.x * 0.5,
    y: center.y + 4.5,
    z: center.z * 0.5 + 9,
    duration: 1.4,
    ease: 'power3.inOut',
  });

  // 轻微的相机翻滚角 (Roll) 增加沉浸感
  gsap.to(camera.up, {
    x: 0.1,
    y: 0.95,
    z: 0.1,
    duration: 1.4,
    ease: 'power2.inOut',
  });

  gsap.to(controls.target, {
    x: center.x,
    y: center.y,
    z: center.z,
    duration: 1.4,
    ease: 'power3.inOut',
    onComplete: () => {
      const centroid = new THREE.Vector3();
      if (roomMeshes.length) {
        roomMeshes.forEach((m) => centroid.add(m.getWorldPosition(new THREE.Vector3())));
        centroid.divideScalar(roomMeshes.length);
        controls.target.copy(centroid);
      }
    },
  });

  rooms.value = await fetchStudyRooms(slug);
  layoutRoomsAroundCenter(center);
}

function backToRing() {
  view.value = 'ring';
  emit('depth-change', null);
  current.value = null;
  focusedSlug = '';
  clearRoomMeshes();
  roomLayer.position.set(0, 0, 0);
  nebula?.setElementTint(null);
  constellationVisuals.forEach((v) => {
    v.root.visible = true;
  });
  if (lineArt) lineArt.root.visible = true;
  if (myZodiac) constellationVisuals.get(myZodiac)?.setHighlight(true);
  hint.value = '拖动旋转黄道带 · 点击星座进入';
  void refreshStats();

  gsap.to(camera.position, { x: 0, y: 10, z: 28, duration: 1.2, ease: 'power3.inOut' });
  gsap.to(camera.up, { x: 0, y: 1, z: 0, duration: 1.2, ease: 'power2.inOut' });
  gsap.to(controls.target, { x: 0, y: 0, z: 0, duration: 1.2, ease: 'power3.inOut' });
}

function findRoomFromObject(obj: THREE.Object3D | null): StudyRoom | null {
  while (obj) {
    if (obj.userData?.type === 'room' && obj.userData.room) {
      return obj.userData.room as StudyRoom;
    }
    obj = obj.parent;
  }
  return null;
}

function setRoomHoverById(roomId: string) {
  hoveredRoomId.value = roomId;
  roomMeshes.forEach((group) => {
    const room = group.userData.room as StudyRoom | undefined;
    group.userData.hoverBoost = room && room.id === roomId ? 0.22 : 0;
  });
}

function selectRoomFromPanel(room: StudyRoom) {
  if (room.is_full) return;
  emit('select-room', room);
}

function onPointerMove(ev: PointerEvent) {
  if (props.dimmed || !container.value) return;
  const rect = container.value.getBoundingClientRect();
  pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
  parallax.x = pointer.x * 0.35;
  parallax.y = pointer.y * 0.25;
  hoverPos.x = ev.clientX - rect.left;
  hoverPos.y = ev.clientY - rect.top;

  if (!pipeline) return;
  raycaster.setFromCamera(pointer, camera);

  if (view.value === 'constellation') {
    const cores = roomMeshes.map((g) => g.children[0]).filter(Boolean);
    const hits = raycaster.intersectObjects(cores, false);
    const room = hits.length ? findRoomFromObject(hits[0].object) : null;
    hoveredRoom.value = room;
    setRoomHoverById(room?.id ?? '');
    hoverTip.value = room?.is_full ? '自习室已满，请等待' : room ? `点击进入 ${room.name}` : '';
    if (container.value) {
      container.value.style.cursor = room ? (room.is_full ? 'not-allowed' : 'pointer') : 'default';
    }
    return;
  }

  const objs: THREE.Object3D[] = [];
  content.traverse((o) => {
    if (o.userData?.type === 'constellation') objs.push(o);
  });
  const hits = raycaster.intersectObjects(objs, true);
  let slug = '';
  for (const hit of hits) {
    let obj: THREE.Object3D | null = hit.object;
    while (obj) {
      if (obj.userData?.slug) {
        slug = obj.userData.slug as string;
        break;
      }
      obj = obj.parent;
    }
    if (slug) break;
  }
  setHover(slug);
  if (container.value) {
    container.value.style.cursor = slug ? 'pointer' : 'default';
  }
  hoveredRoom.value = null;
  hoverTip.value = '';
}

function onClick() {
  if (props.dimmed || !pipeline) return;
  raycaster.setFromCamera(pointer, camera);

  if (view.value === 'constellation') {
    const cores = roomMeshes.map((g) => g.children[0]).filter(Boolean);
    const hits = raycaster.intersectObjects(cores, false);
    if (!hits.length) return;
    const room = findRoomFromObject(hits[0].object);
    if (!room) return;
    if (room.is_full) {
      hoverTip.value = '自习室已满，请等待';
      return;
    }
    emit('select-room', room);
    return;
  }

  const objs: THREE.Object3D[] = [];
  content.traverse((o) => {
    if (o.userData?.type === 'constellation') objs.push(o);
  });
  const hits = raycaster.intersectObjects(objs, true);
  for (const hit of hits) {
    let obj: THREE.Object3D | null = hit.object;
    while (obj) {
      if (obj.userData?.type === 'constellation') {
        triggerComet();
        void enterConstellation(obj.userData.slug);
        return;
      }
      obj = obj.parent;
    }
  }
}

function animate() {
  frameId = requestAnimationFrame(animate);
  if (!pipeline) return;
  if (!props.active && !props.dimmed) return;
  const now = performance.now();
  if (view.value === 'ring') {
    content.rotation.y += props.dimmed ? 0.00018 : 0.0006;
  } else if (view.value === 'constellation') {
    if (roomConnections) {
      (roomConnections.material as THREE.LineBasicMaterial).opacity = 0.32 + Math.sin(now * 0.0012) * 0.1;
    }
    roomMeshes.forEach((group) => {
      const pulse = group.userData.pulse as number;
      group.userData.pulse = pulse + 0.03;
      const twinkle = (Math.sin(pulse) + 1) * 0.5;
      const boost = (group.userData.hoverBoost as number) || 0;
      const scale = 1 + boost + twinkle * (group.userData.room?.is_full ? 0.035 : 0.07);
      group.scale.setScalar(scale);
      group.children.forEach((child) => {
        if (child instanceof THREE.Sprite) {
          child.quaternion.copy(camera.quaternion);
          if (child.userData.starGlow) {
            (child.material as THREE.SpriteMaterial).opacity = 0.34 + boost + twinkle * 0.36;
          }
        }
        if (child instanceof THREE.LineSegments && child.userData.starRays) {
          child.rotation.z -= 0.0015;
          (child.material as THREE.LineBasicMaterial).opacity = 0.42 + twinkle * 0.38;
        }
        if (child instanceof THREE.Group && child.userData.lockRing) {
          child.quaternion.copy(camera.quaternion);
          child.rotation.z += 0.004;
        }
      });
    });
  }
  constellationVisuals.forEach((v) => v.tick(now));
  astrolabe?.tick(now);
  nebula?.tick(now);
  lineArt?.tick(now);
  particleField?.tick(now, parallax);
  controls.update();
  pipeline.composer.render();
}

function onResize() {
  if (!container.value || !pipeline) return;
  const w = container.value.clientWidth;
  const h = container.value.clientHeight;
  if (w <= 0 || h <= 0) return;
  resizeRenderPipeline(pipeline, camera, w, h);
}

function reactivate() {
  onResize();
}

defineExpose({ backToRing, reactivate, view, current });

function playEntranceAnimation() {
  camera.position.set(0, 42, 6);
  gsap.to(camera.position, { x: 0, y: 10, z: 28, duration: 2.2, ease: 'power3.out' });

  const ordered = [...constellationVisuals.values()];
  ordered.forEach((visual) => visual.setRevealFactor(0));
  ordered.forEach((visual, i) => {
    const proxy = { f: 0 };
    gsap.to(proxy, {
      f: 1,
      duration: 0.9,
      delay: 0.5 + i * 0.08,
      ease: 'power2.out',
      onUpdate: () => visual.setRevealFactor(proxy.f),
      onComplete: () => {
        if (visual.slug === myZodiac) visual.setHighlight(true);
      },
    });
  });
}

onMounted(() => {
  if (!container.value) return;
  myZodiac = localStorage.getItem('sparkorbit_zodiac') || '';
  myZodiacRef.value = myZodiac;
  lowPower = window.devicePixelRatio > 1.5 || container.value.clientWidth < 900;

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x040820);
  scene.fog = new THREE.FogExp2(0x040820, 0.008);
  const w = Math.max(container.value.clientWidth, 1);
  const h = Math.max(container.value.clientHeight, 1);
  camera = new THREE.PerspectiveCamera(55, w / h, 0.1, 260);
  camera.position.set(0, 10, 28);
  pipeline = createRenderPipeline(container.value, scene, camera, { lowPower, bloomThreshold: 0.42 });
  controls = new OrbitControls(camera, pipeline.renderer.domElement);
  controls.enableDamping = true;
  controls.minDistance = 6;
  controls.maxDistance = 50;
  controls.enablePan = false;
  raycaster = new THREE.Raycaster();
  scene.add(new THREE.AmbientLight(0x8a7a4a, 0.5));
  scene.add(new THREE.PointLight(0xd4af37, 1.1, 90));

  particleField = buildParticleField(scene, lowPower);
  nebula = buildNebulaBackdrop(scene, lowPower);

  content = new THREE.Group();
  roomLayer = new THREE.Group();
  scene.add(content);
  scene.add(roomLayer);

  astrolabe = buildAstrolabeRing(lowPower);
  content.add(astrolabe.root);

  lineArt = buildZodiacLineArt(lowPower);
  content.add(lineArt.root);

  ZODIAC_CONSTELLATIONS.forEach((c) => {
    const visual = buildConstellationVisual(c, lowPower);
    constellationVisuals.set(c.slug, visual);
    content.add(visual.root);
  });

  pipeline.renderer.domElement.addEventListener('pointermove', onPointerMove);
  pipeline.renderer.domElement.addEventListener('click', onClick);
  window.addEventListener('resize', onResize);

  playEntranceAnimation();
  void refreshStats();
  animate();
});

watch(
  () => props.active,
  (on) => {
    if (on) void nextTick(reactivate);
  },
);

watch(
  () => props.dimmed,
  (dim) => {
    if (controls) controls.enabled = !dim;
    if (dim) {
      setHover('');
      hoverTip.value = '';
      hoveredRoom.value = null;
      setRoomHoverById('');
      if (container.value) container.value.style.cursor = 'default';
    } else if (view.value === 'constellation' && current.value) {
      // 从自习室退回：刷新房间占用并重排星点
      void fetchStudyRooms(current.value.slug).then((list) => {
        rooms.value = list;
        layoutRoomsAroundCenter(worldCenter);
      });
    }
  },
);

onBeforeUnmount(() => {
  cancelAnimationFrame(frameId);
  window.clearTimeout(cometTimer);
  window.removeEventListener('resize', onResize);
  pipeline?.renderer.domElement.removeEventListener('pointermove', onPointerMove);
  pipeline?.renderer.domElement.removeEventListener('click', onClick);
  clearRoomMeshes();
  constellationVisuals.forEach((v) => v.dispose());
  constellationVisuals.clear();
  astrolabe?.dispose();
  astrolabe = null;
  nebula?.dispose();
  nebula = null;
  lineArt?.dispose();
  lineArt = null;
  disposeObject3D(content);
  disposeParticleField(particleField);
  sharedStarTex?.dispose();
  sharedStarTex = null;
  controls?.dispose();
  disposeRenderPipeline(pipeline);
  pipeline = null;
});
</script>

<template>
  <div class="absolute inset-0 overflow-hidden">
    <div ref="container" class="h-full w-full"></div>

    <!-- 彗星式转场 -->
    <div v-if="cometActive" class="comet-transition"></div>

    <template v-if="!dimmed">
      <!-- 星座悬停信息卡 -->
      <ConstellationInfoCard
        v-if="view === 'ring' && hoveredConstellation"
        class="absolute z-20"
        :style="infoCardStyle"
        :constellation="hoveredConstellation"
        :occupancy="constellationStats[hoveredConstellation.slug]?.total_occupancy"
        :room-count="constellationStats[hoveredConstellation.slug]?.room_count"
        :is-mine="hoveredConstellation.slug === myZodiacRef"
      />

      <!-- 房间悬停提示 -->
      <div
        v-if="hoverTip"
        class="pointer-events-none absolute z-20 rounded-xl border border-astro-gold/30 bg-black/70 px-3 py-2 text-xs text-astro-cream backdrop-blur-md"
        :style="{ left: `${hoverPos.x + 12}px`, top: `${hoverPos.y - 28}px` }"
      >
        {{ hoverTip }}
      </div>

      <!-- 面包屑（星座视图） -->
      <div
        v-if="view === 'constellation' && current"
        class="absolute left-1/2 top-20 z-20 flex -translate-x-1/2 items-center gap-2 rounded-full border border-astro-gold/25 bg-black/50 px-4 py-1.5 text-xs backdrop-blur-md"
      >
        <button class="text-astro-dusk transition-colors hover:text-astro-bright" @click="backToRing">
          黄道十二宫
        </button>
        <span class="text-astro-gold/40">/</span>
        <span class="font-serif-astro text-astro-cream">{{ current.symbol }} {{ current.name }}</span>
        <span
          v-if="currentElementMeta"
          class="ml-1 rounded-full border px-1.5 py-0.5 text-[10px]"
          :style="{ borderColor: `${currentElementMeta.css}55`, color: currentElementMeta.css }"
        >
          {{ currentElementMeta.label }}
        </span>
      </div>

      <!-- 星座内房间列表面板 -->
      <div
        v-if="view === 'constellation' && rooms.length"
        class="glass-gold absolute right-4 top-1/2 z-20 w-60 -translate-y-1/2 rounded-2xl p-4"
      >
        <p class="mb-3 font-mono-tech text-[10px] uppercase tracking-[0.3em] text-astro-dusk">
          {{ current?.name }} · 自习室
        </p>
        <div class="max-h-[52vh] space-y-2 overflow-y-auto pr-1">
          <button
            v-for="room in rooms"
            :key="room.id"
            class="block w-full rounded-xl border p-3 text-left transition-all"
            :class="[
              room.is_full
                ? 'cursor-not-allowed border-white/5 opacity-45'
                : 'cursor-pointer border-astro-gold/15 hover:border-astro-bright/50 hover:bg-astro-gold/10',
              hoveredRoomId === room.id && !room.is_full ? 'border-astro-bright/60 bg-astro-gold/12' : '',
            ]"
            :disabled="room.is_full"
            @pointerenter="setRoomHoverById(room.id)"
            @pointerleave="setRoomHoverById('')"
            @click="selectRoomFromPanel(room)"
          >
            <div class="flex items-center justify-between">
              <span class="font-serif-astro text-sm text-astro-cream">{{ room.name }}</span>
              <span
                class="rounded-full border px-1.5 py-0.5 text-[10px]"
                :class="room.size === 'large' ? 'border-astro-bright/45 text-astro-bright' : 'border-astro-gold/30 text-astro-cream/70'"
              >
                {{ room.size === 'large' ? '大' : '小' }}
              </span>
            </div>
            <div class="mt-2 flex items-center gap-2">
              <div class="h-1 flex-1 overflow-hidden rounded-full bg-white/8">
                <div
                  class="h-full rounded-full transition-all"
                  :class="room.is_full ? 'bg-astro-dusk' : 'bg-gradient-to-r from-astro-gold to-astro-bright'"
                  :style="{ width: `${Math.min(100, (room.occupancy / room.capacity) * 100)}%` }"
                ></div>
              </div>
              <span class="font-mono-tech text-[10px] text-astro-cream/70">
                {{ room.is_full ? '满' : `${room.occupancy}/${room.capacity}` }}
              </span>
            </div>
          </button>
        </div>
      </div>

      <!-- 底部：提示 + 黄道轮盘导航 -->
      <div class="pointer-events-none absolute bottom-4 left-1/2 z-20 flex -translate-x-1/2 flex-col items-center gap-2">
        <p class="rounded-full border border-astro-gold/20 bg-black/45 px-4 py-1.5 text-[11px] text-astro-cream/85 backdrop-blur-md">
          {{ hint }}
        </p>
        <ZodiacWheelNav
          v-if="view === 'ring'"
          class="pointer-events-auto"
          :hovered="wheelHovered"
          :mine="myZodiacRef"
          @hover="(slug) => setHover(slug ?? '', false)"
          @select="focusConstellation"
        />
      </div>
    </template>
  </div>
</template>

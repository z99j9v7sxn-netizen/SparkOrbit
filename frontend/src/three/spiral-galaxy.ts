import * as THREE from 'three';
import gsap from 'gsap';
import type { Galaxy } from '../api/orbit';
import { planetNoiseCommon } from './shaders/planet-noise.glsl';
import { galaxyDiskRadius } from './universe-layout';

/**
 * 宇宙层的「科目星系」：点云旋臂 + 盘面 FBM 气体层 + 核球辉光（参考 galaxy-explorer 的分层做法）。
 * 形态（旋臂数 / 倾角 / 旋向）由 slug 哈希决定，稳定可复现；
 * 差速旋转在 shader 内按半径计算（内快外慢），点云与气体层共享同一相位保持旋臂对齐；
 * 学习进度（lit_count / planet_count）映射为核心亮度与 billboard 进度亮弧。
 */
export interface SpiralGalaxyNode {
  root: THREE.Group;
  pickMesh: THREE.Mesh;
  hoverRing: THREE.Mesh;
  /** CSS2D 标签的挂点（盘面上方） */
  labelAnchor: THREE.Object3D;
  tick: (timeMs: number) => void;
  setHover: (on: boolean) => void;
}

export interface SpiralGalaxyOptions {
  /** 全局预算下发的基准点数（planet_count 再做 ±25% 密度加权）；缺省用独立公式 */
  pointBudget?: number;
}

function hashString(str: string): number {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (h << 5) - h + str.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h);
}

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a += 0x6d2b79f5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const spiralVertex = /* glsl */ `
attribute float aScale;
attribute vec3 aColor;
attribute float aPhase;
uniform float uSize;
uniform float uPixelRatio;
uniform float uHover;
uniform float uPhase;
uniform float uRadius;
varying vec3 vColor;
varying float vPhase;
void main() {
  // 差速旋转：角速度随半径衰减（内快外慢），旋臂随时间自然缠绕
  float r = length(position.xz);
  float w = min(1.0 / (0.32 + pow(r / uRadius, 0.85) * 1.55), 2.6);
  float ang = uPhase * w;
  float c = cos(ang);
  float s = sin(ang);
  vec3 p = vec3(position.x * c - position.z * s, position.y, position.x * s + position.z * c);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  // 宇宙层相机距离较远，衰减常数放大 + 像素下限，避免点被压到 1px 以下消失
  gl_PointSize = max(
    uSize * aScale * uPixelRatio * (1.0 + uHover * 0.3) * (48.0 / max(-mv.z, 0.1)),
    uPixelRatio * 1.3
  );
  vColor = aColor;
  vPhase = aPhase;
}
`;

const spiralFragment = /* glsl */ `
uniform float uOpacity;
uniform float uHover;
uniform float uTime;
uniform float uTwinkle;
varying vec3 vColor;
varying float vPhase;
void main() {
  float d = distance(gl_PointCoord, vec2(0.5));
  float a = smoothstep(0.5, 0.0, d);
  a = pow(a, 2.4);
  float tw = mix(1.0, 0.82 + 0.18 * sin(uTime * 1.8 + vPhase * 7.0), uTwinkle);
  a *= uOpacity * tw * (1.0 + uHover * 0.35);
  gl_FragColor = vec4(vColor, a);
}
`;

const gasVertex = /* glsl */ `
varying vec2 vPos;
void main() {
  vPos = position.xy;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

/**
 * 盘面气体层：FBM 湍流 × 旋臂调制 × 径向衰减。
 * 旋臂表达式与点云一致（theta = branchAngle + r·spinCoef），
 * 差速旋转通过对采样坐标做反向旋转实现，与点云共享 uPhase 保持对齐。
 */
const gasFragment = /* glsl */ `
uniform float uPhase;
uniform float uHover;
uniform float uIntensity;
uniform vec3 uInner;
uniform vec3 uOuter;
uniform float uBranches;
uniform float uSpinCoef;
uniform float uRadius;
uniform float uSeed;
varying vec2 vPos;

${planetNoiseCommon}

void main() {
  // 平面局部 (x, y) 经 rotation.x = -PI/2 映射到世界 (x, -z)
  vec2 P = vec2(vPos.x, -vPos.y) / uRadius;
  float r = length(P);
  if (r > 1.0) discard;

  // 与点云同款差速角速度，反向旋转采样坐标 = 图案正向旋转
  float w = min(1.0 / (0.32 + pow(r, 0.85) * 1.55), 2.6);
  float ang = uPhase * w;
  float c = cos(ang);
  float s = sin(ang);
  vec2 q = vec2(P.x * c + P.y * s, -P.x * s + P.y * c);

  float theta = atan(q.y, q.x);
  float arm = 0.5 + 0.5 * cos(uBranches * (theta - r * uSpinCoef));
  arm = pow(arm, 2.1);

  float turb = fbm2(vec3(q * 3.2, uSeed)) * 0.5 + 0.5;
  float falloff = smoothstep(1.0, 0.4, r) * smoothstep(0.04, 0.2, r);
  float density = arm * falloff * (0.4 + 0.6 * turb);

  vec3 col = mix(uInner, uOuter, smoothstep(0.08, 0.9, r));
  float a = density * uIntensity * (1.0 + uHover * 0.55);
  gl_FragColor = vec4(col, a);
}
`;

function createCoreSprite(color: THREE.Color, progress: number, size: number, variant: 'inner' | 'outer'): THREE.Sprite {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext('2d')!;
  const grad = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  const bright = color.clone().lerp(new THREE.Color(0xffffff), 0.75);
  if (variant === 'inner') {
    grad.addColorStop(0, `rgba(255,255,255,${0.85 + progress * 0.15})`);
    grad.addColorStop(0.22, `rgba(${Math.floor(bright.r * 255)},${Math.floor(bright.g * 255)},${Math.floor(bright.b * 255)},${0.5 + progress * 0.35})`);
    grad.addColorStop(0.6, `rgba(${Math.floor(color.r * 255)},${Math.floor(color.g * 255)},${Math.floor(color.b * 255)},0.16)`);
    grad.addColorStop(1, 'transparent');
  } else {
    grad.addColorStop(0, `rgba(${Math.floor(bright.r * 255)},${Math.floor(bright.g * 255)},${Math.floor(bright.b * 255)},${0.22 + progress * 0.1})`);
    grad.addColorStop(0.5, `rgba(${Math.floor(color.r * 255)},${Math.floor(color.g * 255)},${Math.floor(color.b * 255)},0.08)`);
    grad.addColorStop(1, 'transparent');
  }
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 128, 128);

  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: new THREE.CanvasTexture(canvas),
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  const s = variant === 'inner' ? size * (1.15 + progress * 0.45) : size * 2.9;
  sprite.scale.set(s, s, 1);
  return sprite;
}

/** 进度亮弧（billboard）：只画从 12 点方向顺时针点亮 progress 比例的亮弧，底环交给 hoverRing */
function createProgressArcSprite(color: THREE.Color, progress: number, radius: number): THREE.Sprite | null {
  if (progress <= 0.01) return null;
  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const cx = size / 2;
  const r = size * 0.44;

  const bright = color.clone().lerp(new THREE.Color(0xffe9a8), 0.55);
  ctx.lineWidth = size * 0.024;
  ctx.lineCap = 'round';
  ctx.strokeStyle = `rgba(${Math.floor(bright.r * 255)},${Math.floor(bright.g * 255)},${Math.floor(bright.b * 255)},0.8)`;
  ctx.shadowColor = ctx.strokeStyle;
  ctx.shadowBlur = size * 0.03;
  ctx.beginPath();
  ctx.arc(cx, cx, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * Math.min(progress, 1));
  ctx.stroke();

  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: new THREE.CanvasTexture(canvas),
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  const s = radius * 2.35;
  sprite.scale.set(s, s, 1);
  return sprite;
}

export function createSpiralGalaxy(
  galaxy: Galaxy,
  position: THREE.Vector3,
  size: number,
  lowPower = false,
  opts: SpiralGalaxyOptions = {},
): SpiralGalaxyNode {
  const root = new THREE.Group();
  root.position.copy(position);

  const hash = hashString(galaxy.slug);
  const rng = mulberry32(hash);
  const color = new THREE.Color(galaxy.color);
  const progress = galaxy.planet_count > 0 ? galaxy.lit_count / galaxy.planet_count : 0;

  // 盘体（点云 + 气体 + 核心）单独一组；倾角挂在 root 上，旋转全部在 shader 内完成
  const disk = new THREE.Group();
  root.add(disk);
  root.rotation.x = (rng() - 0.5) * 0.85;
  root.rotation.z = (rng() - 0.5) * 0.5;

  const branches = 3 + (hash % 3); // 3~5 条旋臂
  const spinSign = hash % 2 === 0 ? 1 : -1;
  const spin = spinSign * (0.9 + rng() * 0.5);
  const spinCoef = spin * Math.PI * 1.8;
  const diskRadius = galaxyDiskRadius(size);

  // 点数：优先用全局预算（planet_count 做 ±25% 密度加权），无预算时退回独立公式
  let count: number;
  if (opts.pointBudget) {
    const weight = 0.75 + Math.min(galaxy.planet_count / 24, 0.5);
    count = Math.max(400, Math.floor(opts.pointBudget * weight));
  } else {
    const baseCount = Math.min(2600, 1000 + galaxy.planet_count * 130);
    count = lowPower ? Math.floor(baseCount * 0.5) : baseCount;
  }

  const bulgeCount = Math.floor(count * 0.15);
  const armCount = count - bulgeCount;

  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const scales = new Float32Array(count);
  const phases = new Float32Array(count);

  const inside = color.clone().lerp(new THREE.Color(0xfff3d6), 0.55);
  const outside = color.clone().lerp(new THREE.Color(0x1a2550), 0.62);
  const bulgeColor = color.clone().lerp(new THREE.Color(0xfff0d8), 0.72);
  const tmp = new THREE.Color();

  for (let i = 0; i < armCount; i++) {
    const radius = Math.pow(rng(), 0.65) * diskRadius;
    const branchAngle = ((i % branches) / branches) * Math.PI * 2;
    const spinAngle = (radius / diskRadius) * spinCoef;

    const randomness = 0.28;
    const power = 2.6;
    const rx = Math.pow(rng(), power) * (rng() < 0.5 ? 1 : -1) * randomness * radius;
    const ry = Math.pow(rng(), power) * (rng() < 0.5 ? 1 : -1) * randomness * radius * 0.35;
    const rz = Math.pow(rng(), power) * (rng() < 0.5 ? 1 : -1) * randomness * radius;

    positions[i * 3] = Math.cos(branchAngle + spinAngle) * radius + rx;
    positions[i * 3 + 1] = ry;
    positions[i * 3 + 2] = Math.sin(branchAngle + spinAngle) * radius + rz;

    tmp.copy(inside).lerp(outside, radius / diskRadius);
    colors[i * 3] = tmp.r;
    colors[i * 3 + 1] = tmp.g;
    colors[i * 3 + 2] = tmp.b;
    scales[i] = 0.6 + rng() * 1.4;
    phases[i] = rng() * Math.PI * 2;
  }

  // 中心核球：高斯分布的暖白亮团，撑起星系「心脏」的体积感
  const bulgeR = diskRadius * 0.24;
  const gauss = () => (rng() + rng() + rng()) / 1.5 - 1;
  for (let i = armCount; i < count; i++) {
    positions[i * 3] = gauss() * bulgeR;
    positions[i * 3 + 1] = gauss() * bulgeR * 0.6;
    positions[i * 3 + 2] = gauss() * bulgeR;

    tmp.copy(bulgeColor).lerp(new THREE.Color(0xffffff), rng() * 0.35);
    colors[i * 3] = tmp.r;
    colors[i * 3 + 1] = tmp.g;
    colors[i * 3 + 2] = tmp.b;
    scales[i] = 0.8 + rng() * 1.5;
    phases[i] = rng() * Math.PI * 2;
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('aColor', new THREE.BufferAttribute(colors, 3));
  geo.setAttribute('aScale', new THREE.BufferAttribute(scales, 1));
  geo.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));

  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uSize: { value: lowPower ? 1.9 : 2.4 },
      uPixelRatio: { value: Math.min(typeof window !== 'undefined' ? window.devicePixelRatio : 1, 2) },
      uHover: { value: 0 },
      uOpacity: { value: 0.42 + progress * 0.3 },
      uPhase: { value: 0 },
      uRadius: { value: diskRadius },
      uTime: { value: 0 },
      uTwinkle: { value: lowPower ? 0 : 1 },
    },
    vertexShader: spiralVertex,
    fragmentShader: spiralFragment,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const points = new THREE.Points(geo, mat);
  disk.add(points);

  // 盘面气体层：给稀疏点云补上「肉」，宇宙层远距离下星系仍是实体
  const gasMat = new THREE.ShaderMaterial({
    defines: { FBM_OCTAVES: lowPower ? 2 : 3 },
    uniforms: {
      uPhase: { value: 0 },
      uHover: { value: 0 },
      uIntensity: { value: 0.34 + progress * 0.1 },
      uInner: { value: color.clone().lerp(new THREE.Color(0xffe8c8), 0.5) },
      uOuter: { value: color.clone().lerp(new THREE.Color(0x27356e), 0.45) },
      uBranches: { value: branches },
      uSpinCoef: { value: spinCoef },
      uRadius: { value: diskRadius },
      uSeed: { value: (hash % 97) * 0.37 },
    },
    vertexShader: gasVertex,
    fragmentShader: gasFragment,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
  });
  const gas = new THREE.Mesh(new THREE.CircleGeometry(diskRadius * 1.02, 48), gasMat);
  gas.rotation.x = -Math.PI / 2;
  disk.add(gas);

  // 双层核球辉光：大而淡的外晕 + 小而亮的内核，tick 中缓慢「呼吸」
  const coreOuter = createCoreSprite(color, progress, size, 'outer');
  const coreInner = createCoreSprite(color, progress, size, 'inner');
  disk.add(coreOuter);
  disk.add(coreInner);
  const coreInnerBase = coreInner.scale.x;
  const coreOuterBase = coreOuter.scale.x;

  const progressArc = createProgressArcSprite(color, progress, diskRadius);
  if (progressArc) root.add(progressArc);

  // 不可见拾取球：覆盖整个盘面便于点击
  const pickMesh = new THREE.Mesh(
    new THREE.SphereGeometry(diskRadius * 0.82, 16, 16),
    new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false, colorWrite: false }),
  );
  root.add(pickMesh);

  const hoverRing = new THREE.Mesh(
    new THREE.RingGeometry(diskRadius * 1.12, diskRadius * 1.18, 72),
    new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0,
      side: THREE.DoubleSide,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  hoverRing.rotation.x = -Math.PI / 2;
  root.add(hoverRing);

  const labelAnchor = new THREE.Object3D();
  labelAnchor.position.set(0, diskRadius * 0.72 + 1.2, 0);
  root.add(labelAnchor);

  const hoverState = { boost: 0 };
  let hoverTween: gsap.core.Tween | null = null;
  // 基准角速度（rad/s，外缘参考值）；shader 内随半径放大至最高 2.6 倍
  const baseSpinSpeed = spinSign * (0.045 + rng() * 0.03);
  const breathePhase = rng() * Math.PI * 2;
  let phase = 0;
  let lastTick = 0;

  pickMesh.userData = {
    type: 'galaxy',
    slug: galaxy.slug,
    name: galaxy.name,
    sub: `${galaxy.lit_count}/${galaxy.planet_count} 已点亮`,
    hoverRing,
    onHover: (on: boolean) => setHover(on),
  };

  function setHover(on: boolean): void {
    hoverTween?.kill();
    hoverTween = gsap.to(hoverState, { boost: on ? 1 : 0, duration: 0.5, ease: 'power2.out' });
    gsap.to(mat.uniforms.uHover, { value: on ? 1 : 0, duration: 0.45, ease: 'power2.out', overwrite: 'auto' });
    gsap.to(gasMat.uniforms.uHover, { value: on ? 1 : 0, duration: 0.45, ease: 'power2.out', overwrite: 'auto' });
  }

  function tick(timeMs: number): void {
    const dt = lastTick > 0 ? Math.min(timeMs - lastTick, 100) : 16.6;
    lastTick = timeMs;
    phase += dt * 0.001 * baseSpinSpeed * (1 + hoverState.boost * 2.2);
    mat.uniforms.uPhase.value = phase;
    mat.uniforms.uTime.value = timeMs * 0.001;
    gasMat.uniforms.uPhase.value = phase;

    // 核球呼吸：内核快、外晕慢，幅度很小只求「活」
    const t = timeMs * 0.001;
    const sInner = coreInnerBase * (1 + Math.sin(t * 0.9 + breathePhase) * 0.045);
    const sOuter = coreOuterBase * (1 + Math.sin(t * 0.5 + breathePhase + 1.3) * 0.03);
    coreInner.scale.set(sInner, sInner, 1);
    coreOuter.scale.set(sOuter, sOuter, 1);
  }

  return { root, pickMesh, hoverRing, labelAnchor, tick, setHover };
}

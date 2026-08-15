import * as THREE from 'three';

/**
 * 远景星系群（deep-field）：程序化 canvas 图集（椭圆 / 侧向盘 / 正视螺旋 / 不规则四种），
 * 单个 THREE.Points + 图集 uv 偏移 attribute，一次 draw 画出散布远球壳的微小星系。
 * 参考 100,000 Stars 与 galaxy-explorer 的 deep-field billboard 做法。
 */
export interface DistantGalaxies {
  points: THREE.Points;
  dispose: () => void;
}

const CELL = 256;

function drawElliptical(ctx: CanvasRenderingContext2D, cx: number, cy: number): void {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(1, 0.68);
  const g = ctx.createRadialGradient(0, 0, 0, 0, 0, CELL * 0.4);
  g.addColorStop(0, 'rgba(255,255,255,0.9)');
  g.addColorStop(0.35, 'rgba(255,255,255,0.35)');
  g.addColorStop(1, 'transparent');
  ctx.fillStyle = g;
  ctx.fillRect(-CELL / 2, -CELL / 2, CELL, CELL);
  ctx.restore();
}

function drawEdgeOn(ctx: CanvasRenderingContext2D, cx: number, cy: number): void {
  ctx.save();
  ctx.translate(cx, cy);
  // 扁盘
  ctx.scale(1, 0.16);
  const g = ctx.createRadialGradient(0, 0, 0, 0, 0, CELL * 0.42);
  g.addColorStop(0, 'rgba(255,255,255,0.95)');
  g.addColorStop(0.5, 'rgba(255,255,255,0.3)');
  g.addColorStop(1, 'transparent');
  ctx.fillStyle = g;
  ctx.fillRect(-CELL / 2, -CELL * 3, CELL, CELL * 6);
  ctx.restore();
  // 中心核
  ctx.save();
  ctx.translate(cx, cy);
  const core = ctx.createRadialGradient(0, 0, 0, 0, 0, CELL * 0.09);
  core.addColorStop(0, 'rgba(255,255,255,0.95)');
  core.addColorStop(1, 'transparent');
  ctx.fillStyle = core;
  ctx.fillRect(-CELL / 2, -CELL / 2, CELL, CELL);
  ctx.restore();
}

function drawFaceOnSpiral(ctx: CanvasRenderingContext2D, cx: number, cy: number): void {
  ctx.save();
  ctx.translate(cx, cy);
  const g = ctx.createRadialGradient(0, 0, 0, 0, 0, CELL * 0.36);
  g.addColorStop(0, 'rgba(255,255,255,0.9)');
  g.addColorStop(0.3, 'rgba(255,255,255,0.25)');
  g.addColorStop(1, 'transparent');
  ctx.fillStyle = g;
  ctx.fillRect(-CELL / 2, -CELL / 2, CELL, CELL);
  // 两条对称旋臂
  ctx.strokeStyle = 'rgba(255,255,255,0.5)';
  ctx.lineWidth = CELL * 0.035;
  ctx.lineCap = 'round';
  for (let armIdx = 0; armIdx < 2; armIdx++) {
    ctx.beginPath();
    for (let i = 0; i <= 20; i++) {
      const t = i / 20;
      const ang = armIdx * Math.PI + t * Math.PI * 1.5;
      const r = CELL * 0.06 + t * CELL * 0.3;
      const x = Math.cos(ang) * r;
      const y = Math.sin(ang) * r;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
  ctx.restore();
}

function drawIrregular(ctx: CanvasRenderingContext2D, cx: number, cy: number): void {
  ctx.save();
  ctx.translate(cx, cy);
  const blobs: Array<[number, number, number, number]> = [
    [-CELL * 0.08, -CELL * 0.05, CELL * 0.16, 0.7],
    [CELL * 0.1, CELL * 0.06, CELL * 0.12, 0.55],
    [-CELL * 0.02, CELL * 0.12, CELL * 0.09, 0.45],
    [CELL * 0.04, -CELL * 0.13, CELL * 0.08, 0.4],
  ];
  for (const [x, y, r, a] of blobs) {
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, `rgba(255,255,255,${a})`);
    g.addColorStop(1, 'transparent');
    ctx.fillStyle = g;
    ctx.fillRect(-CELL / 2, -CELL / 2, CELL, CELL);
  }
  ctx.restore();
}

function createAtlas(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = CELL * 2;
  canvas.height = CELL * 2;
  const ctx = canvas.getContext('2d')!;
  drawElliptical(ctx, CELL * 0.5, CELL * 0.5);
  drawEdgeOn(ctx, CELL * 1.5, CELL * 0.5);
  drawFaceOnSpiral(ctx, CELL * 0.5, CELL * 1.5);
  drawIrregular(ctx, CELL * 1.5, CELL * 1.5);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

const galaxyVertex = /* glsl */ `
attribute float aSize;
attribute vec2 aCell;
attribute float aRot;
attribute vec3 aTint;
attribute float aAlpha;
uniform float uPixelRatio;
varying vec2 vCell;
varying float vRot;
varying vec3 vTint;
varying float vAlpha;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = aSize * uPixelRatio * (300.0 / max(-mv.z, 0.1));
  vCell = aCell;
  vRot = aRot;
  vTint = aTint;
  vAlpha = aAlpha;
}
`;

const galaxyFragment = /* glsl */ `
uniform sampler2D uAtlas;
varying vec2 vCell;
varying float vRot;
varying vec3 vTint;
varying float vAlpha;
void main() {
  vec2 uv = gl_PointCoord - 0.5;
  float c = cos(vRot);
  float s = sin(vRot);
  uv = vec2(uv.x * c - uv.y * s, uv.x * s + uv.y * c) + 0.5;
  vec4 tex = texture2D(uAtlas, vCell + clamp(uv, 0.0, 1.0) * 0.5);
  gl_FragColor = vec4(vTint * tex.rgb, tex.a);
  gl_FragColor.rgb *= vAlpha;
}
`;

const TINTS = [0xaec6ff, 0xd9c8ff, 0xffd9c2, 0xc8e6ff, 0xf3c9e4, 0xfff0d0];

export function buildDistantGalaxies(scene: THREE.Scene, lowPower = false): DistantGalaxies {
  const count = lowPower ? 18 : 40;
  const positions = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const cells = new Float32Array(count * 2);
  const rots = new Float32Array(count);
  const tints = new Float32Array(count * 3);
  const alphas = new Float32Array(count);

  const tmp = new THREE.Color();
  for (let i = 0; i < count; i++) {
    // 远球壳均匀散布（在远星层之外、天穹之内）
    const r = 380 + Math.random() * 100;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    positions[i * 3 + 2] = r * Math.cos(phi);

    sizes[i] = 14 + Math.random() * 24;
    const cell = Math.floor(Math.random() * 4);
    cells[i * 2] = (cell % 2) * 0.5;
    cells[i * 2 + 1] = Math.floor(cell / 2) * 0.5;
    rots[i] = Math.random() * Math.PI * 2;

    tmp.set(TINTS[Math.floor(Math.random() * TINTS.length)]);
    tints[i * 3] = tmp.r;
    tints[i * 3 + 1] = tmp.g;
    tints[i * 3 + 2] = tmp.b;
    alphas[i] = 0.3 + Math.random() * 0.4;
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
  geo.setAttribute('aCell', new THREE.BufferAttribute(cells, 2));
  geo.setAttribute('aRot', new THREE.BufferAttribute(rots, 1));
  geo.setAttribute('aTint', new THREE.BufferAttribute(tints, 3));
  geo.setAttribute('aAlpha', new THREE.BufferAttribute(alphas, 1));

  const atlas = createAtlas();
  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uAtlas: { value: atlas },
      uPixelRatio: { value: Math.min(typeof window !== 'undefined' ? window.devicePixelRatio : 1, 2) },
    },
    vertexShader: galaxyVertex,
    fragmentShader: galaxyFragment,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const points = new THREE.Points(geo, mat);
  points.renderOrder = -5;
  points.frustumCulled = false;
  scene.add(points);

  return {
    points,
    dispose() {
      scene.remove(points);
      geo.dispose();
      mat.dispose();
      atlas.dispose();
    },
  };
}

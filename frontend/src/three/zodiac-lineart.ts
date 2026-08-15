import * as THREE from 'three';
import { ZODIAC_CONSTELLATIONS, type ZodiacConstellation } from './zodiac-data';

/**
 * 十二宫神话线稿：古典星图铜版画风格的金色描线 Sprite。
 * 平时以极淡水印浮在星座粒子云后方，悬停/聚焦该宫时淡入。
 */
export interface ZodiacLineArt {
  root: THREE.Group;
  /** 高亮某一宫（其余回落基础透明度）；传 null 全部回落 */
  setActive: (slug: string | null) => void;
  tick: (time: number) => void;
  dispose: () => void;
}

type Stroke =
  | { kind: 'path'; pts: Array<[number, number]> }
  | { kind: 'circle'; cx: number; cy: number; r: number };

const P = (pts: Array<[number, number]>): Stroke => ({ kind: 'path', pts });
const C = (cx: number, cy: number, r: number): Stroke => ({ kind: 'circle', cx, cy, r });

/** 标志性图形（-1~1 局部坐标，y 向上），铜版画式简化线稿 */
const LINE_ART: Record<string, Stroke[]> = {
  aries: [
    P([[0, -0.6], [0, -0.05], [-0.12, 0.32], [-0.4, 0.55], [-0.68, 0.45], [-0.78, 0.15], [-0.62, -0.02], [-0.48, 0.12]]),
    P([[0, -0.6], [0, -0.05], [0.12, 0.32], [0.4, 0.55], [0.68, 0.45], [0.78, 0.15], [0.62, -0.02], [0.48, 0.12]]),
  ],
  taurus: [
    C(0, -0.22, 0.36),
    P([[-0.62, 0.62], [-0.45, 0.3], [-0.18, 0.16], [0.18, 0.16], [0.45, 0.3], [0.62, 0.62]]),
  ],
  gemini: [
    P([[-0.58, 0.55], [-0.3, 0.46], [0, 0.43], [0.3, 0.46], [0.58, 0.55]]),
    P([[-0.58, -0.55], [-0.3, -0.46], [0, -0.43], [0.3, -0.46], [0.58, -0.55]]),
    P([[-0.28, 0.46], [-0.3, -0.46]]),
    P([[0.28, 0.46], [0.3, -0.46]]),
  ],
  cancer: [
    C(-0.36, 0.2, 0.16),
    P([[-0.2, 0.24], [0.12, 0.36], [0.52, 0.3]]),
    C(0.36, -0.2, 0.16),
    P([[0.2, -0.24], [-0.12, -0.36], [-0.52, -0.3]]),
  ],
  leo: [
    C(-0.38, -0.08, 0.16),
    P([[-0.24, 0.0], [-0.12, 0.32], [0.12, 0.46], [0.36, 0.34], [0.42, 0.05], [0.3, -0.28], [0.42, -0.5], [0.6, -0.44]]),
  ],
  virgo: [
    P([[-0.72, -0.42], [-0.72, 0.22], [-0.6, 0.42], [-0.48, 0.22], [-0.48, -0.42]]),
    P([[-0.48, 0.22], [-0.36, 0.42], [-0.24, 0.22], [-0.24, -0.42]]),
    P([[-0.24, 0.22], [-0.12, 0.42], [0.0, 0.22], [0.0, -0.2], [0.22, -0.46], [0.44, -0.34], [0.4, -0.1], [0.2, -0.16]]),
  ],
  libra: [
    P([[-0.6, -0.38], [0.6, -0.38]]),
    P([[-0.6, -0.12], [-0.18, -0.12]]),
    P([[-0.18, -0.12], [-0.22, 0.2], [0, 0.38], [0.22, 0.2], [0.18, -0.12]]),
    P([[0.18, -0.12], [0.6, -0.12]]),
  ],
  scorpio: [
    P([[-0.74, -0.36], [-0.74, 0.24], [-0.62, 0.42], [-0.5, 0.24], [-0.5, -0.36]]),
    P([[-0.5, 0.24], [-0.38, 0.42], [-0.26, 0.24], [-0.26, -0.36]]),
    P([[-0.26, 0.24], [-0.14, 0.42], [-0.02, 0.24], [-0.02, -0.16], [0.22, -0.44], [0.52, -0.38]]),
    P([[0.52, -0.38], [0.36, -0.26]]),
    P([[0.52, -0.38], [0.38, -0.52]]),
  ],
  sagittarius: [
    P([[-0.55, -0.55], [0.5, 0.5]]),
    P([[0.5, 0.5], [0.16, 0.44]]),
    P([[0.5, 0.5], [0.44, 0.16]]),
    P([[-0.14, -0.02], [0.22, -0.38]]),
    P([[-0.5, 0.18], [-0.2, -0.08], [0.08, -0.5]]),
  ],
  capricorn: [
    P([[-0.72, 0.4], [-0.55, -0.1], [-0.36, 0.36], [-0.2, -0.14]]),
    P([[-0.2, -0.14], [0.02, 0.26], [0.28, 0.32], [0.46, 0.06], [0.36, -0.26], [0.1, -0.32], [0.04, -0.06], [0.24, 0.0]]),
  ],
  aquarius: [
    P([[-0.66, 0.16], [-0.36, 0.4], [-0.06, 0.16], [0.24, 0.4], [0.54, 0.16]]),
    P([[-0.66, -0.28], [-0.36, -0.04], [-0.06, -0.28], [0.24, -0.04], [0.54, -0.28]]),
  ],
  pisces: [
    P([[-0.24, 0.58], [-0.55, 0.0], [-0.24, -0.58]]),
    P([[0.24, 0.58], [0.55, 0.0], [0.24, -0.58]]),
    P([[-0.44, 0.0], [0.44, 0.0]]),
  ],
};

/** 铜版画式装饰星点位置（所有宫共用，营造星图页面感） */
const DECOR_STARS: Array<[number, number]> = [
  [-0.82, 0.78], [0.85, 0.72], [0.78, -0.8], [-0.86, -0.72], [0.05, 0.88],
];

function drawSmoothPath(ctx: CanvasRenderingContext2D, pts: Array<[number, number]>, toPx: (p: [number, number]) => [number, number]) {
  if (pts.length < 2) return;
  const px = pts.map(toPx);
  ctx.beginPath();
  ctx.moveTo(px[0][0], px[0][1]);
  if (px.length === 2) {
    ctx.lineTo(px[1][0], px[1][1]);
  } else {
    for (let i = 1; i < px.length - 1; i++) {
      const mx = (px[i][0] + px[i + 1][0]) / 2;
      const my = (px[i][1] + px[i + 1][1]) / 2;
      ctx.quadraticCurveTo(px[i][0], px[i][1], mx, my);
    }
    ctx.quadraticCurveTo(
      px[px.length - 2][0], px[px.length - 2][1],
      px[px.length - 1][0], px[px.length - 1][1],
    );
  }
  ctx.stroke();
}

function makeLineArtTexture(c: ZodiacConstellation, size: number): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const half = size / 2;
  const figureScale = half * 0.62;
  // y 取负：canvas 向下为正
  const toPx = (p: [number, number]): [number, number] => [half + p[0] * figureScale, half - p[1] * figureScale];

  // 外饰圆框（双线 + 四向刻点）
  ctx.strokeStyle = 'rgba(212,175,55,0.55)';
  ctx.lineWidth = size / 340;
  ctx.beginPath();
  ctx.arc(half, half, half * 0.92, 0, Math.PI * 2);
  ctx.stroke();
  ctx.strokeStyle = 'rgba(212,175,55,0.28)';
  ctx.beginPath();
  ctx.arc(half, half, half * 0.86, 0, Math.PI * 2);
  ctx.stroke();
  ctx.fillStyle = 'rgba(245,215,110,0.7)';
  [0, Math.PI / 2, Math.PI, (Math.PI / 2) * 3].forEach((a) => {
    ctx.beginPath();
    ctx.arc(half + Math.cos(a) * half * 0.92, half + Math.sin(a) * half * 0.92, size / 170, 0, Math.PI * 2);
    ctx.fill();
  });

  // 装饰星点（四芒小星）
  ctx.strokeStyle = 'rgba(245,215,110,0.5)';
  ctx.lineWidth = size / 512;
  DECOR_STARS.forEach(([x, y]) => {
    const [px, py] = [half + x * half * 0.78, half - y * half * 0.78];
    const r = size / 90;
    ctx.beginPath();
    ctx.moveTo(px - r, py);
    ctx.lineTo(px + r, py);
    ctx.moveTo(px, py - r);
    ctx.lineTo(px, py + r);
    ctx.stroke();
  });

  // 主体线稿
  ctx.strokeStyle = 'rgba(238,213,150,0.92)';
  ctx.lineWidth = size / 128;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.shadowColor = 'rgba(245,215,110,0.8)';
  ctx.shadowBlur = size / 40;
  const strokes = LINE_ART[c.slug] ?? [];
  strokes.forEach((s) => {
    if (s.kind === 'circle') {
      const [cx, cy] = toPx([s.cx, s.cy]);
      ctx.beginPath();
      ctx.arc(cx, cy, s.r * figureScale, 0, Math.PI * 2);
      ctx.stroke();
    } else {
      drawSmoothPath(ctx, s.pts, toPx);
    }
  });
  ctx.shadowBlur = 0;

  return new THREE.CanvasTexture(canvas);
}

const RING_RADIUS = 14;
const BASE_OPACITY = 0.055;
const ACTIVE_OPACITY = 0.28;

export function buildZodiacLineArt(lowPower = false): ZodiacLineArt {
  const root = new THREE.Group();
  root.userData = { skipRaycast: true };
  const disposables: Array<{ dispose: () => void }> = [];
  const size = lowPower ? 320 : 512;

  const entries: Array<{ mat: THREE.SpriteMaterial; target: number; phase: number }> = [];
  const bySlug = new Map<string, { mat: THREE.SpriteMaterial; target: number; phase: number }>();

  ZODIAC_CONSTELLATIONS.forEach((c) => {
    const tex = makeLineArtTexture(c, size);
    disposables.push(tex);
    const mat = new THREE.SpriteMaterial({
      map: tex,
      transparent: true,
      opacity: BASE_OPACITY,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false,
    });
    disposables.push(mat);
    const sprite = new THREE.Sprite(mat);
    const a = (c.eclipticLon * Math.PI) / 180;
    // 放在星座粒子云内侧（相对外部相机为后方），略微抬升
    const r = RING_RADIUS - 2.4;
    sprite.position.set(Math.cos(a) * r, 0.3, Math.sin(a) * r);
    sprite.scale.set(5.4, 5.4, 1);
    sprite.renderOrder = -1;
    sprite.userData = { skipRaycast: true };
    root.add(sprite);
    const entry = { mat, target: BASE_OPACITY, phase: Math.random() * Math.PI * 2 };
    entries.push(entry);
    bySlug.set(c.slug, entry);
  });

  return {
    root,
    setActive(slug: string | null) {
      entries.forEach((e) => {
        e.target = BASE_OPACITY;
      });
      if (slug) {
        const e = bySlug.get(slug);
        if (e) e.target = ACTIVE_OPACITY;
      }
    },
    tick(time: number) {
      entries.forEach((e) => {
        const breathe = e.target > BASE_OPACITY ? Math.sin(time * 0.0016 + e.phase) * 0.04 : 0;
        e.mat.opacity += (e.target + breathe - e.mat.opacity) * 0.08;
      });
    },
    dispose() {
      root.parent?.remove(root);
      disposables.forEach((d) => d.dispose());
    },
  };
}

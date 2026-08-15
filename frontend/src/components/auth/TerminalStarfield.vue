<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';

type StarHue = 'silver' | 'green' | 'blue';

interface Star3D {
  x: number;
  y: number;
  z: number;
  pz: number;
  hue: StarHue;
  twinkle: number;
  twinkleSpeed: number;
}

const canvasRef = ref<HTMLCanvasElement | null>(null);
let raf = 0;
let reduceMotion = false;
let stars: Star3D[] = [];
let w = 0;
let h = 0;
let cx = 0;
let cy = 0;

const FOCUS = 280;
const MAX_Z = 1000;
const MIN_Z = 1;
const SPEED = 2.8;

function pickHue(): StarHue {
  const r = Math.random();
  if (r > 0.92) return 'green';
  if (r > 0.84) return 'blue';
  return 'silver';
}

function resetStar(s: Star3D, randomZ = false) {
  s.x = (Math.random() - 0.5) * w * 1.6;
  s.y = (Math.random() - 0.5) * h * 1.6;
  s.z = randomZ ? Math.random() * MAX_Z : MAX_Z;
  s.pz = s.z;
  s.hue = pickHue();
  s.twinkle = Math.random() * Math.PI * 2;
  s.twinkleSpeed = 0.015 + Math.random() * 0.025;
}

function seedStars(count: number) {
  stars = [];
  for (let i = 0; i < count; i++) {
    const s: Star3D = {
      x: 0,
      y: 0,
      z: 0,
      pz: 0,
      hue: 'silver',
      twinkle: 0,
      twinkleSpeed: 0.02,
    };
    resetStar(s, true);
    stars.push(s);
  }
}

function hueRgb(hue: StarHue): string {
  if (hue === 'green') return '0, 255, 157';
  if (hue === 'blue') return '56, 189, 248';
  return '232, 232, 234';
}

function drawFog(ctx: CanvasRenderingContext2D) {
  const g1 = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(w, h) * 0.7);
  g1.addColorStop(0, 'rgba(0, 255, 157, 0.03)');
  g1.addColorStop(0.35, 'rgba(20, 28, 40, 0.12)');
  g1.addColorStop(1, 'rgba(10, 10, 12, 0)');
  ctx.fillStyle = g1;
  ctx.fillRect(0, 0, w, h);

  const g2 = ctx.createRadialGradient(w * 0.15, h * 0.85, 0, w * 0.15, h * 0.85, Math.max(w, h) * 0.45);
  g2.addColorStop(0, 'rgba(56, 189, 248, 0.04)');
  g2.addColorStop(1, 'rgba(10, 10, 12, 0)');
  ctx.fillStyle = g2;
  ctx.fillRect(0, 0, w, h);
}

function project(x: number, y: number, z: number) {
  const scale = FOCUS / Math.max(z, MIN_Z);
  return {
    sx: cx + x * scale,
    sy: cy + y * scale,
    scale,
  };
}

function drawFrame(_t: number) {
  const cv = canvasRef.value;
  if (!cv) return;
  const ctx = cv.getContext('2d');
  if (!ctx) return;

  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const cw = cv.clientWidth;
  const ch = cv.clientHeight;
  if (cv.width !== Math.floor(cw * dpr) || cv.height !== Math.floor(ch * dpr)) {
    cv.width = Math.floor(cw * dpr);
    cv.height = Math.floor(ch * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    w = cw;
    h = ch;
    cx = w * 0.58;
    cy = h * 0.48;
  }

  // solid base + soft fog — full clear each frame for crisp trails via lineTo
  ctx.fillStyle = '#0a0a0c';
  ctx.fillRect(0, 0, w, h);
  drawFog(ctx);

  for (const s of stars) {
    if (!reduceMotion) {
      s.pz = s.z;
      s.z -= SPEED;
      if (s.z <= MIN_Z) {
        resetStar(s, false);
        continue;
      }
    } else {
      s.twinkle += s.twinkleSpeed;
    }

    const cur = project(s.x, s.y, s.z);
    const depth = 1 - s.z / MAX_Z;
    const alpha = Math.min(1, 0.15 + depth * 0.85);
    const rgb = hueRgb(s.hue);

    if (!reduceMotion) {
      const prev = project(s.x, s.y, s.pz);
      const trailLen = Math.hypot(cur.sx - prev.sx, cur.sy - prev.sy);
      if (trailLen > 0.5 && s.z < MAX_Z * 0.92) {
        ctx.beginPath();
        ctx.moveTo(prev.sx, prev.sy);
        ctx.lineTo(cur.sx, cur.sy);
        ctx.strokeStyle = `rgba(${rgb}, ${alpha * 0.75})`;
        ctx.lineWidth = Math.max(0.4, depth * 1.8);
        ctx.stroke();
      }
    }

    const r = reduceMotion
      ? 0.4 + depth * 1.6 * (0.7 + 0.3 * Math.sin(s.twinkle))
      : Math.max(0.35, depth * 2.2);
    ctx.beginPath();
    ctx.arc(cur.sx, cur.sy, r, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(${rgb}, ${alpha})`;
    ctx.fill();

    if (depth > 0.7 && s.hue !== 'silver') {
      ctx.beginPath();
      ctx.arc(cur.sx, cur.sy, r * 3, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${rgb}, ${alpha * 0.15})`;
      ctx.fill();
    }
  }

  if (!reduceMotion) raf = requestAnimationFrame(drawFrame);
}

function onResize() {
  const cv = canvasRef.value;
  if (!cv) return;
  w = cv.clientWidth;
  h = cv.clientHeight;
  cx = w * 0.58;
  cy = h * 0.48;
  const count = Math.min(320, Math.max(200, Math.floor((w * h) / 4500)));
  if (stars.length !== count) seedStars(count);
  if (reduceMotion) drawFrame(0);
}

onMounted(() => {
  reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const cv = canvasRef.value;
  if (!cv) return;
  w = cv.clientWidth;
  h = cv.clientHeight;
  cx = w * 0.58;
  cy = h * 0.48;
  const count = Math.min(320, Math.max(200, Math.floor((w * h) / 4500)));
  seedStars(count);
  window.addEventListener('resize', onResize);
  raf = requestAnimationFrame(drawFrame);
});

onBeforeUnmount(() => {
  cancelAnimationFrame(raf);
  window.removeEventListener('resize', onResize);
});
</script>

<template>
  <canvas
    ref="canvasRef"
    class="pointer-events-none absolute inset-0 h-full w-full"
    aria-hidden="true"
  />
</template>

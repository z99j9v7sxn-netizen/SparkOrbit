<script lang="ts">
/**
 * StatusOrb：轻量 2D canvas 点阵状态球（仿 thinking-orbs）。
 * 所有实例共享一个 rAF 时钟；离屏 / 后台自动暂停；
 * prefers-reduced-motion 时只绘制一帧静态点阵。
 */
export type StatusOrbState = 'loading' | 'thinking' | 'listening' | 'success' | 'error' | 'offline';

interface StateConfig {
  color: string;
  speed: number;
  wobble: number;
  pulse: number;
  jitter: number;
  animated: boolean;
}

const STATE_CONFIG: Record<StatusOrbState, StateConfig> = {
  loading: { color: '#7dd3fc', speed: 1.4, wobble: 0, pulse: 0, jitter: 0, animated: true },
  thinking: { color: '#c4b5fd', speed: 2.6, wobble: 0.5, pulse: 0.04, jitter: 0, animated: true },
  listening: { color: '#38bdf8', speed: 0.8, wobble: 0, pulse: 0.12, jitter: 0, animated: true },
  success: { color: '#34d399', speed: 0.35, wobble: 0, pulse: 0, jitter: 0, animated: true },
  error: { color: '#fb7185', speed: 0.9, wobble: 0, pulse: 0, jitter: 0.5, animated: true },
  offline: { color: '#64748b', speed: 0, wobble: 0, pulse: 0, jitter: 0, animated: false },
};

const ARIA_LABEL: Record<StatusOrbState, string> = {
  loading: '加载中',
  thinking: '处理中',
  listening: '监听中',
  success: '已完成',
  error: '异常',
  offline: '空闲',
};

/* 共享 rAF 时钟：所有实例一起驱动，页面隐藏时整体暂停 */
const drawFns = new Set<(t: number) => void>();
let sharedRaf = 0;

function sharedTick(now: number) {
  sharedRaf = 0;
  if (document.hidden || !drawFns.size) return;
  for (const fn of drawFns) fn(now / 1000);
  sharedRaf = requestAnimationFrame(sharedTick);
}

function ensureClock() {
  if (!sharedRaf && drawFns.size && !document.hidden) {
    sharedRaf = requestAnimationFrame(sharedTick);
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) ensureClock();
  });
}

/** 斐波那契球面点分布 */
function spherePoints(count: number): Array<[number, number, number]> {
  const pts: Array<[number, number, number]> = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i++) {
    const y = 1 - (i / (count - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const theta = golden * i;
    pts.push([Math.cos(theta) * r, y, Math.sin(theta) * r]);
  }
  return pts;
}
</script>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = withDefaults(
  defineProps<{
    state?: StatusOrbState;
    size?: number;
    label?: string;
  }>(),
  { state: 'loading', size: 20, label: '' },
);

const canvasRef = ref<HTMLCanvasElement | null>(null);
const reducedMotion =
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

onMounted(() => {
  const canvas = canvasRef.value;
  if (!canvas) return;

  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = props.size * dpr;
  canvas.height = props.size * dpr;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.scale(dpr, dpr);

  const dotCount = props.size >= 44 ? 84 : 36;
  const dotRadius = props.size >= 44 ? 1.4 : 0.9;
  const points = spherePoints(dotCount);
  const center = props.size / 2;
  const baseRadius = props.size * 0.38;
  const tiltX = 0.42;

  let visible = true;

  function draw(t: number) {
    if (!visible) return;
    const cfg = STATE_CONFIG[props.state];
    const angle = t * cfg.speed + (cfg.wobble ? Math.sin(t * 1.7) * cfg.wobble : 0);
    const radius = baseRadius * (1 + (cfg.pulse ? Math.sin(t * 3.2) * cfg.pulse : 0));
    const cosY = Math.cos(angle);
    const sinY = Math.sin(angle);
    const cosX = Math.cos(tiltX);
    const sinX = Math.sin(tiltX);

    ctx!.clearRect(0, 0, props.size, props.size);
    ctx!.fillStyle = cfg.color;

    for (let i = 0; i < points.length; i++) {
      const [px, py, pz] = points[i];
      // 绕 Y 轴旋转 + 固定 X 轴倾斜
      const x1 = px * cosY + pz * sinY;
      const z1 = -px * sinY + pz * cosY;
      const y1 = py * cosX - z1 * sinX;
      const z2 = py * sinX + z1 * cosX;

      const jx = cfg.jitter ? (Math.sin(t * 17 + i * 5.3) * cfg.jitter * props.size) / 40 : 0;
      const depth = (z2 + 1) / 2;
      ctx!.globalAlpha = 0.18 + depth * 0.82;
      ctx!.beginPath();
      ctx!.arc(
        center + x1 * radius + jx,
        center + y1 * radius,
        dotRadius * (0.55 + depth * 0.65),
        0,
        Math.PI * 2,
      );
      ctx!.fill();
    }
    ctx!.globalAlpha = 1;
  }

  const cfg = STATE_CONFIG[props.state];
  if (reducedMotion || !cfg.animated) {
    draw(0.001);
  }

  const io = new IntersectionObserver((entries) => {
    visible = entries[0]?.isIntersecting ?? true;
    if (visible && (reducedMotion || !STATE_CONFIG[props.state].animated)) draw(0.001);
  });
  io.observe(canvas);

  let registered = false;
  const syncRegistration = () => {
    const animated = !reducedMotion && STATE_CONFIG[props.state].animated;
    if (animated && !registered) {
      drawFns.add(draw);
      registered = true;
      ensureClock();
    } else if (!animated && registered) {
      drawFns.delete(draw);
      registered = false;
      draw(0.001);
    }
  };
  syncRegistration();

  const stopWatch = watch(() => props.state, syncRegistration);

  onBeforeUnmount(() => {
    stopWatch();
    io.disconnect();
    drawFns.delete(draw);
  });
});
</script>

<template>
  <canvas
    ref="canvasRef"
    class="status-orb"
    :style="{ width: `${size}px`, height: `${size}px` }"
    role="img"
    :aria-label="label || ARIA_LABEL[state]"
  />
</template>

<style scoped>
.status-orb {
  display: inline-block;
  flex-shrink: 0;
  vertical-align: middle;
}
</style>

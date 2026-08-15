<script setup lang="ts">
import { computed } from 'vue';
import {
  ZODIAC_CONSTELLATIONS,
  ZODIAC_ELEMENT_META,
  type ZodiacConstellation,
} from '../../three/zodiac-data';

const props = defineProps<{
  hovered?: string;
  mine?: string;
}>();

const emit = defineEmits<{
  (e: 'hover', slug: string | null): void;
  (e: 'select', slug: string): void;
}>();

const CX = 120;
const CY = 120;
const R_TICK = 113;
const R_OUTER = 104;
const R_INNER = 62;
const R_SYMBOL = 94;
const R_STARS = 77;
const R_HUB = 55;
const R_SUN = 109;

function polar(r: number, deg: number): [number, number] {
  const rad = ((deg - 90) * Math.PI) / 180;
  return [CX + r * Math.cos(rad), CY + r * Math.sin(rad)];
}

function hexToRgba(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
}

interface SectorStar {
  x: number;
  y: number;
  r: number;
}

interface Sector {
  slug: string;
  name: string;
  symbol: string;
  color: string;
  path: string;
  sx: number;
  sy: number;
  stars: SectorStar[];
  edges: Array<[number, number, number, number]>;
}

const sectors = computed<Sector[]>(() =>
  ZODIAC_CONSTELLATIONS.map((c, i) => {
    const start = i * 30 + 1;
    const stop = (i + 1) * 30 - 1;
    const mid = i * 30 + 15;
    const [x1, y1] = polar(R_OUTER, start);
    const [x2, y2] = polar(R_OUTER, stop);
    const [x3, y3] = polar(R_INNER, stop);
    const [x4, y4] = polar(R_INNER, start);
    const [sx, sy] = polar(R_SYMBOL, mid);

    // 迷你星座图：本地坐标 x → 沿环切向角偏移，y → 径向偏移
    const pts = c.stars.map((s) => {
      const [px, py] = polar(R_STARS + s.y * 7.5, mid + s.x * 10.5);
      return { x: px, y: py, r: s.bright ? 1.5 : 0.95 };
    });
    const edges = c.edges.map(
      ([a, b]) => [pts[a].x, pts[a].y, pts[b].x, pts[b].y] as [number, number, number, number],
    );

    return {
      slug: c.slug,
      name: c.name,
      symbol: c.symbol,
      color: ZODIAC_ELEMENT_META[c.element].css,
      path: `M ${x1} ${y1} A ${R_OUTER} ${R_OUTER} 0 0 1 ${x2} ${y2} L ${x3} ${y3} A ${R_INNER} ${R_INNER} 0 0 0 ${x4} ${y4} Z`,
      sx,
      sy,
      stars: pts,
      edges,
    };
  }),
);

// --- 外圈刻度（每 6° 一格，30° 宫界加长） ---
const ticks = computed(() => {
  const list: Array<{ x1: number; y1: number; x2: number; y2: number; major: boolean }> = [];
  for (let deg = 0; deg < 360; deg += 6) {
    const major = deg % 30 === 0;
    const [x1, y1] = polar(R_TICK - (major ? 5 : 2.2), deg);
    const [x2, y2] = polar(R_TICK, deg);
    list.push({ x1, y1, x2, y2, major });
  }
  return list;
});

// --- 雕刻装饰：罗马数字宫序 + 宫界菱形饰点 + 元素色外弧 ---
const ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII'];

const romanLabels = computed(() =>
  ROMAN.map((label, i) => {
    // 位于扇区外缘与刻度环之间的窄带，避开 12px 宫位符号
    const [x, y] = polar(106.8, i * 30 + 15);
    return { label, x, y };
  }),
);

const boundaryDiamonds = computed(() =>
  Array.from({ length: 12 }, (_, i) => {
    const [x, y] = polar(110.2, i * 30);
    const s = 1.7;
    return { path: `M ${x} ${y - s} L ${x + s} ${y} L ${x} ${y + s} L ${x - s} ${y} Z` };
  }),
);

function describeArc(r: number, startDeg: number, endDeg: number): string {
  const [x1, y1] = polar(r, startDeg);
  const [x2, y2] = polar(r, endDeg);
  return `M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`;
}

const elementArcs = computed(() =>
  ZODIAC_CONSTELLATIONS.map((c, i) => ({
    slug: c.slug,
    color: ZODIAC_ELEMENT_META[c.element].css,
    path: describeArc(115.2, i * 30 + 3, (i + 1) * 30 - 3),
  })),
);

// --- 今日太阳所在宫位 ---
function parseMonthDay(s: string): number {
  const [m, d] = s.trim().split('.').map(Number);
  return m * 100 + d;
}

const todaySign = computed<ZodiacConstellation>(() => {
  const now = new Date();
  const md = (now.getMonth() + 1) * 100 + now.getDate();
  return (
    ZODIAC_CONSTELLATIONS.find((c) => {
      const [a, b] = c.dateRange.split('-').map(parseMonthDay);
      return a <= b ? md >= a && md <= b : md >= a || md <= b;
    }) ?? ZODIAC_CONSTELLATIONS[0]
  );
});

const sunPos = computed(() => {
  const idx = ZODIAC_CONSTELLATIONS.findIndex((c) => c.slug === todaySign.value.slug);
  const [x, y] = polar(R_SUN, idx * 30 + 15);
  return { x, y };
});

// --- 古典星盘指针（alidade）：自枢纽边缘指向今日太阳 ---
const alidade = computed(() => {
  const idx = ZODIAC_CONSTELLATIONS.findIndex((c) => c.slug === todaySign.value.slug);
  const deg = idx * 30 + 15;
  const [x1, y1] = polar(R_HUB + 2, deg);
  const [x2, y2] = polar(103, deg);
  const [tx, ty] = polar(105.2, deg);
  const s = 1.5;
  return {
    x1, y1, x2, y2,
    tip: `M ${tx} ${ty - s} L ${tx + s} ${ty} L ${tx} ${ty + s} L ${tx - s} ${ty} Z`,
  };
});

// --- 中心枢纽：悬停显示该星座迷你星图与详情 ---
const hubConstellation = computed(
  () => ZODIAC_CONSTELLATIONS.find((c) => c.slug === props.hovered) ?? null,
);

const hubStars = computed(() => {
  const c = hubConstellation.value;
  if (!c) return [];
  return c.stars.map((s) => ({
    x: CX + s.x * 30,
    y: CY - 12 - s.y * 21,
    r: s.bright ? 2.1 : 1.3,
  }));
});

const hubEdges = computed(() => {
  const c = hubConstellation.value;
  if (!c) return [];
  const pts = hubStars.value;
  return c.edges.map(
    ([a, b]) => [pts[a].x, pts[a].y, pts[b].x, pts[b].y] as [number, number, number, number],
  );
});

const hubColor = computed(() =>
  hubConstellation.value ? ZODIAC_ELEMENT_META[hubConstellation.value.element].css : '#d4af37',
);
</script>

<template>
  <div class="pointer-events-none flex flex-col items-center gap-1.5">
    <svg
      viewBox="0 0 240 240"
      class="pointer-events-auto h-48 w-48 drop-shadow-[0_0_22px_rgba(212,175,55,0.28)]"
      @pointerleave="emit('hover', null)"
    >
      <defs>
        <radialGradient id="zw-hub-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="rgba(245,215,110,0.14)" />
          <stop offset="70%" stop-color="rgba(212,175,55,0.04)" />
          <stop offset="100%" stop-color="rgba(212,175,55,0)" />
        </radialGradient>
        <radialGradient id="zw-base" cx="50%" cy="42%" r="62%">
          <stop offset="0%" stop-color="rgba(12,11,22,0.7)" />
          <stop offset="58%" stop-color="rgba(16,14,26,0.74)" />
          <stop offset="84%" stop-color="rgba(38,32,20,0.78)" />
          <stop offset="96%" stop-color="rgba(84,68,32,0.6)" />
          <stop offset="100%" stop-color="rgba(212,175,55,0.3)" />
        </radialGradient>
        <linearGradient id="zw-sheen" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="rgba(253,248,231,0.12)" />
          <stop offset="35%" stop-color="rgba(253,248,231,0)" />
          <stop offset="70%" stop-color="rgba(253,248,231,0)" />
          <stop offset="100%" stop-color="rgba(245,215,110,0.08)" />
        </linearGradient>
      </defs>

      <!-- 底盘（径向渐变金属质感 + 缓旋光泽） -->
      <circle :cx="CX" :cy="CY" :r="R_TICK + 4" fill="url(#zw-base)" stroke="rgba(212,175,55,0.38)" stroke-width="0.8" />
      <g class="zw-sheen-spin pointer-events-none">
        <circle :cx="CX" :cy="CY" :r="R_TICK + 3" fill="url(#zw-sheen)" />
      </g>

      <!-- 外缘四元素分色弧带 -->
      <g class="pointer-events-none">
        <path
          v-for="a in elementArcs"
          :key="'arc' + a.slug"
          :d="a.path"
          fill="none"
          :stroke="hexToRgba(a.color, hovered === a.slug ? 0.9 : 0.42)"
          :stroke-width="hovered === a.slug ? 1.8 : 1.2"
          stroke-linecap="round"
        />
      </g>

      <!-- 宫界菱形饰点 -->
      <g class="pointer-events-none">
        <path
          v-for="(d, i) in boundaryDiamonds"
          :key="'dia' + i"
          :d="d.path"
          fill="rgba(245,215,110,0.6)"
        />
      </g>

      <!-- 旋转刻度环 -->
      <g class="zw-spin">
        <circle :cx="CX" :cy="CY" :r="R_TICK" fill="none" stroke="rgba(212,175,55,0.3)" stroke-width="0.5" />
        <line
          v-for="(t, i) in ticks"
          :key="i"
          :x1="t.x1"
          :y1="t.y1"
          :x2="t.x2"
          :y2="t.y2"
          :stroke="t.major ? 'rgba(245,215,110,0.55)' : 'rgba(212,175,55,0.3)'"
          :stroke-width="t.major ? 1 : 0.5"
        />
      </g>

      <!-- 反向旋转内虚线环 -->
      <g class="zw-spin-rev">
        <circle
          :cx="CX"
          :cy="CY"
          :r="R_INNER - 4"
          fill="none"
          stroke="rgba(212,175,55,0.28)"
          stroke-width="0.5"
          stroke-dasharray="3 4"
        />
      </g>

      <!-- 十二宫扇区 -->
      <g v-for="s in sectors" :key="s.slug">
        <path
          class="zodiac-wheel-sector"
          :class="{ 'is-mine': mine === s.slug, 'is-hot': hovered === s.slug }"
          :d="s.path"
          :style="{
            fill: hexToRgba(s.color, hovered === s.slug ? 0.24 : 0.055),
            stroke: mine === s.slug ? 'rgba(245,215,110,0.85)' : hexToRgba(s.color, 0.3),
          }"
          @pointerenter="emit('hover', s.slug)"
          @click="emit('select', s.slug)"
        >
          <title>{{ s.name }}</title>
        </path>

        <!-- 扇区内迷你星座连线 -->
        <g class="pointer-events-none" :opacity="hovered === s.slug ? 0.95 : 0.42">
          <line
            v-for="(e, i) in s.edges"
            :key="i"
            :x1="e[0]"
            :y1="e[1]"
            :x2="e[2]"
            :y2="e[3]"
            :stroke="hexToRgba(s.color, 0.55)"
            stroke-width="0.5"
          />
          <circle
            v-for="(p, i) in s.stars"
            :key="i"
            :cx="p.x"
            :cy="p.y"
            :r="p.r"
            :fill="hovered === s.slug ? '#fdf8e7' : hexToRgba(s.color, 0.9)"
          />
        </g>

        <!-- 宫位符号 -->
        <text
          class="zodiac-wheel-symbol"
          :class="{ 'is-hot': hovered === s.slug }"
          :x="s.sx"
          :y="s.sy"
          text-anchor="middle"
          dominant-baseline="central"
          :fill="hovered === s.slug ? '#fdf8e7' : hexToRgba(s.color, 0.8)"
        >
          {{ s.symbol }}
        </text>
      </g>

      <!-- 罗马数字宫序（雕刻风） -->
      <g class="pointer-events-none">
        <text
          v-for="r in romanLabels"
          :key="'rn' + r.label"
          class="font-serif-astro"
          :x="r.x"
          :y="r.y"
          text-anchor="middle"
          dominant-baseline="central"
          fill="rgba(212,175,55,0.55)"
          font-size="4.6"
          letter-spacing="0.5"
        >
          {{ r.label }}
        </text>
      </g>

      <!-- 古典星盘指针（alidade）：指向今日太阳宫位 -->
      <g class="pointer-events-none">
        <line
          :x1="alidade.x1"
          :y1="alidade.y1"
          :x2="alidade.x2"
          :y2="alidade.y2"
          stroke="rgba(245,215,110,0.5)"
          stroke-width="0.8"
        />
        <path :d="alidade.tip" fill="rgba(245,215,110,0.85)" />
      </g>

      <!-- 今日太阳标记 -->
      <g class="pointer-events-none">
        <circle class="zw-sun-pulse" :cx="sunPos.x" :cy="sunPos.y" r="5" fill="rgba(245,215,110,0.22)" />
        <circle :cx="sunPos.x" :cy="sunPos.y" r="2.2" fill="#f5d76e" stroke="rgba(253,248,231,0.9)" stroke-width="0.5">
          <title>今日太阳位于{{ todaySign.name }}</title>
        </circle>
      </g>

      <!-- 中心枢纽 -->
      <circle :cx="CX" :cy="CY" :r="R_HUB" fill="url(#zw-hub-glow)" class="pointer-events-none" />
      <g class="pointer-events-none">
        <template v-if="hubConstellation">
          <line
            v-for="(e, i) in hubEdges"
            :key="'he' + i"
            :x1="e[0]"
            :y1="e[1]"
            :x2="e[2]"
            :y2="e[3]"
            :stroke="hexToRgba(hubColor, 0.7)"
            stroke-width="0.7"
          />
          <circle
            v-for="(p, i) in hubStars"
            :key="'hs' + i"
            :cx="p.x"
            :cy="p.y"
            :r="p.r"
            fill="#fdf8e7"
          />
          <text
            :x="CX"
            :y="CY + 24"
            text-anchor="middle"
            class="font-serif-astro"
            fill="rgba(253,248,231,0.95)"
            font-size="13"
          >
            {{ hubConstellation.name }}
          </text>
          <text
            :x="CX"
            :y="CY + 38"
            text-anchor="middle"
            class="font-mono-tech"
            :fill="hexToRgba(hubColor, 0.85)"
            font-size="8"
            letter-spacing="1"
          >
            {{ hubConstellation.dateRange }}
          </text>
        </template>
        <template v-else>
          <text
            :x="CX"
            :y="CY - 8"
            text-anchor="middle"
            class="font-serif-astro"
            fill="rgba(243,229,184,0.6)"
            font-size="14"
          >
            黄道
          </text>
          <text
            :x="CX"
            :y="CY + 12"
            text-anchor="middle"
            fill="rgba(245,215,110,0.75)"
            font-size="11"
          >
            ☉ {{ todaySign.symbol }} {{ todaySign.name }}
          </text>
          <text
            :x="CX"
            :y="CY + 28"
            text-anchor="middle"
            class="font-mono-tech"
            fill="rgba(243,229,184,0.4)"
            font-size="7"
            letter-spacing="1.5"
          >
            SOL POSITION
          </text>
        </template>
      </g>
    </svg>
    <p class="font-mono-tech text-[10px] uppercase tracking-[0.35em] text-astro-dusk">
      Zodiac Navigator
    </p>
  </div>
</template>

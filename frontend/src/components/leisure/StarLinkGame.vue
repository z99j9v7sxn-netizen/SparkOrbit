<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue';
import { postLeisureSession } from '../../api/zone';
import { useOrbitStore } from '../../stores/orbit';

const emit = defineEmits<{
  (e: 'finished', payload: { score: number; won: boolean }): void;
}>();

const orbit = useOrbitStore();

/** 百分比坐标（相对容器） */
const NODES = [
  { id: 0, x: 20, y: 30 },
  { id: 1, x: 45, y: 18 },
  { id: 2, x: 70, y: 28 },
  { id: 3, x: 35, y: 55 },
  { id: 4, x: 60, y: 60 },
  { id: 5, x: 80, y: 48 },
] as const;

const TARGET: [number, number][] = [
  [0, 1],
  [1, 2],
  [1, 3],
  [3, 4],
  [2, 5],
  [4, 5],
];

const boardRef = ref<HTMLElement | null>(null);
const boardSize = ref({ w: 1, h: 1 });
const selected = ref<number | null>(null);
const links = ref<[number, number][]>([]);
const score = ref(0);
const won = ref(false);
const settling = ref(false);
const resultHint = ref('');
let reported = false;
let ro: ResizeObserver | null = null;

const remaining = computed(() => TARGET.length - links.value.length);

function sameEdge(a: [number, number], b: [number, number]) {
  return (a[0] === b[0] && a[1] === b[1]) || (a[0] === b[1] && a[1] === b[0]);
}

function measure() {
  const el = boardRef.value;
  if (!el) return;
  boardSize.value = { w: el.clientWidth || 1, h: el.clientHeight || 1 };
}

function toPx(n: { x: number; y: number }) {
  return {
    x: (n.x / 100) * boardSize.value.w,
    y: (n.y / 100) * boardSize.value.h,
  };
}

/** 用容器像素空间算长度与角度，避免非正方形容器下 % 斜边失真 */
function lineGeom(a: number, b: number) {
  const pa = toPx(NODES[a]);
  const pb = toPx(NODES[b]);
  const dx = pb.x - pa.x;
  const dy = pb.y - pa.y;
  return {
    x1: pa.x,
    y1: pa.y,
    x2: pb.x,
    y2: pb.y,
    len: Math.hypot(dx, dy),
    angle: (Math.atan2(dy, dx) * 180) / Math.PI,
  };
}

async function onClear() {
  if (reported) return;
  reported = true;
  won.value = true;
  settling.value = true;
  try {
    const res = await postLeisureSession('starlink', score.value, true);
    resultHint.value = res.message;
    orbit.pushNotification('星座连线', res.message, res.points_awarded > 0 ? 'success' : 'info');
  } catch (e) {
    resultHint.value = e instanceof Error ? e.message : '结算失败';
  } finally {
    settling.value = false;
    emit('finished', { score: score.value, won: true });
  }
}

function onNode(id: number) {
  if (won.value || settling.value) return;
  if (selected.value === null) {
    selected.value = id;
    return;
  }
  if (selected.value === id) {
    selected.value = null;
    return;
  }
  const edge: [number, number] = [selected.value, id].sort((a, b) => a - b) as [number, number];
  selected.value = null;
  const valid = TARGET.some((t) => sameEdge(t, edge));
  const exists = links.value.some((l) => sameEdge(l, edge));
  if (valid && !exists) {
    links.value.push(edge);
    score.value += 10;
    if (links.value.length === TARGET.length) void onClear();
  } else {
    score.value = Math.max(0, score.value - 2);
  }
}

function reset() {
  links.value = [];
  selected.value = null;
  score.value = 0;
  won.value = false;
  settling.value = false;
  resultHint.value = '';
  reported = false;
}

onMounted(() => {
  measure();
  if (boardRef.value && typeof ResizeObserver !== 'undefined') {
    ro = new ResizeObserver(() => measure());
    ro.observe(boardRef.value);
  }
  window.addEventListener('resize', measure);
});

onBeforeUnmount(() => {
  ro?.disconnect();
  window.removeEventListener('resize', measure);
});
</script>

<template>
  <div class="space-y-4 rounded-3xl border border-white/10 bg-black/20 p-5">
    <header class="flex items-start justify-between gap-3">
      <div>
        <h3 class="text-lg font-semibold text-white">星座连线</h3>
        <p class="mt-1 text-sm text-slate-400">
          得分 {{ score }} · 剩余 {{ remaining }} 条 · {{ won ? '星座完成！' : '点击两星连出正确脉络' }}
        </p>
      </div>
      <button
        class="shrink-0 rounded-xl border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-40"
        :disabled="settling"
        @click="reset"
      >
        重开
      </button>
    </header>

    <div
      ref="boardRef"
      class="relative h-64 overflow-hidden rounded-2xl border border-white/10 bg-black/30"
    >
      <svg class="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true">
        <line
          v-for="(edge, i) in links"
          :key="i"
          :x1="lineGeom(edge[0], edge[1]).x1"
          :y1="lineGeom(edge[0], edge[1]).y1"
          :x2="lineGeom(edge[0], edge[1]).x2"
          :y2="lineGeom(edge[0], edge[1]).y2"
          stroke="url(#starlink-grad)"
          stroke-width="2"
          stroke-linecap="round"
        />
        <defs>
          <linearGradient id="starlink-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#38bdf8" />
            <stop offset="100%" stop-color="#e879f9" />
          </linearGradient>
        </defs>
      </svg>

      <button
        v-for="n in NODES"
        :key="n.id"
        type="button"
        class="absolute h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 transition"
        :class="selected === n.id ? 'border-amber-300 bg-amber-200' : 'border-sky-300 bg-sky-400/80'"
        :style="{ left: `${n.x}%`, top: `${n.y}%` }"
        :disabled="won || settling"
        @click="onNode(n.id)"
      />

      <p
        v-if="won"
        class="absolute inset-0 flex items-center justify-center bg-black/50 text-lg font-semibold text-amber-200"
      >
        星座连线完成！
      </p>
    </div>

    <p v-if="resultHint" class="text-center text-xs text-slate-400">{{ resultHint }}</p>
    <p class="text-[11px] text-slate-500">按正确星座脉络点击两星连线，完成全部连线即可通关。</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import {
  fetchFocusHeatmap,
  fetchFocusSummary,
  postFocusSession,
  type FocusHeatmap,
  type FocusSummary,
} from '../../api/zone';
import { useOrbitStore } from '../../stores/orbit';
import { LzButton, LzStat } from './ui';

const emit = defineEmits<{ (e: 'close'): void }>();

const orbit = useOrbitStore();
const tab = ref<'controls' | 'stats'>('controls');
const focusMinutes = ref<25 | 45>(25);
const restMinutes = ref(5);
const mode = ref<'focus' | 'rest'>('focus');
const remaining = ref(25 * 60);
const running = ref(false);
const summary = ref<FocusSummary | null>(null);
const heatmap = ref<FocusHeatmap | null>(null);
const weekOffset = ref(0);
const heatmapFallback = ref(false);
let timer: number | null = null;

const SLOTS = ['morning', 'afternoon', 'evening'] as const;
const SLOT_LABELS: Record<string, string> = {
  morning: 'Morning',
  afternoon: 'Afternoon',
  evening: 'Evening',
};
const DAY_LABELS = ['日', '一', '二', '三', '四', '五', '六'];

const statusText = computed(() => {
  if (running.value) return mode.value === 'focus' ? '专注中' : '休息中';
  return mode.value === 'focus' ? '准备进入心流' : '准备休息';
});

const display = computed(() => {
  const m = Math.floor(remaining.value / 60).toString().padStart(2, '0');
  const s = (remaining.value % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
});

const totalFocusLabel = computed(() => {
  const mins = heatmap.value?.total_minutes ?? summary.value?.week_minutes ?? 0;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
});

const weekRangeLabel = computed(() => {
  if (heatmap.value?.week_start && heatmap.value?.week_end) {
    const start = new Date(heatmap.value.week_start);
    const end = new Date(heatmap.value.week_end);
    return `${start.getMonth() + 1}月${start.getDate()}日 - ${end.getMonth() + 1}月${end.getDate()}日`;
  }
  return '本周';
});

const heatmapGrid = computed(() => {
  const grid: number[][] = SLOTS.map(() => Array(7).fill(0));
  if (!heatmap.value) return grid;
  for (const cell of heatmap.value.cells) {
    if (cell.day >= 0 && cell.day < 7) {
      const row = SLOTS.indexOf(cell.slot as typeof SLOTS[number]);
      if (row >= 0) grid[row][cell.day] = cell.minutes;
    }
  }
  return grid;
});

const heatmapMax = computed(() => Math.max(1, ...heatmapGrid.value.flat()));

function cellColor(minutes: number): string {
  if (heatmapFallback.value || !heatmap.value) return 'rgba(148,163,184,0.12)';
  if (minutes <= 0) return 'rgba(34,197,94,0.08)';
  const t = Math.min(1, minutes / heatmapMax.value);
  const alpha = 0.2 + t * 0.75;
  return `rgba(34,197,94,${alpha.toFixed(2)})`;
}

async function loadSummary() {
  try {
    summary.value = await fetchFocusSummary();
  } catch {
    summary.value = null;
  }
}

async function loadHeatmap() {
  try {
    heatmap.value = await fetchFocusHeatmap(weekOffset.value);
    heatmapFallback.value = false;
  } catch {
    heatmap.value = null;
    heatmapFallback.value = true;
  }
}

function applyDuration() {
  remaining.value = (mode.value === 'focus' ? focusMinutes.value : restMinutes.value) * 60;
  stop();
}

function setFocusDuration(m: 25 | 45) {
  focusMinutes.value = m;
  if (mode.value === 'focus') applyDuration();
}

function setMode(next: 'focus' | 'rest') {
  mode.value = next;
  applyDuration();
}

function tick() {
  if (remaining.value <= 0) {
    void finish();
    return;
  }
  remaining.value -= 1;
}

function start() {
  if (running.value) return;
  running.value = true;
  timer = window.setInterval(tick, 1000);
}

function pause() {
  running.value = false;
  if (timer) window.clearInterval(timer);
  timer = null;
}

function stop() {
  pause();
}

async function finish() {
  pause();
  const minutes = mode.value === 'focus' ? focusMinutes.value : restMinutes.value;
  remaining.value = minutes * 60;

  if (mode.value === 'focus') {
    try {
      summary.value = await postFocusSession(minutes, 'pomodoro');
      orbit.pushNotification('专注完成', `完成 ${minutes} 分钟专注，积分已结算`, 'success');
      window.dispatchEvent(new CustomEvent('sparkorbit:checkin', { detail: { minutes } }));
      await loadHeatmap();
    } catch {
      const key = 'sparkorbit_focus_local';
      const prev = Number(localStorage.getItem(key) || 0);
      localStorage.setItem(key, String(prev + minutes));
      orbit.pushNotification('专注完成', `完成 ${minutes} 分钟（本地记录）`, 'success');
    }
  } else {
    orbit.pushNotification('休息结束', '可以开始下一轮专注了', 'info');
    setMode('focus');
  }
}

function prevWeek() {
  weekOffset.value -= 1;
}

function nextWeek() {
  if (weekOffset.value < 0) weekOffset.value += 1;
}

watch(weekOffset, () => void loadHeatmap());
watch(tab, (t) => {
  if (t === 'stats') void loadHeatmap();
});

onMounted(() => {
  void loadSummary();
  applyDuration();
});
onBeforeUnmount(stop);

function startWithMinutes(minutes = 25) {
  focusMinutes.value = minutes >= 45 ? 45 : 25;
  mode.value = 'focus';
  applyDuration();
  start();
}

defineExpose({ startWithMinutes });
</script>

<template>
  <div class="dock-panel flex h-full flex-col text-slate-100">
    <div class="mb-4 flex items-center justify-between gap-2">
      <div class="lz-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          class="lz-tab"
          :class="tab === 'controls' ? 'is-active' : ''"
          :aria-selected="tab === 'controls'"
          @click="tab = 'controls'"
        >
          Controls
        </button>
        <button
          type="button"
          role="tab"
          class="lz-tab"
          :class="tab === 'stats' ? 'is-active' : ''"
          :aria-selected="tab === 'stats'"
          @click="tab = 'stats'"
        >
          Stats
        </button>
      </div>
      <LzButton variant="ghost" size="sm" @click="emit('close')">收起</LzButton>
    </div>

    <div v-if="tab === 'controls'" class="flex flex-1 flex-col items-center justify-center gap-6 py-2">
      <p class="lz-subtitle lz-accent-text">{{ statusText }}</p>
      <p
        class="font-mono-tech text-6xl font-light tracking-[0.12em] text-white [text-shadow:0_0_48px_rgb(var(--lz-accent)/0.5),0_0_16px_rgb(var(--lz-accent)/0.3)]"
      >
        {{ display }}
      </p>
      <LzButton variant="primary" size="lg" class="min-w-[160px]" @click="running ? pause() : start()">
        {{ running ? '暂停' : '开始' }}
      </LzButton>

      <div class="flex flex-wrap items-center justify-center gap-2">
        <span class="lz-caption">专注</span>
        <button
          type="button"
          class="lz-btn lz-btn--sm"
          :class="mode === 'focus' && focusMinutes === 25 ? 'lz-btn--soft' : 'lz-btn--ghost'"
          @click="setMode('focus'); setFocusDuration(25)"
        >
          25′
        </button>
        <button
          type="button"
          class="lz-btn lz-btn--sm"
          :class="mode === 'focus' && focusMinutes === 45 ? 'lz-btn--soft' : 'lz-btn--ghost'"
          @click="setMode('focus'); setFocusDuration(45)"
        >
          45′
        </button>
        <span class="mx-1 text-slate-600">·</span>
        <span class="lz-caption">休息</span>
        <button
          type="button"
          class="lz-btn lz-btn--sm"
          :class="mode === 'rest' ? 'lz-btn--soft' : 'lz-btn--ghost'"
          @click="setMode('rest')"
        >
          {{ restMinutes }}′
        </button>
        <LzButton variant="ghost" size="sm" @click="applyDuration()">重置</LzButton>
      </div>

      <div v-if="summary" class="mt-2 grid w-full grid-cols-3 gap-2">
        <LzStat label="今日" :value="summary.today_minutes" unit="′" />
        <LzStat label="本周" :value="summary.week_minutes" unit="′" />
        <LzStat label="次数" :value="summary.sessions" />
      </div>
    </div>

    <div v-else class="flex flex-1 flex-col gap-4 overflow-y-auto py-1">
      <div class="flex items-center justify-between">
        <LzButton variant="ghost" size="sm" @click="prevWeek">‹</LzButton>
        <span class="lz-desc">{{ weekRangeLabel }}</span>
        <LzButton variant="ghost" size="sm" :class="weekOffset >= 0 ? 'opacity-30' : ''" @click="nextWeek">›</LzButton>
      </div>

      <div>
        <p class="lz-caption uppercase tracking-wider">总专注</p>
        <p class="mt-1 font-mono-tech text-3xl font-semibold text-white [text-shadow:0_0_24px_rgb(var(--lz-accent)/0.4)]">
          {{ totalFocusLabel }}
        </p>
      </div>

      <div class="lz-card lz-card--flat p-3">
        <div class="mb-2 grid grid-cols-8 gap-1">
          <div />
          <div v-for="d in DAY_LABELS" :key="d" class="lz-caption text-center">{{ d }}</div>
        </div>
        <div v-for="(slot, row) in SLOTS" :key="slot" class="mb-1 grid grid-cols-8 items-center gap-1">
          <div class="lz-caption">{{ SLOT_LABELS[slot] }}</div>
          <div
            v-for="day in 7"
            :key="`${slot}-${day}`"
            class="aspect-square rounded-md transition"
            :style="{ backgroundColor: cellColor(heatmapGrid[row][day - 1]) }"
            :title="`${SLOT_LABELS[slot]} · 周${DAY_LABELS[day - 1]} · ${heatmapGrid[row][day - 1]}′`"
          />
        </div>
        <p v-if="heatmapFallback" class="lz-caption mt-2 text-center">
          热力图暂不可用，已显示本周总时长
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts';
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import {
  fetchTeacherStudentFocusHeatmap,
  fetchTeacherStudentFocusSummary,
  fetchTeacherStudentFocusYearly,
} from '../../api/teacher';
import { fetchFocusHeatmap, fetchFocusSummary, fetchFocusYearly } from '../../api/zone';
import { useChartTheme } from '../../composables/useChartTheme';

const props = withDefaults(
  defineProps<{
    studentId?: string;
    classId?: string;
  }>(),
  {
    studentId: '',
    classId: '',
  },
);

const weekLabels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
const slotLabels = [
  { key: 'morning', label: '上午' },
  { key: 'afternoon', label: '下午' },
  { key: 'evening', label: '晚上' },
] as const;

const loading = ref(true);
const todayMinutes = ref(0);
const weekMinutes = ref(0);
const yearMinutes = ref(0);
const sessions = ref(0);

const rootRef = ref<HTMLDivElement | null>(null);
const weekBarRef = ref<HTMLDivElement | null>(null);
const slotBarRef = ref<HTMLDivElement | null>(null);
const calendarRef = ref<HTMLDivElement | null>(null);

const { chart: chartTokens } = useChartTheme();

/** 学生端没有 data-theme 包裹，始终按暗色渲染；教师端跟随主题 */
function inLightContext() {
  return !!rootRef.value?.closest('[data-theme="light"]');
}

let weekChart: echarts.ECharts | null = null;
let slotChart: echarts.ECharts | null = null;
let calendarChart: echarts.ECharts | null = null;

type DailyRow = { date: string; minutes: number; sessions: number; delta: number | null };
type SlotPivot = { day: string; morning: number; afternoon: number; evening: number; total: number };

const dailyRows = ref<DailyRow[]>([]);
const pivotRows = ref<SlotPivot[]>([]);
const dailySort = ref<'date' | 'minutes' | 'sessions'>('date');
const dailySortAsc = ref(false);

const sortedDaily = computed(() => {
  const rows = [...dailyRows.value];
  const key = dailySort.value;
  rows.sort((a, b) => {
    const av = a[key];
    const bv = b[key];
    if (typeof av === 'string' && typeof bv === 'string') {
      return dailySortAsc.value ? av.localeCompare(bv) : bv.localeCompare(av);
    }
    return dailySortAsc.value ? Number(av) - Number(bv) : Number(bv) - Number(av);
  });
  return rows;
});

function toggleSort(key: 'date' | 'minutes' | 'sessions') {
  if (dailySort.value === key) dailySortAsc.value = !dailySortAsc.value;
  else {
    dailySort.value = key;
    dailySortAsc.value = key === 'date' ? false : false;
  }
}

function disposeCharts() {
  weekChart?.dispose();
  slotChart?.dispose();
  calendarChart?.dispose();
  weekChart = null;
  slotChart = null;
  calendarChart = null;
}

async function loadData() {
  loading.value = true;
  disposeCharts();
  try {
    const sid = props.studentId;
    const cid = props.classId || '';
    const [yearly, focus, heat] = await Promise.all(
      sid
        ? [
            fetchTeacherStudentFocusYearly(sid, cid).catch(() => ({
              cells: [] as { date: string; minutes: number; sessions?: number }[],
              total_minutes: 0,
            })),
            fetchTeacherStudentFocusSummary(sid, cid).catch(() => ({
              today_minutes: 0,
              week_minutes: 0,
              sessions: 0,
            })),
            fetchTeacherStudentFocusHeatmap(sid, cid).catch(() => ({
              cells: [] as Array<{ day: number; slot: string; minutes: number }>,
              total_minutes: 0,
              week_start: '',
              week_end: '',
            })),
          ]
        : [
            fetchFocusYearly().catch(() => ({
              cells: [] as { date: string; minutes: number; sessions?: number }[],
              total_minutes: 0,
            })),
            fetchFocusSummary().catch(() => ({ today_minutes: 0, week_minutes: 0, sessions: 0 })),
            fetchFocusHeatmap().catch(() => ({
              cells: [] as Array<{ day: number; slot: string; minutes: number }>,
              total_minutes: 0,
              week_start: '',
              week_end: '',
            })),
          ],
    );

    todayMinutes.value = focus.today_minutes;
    weekMinutes.value = focus.week_minutes;
    yearMinutes.value = yearly.total_minutes;
    sessions.value = focus.sessions;

    const cellMap = new Map(yearly.cells.map((c) => [c.date, c]));
    const rows: DailyRow[] = [];
    for (let i = 0; i < 90; i++) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const key = d.toISOString().slice(0, 10);
      const cell = cellMap.get(key);
      const minutes = cell?.minutes ?? 0;
      const sess = cell?.sessions ?? (minutes > 0 ? 1 : 0);
      const prevDate = new Date(d);
      prevDate.setDate(prevDate.getDate() - 1);
      const prevKey = prevDate.toISOString().slice(0, 10);
      const prevMinutes = cellMap.get(prevKey)?.minutes ?? 0;
      if (minutes > 0 || i < 14) {
        rows.push({
          date: key,
          minutes,
          sessions: sess,
          delta: minutes - prevMinutes,
        });
      }
    }
    dailyRows.value = rows.filter(
      (r) => r.minutes > 0 || r.date >= new Date(Date.now() - 14 * 86400000).toISOString().slice(0, 10),
    );

    const weekMins = [0, 0, 0, 0, 0, 0, 0];
    const pivot: SlotPivot[] = weekLabels.map((day) => ({
      day,
      morning: 0,
      afternoon: 0,
      evening: 0,
      total: 0,
    }));
    heat.cells.forEach((c) => {
      if (c.day < 0 || c.day > 6) return;
      weekMins[c.day] += c.minutes;
      const row = pivot[c.day];
      if (c.slot === 'morning') row.morning += c.minutes;
      else if (c.slot === 'afternoon') row.afternoon += c.minutes;
      else row.evening += c.minutes;
      row.total += c.minutes;
    });
    pivotRows.value = pivot;

    await new Promise((r) => requestAnimationFrame(() => r(null)));

    const light = inLightContext();
    const t = chartTokens.value;
    const axisLabel = light ? t.axisLabel : '#64748b';
    const axisLabelStrong = light ? t.axisLabelStrong : '#94a3b8';
    const splitLine = light ? t.splitLine : 'rgba(148,163,184,0.1)';
    const accent = light ? t.accent : '#38bdf8';

    if (weekBarRef.value) {
      weekChart = echarts.init(weekBarRef.value);
      weekChart.setOption({
        backgroundColor: 'transparent',
        grid: { left: 36, right: 12, top: 16, bottom: 28 },
        tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${v} 分钟` },
        xAxis: {
          type: 'category',
          data: weekLabels,
          axisLabel: { color: axisLabel, fontSize: 11 },
          axisLine: { lineStyle: { color: splitLine } },
        },
        yAxis: {
          type: 'value',
          axisLabel: { color: axisLabel, fontSize: 10 },
          splitLine: { lineStyle: { color: splitLine } },
        },
        series: [
          {
            type: 'bar',
            data: weekMins,
            barMaxWidth: 28,
            itemStyle: { color: accent, borderRadius: [3, 3, 0, 0] },
          },
        ],
      });
    }

    if (slotBarRef.value) {
      const slotTotals = slotLabels.map((s) =>
        heat.cells.filter((c) => c.slot === s.key).reduce((sum, c) => sum + c.minutes, 0),
      );
      slotChart = echarts.init(slotBarRef.value);
      slotChart.setOption({
        backgroundColor: 'transparent',
        grid: { left: 48, right: 24, top: 8, bottom: 8 },
        tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${v} 分钟` },
        xAxis: {
          type: 'value',
          axisLabel: { color: axisLabel, fontSize: 10 },
          splitLine: { lineStyle: { color: splitLine } },
        },
        yAxis: {
          type: 'category',
          data: slotLabels.map((s) => s.label),
          axisLabel: { color: axisLabelStrong, fontSize: 11 },
        },
        series: [
          {
            type: 'bar',
            data: slotTotals,
            barMaxWidth: 18,
            itemStyle: { color: light ? t.palette[1] : '#64748b', borderRadius: [0, 3, 3, 0] },
          },
        ],
      });
    }

    if (calendarRef.value) {
      const end = new Date();
      const start = new Date();
      start.setDate(start.getDate() - 364);
      const startStr = start.toISOString().slice(0, 10);
      const endStr = end.toISOString().slice(0, 10);
      const heatData = yearly.cells.map((c) => [c.date, c.minutes] as [string, number]);
      const maxMin = Math.max(30, ...yearly.cells.map((c) => c.minutes), 1);
      calendarChart = echarts.init(calendarRef.value);
      calendarChart.setOption({
        backgroundColor: 'transparent',
        tooltip: {
          formatter: (p: { data?: [string, number] }) => {
            const d = p.data;
            if (!d) return '';
            return `${d[0]}<br/>专注 ${d[1]} 分钟`;
          },
        },
        visualMap: {
          min: 0,
          max: maxMin,
          orient: 'horizontal',
          left: 'center',
          bottom: 0,
          textStyle: { color: axisLabel, fontSize: 10 },
          inRange: {
            color: light
              ? ['#e2e8f0', '#bae6fd', '#38bdf8', '#0369a1']
              : ['#0f172a', '#1e3a5f', '#38bdf8', '#7dd3fc'],
          },
        },
        calendar: {
          top: 24,
          left: 36,
          right: 12,
          bottom: 36,
          cellSize: ['auto', 11],
          range: [startStr, endStr],
          itemStyle: { borderWidth: 2, borderColor: light ? '#f8fafc' : '#020617' },
          yearLabel: { show: false },
          dayLabel: { color: axisLabel, fontSize: 9, nameMap: 'cn' },
          monthLabel: { color: axisLabelStrong, fontSize: 10, nameMap: 'cn' },
        },
        series: [
          {
            type: 'heatmap',
            coordinateSystem: 'calendar',
            data: heatData,
          },
        ],
      });
    }
  } finally {
    loading.value = false;
  }
}

watch(
  () => [props.studentId, props.classId] as const,
  () => void loadData(),
  { immediate: true },
);

watch(chartTokens, () => void loadData(), { flush: 'post' });

onBeforeUnmount(() => {
  disposeCharts();
});
</script>

<template>
  <div ref="rootRef" class="space-y-5">
    <div>
      <p class="text-[10px] uppercase tracking-[0.35em] text-t-3">Panoramic Data</p>
      <h3 class="mt-1 text-base font-semibold text-t-1">全景学习数据</h3>
      <p class="mt-1 text-xs text-t-3">专注时长、时段分布与明细表（统一专注分钟口径）</p>
    </div>

    <p v-if="loading" class="text-sm text-t-2">加载中…</p>

    <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="rounded-xl border border-t-line/10 bg-t-s1/40 px-3 py-3">
        <p class="text-[10px] text-t-3">今日专注</p>
        <p class="mt-1 text-xl font-semibold tabular-nums text-t-1">{{ todayMinutes }}<span class="ml-1 text-xs font-normal text-t-3">分钟</span></p>
      </div>
      <div class="rounded-xl border border-t-line/10 bg-t-s1/40 px-3 py-3">
        <p class="text-[10px] text-t-3">本周专注</p>
        <p class="mt-1 text-xl font-semibold tabular-nums text-t-1">{{ weekMinutes }}<span class="ml-1 text-xs font-normal text-t-3">分钟</span></p>
      </div>
      <div class="rounded-xl border border-t-line/10 bg-t-s1/40 px-3 py-3">
        <p class="text-[10px] text-t-3">近一年累计</p>
        <p class="mt-1 text-xl font-semibold tabular-nums text-t-1">{{ yearMinutes }}<span class="ml-1 text-xs font-normal text-t-3">分钟</span></p>
      </div>
      <div class="rounded-xl border border-t-line/10 bg-t-s1/40 px-3 py-3">
        <p class="text-[10px] text-t-3">番茄次数</p>
        <p class="mt-1 text-xl font-semibold tabular-nums text-t-1">{{ sessions }}</p>
      </div>
    </div>

    <div class="grid gap-4 lg:grid-cols-2">
      <div class="rounded-xl border border-t-line/10 bg-t-s1/40 p-4">
        <p class="mb-2 text-xs text-t-3">本周每日专注（分钟）</p>
        <div ref="weekBarRef" class="h-40 w-full" />
      </div>
      <div class="rounded-xl border border-t-line/10 bg-t-s1/40 p-4">
        <p class="mb-2 text-xs text-t-3">本周时段分布</p>
        <div ref="slotBarRef" class="h-40 w-full" />
      </div>
    </div>

    <div class="rounded-xl border border-t-line/10 bg-t-s1/40 p-4">
      <p class="mb-2 text-xs text-t-3">近一年专注日历</p>
      <div ref="calendarRef" class="h-44 w-full" />
    </div>

    <div class="grid gap-4 lg:grid-cols-2">
      <div class="rounded-xl border border-t-line/10 bg-t-s1/40 p-4">
        <p class="mb-3 text-xs text-t-3">每日专注明细</p>
        <div class="max-h-64 overflow-auto">
          <table class="w-full text-left text-xs">
            <thead class="sticky top-0 bg-t-s1 text-t-3">
              <tr>
                <th class="cursor-pointer px-2 py-2 font-medium hover:text-t-accent" @click="toggleSort('date')">日期</th>
                <th class="cursor-pointer px-2 py-2 font-medium hover:text-t-accent" @click="toggleSort('minutes')">分钟</th>
                <th class="cursor-pointer px-2 py-2 font-medium hover:text-t-accent" @click="toggleSort('sessions')">次数</th>
                <th class="px-2 py-2 font-medium">较前日</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, i) in sortedDaily"
                :key="row.date"
                class="border-t border-t-line/8"
                :class="i % 2 === 1 ? 'bg-t-line/4' : ''"
              >
                <td class="px-2 py-1.5 tabular-nums text-t-2">{{ row.date }}</td>
                <td class="px-2 py-1.5 tabular-nums text-t-accent">{{ row.minutes }}</td>
                <td class="px-2 py-1.5 tabular-nums text-t-2">{{ row.sessions }}</td>
                <td
                  class="px-2 py-1.5 tabular-nums"
                  :class="(row.delta ?? 0) > 0 ? 'text-t-ok' : (row.delta ?? 0) < 0 ? 'text-t-danger' : 'text-t-3'"
                >
                  {{ row.delta == null ? '—' : row.delta > 0 ? `+${row.delta}` : row.delta }}
                </td>
              </tr>
              <tr v-if="!sortedDaily.length">
                <td colspan="4" class="px-2 py-4 text-center text-t-3">暂无专注记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="rounded-xl border border-t-line/10 bg-t-s1/40 p-4">
        <p class="mb-3 text-xs text-t-3">本周分日分时段（分钟）</p>
        <div class="overflow-x-auto">
          <table class="w-full min-w-[20rem] text-left text-xs">
            <thead class="bg-t-line/5 text-t-3">
              <tr>
                <th class="px-2 py-2 font-medium">星期</th>
                <th class="px-2 py-2 font-medium">上午</th>
                <th class="px-2 py-2 font-medium">下午</th>
                <th class="px-2 py-2 font-medium">晚上</th>
                <th class="px-2 py-2 font-medium">合计</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, i) in pivotRows"
                :key="row.day"
                class="border-t border-t-line/8"
                :class="i % 2 === 1 ? 'bg-t-line/4' : ''"
              >
                <td class="px-2 py-1.5 text-t-2">{{ row.day }}</td>
                <td class="px-2 py-1.5 tabular-nums text-t-2">{{ row.morning }}</td>
                <td class="px-2 py-1.5 tabular-nums text-t-2">{{ row.afternoon }}</td>
                <td class="px-2 py-1.5 tabular-nums text-t-2">{{ row.evening }}</td>
                <td class="px-2 py-1.5 tabular-nums font-medium text-t-accent">{{ row.total }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

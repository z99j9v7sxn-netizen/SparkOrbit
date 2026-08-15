<script setup lang="ts">
import * as echarts from 'echarts';
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import type { AgentRunSummary } from '../../../api/admin';

const props = defineProps<{
  runs: AgentRunSummary[];
}>();

const MODE_LABEL: Record<string, string> = {
  handoff: '顺序接力',
  workflow: '流水线',
  supervisor: '层级统筹',
  council: '并行评议',
};

const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

const stats = computed(() => {
  const running = props.runs.filter((r) => r.status === 'running').length;
  const completed = props.runs.filter((r) => r.status === 'completed').length;
  const failed = props.runs.filter((r) => r.status === 'failed').length;
  const byMode: Record<string, number> = {};
  for (const r of props.runs) {
    byMode[r.mode] = (byMode[r.mode] || 0) + 1;
  }
  return { running, completed, failed, total: props.runs.length, byMode };
});

function renderChart() {
  if (!chartRef.value) return;
  if (!chart) chart = echarts.init(chartRef.value);
  const modes = Object.keys(stats.value.byMode);
  const labels = modes.map((m) => MODE_LABEL[m] || m);
  const values = modes.map((m) => stats.value.byMode[m]);
  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 8, right: 8, top: 12, bottom: 24 },
    xAxis: {
      type: 'category',
      data: labels.length ? labels : ['暂无'],
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      axisLine: { lineStyle: { color: '#334155' } },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: 'rgba(51,65,85,0.45)' } },
      axisLabel: { color: '#64748b', fontSize: 10 },
    },
    series: [
      {
        type: 'bar',
        data: values.length ? values : [0],
        barWidth: 18,
        itemStyle: {
          borderRadius: [6, 6, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#22d3ee' },
            { offset: 1, color: '#0e7490' },
          ]),
        },
      },
    ],
    tooltip: { trigger: 'axis', backgroundColor: '#0f172a', borderColor: '#334155', textStyle: { color: '#e2e8f0', fontSize: 11 } },
  });
}

watch(
  () => props.runs,
  () => renderChart(),
  { deep: true },
);

function onResize() {
  chart?.resize();
}

onMounted(() => {
  renderChart();
  window.addEventListener('resize', onResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', onResize);
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
    <div class="rounded-2xl border border-cyan-400/20 bg-gradient-to-br from-cyan-500/10 via-slate-950/40 to-transparent p-4">
      <p class="font-mono-tech text-[10px] uppercase tracking-[0.25em] text-cyan-300/70">Episodes</p>
      <p class="mt-2 text-3xl font-semibold text-white">{{ stats.total }}</p>
      <p class="mt-1 text-xs text-slate-500">近期运行样本</p>
    </div>
    <div class="rounded-2xl border border-amber-400/20 bg-gradient-to-br from-amber-500/10 to-transparent p-4">
      <p class="font-mono-tech text-[10px] uppercase tracking-[0.25em] text-amber-300/70">Running</p>
      <p class="mt-2 text-3xl font-semibold text-amber-200">{{ stats.running }}</p>
      <p class="mt-1 text-xs text-slate-500">进行中 · 直播高亮</p>
    </div>
    <div class="rounded-2xl border border-emerald-400/20 bg-gradient-to-br from-emerald-500/10 to-transparent p-4">
      <p class="font-mono-tech text-[10px] uppercase tracking-[0.25em] text-emerald-300/70">Completed</p>
      <p class="mt-2 text-3xl font-semibold text-emerald-200">{{ stats.completed }}</p>
      <p class="mt-1 text-xs text-slate-500">已落库可回放</p>
    </div>
    <div class="rounded-2xl border border-rose-400/20 bg-gradient-to-br from-rose-500/10 to-transparent p-4">
      <p class="font-mono-tech text-[10px] uppercase tracking-[0.25em] text-rose-300/70">Failed</p>
      <p class="mt-2 text-3xl font-semibold text-rose-200">{{ stats.failed }}</p>
      <p class="mt-1 text-xs text-slate-500">需排查证据</p>
    </div>
    <div class="rounded-2xl border border-white/10 bg-slate-950/50 p-3 sm:col-span-2 xl:col-span-1">
      <p class="mb-1 font-mono-tech text-[10px] uppercase tracking-[0.25em] text-slate-500">Mode mix</p>
      <div ref="chartRef" class="h-[88px] w-full" />
    </div>
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts';
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { fetchMasteryOverview, type MasteryOverview, type WeakPlanet } from '../../api/learnExtras';

const loading = ref(true);
const emptyHint = ref('');
const data = ref<MasteryOverview | null>(null);
const seriesRef = ref<HTMLDivElement | null>(null);
const galaxyRef = ref<HTMLDivElement | null>(null);
const accuracyRef = ref<HTMLDivElement | null>(null);

let seriesChart: echarts.ECharts | null = null;
let galaxyChart: echarts.ECharts | null = null;
let accuracyChart: echarts.ECharts | null = null;

const STATUS_LABEL: Record<string, string> = {
  dim: '未点亮',
  lit: '已点亮',
  fading: '衰减中',
  meteor: '流星',
};

function trendArrow(trend: string): string {
  if (trend === 'up') return '↑';
  if (trend === 'down') return '↓';
  return '→';
}

function formatTime(iso?: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function renderCharts(overview: MasteryOverview) {
  if (seriesRef.value) {
    seriesChart?.dispose();
    seriesChart = echarts.init(seriesRef.value);
    const colors = ['#38bdf8', '#34d399', '#fbbf24', '#a78bfa', '#f472b6'];
    seriesChart.setOption({
      backgroundColor: 'transparent',
      grid: { left: 36, right: 12, top: 28, bottom: 28 },
      legend: {
        data: overview.series.map((s) => s.planet_name),
        textStyle: { color: '#94a3b8', fontSize: 10 },
        top: 0,
      },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: overview.series[0]?.labels || [],
        axisLabel: { color: '#64748b', fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        axisLabel: { color: '#64748b', fontSize: 10 },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,0.12)' } },
      },
      series: overview.series.map((s, i) => ({
        name: s.planet_name,
        type: 'line',
        smooth: true,
        data: s.scores,
        itemStyle: { color: colors[i % colors.length] },
        lineStyle: { width: 2 },
      })),
    });
  }

  if (galaxyRef.value) {
    galaxyChart?.dispose();
    galaxyChart = echarts.init(galaxyRef.value);
    galaxyChart.setOption({
      backgroundColor: 'transparent',
      grid: { left: 48, right: 12, top: 16, bottom: 28 },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: overview.by_galaxy.map((g) => g.galaxy_name),
        axisLabel: { color: '#64748b', fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        axisLabel: { color: '#64748b', fontSize: 10 },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,0.12)' } },
      },
      series: [
        {
          type: 'bar',
          data: overview.by_galaxy.map((g) => g.avg_score),
          itemStyle: { color: '#38bdf8', borderRadius: [4, 4, 0, 0] },
          barMaxWidth: 36,
        },
      ],
    });
  }

  if (accuracyRef.value) {
    accuracyChart?.dispose();
    accuracyChart = echarts.init(accuracyRef.value);
    accuracyChart.setOption({
      backgroundColor: 'transparent',
      grid: { left: 36, right: 12, top: 16, bottom: 28 },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: overview.accuracy_daily.map((d) => d.date.slice(5)),
        axisLabel: { color: '#64748b', fontSize: 9 },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        axisLabel: { color: '#64748b', fontSize: 10 },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,0.12)' } },
      },
      series: [
        {
          type: 'line',
          smooth: true,
          data: overview.accuracy_daily.map((d) => d.correct_rate),
          areaStyle: { color: 'rgba(56,189,248,0.12)' },
          itemStyle: { color: '#38bdf8' },
          lineStyle: { width: 2 },
        },
      ],
    });
  }
}

function onWeakClick(row: WeakPlanet) {
  window.dispatchEvent(
    new CustomEvent('sparkorbit:focus-planet', { detail: { slug: row.planet_slug, name: row.planet_name } }),
  );
}

onMounted(async () => {
  try {
    const overview = await fetchMasteryOverview();
    data.value = overview;
    const hasPractice =
      overview.weak_planets.length > 0 ||
      overview.accuracy_daily.length > 0 ||
      overview.series.some((s) => !s.sample_sparse);
    if (!hasPractice) {
      emptyHint.value = '暂无足够练习数据。去学区挑战行星后，这里会生成掌握曲线与正确率趋势。';
    }
    await new Promise((r) => requestAnimationFrame(() => r(null)));
    renderCharts(overview);
  } catch {
    emptyHint.value = '加载掌握数据失败，请稍后重试。';
  } finally {
    loading.value = false;
  }
});

onBeforeUnmount(() => {
  seriesChart?.dispose();
  galaxyChart?.dispose();
  accuracyChart?.dispose();
});
</script>

<template>
  <div class="space-y-4 rounded-2xl border border-white/10 bg-slate-900/60 p-4">
    <div>
      <p class="text-[10px] uppercase tracking-[0.35em] text-slate-500">Growth Track</p>
      <h3 class="mt-1 text-base font-semibold text-white">知识点掌握轨迹</h3>
      <p class="mt-1 text-xs text-slate-400">掌握曲线、学科分布与近 30 日正确率</p>
    </div>

    <p v-if="loading" class="text-sm text-slate-400">加载中…</p>
    <p v-else-if="emptyHint" class="rounded-xl border border-dashed border-white/15 bg-white/[0.03] px-3 py-3 text-xs leading-5 text-slate-400">
      {{ emptyHint }}
    </p>

    <template v-if="data && !loading">
      <div>
        <p class="mb-2 text-xs text-slate-400">知识点掌握曲线（Top 行星）</p>
        <div ref="seriesRef" class="h-44 w-full" />
        <p v-if="data.series.some((s) => s.sample_sparse)" class="mt-1 text-[10px] text-amber-300/70">
          部分曲线样本不足，已用当前掌握分合成短序列
        </p>
      </div>

      <div class="grid gap-4 sm:grid-cols-2">
        <div>
          <p class="mb-2 text-xs text-slate-400">学科平均掌握度</p>
          <div ref="galaxyRef" class="h-36 w-full" />
        </div>
        <div>
          <p class="mb-2 text-xs text-slate-400">近 30 日答题正确率</p>
          <div ref="accuracyRef" class="h-36 w-full" />
          <p v-if="!data.accuracy_daily.length" class="mt-2 text-[10px] text-slate-500">近 30 日尚无答题记录</p>
        </div>
      </div>

      <div>
        <p class="mb-2 text-xs text-slate-400">薄弱知识点</p>
        <div class="overflow-x-auto rounded-xl border border-white/10">
          <table class="w-full min-w-[28rem] text-left text-xs">
            <thead class="bg-white/[0.04] text-slate-400">
              <tr>
                <th class="px-3 py-2 font-medium">知识点</th>
                <th class="px-3 py-2 font-medium">掌握分</th>
                <th class="px-3 py-2 font-medium">状态</th>
                <th class="px-3 py-2 font-medium">近正确率</th>
                <th class="px-3 py-2 font-medium">趋势</th>
                <th class="px-3 py-2 font-medium">上次练习</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, i) in data.weak_planets"
                :key="row.planet_slug"
                class="cursor-pointer border-t border-white/5 transition hover:bg-sky-500/10"
                :class="i % 2 === 1 ? 'bg-white/[0.02]' : ''"
                @click="onWeakClick(row)"
              >
                <td class="px-3 py-2 text-slate-200">
                  <span class="block truncate">{{ row.planet_name }}</span>
                  <span class="text-[10px] text-slate-500">{{ row.galaxy_name }}</span>
                </td>
                <td class="px-3 py-2 tabular-nums text-sky-200">{{ row.score }}</td>
                <td class="px-3 py-2 text-slate-300">{{ STATUS_LABEL[row.status] || row.status }}</td>
                <td class="px-3 py-2 tabular-nums text-slate-300">{{ row.recent_accuracy }}%</td>
                <td
                  class="px-3 py-2"
                  :class="row.trend === 'up' ? 'text-emerald-300' : row.trend === 'down' ? 'text-rose-300' : 'text-slate-400'"
                >
                  {{ trendArrow(row.trend) }}
                </td>
                <td class="px-3 py-2 text-slate-400">{{ formatTime(row.last_practiced_at) }}</td>
              </tr>
              <tr v-if="!data.weak_planets.length">
                <td colspan="6" class="px-3 py-4 text-center text-slate-500">暂无薄弱点记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

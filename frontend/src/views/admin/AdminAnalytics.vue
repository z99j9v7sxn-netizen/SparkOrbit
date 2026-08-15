<script setup lang="ts">
import * as echarts from 'echarts';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { fetchAdminAnalytics, type AdminAnalytics } from '../../api/admin';
import { parseApiError } from '../../api/errors';
import AdminEmptyState from '../../components/admin/AdminEmptyState.vue';
import AdminPageHeader from '../../components/admin/AdminPageHeader.vue';
import AdminSkeleton from '../../components/admin/AdminSkeleton.vue';
import { useAdminTheme } from '../../composables/useAdminTheme';
import { useCountUp } from '../../composables/useCountUp';

const { isLight } = useAdminTheme();

const data = ref<AdminAnalytics | null>(null);
const loading = ref(true);
const msg = ref('');

const dauAnim = useCountUp(computed(() => data.value?.kpis.dau ?? 0));
const wauAnim = useCountUp(computed(() => data.value?.kpis.wau ?? 0));
const totalAnim = useCountUp(computed(() => data.value?.kpis.total_users ?? 0));
const newAnim = useCountUp(computed(() => data.value?.kpis.new_users_7d ?? 0));

const trendRef = ref<HTMLDivElement | null>(null);
const hourRef = ref<HTMLDivElement | null>(null);
const planetRef = ref<HTMLDivElement | null>(null);
const charts: echarts.ECharts[] = [];
let resizeObserver: ResizeObserver | null = null;

function baseAxis(light: boolean) {
  return {
    axisLabel: { color: '#64748b', fontSize: 10 },
    splitLine: { lineStyle: { color: light ? 'rgba(15,23,42,0.08)' : 'rgba(51,65,85,0.4)' } },
  };
}

function tooltipStyle(light: boolean) {
  return {
    backgroundColor: light ? '#ffffff' : '#0f172a',
    borderColor: light ? 'rgba(15,23,42,0.12)' : '#334155',
    textStyle: { color: light ? '#0f172a' : '#e2e8f0', fontSize: 11 },
  };
}

function initChart(el: HTMLDivElement | null): echarts.ECharts | null {
  if (!el) return null;
  const chart = echarts.init(el);
  charts.push(chart);
  if (!resizeObserver) resizeObserver = new ResizeObserver(() => charts.forEach((c) => c.resize()));
  resizeObserver.observe(el);
  return chart;
}

function renderCharts() {
  if (!data.value) return;
  const light = isLight.value;
  charts.forEach((c) => c.dispose());
  charts.length = 0;

  // 活跃 + 注册趋势（折线）
  const trend = initChart(trendRef.value);
  if (trend) {
    const dates = data.value.active_trend.map((r) => r.date.slice(5));
    const regMap = new Map(data.value.registration_trend.map((r) => [r.date.slice(5), r.count]));
    trend.setOption({
      backgroundColor: 'transparent',
      legend: { top: 0, right: 0, itemWidth: 10, itemHeight: 10, textStyle: { color: '#64748b', fontSize: 10 } },
      grid: { left: 8, right: 16, top: 28, bottom: 8, containLabel: true },
      xAxis: { type: 'category', data: dates, axisLabel: { color: '#64748b', fontSize: 10 } },
      yAxis: { type: 'value', ...baseAxis(light) },
      tooltip: { trigger: 'axis', ...tooltipStyle(light) },
      series: [
        {
          name: '活跃用户',
          type: 'line',
          smooth: true,
          data: data.value.active_trend.map((r) => r.active_users),
          itemStyle: { color: light ? '#0284c7' : '#38bdf8' },
          areaStyle: { opacity: 0.12 },
        },
        {
          name: '新注册',
          type: 'line',
          smooth: true,
          data: dates.map((d) => regMap.get(d) ?? 0),
          itemStyle: { color: light ? '#059669' : '#34d399' },
        },
      ],
    });
  }

  // 活跃时段分布（柱状）
  const hour = initChart(hourRef.value);
  if (hour) {
    hour.setOption({
      backgroundColor: 'transparent',
      grid: { left: 8, right: 8, top: 12, bottom: 8, containLabel: true },
      xAxis: {
        type: 'category',
        data: data.value.hour_distribution.map((r) => `${r.hour}`),
        axisLabel: { color: '#64748b', fontSize: 9 },
      },
      yAxis: { type: 'value', ...baseAxis(light) },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipStyle(light) },
      series: [
        {
          name: '调用量',
          type: 'bar',
          data: data.value.hour_distribution.map((r) => r.calls),
          barWidth: '60%',
          itemStyle: {
            borderRadius: [3, 3, 0, 0],
            color: light ? 'rgba(124,58,237,0.7)' : 'rgba(167,139,250,0.7)',
          },
        },
      ],
    });
  }

  // 行星热度 Top10（横向条形）
  const planet = initChart(planetRef.value);
  if (planet && data.value.top_planets.length) {
    const rows = [...data.value.top_planets].reverse();
    planet.setOption({
      backgroundColor: 'transparent',
      legend: { top: 0, right: 0, itemWidth: 10, itemHeight: 10, textStyle: { color: '#64748b', fontSize: 10 } },
      grid: { left: 8, right: 16, top: 28, bottom: 8, containLabel: true },
      xAxis: { type: 'value', ...baseAxis(light) },
      yAxis: {
        type: 'category',
        data: rows.map((r) => r.planet),
        axisLabel: { color: light ? '#334155' : '#cbd5e1', fontSize: 10 },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        ...tooltipStyle(light),
        formatter: (params: unknown) => {
          const arr = params as { dataIndex: number }[];
          const row = rows[arr?.[0]?.dataIndex ?? 0];
          if (!row) return '';
          return `${row.planet}（${row.galaxy}）<br/>学习人数 ${row.learners} · 点亮 ${row.lit}`;
        },
      },
      series: [
        {
          name: '学习人数',
          type: 'bar',
          data: rows.map((r) => r.learners),
          barWidth: 10,
          itemStyle: { borderRadius: [0, 5, 5, 0], color: light ? 'rgba(2,132,199,0.8)' : 'rgba(56,189,248,0.8)' },
        },
        {
          name: '点亮数',
          type: 'bar',
          data: rows.map((r) => r.lit),
          barWidth: 5,
          itemStyle: { borderRadius: [0, 5, 5, 0], color: light ? 'rgba(5,150,105,0.7)' : 'rgba(52,211,153,0.7)' },
        },
      ],
    });
  }
}

watch(isLight, async () => {
  await nextTick();
  renderCharts();
});

async function load() {
  loading.value = true;
  msg.value = '';
  try {
    data.value = await fetchAdminAnalytics();
  } catch (err) {
    msg.value = parseApiError(err, '数据分析加载失败');
  } finally {
    loading.value = false;
  }
  await nextTick();
  renderCharts();
}

onMounted(load);

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  charts.forEach((c) => c.dispose());
  charts.length = 0;
});
</script>

<template>
  <div class="space-y-5">
    <AdminPageHeader kicker="Analytics" title="数据分析" subtitle="用户活跃、注册增长与学习行为（Usage 看成本，这里看业务）">
      <template #actions>
        <button type="button" class="t-btn t-btn--md t-btn--ghost" :disabled="loading" @click="load">
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </template>
    </AdminPageHeader>

    <p v-if="msg" class="rounded-xl border border-t-danger/25 bg-t-danger/10 px-4 py-3 text-sm text-t-danger">{{ msg }}</p>

    <AdminSkeleton v-if="loading && !data" :rows="6" />
    <AdminEmptyState v-else-if="!data" title="暂无数据" hint="等待用户产生学习行为后再来看看" />
    <template v-else>
      <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div class="adm-kpi p-4">
          <p class="text-xs text-t-2">日活（24h）</p>
          <p class="adm-kpi__value mt-2">{{ dauAnim }}</p>
        </div>
        <div class="adm-kpi adm-kpi--ok p-4">
          <p class="text-xs text-t-2">周活（7d）</p>
          <p class="adm-kpi__value mt-2">{{ wauAnim }}</p>
        </div>
        <div class="adm-kpi adm-kpi--accent2 p-4">
          <p class="text-xs text-t-2">注册用户</p>
          <p class="adm-kpi__value mt-2">{{ totalAnim }}</p>
        </div>
        <div class="adm-kpi adm-kpi--warn p-4">
          <p class="text-xs text-t-2">7 日新增</p>
          <p class="adm-kpi__value mt-2">{{ newAnim }}</p>
        </div>
      </div>

      <section class="t-card p-5">
        <h3 class="text-sm font-semibold text-t-1">近 14 天活跃与注册趋势</h3>
        <div ref="trendRef" class="mt-3 h-[260px] w-full" />
      </section>

      <div class="grid gap-4 lg:grid-cols-2">
        <section class="t-card p-5">
          <h3 class="text-sm font-semibold text-t-1">活跃时段分布（近 7 天 · UTC）</h3>
          <div ref="hourRef" class="mt-3 h-[240px] w-full" />
        </section>

        <section class="t-card p-5">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-semibold text-t-1">行星学习热度 Top10</h3>
            <span class="t-kicker">Planets</span>
          </div>
          <div v-if="data.top_planets.length" ref="planetRef" class="mt-3 h-[240px] w-full" />
          <div v-else class="flex h-[240px] items-center justify-center text-sm text-t-3">暂无学习记录</div>
        </section>
      </div>

      <section v-if="data.grading_trend.length" class="t-card p-5">
        <h3 class="text-sm font-semibold text-t-1">近 7 天教师批阅</h3>
        <div class="mt-3 flex flex-wrap gap-3">
          <div v-for="g in data.grading_trend" :key="g.date" class="adm-kpi px-4 py-3">
            <span class="text-xs text-t-2">{{ g.date.slice(5) }}</span>
            <span class="ml-3 font-mono text-lg font-semibold text-t-1">{{ g.count }}</span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

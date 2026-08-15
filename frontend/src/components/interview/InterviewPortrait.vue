<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { LzBadge, LzButton, LzEmptyState, LzProgress, LzSkeleton } from '../learning/ui';
import InterviewScoreRing from './InterviewScoreRing.vue';
import { useEchart } from '../../composables/useEchart';
import { parseApiError } from '../../api/errors';
import { fetchInterviewPortrait, type InterviewPortrait } from '../../api/interview';

const emit = defineEmits<{
  (e: 'open-cabin'): void;
  (e: 'open-session', sessionId: string): void;
  (e: 'retry', payload: { scenario: 'job' | 'academic'; job_role?: string }): void;
}>();

const loading = ref(false);
const error = ref('');
const portrait = ref<InterviewPortrait | null>(null);
const scenario = ref<'job' | 'academic'>('job');
const radarRef = ref<HTMLDivElement | null>(null);
const trendRef = ref<HTMLDivElement | null>(null);
const radar = useEchart(radarRef);
const trend = useEchart(trendRef);

const block = computed(() => (scenario.value === 'academic' ? portrait.value?.academic : portrait.value?.job));
const filteredWeak = computed(
  () => (portrait.value?.weak_dims || []).filter((d) => d.scenario === scenario.value),
);
const roleRows = computed(
  () => (portrait.value?.by_role || []).filter((r) => r.scenario === scenario.value),
);
const loopHint = computed(() => {
  const counts = portrait.value?.loop_counts || {};
  const parts: string[] = [];
  if (counts.mistake) parts.push(`${counts.mistake} 条错题`);
  if (counts.review) parts.push(`${counts.review} 张闪卡`);
  if (counts.resource) parts.push(`${counts.resource} 份复盘包`);
  return parts.join(' · ');
});

function dimKeys() {
  const b = block.value;
  if (!b) return [];
  const labels = b.dimension_labels || {};
  const fromAvg = Object.keys(b.dimension_avg || {});
  if (fromAvg.length) return fromAvg;
  return Object.keys(labels);
}

function renderRadar() {
  const b = block.value;
  if (!b || !b.count) {
    radar.clear();
    return;
  }
  const keys = dimKeys();
  const labels = b.dimension_labels || {};
  radar.setOption({
    backgroundColor: 'transparent',
    legend: {
      data: ['历史均值', '最近一场'],
      textStyle: { color: '#94a3b8', fontSize: 11 },
      bottom: 0,
    },
    radar: {
      indicator: keys.map((k) => ({ name: labels[k] || k, max: 100 })),
      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.22)' } },
      splitArea: { areaStyle: { color: ['rgba(245,158,11,0.05)', 'transparent'] } },
      axisName: { color: '#cbd5e1', fontSize: 12 },
      axisLine: { lineStyle: { color: 'rgba(148,163,184,0.25)' } },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: keys.map((k) => Number(b.dimension_avg[k] ?? 0)),
            name: '历史均值',
            areaStyle: { color: 'rgba(245,158,11,0.18)' },
            lineStyle: { color: '#f59e0b' },
            itemStyle: { color: '#f59e0b' },
          },
          {
            value: keys.map((k) => Number(b.dimension_latest[k] ?? 0)),
            name: '最近一场',
            areaStyle: { color: 'rgba(56,189,248,0.12)' },
            lineStyle: { color: '#38bdf8' },
            itemStyle: { color: '#38bdf8' },
          },
        ],
      },
    ],
  });
}

function renderTrend() {
  const points = portrait.value?.trend || [];
  if (points.length < 2) {
    trend.clear();
    return;
  }
  trend.setOption({
    backgroundColor: 'transparent',
    grid: { left: 36, right: 12, top: 16, bottom: 28 },
    xAxis: {
      type: 'category',
      data: points.map((p) => (p.at || '').slice(5, 10)),
      axisLine: { lineStyle: { color: 'rgba(148,163,184,0.3)' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.12)' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
    },
    tooltip: { trigger: 'axis' },
    series: [
      {
        type: 'line',
        data: points.map((p) => p.overall_score ?? 0),
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        lineStyle: { color: '#f59e0b', width: 2 },
        itemStyle: { color: '#fbbf24' },
        areaStyle: { color: 'rgba(245,158,11,0.12)' },
      },
    ],
  });
}

/** 迷你趋势 sparkline（SVG polyline，无需图表实例） */
const sparkline = computed(() => {
  const points = (portrait.value?.trend || []).map((p) => Number(p.overall_score ?? 0));
  if (points.length < 2) return '';
  const w = 96;
  const h = 28;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = Math.max(max - min, 1);
  return points
    .map((v, i) => `${((i / (points.length - 1)) * w).toFixed(1)},${(h - ((v - min) / span) * h).toFixed(1)}`)
    .join(' ');
});

async function load() {
  loading.value = true;
  error.value = '';
  try {
    portrait.value = await fetchInterviewPortrait();
    if (portrait.value.job.count === 0 && portrait.value.academic.count > 0) {
      scenario.value = 'academic';
    }
  } catch (err) {
    error.value = parseApiError(err, '能力画像加载失败');
  } finally {
    loading.value = false;
  }
  await nextTick();
  renderRadar();
  renderTrend();
}

function retryWeak() {
  const b = block.value;
  emit('retry', {
    scenario: scenario.value,
    job_role: b?.latest_job_role || undefined,
  });
}

watch(scenario, async () => {
  if (loading.value) return;
  await nextTick();
  renderRadar();
});

onMounted(load);
</script>

<template>
  <div v-if="loading" class="p-4"><LzSkeleton preset="card" /></div>
  <LzEmptyState v-else-if="error" icon="!" :title="error" />
  <LzEmptyState
    v-else-if="!portrait?.session_count"
    title="还没有面试能力档案"
    desc="完成一场求职或升学模拟面试后，这里会汇总五维均值、趋势与弱项。"
    action-text="去面试舱开一场"
    @action="emit('open-cabin')"
  />
  <div v-else class="space-y-4">
    <div class="grid gap-3 sm:grid-cols-3">
      <div class="lz-card flex items-center gap-3 p-4">
        <div>
          <p class="font-mono-tech text-2xl font-semibold text-amber-200">{{ portrait.session_count }}</p>
          <p class="text-[11px] text-slate-500">已完成场次</p>
        </div>
        <svg v-if="sparkline" class="ml-auto" width="96" height="28" viewBox="0 0 96 28" aria-hidden="true">
          <polyline :points="sparkline" fill="none" stroke="#f59e0b" stroke-width="1.5" stroke-linejoin="round" />
        </svg>
      </div>
      <div class="lz-card flex items-center gap-3 p-4">
        <InterviewScoreRing :score="portrait.avg_score" :size="56" :show-grade="false" />
        <div>
          <p class="text-sm text-slate-200">综合均分</p>
          <p class="text-[11px] text-slate-500">全部已完成会话</p>
        </div>
      </div>
      <div class="lz-card flex items-center gap-3 p-4">
        <InterviewScoreRing :score="portrait.latest?.overall_score ?? null" :size="56" :show-grade="false" />
        <div class="min-w-0">
          <p class="text-sm text-slate-200">最近一场</p>
          <p class="truncate text-[11px] text-slate-500">
            {{ portrait.latest ? `${portrait.latest.job_role_label} · ${portrait.latest.scenario === 'academic' ? '升学' : '求职'}` : '—' }}
          </p>
        </div>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <button
        type="button"
        class="rounded-full px-3 py-1 text-xs"
        :class="scenario === 'job' ? 'bg-amber-400/20 text-amber-100' : 'text-slate-400 hover:text-slate-200'"
        @click="scenario = 'job'"
      >
        求职舱 · {{ portrait.job.count }} 场
      </button>
      <button
        type="button"
        class="rounded-full px-3 py-1 text-xs"
        :class="scenario === 'academic' ? 'bg-amber-400/20 text-amber-100' : 'text-slate-400 hover:text-slate-200'"
        @click="scenario = 'academic'"
      >
        升学舱 · {{ portrait.academic.count }} 场
      </button>
    </div>

    <LzEmptyState
      v-if="!block?.count"
      title="该舱还没有完成场次"
      desc="切换另一舱，或去面试舱补一场。"
      action-text="去面试舱"
      @action="emit('open-cabin')"
    />
    <template v-else>
      <section class="lz-hud-card p-4 md:p-5">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h4 class="text-sm text-amber-100">五维能力画像</h4>
          <LzBadge tone="warning">均值 vs 最近一场</LzBadge>
        </div>
        <div class="grid gap-4 md:grid-cols-[minmax(0,1fr)_16rem] md:items-center">
          <div ref="radarRef" class="h-64 min-h-[16rem] w-full" />
          <div class="space-y-2.5">
            <LzProgress
              v-for="key in dimKeys()"
              :key="key"
              :label="(block.dimension_labels || {})[key] || key"
              :value="Number(block.dimension_avg[key] ?? 0)"
              show-value
            />
          </div>
        </div>
      </section>

      <section v-if="(portrait.trend || []).length >= 2" class="lz-card p-4 md:p-5">
        <h4 class="mb-2 text-sm text-amber-100">综合分趋势</h4>
        <div ref="trendRef" class="h-44 w-full" />
      </section>

      <section class="lz-card p-4 md:p-5">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h4 class="text-sm text-amber-100">弱项</h4>
          <LzButton size="sm" variant="soft" @click="retryWeak">针对弱项再开一场</LzButton>
        </div>
        <p v-if="!filteredWeak.length" class="text-xs text-slate-500">当前舱五维均在 70 分以上。</p>
        <ul v-else class="space-y-2">
          <li
            v-for="item in filteredWeak"
            :key="`${item.scenario}-${item.key}`"
            class="rounded-xl border border-white/10 px-3 py-2.5"
          >
            <div class="mb-1.5 flex items-center justify-between">
              <span class="text-sm text-slate-200">{{ item.label }}</span>
              <span class="font-mono-tech text-xs text-rose-300">{{ item.avg }}</span>
            </div>
            <LzProgress :value="Number(item.avg ?? 0)" />
            <p class="mt-1 text-[11px] text-slate-500">
              「{{ item.label }}」历史均分低于 70，建议针对该维度再练一场或去练习舱单题快练。
            </p>
          </li>
        </ul>
      </section>

      <section v-if="roleRows.length" class="lz-card p-4 md:p-5">
        <h4 class="mb-3 text-sm text-amber-100">岗位对照</h4>
        <ul class="space-y-3">
          <li v-for="row in roleRows" :key="row.job_role">
            <div class="mb-1 flex items-center justify-between text-xs">
              <span class="text-slate-200">{{ row.job_role_label }} · {{ row.count }} 场</span>
              <span class="text-amber-200">{{ row.avg_score ?? '—' }}</span>
            </div>
            <LzProgress :value="Number(row.avg_score ?? 0)" />
          </li>
        </ul>
      </section>
    </template>

    <section class="lz-card p-4 md:p-5">
      <h4 class="mb-2 text-sm text-amber-100">回流训练</h4>
      <p class="text-xs leading-relaxed text-slate-400">
        {{ loopHint || '完成面试后，弱项会自动写入错题本与复习闪卡。' }}
        请到学习区的错题本 / 复习队列继续练。
      </p>
      <ul v-if="portrait.recent_refs?.length" class="mt-3 space-y-1 text-xs text-slate-500">
        <li v-for="(item, idx) in portrait.recent_refs" :key="idx">
          · {{ String((item as { kind?: string }).kind || 'item') }} ·
          {{ String((item as { title?: string }).title || (item as { id?: string }).id || '') }}
        </li>
      </ul>
      <div class="mt-3 flex flex-wrap gap-2">
        <LzButton size="sm" variant="ghost" @click="emit('open-cabin')">再开一场</LzButton>
        <LzButton
          v-if="portrait.latest?.id"
          size="sm"
          variant="ghost"
          @click="emit('open-session', portrait.latest.id)"
        >
          查看最近报告
        </LzButton>
      </div>
    </section>
  </div>
</template>

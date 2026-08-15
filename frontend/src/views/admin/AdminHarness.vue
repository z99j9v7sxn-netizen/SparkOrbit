<script setup lang="ts">
import * as echarts from 'echarts';
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import {
  fetchAdminHarnessFindings,
  fetchAdminHarnessMeta,
  fetchAdminHarnessReportHtml,
  type HarnessFindingsPayload,
  type HarnessMeta,
} from '../../api/admin';
import { parseApiError } from '../../api/errors';
import AdminPageHeader from '../../components/admin/AdminPageHeader.vue';
import { useAdminTheme } from '../../composables/useAdminTheme';
import { useAuthStore } from '../../stores/auth';

const { isLight } = useAdminTheme();
const meta = ref<HarnessMeta | null>(null);
const findings = ref<HarnessFindingsPayload | null>(null);
const html = ref('');
const msg = ref('');
const loading = ref(false);
const showRaw = ref(false);
const auth = useAuthStore();
const dimChartRef = ref<HTMLDivElement | null>(null);
let dimChart: echarts.ECharts | null = null;

const isPlaceholderHtml = computed(() => /占位报告|落地脚手架|placeholder/i.test(html.value || ''));

const dims = computed(() => findings.value?.dimensions || []);
const cards = computed(() => findings.value?.findings || []);

function priorityClass(p: string) {
  const x = (p || '').toLowerCase();
  if (x === 'high') return 't-badge--danger';
  if (x === 'medium') return 't-badge--warn';
  return 't-badge--neutral';
}

function evidenceLabel(state: string) {
  if (state === 'missing') return '证据缺失';
  if (state === 'partial') return '部分证据';
  if (state === 'observed') return '已观察';
  return state || '未知';
}

function findingCause(c: { cause?: string; summary?: string }) {
  return c.cause || c.summary || '—';
}

function renderDimChart() {
  if (!dimChartRef.value) return;
  if (!dimChart) dimChart = echarts.init(dimChartRef.value);
  const light = isLight.value;
  const labels = dims.value.map((d) => d.label);
  const values = dims.value.map((d) => (typeof d.score === 'number' ? d.score : 0));
  const colors = dims.value.map((d) => {
    if (d.evidence_state === 'missing') return light ? '#94a3b8' : '#475569';
    if (d.evidence_state === 'partial') return light ? '#0284c7' : '#38bdf8';
    return light ? '#059669' : '#34d399';
  });
  dimChart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 88, right: 16, top: 8, bottom: 8 },
    xAxis: {
      type: 'value',
      max: 100,
      splitLine: { lineStyle: { color: light ? 'rgba(15,23,42,0.08)' : 'rgba(51,65,85,0.4)' } },
      axisLabel: { color: '#64748b', fontSize: 10 },
    },
    yAxis: {
      type: 'category',
      data: labels,
      axisLabel: { color: light ? '#334155' : '#cbd5e1', fontSize: 11 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: 'bar',
        data: values.map((v, i) => ({
          value: dims.value[i]?.score == null ? 18 : v,
          itemStyle: {
            color: colors[i],
            opacity: dims.value[i]?.score == null ? 0.35 : 0.9,
            borderRadius: [0, 6, 6, 0],
          },
        })),
        barWidth: 14,
        label: {
          show: true,
          position: 'right',
          color: isLight.value ? '#64748b' : '#94a3b8',
          fontSize: 10,
          formatter: (p: { dataIndex: number }) => {
            const d = dims.value[p.dataIndex];
            return d?.score == null ? evidenceLabel(d?.evidence_state || '') : `${d.score}`;
          },
        },
      },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: isLight.value ? '#ffffff' : '#0f172a',
      borderColor: isLight.value ? 'rgba(15,23,42,0.12)' : '#334155',
      textStyle: { color: isLight.value ? '#0f172a' : '#e2e8f0', fontSize: 11 },
      formatter: (params: unknown) => {
        const arr = params as { dataIndex: number }[];
        const i = arr?.[0]?.dataIndex ?? 0;
        const d = dims.value[i];
        if (!d) return '';
        return `${d.label}<br/>${d.note || ''}<br/>状态：${evidenceLabel(d.evidence_state)}`;
      },
    },
  });
}

async function load() {
  loading.value = true;
  msg.value = '';
  try {
    const [m, f, h] = await Promise.all([
      fetchAdminHarnessMeta(),
      fetchAdminHarnessFindings(),
      fetchAdminHarnessReportHtml(),
    ]);
    meta.value = m;
    findings.value = f;
    html.value = h;
    await nextTick();
    renderDimChart();
  } catch (err) {
    msg.value = parseApiError(err, '加载 Harness 失败');
  } finally {
    loading.value = false;
  }
}

watch(dims, () => renderDimChart(), { deep: true });
watch(isLight, () => renderDimChart());

function onResize() {
  dimChart?.resize();
}

onMounted(() => {
  void load();
  window.addEventListener('resize', onResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', onResize);
  dimChart?.dispose();
  dimChart = null;
});
</script>

<template>
  <div class="space-y-5">
    <AdminPageHeader
      kicker="Dev Quality Loop"
      title="Agent 工程体检"
      subtitle="仿 Better Harness 报告壳 · 开发侧产物 · 与学生运行观测分离"
    >
      <template #actions>
        <button type="button" class="t-btn t-btn--md t-btn--ghost" :disabled="loading" @click="load">
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </template>
    </AdminPageHeader>

    <p v-if="msg" class="rounded-xl border border-t-danger/25 bg-t-danger/10 px-4 py-3 text-sm text-t-danger">{{ msg }}</p>

    <div class="t-card p-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p class="text-sm text-t-1/90">{{ findings?.project || 'SparkOrbit' }} · {{ findings?.status || 'unknown' }}</p>
          <p class="mt-1 text-xs text-t-3">{{ findings?.note || meta?.note }}</p>
        </div>
        <p class="font-mono-tech text-[10px] text-t-3">admin · {{ auth.user?.displayName || auth.user?.username }}</p>
      </div>
      <div v-if="findings?.feedforward?.length" class="mt-3 flex flex-wrap gap-1.5">
        <span v-for="f in findings.feedforward" :key="f" class="t-badge t-badge--info font-mono-tech">{{ f }}</span>
      </div>
    </div>

    <div class="grid gap-4 xl:grid-cols-[1.05fr_1fr]">
      <div class="t-card p-4">
        <p class="t-kicker">Agent Work Loop</p>
        <h3 class="mt-1 text-sm font-medium text-t-1">五维概览</h3>
        <p class="mt-1 text-xs text-t-3">无数值分数时显示证据状态（缺证据不瞎打分）</p>
        <div ref="dimChartRef" class="mt-3 h-[220px] w-full" />
        <ul class="mt-2 space-y-2">
          <li v-for="d in dims" :key="d.id" class="text-[11px] text-t-3">
            <div class="flex items-center gap-2">
              <span class="w-28 shrink-0 truncate text-t-2">{{ d.label }}</span>
              <div class="adm-ratio min-w-0 flex-1">
                <span class="adm-ratio__fill" :style="{ width: `${d.score ?? 0}%` }" />
              </div>
              <span class="w-14 shrink-0 text-right font-mono">{{ d.score ?? evidenceLabel(d.evidence_state) }}</span>
            </div>
            <p v-if="d.note" class="mt-0.5 pl-30 text-[10px] text-t-3/80">{{ d.note }}</p>
          </li>
        </ul>
      </div>

      <div class="t-card p-4">
        <p class="t-kicker">Artifacts</p>
        <h3 class="mt-1 text-sm font-medium text-t-1">产物状态</h3>
        <div v-if="meta" class="mt-3 grid gap-2 sm:grid-cols-2">
          <div
            v-for="(info, name) in meta.files"
            :key="name"
            class="rounded-xl border border-t-line/12 bg-t-s1/30 p-3"
          >
            <p class="font-mono-tech text-[10px] text-t-3">{{ name }}</p>
            <p class="mt-1 text-sm" :class="info.exists ? 'text-t-ok' : 'text-t-3'">
              {{ info.exists ? `就绪 · ${info.size} B` : '缺失' }}
            </p>
          </div>
        </div>
        <p class="mt-3 text-xs text-t-3">{{ meta?.reproduce }}</p>
      </div>
    </div>

    <div class="t-card">
      <div class="border-b border-t-line/10 px-4 py-3">
        <p class="t-kicker">Prioritized findings</p>
        <h3 class="mt-1 text-sm font-medium text-t-1">优先发现</h3>
      </div>
      <div class="space-y-3 p-4">
        <article
          v-for="(c, i) in cards"
          :key="c.id"
          class="finding-card rounded-xl border border-t-line/12 bg-t-s1/30 p-4"
          :style="{ animationDelay: `${i * 60}ms` }"
        >
          <div class="flex flex-wrap items-center gap-2">
            <span class="t-badge uppercase" :class="priorityClass(c.priority)">
              {{ c.priority }}
            </span>
            <span class="font-mono-tech text-[10px] text-t-3">{{ c.id }} · {{ c.dimension }}</span>
          </div>
          <h4 class="mt-2 text-sm font-medium text-t-1">{{ c.title }}</h4>
          <dl class="mt-3 grid gap-2 text-xs text-t-2 sm:grid-cols-2">
            <div>
              <dt class="text-t-3">Cause</dt>
              <dd class="mt-0.5 text-t-1/85">{{ findingCause(c) }}</dd>
            </div>
            <div>
              <dt class="text-t-3">Expected</dt>
              <dd class="mt-0.5 text-t-1/85">{{ c.expected }}</dd>
            </div>
            <div class="sm:col-span-2">
              <dt class="text-t-3">Repair</dt>
              <dd class="mt-0.5 text-t-accent/90">{{ c.repair }}</dd>
            </div>
            <div v-if="c.acceptance" class="sm:col-span-2">
              <dt class="text-t-3">Acceptance</dt>
              <dd class="mt-0.5 text-t-ok/90">{{ c.acceptance }}</dd>
            </div>
          </dl>
        </article>
        <p v-if="!cards.length" class="py-8 text-center text-sm text-t-3">暂无 findings（证据缺失）</p>
      </div>
    </div>

    <div class="t-card">
      <div class="flex flex-wrap items-center justify-between gap-2 border-b border-t-line/10 px-4 py-3">
        <div>
          <p class="text-sm text-t-1/90">原始 report.html</p>
          <p class="text-xs text-t-3">
            {{ isPlaceholderHtml ? '当前为占位 HTML，已弱化展示；优先看上方原生五维与发现' : '检测到非占位报告，可展开预览' }}
          </p>
        </div>
        <button type="button" class="t-btn t-btn--sm t-btn--ghost" @click="showRaw = !showRaw">
          {{ showRaw ? '收起' : '展开预览' }}
        </button>
      </div>
      <iframe
        v-show="showRaw && !isPlaceholderHtml"
        title="Better Harness Report"
        class="h-[60vh] w-full bg-white"
        :srcdoc="html"
      />
      <div
        v-if="showRaw && isPlaceholderHtml"
        class="px-4 py-8 text-center text-sm text-t-3"
      >
        占位报告已折叠。请按 README 用 CLI 生成真实报告后覆盖
        <code class="text-t-2">docs/evidence/better-harness/report.html</code>
      </div>
    </div>
  </div>
</template>

<style scoped>
.finding-card {
  animation: fade-up 0.4s ease both;
}
@keyframes fade-up {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>

<script setup lang="ts">
import * as echarts from 'echarts';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { fetchWeeklyActivity } from '../../api/orbit';
import { applyEvaluationToPath, fetchEvaluationReport, runClosedLoop, type EvaluationReport } from '../../api/learnExtras';
import { parseApiError } from '../../api/errors';
import { fetchWeeklyReport, type WeeklyReport } from '../../api/review';
import { fetchFocusSummary } from '../../api/zone';
import { useOrbitStore } from '../../stores/orbit';
import { LzBadge, LzButton, LzSection, LzSkeleton, LzStat, LzTabs, type LzTabItem } from './ui';

const orbit = useOrbitStore();
const TABS: LzTabItem[] = [
  { key: 'growth', label: '成长评估' },
  { key: 'weekly', label: '学习周报' },
];
const tab = ref('growth');

const chartRef = ref<HTMLDivElement | null>(null);
const radarRef = ref<HTMLDivElement | null>(null);
const posterRef = ref<HTMLCanvasElement | null>(null);
const summaryText = ref('加载成长周报…');
const report = ref<EvaluationReport | null>(null);
const weekly = ref<WeeklyReport | null>(null);
const weeklyLoading = ref(false);
const pathMsg = ref('');
const loopBusy = ref(false);
let chart: echarts.ECharts | null = null;
let radar: echarts.ECharts | null = null;

const selectionAskCount = computed(() => Number(report.value?.selection_ask_count || 0));
const heatByDay = computed(() => {
  const raw = report.value?.learn_heatmap_summary?.by_day;
  if (!raw || typeof raw !== 'object') return [] as Array<{ day: string; count: number }>;
  return Object.entries(raw as Record<string, unknown>)
    .map(([day, count]) => ({ day, count: Number(count) || 0 }))
    .filter((x) => x.day && x.day !== 'unknown')
    .slice(-14);
});
const heatMax = computed(() => Math.max(1, ...heatByDay.value.map((x) => x.count), 1));
const heatByKind = computed(() => {
  const raw = report.value?.learn_heatmap_summary?.by_kind;
  if (!raw || typeof raw !== 'object') return [] as Array<{ kind: string; count: number }>;
  return Object.entries(raw as Record<string, unknown>)
    .map(([kind, count]) => ({ kind, count: Number(count) || 0 }))
    .filter((x) => x.count > 0)
    .sort((a, b) => b.count - a.count)
    .slice(0, 6);
});
const evidenceTotal = computed(() =>
  Number(report.value?.learn_heatmap_summary?.total_evidence || report.value?.dimensions?.learn_evidence_total || 0),
);

function heatColor(count: number) {
  const t = Math.min(1, count / heatMax.value);
  const a = 0.12 + t * 0.75;
  return `rgba(56,189,248,${a.toFixed(2)})`;
}

function renderRadar(evalReport: EvaluationReport) {
  if (!radarRef.value) return;
  if (!radar) radar = echarts.init(radarRef.value);
  const focusScore = Math.min(100, Number(evalReport.dimensions?.focus_minutes || 0) / 3);
  const resourceScore = Math.min(100, Number(evalReport.dimensions?.resource_count || 0) * 15);
  radar.setOption({
    backgroundColor: 'transparent',
    radar: {
      indicator: [
        { name: '掌握率', max: 100 },
        { name: '答题正确率', max: 100 },
        { name: '专注', max: 100 },
        { name: '资源使用', max: 100 },
      ],
      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.2)' } },
      axisName: { color: '#cbd5e1', fontSize: 10 },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: [
              Number(evalReport.mastery_rate) || 0,
              Number(evalReport.quiz_accuracy) || 0,
              focusScore,
              resourceScore,
            ],
            name: '能力画像',
          },
        ],
        areaStyle: { color: 'rgba(56,189,248,0.25)' },
        lineStyle: { color: '#38bdf8' },
        itemStyle: { color: '#38bdf8' },
      },
    ],
  });
  radar.resize();
}

async function loadGrowth() {
  const [weeklyAct, focus, evalReport] = await Promise.all([
    fetchWeeklyActivity().catch(() => ({ labels: [], hours: [] })),
    fetchFocusSummary().catch(() => ({ today_minutes: 0, week_minutes: 0, sessions: 0 })),
    fetchEvaluationReport().catch(() => null),
  ]);
  report.value = evalReport;
  const hours = weeklyAct.hours || [];
  const total = hours.reduce((a: number, b: number) => a + b, 0);
  summaryText.value =
    evalReport?.summary ||
    `本周学习约 ${total.toFixed(1)} 小时，专注 ${focus.week_minutes} 分钟，共 ${focus.sessions} 次番茄。`;

  if (chartRef.value) {
    if (!chart) chart = echarts.init(chartRef.value);
    chart.setOption({
      backgroundColor: 'transparent',
      grid: { left: 28, right: 12, top: 20, bottom: 28 },
      xAxis: { type: 'category', data: weeklyAct.labels || [], axisLabel: { color: '#94a3b8', fontSize: 10 } },
      yAxis: { type: 'value', axisLabel: { color: '#64748b', fontSize: 10 }, splitLine: { lineStyle: { color: 'rgba(148,163,184,0.12)' } } },
      series: [{ type: 'bar', data: hours, itemStyle: { color: '#38bdf8', borderRadius: [6, 6, 0, 0] } }],
    });
  }

  if (evalReport) {
    await nextTick();
    renderRadar(evalReport);
  }
}

async function loadWeekly() {
  weeklyLoading.value = true;
  try {
    weekly.value = await fetchWeeklyReport();
    await nextTick();
    drawPoster();
  } catch (e) {
    orbit.pushNotification('学习周报', e instanceof Error ? e.message : '加载失败', 'warning');
    weekly.value = null;
  } finally {
    weeklyLoading.value = false;
  }
}

function drawPoster() {
  const canvas = posterRef.value;
  const data = weekly.value;
  if (!canvas || !data) return;
  const w = 720;
  const h = 960;
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const grad = ctx.createLinearGradient(0, 0, w, h);
  grad.addColorStop(0, '#071428');
  grad.addColorStop(0.55, '#0b1f3a');
  grad.addColorStop(1, '#102a4a');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, w, h);

  // stars
  ctx.fillStyle = 'rgba(255,255,255,0.35)';
  for (let i = 0; i < 60; i++) {
    const x = (i * 97) % w;
    const y = (i * 53) % h;
    ctx.beginPath();
    ctx.arc(x, y, (i % 3) * 0.4 + 0.6, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.fillStyle = '#7dd3fc';
  ctx.font = '600 18px "Segoe UI", sans-serif';
  ctx.fillText('SparkOrbit · 学习周报', 48, 64);

  ctx.fillStyle = '#ffffff';
  ctx.font = '700 36px "Segoe UI", sans-serif';
  ctx.fillText(data.display_name || '星航员', 48, 120);

  ctx.fillStyle = '#94a3b8';
  ctx.font = '400 16px "Segoe UI", sans-serif';
  ctx.fillText(`${data.week_start}  →  ${data.week_end}`, 48, 152);

  const cards: Array<{ label: string; value: string }> = [
    { label: '专注时长', value: `${data.focus_minutes} 分` },
    { label: '点亮行星', value: `${data.planets_lit}` },
    { label: '复习完成', value: `${data.reviews_done}` },
    { label: '记住率', value: `${data.remember_rate}%` },
    { label: '刷题数', value: `${data.practice_total}` },
    { label: '正确率', value: `${data.practice_correct_rate}%` },
  ];

  cards.forEach((c, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 48 + col * 312;
    const y = 200 + row * 120;
    ctx.fillStyle = 'rgba(56,189,248,0.12)';
    roundRect(ctx, x, y, 288, 96, 16);
    ctx.fill();
    ctx.strokeStyle = 'rgba(125,211,252,0.35)';
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = '#94a3b8';
    ctx.font = '400 14px "Segoe UI", sans-serif';
    ctx.fillText(c.label, x + 20, y + 34);
    ctx.fillStyle = '#e0f2fe';
    ctx.font = '700 28px "Segoe UI", sans-serif';
    ctx.fillText(c.value, x + 20, y + 72);
  });

  ctx.fillStyle = 'rgba(255,255,255,0.06)';
  roundRect(ctx, 48, 580, 624, 160, 18);
  ctx.fill();
  ctx.fillStyle = '#cbd5e1';
  ctx.font = '500 18px "Segoe UI", sans-serif';
  wrapText(ctx, data.summary || '本周暂无总结', 72, 630, 576, 28);

  ctx.fillStyle = '#64748b';
  ctx.font = '400 14px "Segoe UI", sans-serif';
  ctx.fillText(`连续打卡 ${data.streak_days} 天 · 积分 ${data.points}`, 48, 800);
  ctx.fillText('星轨在延伸，下周见', 48, 860);
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function wrapText(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, maxWidth: number, lineHeight: number) {
  const chars = [...text];
  let line = '';
  let yy = y;
  for (const ch of chars) {
    const test = line + ch;
    if (ctx.measureText(test).width > maxWidth && line) {
      ctx.fillText(line, x, yy);
      line = ch;
      yy += lineHeight;
    } else {
      line = test;
    }
  }
  if (line) ctx.fillText(line, x, yy);
}

function downloadPoster() {
  const canvas = posterRef.value;
  if (!canvas) return;
  drawPoster();
  const a = document.createElement('a');
  a.href = canvas.toDataURL('image/png');
  a.download = `sparkorbit-weekly-${weekly.value?.week_end || 'report'}.png`;
  a.click();
  orbit.pushNotification('学习周报', '海报已导出', 'success');
}

async function regenPath() {
  pathMsg.value = '正在根据评估重排路径…';
  try {
    await applyEvaluationToPath();
    pathMsg.value = '学习路径已更新，正在打开「学习路径」面板…';
    window.dispatchEvent(new CustomEvent('sparkorbit:open-dock', { detail: { dock: 'path' } }));
  } catch (err) {
    pathMsg.value = parseApiError(err, '路径重排失败');
  }
}

async function runFullLoop() {
  loopBusy.value = true;
  pathMsg.value = '正在执行评估→路径→资源全自动闭环…';
  try {
    const res = await runClosedLoop(2, true);
    const n = (res.generated || []).filter((g) => g.resource_id).length;
    pathMsg.value = `${res.message || '闭环完成'}；资源 ${n} 份；run=${res.run_id}`;
    window.dispatchEvent(new CustomEvent('sparkorbit:open-dock', { detail: { dock: 'path' } }));
  } catch (err) {
    pathMsg.value = parseApiError(err, '闭环执行失败');
  } finally {
    loopBusy.value = false;
  }
}

function onResize() {
  chart?.resize();
  radar?.resize();
}

watch(tab, (next) => {
  if (next === 'weekly' && !weekly.value) void loadWeekly();
  if (next === 'growth') {
    void nextTick(() => {
      chart?.resize();
      radar?.resize();
    });
  }
});

onMounted(() => {
  void loadGrowth();
  window.addEventListener('resize', onResize);
});
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize);
  chart?.dispose();
  radar?.dispose();
  chart = null;
  radar = null;
});
</script>

<template>
  <div class="dock-panel space-y-4">
    <LzTabs v-model="tab" :items="TABS" />

    <template v-if="tab === 'growth'">
      <div class="rounded-[var(--radius-panel)] border border-[rgb(var(--lz-accent)/0.18)] bg-gradient-to-br from-[rgb(var(--lz-accent)/0.09)] to-transparent p-4">
        <div class="flex items-start gap-3">
          <img src="/icons/growth.svg" alt="" class="mt-0.5 h-7 w-7 shrink-0" />
          <div class="min-w-0 flex-1">
            <p class="lz-caption lz-accent-text uppercase tracking-[0.35em] opacity-80">Growth Report</p>
            <h3 class="lz-title mt-1">成长评估</h3>
            <LzSkeleton v-if="summaryText === '加载成长周报…'" preset="text" :rows="2" class="mt-2" />
            <p v-else class="lz-body mt-1">{{ summaryText }}</p>
          </div>
        </div>
      </div>

      <LzSection title="本周学习时长" boxed>
        <div ref="chartRef" class="h-40 w-full" />
      </LzSection>
      <LzSection v-if="report" title="能力雷达" boxed>
        <div ref="radarRef" class="h-44 w-full" />
      </LzSection>

      <LzSection v-if="report" title="学习热力 · 学闸证据" boxed>
        <div class="grid grid-cols-2 gap-2">
          <LzStat label="划词提问" :value="selectionAskCount" unit="次" />
          <LzStat label="证据合计" :value="evidenceTotal" unit="条" />
        </div>
        <div v-if="heatByDay.length" class="mt-3 flex flex-wrap gap-1.5">
          <div
            v-for="cell in heatByDay"
            :key="cell.day"
            class="group relative flex h-9 min-w-[2.25rem] flex-1 flex-col items-center justify-end rounded-md border border-white/10"
            :style="{ backgroundColor: heatColor(cell.count) }"
            :title="`${cell.day} · ${cell.count} 条`"
          >
            <span class="pb-0.5 text-[9px] text-slate-200/90">{{ cell.count }}</span>
            <span class="absolute -bottom-4 text-[8px] text-slate-500 opacity-0 transition group-hover:opacity-100">
              {{ cell.day.slice(5) }}
            </span>
          </div>
        </div>
        <p v-else class="lz-caption mt-2">暂无按日学习证据，可在星库划词提问或演武/笔记产生证据。</p>
        <ul v-if="heatByKind.length" class="mt-4 flex flex-wrap gap-1.5">
          <li v-for="k in heatByKind" :key="k.kind">
            <LzBadge tone="neutral">{{ k.kind }} · {{ k.count }}</LzBadge>
          </li>
        </ul>
      </LzSection>

      <div v-if="report" class="grid gap-3 sm:grid-cols-2">
        <div class="rounded-[var(--radius-card)] border border-emerald-400/20 bg-emerald-500/5 p-4">
          <p class="text-[13px] font-semibold text-emerald-200">优势</p>
          <ul class="mt-2 space-y-1.5">
            <li v-for="(s, i) in report.strengths" :key="i" class="lz-desc flex gap-2">
              <span class="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
              <span>{{ s }}</span>
            </li>
          </ul>
        </div>
        <div class="rounded-[var(--radius-card)] border border-amber-400/20 bg-amber-500/5 p-4">
          <p class="text-[13px] font-semibold text-amber-200">待提升</p>
          <ul class="mt-2 space-y-1.5">
            <li v-for="(w, i) in report.weaknesses" :key="i" class="lz-desc flex gap-2">
              <span class="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
              <span>{{ w }}</span>
            </li>
          </ul>
        </div>
      </div>

      <div v-if="report?.suggestions?.length" class="lz-card p-4">
        <p class="lz-subtitle lz-accent-text">改进建议</p>
        <ul class="mt-2 space-y-1.5">
          <li v-for="(s, i) in report.suggestions" :key="i" class="lz-desc flex gap-2">
            <span class="lz-accent-text">{{ i + 1 }}.</span>
            <span>{{ s }}</span>
          </li>
        </ul>
        <LzButton variant="soft" size="md" block class="mt-4" @click="regenPath">
          按建议重排学习路径
        </LzButton>
        <LzButton variant="primary" size="md" block class="mt-2" :loading="loopBusy" @click="runFullLoop">
          {{ loopBusy ? '闭环执行中…' : '一键全自动补强（评估→路径→资源）' }}
        </LzButton>
        <p class="lz-caption mt-2">
          将根据评估更新「学习路径」；全自动补强还会为 Top2 弱项触发生成资源，并在管理端 `/admin/agents` 以 mode=loop 回放。
        </p>
        <p v-if="pathMsg" class="mt-2" :class="pathMsg.includes('失败') ? 'text-xs text-rose-300' : 'lz-caption'">
          {{ pathMsg }}
        </p>
      </div>
    </template>

    <template v-else>
      <div class="rounded-[var(--radius-panel)] border border-amber-400/20 bg-gradient-to-br from-amber-500/10 to-transparent p-4">
        <p class="lz-caption text-amber-200/80 uppercase tracking-[0.35em]">Weekly Report</p>
        <h3 class="lz-title mt-1">本周学习周报</h3>
        <p class="lz-desc mt-1">聚合专注、复习、刷题与模考，可导出分享海报</p>
      </div>

      <LzSkeleton v-if="weeklyLoading" preset="card" :rows="4" />
      <template v-else-if="weekly">
        <p class="lz-body">{{ weekly.summary }}</p>
        <p class="lz-caption">{{ weekly.week_start }} → {{ weekly.week_end }}</p>
        <div class="grid grid-cols-2 gap-2 sm:grid-cols-3">
          <LzStat label="专注" :value="weekly.focus_minutes" unit="分" />
          <LzStat label="点亮" :value="weekly.planets_lit" unit="颗" />
          <LzStat label="复习" :value="weekly.reviews_done" unit="项" />
          <LzStat label="记住率" :value="weekly.remember_rate" unit="%" />
          <LzStat label="刷题" :value="weekly.practice_total" unit="道" />
          <LzStat label="正确率" :value="weekly.practice_correct_rate" unit="%" />
        </div>
        <div class="grid grid-cols-2 gap-2">
          <LzStat label="模考次数" :value="weekly.mock_count" unit="次" />
          <LzStat label="模考最佳" :value="weekly.mock_best" unit="分" />
        </div>

        <LzSection title="分享海报" boxed>
          <canvas ref="posterRef" class="mx-auto max-h-80 w-full max-w-xs rounded-xl border border-white/10" />
          <div class="mt-3 flex gap-2">
            <LzButton variant="primary" size="sm" @click="downloadPoster">导出 PNG</LzButton>
            <LzButton variant="ghost" size="sm" @click="drawPoster">刷新海报</LzButton>
          </div>
        </LzSection>
      </template>
      <p v-else class="lz-caption">周报暂不可用，稍后再试</p>
    </template>
  </div>
</template>

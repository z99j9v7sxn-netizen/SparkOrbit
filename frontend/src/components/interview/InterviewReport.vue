<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { LzBadge, LzEmptyState, LzProgress, LzSkeleton } from '../learning/ui';
import InterviewScoreRing from './InterviewScoreRing.vue';
import { useEchart } from '../../composables/useEchart';
import { parseApiError } from '../../api/errors';
import {
  fetchInterviewReport,
  fetchInterviewSession,
  type InterviewReport,
  type InterviewSessionDetail,
  type InterviewTurn,
} from '../../api/interview';

type CouncilView = { role?: string; score?: number; view?: string; issues?: unknown };

const props = defineProps<{ sessionId?: string; reportId?: string }>();

const loading = ref(false);
const error = ref('');
const detail = ref<InterviewSessionDetail | null>(null);
const report = ref<InterviewReport | null>(null);
const radarRef = ref<HTMLDivElement | null>(null);
const radar = useEchart(radarRef);
const expandedTurn = ref('');

const KIND_LABEL: Record<string, string> = {
  mistake: '错题本',
  review: '复习闪卡',
  resource: '复盘包',
  assignment: '作业成绩',
};

const COUNCIL_ICON: Record<string, string> = {
  技术官: '⌘',
  HR官: '☰',
  业务官: '◈',
  学科导师: '✦',
  综合素质官: '❖',
  科研潜力官: '◎',
};

function renderRadar(item: InterviewReport) {
  const labels = item.dimension_labels || {};
  const keys = Object.keys(item.dimension_scores || {});
  if (!keys.length) return;
  radar.setOption({
    backgroundColor: 'transparent',
    radar: {
      indicator: keys.map((k) => ({ name: labels[k] || k, max: 100 })),
      radius: '68%',
      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.2)' } },
      splitArea: {
        areaStyle: { color: ['rgba(245,158,11,0.03)', 'transparent'] },
      },
      axisName: { color: '#fcd34d', fontSize: 11 },
    },
    series: [
      {
        type: 'radar',
        data: [{ value: keys.map((k) => Number(item.dimension_scores[k] || 0)), name: '本场画像' }],
        areaStyle: { color: 'rgba(245,158,11,0.22)' },
        lineStyle: { color: '#f59e0b' },
        itemStyle: { color: '#f59e0b' },
      },
    ],
  });
}

function councilIssues(view: CouncilView): string[] {
  const raw = view.issues;
  if (!Array.isArray(raw)) return [];
  return raw.map((item) => String(item)).filter(Boolean);
}

function refKind(item: Record<string, unknown>) {
  return KIND_LABEL[String(item.kind || '')] || String(item.kind || '资源');
}

function refTitle(item: Record<string, unknown>) {
  return String(item.title || item.id || '');
}

function modalityRows(turn: InterviewTurn) {
  return [
    { key: 'semantic', label: '语义', value: turn.semantic_score },
    { key: 'prosody', label: '语调', value: turn.prosody_score },
    { key: 'visual', label: '仪态', value: turn.visual_score },
  ];
}

/** 表达细节分析：由逐题 prosody_detail 聚合 */
const expression = computed(() => {
  const turns = detail.value?.turns || [];
  const details = turns.map((t) => t.prosody_detail || {}).filter((d) => d && d.duration_sec != null);
  if (!details.length) return null;
  const totalChars = details.reduce((s, d) => s + Number(d.char_count || 0), 0);
  const totalSec = details.reduce((s, d) => s + Number(d.duration_sec || 0), 0);
  const fillers = details.reduce((s, d) => s + Number(d.filler_count || 0), 0);
  const pauses = details.map((d) => Number(d.pause_ratio || 0));
  const avgPause = pauses.reduce((s, v) => s + v, 0) / pauses.length;
  const rate = totalSec > 0 ? totalChars / totalSec : 0;
  const reasons = [...new Set(details.flatMap((d) => (d.reasons || []) as string[]))].slice(0, 4);
  let advice = '';
  if (rate > 0 && rate < 2.2) advice = '整体语速偏慢，回答前先在心里列要点，可以让节奏更紧凑。';
  else if (rate > 6.5) advice = '语速偏快，重点句子适当放慢并停顿，让面试官跟上你的思路。';
  else if (fillers >= 6) advice = '口头禅偏多，试着用短暂停顿替代「嗯、啊、就是」。';
  else if (avgPause > 0.35) advice = '停顿占比偏高，作答前先想清楚结论再展开。';
  else advice = '表达节奏总体自然，保持即可。';
  return {
    rate: rate ? (rate * 60).toFixed(0) : '—',
    fillers,
    pause: `${Math.round(avgPause * 100)}%`,
    duration: Math.round(totalSec),
    reasons,
    advice,
  };
});

/** 岗位情报对照 */
const intel = computed(() => detail.value?.prep_intel || null);
const hasIntel = computed(() => {
  const i = intel.value;
  return Boolean(i && (i.job?.summary || (i.job?.skills || []).length || (i.topics || []).length));
});

async function load() {
  if (!props.sessionId && !props.reportId) return;
  loading.value = true;
  error.value = '';
  expandedTurn.value = '';
  try {
    if (props.sessionId) {
      detail.value = await fetchInterviewSession(props.sessionId);
      report.value = detail.value.report;
    } else if (props.reportId) {
      report.value = await fetchInterviewReport(props.reportId);
    }
    await nextTick();
    if (report.value) renderRadar(report.value);
  } catch (err) {
    error.value = parseApiError(err, '报告加载失败');
  } finally {
    loading.value = false;
  }
}

function toggleTurn(id: string) {
  expandedTurn.value = expandedTurn.value === id ? '' : id;
}

function printReport() {
  window.print();
}

onMounted(load);
watch(() => [props.sessionId, props.reportId], load);
</script>

<template>
  <div v-if="loading" class="p-4"><LzSkeleton preset="card" /></div>
  <LzEmptyState v-else-if="error" icon="!" :title="error" />
  <div v-else-if="report" class="iv-report space-y-5">
    <!-- 头部：得分环 + 雷达 + 快照 -->
    <div class="lz-card p-5">
      <div class="mb-4 flex flex-wrap items-center gap-2">
        <LzBadge tone="warning">本场已完成</LzBadge>
        <LzBadge v-for="m in report.degraded_modalities" :key="m" tone="neutral">{{ m }} 已降级</LzBadge>
        <button
          type="button"
          class="iv-no-print ml-auto rounded-lg border border-white/10 px-2.5 py-1 text-xs text-slate-400 transition hover:border-amber-400/40 hover:text-amber-200"
          @click="printReport"
        >
          打印 / 导出 PDF
        </button>
      </div>
      <div class="grid gap-5 md:grid-cols-[auto_1fr]">
        <div class="flex flex-col items-center justify-center gap-3">
          <InterviewScoreRing :score="detail?.overall_score ?? null" :size="112" />
          <p class="max-w-[12rem] text-center text-[11px] text-slate-500">综合三方评议与逐题多模态评分</p>
        </div>
        <div>
          <p class="text-sm leading-relaxed text-slate-200">{{ report.summary }}</p>
          <div ref="radarRef" class="mt-3 h-52 w-full" />
        </div>
      </div>
      <div class="mt-2 space-y-2">
        <p class="text-xs text-amber-100">本场能力快照</p>
        <LzProgress
          v-for="(score, key) in report.dimension_scores"
          :key="key"
          :label="report.dimension_labels[key] || String(key)"
          :value="Number(score || 0)"
          show-value
        />
      </div>
    </div>

    <!-- 表达分析 -->
    <section v-if="expression" class="lz-card p-4">
      <h4 class="mb-3 text-sm text-amber-100">表达分析</h4>
      <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <div class="rounded-xl border border-white/10 p-3 text-center">
          <p class="font-mono-tech text-lg text-amber-200">{{ expression.rate }}</p>
          <p class="text-[10px] text-slate-500">字 / 分钟</p>
        </div>
        <div class="rounded-xl border border-white/10 p-3 text-center">
          <p class="font-mono-tech text-lg text-amber-200">{{ expression.fillers }}</p>
          <p class="text-[10px] text-slate-500">填充词次数</p>
        </div>
        <div class="rounded-xl border border-white/10 p-3 text-center">
          <p class="font-mono-tech text-lg text-amber-200">{{ expression.pause }}</p>
          <p class="text-[10px] text-slate-500">平均停顿占比</p>
        </div>
        <div class="rounded-xl border border-white/10 p-3 text-center">
          <p class="font-mono-tech text-lg text-amber-200">{{ expression.duration }}s</p>
          <p class="text-[10px] text-slate-500">总作答时长</p>
        </div>
      </div>
      <p class="mt-3 text-xs leading-relaxed text-slate-300">{{ expression.advice }}</p>
      <ul v-if="expression.reasons.length" class="mt-2 space-y-0.5 text-xs text-slate-500">
        <li v-for="r in expression.reasons" :key="r">· {{ r }}</li>
      </ul>
    </section>

    <!-- 岗位情报对照 -->
    <section v-if="hasIntel" class="lz-card p-4">
      <h4 class="mb-2 text-sm text-amber-100">岗位情报对照</h4>
      <p v-if="intel?.job?.summary" class="text-xs leading-relaxed text-slate-300">{{ intel.job.summary }}</p>
      <div v-if="(intel?.job?.skills || []).length" class="mt-2 flex flex-wrap gap-1.5">
        <LzBadge v-for="skill in intel!.job!.skills" :key="skill" tone="accent">{{ skill }}</LzBadge>
      </div>
      <p v-if="(intel?.topics || []).length" class="mt-2 text-xs text-slate-500">
        本场考察主题：{{ intel!.topics!.join('、') }}
      </p>
    </section>

    <div class="grid gap-3 md:grid-cols-2">
      <section class="lz-card p-4">
        <h4 class="mb-2 text-sm text-amber-100">关键问题</h4>
        <ul class="space-y-1 text-xs text-slate-400">
          <li v-for="item in report.key_issues" :key="item">· {{ item }}</li>
        </ul>
      </section>
      <section class="lz-card p-4">
        <h4 class="mb-2 text-sm text-amber-100">改进建议</h4>
        <ul class="space-y-1 text-xs text-slate-400">
          <li v-for="item in report.suggestions" :key="item">· {{ item }}</li>
        </ul>
      </section>
    </div>

    <!-- 三视角评议 -->
    <section v-if="Object.keys(report.council_views || {}).length" class="lz-card p-4">
      <h4 class="mb-3 text-sm text-amber-100">三视角评议</h4>
      <div class="grid gap-3 md:grid-cols-3">
        <article
          v-for="(view, role) in report.council_views"
          :key="role"
          class="flex flex-col rounded-xl border border-white/10 p-3"
        >
          <div class="mb-2 flex items-center gap-2">
            <span
              class="flex h-8 w-8 items-center justify-center rounded-lg border border-amber-400/25 bg-amber-400/10 text-sm text-amber-200"
              aria-hidden="true"
            >
              {{ COUNCIL_ICON[String((view as CouncilView).role || role)] || '◇' }}
            </span>
            <div>
              <p class="text-xs text-amber-200/90">{{ (view as CouncilView).role || role }}</p>
              <p class="font-mono-tech text-sm text-amber-100">{{ (view as CouncilView).score ?? '—' }}</p>
            </div>
          </div>
          <p class="flex-1 text-xs leading-relaxed text-slate-300">{{ (view as CouncilView).view }}</p>
          <ul v-if="councilIssues(view as CouncilView).length" class="mt-2 space-y-0.5 text-xs text-rose-300/80">
            <li v-for="issue in councilIssues(view as CouncilView)" :key="issue">· {{ issue }}</li>
          </ul>
        </article>
      </div>
    </section>

    <!-- 回流资源 -->
    <section v-if="report.resource_refs?.length" class="lz-card p-4">
      <h4 class="mb-2 text-sm text-amber-100">回流资源</h4>
      <p class="mb-2 text-xs text-slate-500">弱项已写入学习区错题本 / 复习队列，可回学习区继续练。</p>
      <ul class="space-y-2">
        <li
          v-for="(item, idx) in report.resource_refs"
          :key="idx"
          class="flex items-center justify-between gap-3 rounded-xl border border-white/10 px-3 py-2"
        >
          <span class="min-w-0 truncate text-xs text-slate-300">{{ refTitle(item) }}</span>
          <LzBadge tone="neutral">{{ refKind(item) }}</LzBadge>
        </li>
      </ul>
    </section>

    <p v-if="report.teacher_comment" class="lz-card p-4 text-xs text-slate-300">教师评语：{{ report.teacher_comment }}</p>

    <!-- 逐题时间线 -->
    <section v-if="detail?.turns?.length" class="space-y-2">
      <h4 class="text-sm text-slate-200">逐题回放</h4>
      <article
        v-for="turn in detail.turns"
        :key="turn.id"
        class="lz-card overflow-hidden p-0"
      >
        <button
          type="button"
          class="flex w-full items-center gap-3 p-4 text-left"
          @click="toggleTurn(turn.id)"
        >
          <InterviewScoreRing :score="turn.fused_score" :size="44" :show-grade="false" />
          <div class="min-w-0 flex-1">
            <p class="text-xs text-amber-200/80">
              第 {{ turn.turn_index + 1 }} 题
              <span v-if="turn.followup_strategy && turn.followup_strategy !== 'next'" class="ml-1 rounded bg-rose-400/15 px-1.5 py-0.5 text-[10px] text-rose-200">
                触发追问
              </span>
            </p>
            <p class="mt-0.5 truncate text-sm text-slate-100">{{ turn.question }}</p>
          </div>
          <span class="text-xs text-slate-500">{{ expandedTurn === turn.id ? '收起 ▲' : '展开 ▼' }}</span>
        </button>
        <div v-if="expandedTurn === turn.id" class="space-y-3 border-t border-white/5 p-4">
          <div class="grid gap-2 sm:grid-cols-3">
            <LzProgress
              v-for="row in modalityRows(turn)"
              :key="row.key"
              :label="row.label"
              :value="Number(row.value ?? 0)"
              show-value
            />
          </div>
          <p class="text-xs text-slate-400">转写：{{ turn.transcript || '（空）' }}</p>
          <p class="text-xs text-slate-500">{{ turn.feedback }}</p>
          <p v-if="(turn.prosody_detail?.reasons || []).length" class="text-xs text-slate-500">
            表达提示：{{ (turn.prosody_detail.reasons || []).join('；') }}
          </p>
          <audio v-if="turn.audio_url" class="w-full" controls preload="none" :src="turn.audio_url" />
          <div v-if="turn.frame_urls?.length" class="flex flex-wrap gap-2">
            <img
              v-for="url in turn.frame_urls"
              :key="url"
              :src="url"
              alt="面试关键帧"
              class="h-20 w-20 rounded-lg object-cover ring-1 ring-white/10"
            />
          </div>
        </div>
      </article>
    </section>
  </div>
  <LzEmptyState v-else title="还没有报告" desc="完成一场面试后，能力画像会显示在这里" />
</template>

<style scoped>
@media print {
  .iv-no-print {
    display: none;
  }

  .iv-report {
    color: #0f172a;
  }
}
</style>

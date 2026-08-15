<script setup lang="ts">
import * as echarts from 'echarts';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import {
  fetchLearningStory,
  fetchStudentDetail,
  fetchTeacherStudentEvaluation,
  fetchTeacherStudentLearnHeatmap,
  fetchTeacherStudentVaultFile,
  fetchTeacherStudentVaultTree,
  searchTeacherStudentVault,
  type LearningStory,
  type StudentDetail,
  type VaultTreeNode,
} from '../api/teacher';
import MarkdownView from '../components/common/MarkdownView.vue';
import PanoramicData from '../components/domain/PanoramicData.vue';
import TeacherEmptyState from '../components/teacher/TeacherEmptyState.vue';
import TeacherLoading from '../components/teacher/TeacherLoading.vue';
import TeacherStatCard from '../components/teacher/TeacherStatCard.vue';
import VaultTreeView from '../components/teacher/VaultTreeView.vue';
import { useChartTheme } from '../composables/useChartTheme';
import { useTeacherClassStore } from '../stores/teacherClass';

type DetailTab = 'overview' | 'growth' | 'vault';

const route = useRoute();
const router = useRouter();
const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);
const { chart: chartTokens } = useChartTheme();

const detail = ref<StudentDetail | null>(null);
const story = ref<LearningStory | null>(null);
const loading = ref(true);
const error = ref('');
const radarRef = ref<HTMLDivElement | null>(null);
let radar: echarts.ECharts | null = null;

const activeTab = ref<DetailTab>('overview');

const learnHeat = ref<{
  selection_ask_count: number;
  learn_heatmap_summary: {
    by_kind?: Record<string, number>;
    by_day?: Record<string, number>;
    total_evidence?: number;
  };
} | null>(null);

const evalReport = ref<{
  summary: string;
  dimensions: Record<string, unknown>;
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
  mastery_rate: number;
  quiz_accuracy: number;
  selection_ask_count: number;
  learn_heatmap_summary: {
    by_kind?: Record<string, number>;
    by_day?: Record<string, number>;
    total_evidence?: number;
  };
} | null>(null);
const evalLoading = ref(false);
const growthRadarRef = ref<HTMLDivElement | null>(null);
let growthRadar: echarts.ECharts | null = null;

const vaultTree = ref<VaultTreeNode[]>([]);
const vaultLoading = ref(false);
const vaultError = ref('');
const vaultQuery = ref('');
const vaultHits = ref<Array<{ path: string; title: string; snippet: string }>>([]);
const activeVaultPath = ref('');
const vaultFile = ref<{ path: string; title: string; content: string; body: string } | null>(null);
const vaultFileLoading = ref(false);

const heatByDay = computed(() => {
  const raw =
    evalReport.value?.learn_heatmap_summary?.by_day || learnHeat.value?.learn_heatmap_summary?.by_day;
  if (!raw || typeof raw !== 'object') return [] as Array<{ day: string; count: number }>;
  return Object.entries(raw)
    .map(([day, count]) => ({ day, count: Number(count) || 0 }))
    .filter((x) => x.day && x.day !== 'unknown')
    .slice(-14);
});
const heatMax = computed(() => Math.max(1, ...heatByDay.value.map((x) => x.count), 1));
const heatByKind = computed(() => {
  const raw =
    evalReport.value?.learn_heatmap_summary?.by_kind || learnHeat.value?.learn_heatmap_summary?.by_kind;
  if (!raw || typeof raw !== 'object') return [] as Array<{ kind: string; count: number }>;
  return Object.entries(raw)
    .map(([kind, count]) => ({ kind, count: Number(count) || 0 }))
    .filter((x) => x.count > 0)
    .sort((a, b) => b.count - a.count)
    .slice(0, 6);
});

const highlightFolders = [
  { folder: '20-Clips', label: '划词剪藏' },
  { folder: '50-Daily', label: '学习日记' },
  { folder: '70-Workshop', label: '工坊产物' },
];

function heatColor(count: number) {
  const t = Math.min(1, count / heatMax.value);
  const a = 0.12 + t * 0.75;
  return `rgb(var(--t-accent) / ${a.toFixed(2)})`;
}

const DIM_LABELS: Record<string, string> = {
  major_background: '专业背景',
  prior_knowledge: '前置知识',
  cognitive_style: '认知风格',
  mistake_tendency: '易错倾向',
  learning_goal: '学习目标',
  time_flexibility: '时间弹性',
  modality_preference: '资源模态偏好',
  motivation_level: '学习动机强度',
};

function dimScore(dims: Record<string, unknown>, key: string): number {
  const raw = dims[key];
  if (raw && typeof raw === 'object' && 'score' in raw) {
    return Number((raw as { score?: number }).score ?? 50);
  }
  if (typeof raw === 'number') return raw;
  return 50;
}

function renderRadar() {
  if (!radarRef.value || !detail.value?.profile?.dimensions) return;
  if (!radar) radar = echarts.init(radarRef.value);
  const t = chartTokens.value;
  const dims = detail.value.profile.dimensions;
  const keys = Object.keys(DIM_LABELS);
  radar.setOption({
    backgroundColor: 'transparent',
    radar: {
      indicator: keys.map((k) => ({ name: DIM_LABELS[k], max: 100 })),
      splitLine: { lineStyle: { color: t.splitLine } },
      axisName: { color: t.axisLabelStrong, fontSize: 11 },
    },
    series: [
      {
        type: 'radar',
        data: [{ value: keys.map((k) => dimScore(dims, k)), name: detail.value.display_name }],
        areaStyle: { color: t.accentSoft },
        lineStyle: { color: t.accent },
      },
    ],
  });
}

function renderGrowthRadar() {
  if (!growthRadarRef.value || !evalReport.value) return;
  if (!growthRadar) growthRadar = echarts.init(growthRadarRef.value);
  const t = chartTokens.value;
  const r = evalReport.value;
  const focusScore = Math.min(100, Number(r.dimensions?.focus_minutes || 0) / 3);
  const resourceScore = Math.min(100, Number(r.dimensions?.resource_count || 0) * 15);
  growthRadar.setOption({
    backgroundColor: 'transparent',
    radar: {
      indicator: [
        { name: '掌握率', max: 100 },
        { name: '答题正确率', max: 100 },
        { name: '专注', max: 100 },
        { name: '资源使用', max: 100 },
      ],
      splitLine: { lineStyle: { color: t.splitLine } },
      axisName: { color: t.axisLabelStrong, fontSize: 10 },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: [
              Number(r.mastery_rate) || 0,
              Number(r.quiz_accuracy) || 0,
              focusScore,
              resourceScore,
            ],
            name: '能力画像',
          },
        ],
        areaStyle: { color: t.accentSoft },
        lineStyle: { color: t.accent },
        itemStyle: { color: t.accent },
      },
    ],
  });
  growthRadar.resize();
}

function syncTabFromRoute() {
  const t = String(route.query.tab || 'overview');
  if (t === 'growth' || t === 'vault' || t === 'overview') activeTab.value = t;
}

async function load() {
  const id = route.params.id as string;
  const cid = (route.query.class_id as string) || classId.value || '';
  loading.value = true;
  error.value = '';
  detail.value = null;
  story.value = null;
  learnHeat.value = null;
  evalReport.value = null;
  vaultTree.value = [];
  vaultFile.value = null;
  activeVaultPath.value = '';
  try {
    detail.value = await fetchStudentDetail(id, cid);
    story.value = await fetchLearningStory(id, cid).catch(() => null);
    learnHeat.value = await fetchTeacherStudentLearnHeatmap(id, cid).catch(() => null);
    await nextTick();
    if (activeTab.value === 'overview') renderRadar();
    if (activeTab.value === 'growth') await loadGrowth();
    if (activeTab.value === 'vault') await loadVaultTree();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载学生详情失败';
  } finally {
    loading.value = false;
  }
}

async function loadGrowth() {
  const id = route.params.id as string;
  const cid = (route.query.class_id as string) || classId.value || '';
  evalLoading.value = true;
  try {
    evalReport.value = await fetchTeacherStudentEvaluation(id, cid);
    await nextTick();
    renderGrowthRadar();
  } catch {
    evalReport.value = null;
  } finally {
    evalLoading.value = false;
  }
}

async function loadVaultTree() {
  const id = route.params.id as string;
  const cid = (route.query.class_id as string) || classId.value || '';
  vaultLoading.value = true;
  vaultError.value = '';
  try {
    const res = await fetchTeacherStudentVaultTree(id, cid);
    vaultTree.value = res.tree || [];
  } catch (e) {
    vaultError.value = e instanceof Error ? e.message : '加载知识库失败';
    vaultTree.value = [];
  } finally {
    vaultLoading.value = false;
  }
}

async function openVaultFile(path: string) {
  if (!path) return;
  const id = route.params.id as string;
  const cid = (route.query.class_id as string) || classId.value || '';
  activeVaultPath.value = path;
  vaultFileLoading.value = true;
  try {
    vaultFile.value = await fetchTeacherStudentVaultFile(id, path, cid);
  } catch {
    vaultFile.value = null;
  } finally {
    vaultFileLoading.value = false;
  }
}

async function runVaultSearch() {
  const id = route.params.id as string;
  const cid = (route.query.class_id as string) || classId.value || '';
  try {
    const res = await searchTeacherStudentVault(id, vaultQuery.value.trim(), cid);
    vaultHits.value = res.results || [];
  } catch {
    vaultHits.value = [];
  }
}

function goBack() {
  if (window.history.length > 1) router.back();
  else void router.push('/teacher/insight');
}

function setTab(tab: DetailTab) {
  activeTab.value = tab;
  void router.replace({
    path: route.path,
    query: { ...route.query, tab },
  });
  if (tab === 'overview') void nextTick(() => renderRadar());
  if (tab === 'growth' && !evalReport.value) void loadGrowth();
  else if (tab === 'growth') void nextTick(() => renderGrowthRadar());
  if (tab === 'vault' && !vaultTree.value.length) void loadVaultTree();
}

function flattenFiles(nodes: VaultTreeNode[], acc: VaultTreeNode[] = []): VaultTreeNode[] {
  for (const n of nodes) {
    if (n.type === 'file' || (n.path && !n.children?.length)) acc.push(n);
    if (n.children?.length) flattenFiles(n.children, acc);
  }
  return acc;
}

const highlightCounts = computed(() => {
  const files = flattenFiles(vaultTree.value);
  return highlightFolders.map((h) => ({
    ...h,
    count: files.filter((f) => (f.path || '').startsWith(h.folder)).length,
  }));
});

watch(() => route.params.id, () => void load());
watch(
  () => route.query.tab,
  () => {
    syncTabFromRoute();
    if (activeTab.value === 'growth' && !evalReport.value && detail.value) void loadGrowth();
    if (activeTab.value === 'vault' && !vaultTree.value.length && detail.value) void loadVaultTree();
  },
);
watch(detail, () => {
  void nextTick(() => {
    if (activeTab.value === 'overview') renderRadar();
  });
});
watch(chartTokens, () => {
  renderRadar();
  renderGrowthRadar();
});

function onResize() {
  radar?.resize();
  growthRadar?.resize();
}

onMounted(() => {
  syncTabFromRoute();
  void load();
  window.addEventListener('resize', onResize);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize);
  radar?.dispose();
  growthRadar?.dispose();
});
</script>

<template>
  <div class="space-y-4">
    <header class="t-card glass-edge flex flex-wrap items-center justify-between gap-4 px-6 py-4">
      <div>
        <button type="button" class="text-xs text-t-accent transition hover:opacity-80" @click="goBack">← 返回</button>
        <h1 class="mt-2 text-2xl font-semibold tracking-tight text-t-1">{{ detail?.display_name ?? '学生详情' }}</h1>
        <p v-if="detail" class="mt-1 text-xs text-t-3">@{{ detail.username }}</p>
      </div>
      <div v-if="detail" class="flex items-center gap-3">
        <TeacherStatCard label="掌握率" :value="`${detail.mastery_rate}%`" accent="emerald" class="!p-3 min-w-[100px]" />
        <TeacherStatCard label="专注分钟" :value="detail.focus_minutes" accent="sky" class="!p-3 min-w-[100px]" />
        <button
          type="button"
          class="t-btn t-btn--soft t-btn--sm"
          @click="router.push({ path: '/teacher/messages', query: { student_id: detail.user_id } })"
        >
          发私信
        </button>
      </div>
    </header>

    <div class="t-tabs">
      <button
        v-for="t in [
          { key: 'overview', label: '概览' },
          { key: 'growth', label: '成长评估' },
          { key: 'vault', label: '知识库' },
        ]"
        :key="t.key"
        type="button"
        class="t-tab"
        :class="{ 'is-active': activeTab === t.key }"
        @click="setTab(t.key as DetailTab)"
      >
        {{ t.label }}
      </button>
    </div>

    <TeacherLoading v-if="loading" :rows="5" />
    <p v-else-if="error" class="rounded-xl border border-t-danger/30 bg-t-danger/10 px-4 py-3 text-sm text-t-danger">{{ error }}</p>

    <template v-else-if="detail">
      <!-- 概览 -->
      <template v-if="activeTab === 'overview'">
        <section v-if="story" class="t-card glass-edge border-t-accent/20 p-5">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 class="text-[15px] font-semibold text-t-1">可解释学情条</h2>
              <p class="mt-2 text-sm leading-relaxed text-t-2">{{ story.narrative }}</p>
            </div>
            <div v-if="story.action_hints?.length" class="flex flex-wrap gap-2">
              <span v-for="h in story.action_hints" :key="h" class="t-badge t-badge--warn">
                {{ h }}
              </span>
            </div>
          </div>
          <div class="mt-4 grid gap-4 lg:grid-cols-3">
            <div>
              <p class="text-[11px] uppercase tracking-wide text-t-3">闸门卡点</p>
              <ul class="mt-2 space-y-1.5 text-xs text-t-2">
                <li v-for="g in story.gate_progress.filter((x) => !x.lit).slice(0, 5)" :key="g.planet_slug">
                  {{ g.planet_name }}
                  <span class="text-t-accent">→ {{ g.next_gate || '—' }}</span>
                  <span v-if="g.decay_state" class="ml-1 text-t-warn">({{ g.decay_state }})</span>
                </li>
                <li v-if="!story.gate_progress.some((x) => !x.lit)" class="text-t-3">全部已点亮或暂无记录</li>
              </ul>
            </div>
            <div>
              <p class="text-[11px] uppercase tracking-wide text-t-3">最近 Agent</p>
              <ul class="mt-2 space-y-1.5 text-xs text-t-2">
                <li v-for="r in story.recent_agent_runs.slice(0, 4)" :key="r.id">
                  <span class="text-t-accent">{{ r.mode || r.scene }}</span>
                  · {{ r.topic || '未命名' }}
                  <span class="text-t-3">({{ r.status }})</span>
                </li>
                <li v-if="!story.recent_agent_runs.length" class="text-t-3">暂无运行</li>
              </ul>
            </div>
            <div>
              <p class="text-[11px] uppercase tracking-wide text-t-3">Shield 待审</p>
              <ul class="mt-2 space-y-1.5 text-xs text-t-2">
                <li v-for="t in story.pending_tickets.slice(0, 4)" :key="t.id">
                  {{ t.planet_name || t.planet_slug || '未知行星' }}
                  · 置信 {{ Math.round((t.confidence || 0) * 100) }}%
                </li>
                <li v-if="!story.pending_tickets.length" class="text-t-3">无待审工单</li>
              </ul>
              <p v-if="story.review_planets?.length" class="mt-3 text-[11px] text-t-warn">
                复习预警 {{ story.review_planets.length }} 颗：
                {{ story.review_planets.slice(0, 3).map((p) => p.planet_name).join('、') }}
              </p>
            </div>
          </div>
        </section>

        <div class="grid gap-4 xl:grid-cols-2">
          <section class="t-card glass-edge p-5">
            <h2 class="text-[15px] font-semibold text-t-1">六维画像</h2>
            <p class="mt-2 text-sm text-t-2">{{ detail.profile?.summary || '暂无摘要' }}</p>
            <div v-if="detail.profile?.dimensions" ref="radarRef" class="mt-3 h-64 w-full"></div>
            <TeacherEmptyState v-else class="mt-4" title="暂无画像数据" />
          </section>

          <section class="t-card glass-edge p-5">
            <h2 class="text-[15px] font-semibold text-t-1">学闸学习热力</h2>
            <p class="mt-1 text-[11px] text-t-3">
              划词提问 {{ learnHeat?.selection_ask_count ?? 0 }} 次 · 证据合计
              {{ learnHeat?.learn_heatmap_summary?.total_evidence ?? 0 }} 条
            </p>
            <div v-if="heatByDay.length" class="mt-3 flex flex-wrap gap-1.5">
              <div
                v-for="cell in heatByDay"
                :key="cell.day"
                class="group relative flex h-9 min-w-[2.25rem] flex-1 flex-col items-center justify-end rounded-md border border-t-line/10"
                :style="{ backgroundColor: heatColor(cell.count) }"
                :title="`${cell.day} · ${cell.count} 条`"
              >
                <span class="pb-0.5 text-[9px] text-t-1/90">{{ cell.count }}</span>
              </div>
            </div>
            <TeacherEmptyState v-else class="mt-3" title="暂无学闸证据热力" description="学生划词提问或演武/笔记后可见" />
            <ul v-if="heatByKind.length" class="mt-4 flex flex-wrap gap-2">
              <li v-for="k in heatByKind" :key="k.kind" class="t-badge t-badge--neutral">
                {{ k.kind }} · {{ k.count }}
              </li>
            </ul>
          </section>
        </div>

        <section class="t-card glass-edge p-5">
          <PanoramicData :student-id="detail.user_id" :class-id="detail.class_id || classId || ''" />
        </section>

        <section class="t-card glass-edge p-5">
          <h2 class="text-[15px] font-semibold text-t-1">行星掌握明细</h2>
          <div class="mt-3 flex flex-wrap gap-2">
            <span
              v-for="m in detail.mastery"
              :key="m.planet_slug"
              class="rounded-lg border px-2 py-1 text-xs"
              :class="m.status === 'lit' ? 'border-t-ok/30 bg-t-ok/8 text-t-ok' : 'border-t-line/10 text-t-3'"
            >
              {{ m.planet_name }} {{ Math.round(m.score) }}%
            </span>
          </div>
          <TeacherEmptyState v-if="!detail.mastery.length" class="mt-3" title="暂无掌握记录" />
        </section>

        <div class="grid gap-4 xl:grid-cols-2">
          <section class="t-card glass-edge p-5">
            <h2 class="text-[15px] font-semibold text-t-1">干预记录</h2>
            <div class="mt-3 space-y-2">
              <div v-for="a in detail.alerts" :key="a.id" class="rounded-xl border border-t-line/10 bg-t-s1/30 px-4 py-2 text-xs text-t-2">
                <span class="text-t-accent">{{ a.type }}</span> · {{ a.message.slice(0, 120) }}
              </div>
              <TeacherEmptyState v-if="!detail.alerts.length" title="暂无干预记录" />
            </div>
          </section>

          <section class="t-card glass-edge p-5">
            <h2 class="text-[15px] font-semibold text-t-1">错题本</h2>
            <div class="mt-3 space-y-2">
              <div v-for="m in detail.mistakes" :key="m.id" class="rounded-xl border border-t-line/10 bg-t-s1/30 px-4 py-2 text-xs text-t-2">
                [{{ m.subject || '未分类' }}] {{ m.question.slice(0, 100) }}
              </div>
              <TeacherEmptyState v-if="!detail.mistakes.length" title="暂无错题" />
            </div>
          </section>
        </div>

        <section class="t-card glass-edge p-5">
          <h2 class="text-[15px] font-semibold text-t-1">作业提交</h2>
          <div class="mt-3 space-y-2">
            <div
              v-for="(a, i) in detail.assignments"
              :key="i"
              class="flex justify-between rounded-xl border border-t-line/10 bg-t-s1/30 px-4 py-2 text-xs"
            >
              <span class="font-medium text-t-1">{{ a.assignment_title }}</span>
              <span class="text-t-3">{{ a.status }} · {{ a.score ?? '—' }}</span>
            </div>
            <TeacherEmptyState v-if="!detail.assignments.length" title="暂无作业提交" />
          </div>
        </section>
      </template>

      <!-- 成长评估 -->
      <template v-else-if="activeTab === 'growth'">
        <TeacherLoading v-if="evalLoading" :rows="4" />
        <template v-else-if="evalReport">
          <section class="t-card glass-edge p-5">
            <p class="t-kicker">Growth Report</p>
            <h2 class="mt-1 text-[15px] font-semibold text-t-1">成长评估（只读）</h2>
            <p class="mt-2 text-sm leading-6 text-t-2">{{ evalReport.summary }}</p>
            <div class="mt-4 grid gap-3 sm:grid-cols-3">
              <TeacherStatCard label="掌握率" :value="`${evalReport.mastery_rate}%`" accent="emerald" />
              <TeacherStatCard label="正确率" :value="`${evalReport.quiz_accuracy}%`" accent="sky" />
              <TeacherStatCard label="划词提问" :value="evalReport.selection_ask_count" accent="amber" />
            </div>
          </section>

          <div class="grid gap-4 xl:grid-cols-2">
            <section class="t-card glass-edge p-5">
              <h3 class="text-sm font-semibold text-t-1">能力雷达</h3>
              <div ref="growthRadarRef" class="mt-2 h-52 w-full" />
            </section>

            <section class="t-card glass-edge p-5">
              <h3 class="text-sm font-semibold text-t-1">学习热力 · 学闸证据</h3>
              <p class="mt-1 text-[11px] text-t-3">
                证据合计 {{ evalReport.learn_heatmap_summary?.total_evidence ?? 0 }} 条
              </p>
              <div v-if="heatByDay.length" class="mt-3 flex flex-wrap gap-1.5">
                <div
                  v-for="cell in heatByDay"
                  :key="cell.day"
                  class="flex h-9 min-w-[2.25rem] flex-1 flex-col items-center justify-end rounded-md border border-t-line/10"
                  :style="{ backgroundColor: heatColor(cell.count) }"
                  :title="`${cell.day} · ${cell.count}`"
                >
                  <span class="pb-0.5 text-[9px] text-t-1/90">{{ cell.count }}</span>
                </div>
              </div>
              <ul v-if="heatByKind.length" class="mt-4 flex flex-wrap gap-2">
                <li v-for="k in heatByKind" :key="k.kind" class="t-badge t-badge--neutral">
                  {{ k.kind }} · {{ k.count }}
                </li>
              </ul>
            </section>
          </div>

          <div class="grid gap-4 md:grid-cols-3">
            <section class="t-card glass-edge p-5">
              <h3 class="text-sm font-semibold text-t-ok">优势</h3>
              <ul class="mt-2 list-disc space-y-1 pl-5 text-xs text-t-2">
                <li v-for="(s, i) in evalReport.strengths" :key="i">{{ s }}</li>
              </ul>
              <TeacherEmptyState v-if="!evalReport.strengths?.length" class="mt-2" title="暂无" />
            </section>
            <section class="t-card glass-edge p-5">
              <h3 class="text-sm font-semibold text-t-warn">待提升</h3>
              <ul class="mt-2 list-disc space-y-1 pl-5 text-xs text-t-2">
                <li v-for="(s, i) in evalReport.weaknesses" :key="i">{{ s }}</li>
              </ul>
              <TeacherEmptyState v-if="!evalReport.weaknesses?.length" class="mt-2" title="暂无" />
            </section>
            <section class="t-card glass-edge p-5">
              <h3 class="text-sm font-semibold text-t-accent">改进建议</h3>
              <ul class="mt-2 list-disc space-y-1 pl-5 text-xs text-t-2">
                <li v-for="(s, i) in evalReport.suggestions" :key="i">{{ s }}</li>
              </ul>
              <TeacherEmptyState v-if="!evalReport.suggestions?.length" class="mt-2" title="暂无" />
            </section>
          </div>
        </template>
        <TeacherEmptyState v-else title="暂无成长评估数据" />
      </template>

      <!-- 知识库只读 -->
      <template v-else>
        <section class="t-card glass-edge p-5">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 class="text-[15px] font-semibold text-t-1">星轨知识库（只读）</h2>
              <p class="mt-1 text-[11px] text-t-3">可浏览划词剪藏、学习日记、工坊产物等，不可编辑</p>
            </div>
            <div class="flex gap-2">
              <input v-model="vaultQuery" placeholder="搜索笔记标题…" class="t-input w-52 py-1.5" @keyup.enter="runVaultSearch" />
              <button type="button" class="t-btn t-btn--ghost t-btn--sm" @click="runVaultSearch">搜索</button>
            </div>
          </div>
          <div class="mt-3 flex flex-wrap gap-2">
            <span v-for="h in highlightCounts" :key="h.folder" class="t-badge t-badge--neutral">
              {{ h.label }} · {{ h.count }}
            </span>
          </div>
        </section>

        <TeacherLoading v-if="vaultLoading" :rows="4" />
        <p v-else-if="vaultError" class="rounded-xl border border-t-danger/30 bg-t-danger/10 px-4 py-3 text-sm text-t-danger">
          {{ vaultError }}
        </p>

        <section v-else class="t-card glass-edge grid gap-4 p-5 lg:grid-cols-[300px_1fr]">
          <div class="max-h-[560px] space-y-1 overflow-y-auto">
            <template v-if="vaultHits.length && vaultQuery.trim()">
              <p class="mb-2 text-[11px] text-t-3">搜索结果</p>
              <button
                v-for="hit in vaultHits"
                :key="hit.path"
                type="button"
                class="block w-full rounded-lg border px-3 py-2 text-left text-xs transition"
                :class="
                  activeVaultPath === hit.path
                    ? 'border-t-accent/40 bg-t-accent/10 text-t-1'
                    : 'border-t-line/10 text-t-2 hover:bg-t-line/5'
                "
                @click="openVaultFile(hit.path)"
              >
                <p class="truncate">{{ hit.title || hit.path }}</p>
                <p class="mt-0.5 truncate text-[10px] text-t-3">{{ hit.path }}</p>
              </button>
            </template>
            <template v-else>
              <VaultTreeView :nodes="vaultTree" :active-path="activeVaultPath" @open="openVaultFile" />
              <TeacherEmptyState v-if="!vaultTree.length" title="知识库为空" />
            </template>
          </div>
          <div class="min-h-[360px]">
            <TeacherLoading v-if="vaultFileLoading" :rows="3" />
            <template v-else-if="vaultFile">
              <h3 class="text-sm font-semibold text-t-1">{{ vaultFile.title || vaultFile.path }}</h3>
              <p class="mt-1 font-mono-tech text-[10px] text-t-3">{{ vaultFile.path }}</p>
              <div class="t-card--flat mt-3 max-h-[520px] overflow-y-auto rounded-xl border border-t-line/10 p-4">
                <MarkdownView :content="vaultFile.body || vaultFile.content" />
              </div>
            </template>
            <TeacherEmptyState v-else title="选择左侧笔记预览" description="仅支持只读浏览" />
          </div>
        </section>
      </template>
    </template>
  </div>
</template>

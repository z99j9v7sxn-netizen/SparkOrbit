<script setup lang="ts">
import * as echarts from 'echarts';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import {
  extractProfile,
  fetchImprovementPlans,
  fetchProfileEvidence,
  fetchProfileHistory,
  fetchProfileMeta,
  submitImprovement,
  syncRemediationToPath,
  updateImprovementStep,
  type ChatMessage,
  type DimensionProfile,
  type ProfileEvidenceItem,
  type ProfileHistoryItem,
  type ProfileWarning,
  type RemediationPlanView,
  type StudentProfileExtract,
} from '../api/profiles';
import { generateLearningPath, refreshProfileManual } from '../api/learnExtras';
import { parseApiError } from '../api/errors';
import { useAuthStore } from '../stores/auth';
import { LzBadge, LzButton, LzEmptyState, LzSection, LzSkeleton, LzTabs } from './learning/ui';
import MirrorDimensionMeter from './mirror/MirrorDimensionMeter.vue';
import MirrorHistoryTimeline from './mirror/MirrorHistoryTimeline.vue';
import { cleanSummaryText } from './mirror/profileText';

type DimensionKey =
  | 'major_background'
  | 'prior_knowledge'
  | 'cognitive_style'
  | 'mistake_tendency'
  | 'learning_goal'
  | 'time_flexibility'
  | 'modality_preference'
  | 'motivation_level';

interface DimensionState {
  key: DimensionKey;
  label: string;
  score: number;
  status: string;
  evidence: string[];
}

interface SimSummary {
  topic: string;
  pathSteps: string[];
  rootCause: string;
}

const props = withDefaults(defineProps<{ simSummary?: SimSummary | null }>(), { simSummary: null });

const DIMENSION_LABELS: Record<DimensionKey, string> = {
  major_background: '专业背景',
  prior_knowledge: '前置知识',
  cognitive_style: '认知风格',
  mistake_tendency: '易错倾向',
  learning_goal: '学习目标',
  time_flexibility: '时间弹性',
  modality_preference: '资源模态偏好',
  motivation_level: '学习动机强度',
};

const DIMENSION_SHORT: Record<DimensionKey, string> = {
  major_background: '专业',
  prior_knowledge: '前置',
  cognitive_style: '认知',
  mistake_tendency: '易错',
  learning_goal: '目标',
  time_flexibility: '时间',
  modality_preference: '模态',
  motivation_level: '动机',
};

const GRADE_LABEL: Record<string, string> = {
  excellent: '优秀',
  pass: '合格',
  fail: '不合格',
};

const emit = defineEmits<{
  (e: 'simulate', payload: string | { topic: string; targetDimension?: string }): void;
}>();

const auth = useAuthStore();
const chartRef = ref<HTMLDivElement | null>(null);
const trendRef = ref<HTMLDivElement | null>(null);
const streamText = ref('等待画像抽取…');
const loading = ref(false);
const historyLoading = ref(false);
const chatInput = ref('');
const chatMessages = ref<ChatMessage[]>([
  { role: 'assistant', content: '你好，我是画像采集助手。可以先说说你的专业、已学内容和最近的学习目标吗？' },
]);
const extractionSummary = ref('');
const followUps = ref<string[]>([]);
const profileHistory = ref<ProfileHistoryItem[]>([]);
const currentProfile = ref<StudentProfileExtract | null>(null);
const panelTab = ref<'overview' | 'collect' | 'history'>('overview');
const collectSubTab = ref<'initial' | 'improve'>('initial');
const selectedDim = ref<DimensionState | null>(null);
const lastSimSummary = ref<SimSummary | null>(null);
const hasRealProfile = ref(false);
const profileWarnings = ref<ProfileWarning[]>([]);
const improvementPlans = ref<RemediationPlanView[]>([]);
const plansLoading = ref(false);
const reflectionDrafts = ref<Record<string, string>>({});
const submittingPlanId = ref<string | null>(null);
const improveMsg = ref('');
const evidenceItems = ref<ProfileEvidenceItem[]>([]);
const evidenceLoading = ref(false);
const evidenceDim = ref<DimensionKey | ''>('');
const lastSources = ref<Record<string, string>>({});
const layerSummaries = ref<Record<string, string>>({});
const layerCounts = ref<Record<string, number>>({});
const pendingEvents = ref(0);
const updateSource = ref('');
const dimensions = ref<DimensionState[]>([
  { key: 'major_background', label: '专业背景', score: 68, status: '基础较明确', evidence: [] },
  { key: 'prior_knowledge', label: '前置知识', score: 55, status: '仍需补强', evidence: [] },
  { key: 'cognitive_style', label: '认知风格', score: 78, status: '偏结构化', evidence: [] },
  { key: 'mistake_tendency', label: '易错倾向', score: 42, status: '存在遗漏风险', evidence: [] },
  { key: 'learning_goal', label: '学习目标', score: 82, status: '目标清晰', evidence: [] },
  { key: 'time_flexibility', label: '时间弹性', score: 61, status: '较为稳定', evidence: [] },
  { key: 'modality_preference', label: '资源模态偏好', score: 50, status: '待补充', evidence: [] },
  { key: 'motivation_level', label: '学习动机强度', score: 50, status: '待补充', evidence: [] },
]);

let chart: echarts.ECharts | null = null;
let trendChart: echarts.ECharts | null = null;
let eventSource: EventSource | null = null;
let resizeObserver: ResizeObserver | null = null;

const syncRate = computed(() => {
  if (!hasRealProfile.value) return 0;
  const total = dimensions.value.reduce((sum, item) => sum + item.score, 0);
  return Math.round((total / (dimensions.value.length * 100)) * 100);
});

const weakDimensions = computed(() => {
  if (!hasRealProfile.value) return [];
  return dimensions.value.filter((d) => d.score < 60).sort((a, b) => a.score - b.score);
});

const focusWeakDims = computed(() => weakDimensions.value.slice(0, 2));
const moreWeakDims = computed(() => weakDimensions.value.slice(2));

const sortedDimensions = computed(() =>
  [...dimensions.value].sort((a, b) => a.score - b.score),
);

const personaBrief = computed(() => {
  const raw = cleanSummaryText(extractionSummary.value);
  if (raw) return raw.length > 40 ? `${raw.slice(0, 40)}…` : raw;
  if (!hasRealProfile.value) return '尚未采集画像，先聊聊专业与目标';
  return '画像已落库，可针对薄弱维发起预演';
});

const hasUsefulSummary = computed(() => Boolean(cleanSummaryText(extractionSummary.value)));

const openPlans = computed(() =>
  improvementPlans.value.filter((p) => p.status === 'open' || (p.submission?.final_grade === 'fail' && !p.submission?.teacher_reviewed)),
);

const detailsOpen = ref(false);
const moreWeakOpen = ref(false);
const expandedDimKey = ref<DimensionKey | ''>('');
const preferReducedMotion = ref(false);

function toggleDimExpand(key: DimensionKey) {
  expandedDimKey.value = expandedDimKey.value === key ? '' : key;
}

function primaryHeroAction() {
  if (!hasRealProfile.value) {
    panelTab.value = 'collect';
    collectSubTab.value = 'initial';
    return;
  }
  const top = focusWeakDims.value[0];
  if (top) triggerSim(top);
  else void handleRepath();
}

function recallHistoryVersion(item: ProfileHistoryItem) {
  updateRadar(profileFromHistory(item), cleanSummaryText(item.summary) || '已载入该历史版本');
  panelTab.value = 'overview';
  void nextTickResize();
}

function goOverviewForSim() {
  panelTab.value = 'overview';
}

function dimFromProfile(key: DimensionKey, profile: StudentProfileExtract): DimensionProfile {
  return profile[key];
}

function profileFromHistory(item: ProfileHistoryItem): StudentProfileExtract {
  const dim = (key: DimensionKey, textKey: keyof ProfileHistoryItem, scoreKey: keyof ProfileHistoryItem) => ({
    value: String(item[textKey] || '待补充'),
    score: Number(item[scoreKey] ?? 0) || 50,
    evidence: [] as string[],
  });
  return {
    student_name: item.student_name,
    major_background: dim('major_background', 'major_background', 'major_background_score'),
    prior_knowledge: dim('prior_knowledge', 'prior_knowledge', 'prior_knowledge_score'),
    cognitive_style: dim('cognitive_style', 'cognitive_style', 'cognitive_style_score'),
    mistake_tendency: dim('mistake_tendency', 'mistake_tendency', 'mistake_tendency_score'),
    learning_goal: dim('learning_goal', 'learning_goal', 'learning_goal_score'),
    time_flexibility: dim('time_flexibility', 'time_flexibility', 'time_flexibility_score'),
    modality_preference: dim('modality_preference', 'modality_preference', 'modality_preference_score'),
    motivation_level: dim('motivation_level', 'motivation_level', 'motivation_level_score'),
    missing_dimensions: [],
    follow_up_questions: [],
    summary: item.summary,
  };
}

function updateRadar(profile: StudentProfileExtract, thought?: string) {
  currentProfile.value = profile;
  dimensions.value = (Object.keys(DIMENSION_LABELS) as DimensionKey[]).map((key) => {
    const dim = dimFromProfile(key, profile);
    return {
      key,
      label: DIMENSION_LABELS[key],
      score: dim.score,
      status: dim.value || '待补充',
      evidence: dim.evidence || [],
    };
  });
  applyRadarOption();
  extractionSummary.value = profile.summary;
  followUps.value = profile.follow_up_questions;
  hasRealProfile.value = true;
  if (thought) streamText.value = thought;
}

function radarIndicators() {
  return dimensions.value.map((item) => ({
    name: DIMENSION_SHORT[item.key],
    max: 100,
    // custom field for tooltip via formatter
    fullName: item.label,
    score: item.score,
  }));
}

function applyRadarOption() {
  if (!chart) return;
  const scores = dimensions.value.map((item) => item.score);
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: () =>
        dimensions.value
          .map((d) => `${d.label}：${d.score}`)
          .join('<br/>'),
    },
    radar: {
      radius: '68%',
      center: ['50%', '52%'],
      splitNumber: 4,
      axisName: {
        color: '#bae6fd',
        fontSize: 11,
        fontWeight: 600,
        formatter: (name: string) => {
          const dim = dimensions.value.find((d) => DIMENSION_SHORT[d.key] === name);
          if (!dim) return name;
          return dim.score < 60 ? `{weak|${name}}` : `{ok|${name}}`;
        },
        rich: {
          weak: { color: '#fbbf24', fontWeight: 700, fontSize: 11 },
          ok: { color: '#bae6fd', fontWeight: 600, fontSize: 11 },
        },
      },
      axisLine: { lineStyle: { color: 'rgba(125, 211, 252, 0.28)' } },
      splitLine: { lineStyle: { color: 'rgba(125, 211, 252, 0.16)' } },
      splitArea: {
        show: true,
        areaStyle: {
          color: ['rgba(14, 165, 233, 0.04)', 'rgba(14, 165, 233, 0.01)'],
        },
      },
      indicator: radarIndicators(),
    },
    series: [
      {
        type: 'radar',
        symbol: 'circle',
        symbolSize: 6,
        data: [
          {
            value: scores,
            name: '画像',
            areaStyle: {
              color: preferReducedMotion.value
                ? 'rgba(56, 189, 248, 0.22)'
                : {
                    type: 'radial',
                    x: 0.5,
                    y: 0.5,
                    r: 0.7,
                    colorStops: [
                      { offset: 0, color: 'rgba(56, 189, 248, 0.38)' },
                      { offset: 1, color: 'rgba(16, 185, 129, 0.08)' },
                    ],
                  },
            },
            lineStyle: { color: '#38bdf8', width: 2 },
            itemStyle: { color: '#38bdf8' },
          },
        ],
      },
    ],
  });
}

function renderRadar() {
  if (!chartRef.value) return;
  chart?.dispose();
  chart = echarts.init(chartRef.value);
  applyRadarOption();
  chart.off('click');
  chart.on('click', (params: { componentType?: string; dataIndex?: number; name?: string }) => {
    if (typeof params.dataIndex === 'number' && dimensions.value[params.dataIndex]) {
      const dim = dimensions.value[params.dataIndex];
      openDimension(dim);
      expandedDimKey.value = dim.key;
      return;
    }
    const name = String(params?.name || '');
    const byShort = dimensions.value.find((d) => DIMENSION_SHORT[d.key] === name);
    if (byShort) {
      openDimension(byShort);
      expandedDimKey.value = byShort.key;
    }
  });
}

function renderTrend() {
  if (!trendRef.value || profileHistory.value.length < 2) return;
  trendChart?.dispose();
  trendChart = echarts.init(trendRef.value);
  const ordered = [...profileHistory.value].reverse().slice(-8);
  const labels = ordered.map((item, i) => {
    if (item.created_at) {
      const d = new Date(item.created_at);
      return `${d.getMonth() + 1}/${d.getDate()}`;
    }
    return `#${i + 1}`;
  });
  const seriesKeys: { key: keyof ProfileHistoryItem; name: string; color: string }[] = [
    { key: 'prior_knowledge_score', name: '前置知识', color: '#38bdf8' },
    { key: 'mistake_tendency_score', name: '易错倾向', color: '#f472b6' },
    { key: 'learning_goal_score', name: '学习目标', color: '#a78bfa' },
  ];
  trendChart.setOption({
    backgroundColor: 'transparent',
    legend: { bottom: 0, textStyle: { color: '#94a3b8', fontSize: 10 } },
    grid: { left: 28, right: 12, top: 16, bottom: 36 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: labels, axisLabel: { color: '#94a3b8', fontSize: 10 } },
    yAxis: { type: 'value', min: 0, max: 100, axisLabel: { color: '#64748b', fontSize: 10 }, splitLine: { lineStyle: { color: 'rgba(148,163,184,0.12)' } } },
    series: seriesKeys.map((s) => ({
      name: s.name,
      type: 'line',
      smooth: true,
      symbolSize: 6,
      lineStyle: { width: 2, color: s.color },
      itemStyle: { color: s.color },
      data: ordered.map((item) => Number(item[s.key] ?? 0)),
    })),
  });
}

const refreshMsg = ref('');
const repathMsg = ref('');
const repathLoading = ref(false);
const syncPathMsg = ref('');

async function handleProfileRefresh() {
  refreshMsg.value = '';
  repathMsg.value = '';
  try {
    const res = await refreshProfileManual();
    refreshMsg.value = res.message;
    await loadHistory();
    await loadMeta();
    repathMsg.value = '画像已更新，可一键重排学习路径';
  } catch {
    refreshMsg.value = '画像刷新失败';
  }
}

async function handleRepath() {
  repathLoading.value = true;
  repathMsg.value = '';
  try {
    await generateLearningPath('', true);
    repathMsg.value = '学习路径已按最新画像重排';
    window.dispatchEvent(new CustomEvent('sparkorbit:open-dock', { detail: { dock: 'path' } }));
  } catch (err) {
    repathMsg.value = parseApiError(err, '路径重排失败');
  } finally {
    repathLoading.value = false;
  }
}

async function handleSyncPlanToPath(planId: string) {
  syncPathMsg.value = '';
  try {
    const res = await syncRemediationToPath(planId);
    syncPathMsg.value = res.message;
    window.dispatchEvent(new CustomEvent('sparkorbit:open-dock', { detail: { dock: 'path' } }));
  } catch (err) {
    syncPathMsg.value = parseApiError(err, '同步路径失败');
  }
}

async function loadMeta() {
  try {
    const meta = await fetchProfileMeta();
    profileWarnings.value = (meta.warnings || []) as ProfileWarning[];
    lastSources.value = meta.last_sources || {};
    layerSummaries.value = meta.layer_summaries || {};
    layerCounts.value = meta.layers || {};
    pendingEvents.value = meta.pending_events || 0;
    updateSource.value = meta.update_source || '';
    if (meta.has_profile) {
      hasRealProfile.value = true;
    }
  } catch {
    profileWarnings.value = [];
  }
}

async function loadEvidence(dimension: DimensionKey | '' = '') {
  evidenceLoading.value = true;
  evidenceDim.value = dimension;
  try {
    const res = await fetchProfileEvidence(dimension);
    evidenceItems.value = res.items || [];
  } catch {
    evidenceItems.value = [];
  } finally {
    evidenceLoading.value = false;
  }
}

function sourceLabel(key: string): string {
  const map: Record<string, string> = {
    profiler: '对话',
    auto_refresh: '随学随新',
    vault_analyze: '知识库 AI',
    improvement: '改进闭环',
    challenge: '挑战',
    workshop: '工坊入库',
  };
  return map[key] || key;
}

function relativeSourceTime(iso?: string): string {
  if (!iso) return '未更新';
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso.slice(0, 16);
  const m = Math.floor((Date.now() - t) / 60000);
  if (m < 1) return '刚刚';
  if (m < 60) return `${m} 分钟前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} 小时前`;
  return `${Math.floor(h / 24)} 天前`;
}

function openDimension(item: DimensionState) {
  selectedDim.value = item;
  void loadEvidence(item.key);
}

async function loadPlans() {
  plansLoading.value = true;
  try {
    improvementPlans.value = await fetchImprovementPlans();
  } catch {
    improvementPlans.value = [];
  } finally {
    plansLoading.value = false;
  }
}

async function loadHistory() {
  historyLoading.value = true;
  try {
    profileHistory.value = await fetchProfileHistory();
    if (profileHistory.value.length && !currentProfile.value) {
      const latest = profileHistory.value[0];
      updateRadar(profileFromHistory(latest), latest.summary || '已加载历史画像');
    } else if (!profileHistory.value.length) {
      hasRealProfile.value = false;
    } else if (profileHistory.value.length && currentProfile.value) {
      const latest = profileHistory.value[0];
      updateRadar(profileFromHistory(latest));
    }
    renderTrend();
  } finally {
    historyLoading.value = false;
  }
}

async function submitInterview() {
  const text = chatInput.value.trim();
  if (!text) return;
  chatMessages.value.push({ role: 'user', content: text });
  chatInput.value = '';
  loading.value = true;
  try {
    const result = await extractProfile(auth.user?.displayName ?? '星轨学习者', chatMessages.value);
    updateRadar(result.profile, '画像已更新，可继续回答追问以完善维度。');
    if (result.raw?.warnings) {
      profileWarnings.value = result.raw.warnings as ProfileWarning[];
    }
    const asked = new Set(
      chatMessages.value.filter((m) => m.role === 'assistant').map((m) => m.content.trim()),
    );
    const nextFollowUp = (result.profile.follow_up_questions || []).find((q) => q && !asked.has(q.trim()));
    if (nextFollowUp) {
      chatMessages.value.push({
        role: 'assistant',
        content: nextFollowUp,
      });
    } else {
      chatMessages.value.push({
        role: 'assistant',
            content: '画像已更新，可在概览页查看八维雷达，随后发起推演。',
      });
    }
    await loadHistory();
    await loadMeta();
  } catch (error) {
    const msg = parseApiError(error, '画像抽取失败，请检查网络后重试。');
    streamText.value = msg;
    const isServerFault =
      /internal server error|502|503|504|落库失败|抽取失败/i.test(msg) ||
      /OperationalError|Unknown column/i.test(msg);
    chatMessages.value.push({
      role: 'assistant',
      content: isServerFault
        ? `抽取未成功：${msg}。这是服务端问题，不是你的关键词不够。请稍后重试；若持续失败请重启后端后再试。`
        : `抽取未成功：${msg}。可再补充专业、已学内容和学习目标后点击「发送并更新画像」。`,
    });
  } finally {
    loading.value = false;
  }
}

function useFollowUp(q: string) {
  chatInput.value = q;
  panelTab.value = 'collect';
  collectSubTab.value = 'initial';
}

function triggerSim(dim: DimensionState) {
  if (!hasRealProfile.value) {
    streamText.value = '请先完成学生画像抽取后再发起推演。';
    panelTab.value = 'collect';
    collectSubTab.value = 'initial';
    return;
  }
  emit('simulate', {
    topic: `${dim.label}认知澄清：${dim.status}`,
    targetDimension: dim.key,
  });
}

async function saveStepEvidence(plan: RemediationPlanView, stepIndex: number, evidence: string) {
  improveMsg.value = '';
  try {
    const updated = await updateImprovementStep(plan.id, stepIndex, {
      evidence_text: evidence,
      done: evidence.trim().length > 0,
    });
    const idx = improvementPlans.value.findIndex((p) => p.id === plan.id);
    if (idx >= 0) improvementPlans.value[idx] = updated;
  } catch (e) {
    improveMsg.value = e instanceof Error ? e.message : '步骤保存失败';
  }
}

async function handleSubmitImprovement(plan: RemediationPlanView) {
  improveMsg.value = '';
  submittingPlanId.value = plan.id;
  try {
    const reflection = (reflectionDrafts.value[plan.id] || '').trim();
    const updated = await submitImprovement(plan.id, reflection);
    const idx = improvementPlans.value.findIndex((p) => p.id === plan.id);
    if (idx >= 0) improvementPlans.value[idx] = updated;
    improveMsg.value = `已评分：${GRADE_LABEL[updated.submission?.final_grade || ''] || updated.submission?.final_grade}`;
    await loadHistory();
    await loadMeta();
  } catch (e) {
    improveMsg.value = e instanceof Error ? e.message : '提交失败';
  } finally {
    submittingPlanId.value = null;
  }
}

function connectProfileStream() {
  eventSource = new EventSource('/api/profiles/stream');
  eventSource.onmessage = (event) => {
    const payload = JSON.parse(event.data) as { thought?: string };
    if (payload.thought) streamText.value = payload.thought;
  };
  eventSource.onerror = () => {
    eventSource?.close();
  };
}

function resizeCharts() {
  chart?.resize();
  trendChart?.resize();
}

watch(panelTab, (tab) => {
  if (tab === 'overview') {
    void nextTickResize();
  }
  if (tab === 'history') renderTrend();
  if (tab === 'collect') void loadPlans();
});

watch(collectSubTab, (tab) => {
  if (tab === 'improve') void loadPlans();
});

function nextTickResize() {
  requestAnimationFrame(resizeCharts);
}

function onSimComplete(ev: Event) {
  const detail = (ev as CustomEvent<SimSummary>).detail;
  if (!detail?.topic) return;
  lastSimSummary.value = detail;
  void loadPlans();
}

watch(
  () => props.simSummary,
  (next) => {
    if (next?.topic) lastSimSummary.value = next;
  },
  { immediate: true },
);

onMounted(async () => {
  preferReducedMotion.value =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches === true;
  renderRadar();
  connectProfileStream();
  window.addEventListener('sparkorbit:sim-complete', onSimComplete as EventListener);
  await loadHistory();
  await loadMeta();
  await loadPlans();
  if (chartRef.value) {
    resizeObserver = new ResizeObserver(resizeCharts);
    resizeObserver.observe(chartRef.value);
    if (trendRef.value) resizeObserver.observe(trendRef.value);
  }
  window.addEventListener('resize', resizeCharts);
});

onBeforeUnmount(() => {
  eventSource?.close();
  window.removeEventListener('sparkorbit:sim-complete', onSimComplete as EventListener);
  chart?.dispose();
  trendChart?.dispose();
  resizeObserver?.disconnect();
  window.removeEventListener('resize', resizeCharts);
});
</script>

<template>
  <div class="dock-panel glass-panel space-y-3 rounded-2xl p-3 text-sky-50">
    <LzTabs
      block
      :items="[
        { key: 'overview', label: '概览' },
        { key: 'collect', label: '采集' },
        { key: 'history', label: '历史' },
      ]"
      :model-value="panelTab"
      @update:model-value="panelTab = $event as typeof panelTab"
    />

    <section v-show="panelTab === 'overview'" class="space-y-3">
      <!-- Hero -->
      <div class="lz-card flex items-center gap-3 p-3">
        <div
          class="relative flex h-16 w-16 shrink-0 items-center justify-center rounded-full border border-[rgb(var(--lz-accent)/0.3)]"
          :style="{
            background: hasRealProfile
              ? `conic-gradient(rgb(var(--lz-accent)) ${syncRate * 3.6}deg, rgba(148,163,184,0.15) 0)`
              : 'rgba(148,163,184,0.15)',
          }"
          :title="hasRealProfile ? `画像充实度 ${syncRate}（八维均分）` : '画像尚未落库'"
        >
          <div class="flex h-12 w-12 flex-col items-center justify-center rounded-full bg-slate-950 text-center">
            <span class="lz-accent-text text-sm font-semibold">{{ hasRealProfile ? syncRate : '—' }}</span>
            <span class="text-[9px] text-slate-500">{{ hasRealProfile ? '充实度' : '未同步' }}</span>
          </div>
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-2">
            <p class="lz-accent-text text-[10px] uppercase tracking-[0.28em] opacity-80">Mirror · 认知孪生</p>
            <LzBadge :tone="hasRealProfile ? 'success' : 'warning'">
              {{ hasRealProfile ? '已同步' : '未同步' }}
              <template v-if="hasRealProfile && updateSource">
                · {{ sourceLabel(updateSource) }}
              </template>
            </LzBadge>
          </div>
          <p class="mt-1 text-sm leading-5 text-white">{{ personaBrief }}</p>
          <div class="mt-2 flex flex-wrap gap-1.5">
            <LzButton variant="primary" size="sm" @click="primaryHeroAction">
              {{
                !hasRealProfile
                  ? '去采集'
                  : focusWeakDims[0]
                    ? `预演 · ${focusWeakDims[0].label}`
                    : '重排路径'
              }}
            </LzButton>
            <LzButton
              v-if="hasRealProfile"
              variant="ghost"
              size="sm"
              :loading="repathLoading"
              @click="handleRepath"
            >
              {{ repathLoading ? '重排中…' : '一键重排路径' }}
            </LzButton>
          </div>
          <p v-if="repathMsg" class="lz-caption lz-accent-text mt-1">{{ repathMsg }}</p>
        </div>
      </div>

      <!-- Radar -->
      <div class="lz-card lz-card--flat p-2">
        <div class="mb-1 flex items-center justify-between px-1">
          <p class="lz-caption">八维能力雷达 · 琥珀为薄弱轴</p>
          <span class="lz-caption">{{ profileHistory.length }} 条历史</span>
        </div>
        <div class="mx-auto aspect-square max-h-[260px] w-full max-w-[320px]">
          <div ref="chartRef" class="h-full w-full min-h-[200px]"></div>
        </div>
      </div>

      <!-- Insight -->
      <div class="lz-card flex gap-2 p-2.5">
        <span class="w-0.5 shrink-0 rounded-full bg-[rgb(var(--lz-accent)/0.7)]" aria-hidden="true" />
        <div class="min-w-0">
          <p class="lz-accent-text text-[10px] font-medium">实时洞察</p>
          <p class="lz-body mt-0.5">{{ streamText }}</p>
          <p v-if="hasRealProfile && updateSource" class="lz-caption mt-1">
            最近来源 · {{ sourceLabel(updateSource) }}
          </p>
        </div>
      </div>

      <p
        v-if="!hasRealProfile"
        class="rounded-[var(--radius-card)] border border-amber-400/25 bg-amber-500/10 px-2.5 py-2 text-[11px] leading-5 text-amber-100"
      >
        画像尚未落库。先到「采集」说明专业、已学内容与目标后再发起推演。
        <button class="lz-accent-text ml-1 hover:opacity-80" @click="panelTab = 'collect'; collectSubTab = 'initial'">去采集 →</button>
      </p>

      <div v-if="profileWarnings.length" class="rounded-[var(--radius-card)] border border-rose-400/25 bg-rose-500/10 p-2.5">
        <p class="text-[11px] font-medium text-rose-100">改进警告</p>
        <ul class="mt-1 space-y-1 text-[11px] leading-5 text-rose-100/90">
          <li v-for="(w, i) in profileWarnings.slice(0, 3)" :key="i">
            · {{ DIMENSION_LABELS[w.dimension as DimensionKey] || w.dimension }}：{{ w.text }}
          </li>
        </ul>
        <button class="lz-accent-text mt-2 text-[10px]" @click="panelTab = 'collect'; collectSubTab = 'improve'">去采集后改进 →</button>
      </div>

      <!-- Focus CTAs: top 2 -->
      <LzSection v-if="focusWeakDims.length" title="焦点行动" desc="优先补齐分数最低的薄弱维">
        <div class="space-y-2">
          <div
            v-for="dim in focusWeakDims"
            :key="dim.key"
            class="rounded-[var(--radius-card)] border border-amber-400/25 bg-amber-500/[0.07] p-3"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <p class="text-sm font-medium text-amber-50">{{ dim.label }}</p>
                <p class="lz-desc mt-0.5">{{ dim.status }}</p>
              </div>
              <span class="shrink-0 text-lg font-semibold tabular-nums text-amber-200">{{ dim.score }}</span>
            </div>
            <div class="mt-2.5 flex flex-wrap gap-1.5">
              <LzButton variant="soft" size="sm" @click="triggerSim(dim)">发起预演</LzButton>
              <LzButton variant="ghost" size="sm" @click="openDimension(dim); detailsOpen = true">看证据</LzButton>
            </div>
          </div>
          <button
            v-if="moreWeakDims.length"
            type="button"
            class="lz-btn lz-btn--ghost lz-btn--sm w-full border-dashed"
            @click="moreWeakOpen = !moreWeakOpen"
          >
            {{ moreWeakOpen ? '收起' : `还有 ${moreWeakDims.length} 个薄弱维` }}
          </button>
          <div v-if="moreWeakOpen" class="space-y-1">
            <button
              v-for="dim in moreWeakDims"
              :key="dim.key"
              type="button"
              class="lz-card lz-card--flat lz-card--hover flex w-full items-center justify-between px-2.5 py-1.5 text-left text-[11px] text-slate-300"
              @click="triggerSim(dim)"
            >
              <span>{{ dim.label }} · {{ dim.score }}</span>
              <span class="lz-accent-text">预演 →</span>
            </button>
          </div>
        </div>
      </LzSection>

      <!-- Dimension meters (Luminous Meter) · 两列缩短纵向 -->
      <LzSection title="维度明细" desc="点击卡片展开状态与证据">
        <div class="grid grid-cols-2 gap-2">
          <MirrorDimensionMeter
            v-for="item in sortedDimensions"
            :key="item.key"
            :label="item.label"
            :short="DIMENSION_SHORT[item.key]"
            :score="item.score"
            :status="item.status"
            :evidence="item.evidence"
            :expanded="expandedDimKey === item.key"
            :animate="!preferReducedMotion"
            :class="expandedDimKey === item.key ? 'col-span-2' : ''"
            @select="toggleDimExpand(item.key); openDimension(item)"
          />
        </div>
      </LzSection>

      <!-- Summary -->
      <div class="lz-card mt-1 p-2.5">
        <p class="lz-subtitle text-white">画像摘要</p>
        <p v-if="hasUsefulSummary" class="lz-body mt-1">
          {{ cleanSummaryText(extractionSummary) }}
        </p>
        <p v-else class="lz-desc mt-1">
          完成一次采集或学习后，这里会生成可读的人设摘要。
        </p>
      </div>

      <!-- Collapsed secondary -->
      <div class="lz-card lz-card--flat">
        <button
          type="button"
          class="flex w-full items-center justify-between px-3 py-2 text-left text-[11px] text-slate-300 hover:text-white"
          @click="detailsOpen = !detailsOpen"
        >
          <span>更多细节 · 来源 / 证据 / 追问 / 推演</span>
          <span class="text-slate-500">{{ detailsOpen ? '收起' : '展开' }}</span>
        </button>
        <div v-if="detailsOpen" class="space-y-3 border-t border-white/5 px-3 py-3">
          <div class="flex flex-wrap gap-1.5">
            <LzBadge
              v-for="key in ['profiler', 'auto_refresh', 'vault_analyze', 'improvement']"
              :key="key"
              :tone="lastSources[key] ? 'accent' : 'neutral'"
              :title="lastSources[key] || ''"
            >
              {{ sourceLabel(key) }} · {{ relativeSourceTime(lastSources[key]) }}
            </LzBadge>
            <LzBadge v-if="pendingEvents" tone="warning">待处理事件 {{ pendingEvents }}</LzBadge>
          </div>

          <div class="grid grid-cols-3 gap-1.5">
            <button
              type="button"
              class="lz-card lz-card--hover p-2 text-left"
              @click="loadEvidence('')"
            >
              <p class="lz-caption">航迹记忆</p>
              <p class="mt-0.5 line-clamp-2 text-[10px] leading-4 text-slate-200">
                {{ layerSummaries.trajectory || '近期学习航迹' }}
              </p>
              <p class="lz-accent-text mt-1 text-[10px]">证据 {{ layerCounts.trajectory || 0 }}</p>
            </button>
            <button
              type="button"
              class="lz-card lz-card--hover p-2 text-left"
              @click="loadEvidence('prior_knowledge')"
            >
              <p class="lz-caption">掌握星图</p>
              <p class="mt-0.5 line-clamp-2 text-[10px] leading-4 text-slate-200">
                {{ layerSummaries.mastery || '会什么 / 卡在哪' }}
              </p>
              <p class="lz-accent-text mt-1 text-[10px]">证据 {{ layerCounts.mastery || 0 }}</p>
            </button>
            <button
              type="button"
              class="lz-card lz-card--hover p-2 text-left"
              @click="loadEvidence('learning_goal')"
            >
              <p class="lz-caption">调适意志</p>
              <p class="mt-0.5 line-clamp-2 text-[10px] leading-4 text-slate-200">
                {{ layerSummaries.will || '目标与节奏' }}
              </p>
              <p class="lz-accent-text mt-1 text-[10px]">证据 {{ layerCounts.will || 0 }}</p>
            </button>
          </div>

          <div v-if="evidenceItems.length || evidenceLoading" class="lz-card lz-card--active p-2.5">
            <div class="flex items-center justify-between gap-2">
              <p class="lz-subtitle text-[11px]">
                证据链{{ evidenceDim ? ` · ${DIMENSION_LABELS[evidenceDim]}` : '' }}
              </p>
              <button type="button" class="lz-caption hover:text-slate-200" @click="evidenceItems = []">收起</button>
            </div>
            <LzSkeleton v-if="evidenceLoading" preset="text" :rows="2" class="mt-2" />
            <ul v-else class="lz-body mt-1 max-h-36 space-y-1 overflow-y-auto text-[11px]">
              <li v-for="(ev, i) in evidenceItems.slice(0, 12)" :key="i">
                <span class="text-slate-500">{{ (ev.at || '').slice(0, 16) }}</span>
                · {{ ev.event_type }}
                <span v-if="ev.delta_hint" class="text-amber-200/80">（{{ ev.delta_hint }}）</span>
                — {{ ev.summary }}
              </li>
            </ul>
          </div>

          <div v-if="followUps.length" class="lz-card p-2.5">
            <p class="lz-subtitle text-[11px]">学习建议 · 追问</p>
            <ul class="lz-body mt-1 space-y-1 text-[11px]">
              <li v-for="(q, i) in followUps.slice(0, 4)" :key="i">· {{ q }}</li>
            </ul>
            <button class="lz-accent-text mt-2 text-[10px] hover:opacity-80" @click="panelTab = 'collect'; collectSubTab = 'initial'">去采集页回答 →</button>
          </div>

          <div v-if="lastSimSummary" class="rounded-[var(--radius-card)] border border-emerald-400/20 bg-emerald-500/5 p-2.5">
            <p class="text-[11px] font-medium text-emerald-100">最近推演结论 · {{ lastSimSummary.topic }}</p>
            <p v-if="lastSimSummary.rootCause" class="lz-body mt-1 text-[11px]">错因：{{ lastSimSummary.rootCause }}</p>
            <ul v-if="lastSimSummary.pathSteps.length" class="lz-body mt-1 space-y-0.5 text-[11px]">
              <li v-for="(step, i) in lastSimSummary.pathSteps.slice(0, 3)" :key="i">{{ i + 1 }}. {{ step }}</li>
            </ul>
            <button class="mt-2 text-[10px] text-emerald-300" @click="panelTab = 'collect'; collectSubTab = 'improve'">去完成改进验收 →</button>
          </div>

          <div class="flex flex-wrap items-center gap-1.5">
            <LzButton variant="ghost" size="sm" @click="handleProfileRefresh">手动刷新画像</LzButton>
            <p v-if="refreshMsg" class="text-[10px] text-emerald-300">{{ refreshMsg }}</p>
          </div>
        </div>
      </div>
    </section>

    <section v-show="panelTab === 'collect'" class="space-y-3">
      <LzTabs
        block
        :items="[
          { key: 'initial', label: '首次采集' },
          { key: 'improve', label: openPlans.length ? `改进闭环 · ${openPlans.length}` : '改进闭环' },
        ]"
        :model-value="collectSubTab"
        @update:model-value="collectSubTab = $event as typeof collectSubTab"
      />

      <template v-if="collectSubTab === 'initial'">
        <div
          class="rounded-[var(--radius-card)] border px-3 py-2 text-[11px] leading-5"
          :class="
            hasRealProfile
              ? 'border-emerald-400/20 bg-emerald-500/5 text-emerald-100/90'
              : 'border-amber-400/25 bg-amber-500/10 text-amber-100'
          "
        >
          <p v-if="!hasRealProfile">
            一次说清：专业、已学内容、最近学习目标，再点下方发送。无历史时推演会被拦截。
          </p>
          <p v-else>
            画像已落库。可继续回答追问补全薄弱维，或切换到「改进闭环」完成补救验收。
          </p>
        </div>

        <div class="lz-card lz-card--flat max-h-56 space-y-2.5 overflow-auto p-3">
          <div
            v-for="(msg, i) in chatMessages"
            :key="i"
            class="flex"
            :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <div
              class="max-w-[88%] rounded-2xl px-3 py-2 text-[11px] leading-5"
              :class="
                msg.role === 'user'
                  ? 'rounded-br-md bg-[rgb(var(--lz-accent)/0.22)] text-white ring-1 ring-[rgb(var(--lz-accent)/0.3)]'
                  : 'rounded-bl-md bg-white/[0.06] text-slate-200 ring-1 ring-white/10'
              "
            >
              <p class="mb-0.5 text-[9px] uppercase tracking-wider opacity-60">
                {{ msg.role === 'user' ? '你' : '助手' }}
              </p>
              {{ msg.content }}
            </div>
          </div>
        </div>

        <LzSection v-if="followUps.length" title="建议追问">
          <div class="grid gap-1.5 sm:grid-cols-3">
            <button
              v-for="q in followUps.slice(0, 3)"
              :key="q"
              type="button"
              class="lz-card lz-card--hover px-2.5 py-2 text-left text-[10px] leading-4 text-slate-200"
              @click="useFollowUp(q)"
            >
              {{ q.length > 36 ? `${q.slice(0, 36)}…` : q }}
            </button>
          </div>
        </LzSection>

        <div class="lz-card space-y-2 p-2.5">
          <textarea
            v-model="chatInput"
            rows="2"
            class="lz-input w-full resize-none px-3 py-2"
            placeholder="回答画像追问，或直接描述专业 / 已学 / 目标…"
            @keyup.enter.exact="submitInterview"
          />
          <LzButton variant="primary" block :loading="loading" @click="submitInterview">
            {{ loading ? '分析中…' : '发送并更新画像' }}
          </LzButton>
        </div>
      </template>

      <template v-else>
        <div class="lz-card lz-card--flat px-3 py-2">
          <p class="lz-desc">完成推演补救步骤并提交证据与短反思；AI 先评三档，教师可覆盖。不合格可重提一次。</p>
        </div>
        <p v-if="improveMsg" class="text-[10px] text-emerald-300">{{ improveMsg }}</p>
        <p v-if="syncPathMsg" class="lz-caption lz-accent-text">{{ syncPathMsg }}</p>
        <LzSkeleton v-if="plansLoading" preset="card" :rows="2" />

        <LzEmptyState
          v-else-if="!improvementPlans.length"
          icon="✦"
          title="暂无改进计划"
          desc="从概览薄弱维发起镜像预演后，补救步骤会出现在这里。"
          action-text="回概览发起预演"
          @action="goOverviewForSim"
        />

        <div v-else class="max-h-[28rem] space-y-3 overflow-auto">
          <article
            v-for="plan in improvementPlans"
            :key="plan.id"
            class="lz-card p-3"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <p class="text-[12px] font-medium text-white">{{ plan.topic }}</p>
                <p class="lz-caption mt-0.5 text-[10px]">
                  目标维 · {{ plan.target_dimension_label }}
                  <span class="text-slate-600">·</span>
                  {{ plan.status }}
                </p>
              </div>
              <div class="flex shrink-0 flex-col items-end gap-1.5">
                <LzBadge
                  v-if="plan.submission"
                  :tone="
                    plan.submission.final_grade === 'excellent'
                      ? 'success'
                      : plan.submission.final_grade === 'fail'
                        ? 'danger'
                        : 'accent'
                  "
                >
                  {{ GRADE_LABEL[plan.submission.final_grade] || plan.submission.final_grade }}
                </LzBadge>
                <LzButton variant="soft" size="sm" @click="handleSyncPlanToPath(plan.id)">
                  同步到学习路径
                </LzButton>
              </div>
            </div>
            <p v-if="plan.root_cause" class="lz-caption mt-2 text-[10px] leading-4">
              错因：{{ plan.root_cause }}
            </p>

            <ol class="mt-3 space-y-2 border-l border-[rgb(var(--lz-accent)/0.2)] pl-3">
              <li
                v-for="step in plan.steps"
                :key="step.index"
                class="lz-card lz-card--flat relative p-2"
              >
                <span
                  class="absolute -left-[calc(0.75rem+5px)] top-3 h-2.5 w-2.5 rounded-full border border-[rgb(var(--lz-accent)/0.4)]"
                  :class="step.done ? 'bg-[rgb(var(--lz-accent))]' : 'bg-slate-950'"
                  aria-hidden="true"
                />
                <label class="flex items-start gap-2 text-[11px] text-slate-200">
                  <input
                    type="checkbox"
                    class="mt-0.5"
                    :checked="step.done"
                    :disabled="!!plan.submission && plan.submission.final_grade !== 'fail'"
                    @change="saveStepEvidence(plan, step.index, step.evidence_text || ( ($event.target as HTMLInputElement).checked ? '已完成' : '' ))"
                  />
                  <span>{{ step.index + 1 }}. {{ step.title }}</span>
                </label>
                <textarea
                  v-if="!plan.submission || plan.submission.final_grade === 'fail'"
                  class="lz-input mt-1.5 w-full resize-none px-2 py-1 text-[11px]"
                  rows="2"
                  placeholder="填写本步证据（表格要点/笔记/案例分析）"
                  :value="step.evidence_text"
                  @blur="saveStepEvidence(plan, step.index, ($event.target as HTMLTextAreaElement).value)"
                />
                <p v-else-if="step.evidence_text" class="lz-caption mt-1 text-[10px]">证据：{{ step.evidence_text }}</p>
              </li>
            </ol>

            <template v-if="!plan.submission || plan.submission.final_grade === 'fail'">
              <textarea
                v-model="reflectionDrafts[plan.id]"
                class="lz-input mt-3 w-full resize-none px-2.5 py-2 text-[11px]"
                rows="2"
                placeholder="短反思：如何区分错因中的关键概念？"
              />
              <LzButton
                variant="primary"
                block
                class="mt-2"
                :loading="submittingPlanId === plan.id"
                @click="handleSubmitImprovement(plan)"
              >
                {{ submittingPlanId === plan.id ? '评分中…' : '提交改进验收' }}
              </LzButton>
            </template>
            <div
              v-else-if="plan.submission"
              class="lz-card lz-card--flat mt-3 p-2.5 text-[10px] leading-4 text-slate-300"
            >
              <p>{{ plan.submission.ai_feedback }}</p>
              <p v-if="plan.submission.applied_delta" class="mt-1 text-emerald-300">已加分 +{{ plan.submission.applied_delta }}</p>
              <p v-if="plan.submission.pending_review" class="mt-1 text-amber-200">待教师复核</p>
              <p v-if="plan.submission.teacher_reviewed" class="lz-accent-text mt-1">教师已复核</p>
            </div>
          </article>
        </div>
      </template>
    </section>

    <section v-show="panelTab === 'history'" class="space-y-3">
      <div class="lz-card flex flex-wrap items-center justify-between gap-2 p-3">
        <div class="min-w-0">
          <p class="lz-accent-text text-[10px] uppercase tracking-[0.28em] opacity-80">随学随新</p>
          <p class="lz-desc mt-0.5">学习行为累积后自动更新画像版本</p>
        </div>
        <div class="flex flex-wrap gap-1.5">
          <LzButton variant="ghost" size="sm" @click="handleProfileRefresh">手动刷新画像</LzButton>
          <LzButton variant="soft" size="sm" :loading="repathLoading" @click="handleRepath">
            {{ repathLoading ? '重排中…' : '一键重排路径' }}
          </LzButton>
        </div>
      </div>
      <p v-if="refreshMsg" class="text-[10px] text-emerald-300">{{ refreshMsg }}</p>
      <p v-if="repathMsg" class="lz-caption lz-accent-text">{{ repathMsg }}</p>

      <LzSection title="充实度趋势" boxed>
        <div v-if="profileHistory.length >= 2" class="aspect-[4/3] w-full">
          <div ref="trendRef" class="h-full min-h-[160px] w-full"></div>
        </div>
        <LzEmptyState
          v-else
          icon="✦"
          title="趋势尚未成型"
          desc="至少保留 2 条画像版本后，这里会显示充实度变化曲线。"
        />
      </LzSection>

      <LzSection title="版本时间线">
        <MirrorHistoryTimeline
          :items="profileHistory"
          :loading="historyLoading"
          @recall="recallHistoryVersion"
          @collect="panelTab = 'collect'; collectSubTab = 'initial'"
        />
      </LzSection>
    </section>

    <teleport to="body">
      <div v-if="selectedDim" class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" @click.self="selectedDim = null">
        <div class="w-full max-w-sm rounded-[var(--radius-panel)] border border-[var(--border-strong)] bg-slate-950/95 p-4 shadow-glow-lg">
          <div class="flex items-start justify-between gap-2">
            <div>
              <p class="lz-accent-text text-[10px] uppercase tracking-wider opacity-80">维度详情</p>
              <h3 class="lz-title text-base">{{ selectedDim.label }}</h3>
              <p class="lz-accent-text mt-1 text-sm">{{ selectedDim.score }} 分 · {{ selectedDim.status }}</p>
            </div>
            <button class="text-slate-400 hover:text-white" @click="selectedDim = null">✕</button>
          </div>
          <div class="mt-3">
            <p class="lz-subtitle text-xs">依据</p>
            <ul class="lz-body mt-1 space-y-1 text-[11px]">
              <li v-for="(ev, i) in selectedDim.evidence" :key="'d'+i">· {{ ev }}</li>
              <li v-for="(ev, i) in evidenceItems.slice(0, 6)" :key="'e'+i" class="text-slate-400">
                · {{ ev.event_type }}：{{ ev.summary }}
              </li>
              <li v-if="!selectedDim.evidence.length && !evidenceItems.length" class="text-slate-500">
                暂无结构化依据，可通过采集或知识库 AI 刷新补充。
              </li>
            </ul>
          </div>
          <div class="lz-card lz-card--flat mt-3 p-2 text-[11px] text-slate-300">
            建议：针对「{{ selectedDim.label }}」做 1 次推演预演，或完成 25 分钟专项专注。
          </div>
          <LzButton variant="soft" block class="mt-3" @click="triggerSim(selectedDim); selectedDim = null">
            基于该维度发起推演
          </LzButton>
        </div>
      </div>
    </teleport>
  </div>
</template>

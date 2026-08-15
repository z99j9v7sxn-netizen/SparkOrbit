<script setup lang="ts">
import * as echarts from 'echarts';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRouter } from 'vue-router';
import {
  dispatchTask,
  fetchClassOverview,
  fetchGravityWells,
  fetchProfileMatrix,
  fetchReviewTickets,
  fetchStudentRisks,
  interveneStudent,
  resolveReviewTicket,
  type ClassOverview,
  type GravityWell,
  type HeatItem,
  type ProfileMatrix,
  type ReviewTicket,
  type StudentRisk,
} from '../../api/dashboard';
import { fetchTeacherTodos, type TeacherTodoItem } from '../../api/teacherSuite';
import TimeWarpSandbox from '../TimeWarpSandbox.vue';
import OrbCore, { type OrbState } from '../common/orb/OrbCore.vue';
import { useChartTheme } from '../../composables/useChartTheme';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';
import TeacherStatCard from './TeacherStatCard.vue';
import { useTeacherClassStore } from '../../stores/teacherClass';

const router = useRouter();
const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);
const { chart: chartTokens } = useChartTheme();

const overview = ref<ClassOverview | null>(null);
const risks = ref<StudentRisk[]>([]);
const profileMatrix = ref<ProfileMatrix | null>(null);
const gravityWells = ref<GravityWell[]>([]);
const reviewTickets = ref<ReviewTicket[]>([]);
const todoItems = ref<TeacherTodoItem[]>([]);
const dispatchMsg = ref('');
const error = ref('');
const loading = ref(false);
const riskFilter = ref<'all' | 'high' | 'medium' | 'low'>('all');
const selectedIds = ref<string[]>([]);
const heatOpen = ref(false);
const matrixChartRef = ref<HTMLDivElement | null>(null);
const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
let matrixChart: echarts.ECharts | null = null;
let timer: number | null = null;

const riskFilterOptions = [
  { value: 'all', label: '全部' },
  { value: 'high', label: '高风险' },
  { value: 'medium', label: '中风险' },
  { value: 'low', label: '稳定' },
] as const;

const filteredRisks = computed(() =>
  riskFilter.value === 'all' ? risks.value : risks.value.filter((r) => r.risk_level === riskFilter.value),
);

const heatByGalaxy = computed(() => {
  const map = new Map<string, HeatItem[]>();
  overview.value?.heatmap.forEach((h) => {
    if (!map.has(h.galaxy_name)) map.set(h.galaxy_name, []);
    map.get(h.galaxy_name)!.push(h);
  });
  return Array.from(map.entries());
});

const highRiskCount = computed(() => risks.value.filter((r) => r.risk_level === 'high').length);

const classHealthState = computed<OrbState>(() => {
  if (error.value) return 'error';
  if (loading.value && !overview.value) return 'thinking';
  if (highRiskCount.value > 0) return 'alert';
  return 'idle';
});

const classHealthLabel = computed(() => {
  if (error.value) return '数据异常';
  if (loading.value && !overview.value) return '同步中…';
  if (highRiskCount.value > 0) return `${highRiskCount.value} 名高风险学生`;
  return '班级状态良好';
});

function riskBadgeClass(level: string) {
  return level === 'high' ? 't-badge t-badge--danger' : level === 'medium' ? 't-badge t-badge--warn' : 't-badge t-badge--ok';
}

function heatClass(rate: number) {
  if (rate >= 70) return 'bg-t-ok/75 text-white';
  if (rate >= 40) return 'bg-t-warn/70 text-white';
  if (rate >= 15) return 'bg-t-danger/60 text-white';
  return 'bg-t-line/20 text-t-2';
}

function renderChart() {
  if (!chartRef.value || !overview.value) return;
  if (!chart) chart = echarts.init(chartRef.value);
  const t = chartTokens.value;
  const items = overview.value.weakest_planets;
  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 130, right: 30, top: 10, bottom: 20 },
    tooltip: {
      backgroundColor: t.tooltip.backgroundColor,
      borderColor: t.tooltip.borderColor,
      textStyle: { color: t.tooltip.textColor },
    },
    xAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: t.axisLabel },
      splitLine: { lineStyle: { color: t.splitLine } },
    },
    yAxis: {
      type: 'category',
      data: items.map((i) => i.planet_name).reverse(),
      axisLabel: { color: t.axisLabelStrong, fontSize: 11 },
    },
    series: [
      {
        type: 'bar',
        data: items.map((i) => i.mastery_rate).reverse(),
        itemStyle: { borderRadius: [0, 6, 6, 0], color: t.palette[2] },
        barWidth: 14,
      },
    ],
  });
}

function renderMatrixChart() {
  if (!matrixChartRef.value || !profileMatrix.value) return;
  if (!matrixChart) matrixChart = echarts.init(matrixChartRef.value);
  const t = chartTokens.value;
  const dims = profileMatrix.value.dimension_averages;
  const labels = ['专业背景', '前置知识', '认知风格', '易错倾向', '学习目标', '时间弹性'];
  const keys = [
    'major_background',
    'prior_knowledge',
    'cognitive_style',
    'mistake_tendency',
    'learning_goal',
    'time_flexibility',
    'modality_preference',
    'motivation_level',
  ];
  matrixChart.setOption({
    backgroundColor: 'transparent',
    radar: {
      indicator: labels.map((n) => ({ name: n, max: 100 })),
      splitLine: { lineStyle: { color: t.splitLine } },
      axisName: { color: t.axisLabelStrong, fontSize: 11 },
    },
    series: [
      {
        type: 'radar',
        data: [{ value: keys.map((k) => dims[k] ?? 50), name: profileMatrix.value.class_tendency_label }],
        areaStyle: { color: t.accentSoft },
        lineStyle: { color: t.accent },
      },
    ],
  });
}

function onResize() {
  chart?.resize();
  matrixChart?.resize();
}

async function loadAll() {
  const cid = classId.value;
  if (!cid) {
    overview.value = null;
    risks.value = [];
    profileMatrix.value = null;
    gravityWells.value = [];
    reviewTickets.value = [];
    return;
  }
  loading.value = true;
  error.value = '';
  try {
    const [ov, rk, pm, gw, tickets, todos] = await Promise.all([
      fetchClassOverview(cid),
      fetchStudentRisks(cid),
      fetchProfileMatrix(cid),
      fetchGravityWells(cid),
      fetchReviewTickets(cid).catch(() => [] as ReviewTicket[]),
      fetchTeacherTodos(cid).catch(() => ({ items: [] as TeacherTodoItem[], total: 0 })),
    ]);
    overview.value = ov;
    risks.value = rk;
    profileMatrix.value = pm;
    gravityWells.value = gw;
    reviewTickets.value = tickets;
    todoItems.value = todos.items;
    await nextTick();
    renderChart();
    renderMatrixChart();
    chart?.resize();
    matrixChart?.resize();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载看板失败';
  } finally {
    loading.value = false;
  }
}

async function handleDispatch(student: StudentRisk) {
  dispatchMsg.value = '';
  try {
    await dispatchTask(student.user_id, `${student.display_name} 同学，老师为你安排了针对性复习，加油点亮更多行星！`);
    dispatchMsg.value = `已向 ${student.display_name} 派发智能复习任务`;
  } catch {
    dispatchMsg.value = '派发失败';
  }
}

async function handleBatchDispatch() {
  for (const id of selectedIds.value) {
    const s = risks.value.find((r) => r.user_id === id);
    if (s) await handleDispatch(s);
  }
  selectedIds.value = [];
}

async function handleIntervene(student: StudentRisk) {
  try {
    const res = await interveneStudent(student.user_id, `${student.display_name} 同学，老师已为你派遣专属救援助手。`);
    dispatchMsg.value = res.message || `已向 ${student.display_name} 投放救援助手`;
  } catch {
    dispatchMsg.value = '干预失败';
  }
}

function openStudent(id: string) {
  void router.push({ path: `/teacher/students/${id}`, query: { class_id: classId.value } });
}

async function handleResolveTicket(ticket: ReviewTicket) {
  try {
    await resolveReviewTicket(ticket.id);
    reviewTickets.value = reviewTickets.value.filter((t) => t.id !== ticket.id);
    dispatchMsg.value = `已办结待人审工单：${ticket.planet_name}`;
  } catch {
    dispatchMsg.value = '办结工单失败';
  }
}

watch(classId, () => void loadAll());
watch(overview, () => overview.value && renderChart(), { flush: 'post' });
watch(profileMatrix, () => profileMatrix.value && renderMatrixChart(), { flush: 'post' });
watch(chartTokens, () => {
  renderChart();
  renderMatrixChart();
});

onMounted(async () => {
  await loadAll();
  timer = window.setInterval(() => void loadAll(), 30000);
  window.addEventListener('resize', onResize);
});

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer);
  window.removeEventListener('resize', onResize);
  chart?.dispose();
  matrixChart?.dispose();
});
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="学情看板" subtitle="班级掌握度、风险预警与智能干预" />

    <TeacherLoading v-if="loading && !overview" :rows="6" />
    <p v-else-if="error" class="rounded-xl border border-t-danger/30 bg-t-danger/10 px-4 py-3 text-sm text-t-danger">{{ error }}</p>

    <template v-else>
      <!-- 待办中心：聚合各页面待处理事项 -->
      <section v-if="todoItems.length" class="t-card glass-edge p-4">
        <div class="flex items-baseline justify-between gap-2">
          <h3 class="text-[13px] font-semibold text-t-1">今日待办</h3>
          <span class="t-kicker">To-Do</span>
        </div>
        <div class="mt-2 flex flex-wrap gap-2">
          <button
            v-for="t in todoItems"
            :key="t.key"
            type="button"
            class="flex items-center gap-2 rounded-xl border px-3 py-2 text-left transition"
            :class="t.count > 0 ? 'border-t-warn/35 bg-t-warn/8 hover:bg-t-warn/14' : 'border-t-line/10 bg-t-s1/30 opacity-60'"
            @click="t.link !== '/teacher/dashboard' && router.push(t.link)"
          >
            <span class="font-mono-tech text-lg font-semibold" :class="t.count > 0 ? 'text-t-warn' : 'text-t-3'">{{ t.count }}</span>
            <span class="text-xs text-t-2">{{ t.label }}</span>
          </button>
        </div>
      </section>

      <!-- Bento 首屏：班级脉搏 hero + KPI -->
      <div class="grid grid-cols-2 gap-4 lg:grid-cols-6">
        <section class="t-card glass-edge col-span-2 flex items-center gap-4 p-5">
          <OrbCore :state="classHealthState" palette="cyan" :size="72" :label="`班级健康度：${classHealthLabel}`" />
          <div class="min-w-0">
            <p class="t-kicker">Class Pulse</p>
            <p class="mt-1 text-base font-semibold text-t-1">{{ classHealthLabel }}</p>
            <p class="mt-0.5 text-[11px] text-t-3">每 30 秒自动同步</p>
          </div>
        </section>
        <TeacherStatCard label="班级学生" :value="overview?.total_students ?? 0" />
        <TeacherStatCard label="知识行星" :value="overview?.total_planets ?? 0" />
        <TeacherStatCard label="平均掌握率" :value="`${overview?.avg_mastery_rate ?? 0}%`" accent="emerald" />
        <TeacherStatCard label="高风险学生" :value="highRiskCount" accent="rose" />
      </div>

      <!-- 图表区 2:1 -->
      <div class="grid gap-4 xl:grid-cols-3">
        <section class="t-card glass-edge p-5 xl:col-span-2">
          <div class="flex items-baseline justify-between gap-2">
            <h3 class="text-[15px] font-semibold text-t-1">最薄弱的知识行星</h3>
            <span class="t-kicker">Weakest Planets</span>
          </div>
          <div ref="chartRef" class="mt-3 h-64 w-full"></div>
        </section>
        <section class="t-card glass-edge p-5">
          <div class="flex items-baseline justify-between gap-2">
            <h3 class="text-[15px] font-semibold text-t-1">群体六维画像</h3>
            <span class="t-kicker">Matrix</span>
          </div>
          <p class="mt-1 text-xs text-t-2">
            班级倾向：<span class="font-medium text-t-accent">{{ profileMatrix?.class_tendency_label ?? '—' }}</span>
          </p>
          <div ref="matrixChartRef" class="mt-2 h-56 w-full"></div>
        </section>
      </div>

      <!-- 预警区 -->
      <div class="grid gap-4 xl:grid-cols-2">
        <section class="t-card glass-edge p-5">
          <h3 class="text-[15px] font-semibold text-t-1">引力陷阱预警</h3>
          <div class="mt-3 max-h-64 space-y-2 overflow-auto">
            <div
              v-for="w in gravityWells"
              :key="w.planet_slug"
              class="flex items-center justify-between rounded-xl border px-3 py-2"
              :class="w.severity === 'critical' ? 'border-t-danger/35 bg-t-danger/8' : 'border-t-warn/30 bg-t-warn/8'"
            >
              <div>
                <p class="text-sm font-medium text-t-1">{{ w.planet_name }}</p>
                <p class="text-[10px] text-t-3">{{ w.galaxy_name }}</p>
              </div>
              <span class="font-mono-tech text-sm font-semibold" :class="w.severity === 'critical' ? 'text-t-danger' : 'text-t-warn'">
                {{ w.stuck_rate }}% 卡壳
              </span>
            </div>
            <TeacherEmptyState v-if="!gravityWells.length" title="暂无引力陷阱" description="当前班级知识点掌握较均衡" />
          </div>
        </section>

        <section class="t-card glass-edge p-5">
          <div class="flex items-baseline justify-between gap-2">
            <h3 class="text-[15px] font-semibold text-t-1">待人审 · 低置信判题工单</h3>
            <span v-if="reviewTickets.length" class="t-badge t-badge--danger">{{ reviewTickets.length }}</span>
          </div>
          <p class="mt-1 text-xs text-t-3">置信度 &lt; 55% 或知识点引用异常时自动转入</p>
          <div class="mt-3 max-h-56 space-y-2 overflow-auto">
            <div v-for="t in reviewTickets" :key="t.id" class="rounded-xl border border-t-danger/25 bg-t-danger/6 px-3 py-2">
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <p class="text-sm font-medium text-t-1">{{ t.student_name }} · {{ t.planet_name }}</p>
                  <p class="mt-0.5 font-mono-tech text-[10px] text-t-accent">
                    kp={{ t.knowledge_point_id }} · cited={{ t.cited_knowledge_point_id }} · conf={{ (t.confidence * 100).toFixed(0) }}%
                  </p>
                  <p class="mt-1 text-[11px] text-t-2">{{ t.reason }}</p>
                  <p class="mt-1 line-clamp-2 text-[10px] text-t-3">{{ t.question_preview }}</p>
                </div>
                <button type="button" class="t-btn t-btn--ghost t-btn--sm shrink-0" @click="handleResolveTicket(t)">办结</button>
              </div>
            </div>
            <TeacherEmptyState v-if="!reviewTickets.length" title="暂无待人审工单" description="学生端勾选「强制低置信」提交即可演示" />
          </div>
        </section>
      </div>

      <!-- 星图热力：可展开 -->
      <section class="t-card glass-edge p-5">
        <button type="button" class="flex w-full items-center justify-between gap-2 text-left" @click="heatOpen = !heatOpen">
          <div>
            <h3 class="text-[15px] font-semibold text-t-1">二维星图热力</h3>
            <p class="mt-0.5 text-xs text-t-3">按星系分组的行星掌握率热力分布</p>
          </div>
          <svg
            viewBox="0 0 16 16"
            class="h-4 w-4 shrink-0 text-t-3 transition-transform duration-200"
            :class="heatOpen ? 'rotate-180' : ''"
            fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"
          >
            <path d="m4 6 4 4 4-4" />
          </svg>
        </button>
        <div v-show="heatOpen" class="mt-3 max-h-72 space-y-3 overflow-auto">
          <div v-for="[galaxy, planets] in heatByGalaxy" :key="galaxy">
            <p class="mb-1 text-xs font-medium text-t-2">{{ galaxy }}</p>
            <div class="flex flex-wrap gap-1.5">
              <div
                v-for="p in planets"
                :key="p.planet_slug"
                class="rounded-md px-2 py-1 text-[10px]"
                :class="heatClass(p.mastery_rate)"
                :title="`${p.planet_name}：${p.mastery_rate}%`"
              >
                {{ p.planet_name }}
              </div>
            </div>
          </div>
          <TeacherEmptyState v-if="!heatByGalaxy.length" title="暂无热力数据" />
        </div>
      </section>

      <TimeWarpSandbox />

      <!-- 风险学生 -->
      <section class="t-card glass-edge p-5">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 class="text-[15px] font-semibold text-t-1">认知状态低迷学生</h3>
            <p class="mt-0.5 text-xs text-t-3">支持筛选、批量派发与下钻详情</p>
          </div>
          <div class="flex items-center gap-2">
            <div class="t-tabs">
              <button
                v-for="opt in riskFilterOptions"
                :key="opt.value"
                type="button"
                class="t-tab"
                :class="{ 'is-active': riskFilter === opt.value }"
                @click="riskFilter = opt.value"
              >
                {{ opt.label }}
              </button>
            </div>
            <button v-if="selectedIds.length" type="button" class="t-btn t-btn--primary t-btn--sm" @click="handleBatchDispatch">
              批量派发 ({{ selectedIds.length }})
            </button>
          </div>
        </div>
        <p v-if="dispatchMsg" class="mt-2 text-xs text-t-ok">{{ dispatchMsg }}</p>
        <div class="mt-3 space-y-2">
          <div
            v-for="s in filteredRisks"
            :key="s.user_id"
            class="t-card--flat flex flex-wrap items-center justify-between gap-2 rounded-xl border border-t-line/10 px-4 py-2.5 transition hover:border-t-accent/30"
          >
            <div class="flex items-center gap-3">
              <input v-model="selectedIds" type="checkbox" :value="s.user_id" class="t-check rounded" />
              <span :class="riskBadgeClass(s.risk_level)">
                {{ s.risk_level === 'high' ? '高风险' : s.risk_level === 'medium' ? '中风险' : '稳定' }}
              </span>
              <button type="button" class="text-sm font-medium text-t-1 transition hover:text-t-accent" @click="openStudent(s.user_id)">
                {{ s.display_name }}
              </button>
              <span class="font-mono-tech text-[11px] text-t-3">掌握 {{ s.mastery_rate }}%</span>
            </div>
            <div class="flex gap-2">
              <button type="button" class="t-btn t-btn--soft t-btn--sm" @click="handleDispatch(s)">派发复习</button>
              <button type="button" class="t-btn t-btn--ghost t-btn--sm" @click="handleIntervene(s)">救援助手</button>
            </div>
          </div>
          <TeacherEmptyState v-if="!filteredRisks.length" title="暂无匹配学生" />
        </div>
      </section>
    </template>
  </div>
</template>

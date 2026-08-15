<script setup lang="ts">
import * as echarts from 'echarts';
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRouter } from 'vue-router';
import { fetchTeacherAssignments, type AssignmentItem } from '../../api/teacher';
import {
  fetchAssignmentAnalysis,
  fetchGradeTrends,
  type AssignmentAnalysis,
  type GradeTrends,
} from '../../api/teacherSuite';
import { parseApiError } from '../../api/errors';
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

const assignments = ref<AssignmentItem[]>([]);
const selectedId = ref('');
const analysis = ref<AssignmentAnalysis | null>(null);
const trends = ref<GradeTrends | null>(null);
const loading = ref(false);
const analysisLoading = ref(false);
const error = ref('');

const distChartRef = ref<HTMLDivElement | null>(null);
const trendChartRef = ref<HTMLDivElement | null>(null);
let distChart: echarts.ECharts | null = null;
let trendChart: echarts.ECharts | null = null;

function renderDistChart() {
  if (!distChartRef.value || !analysis.value) return;
  if (!distChart) distChart = echarts.init(distChartRef.value);
  const t = chartTokens.value;
  const dist = analysis.value.distribution;
  distChart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 40, right: 20, top: 20, bottom: 30 },
    tooltip: {
      backgroundColor: t.tooltip.backgroundColor,
      borderColor: t.tooltip.borderColor,
      textStyle: { color: t.tooltip.textColor },
    },
    xAxis: { type: 'category', data: dist.map((d) => d.label), axisLabel: { color: t.axisLabel } },
    yAxis: { type: 'value', minInterval: 1, axisLabel: { color: t.axisLabel }, splitLine: { lineStyle: { color: t.splitLine } } },
    series: [
      {
        type: 'bar',
        data: dist.map((d) => d.count),
        itemStyle: { borderRadius: [6, 6, 0, 0], color: t.palette[0] },
        barWidth: 28,
      },
    ],
  });
}

function renderTrendChart() {
  if (!trendChartRef.value || !trends.value) return;
  if (!trendChart) trendChart = echarts.init(trendChartRef.value);
  const t = chartTokens.value;
  const rows = trends.value.trend.filter((x) => x.avg_score !== null);
  trendChart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 40, right: 20, top: 20, bottom: 50 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: t.tooltip.backgroundColor,
      borderColor: t.tooltip.borderColor,
      textStyle: { color: t.tooltip.textColor },
    },
    xAxis: {
      type: 'category',
      data: rows.map((x) => x.title),
      axisLabel: { color: t.axisLabel, rotate: 24, fontSize: 10, width: 90, overflow: 'truncate' },
    },
    yAxis: { type: 'value', max: 100, axisLabel: { color: t.axisLabel }, splitLine: { lineStyle: { color: t.splitLine } } },
    series: [
      {
        type: 'line',
        data: rows.map((x) => x.avg_score),
        smooth: true,
        symbolSize: 8,
        lineStyle: { color: t.accent, width: 2.5 },
        itemStyle: { color: t.accent },
        areaStyle: { color: t.accentSoft },
      },
    ],
  });
}

async function load() {
  if (!classId.value) {
    assignments.value = [];
    trends.value = null;
    analysis.value = null;
    return;
  }
  loading.value = true;
  error.value = '';
  try {
    const [asn, tr] = await Promise.all([fetchTeacherAssignments(classId.value), fetchGradeTrends(classId.value)]);
    assignments.value = asn;
    trends.value = tr;
    if (!selectedId.value && asn.length) selectedId.value = asn[0].id;
    await nextTick();
    renderTrendChart();
  } catch (e) {
    error.value = parseApiError(e, '加载成绩分析失败');
  } finally {
    loading.value = false;
  }
}

async function loadAnalysis() {
  if (!selectedId.value) {
    analysis.value = null;
    return;
  }
  analysisLoading.value = true;
  try {
    analysis.value = await fetchAssignmentAnalysis(selectedId.value);
    await nextTick();
    renderDistChart();
  } catch (e) {
    error.value = parseApiError(e, '加载作业分析失败');
  } finally {
    analysisLoading.value = false;
  }
}

function openStudent(id: string) {
  void router.push({ path: `/teacher/students/${id}`, query: { class_id: classId.value } });
}

function onResize() {
  distChart?.resize();
  trendChart?.resize();
}

watch(classId, () => {
  selectedId.value = '';
  void load();
});
watch(selectedId, () => void loadAnalysis());
watch(chartTokens, () => {
  renderDistChart();
  renderTrendChart();
});

onMounted(async () => {
  await load();
  await loadAnalysis();
  window.addEventListener('resize', onResize);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize);
  distChart?.dispose();
  trendChart?.dispose();
});
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="成绩分析" subtitle="单次作业分数分布 · 班级均分趋势 · 学生进退步排名" />

    <TeacherLoading v-if="loading && !trends" :rows="6" />
    <p v-else-if="error" class="rounded-xl border border-t-danger/30 bg-t-danger/10 px-4 py-3 text-sm text-t-danger">{{ error }}</p>

    <template v-else>
      <!-- 单次作业分析 -->
      <section class="t-card glass-edge p-5">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h3 class="text-[15px] font-semibold text-t-1">单次作业分析</h3>
          <select v-model="selectedId" class="t-input w-auto max-w-[320px] cursor-pointer py-1.5 text-sm">
            <option value="">选择作业</option>
            <option v-for="a in assignments" :key="a.id" :value="a.id">{{ a.title }}</option>
          </select>
        </div>

        <TeacherLoading v-if="analysisLoading" class="mt-3" :rows="3" />
        <template v-else-if="analysis">
          <div class="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-6">
            <TeacherStatCard label="应交 / 已交" :value="`${analysis.total_students} / ${analysis.submitted_count}`" />
            <TeacherStatCard label="已批改" :value="analysis.graded_count" />
            <TeacherStatCard label="未提交" :value="analysis.missing_count" accent="rose" />
            <TeacherStatCard label="平均分" :value="analysis.avg_score ?? '—'" accent="emerald" />
            <TeacherStatCard label="最高 / 最低" :value="analysis.max_score !== null ? `${analysis.max_score} / ${analysis.min_score}` : '—'" />
            <TeacherStatCard label="及格率" :value="analysis.pass_rate !== null ? `${analysis.pass_rate}%` : '—'" accent="sky" />
          </div>

          <div class="mt-4 grid gap-4 xl:grid-cols-2">
            <div>
              <p class="text-xs font-medium text-t-2">分数段分布</p>
              <div ref="distChartRef" class="mt-2 h-56 w-full"></div>
            </div>
            <div>
              <p class="text-xs font-medium text-t-2">学生得分明细</p>
              <div class="t-table-wrap mt-2 max-h-56 overflow-y-auto">
                <table class="t-table">
                  <thead>
                    <tr><th>学生</th><th>分数</th><th>状态</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="s in analysis.students" :key="s.student_id" class="is-clickable" @click="openStudent(s.student_id)">
                      <td class="font-medium text-t-1">{{ s.student_name }}</td>
                      <td class="font-mono-tech">{{ s.score ?? '—' }}</td>
                      <td>
                        <span class="t-badge" :class="s.status === 'graded' ? 't-badge--ok' : 't-badge--warn'">
                          {{ s.status === 'graded' ? '已批改' : '待批改' }}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
                <TeacherEmptyState v-if="!analysis.students.length" class="m-3" title="暂无提交" />
              </div>
            </div>
          </div>
        </template>
        <TeacherEmptyState v-else class="mt-4" title="请选择作业" description="选择一次作业查看分数分布与明细" />
      </section>

      <!-- 班级趋势 -->
      <section class="t-card glass-edge p-5">
        <div class="flex items-baseline justify-between gap-2">
          <h3 class="text-[15px] font-semibold text-t-1">班级均分趋势</h3>
          <span class="t-kicker">Trend</span>
        </div>
        <div v-if="trends?.trend?.some((x) => x.avg_score !== null)" ref="trendChartRef" class="mt-3 h-64 w-full"></div>
        <TeacherEmptyState v-else class="mt-3" title="暂无趋势数据" description="批改两次以上作业后可见" />
      </section>

      <!-- 进退步排名 -->
      <section class="t-card glass-edge p-5">
        <div class="flex items-baseline justify-between gap-2">
          <h3 class="text-[15px] font-semibold text-t-1">学生进退步排名</h3>
          <span class="t-kicker">按后期与前期均分差值</span>
        </div>
        <div class="t-table-wrap mt-3">
          <table class="t-table">
            <thead>
              <tr><th>学生</th><th>参与作业</th><th>近期均分</th><th>进退步</th></tr>
            </thead>
            <tbody>
              <tr v-for="p in trends?.progress || []" :key="p.student_id" class="is-clickable" @click="openStudent(p.student_id)">
                <td class="font-medium text-t-1">{{ p.student_name }}</td>
                <td class="font-mono-tech">{{ p.assignment_count }}</td>
                <td class="font-mono-tech">{{ p.recent_avg }}</td>
                <td>
                  <span class="font-mono-tech font-semibold" :class="p.delta >= 0 ? 'text-t-ok' : 'text-t-danger'">
                    {{ p.delta >= 0 ? '+' : '' }}{{ p.delta }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <TeacherEmptyState v-if="!trends?.progress?.length" class="m-4" title="暂无进退步数据" description="学生完成两次以上批改作业后可见" />
        </div>
      </section>
    </template>
  </div>
</template>

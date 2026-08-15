<script setup lang="ts">
import * as echarts from 'echarts';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import {
  dispatchTask,
  fetchApiQuota,
  fetchClassOverview,
  fetchGravityWells,
  fetchProfileMatrix,
  fetchStudentRisks,
  forgeGalaxyFromPdf,
  interveneStudent,
  type ApiQuota,
  type ClassOverview,
  type GravityWell,
  type HeatItem,
  type ProfileMatrix,
  type StudentRisk,
} from '../api/dashboard';
import { apiPost } from '../api/client';
import { fetchClasses } from '../api/auth';
import { fetchGalaxies } from '../api/orbit';
import { uploadTeacherResource } from '../api/zone';
import TimeWarpSandbox from '../components/TimeWarpSandbox.vue';
import { useAuthStore } from '../stores/auth';

const auth = useAuthStore();
const router = useRouter();

const overview = ref<ClassOverview | null>(null);
const risks = ref<StudentRisk[]>([]);
const quota = ref<ApiQuota | null>(null);
const profileMatrix = ref<ProfileMatrix | null>(null);
const gravityWells = ref<GravityWell[]>([]);
const dispatchMsg = ref('');
const importText = ref('student010,王小明\nstudent011,李小红');
const importClassId = ref('');
const importMsg = ref('');
const classOptions = ref<{ id: string; name: string }[]>([]);
const forgeMsg = ref('');
const resourceTitle = ref('');
const resourceGalaxy = ref('');
const resourceClassId = ref('');
const resourceMsg = ref('');
const galaxies = ref<{ slug: string; name: string }[]>([]);
const matrixChartRef = ref<HTMLDivElement | null>(null);
const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
let matrixChart: echarts.ECharts | null = null;

const isAdmin = computed(() => auth.user?.role === 'admin');
const isTeacher = computed(() => auth.user?.role === 'teacher' || auth.user?.role === 'admin');

function riskColor(level: string) {
  return level === 'high' ? 'text-rose-300 border-rose-400/40 bg-rose-500/10'
    : level === 'medium' ? 'text-amber-300 border-amber-400/40 bg-amber-500/10'
    : 'text-emerald-300 border-emerald-400/40 bg-emerald-500/10';
}

function heatColor(rate: number): string {
  if (rate >= 70) return 'background:rgba(16,185,129,0.75)';
  if (rate >= 40) return 'background:rgba(245,158,11,0.7)';
  if (rate >= 15) return 'background:rgba(239,68,68,0.55)';
  return 'background:rgba(148,163,184,0.25)';
}

const heatByGalaxy = computed(() => {
  const map = new Map<string, HeatItem[]>();
  overview.value?.heatmap.forEach((h) => {
    if (!map.has(h.galaxy_name)) map.set(h.galaxy_name, []);
    map.get(h.galaxy_name)!.push(h);
  });
  return Array.from(map.entries());
});

function renderChart() {
  if (!chartRef.value || !overview.value) return;
  chart = echarts.init(chartRef.value);
  const items = overview.value.weakest_planets;
  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 130, right: 30, top: 10, bottom: 20 },
    xAxis: { type: 'value', max: 100, axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: 'rgba(148,163,184,0.12)' } } },
    yAxis: {
      type: 'category',
      data: items.map((i) => i.planet_name).reverse(),
      axisLabel: { color: '#cbd5e1', fontSize: 11 },
    },
    tooltip: { trigger: 'axis' },
    series: [
      {
        type: 'bar',
        data: items.map((i) => i.mastery_rate).reverse(),
        itemStyle: {
          borderRadius: [0, 6, 6, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#ef4444' },
            { offset: 1, color: '#f59e0b' },
          ]),
        },
        barWidth: 14,
        label: { show: true, position: 'right', formatter: '{c}%', color: '#e2e8f0' },
      },
    ],
  });
}

function renderMatrixChart() {
  if (!matrixChartRef.value || !profileMatrix.value) return;
  if (!matrixChart) matrixChart = echarts.init(matrixChartRef.value);
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
      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.15)' } },
      axisName: { color: '#cbd5e1', fontSize: 11 },
    },
    series: [{
      type: 'radar',
      data: [{ value: keys.map((k) => dims[k] ?? 50), name: profileMatrix.value.class_tendency_label }],
      areaStyle: { color: 'rgba(125,211,252,0.25)' },
      lineStyle: { color: '#7dd3fc' },
    }],
  });
}

async function loadAll() {
  const tasks: Promise<unknown>[] = [
    fetchClassOverview().then((d) => (overview.value = d)),
    fetchStudentRisks().then((d) => (risks.value = d)),
    fetchProfileMatrix().then((d) => (profileMatrix.value = d)),
    fetchGravityWells().then((d) => (gravityWells.value = d)),
    fetchGalaxies().then((d) => (galaxies.value = d.map((g) => ({ slug: g.slug, name: g.name })))),
  ];
  if (isAdmin.value) tasks.push(fetchApiQuota().then((d) => (quota.value = d)));
  await Promise.all(tasks);
}

async function handleUploadResource(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  resourceMsg.value = '正在上传班级资料…';
  try {
    const res = await uploadTeacherResource(
      file,
      resourceTitle.value.trim() || file.name,
      resourceGalaxy.value,
      resourceClassId.value,
    );
    resourceMsg.value = `资料「${res.title}」已上传，学生可在笔记面板下载`;
    resourceTitle.value = '';
  } catch {
    resourceMsg.value = '资料上传失败';
  }
  input.value = '';
}

async function handleIntervene(student: StudentRisk, planetSlug?: string) {
  dispatchMsg.value = '';
  try {
    const res = await interveneStudent(
      student.user_id,
      `${student.display_name} 同学，老师已为你派遣专属救援助手，请聚焦薄弱点逐步突破。`,
      planetSlug,
    );
    dispatchMsg.value = res.message || `已向 ${student.display_name} 投放救援助手`;
  } catch {
    dispatchMsg.value = '干预失败';
  }
}

async function handleForgePdf(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  forgeMsg.value = '正在解析 PDF 并生成星系…';
  try {
    const res = await forgeGalaxyFromPdf(file, file.name);
    forgeMsg.value = `星系「${res.galaxy_name}」已生成，共 ${res.planet_count} 颗行星`;
    await loadAll();
  } catch {
    forgeMsg.value = 'PDF 星系锻造失败';
  }
  input.value = '';
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

async function handleImport() {
  importMsg.value = '';
  const students = importText.value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [username, display_name] = line.split(',').map((s) => s.trim());
      return { username, display_name: display_name || username, password: '123456' };
    })
    .filter((s) => s.username);
  if (!students.length) return;
  try {
    const res = await apiPost<{ created: number; skipped: number }>('/api/admin/students/import', {
      students,
      class_id: importClassId.value,
    });
    importMsg.value = `导入完成：新增 ${res.created}，跳过 ${res.skipped}`;
    await loadAll();
  } catch {
    importMsg.value = '导入失败（需管理员权限）';
  }
}

function logout() {
  auth.logout();
  router.push('/');
}

watch(overview, () => {
  if (overview.value) renderChart();
});

watch(profileMatrix, () => {
  if (profileMatrix.value) renderMatrixChart();
});

onMounted(async () => {
  await loadAll();
  classOptions.value = await fetchClasses();
  importClassId.value = classOptions.value[0]?.id ?? '';
  window.addEventListener('resize', () => { chart?.resize(); matrixChart?.resize(); });
});

onBeforeUnmount(() => { chart?.dispose(); matrixChart?.dispose(); });
</script>

<template>
  <main class="min-h-screen bg-[#050816] px-6 py-6 text-sky-100">
    <section class="mx-auto max-w-7xl space-y-5">
      <header class="glass flex items-center justify-between rounded-2xl px-6 py-4">
        <div>
          <p class="text-[10px] uppercase tracking-[0.45em] text-sky-300/70">SparkOrbit · 舰队指挥中心</p>
          <h1 class="mt-1 text-2xl font-semibold text-white">管理员 · 宇宙矩阵中心</h1>
        </div>
        <button class="glass rounded-2xl px-4 py-2 text-sm text-slate-200 hover:bg-white/10" @click="logout">退出登录</button>
      </header>

      <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div class="glass rounded-2xl p-4"><p class="text-xs text-slate-400">班级学生</p><p class="mt-1 text-2xl font-semibold text-white">{{ overview?.total_students ?? 0 }}</p></div>
        <div class="glass rounded-2xl p-4"><p class="text-xs text-slate-400">知识行星</p><p class="mt-1 text-2xl font-semibold text-white">{{ overview?.total_planets ?? 0 }}</p></div>
        <div class="glass rounded-2xl p-4"><p class="text-xs text-slate-400">平均掌握率</p><p class="mt-1 text-2xl font-semibold text-emerald-300">{{ overview?.avg_mastery_rate ?? 0 }}%</p></div>
        <div class="glass rounded-2xl p-4"><p class="text-xs text-slate-400">高风险学生</p><p class="mt-1 text-2xl font-semibold text-rose-300">{{ risks.filter((r) => r.risk_level === 'high').length }}</p></div>
      </div>

      <div class="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <section class="glass rounded-2xl p-5">
          <h2 class="text-base font-semibold text-white">最薄弱的知识行星（掌握率最低）</h2>
          <p class="text-xs text-slate-400">用于定位班级整体最需要干预的知识点。</p>
          <div ref="chartRef" class="mt-3 h-64 w-full"></div>
        </section>

        <section class="glass rounded-2xl p-5">
          <h2 class="text-base font-semibold text-white">二维星图热力</h2>
          <p class="text-xs text-slate-400">每格为一颗行星，颜色越暗代表掌握度越差。</p>
          <div class="mt-3 max-h-64 space-y-3 overflow-auto pr-1">
            <div v-for="[galaxy, planets] in heatByGalaxy" :key="galaxy">
              <p class="mb-1 text-xs text-sky-200">{{ galaxy }}</p>
              <div class="flex flex-wrap gap-1.5">
                <div
                  v-for="p in planets"
                  :key="p.planet_slug"
                  class="flex h-9 min-w-16 flex-1 items-center justify-center rounded-md px-2 text-[10px] text-white/90"
                  :style="heatColor(p.mastery_rate)"
                  :title="`${p.planet_name}：${p.mastery_rate}%（${p.lit_count}/${p.total_students}）`"
                >{{ p.planet_name }}</div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div class="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <section class="glass rounded-2xl p-5">
          <h2 class="text-base font-semibold text-white">群体六维画像矩阵</h2>
          <p class="text-xs text-slate-400">
            班级整体倾向：
            <span class="text-sky-300">{{ profileMatrix?.class_tendency_label ?? '加载中' }}</span>
            （探索 {{ profileMatrix?.explore_score ?? 0 }} / 保守 {{ profileMatrix?.conservative_score ?? 0 }}）
          </p>
          <div ref="matrixChartRef" class="mt-3 h-64 w-full"></div>
        </section>

        <section class="glass rounded-2xl p-5">
          <h2 class="text-base font-semibold text-white">引力陷阱预警</h2>
          <p class="text-xs text-slate-400">>60% 学生卡壳的行星形成引力黑洞</p>
          <div class="mt-3 max-h-64 space-y-2 overflow-auto">
            <div
              v-for="w in gravityWells"
              :key="w.planet_slug"
              class="flex items-center justify-between rounded-xl border px-3 py-2"
              :class="w.severity === 'critical' ? 'border-rose-400/40 bg-rose-500/10' : 'border-amber-400/30 bg-amber-500/10'"
            >
              <div>
                <p class="text-sm text-white">{{ w.planet_name }}</p>
                <p class="text-[10px] text-slate-400">{{ w.galaxy_name }}</p>
              </div>
              <span class="text-sm font-semibold text-rose-200">{{ w.stuck_rate }}% 卡壳</span>
            </div>
            <p v-if="!gravityWells.length" class="text-xs text-slate-500">暂无引力陷阱，班级状态良好。</p>
          </div>
        </section>
      </div>

      <TimeWarpSandbox />

      <section class="glass rounded-2xl p-5">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-base font-semibold text-white">认知状态低迷学生 · 预警干预</h2>
            <p class="text-xs text-slate-400">系统按掌握率与近期错误自动分级，可一键派发智能复习任务。</p>
          </div>
          <span v-if="dispatchMsg" class="text-xs text-emerald-300">{{ dispatchMsg }}</span>
        </div>
        <div class="mt-3 space-y-2">
          <div v-for="s in risks" :key="s.user_id" class="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-4 py-2.5">
            <div class="flex items-center gap-3">
              <span class="rounded-full border px-2 py-0.5 text-[10px]" :class="riskColor(s.risk_level)">{{ s.risk_level === 'high' ? '高风险' : s.risk_level === 'medium' ? '中风险' : '稳定' }}</span>
              <span class="text-sm text-white">{{ s.display_name }}</span>
              <span class="text-[11px] text-slate-400">掌握 {{ s.mastery_rate }}% · 点亮 {{ s.lit_count }}/{{ s.total_planets }} · 近期错误 {{ s.recent_wrong }}</span>
            </div>
            <div class="flex gap-2">
              <button class="rounded-lg border border-sky-300/20 bg-sky-400/10 px-3 py-1.5 text-xs text-sky-100 hover:bg-sky-400/20" @click="handleDispatch(s)">派发复习</button>
              <button class="rounded-lg border border-purple-300/20 bg-purple-400/10 px-3 py-1.5 text-xs text-purple-100 hover:bg-purple-400/20" @click="handleIntervene(s)">救援助手</button>
            </div>
          </div>
        </div>
      </section>

      <section v-if="isAdmin" class="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <div class="glass rounded-2xl p-5">
          <h2 class="text-base font-semibold text-white">大模型调用监控</h2>
          <div class="mt-3 space-y-2 text-sm text-slate-300">
            <p>DeepSeek 配置：<span :class="quota?.deepseek_configured ? 'text-emerald-300' : 'text-rose-300'">{{ quota?.deepseek_configured ? '已配置' : '未配置' }}</span></p>
            <p>模型：<span class="text-sky-200">{{ quota?.deepseek_model }}</span></p>
            <p>画像抽取次数：<span class="text-white">{{ quota?.total_extractions ?? 0 }}</span></p>
            <p>出题次数：<span class="text-white">{{ quota?.total_challenges ?? 0 }}</span></p>
          </div>
        </div>
        <div class="glass rounded-2xl p-5">
          <h2 class="text-base font-semibold text-white">星际造物主 · 星系锻造</h2>
          <p class="text-xs text-slate-400">上传 PDF 讲义，自动解析层级并生成新星系</p>
          <label class="mt-3 flex cursor-pointer flex-col items-center rounded-xl border border-dashed border-purple-400/30 bg-purple-500/5 px-4 py-6 text-sm text-purple-200 hover:bg-purple-500/10">
            <span class="inline-flex items-center gap-1.5"><img class="h-4 w-4" src="/icons/file.svg" alt="" aria-hidden="true" /> 点击上传 PDF 讲义</span>
            <input type="file" accept=".pdf" class="hidden" @change="handleForgePdf" />
          </label>
          <p v-if="forgeMsg" class="mt-2 text-xs text-sky-300">{{ forgeMsg }}</p>
        </div>
        <div class="glass rounded-2xl p-5">
          <h2 class="text-base font-semibold text-white">导入学生名单</h2>
          <p class="text-xs text-slate-400">每行一个：用户名,姓名（默认密码 123456）</p>
          <select v-model="importClassId" class="mt-2 w-full rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 outline-none">
            <option value="">不绑定班级</option>
            <option v-for="c in classOptions" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <textarea v-model="importText" class="mt-2 h-24 w-full rounded-xl border border-white/10 bg-slate-950/70 p-2.5 text-sm text-slate-100 outline-none"></textarea>
          <button class="mt-2 rounded-xl bg-gradient-to-r from-sky-500 to-purple-500 px-4 py-2 text-sm font-semibold text-white" @click="handleImport">批量导入</button>
          <p v-if="importMsg" class="mt-2 text-xs text-sky-300">{{ importMsg }}</p>
        </div>
      </section>
    </section>
  </main>
</template>

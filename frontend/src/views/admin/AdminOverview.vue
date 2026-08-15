<script setup lang="ts">
import * as echarts from 'echarts';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import {
  fetchAdminAgentRuns,
  fetchAdminAlerts,
  fetchAdminErrors,
  fetchAdminJobs,
  fetchAdminUsage,
  fetchSystemOverview,
  type AgentRunSummary,
  type ApiErrorItem,
  type ApiUsageSummary,
  type JobStatusItem,
  type ModelConfigItem,
  type SystemOverview,
} from '../../api/admin';
import { parseApiError } from '../../api/errors';
import AdminPageHeader from '../../components/admin/AdminPageHeader.vue';
import { adminNavItems } from '../../components/admin/adminNav';
import OrbCore, { type OrbState } from '../../components/common/orb/OrbCore.vue';
import { useAdminTheme } from '../../composables/useAdminTheme';
import { useCountUp } from '../../composables/useCountUp';
import { relativeTime } from '../../utils/relativeTime';

const router = useRouter();
const { isLight } = useAdminTheme();

const overview = ref<SystemOverview | null>(null);
const usage = ref<ApiUsageSummary[]>([]);
const recentErrors = ref<ApiErrorItem[]>([]);
const recentRuns = ref<AgentRunSummary[]>([]);
const openAlerts = ref(0);
const jobs = ref<JobStatusItem[]>([]);
const msg = ref('');
const loading = ref(false);

const healthState = computed<OrbState>(() => {
  if (msg.value) return 'error';
  if (!overview.value) return 'thinking';
  if (overview.value.maintenance_enabled || overview.value.today_errors > 0) return 'alert';
  return 'idle';
});

const healthLabel = computed(() => {
  if (msg.value) return '加载异常';
  if (!overview.value) return '巡检中…';
  if (overview.value.maintenance_enabled) return '维护模式';
  if (overview.value.today_errors > 0) return '存在异常';
  return '系统健康';
});

const userCount = useCountUp(computed(() => overview.value?.user_count ?? 0));
const todayCalls = useCountUp(computed(() => overview.value?.today_calls ?? 0));
const todayTokens = useCountUp(computed(() => overview.value?.today_tokens ?? 0));
const todayErrors = useCountUp(computed(() => overview.value?.today_errors ?? 0));

const fallbackModels = computed<ModelConfigItem[]>(() => {
  if (!overview.value) return [];
  return [
    {
      key: 'deepseek',
      name: 'DeepSeek 文本',
      model: overview.value.deepseek_model,
      configured: overview.value.deepseek_configured,
    },
  ];
});

const models = computed(() =>
  overview.value?.models?.length ? overview.value.models : fallbackModels.value,
);

const quickLinks = computed(() => adminNavItems.filter((i) => i.path !== '/admin'));

const MODE_BADGE: Record<string, string> = {
  workflow: 't-badge--info',
  handoff: 't-badge--ok',
  supervisor: 't-badge--neutral',
  council: 't-badge--warn',
};

function runStatusBadge(status: string) {
  if (status === 'running') return 't-badge--info';
  if (status === 'completed') return 't-badge--ok';
  if (status === 'failed') return 't-badge--danger';
  return 't-badge--neutral';
}

/* ---- 用量图表 ---- */
const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

const topUsage = computed(() =>
  [...usage.value].sort((a, b) => b.total_tokens - a.total_tokens).slice(0, 8).reverse(),
);

function renderChart() {
  if (!chartRef.value || !topUsage.value.length) return;
  if (!chart) {
    chart = echarts.init(chartRef.value);
    resizeObserver = new ResizeObserver(() => chart?.resize());
    resizeObserver.observe(chartRef.value);
  }
  const light = isLight.value;
  const axisColor = light ? '#64748b' : '#64748b';
  const labelColor = light ? '#334155' : '#cbd5e1';
  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 8, right: 52, top: 8, bottom: 8, containLabel: true },
    xAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: light ? 'rgba(15,23,42,0.08)' : 'rgba(51,65,85,0.4)' } },
      axisLabel: { color: axisColor, fontSize: 10 },
    },
    yAxis: {
      type: 'category',
      data: topUsage.value.map((u) => u.endpoint),
      axisLabel: {
        color: labelColor,
        fontSize: 10,
        fontFamily: 'JetBrains Mono, monospace',
        formatter: (v: string) => (v.length > 22 ? `${v.slice(0, 22)}…` : v),
      },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: 'bar',
        data: topUsage.value.map((u) => u.total_tokens),
        barWidth: 12,
        itemStyle: {
          borderRadius: [0, 6, 6, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: light ? 'rgba(2,132,199,0.85)' : 'rgba(56,189,248,0.85)' },
            { offset: 1, color: light ? 'rgba(124,58,237,0.65)' : 'rgba(167,139,250,0.65)' },
          ]),
        },
        label: {
          show: true,
          position: 'right',
          color: axisColor,
          fontSize: 10,
          fontFamily: 'JetBrains Mono, monospace',
        },
      },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: light ? '#ffffff' : '#0f172a',
      borderColor: light ? 'rgba(15,23,42,0.12)' : '#334155',
      textStyle: { color: light ? '#0f172a' : '#e2e8f0', fontSize: 11 },
      formatter: (params: unknown) => {
        const arr = params as { dataIndex: number }[];
        const row = topUsage.value[arr?.[0]?.dataIndex ?? 0];
        if (!row) return '';
        return `${row.endpoint}<br/>调用 ${row.calls} 次 · 共 ${row.total_tokens} tokens`;
      },
    },
  });
}

watch([topUsage, isLight], async () => {
  await nextTick();
  renderChart();
});

async function load() {
  loading.value = true;
  msg.value = '';
  const [ov, us, er, ru, al, jb] = await Promise.allSettled([
    fetchSystemOverview(),
    fetchAdminUsage(7),
    fetchAdminErrors(5),
    fetchAdminAgentRuns({ limit: 5 }),
    fetchAdminAlerts({ status_filter: 'open', limit: 1 }),
    fetchAdminJobs(),
  ]);
  if (ov.status === 'fulfilled') overview.value = ov.value;
  else msg.value = parseApiError(ov.reason, '加载失败');
  if (us.status === 'fulfilled') usage.value = us.value;
  if (er.status === 'fulfilled') recentErrors.value = er.value;
  if (ru.status === 'fulfilled') recentRuns.value = ru.value;
  if (al.status === 'fulfilled') openAlerts.value = al.value.open_count;
  if (jb.status === 'fulfilled') jobs.value = jb.value;
  loading.value = false;
  await nextTick();
  renderChart();
}

onMounted(load);

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div class="space-y-5">
    <AdminPageHeader
      kicker="Control Center"
      title="系统概览"
      subtitle="平台健康、调用量与维护状态一览"
    >
      <template #actions>
        <button type="button" class="t-btn t-btn--md t-btn--ghost" :disabled="loading" @click="load">
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </template>
    </AdminPageHeader>

    <p v-if="msg" class="rounded-xl border border-t-danger/25 bg-t-danger/10 px-4 py-3 text-sm text-t-danger">
      {{ msg }}
    </p>

    <!-- Bento 第一行：健康 hero + 大模型配置 -->
    <div class="grid gap-4 lg:grid-cols-3">
      <section class="t-card flex flex-wrap items-center justify-between gap-4 p-5 lg:col-span-2">
        <div class="flex items-center gap-4">
          <OrbCore :state="healthState" palette="violet" :size="84" :label="`系统健康度：${healthLabel}`" />
          <div>
            <p class="t-kicker">System Pulse</p>
            <p class="mt-1 text-lg font-semibold text-t-1">{{ healthLabel }}</p>
            <p v-if="overview?.maintenance_enabled && overview.maintenance_message" class="mt-1 max-w-md text-xs text-t-2">
              {{ overview.maintenance_message }}
            </p>
            <p v-else class="mt-1 text-xs text-t-3">今日调用、异常与维护状态实时汇总</p>
          </div>
        </div>
        <div class="flex flex-col items-end gap-2">
          <span
            v-if="overview"
            class="adm-pill"
            :class="overview.maintenance_enabled ? 'adm-pill--warn' : 'adm-pill--ok'"
          >
            <span class="adm-pill__dot" aria-hidden="true" />
            {{ overview.maintenance_enabled ? '维护中' : '运行正常' }}
          </span>
          <button
            v-if="openAlerts"
            type="button"
            class="adm-pill adm-pill--warn cursor-pointer"
            @click="router.push('/admin/alerts')"
          >
            <span class="adm-pill__dot" aria-hidden="true" />
            {{ openAlerts }} 条告警待处理
          </button>
        </div>
      </section>

      <section class="t-card p-5">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-t-1">大模型配置</h3>
          <span class="t-kicker">Models</span>
        </div>
        <ul class="mt-3 text-sm">
          <li
            v-for="item in models"
            :key="item.key"
            class="flex items-start justify-between gap-3 border-b border-t-line/8 py-2.5 last:border-0"
          >
            <div class="min-w-0">
              <p class="text-t-1/90">{{ item.name }}</p>
              <p class="mt-0.5 truncate font-mono text-xs text-t-3" :title="item.model">
                {{ item.model || '—' }}
              </p>
            </div>
            <span class="t-badge shrink-0" :class="item.configured ? 't-badge--ok' : 't-badge--warn'">
              {{ item.configured ? '已配置' : '未配置' }}
            </span>
          </li>
          <li v-if="!models.length" class="py-4 text-center text-xs text-t-3">暂无模型配置</li>
        </ul>
      </section>
    </div>

    <!-- Bento 第二行：KPI -->
    <div v-if="overview" class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <button type="button" class="adm-kpi adm-kpi--clickable p-4 text-left" @click="router.push('/admin/users')">
        <p class="text-xs text-t-2">注册用户</p>
        <p class="adm-kpi__value mt-2">{{ userCount }}</p>
        <p class="mt-1 text-[11px] text-t-3">学生 / 教师 / 管理员</p>
      </button>
      <button type="button" class="adm-kpi adm-kpi--clickable p-4 text-left" @click="router.push('/admin/usage')">
        <p class="text-xs text-t-2">今日 API 调用</p>
        <p class="adm-kpi__value mt-2">{{ todayCalls }}</p>
        <p class="mt-1 text-[11px] text-t-3">LLM 业务端点合计</p>
      </button>
      <button type="button" class="adm-kpi adm-kpi--clickable adm-kpi--ok p-4 text-left" @click="router.push('/admin/usage')">
        <p class="text-xs text-t-2">今日 Token</p>
        <p class="adm-kpi__value mt-2">{{ todayTokens }}</p>
        <p class="mt-1 text-[11px] text-t-3">prompt + completion</p>
      </button>
      <button
        type="button"
        class="adm-kpi adm-kpi--clickable p-4 text-left"
        :class="overview.today_errors ? 'adm-kpi--danger' : ''"
        @click="router.push('/admin/errors')"
      >
        <p class="text-xs text-t-2">今日异常</p>
        <p class="adm-kpi__value mt-2" :class="overview.today_errors ? '!text-t-danger' : ''">
          {{ todayErrors }}
        </p>
        <p class="mt-1 text-[11px] text-t-3">{{ overview.today_errors ? '点击查看详情' : '一切正常' }}</p>
      </button>
    </div>

    <!-- Bento 第三行：用量图表 + 最近异常 -->
    <div class="grid gap-4 lg:grid-cols-3">
      <section class="t-card p-5 lg:col-span-2">
        <div class="flex items-center justify-between">
          <div>
            <h3 class="text-sm font-semibold text-t-1">近 7 日端点用量</h3>
            <p class="mt-0.5 text-xs text-t-3">按 Token 消耗排序（前 8）</p>
          </div>
          <button type="button" class="t-btn t-btn--sm t-btn--ghost" @click="router.push('/admin/usage')">
            查看全部
          </button>
        </div>
        <div v-if="topUsage.length" ref="chartRef" class="mt-3 h-[240px] w-full" />
        <div v-else class="flex h-[240px] items-center justify-center text-sm text-t-3">
          暂无调用记录
        </div>
      </section>

      <section class="t-card p-5">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-t-1">最近异常</h3>
          <button type="button" class="t-btn t-btn--sm t-btn--ghost" @click="router.push('/admin/errors')">
            全部
          </button>
        </div>
        <ul v-if="recentErrors.length" class="mt-3 space-y-2.5">
          <li v-for="item in recentErrors" :key="item.id" class="rounded-xl border border-t-danger/15 bg-t-danger/5 p-2.5">
            <div class="flex items-center justify-between gap-2">
              <span class="truncate font-mono text-[11px] text-t-danger/90">{{ item.endpoint }}</span>
              <span class="shrink-0 text-[10px] text-t-3">{{ relativeTime(item.created_at) }}</span>
            </div>
            <p class="mt-1 line-clamp-2 text-xs text-t-2">{{ item.error_message }}</p>
          </li>
        </ul>
        <div v-else class="flex h-[200px] flex-col items-center justify-center gap-1.5 text-center">
          <span class="adm-pill adm-pill--ok"><span class="adm-pill__dot" aria-hidden="true" />无异常</span>
          <p class="text-xs text-t-3">系统调用一切正常</p>
        </div>
      </section>
    </div>

    <!-- Bento 第四行：最近 Agent 运行 + 快捷入口 -->
    <div class="grid gap-4 lg:grid-cols-3">
      <section class="t-card p-5 lg:col-span-2">
        <div class="flex items-center justify-between">
          <div>
            <h3 class="text-sm font-semibold text-t-1">最近 Agent 运行</h3>
            <p class="mt-0.5 text-xs text-t-3">资源工坊 / 镜像预演 / 伴学等编排回放</p>
          </div>
          <button type="button" class="t-btn t-btn--sm t-btn--ghost" @click="router.push('/admin/agents')">
            进入观测台
          </button>
        </div>
        <ul v-if="recentRuns.length" class="mt-3">
          <li
            v-for="run in recentRuns"
            :key="run.id"
            class="flex cursor-pointer flex-wrap items-center gap-2.5 border-b border-t-line/8 py-2.5 transition last:border-0 hover:bg-t-accent/5"
            @click="router.push('/admin/agents')"
          >
            <span class="adm-avatar">{{ (run.user_name || run.user_id || '?').slice(0, 1).toUpperCase() }}</span>
            <div class="min-w-0 flex-1">
              <p class="truncate text-[13px] text-t-1/90">{{ run.topic || run.scene }}</p>
              <p class="mt-0.5 truncate text-[11px] text-t-3">{{ run.user_name || run.user_id }} · {{ run.scene }}</p>
            </div>
            <span class="t-badge" :class="MODE_BADGE[run.mode] || 't-badge--neutral'">{{ run.mode }}</span>
            <span class="t-badge" :class="runStatusBadge(run.status)">{{ run.status }}</span>
            <span class="w-16 shrink-0 text-right text-[10px] text-t-3">{{ relativeTime(run.created_at) }}</span>
          </li>
        </ul>
        <div v-else class="flex h-[160px] items-center justify-center text-sm text-t-3">
          暂无运行记录，可在观测台注入四模式演示数据
        </div>
      </section>

      <section class="t-card p-5">
        <h3 class="text-sm font-semibold text-t-1">后台任务心跳</h3>
        <ul v-if="jobs.length" class="mt-3 space-y-2.5">
          <li v-for="job in jobs" :key="job.id" class="rounded-xl border border-t-line/10 bg-t-s1/30 p-2.5">
            <div class="flex items-center gap-2">
              <span class="h-1.5 w-1.5 rounded-full" :class="job.ok ? 'bg-t-ok' : job.last_run ? 'bg-t-danger' : 'bg-t-line/40'" />
              <span class="text-[13px] text-t-1/90">{{ job.label }}</span>
              <span class="ml-auto text-[10px] text-t-3">{{ job.last_run ? relativeTime(job.last_run) : '未执行' }}</span>
            </div>
            <p class="mt-1 truncate text-[11px] text-t-3" :title="job.detail">{{ job.detail }} · {{ job.interval }}</p>
          </li>
        </ul>
        <p v-else class="mt-3 text-xs text-t-3">后台任务尚未上报心跳</p>

        <h3 class="mt-4 text-sm font-semibold text-t-1">快捷入口</h3>
        <div class="mt-3 grid grid-cols-2 gap-2">
          <button
            v-for="link in quickLinks"
            :key="link.path"
            type="button"
            class="flex items-center gap-2 rounded-xl border border-t-line/12 bg-t-s1/30 px-3 py-2.5 text-left text-xs text-t-2 transition hover:border-t-accent/35 hover:bg-t-accent/8 hover:text-t-1"
            @click="router.push(link.path)"
          >
            <svg
              viewBox="0 0 16 16"
              class="h-3.5 w-3.5 shrink-0 opacity-80"
              fill="none"
              stroke="currentColor"
              stroke-width="1.3"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
              v-html="link.icon"
            />
            <span class="truncate">{{ link.label }}</span>
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

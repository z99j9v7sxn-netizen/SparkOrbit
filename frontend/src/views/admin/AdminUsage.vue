<script setup lang="ts">
import * as echarts from 'echarts';
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import {
  fetchAdminProviders,
  fetchAdminUsage,
  fetchApiQuota,
  refreshAdminProviderBalance,
  type ApiQuota,
  type ApiUsageSummary,
  type ProviderItem,
} from '../../api/admin';
import { parseApiError } from '../../api/errors';
import AdminEmptyState from '../../components/admin/AdminEmptyState.vue';
import AdminPageHeader from '../../components/admin/AdminPageHeader.vue';
import AdminSkeleton from '../../components/admin/AdminSkeleton.vue';
import { useAdminTheme } from '../../composables/useAdminTheme';

const { isLight } = useAdminTheme();

const quota = ref<ApiQuota | null>(null);
const usage = ref<ApiUsageSummary[]>([]);
const days = ref(7);
const msg = ref('');
const loading = ref(false);

/* ---- API 余额卡片 ---- */
const providers = ref<ProviderItem[]>([]);
const balanceRefreshing = ref(false);

function balanceState(p: ProviderItem): 'critical' | 'warn' | 'ok' | 'unknown' {
  const b = p.balance;
  if (!b || !b.ok) return 'unknown';
  if (b.is_available === false) return 'critical';
  const threshold = p.balance_warn_threshold ?? 0;
  if (threshold > 0 && (b.total_balance ?? 0) < threshold) return 'warn';
  return 'ok';
}

function fmtChecked(iso?: string): string {
  if (!iso) return '尚未检查';
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false });
  } catch {
    return iso;
  }
}

async function loadProviders() {
  try {
    providers.value = await fetchAdminProviders();
  } catch {
    providers.value = [];
  }
}

async function refreshBalance() {
  balanceRefreshing.value = true;
  try {
    await refreshAdminProviderBalance();
    await loadProviders();
  } catch (err) {
    msg.value = parseApiError(err, '余额刷新失败');
  } finally {
    balanceRefreshing.value = false;
  }
}

const DAY_OPTIONS = [7, 14, 30];

const sorted = computed(() => [...usage.value].sort((a, b) => b.total_tokens - a.total_tokens));
const maxTokens = computed(() => Math.max(...sorted.value.map((u) => u.total_tokens), 1));
const totalCalls = computed(() => usage.value.reduce((acc, u) => acc + u.calls, 0));
const totalTokens = computed(() => usage.value.reduce((acc, u) => acc + u.total_tokens, 0));

/* ---- 双维度条形图：调用次数 + Token ---- */
const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

const chartRows = computed(() => sorted.value.slice(0, 10).reverse());

function renderChart() {
  if (!chartRef.value || !chartRows.value.length) return;
  if (!chart) {
    chart = echarts.init(chartRef.value);
    resizeObserver = new ResizeObserver(() => chart?.resize());
    resizeObserver.observe(chartRef.value);
  }
  const light = isLight.value;
  const axisColor = '#64748b';
  const labelColor = light ? '#334155' : '#cbd5e1';
  const splitColor = light ? 'rgba(15,23,42,0.08)' : 'rgba(51,65,85,0.4)';
  chart.setOption({
    backgroundColor: 'transparent',
    legend: {
      top: 0,
      right: 0,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: axisColor, fontSize: 10 },
    },
    grid: { left: 8, right: 16, top: 28, bottom: 8, containLabel: true },
    xAxis: [
      {
        type: 'value',
        position: 'bottom',
        splitLine: { lineStyle: { color: splitColor } },
        axisLabel: { color: axisColor, fontSize: 10 },
      },
    ],
    yAxis: {
      type: 'category',
      data: chartRows.value.map((u) => u.endpoint),
      axisLabel: {
        color: labelColor,
        fontSize: 10,
        fontFamily: 'JetBrains Mono, monospace',
        formatter: (v: string) => (v.length > 24 ? `${v.slice(0, 24)}…` : v),
      },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        name: 'Token',
        type: 'bar',
        data: chartRows.value.map((u) => u.total_tokens),
        barWidth: 10,
        itemStyle: {
          borderRadius: [0, 5, 5, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: light ? 'rgba(2,132,199,0.85)' : 'rgba(56,189,248,0.85)' },
            { offset: 1, color: light ? 'rgba(124,58,237,0.6)' : 'rgba(167,139,250,0.6)' },
          ]),
        },
      },
      {
        name: '调用次数',
        type: 'bar',
        data: chartRows.value.map((u) => u.calls),
        barWidth: 5,
        itemStyle: {
          borderRadius: [0, 5, 5, 0],
          color: light ? 'rgba(5,150,105,0.7)' : 'rgba(52,211,153,0.7)',
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
        const row = chartRows.value[arr?.[0]?.dataIndex ?? 0];
        if (!row) return '';
        return `${row.endpoint}<br/>调用 ${row.calls} 次<br/>Prompt ${row.prompt_tokens} · Completion ${row.completion_tokens}<br/>共 ${row.total_tokens} tokens`;
      },
    },
  });
}

watch([chartRows, isLight], async () => {
  await nextTick();
  renderChart();
});

async function load() {
  loading.value = true;
  msg.value = '';
  const errors: string[] = [];
  try {
    quota.value = await fetchApiQuota();
  } catch (err) {
    quota.value = null;
    errors.push(parseApiError(err, '配额加载失败'));
  }
  try {
    usage.value = await fetchAdminUsage(days.value);
  } catch (err) {
    usage.value = [];
    errors.push(parseApiError(err, '用量明细加载失败'));
  }
  if (errors.length) msg.value = errors.join('；');
  loading.value = false;
  void loadProviders();
  await nextTick();
  renderChart();
}

function setDays(value: number) {
  if (days.value === value) return;
  days.value = value;
  void load();
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
      kicker="Usage Monitor"
      title="Token 用量"
      :subtitle="`按端点统计近 ${days} 日调用与 Token 消耗`"
    >
      <template #actions>
        <div class="t-tabs" role="tablist" aria-label="统计天数">
          <button
            v-for="d in DAY_OPTIONS"
            :key="d"
            type="button"
            role="tab"
            class="t-tab"
            :class="{ 'is-active': days === d }"
            :aria-selected="days === d"
            @click="setDays(d)"
          >
            {{ d }} 天
          </button>
        </div>
        <button type="button" class="t-btn t-btn--md t-btn--ghost" :disabled="loading" @click="load">
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </template>
    </AdminPageHeader>

    <p v-if="msg" class="rounded-xl border border-t-danger/25 bg-t-danger/10 px-4 py-3 text-sm text-t-danger">{{ msg }}</p>

    <!-- API 余额卡片区 -->
    <section v-if="providers.length" class="t-card p-5">
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-sm font-semibold text-t-1">API 余额</h3>
          <p class="mt-0.5 text-xs text-t-3">各平台配置状态与账户余额（DeepSeek 支持在线查询）</p>
        </div>
        <button
          type="button"
          class="t-btn t-btn--sm t-btn--ghost"
          :disabled="balanceRefreshing"
          @click="refreshBalance"
        >
          {{ balanceRefreshing ? '刷新中…' : '刷新余额' }}
        </button>
      </div>
      <div class="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div
          v-for="p in providers"
          :key="p.id"
          class="rounded-xl border p-3.5"
          :class="{
            'border-t-danger/40 bg-t-danger/5': balanceState(p) === 'critical',
            'border-t-warn/40 bg-t-warn/5': balanceState(p) === 'warn',
            'border-t-line bg-t-s2/40': balanceState(p) === 'ok' || balanceState(p) === 'unknown',
          }"
        >
          <div class="flex items-center justify-between">
            <p class="text-sm font-semibold text-t-1">{{ p.label }}</p>
            <span
              class="rounded-full px-2 py-0.5 text-[10px] font-medium"
              :class="p.configured ? 'bg-t-ok/15 text-t-ok' : 'bg-t-s2 text-t-3'"
            >
              {{ p.configured ? '已配置' : '未配置' }}
            </span>
          </div>
          <template v-if="p.balance_supported">
            <template v-if="p.balance && p.balance.ok">
              <p
                class="mt-2 font-mono text-xl font-bold"
                :class="{
                  'text-t-danger': balanceState(p) === 'critical',
                  'text-t-warn': balanceState(p) === 'warn',
                  'text-t-1': balanceState(p) === 'ok',
                }"
              >
                {{ p.balance.total_balance ?? 0 }} {{ p.balance.currency || 'CNY' }}
              </p>
              <p class="mt-1 text-[11px]" :class="p.balance.is_available === false ? 'text-t-danger' : 'text-t-2'">
                {{ p.balance.is_available === false ? '账户不可用（余额耗尽）' : `预警阈值 ${p.balance_warn_threshold ?? 0} 元` }}
              </p>
              <p class="mt-1 text-[11px] text-t-3">检查于 {{ fmtChecked(p.balance.checked_at) }}</p>
            </template>
            <template v-else>
              <p class="mt-2 text-xs text-t-3">
                {{ p.configured ? (p.balance?.error ? `查询失败：${p.balance.error}` : '余额尚未查询，可点击「刷新余额」') : '配置 Key 后可查询余额' }}
              </p>
            </template>
          </template>
          <template v-else>
            <p class="mt-2 text-xs text-t-3">平台不支持在线余额查询</p>
            <p class="mt-1 truncate text-[11px] text-t-3">{{ p.description }}</p>
          </template>
        </div>
      </div>
    </section>

    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <div class="adm-kpi p-4">
        <p class="text-xs text-t-2">{{ days }} 日总调用</p>
        <p class="adm-kpi__value mt-2">{{ totalCalls || quota?.total_calls_7d || '—' }}</p>
      </div>
      <div class="adm-kpi adm-kpi--ok p-4">
        <p class="text-xs text-t-2">{{ days }} 日总 Token</p>
        <p class="adm-kpi__value mt-2">{{ totalTokens || quota?.total_tokens_7d || '—' }}</p>
      </div>
      <div class="adm-kpi adm-kpi--accent2 p-4">
        <p class="text-xs text-t-2">画像抽取次数</p>
        <p class="adm-kpi__value mt-2">{{ quota?.total_extractions ?? '—' }}</p>
      </div>
      <div class="adm-kpi adm-kpi--warn p-4">
        <p class="text-xs text-t-2">挑战题生成</p>
        <p class="adm-kpi__value mt-2">{{ quota?.total_challenges ?? '—' }}</p>
      </div>
    </div>

    <!-- 用量图表 -->
    <section v-if="chartRows.length" class="t-card p-5">
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-sm font-semibold text-t-1">端点用量分布</h3>
          <p class="mt-0.5 text-xs text-t-3">按 Token 消耗排序（前 10）· 双维度对比</p>
        </div>
      </div>
      <div ref="chartRef" class="mt-3 h-[300px] w-full" />
    </section>

    <!-- 明细表格 -->
    <AdminSkeleton v-if="loading && !usage.length" :rows="6" />
    <AdminEmptyState
      v-else-if="!sorted.length"
      title="暂无调用记录"
      hint="学生生成路径、挑战答题等 LLM 调用后将在此汇总"
    />
    <transition v-else name="fade-scale" appear>
      <div class="t-table-wrap">
        <table class="t-table">
          <thead>
            <tr>
              <th>端点</th>
              <th>调用次数</th>
              <th>Prompt</th>
              <th>Completion</th>
              <th class="w-52">总 Tokens</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in sorted" :key="row.endpoint">
              <td class="font-mono text-xs text-t-accent/90">{{ row.endpoint }}</td>
              <td class="font-mono text-[13px]">{{ row.calls }}</td>
              <td class="font-mono text-[13px] text-t-2">{{ row.prompt_tokens }}</td>
              <td class="font-mono text-[13px] text-t-2">{{ row.completion_tokens }}</td>
              <td>
                <div class="flex items-center gap-2.5">
                  <span class="w-16 shrink-0 font-mono text-[13px] font-medium text-t-1">{{ row.total_tokens }}</span>
                  <div class="adm-ratio min-w-0 flex-1">
                    <span class="adm-ratio__fill" :style="{ width: `${Math.max((row.total_tokens / maxTokens) * 100, 2)}%` }" />
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </transition>
  </div>
</template>

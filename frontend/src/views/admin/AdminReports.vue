<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import {
  fetchSecurityReportDetail,
  fetchSecurityReports,
  generateSecurityReport,
  type SecurityReportItem,
} from '../../api/admin';
import { parseApiError } from '../../api/errors';
import AdminEmptyState from '../../components/admin/AdminEmptyState.vue';
import AdminPageHeader from '../../components/admin/AdminPageHeader.vue';
import AdminSkeleton from '../../components/admin/AdminSkeleton.vue';
import MarkdownView from '../../components/common/MarkdownView.vue';
import { relativeTime } from '../../utils/relativeTime';

const reports = ref<SecurityReportItem[]>([]);
const current = ref<SecurityReportItem | null>(null);
const loading = ref(true);
const detailLoading = ref(false);
const generating = ref(false);
const msg = ref('');
const msgTone = ref<'ok' | 'err'>('ok');

const todayStr = new Date().toISOString().slice(0, 10);

interface SummaryKpi {
  label: string;
  value: string;
  tone?: string;
}

const summaryKpis = computed<SummaryKpi[]>(() => {
  const s = current.value?.summary as Record<string, Record<string, number>> | undefined;
  if (!s) return [];
  const api = s.api || {};
  const login = s.login || {};
  const alerts = s.alerts || {};
  const users = s.users || {};
  return [
    { label: 'API 调用', value: String(api.calls ?? 0) },
    { label: '调用失败', value: String(api.errors ?? 0), tone: (api.errors ?? 0) > 0 ? 'danger' : '' },
    { label: 'Token 消耗', value: String(api.tokens ?? 0) },
    { label: '活跃用户', value: String(users.active ?? 0) },
    { label: '登录失败', value: String(login.failed ?? 0), tone: (login.failed ?? 0) > 0 ? 'warn' : '' },
    { label: '新增告警', value: String(alerts.created ?? 0), tone: (alerts.created ?? 0) > 0 ? 'warn' : '' },
  ];
});

async function load() {
  loading.value = true;
  msg.value = '';
  try {
    reports.value = await fetchSecurityReports();
    if (reports.value.length && !current.value) {
      await openReport(reports.value[0].report_date);
    }
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '日报列表加载失败');
  } finally {
    loading.value = false;
  }
}

async function openReport(date: string) {
  detailLoading.value = true;
  try {
    current.value = await fetchSecurityReportDetail(date);
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '日报加载失败');
  } finally {
    detailLoading.value = false;
  }
}

async function generateToday(force = false) {
  generating.value = true;
  msg.value = '';
  try {
    const report = await generateSecurityReport(todayStr, force);
    current.value = report;
    msgTone.value = 'ok';
    msg.value = `已生成 ${report.report_date} 日报（${report.generated_by === 'llm' ? 'AI 摘要' : '规则模板'}）`;
    reports.value = await fetchSecurityReports();
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '日报生成失败');
  } finally {
    generating.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="space-y-5">
    <AdminPageHeader kicker="Daily Report" title="安全日报" subtitle="数据自动汇聚 + AI 摘要生成，规则模板兜底">
      <template #actions>
        <button type="button" class="t-btn t-btn--md t-btn--soft" :disabled="generating" @click="generateToday(true)">
          {{ generating ? '生成中…' : '生成今日日报' }}
        </button>
        <button type="button" class="t-btn t-btn--md t-btn--ghost" :disabled="loading" @click="load">
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </template>
    </AdminPageHeader>

    <p
      v-if="msg"
      class="rounded-xl border px-4 py-2.5 text-sm"
      :class="msgTone === 'ok' ? 'border-t-accent/20 bg-t-accent/8 text-t-accent' : 'border-t-danger/25 bg-t-danger/10 text-t-danger'"
    >
      {{ msg }}
    </p>

    <AdminSkeleton v-if="loading" :rows="5" />
    <AdminEmptyState
      v-else-if="!reports.length && !current"
      title="暂无日报"
      hint="系统每日自动生成前一日日报，也可点击「生成今日日报」立即体验"
    />
    <div v-else class="grid gap-4 lg:grid-cols-[260px_1fr]">
      <!-- 日报列表 -->
      <section class="t-card max-h-[70vh] overflow-y-auto p-3">
        <p class="px-2 py-1 text-xs font-semibold text-t-3">历史日报</p>
        <button
          v-for="r in reports"
          :key="r.report_date"
          type="button"
          class="mt-1 flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2.5 text-left transition"
          :class="current?.report_date === r.report_date ? 'bg-t-accent/10 text-t-1' : 'text-t-2 hover:bg-t-s1/40'"
          @click="openReport(r.report_date)"
        >
          <span class="font-mono text-[13px]">{{ r.report_date }}</span>
          <span class="t-badge" :class="r.generated_by === 'llm' ? 't-badge--info' : 't-badge--neutral'">
            {{ r.generated_by === 'llm' ? 'AI' : '规则' }}
          </span>
        </button>
      </section>

      <!-- 日报正文 -->
      <section class="t-card p-5">
        <AdminSkeleton v-if="detailLoading" :rows="6" />
        <template v-else-if="current">
          <div class="flex flex-wrap items-center gap-2">
            <h3 class="text-base font-semibold text-t-1">{{ current.report_date }} 安全日报</h3>
            <span class="t-badge" :class="current.generated_by === 'llm' ? 't-badge--info' : 't-badge--neutral'">
              {{ current.generated_by === 'llm' ? 'AI 摘要' : '规则模板' }}
            </span>
            <span class="ml-auto text-[11px] text-t-3" :title="current.created_at">
              生成于 {{ relativeTime(current.created_at) }}
            </span>
          </div>

          <div v-if="summaryKpis.length" class="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
            <div
              v-for="kpi in summaryKpis"
              :key="kpi.label"
              class="adm-kpi p-3"
              :class="kpi.tone === 'danger' ? 'adm-kpi--danger' : kpi.tone === 'warn' ? 'adm-kpi--warn' : ''"
            >
              <p class="text-[11px] text-t-2">{{ kpi.label }}</p>
              <p class="mt-1 font-mono text-lg font-semibold text-t-1">{{ kpi.value }}</p>
            </div>
          </div>

          <div class="mt-4 border-t border-t-line/10 pt-4">
            <MarkdownView :content="current.markdown_content" />
          </div>
        </template>
        <div v-else class="flex h-40 items-center justify-center text-sm text-t-3">从左侧选择一份日报查看</div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import {
  fetchAdminAlerts,
  scanAdminAlerts,
  triageAdminAlert,
  updateAdminAlert,
  type SystemAlertItem,
} from '../../api/admin';
import { parseApiError } from '../../api/errors';
import AdminEmptyState from '../../components/admin/AdminEmptyState.vue';
import AdminPageHeader from '../../components/admin/AdminPageHeader.vue';
import AdminSkeleton from '../../components/admin/AdminSkeleton.vue';
import MarkdownView from '../../components/common/MarkdownView.vue';
import { relativeTime } from '../../utils/relativeTime';
import { useCountUp } from '../../composables/useCountUp';

const alerts = ref<SystemAlertItem[]>([]);
const openCount = ref(0);
const loading = ref(true);
const scanning = ref(false);
const triagingId = ref('');
const msg = ref('');
const msgTone = ref<'ok' | 'err'>('ok');
const statusFilter = ref('');

const STATUS_TABS = [
  { value: '', label: '全部' },
  { value: 'open', label: '待处理' },
  { value: 'acked', label: '已确认' },
  { value: 'resolved', label: '已处置' },
  { value: 'false_positive', label: '误报' },
];

const LEVEL_BADGE: Record<string, string> = {
  critical: 't-badge--danger',
  warning: 't-badge--warn',
  info: 't-badge--info',
};
const LEVEL_LABEL: Record<string, string> = { critical: '严重', warning: '警告', info: '提示' };
const STATUS_BADGE: Record<string, string> = {
  open: 't-badge--danger',
  acked: 't-badge--warn',
  resolved: 't-badge--ok',
  false_positive: 't-badge--neutral',
};
const STATUS_LABEL: Record<string, string> = {
  open: '待处理',
  acked: '已确认',
  resolved: '已处置',
  false_positive: '误报',
};
const CATEGORY_LABEL: Record<string, string> = {
  llm_failure: 'LLM 故障',
  token_quota: 'Token 配额',
  agent_failure: 'Agent 失败',
  login_security: '登录安全',
};
const VERDICT_LABEL: Record<string, string> = {
  true_positive: '真阳性',
  false_positive: '误报',
  uncertain: '待人工确认',
};

const openAnim = useCountUp(computed(() => openCount.value));
const criticalCount = computed(
  () => alerts.value.filter((a) => a.level === 'critical' && a.status === 'open').length,
);

async function load() {
  loading.value = true;
  msg.value = '';
  try {
    const page = await fetchAdminAlerts({ status_filter: statusFilter.value, limit: 100 });
    alerts.value = page.items;
    openCount.value = page.open_count;
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '加载失败');
  } finally {
    loading.value = false;
  }
}

function setStatus(value: string) {
  if (statusFilter.value === value) return;
  statusFilter.value = value;
  void load();
}

async function scan() {
  scanning.value = true;
  msg.value = '';
  try {
    const res = await scanAdminAlerts();
    msgTone.value = 'ok';
    msg.value = res.count ? `扫描完成，新增 ${res.count} 条告警` : '扫描完成，未发现新告警';
    await load();
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '扫描失败');
  } finally {
    scanning.value = false;
  }
}

async function setAlertStatus(alert: SystemAlertItem, status: string) {
  try {
    const updated = await updateAdminAlert(alert.id, status);
    alerts.value = alerts.value.map((a) => (a.id === updated.id ? updated : a));
    openCount.value += (status === 'open' ? 1 : 0) - (alert.status === 'open' ? 1 : 0);
    msgTone.value = 'ok';
    msg.value = `已将告警标记为「${STATUS_LABEL[status] || status}」`;
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '操作失败');
  }
}

async function triage(alert: SystemAlertItem) {
  triagingId.value = alert.id;
  msg.value = '';
  try {
    const updated = await triageAdminAlert(alert.id);
    alerts.value = alerts.value.map((a) => (a.id === updated.id ? updated : a));
    msgTone.value = 'ok';
    msg.value = 'AI 研判完成';
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, 'AI 研判失败');
  } finally {
    triagingId.value = '';
  }
}

onMounted(load);
</script>

<template>
  <div class="space-y-5">
    <AdminPageHeader kicker="Alert Triage" title="告警中心" subtitle="规则引擎发现 → AI 研判 → 处置闭环">
      <template #actions>
        <button type="button" class="t-btn t-btn--md t-btn--soft" :disabled="scanning" @click="scan">
          {{ scanning ? '扫描中…' : '立即扫描' }}
        </button>
        <button type="button" class="t-btn t-btn--md t-btn--ghost" :disabled="loading" @click="load">
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </template>
    </AdminPageHeader>

    <div class="flex flex-wrap items-center gap-2.5">
      <div class="adm-kpi adm-kpi--danger px-4 py-3">
        <span class="text-xs text-t-2">待处理告警</span>
        <span class="ml-3 font-mono text-xl font-semibold" :class="openCount ? 'text-t-danger' : 'text-t-1'">{{ openAnim }}</span>
      </div>
      <div class="adm-kpi adm-kpi--warn px-4 py-3">
        <span class="text-xs text-t-2">其中严重</span>
        <span class="ml-3 font-mono text-xl font-semibold text-t-1">{{ criticalCount }}</span>
      </div>
      <div class="t-tabs ml-auto" role="tablist" aria-label="按状态筛选">
        <button
          v-for="t in STATUS_TABS"
          :key="t.value"
          type="button"
          role="tab"
          class="t-tab"
          :class="{ 'is-active': statusFilter === t.value }"
          @click="setStatus(t.value)"
        >
          {{ t.label }}
        </button>
      </div>
    </div>

    <p
      v-if="msg"
      class="rounded-xl border px-4 py-2.5 text-sm"
      :class="msgTone === 'ok' ? 'border-t-accent/20 bg-t-accent/8 text-t-accent' : 'border-t-danger/25 bg-t-danger/10 text-t-danger'"
    >
      {{ msg }}
    </p>

    <AdminSkeleton v-if="loading" :rows="5" variant="cards" />
    <AdminEmptyState
      v-else-if="!alerts.length"
      icon="✓"
      title="暂无告警"
      hint="规则引擎每 10 分钟自动扫描，也可点击「立即扫描」"
    />
    <transition v-else name="fade-scale" appear>
      <div class="space-y-3">
        <article v-for="alert in alerts" :key="alert.id" class="t-card p-4">
          <div class="flex flex-wrap items-center gap-2">
            <span class="t-badge" :class="LEVEL_BADGE[alert.level] || 't-badge--neutral'">
              {{ LEVEL_LABEL[alert.level] || alert.level }}
            </span>
            <span class="t-badge t-badge--neutral">{{ CATEGORY_LABEL[alert.category] || alert.category }}</span>
            <span class="text-sm font-medium text-t-1/90">{{ alert.title }}</span>
            <span class="ml-auto flex items-center gap-2">
              <span class="t-badge" :class="STATUS_BADGE[alert.status] || 't-badge--neutral'">
                {{ STATUS_LABEL[alert.status] || alert.status }}
              </span>
              <span class="text-[11px] text-t-3" :title="alert.created_at">{{ relativeTime(alert.created_at) }}</span>
            </span>
          </div>

          <p class="mt-2 text-sm text-t-2">{{ alert.detail }}</p>

          <!-- AI 研判结果 -->
          <div v-if="alert.triage_note" class="mt-3 rounded-xl border border-t-accent/20 bg-t-accent/5 p-3">
            <p class="flex items-center gap-2 text-xs font-semibold text-t-accent">
              AI 研判
              <span
                class="t-badge"
                :class="alert.triage_verdict === 'true_positive' ? 't-badge--danger' : alert.triage_verdict === 'false_positive' ? 't-badge--ok' : 't-badge--warn'"
              >
                {{ VERDICT_LABEL[alert.triage_verdict] || alert.triage_verdict }}
              </span>
            </p>
            <MarkdownView :content="alert.triage_note" class="mt-1.5 !text-xs" />
          </div>

          <div class="mt-3 flex flex-wrap items-center gap-2 border-t border-t-line/10 pt-3">
            <button
              type="button"
              class="t-btn t-btn--sm t-btn--soft"
              :disabled="triagingId === alert.id"
              @click="triage(alert)"
            >
              {{ triagingId === alert.id ? 'AI 研判中…' : alert.triage_note ? '重新研判' : 'AI 研判' }}
            </button>
            <span class="mx-1 h-4 w-px bg-t-line/20" aria-hidden="true" />
            <button
              v-if="alert.status === 'open'"
              type="button"
              class="t-btn t-btn--sm t-btn--ghost"
              @click="setAlertStatus(alert, 'acked')"
            >
              确认
            </button>
            <button
              v-if="alert.status !== 'resolved'"
              type="button"
              class="t-btn t-btn--sm t-btn--ghost"
              @click="setAlertStatus(alert, 'resolved')"
            >
              标记已处置
            </button>
            <button
              v-if="alert.status !== 'false_positive'"
              type="button"
              class="t-btn t-btn--sm t-btn--ghost"
              @click="setAlertStatus(alert, 'false_positive')"
            >
              标记误报
            </button>
            <button
              v-if="alert.status !== 'open'"
              type="button"
              class="t-btn t-btn--sm t-btn--ghost"
              @click="setAlertStatus(alert, 'open')"
            >
              重新打开
            </button>
          </div>
        </article>
      </div>
    </transition>
  </div>
</template>

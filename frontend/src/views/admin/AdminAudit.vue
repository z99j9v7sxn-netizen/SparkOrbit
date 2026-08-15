<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import {
  exportAdminCsv,
  fetchAuditLogs,
  fetchLoginLogs,
  type AuditLogItem,
  type LoginLogItem,
} from '../../api/admin';
import { parseApiError } from '../../api/errors';
import AdminEmptyState from '../../components/admin/AdminEmptyState.vue';
import AdminPageHeader from '../../components/admin/AdminPageHeader.vue';
import AdminSkeleton from '../../components/admin/AdminSkeleton.vue';
import { relativeTime } from '../../utils/relativeTime';

const tab = ref<'audit' | 'login'>('audit');
const loading = ref(true);
const msg = ref('');

const auditItems = ref<AuditLogItem[]>([]);
const auditTotal = ref(0);
const auditActions = ref<string[]>([]);
const actionFilter = ref('');
const days = ref(7);
const expandedId = ref('');

const loginItems = ref<LoginLogItem[]>([]);
const loginTotal = ref(0);
const riskyAccounts = ref<{ username: string; fails: number }[]>([]);
const successFilter = ref('');
const usernameFilter = ref('');

const ACTION_LABEL: Record<string, string> = {
  import_students: '批量导入学生',
  upsert_galaxy: '保存星系',
  upsert_planet: '保存行星',
  delete_planet: '删除行星',
  forge_galaxy: 'PDF 锻造星系',
  update_user: '更新用户',
  reset_password: '重置密码',
  batch_set_active: '批量启停',
  update_maintenance: '维护模式',
  update_settings: '修改系统配置',
  send_announcement: '发布公告',
  update_alert: '处置告警',
  update_feedback: '处理反馈',
  delete_file: '删除文件',
};

const DAY_OPTIONS = [7, 14, 30];

const failCount = computed(() => loginItems.value.filter((l) => !l.success).length);

async function loadAudit() {
  loading.value = true;
  msg.value = '';
  try {
    const page = await fetchAuditLogs({ action: actionFilter.value, days: days.value, limit: 100 });
    auditItems.value = page.items;
    auditTotal.value = page.total;
    auditActions.value = page.actions;
  } catch (err) {
    msg.value = parseApiError(err, '审计日志加载失败');
  } finally {
    loading.value = false;
  }
}

async function loadLogin() {
  loading.value = true;
  msg.value = '';
  try {
    const page = await fetchLoginLogs({
      success: successFilter.value,
      username: usernameFilter.value.trim(),
      days: days.value,
      limit: 100,
    });
    loginItems.value = page.items;
    loginTotal.value = page.total;
    riskyAccounts.value = page.risky_accounts;
  } catch (err) {
    msg.value = parseApiError(err, '登录日志加载失败');
  } finally {
    loading.value = false;
  }
}

function load() {
  return tab.value === 'audit' ? loadAudit() : loadLogin();
}

function setTab(value: 'audit' | 'login') {
  if (tab.value === value) return;
  tab.value = value;
  void load();
}

function setDays(value: number) {
  if (days.value === value) return;
  days.value = value;
  void load();
}

async function exportCsv() {
  try {
    await exportAdminCsv(tab.value === 'audit' ? 'audit' : 'login', days.value);
  } catch (err) {
    msg.value = parseApiError(err, '导出失败');
  }
}

function detailText(item: AuditLogItem) {
  const entries = Object.entries(item.detail || {});
  if (!entries.length) return '';
  return entries.map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(' · ');
}

onMounted(load);
</script>

<template>
  <div class="space-y-5">
    <AdminPageHeader kicker="Audit Trail" title="审计日志" subtitle="管理员操作留痕与登录安全记录">
      <template #actions>
        <div class="t-tabs" role="tablist" aria-label="统计天数">
          <button
            v-for="d in DAY_OPTIONS"
            :key="d"
            type="button"
            role="tab"
            class="t-tab"
            :class="{ 'is-active': days === d }"
            @click="setDays(d)"
          >
            {{ d }} 天
          </button>
        </div>
        <button type="button" class="t-btn t-btn--md t-btn--ghost" @click="exportCsv">导出 CSV</button>
        <button type="button" class="t-btn t-btn--md t-btn--ghost" :disabled="loading" @click="load">
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </template>
    </AdminPageHeader>

    <div class="flex flex-wrap items-center gap-2.5">
      <div class="t-tabs" role="tablist" aria-label="日志类型">
        <button type="button" role="tab" class="t-tab" :class="{ 'is-active': tab === 'audit' }" @click="setTab('audit')">
          操作审计（{{ auditTotal }}）
        </button>
        <button type="button" role="tab" class="t-tab" :class="{ 'is-active': tab === 'login' }" @click="setTab('login')">
          登录安全（{{ loginTotal }}）
        </button>
      </div>

      <template v-if="tab === 'audit'">
        <select v-model="actionFilter" class="t-input t-input--fit min-w-36" @change="loadAudit">
          <option value="">全部动作</option>
          <option v-for="a in auditActions" :key="a" :value="a">{{ ACTION_LABEL[a] || a }}</option>
        </select>
      </template>
      <template v-else>
        <select v-model="successFilter" class="t-input t-input--fit min-w-28" @change="loadLogin">
          <option value="">全部结果</option>
          <option value="true">成功</option>
          <option value="false">失败</option>
        </select>
        <input
          v-model="usernameFilter"
          type="search"
          placeholder="按用户名筛选"
          class="t-input t-input--fit w-44"
          @keyup.enter="loadLogin"
        />
      </template>
    </div>

    <p v-if="msg" class="rounded-xl border border-t-danger/25 bg-t-danger/10 px-4 py-2.5 text-sm text-t-danger">{{ msg }}</p>

    <!-- 高危账号提示 -->
    <div
      v-if="tab === 'login' && riskyAccounts.length"
      class="rounded-xl border border-t-danger/30 bg-t-danger/10 px-4 py-3 text-sm text-t-danger"
    >
      <p class="font-semibold">近 1 小时高危账号（连续登录失败 ≥ 5 次）：</p>
      <p class="mt-1">
        <span v-for="acc in riskyAccounts" :key="acc.username" class="t-badge t-badge--danger mr-2 font-mono">
          {{ acc.username }} × {{ acc.fails }}
        </span>
      </p>
    </div>

    <AdminSkeleton v-if="loading" :rows="6" />

    <!-- 操作审计 -->
    <template v-else-if="tab === 'audit'">
      <AdminEmptyState v-if="!auditItems.length" title="暂无审计记录" hint="管理员执行敏感操作后将在此留痕" />
      <transition v-else name="fade-scale" appear>
        <div class="space-y-2.5">
          <article
            v-for="item in auditItems"
            :key="item.id"
            class="t-card cursor-pointer p-4 transition hover:border-t-accent/30"
            @click="expandedId = expandedId === item.id ? '' : item.id"
          >
            <div class="flex flex-wrap items-center gap-2">
              <span class="adm-avatar">{{ (item.username || '?').slice(0, 1).toUpperCase() }}</span>
              <span class="text-[13px] text-t-1/90">{{ item.username || '系统' }}</span>
              <span class="t-badge t-badge--info">{{ ACTION_LABEL[item.action] || item.action }}</span>
              <span v-if="item.target_id" class="t-badge t-badge--neutral font-mono">
                {{ item.target_type }}:{{ item.target_id }}
              </span>
              <span class="ml-auto text-[11px] text-t-3" :title="item.created_at">{{ relativeTime(item.created_at) }}</span>
            </div>
            <p v-if="detailText(item)" class="mt-2 font-mono text-xs text-t-2" :class="expandedId === item.id ? 'break-all' : 'line-clamp-1'">
              {{ detailText(item) }}
            </p>
            <p v-if="expandedId === item.id" class="mt-2 border-t border-t-line/10 pt-2 text-xs text-t-3">
              IP {{ item.ip || '—' }} · <span class="font-mono">{{ item.created_at }}</span>
              <span v-if="item.user_agent" class="ml-2 opacity-70">{{ item.user_agent }}</span>
            </p>
          </article>
        </div>
      </transition>
    </template>

    <!-- 登录安全 -->
    <template v-else>
      <div class="flex flex-wrap items-center gap-2.5">
        <div class="adm-kpi px-4 py-3">
          <span class="text-xs text-t-2">记录条数</span>
          <span class="ml-3 font-mono text-xl font-semibold text-t-1">{{ loginTotal }}</span>
        </div>
        <div class="adm-kpi adm-kpi--danger px-4 py-3">
          <span class="text-xs text-t-2">本页失败</span>
          <span class="ml-3 font-mono text-xl font-semibold" :class="failCount ? 'text-t-danger' : 'text-t-1'">{{ failCount }}</span>
        </div>
      </div>
      <AdminEmptyState v-if="!loginItems.length" title="暂无登录记录" hint="用户登录成功或失败都会在此记录" />
      <transition v-else name="fade-scale" appear>
        <div class="t-table-wrap">
          <table class="t-table">
            <thead>
              <tr>
                <th>用户名</th>
                <th>结果</th>
                <th>原因</th>
                <th>IP</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in loginItems" :key="item.id">
                <td class="font-mono text-[13px]">{{ item.username }}</td>
                <td>
                  <span class="t-badge" :class="item.success ? 't-badge--ok' : 't-badge--danger'">
                    {{ item.success ? '成功' : '失败' }}
                  </span>
                </td>
                <td class="text-[12px] text-t-2">{{ item.reason || '—' }}</td>
                <td class="font-mono text-[12px] text-t-3">{{ item.ip || '—' }}</td>
                <td class="text-[12px] text-t-2" :title="item.created_at">{{ relativeTime(item.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </transition>
    </template>
  </div>
</template>

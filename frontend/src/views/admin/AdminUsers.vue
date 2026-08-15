<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import {
  batchSetUserActive,
  exportAdminCsv,
  fetchAdminUserDetail,
  fetchAdminUsers,
  resetAdminUserPassword,
  updateAdminUser,
  type UserAdminDetail,
  type UserAdminItem,
} from '../../api/admin';
import { parseApiError } from '../../api/errors';
import AdminEmptyState from '../../components/admin/AdminEmptyState.vue';
import AdminPageHeader from '../../components/admin/AdminPageHeader.vue';
import AdminSkeleton from '../../components/admin/AdminSkeleton.vue';
import { relativeTime } from '../../utils/relativeTime';
import { useCountUp } from '../../composables/useCountUp';

const users = ref<UserAdminItem[]>([]);
const roleFilter = ref('');
const search = ref('');
const msg = ref('');
const msgTone = ref<'ok' | 'err'>('ok');
const loading = ref(true);
const selectedIds = ref<Set<string>>(new Set());

/* 详情抽屉 */
const drawerUser = ref<UserAdminItem | null>(null);
const drawerDetail = ref<UserAdminDetail | null>(null);
const drawerLoading = ref(false);

/* 重置密码 */
const tempPassword = ref('');
const tempPasswordUser = ref('');

const ROLE_TABS = [
  { value: '', label: '全部' },
  { value: 'student', label: '学生' },
  { value: 'teacher', label: '教师' },
  { value: 'admin', label: '管理员' },
];

const ROLE_LABEL: Record<string, string> = { student: '学生', teacher: '教师', admin: '管理员' };
const ROLE_BADGE: Record<string, string> = {
  admin: 't-badge--warn',
  teacher: 't-badge--info',
  student: 't-badge--neutral',
};

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return users.value;
  return users.value.filter(
    (u) => u.username.toLowerCase().includes(q) || (u.display_name || '').toLowerCase().includes(q),
  );
});

const totalCount = computed(() => users.value.length);
const activeCount = computed(() => users.value.filter((u) => u.is_active).length);
const teacherCount = computed(() => users.value.filter((u) => u.role === 'teacher').length);
const totalAnim = useCountUp(totalCount);
const activeAnim = useCountUp(activeCount);
const teacherAnim = useCountUp(teacherCount);

const allChecked = computed(
  () => filtered.value.length > 0 && filtered.value.every((u) => selectedIds.value.has(u.id)),
);

async function load() {
  loading.value = true;
  try {
    users.value = await fetchAdminUsers(roleFilter.value);
    selectedIds.value = new Set();
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '加载失败');
  } finally {
    loading.value = false;
  }
}

function setRole(value: string) {
  if (roleFilter.value === value) return;
  roleFilter.value = value;
  void load();
}

function toggleSelect(id: string) {
  const next = new Set(selectedIds.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  selectedIds.value = next;
}

function toggleSelectAll() {
  selectedIds.value = allChecked.value ? new Set() : new Set(filtered.value.map((u) => u.id));
}

async function toggleActive(user: UserAdminItem) {
  try {
    const updated = await updateAdminUser(user.id, { is_active: !user.is_active });
    users.value = users.value.map((item) => (item.id === updated.id ? updated : item));
    msgTone.value = 'ok';
    msg.value = `已${updated.is_active ? '启用' : '停用'} ${updated.display_name}`;
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '操作失败');
  }
}

async function changeRole(user: UserAdminItem, role: string) {
  if (role === user.role) return;
  try {
    const updated = await updateAdminUser(user.id, { role });
    users.value = users.value.map((item) => (item.id === updated.id ? updated : item));
    msgTone.value = 'ok';
    msg.value = `已将 ${updated.display_name} 的角色改为「${ROLE_LABEL[role] || role}」`;
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '角色变更失败');
  }
}

async function batchActive(isActive: boolean) {
  if (!selectedIds.value.size) return;
  try {
    const res = await batchSetUserActive([...selectedIds.value], isActive);
    msgTone.value = 'ok';
    msg.value = `已批量${isActive ? '启用' : '停用'} ${res.updated} 个账号`;
    await load();
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '批量操作失败');
  }
}

async function resetPassword(user: UserAdminItem) {
  if (!window.confirm(`确认重置 ${user.display_name}（@${user.username}）的密码？旧密码将立即失效。`)) return;
  try {
    const res = await resetAdminUserPassword(user.id);
    tempPassword.value = res.temp_password;
    tempPasswordUser.value = `${user.display_name}（@${user.username}）`;
    msgTone.value = 'ok';
    msg.value = '密码已重置，请将临时密码告知用户';
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '重置失败');
  }
}

async function copyTempPassword() {
  try {
    await navigator.clipboard.writeText(tempPassword.value);
    msgTone.value = 'ok';
    msg.value = '临时密码已复制到剪贴板';
  } catch {
    /* 剪贴板不可用时用户可手动选中复制 */
  }
}

async function openDrawer(user: UserAdminItem) {
  drawerUser.value = user;
  drawerDetail.value = null;
  drawerLoading.value = true;
  try {
    drawerDetail.value = await fetchAdminUserDetail(user.id);
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '详情加载失败');
  } finally {
    drawerLoading.value = false;
  }
}

async function exportUsers() {
  try {
    await exportAdminCsv('users');
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '导出失败');
  }
}

const MODE_BADGE: Record<string, string> = {
  workflow: 't-badge--info',
  handoff: 't-badge--ok',
  supervisor: 't-badge--neutral',
  council: 't-badge--warn',
};

onMounted(load);
</script>

<template>
  <div class="space-y-5">
    <AdminPageHeader kicker="Accounts" title="用户管理" subtitle="账号启停、角色变更、密码重置与详情速览">
      <template #actions>
        <button type="button" class="t-btn t-btn--md t-btn--ghost" @click="exportUsers">导出 CSV</button>
        <button type="button" class="t-btn t-btn--md t-btn--ghost" :disabled="loading" @click="load">
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </template>
    </AdminPageHeader>

    <div class="grid gap-4 sm:grid-cols-3">
      <div class="adm-kpi p-4">
        <p class="text-xs text-t-2">账号总数</p>
        <p class="adm-kpi__value mt-2">{{ totalAnim }}</p>
      </div>
      <div class="adm-kpi adm-kpi--ok p-4">
        <p class="text-xs text-t-2">启用中</p>
        <p class="adm-kpi__value mt-2">{{ activeAnim }}</p>
      </div>
      <div class="adm-kpi adm-kpi--accent2 p-4">
        <p class="text-xs text-t-2">教师账号</p>
        <p class="adm-kpi__value mt-2">{{ teacherAnim }}</p>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-2.5">
      <div class="t-tabs" role="tablist" aria-label="按角色筛选">
        <button
          v-for="tab in ROLE_TABS"
          :key="tab.value"
          type="button"
          role="tab"
          class="t-tab"
          :class="{ 'is-active': roleFilter === tab.value }"
          :aria-selected="roleFilter === tab.value"
          @click="setRole(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>
      <div class="relative w-56">
        <svg
          viewBox="0 0 16 16"
          class="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-t-3"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
        >
          <circle cx="7" cy="7" r="4.5" />
          <path d="m13.5 13.5-3.2-3.2" />
        </svg>
        <input
          v-model="search"
          type="search"
          placeholder="搜索用户名 / 显示名"
          class="t-input t-input--icon"
        />
      </div>

      <!-- 批量操作 -->
      <div v-if="selectedIds.size" class="ml-auto flex items-center gap-2">
        <span class="text-xs text-t-2">已选 {{ selectedIds.size }} 项</span>
        <button type="button" class="t-btn t-btn--sm t-btn--soft" @click="batchActive(true)">批量启用</button>
        <button type="button" class="t-btn t-btn--sm t-btn--danger" @click="batchActive(false)">批量停用</button>
      </div>
    </div>

    <p
      v-if="msg"
      class="rounded-xl border px-4 py-2.5 text-sm"
      :class="msgTone === 'ok' ? 'border-t-accent/20 bg-t-accent/8 text-t-accent' : 'border-t-danger/25 bg-t-danger/10 text-t-danger'"
    >
      {{ msg }}
    </p>

    <!-- 临时密码展示 -->
    <div
      v-if="tempPassword"
      class="flex flex-wrap items-center gap-3 rounded-xl border border-t-warn/30 bg-t-warn/10 px-4 py-3 text-sm"
    >
      <span class="text-t-1/90">{{ tempPasswordUser }} 的临时密码：</span>
      <code class="rounded-lg bg-t-s1/60 px-3 py-1 font-mono text-base font-semibold tracking-wider text-t-1">{{ tempPassword }}</code>
      <button type="button" class="t-btn t-btn--sm t-btn--soft" @click="copyTempPassword">复制</button>
      <button type="button" class="t-btn t-btn--sm t-btn--ghost" @click="tempPassword = ''">关闭</button>
      <span class="w-full text-xs text-t-3">仅本次显示，关闭后无法找回；请尽快告知用户并提醒修改。</span>
    </div>

    <AdminSkeleton v-if="loading" :rows="6" />
    <AdminEmptyState v-else-if="!filtered.length" title="没有匹配的账号" hint="调整角色筛选或搜索关键词" />
    <transition v-else name="fade-scale" appear>
      <div class="t-table-wrap">
        <table class="t-table">
          <thead>
            <tr>
              <th class="w-8">
                <input type="checkbox" :checked="allChecked" aria-label="全选" @change="toggleSelectAll" />
              </th>
              <th>用户</th>
              <th>角色</th>
              <th>状态</th>
              <th>注册时间</th>
              <th class="text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in filtered" :key="user.id">
              <td>
                <input
                  type="checkbox"
                  :checked="selectedIds.has(user.id)"
                  :aria-label="`选择 ${user.username}`"
                  @change="toggleSelect(user.id)"
                />
              </td>
              <td>
                <button type="button" class="flex items-center gap-2.5 text-left" @click="openDrawer(user)">
                  <span class="adm-avatar">{{ (user.display_name || user.username || '?').slice(0, 1).toUpperCase() }}</span>
                  <div class="min-w-0">
                    <p class="truncate text-[13px] text-t-1/90 underline-offset-2 hover:underline">{{ user.display_name || '—' }}</p>
                    <p class="truncate font-mono text-[11px] text-t-3">@{{ user.username }}</p>
                  </div>
                </button>
              </td>
              <td>
                <select
                  class="t-input t-input--fit !py-1 text-xs"
                  :value="user.role"
                  :aria-label="`${user.username} 的角色`"
                  @change="changeRole(user, ($event.target as HTMLSelectElement).value)"
                >
                  <option value="student">学生</option>
                  <option value="teacher">教师</option>
                  <option value="admin">管理员</option>
                </select>
              </td>
              <td>
                <span class="inline-flex items-center gap-1.5 text-[13px]" :class="user.is_active ? 'text-t-ok' : 'text-t-danger'">
                  <span class="h-1.5 w-1.5 rounded-full bg-current" />
                  {{ user.is_active ? '启用' : '停用' }}
                </span>
              </td>
              <td class="text-[12px] text-t-2">{{ relativeTime(user.created_at) }}</td>
              <td class="text-right">
                <div class="inline-flex gap-1.5">
                  <button type="button" class="t-btn t-btn--sm t-btn--ghost" @click="resetPassword(user)">重置密码</button>
                  <button
                    type="button"
                    class="t-btn t-btn--sm"
                    :class="user.is_active ? 't-btn--danger' : 't-btn--soft'"
                    @click="toggleActive(user)"
                  >
                    {{ user.is_active ? '停用' : '启用' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </transition>

    <!-- 用户详情抽屉 -->
    <teleport to="body">
      <transition name="fade-scale">
        <div v-if="drawerUser" class="fixed inset-0 z-50 flex justify-end bg-black/40" @click.self="drawerUser = null">
          <aside class="h-full w-full max-w-md overflow-y-auto border-l border-t-line/15 bg-t-s0 p-5 shadow-2xl">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <span class="adm-avatar">{{ (drawerUser.display_name || '?').slice(0, 1).toUpperCase() }}</span>
                <div>
                  <p class="text-sm font-semibold text-t-1">{{ drawerUser.display_name }}</p>
                  <p class="font-mono text-xs text-t-3">@{{ drawerUser.username }}</p>
                </div>
                <span class="t-badge" :class="ROLE_BADGE[drawerUser.role] || 't-badge--neutral'">
                  {{ ROLE_LABEL[drawerUser.role] || drawerUser.role }}
                </span>
              </div>
              <button type="button" class="t-btn t-btn--sm t-btn--ghost" @click="drawerUser = null">关闭</button>
            </div>

            <AdminSkeleton v-if="drawerLoading" :rows="5" class="mt-4" />
            <template v-else-if="drawerDetail">
              <div class="mt-4 grid grid-cols-2 gap-3">
                <div class="adm-kpi p-3">
                  <p class="text-[11px] text-t-2">7 日调用</p>
                  <p class="mt-1 font-mono text-lg font-semibold text-t-1">{{ drawerDetail.usage_7d.calls }}</p>
                </div>
                <div class="adm-kpi p-3">
                  <p class="text-[11px] text-t-2">7 日 Token</p>
                  <p class="mt-1 font-mono text-lg font-semibold text-t-1">{{ drawerDetail.usage_7d.tokens }}</p>
                </div>
                <div class="adm-kpi adm-kpi--ok p-3">
                  <p class="text-[11px] text-t-2">点亮行星</p>
                  <p class="mt-1 font-mono text-lg font-semibold text-t-1">
                    {{ drawerDetail.mastery.lit }} / {{ drawerDetail.mastery.total }}
                  </p>
                </div>
                <div class="adm-kpi adm-kpi--accent2 p-3">
                  <p class="text-[11px] text-t-2">连续学习</p>
                  <p class="mt-1 font-mono text-lg font-semibold text-t-1">{{ drawerDetail.user.streak_days }} 天</p>
                </div>
              </div>

              <section class="mt-5">
                <h4 class="text-xs font-semibold text-t-3">最近 Agent 运行</h4>
                <ul v-if="drawerDetail.recent_agent_runs.length" class="mt-2 space-y-2">
                  <li
                    v-for="run in drawerDetail.recent_agent_runs"
                    :key="run.id"
                    class="rounded-xl border border-t-line/10 bg-t-s1/30 p-2.5"
                  >
                    <div class="flex items-center gap-2">
                      <span class="t-badge" :class="MODE_BADGE[run.mode] || 't-badge--neutral'">{{ run.mode }}</span>
                      <span class="truncate text-xs text-t-1/90">{{ run.topic || run.scene }}</span>
                      <span class="ml-auto text-[10px] text-t-3">{{ relativeTime(run.created_at) }}</span>
                    </div>
                  </li>
                </ul>
                <p v-else class="mt-2 text-xs text-t-3">暂无运行记录</p>
              </section>

              <section class="mt-5">
                <h4 class="text-xs font-semibold text-t-3">最近登录</h4>
                <ul v-if="drawerDetail.recent_logins.length" class="mt-2 space-y-1.5">
                  <li
                    v-for="log in drawerDetail.recent_logins"
                    :key="log.id"
                    class="flex items-center gap-2 text-xs"
                  >
                    <span class="t-badge" :class="log.success ? 't-badge--ok' : 't-badge--danger'">
                      {{ log.success ? '成功' : '失败' }}
                    </span>
                    <span class="font-mono text-t-3">{{ log.ip || '—' }}</span>
                    <span class="ml-auto text-t-3" :title="log.created_at">{{ relativeTime(log.created_at) }}</span>
                  </li>
                </ul>
                <p v-else class="mt-2 text-xs text-t-3">暂无登录记录</p>
              </section>
            </template>
          </aside>
        </div>
      </transition>
    </teleport>
  </div>
</template>

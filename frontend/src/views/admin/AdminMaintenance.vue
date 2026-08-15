<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { fetchMaintenance, sendAdminAnnouncement, updateMaintenance } from '../../api/admin';
import { parseApiError } from '../../api/errors';
import AdminPageHeader from '../../components/admin/AdminPageHeader.vue';

const enabled = ref(false);
const savedEnabled = ref(false);
const message = ref('系统维护中，请稍后再试');
const msg = ref('');
const msgTone = ref<'ok' | 'err'>('ok');
const saving = ref(false);
const loading = ref(true);
const confirmOpen = ref(false);

const dirty = computed(() => enabled.value !== savedEnabled.value);

async function load() {
  loading.value = true;
  try {
    const data = await fetchMaintenance();
    enabled.value = data.enabled;
    savedEnabled.value = data.enabled;
    message.value = data.message;
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '加载失败');
  } finally {
    loading.value = false;
  }
}

function onSaveClick() {
  // 从关闭切到开启会拦截学生/教师写操作，需要二次确认
  if (enabled.value && !savedEnabled.value) {
    confirmOpen.value = true;
    return;
  }
  void save();
}

async function save() {
  confirmOpen.value = false;
  saving.value = true;
  msg.value = '';
  try {
    const data = await updateMaintenance(enabled.value, message.value);
    enabled.value = data.enabled;
    savedEnabled.value = data.enabled;
    message.value = data.message;
    msgTone.value = 'ok';
    msg.value = '维护设置已保存';
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '保存失败');
  } finally {
    saving.value = false;
  }
}

/* ---- 系统公告群发 ---- */
const annTitle = ref('');
const annBody = ref('');
const annRole = ref('all');
const annSending = ref(false);
const annMsg = ref('');
const annTone = ref<'ok' | 'err'>('ok');

const ANN_ROLES = [
  { value: 'all', label: '全体用户' },
  { value: 'student', label: '仅学生' },
  { value: 'teacher', label: '仅教师' },
];

async function sendAnnouncement() {
  if (!annTitle.value.trim() || !annBody.value.trim()) return;
  annSending.value = true;
  annMsg.value = '';
  try {
    const res = await sendAdminAnnouncement(annTitle.value.trim(), annBody.value.trim(), annRole.value);
    annTone.value = 'ok';
    annMsg.value = `公告已发送给 ${res.sent} 位用户`;
    annTitle.value = '';
    annBody.value = '';
  } catch (err) {
    annTone.value = 'err';
    annMsg.value = parseApiError(err, '发送失败');
  } finally {
    annSending.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="space-y-5">
    <AdminPageHeader kicker="Operations" title="维护模式" subtitle="开启后，非管理员用户的写操作将返回 503">
      <template #actions>
        <span class="adm-pill" :class="loading ? 'adm-pill--neutral' : savedEnabled ? 'adm-pill--warn' : 'adm-pill--ok'">
          <span class="adm-pill__dot" aria-hidden="true" />
          {{ loading ? '加载中…' : savedEnabled ? '维护中' : '运行正常' }}
        </span>
      </template>
    </AdminPageHeader>

    <div class="grid gap-4 lg:grid-cols-2">
      <!-- 大开关卡 -->
      <section class="t-card space-y-5 p-5">
        <label class="flex cursor-pointer items-center justify-between gap-3">
          <span>
            <span class="block text-sm font-medium text-t-1">启用维护模式</span>
            <span class="mt-0.5 block text-xs text-t-3">学生 / 教师端的写操作会被暂时拦截</span>
          </span>
          <span
            class="relative inline-flex h-7 w-13 shrink-0 items-center rounded-full transition"
            :class="enabled ? 'bg-t-warn/80' : 'bg-t-s3'"
          >
            <input v-model="enabled" type="checkbox" class="peer sr-only" />
            <span
              class="absolute left-0.5 h-6 w-6 rounded-full bg-white shadow transition-transform"
              :class="enabled ? 'translate-x-6' : 'translate-x-0'"
            />
          </span>
        </label>

        <div>
          <p class="mb-1.5 text-xs text-t-3">维护公告（用户可见）</p>
          <textarea
            v-model="message"
            rows="4"
            class="t-input resize-y"
            placeholder="维护公告"
          />
        </div>

        <div class="flex items-center gap-3">
          <button
            type="button"
            class="t-btn t-btn--md t-btn--primary"
            :disabled="saving || loading"
            @click="onSaveClick"
          >
            {{ saving ? '保存中…' : '保存设置' }}
          </button>
          <span v-if="dirty" class="text-xs text-t-warn">有未保存的更改</span>
        </div>

        <p
          v-if="msg"
          class="rounded-xl border px-4 py-2.5 text-sm"
          :class="msgTone === 'ok' ? 'border-t-accent/20 bg-t-accent/8 text-t-accent' : 'border-t-danger/25 bg-t-danger/10 text-t-danger'"
        >
          {{ msg }}
        </p>
      </section>

      <!-- 学生端实时预览 -->
      <section class="t-card p-5">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-t-1">用户将看到的提示</h3>
          <span class="t-kicker">Preview</span>
        </div>
        <div class="mt-4 rounded-2xl border border-t-line/12 bg-t-bg/60 p-6">
          <div
            class="mx-auto flex max-w-sm flex-col items-center gap-3 rounded-2xl border p-6 text-center"
            :class="enabled ? 'border-t-warn/35 bg-t-warn/8' : 'border-t-line/15 bg-t-s1/40 opacity-60'"
          >
            <svg viewBox="0 0 16 16" class="h-8 w-8" :class="enabled ? 'text-t-warn' : 'text-t-3'" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M2.5 5h11M2.5 11h11" />
              <circle cx="6" cy="5" r="1.7" />
              <circle cx="10" cy="11" r="1.7" />
            </svg>
            <p class="text-sm font-semibold" :class="enabled ? 'text-t-warn' : 'text-t-2'">系统维护中</p>
            <p class="text-xs leading-relaxed" :class="enabled ? 'text-t-1/80' : 'text-t-3'">
              {{ message || '系统维护中，请稍后再试' }}
            </p>
          </div>
          <p class="mt-3 text-center text-[11px] text-t-3">
            {{ enabled ? '保存后学生 / 教师的写操作将收到上述提示' : '当前为关闭状态，预览仅供参考' }}
          </p>
        </div>
      </section>
    </div>

    <!-- 系统公告群发 -->
    <section class="t-card p-5">
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-sm font-semibold text-t-1">发布系统公告</h3>
          <p class="mt-0.5 text-xs text-t-3">通过站内通知按角色群发，用户在通知中心可见</p>
        </div>
        <span class="t-kicker">Announcement</span>
      </div>
      <div class="mt-4 grid gap-3 lg:grid-cols-[1fr_2fr_auto_auto]">
        <input v-model="annTitle" type="text" maxlength="120" placeholder="公告标题" class="t-input" />
        <input v-model="annBody" type="text" maxlength="500" placeholder="公告内容" class="t-input" />
        <select v-model="annRole" class="t-input t-input--fit min-w-28">
          <option v-for="r in ANN_ROLES" :key="r.value" :value="r.value">{{ r.label }}</option>
        </select>
        <button
          type="button"
          class="t-btn t-btn--md t-btn--primary"
          :disabled="annSending || !annTitle.trim() || !annBody.trim()"
          @click="sendAnnouncement"
        >
          {{ annSending ? '发送中…' : '发送公告' }}
        </button>
      </div>
      <p
        v-if="annMsg"
        class="mt-3 rounded-xl border px-4 py-2.5 text-sm"
        :class="annTone === 'ok' ? 'border-t-accent/20 bg-t-accent/8 text-t-accent' : 'border-t-danger/25 bg-t-danger/10 text-t-danger'"
      >
        {{ annMsg }}
      </p>
    </section>

    <!-- 开启维护二次确认 -->
    <teleport to="body">
      <transition name="fade-scale">
        <div v-if="confirmOpen" class="t-cmdk-overlay !items-center !p-4" @click.self="confirmOpen = false">
          <div class="t-cmdk max-w-md p-6">
            <p class="t-kicker !text-t-warn">Confirm</p>
            <h3 class="mt-1 text-lg font-semibold text-t-1">确认开启维护模式？</h3>
            <p class="mt-2 text-sm text-t-2">
              开启后，所有学生和教师的写操作（提交作业、生成资源等）会立即被拦截并返回 503，直到你再次关闭维护模式。
            </p>
            <div class="mt-5 flex justify-end gap-2">
              <button type="button" class="t-btn t-btn--md t-btn--ghost" @click="confirmOpen = false">
                取消
              </button>
              <button type="button" class="t-btn t-btn--md t-btn--primary" :disabled="saving" @click="save">
                确认开启
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>
  </div>
</template>

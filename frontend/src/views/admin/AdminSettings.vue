<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import {
  fetchAdminProviders,
  fetchAdminSettings,
  testAdminProvider,
  updateAdminProvider,
  updateAdminSettings,
  type ProviderItem,
  type ProviderTestResult,
  type SettingItem,
} from '../../api/admin';
import { parseApiError } from '../../api/errors';
import AdminPageHeader from '../../components/admin/AdminPageHeader.vue';
import AdminSkeleton from '../../components/admin/AdminSkeleton.vue';

const settings = ref<SettingItem[]>([]);
const draft = ref<Record<string, string>>({});
const loading = ref(true);
const saving = ref(false);
const msg = ref('');
const msgTone = ref<'ok' | 'err'>('ok');

const GROUP_META: Record<string, { label: string; description: string }> = {
  quota: { label: '配额管理', description: '控制全站 LLM 成本与告警阈值' },
  shield: { label: '思想防火墙', description: 'AI 输出内容安全审核策略' },
  features: { label: '功能开关', description: '控制学生端各功能入口开放状态' },
};

const grouped = computed(() => {
  const map = new Map<string, SettingItem[]>();
  for (const item of settings.value) {
    const list = map.get(item.group) || [];
    list.push(item);
    map.set(item.group, list);
  }
  return [...map.entries()].map(([group, items]) => ({
    group,
    meta: GROUP_META[group] || { label: group, description: '' },
    items,
  }));
});

const dirty = computed(() => settings.value.some((s) => (draft.value[s.key] ?? s.value) !== s.value));

function isTrue(value: string) {
  return ['1', 'true', 'yes', 'on'].includes((value || '').trim().toLowerCase());
}

function toggleBool(key: string) {
  const current = draft.value[key] ?? settings.value.find((s) => s.key === key)?.value ?? '';
  draft.value = { ...draft.value, [key]: isTrue(current) ? 'false' : 'true' };
}

function currentValue(item: SettingItem) {
  return draft.value[item.key] ?? item.value;
}

async function load() {
  loading.value = true;
  msg.value = '';
  try {
    settings.value = await fetchAdminSettings();
    draft.value = {};
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '配置加载失败');
  } finally {
    loading.value = false;
  }
}

async function save() {
  const changed: Record<string, string> = {};
  for (const item of settings.value) {
    const value = draft.value[item.key];
    if (value !== undefined && value !== item.value) changed[item.key] = value;
  }
  if (!Object.keys(changed).length) return;
  saving.value = true;
  msg.value = '';
  try {
    settings.value = await updateAdminSettings(changed);
    draft.value = {};
    msgTone.value = 'ok';
    msg.value = '配置已保存并即时生效';
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '保存失败');
  } finally {
    saving.value = false;
  }
}

/* ---- API 密钥管理 ---- */
const providers = ref<ProviderItem[]>([]);
const providersLoading = ref(false);
const testResults = ref<Record<string, ProviderTestResult & { pending?: boolean }>>({});

const keyModal = ref<{ provider: ProviderItem; apiKey: string; model: string } | null>(null);
const keySaving = ref(false);
const keyModalMsg = ref('');
const keyModalTone = ref<'ok' | 'err'>('ok');

const SOURCE_LABEL: Record<string, string> = {
  env: '.env',
  override: '在线覆盖',
  none: '未配置',
};

async function loadProviders() {
  providersLoading.value = true;
  try {
    providers.value = await fetchAdminProviders();
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, 'API 平台列表加载失败');
  } finally {
    providersLoading.value = false;
  }
}

async function testProvider(providerId: string) {
  testResults.value = { ...testResults.value, [providerId]: { ok: false, detail: '测试中…', pending: true } };
  try {
    const result = await testAdminProvider(providerId);
    testResults.value = { ...testResults.value, [providerId]: result };
  } catch (err) {
    testResults.value = {
      ...testResults.value,
      [providerId]: { ok: false, detail: parseApiError(err, '测试请求失败') },
    };
  }
}

function openKeyModal(provider: ProviderItem) {
  keyModal.value = { provider, apiKey: '', model: '' };
  keyModalMsg.value = '';
}

async function saveKey() {
  const modal = keyModal.value;
  if (!modal) return;
  const apiKey = modal.apiKey.trim();
  const model = modal.model.trim();
  if (!apiKey && !model) {
    keyModalTone.value = 'err';
    keyModalMsg.value = '请输入新的 API Key 或模型';
    return;
  }
  keySaving.value = true;
  keyModalMsg.value = '';
  try {
    await updateAdminProvider(modal.provider.id, { api_key: apiKey, model });
    keyModalTone.value = 'ok';
    keyModalMsg.value = '已保存，正在测试连通性…';
    const result = await testAdminProvider(modal.provider.id);
    testResults.value = { ...testResults.value, [modal.provider.id]: result };
    keyModalTone.value = result.ok ? 'ok' : 'err';
    keyModalMsg.value = result.ok ? `保存成功：${result.detail}` : `已保存，但连通性测试失败：${result.detail}`;
    await loadProviders();
    if (result.ok) {
      setTimeout(() => {
        keyModal.value = null;
      }, 1200);
    }
  } catch (err) {
    keyModalTone.value = 'err';
    keyModalMsg.value = parseApiError(err, '保存失败');
  } finally {
    keySaving.value = false;
  }
}

onMounted(() => {
  void load();
  void loadProviders();
});
</script>

<template>
  <div class="space-y-5">
    <AdminPageHeader kicker="Runtime Config" title="系统配置" subtitle="配额 / 思想防火墙 / 功能开关 / API 密钥，保存即生效">
      <template #actions>
        <button type="button" class="t-btn t-btn--md t-btn--soft" :disabled="!dirty || saving" @click="save">
          {{ saving ? '保存中…' : dirty ? '保存修改' : '暂无修改' }}
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

    <AdminSkeleton v-if="loading" :rows="6" />
    <template v-else>
      <section v-for="section in grouped" :key="section.group" class="t-card p-5">
        <div>
          <h3 class="text-sm font-semibold text-t-1">{{ section.meta.label }}</h3>
          <p class="mt-0.5 text-xs text-t-3">{{ section.meta.description }}</p>
        </div>
        <div class="mt-4 space-y-4">
          <div
            v-for="item in section.items"
            :key="item.key"
            class="flex flex-wrap items-start justify-between gap-3 border-b border-t-line/8 pb-4 last:border-0 last:pb-0"
          >
            <div class="min-w-0 max-w-md">
              <p class="text-[13px] text-t-1/90">{{ item.label }}</p>
              <p class="mt-0.5 text-xs text-t-3">{{ item.description }}</p>
            </div>

            <!-- bool 开关 -->
            <button
              v-if="item.type === 'bool'"
              type="button"
              class="relative h-6 w-11 shrink-0 rounded-full transition"
              :class="isTrue(currentValue(item)) ? 'bg-t-accent' : 'bg-t-line/30'"
              role="switch"
              :aria-checked="isTrue(currentValue(item))"
              :aria-label="item.label"
              @click="toggleBool(item.key)"
            >
              <span
                class="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all"
                :class="isTrue(currentValue(item)) ? 'left-[22px]' : 'left-0.5'"
              />
            </button>

            <!-- int 输入 -->
            <input
              v-else-if="item.type === 'int'"
              :value="currentValue(item)"
              type="number"
              min="0"
              class="t-input t-input--fit w-40 font-mono"
              @input="draft = { ...draft, [item.key]: ($event.target as HTMLInputElement).value }"
            />

            <!-- text 多行 -->
            <textarea
              v-else
              :value="currentValue(item)"
              rows="3"
              class="t-input w-full max-w-sm font-mono text-xs"
              placeholder="逗号或换行分隔"
              @input="draft = { ...draft, [item.key]: ($event.target as HTMLTextAreaElement).value }"
            />
          </div>
        </div>
      </section>
    </template>

    <!-- API 密钥管理 -->
    <section class="t-card p-5">
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-sm font-semibold text-t-1">API 密钥管理</h3>
          <p class="mt-0.5 text-xs text-t-3">
            在线更换各平台 API Key（覆盖 .env 配置，重启不丢失）；Key 永远掩码显示，变更写入审计日志
          </p>
        </div>
        <button type="button" class="t-btn t-btn--sm t-btn--ghost" :disabled="providersLoading" @click="loadProviders">
          {{ providersLoading ? '刷新中…' : '刷新' }}
        </button>
      </div>

      <div class="mt-4 space-y-3">
        <div
          v-for="p in providers"
          :key="p.id"
          class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-t-line/60 bg-t-s2/30 px-4 py-3"
        >
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <p class="text-sm font-semibold text-t-1">{{ p.label }}</p>
              <span
                class="rounded-full px-2 py-0.5 text-[10px] font-medium"
                :class="{
                  'bg-t-accent/15 text-t-accent': p.key_source === 'override',
                  'bg-t-ok/15 text-t-ok': p.key_source === 'env',
                  'bg-t-s2 text-t-3': p.key_source === 'none',
                }"
              >
                {{ SOURCE_LABEL[p.key_source] }}
              </span>
            </div>
            <p class="mt-1 text-xs text-t-3">{{ p.description }}</p>
            <p class="mt-1 font-mono text-xs text-t-2">
              Key：{{ p.key_masked || '（未配置）' }}
              <template v-if="p.model"> · 模型：{{ p.model }}</template>
            </p>
            <p
              v-if="testResults[p.id]"
              class="mt-1 text-xs"
              :class="testResults[p.id].pending ? 'text-t-3' : testResults[p.id].ok ? 'text-t-ok' : 'text-t-danger'"
            >
              {{ testResults[p.id].detail }}
            </p>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <button
              type="button"
              class="t-btn t-btn--sm t-btn--ghost"
              :disabled="!p.configured || testResults[p.id]?.pending"
              @click="testProvider(p.id)"
            >
              测试连通
            </button>
            <button v-if="p.editable" type="button" class="t-btn t-btn--sm t-btn--soft" @click="openKeyModal(p)">
              更换密钥
            </button>
            <span v-else class="text-[11px] text-t-3">仅 .env 配置</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 更换密钥弹窗 -->
    <div
      v-if="keyModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      @click.self="keyModal = null"
    >
      <div class="t-card w-full max-w-md p-5">
        <h3 class="text-sm font-semibold text-t-1">更换 {{ keyModal.provider.label }} 密钥</h3>
        <p class="mt-1 text-xs text-t-3">
          当前：{{ keyModal.provider.key_masked || '未配置' }}（{{ SOURCE_LABEL[keyModal.provider.key_source] }}）。
          保存后立即生效并自动测试连通性。
        </p>
        <div class="mt-4 space-y-3">
          <div>
            <label class="text-xs text-t-2" for="provider-new-key">新 API Key</label>
            <input
              id="provider-new-key"
              v-model="keyModal.apiKey"
              type="password"
              autocomplete="off"
              class="t-input mt-1 w-full font-mono text-xs"
              placeholder="sk-…（留空表示只改模型）"
            />
          </div>
          <div v-if="keyModal.provider.id === 'deepseek' || keyModal.provider.id === 'doubao'">
            <label class="text-xs text-t-2" for="provider-new-model">模型 / 接入点（可选）</label>
            <input
              id="provider-new-model"
              v-model="keyModal.model"
              type="text"
              class="t-input mt-1 w-full font-mono text-xs"
              :placeholder="keyModal.provider.model || (keyModal.provider.id === 'deepseek' ? 'deepseek-chat' : 'ep-…')"
            />
          </div>
        </div>
        <p
          v-if="keyModalMsg"
          class="mt-3 rounded-lg border px-3 py-2 text-xs"
          :class="keyModalTone === 'ok' ? 'border-t-ok/25 bg-t-ok/10 text-t-ok' : 'border-t-danger/25 bg-t-danger/10 text-t-danger'"
        >
          {{ keyModalMsg }}
        </p>
        <div class="mt-4 flex justify-end gap-2">
          <button type="button" class="t-btn t-btn--sm t-btn--ghost" :disabled="keySaving" @click="keyModal = null">
            取消
          </button>
          <button type="button" class="t-btn t-btn--sm t-btn--soft" :disabled="keySaving" @click="saveKey">
            {{ keySaving ? '保存中…' : '保存并测试' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

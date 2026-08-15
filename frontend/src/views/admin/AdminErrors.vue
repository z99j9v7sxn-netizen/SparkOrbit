<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { fetchAdminErrors, type ApiErrorItem } from '../../api/admin';
import { parseApiError } from '../../api/errors';
import AdminEmptyState from '../../components/admin/AdminEmptyState.vue';
import AdminPageHeader from '../../components/admin/AdminPageHeader.vue';
import AdminSkeleton from '../../components/admin/AdminSkeleton.vue';
import { relativeTime } from '../../utils/relativeTime';
import { useCountUp } from '../../composables/useCountUp';

const errors = ref<ApiErrorItem[]>([]);
const msg = ref('');
const loading = ref(true);
const endpointFilter = ref('');
const expandedId = ref('');

const endpoints = computed(() => [...new Set(errors.value.map((e) => e.endpoint))].slice(0, 20));
const filtered = computed(() =>
  endpointFilter.value ? errors.value.filter((e) => e.endpoint === endpointFilter.value) : errors.value,
);
const totalCount = computed(() => errors.value.length);
const totalAnim = useCountUp(totalCount);

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? '' : id;
}

async function load() {
  loading.value = true;
  msg.value = '';
  try {
    errors.value = await fetchAdminErrors(80);
  } catch (err) {
    msg.value = parseApiError(err, '加载失败');
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="space-y-5">
    <AdminPageHeader kicker="Incidents" title="接口异常" subtitle="LLM 与 API 调用失败记录（最近 80 条）">
      <template #actions>
        <select v-model="endpointFilter" class="t-input t-input--fit min-w-36">
          <option value="">全部端点</option>
          <option v-for="ep in endpoints" :key="ep" :value="ep">{{ ep }}</option>
        </select>
        <button type="button" class="t-btn t-btn--md t-btn--ghost" :disabled="loading" @click="load">
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </template>
    </AdminPageHeader>

    <div class="flex flex-wrap items-center gap-2.5">
      <div class="adm-kpi adm-kpi--danger px-4 py-3">
        <span class="text-xs text-t-2">异常条数</span>
        <span class="ml-3 font-mono text-xl font-semibold" :class="totalCount ? 'text-t-danger' : 'text-t-1'">{{ totalAnim }}</span>
      </div>
      <span v-if="endpointFilter" class="t-badge t-badge--danger">
        {{ endpointFilter }}
        <button type="button" class="ml-1 opacity-70 hover:opacity-100" @click="endpointFilter = ''">×</button>
      </span>
    </div>

    <p v-if="msg" class="rounded-xl border border-t-danger/25 bg-t-danger/10 px-4 py-2.5 text-sm text-t-danger">{{ msg }}</p>

    <AdminSkeleton v-if="loading" :rows="5" variant="cards" />
    <AdminEmptyState v-else-if="!filtered.length" icon="✓" title="暂无异常记录" hint="系统调用一切正常" />
    <transition v-else name="fade-scale" appear>
      <div class="space-y-2.5">
        <article
          v-for="item in filtered"
          :key="item.id"
          class="t-card cursor-pointer border-t-danger/15 p-4 transition hover:border-t-danger/35"
          @click="toggleExpand(item.id)"
        >
          <div class="flex flex-wrap items-center gap-2">
            <span class="t-badge t-badge--danger font-mono">{{ item.endpoint }}</span>
            <span v-if="item.model" class="t-badge t-badge--neutral font-mono">{{ item.model }}</span>
            <span class="ml-auto flex items-center gap-2 text-[11px] text-t-3">
              <span :title="item.created_at">{{ relativeTime(item.created_at) }}</span>
              <svg
                viewBox="0 0 16 16"
                class="h-3 w-3 transition-transform duration-200"
                :class="expandedId === item.id ? 'rotate-180' : ''"
                fill="none"
                stroke="currentColor"
                stroke-width="1.6"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="m4 6 4 4 4-4" />
              </svg>
            </span>
          </div>
          <p
            class="mt-2 text-sm text-t-1/90"
            :class="expandedId === item.id ? 'whitespace-pre-wrap break-all' : 'line-clamp-2'"
          >
            {{ item.error_message }}
          </p>
          <p v-if="expandedId === item.id" class="mt-2.5 border-t border-t-line/10 pt-2 text-xs text-t-3">
            用户 {{ item.user_id || '系统' }} · <span class="font-mono">{{ item.created_at }}</span>
          </p>
        </article>
      </div>
    </transition>
  </div>
</template>

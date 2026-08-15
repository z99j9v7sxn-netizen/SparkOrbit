<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { LzBadge, LzButton, LzEmptyState } from '../../learning/ui';
import { parseApiError } from '../../../api/errors';
import {
  deleteInterviewApplication,
  fetchInterviewApplications,
  patchInterviewApplication,
  type InterviewApplication,
} from '../../../api/interview';

const COLUMNS = [
  { key: 'wishlist', label: '想投' },
  { key: 'applied', label: '已投' },
  { key: 'oa', label: '笔试' },
  { key: 'interview', label: '面试' },
  { key: 'offer', label: 'Offer' },
  { key: 'rejected', label: '未通过' },
];

const props = defineProps<{ refreshKey?: number }>();

const items = ref<InterviewApplication[]>([]);
const error = ref('');
const busyId = ref('');

const grouped = computed(() =>
  COLUMNS.map((col) => ({ ...col, items: items.value.filter((i) => i.status === col.key) })),
);

async function load() {
  try {
    items.value = await fetchInterviewApplications();
  } catch (err) {
    error.value = parseApiError(err, '投递看板加载失败');
  }
}

onMounted(load);
watch(() => props.refreshKey, load);

async function setStatus(row: InterviewApplication, status: string) {
  busyId.value = row.id;
  error.value = '';
  try {
    const updated = await patchInterviewApplication(row.id, { status });
    items.value = items.value.map((i) => (i.id === row.id ? updated : i));
  } catch (err) {
    error.value = parseApiError(err, '更新失败');
  } finally {
    busyId.value = '';
  }
}

async function saveNotes(row: InterviewApplication, notes: string) {
  try {
    const updated = await patchInterviewApplication(row.id, { notes });
    items.value = items.value.map((i) => (i.id === row.id ? updated : i));
  } catch (err) {
    error.value = parseApiError(err, '备注保存失败');
  }
}

async function remove(row: InterviewApplication) {
  busyId.value = row.id;
  try {
    await deleteInterviewApplication(row.id);
    items.value = items.value.filter((i) => i.id !== row.id);
  } catch (err) {
    error.value = parseApiError(err, '删除失败');
  } finally {
    busyId.value = '';
  }
}
</script>

<template>
  <div class="space-y-3">
    <p class="text-xs text-slate-500">记录意向与进度，不替代各司招聘系统。</p>
    <p v-if="error" class="text-xs text-rose-300">{{ error }}</p>
    <div class="grid gap-2 md:grid-cols-3 xl:grid-cols-6">
      <section v-for="col in grouped" :key="col.key" class="lz-card min-h-[140px] space-y-2 p-3">
        <div class="flex items-center justify-between">
          <h4 class="text-xs text-amber-100">{{ col.label }}</h4>
          <LzBadge tone="neutral">{{ col.items.length }}</LzBadge>
        </div>
        <article
          v-for="row in col.items"
          :key="row.id"
          class="rounded-xl border border-white/10 p-2 space-y-1.5"
        >
          <p class="truncate text-sm text-slate-100">{{ row.company }}</p>
          <p v-if="row.role" class="truncate text-[11px] text-slate-500">{{ row.role }}</p>
          <a
            v-if="row.portal_url"
            class="block truncate text-[11px] text-amber-200/80"
            :href="row.portal_url"
            target="_blank"
            rel="noopener noreferrer"
          >
            打开官网
          </a>
          <input
            class="lz-input h-7 w-full text-[11px]"
            :value="row.notes"
            placeholder="备注"
            @blur="saveNotes(row, ($event.target as HTMLInputElement).value)"
          />
          <div class="flex flex-wrap gap-1">
            <select
              class="lz-input h-7 flex-1 text-[11px]"
              :value="row.status"
              :disabled="busyId === row.id"
              @change="setStatus(row, ($event.target as HTMLSelectElement).value)"
            >
              <option v-for="opt in COLUMNS" :key="opt.key" :value="opt.key">{{ opt.label }}</option>
            </select>
            <LzButton size="sm" variant="danger" :disabled="busyId === row.id" @click="remove(row)">删</LzButton>
          </div>
        </article>
        <p v-if="!col.items.length" class="text-center text-[11px] text-slate-600">空</p>
      </section>
    </div>
    <LzEmptyState v-if="!items.length" title="还没有投递记录" desc="从校招门户点「记入看板」开始" />
  </div>
</template>

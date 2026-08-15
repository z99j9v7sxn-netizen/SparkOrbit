<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { fetchTeacherPatrol, type PatrolStudent } from '../../api/study';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';
import { useTeacherClassStore } from '../../stores/teacherClass';

const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);

const rows = ref<PatrolStudent[]>([]);
const error = ref('');
const loading = ref(false);
const filter = ref<'all' | 'online' | 'offline' | 'help'>('all');
const preview = ref<PatrolStudent | null>(null);
let timer: number | null = null;

const statusLabel: Record<string, string> = {
  focus: '专注',
  break: '休息',
  help: '求助',
  offline: '离线',
};

const filtered = computed(() => {
  if (filter.value === 'all') return rows.value;
  if (filter.value === 'online') return rows.value.filter((r) => r.online);
  if (filter.value === 'offline') return rows.value.filter((r) => !r.online);
  return rows.value.filter((r) => r.status === 'help');
});

async function load() {
  loading.value = true;
  error.value = '';
  try {
    rows.value = await fetchTeacherPatrol(classId.value);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载巡查数据失败';
  } finally {
    loading.value = false;
  }
}

function frameSrc(row: PatrolStudent) {
  if (!row.frame_url) return '';
  const sep = row.frame_url.includes('?') ? '&' : '?';
  return `${row.frame_url}${sep}t=${encodeURIComponent(row.updated_at || String(Date.now()))}`;
}

watch(classId, () => void load());

onMounted(() => {
  void load();
  timer = window.setInterval(() => void load(), 4000);
});

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer);
});
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="自习室巡查" subtitle="学生开启智能监督后约 4 秒自动刷新画面">
      <template #actions>
        <div class="flex flex-wrap items-center gap-2">
          <div class="t-tabs">
            <button
              v-for="f in [
                { id: 'all', label: '全部' },
                { id: 'online', label: '在线' },
                { id: 'offline', label: '离线' },
                { id: 'help', label: '求助' },
              ]"
              :key="f.id"
              type="button"
              class="t-tab"
              :class="{ 'is-active': filter === f.id }"
              @click="filter = f.id as typeof filter"
            >
              {{ f.label }}
            </button>
          </div>
          <button type="button" class="t-btn t-btn--ghost t-btn--sm" :disabled="loading" @click="load">
            {{ loading ? '刷新中…' : '立即刷新' }}
          </button>
        </div>
      </template>
    </TeacherPageHeader>

    <p v-if="error" class="text-sm text-t-danger">{{ error }}</p>
    <TeacherLoading v-if="loading && !rows.length" :rows="4" />

    <div v-else class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <article
        v-for="row in filtered"
        :key="row.user_id"
        class="t-card t-card--hover cursor-pointer overflow-hidden"
        @click="preview = row"
      >
        <div class="aspect-video bg-t-bg/60">
          <img
            v-if="row.frame_url"
            :src="frameSrc(row)"
            :alt="`${row.display_name} 巡查截图`"
            class="h-full w-full object-cover"
          />
          <div v-else class="flex h-full items-center justify-center text-xs text-t-3">暂无截图</div>
        </div>
        <div class="space-y-1 px-4 py-3">
          <div class="flex items-center justify-between gap-2">
            <p class="text-sm font-medium text-t-1">{{ row.display_name }}</p>
            <span
              class="t-badge"
              :class="row.status === 'help' ? 't-badge--danger' : row.online ? 't-badge--ok' : 't-badge--neutral'"
            >
              {{ statusLabel[row.status] || row.status }}
            </span>
          </div>
          <p class="text-[11px] text-t-3">
            {{ row.class_name || '未分班' }}
            <template v-if="row.room_name"> · {{ row.constellation }} · {{ row.room_name }}</template>
          </p>
        </div>
      </article>
      <div v-if="!filtered.length" class="sm:col-span-2 xl:col-span-3">
        <TeacherEmptyState title="暂无巡查画面" description="学生进入自习室并开启监督后会出现在这里" />
      </div>
    </div>

    <!-- Fullscreen preview -->
    <div
      v-if="preview"
      class="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
      @click.self="preview = null"
    >
      <div class="t-cmdk max-h-[90vh] w-full max-w-3xl overflow-hidden">
        <div class="flex items-center justify-between border-b border-t-line/10 px-4 py-3">
          <p class="text-sm font-medium text-t-1">{{ preview.display_name }} · {{ statusLabel[preview.status] || preview.status }}</p>
          <button type="button" class="text-xs text-t-3 transition hover:text-t-1" @click="preview = null">关闭</button>
        </div>
        <div class="bg-black">
          <img v-if="preview.frame_url" :src="frameSrc(preview)" alt="预览" class="max-h-[70vh] w-full object-contain" />
          <p v-else class="py-20 text-center text-sm text-t-3">暂无截图</p>
        </div>
      </div>
    </div>
  </div>
</template>

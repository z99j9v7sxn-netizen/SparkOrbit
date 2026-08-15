<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRouter } from 'vue-router';
import { exportGradesCsv, fetchGradebook, type GradebookRow } from '../../api/teacher';
import { parseApiError } from '../../api/errors';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';
import { useTeacherClassStore } from '../../stores/teacherClass';

const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);
const router = useRouter();

const rows = ref<GradebookRow[]>([]);
const sortKey = ref<keyof GradebookRow>('mastery_rate');
const search = ref('');
const loading = ref(false);
const error = ref('');
const exportMsg = ref('');

async function load() {
  if (!classId.value) {
    rows.value = [];
    return;
  }
  loading.value = true;
  error.value = '';
  try {
    rows.value = await fetchGradebook(classId.value);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载成绩失败';
  } finally {
    loading.value = false;
  }
}

const filteredRows = computed(() => {
  const q = search.value.trim().toLowerCase();
  let list = [...rows.value];
  if (q) {
    list = list.filter(
      (r) => r.display_name.toLowerCase().includes(q) || r.username.toLowerCase().includes(q),
    );
  }
  return list.sort((a, b) => Number(b[sortKey.value] ?? 0) - Number(a[sortKey.value] ?? 0));
});

async function exportCsv() {
  if (!classId.value) {
    exportMsg.value = '请先选择班级';
    return;
  }
  exportMsg.value = '';
  try {
    await exportGradesCsv(classId.value);
    exportMsg.value = '成绩 CSV 已下载';
  } catch (err) {
    exportMsg.value = parseApiError(err, '导出失败');
  }
}

function openStudent(id: string) {
  void router.push({ path: `/teacher/students/${id}`, query: { class_id: classId.value } });
}

function barColor(rate: number) {
  if (rate >= 70) return 'bg-t-ok';
  if (rate >= 40) return 'bg-t-warn';
  return 'bg-t-danger';
}

watch(classId, () => void load());
onMounted(load);
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="成绩册" subtitle="掌握率、答题正确率与作业均分统计">
      <template #actions>
        <input v-model="search" placeholder="搜索姓名 / 用户名" class="t-input w-48" />
        <button type="button" class="t-btn t-btn--soft t-btn--sm" @click="exportCsv">导出 CSV</button>
      </template>
    </TeacherPageHeader>

    <p v-if="exportMsg" class="text-xs" :class="exportMsg.includes('失败') ? 'text-t-danger' : 'text-t-ok'">
      {{ exportMsg }}
    </p>

    <TeacherLoading v-if="loading" variant="skeleton" :rows="6" />
    <p v-else-if="error" class="text-sm text-t-danger">{{ error }}</p>

    <section v-else class="t-table-wrap">
      <table class="t-table">
        <thead>
          <tr>
            <th>姓名</th>
            <th class="cursor-pointer select-none" @click="sortKey = 'mastery_rate'">
              掌握率 <span v-if="sortKey === 'mastery_rate'" class="text-t-accent">↓</span>
            </th>
            <th class="cursor-pointer select-none" @click="sortKey = 'quiz_accuracy'">
              答题正确率 <span v-if="sortKey === 'quiz_accuracy'" class="text-t-accent">↓</span>
            </th>
            <th class="cursor-pointer select-none" @click="sortKey = 'assignment_avg'">
              作业均分 <span v-if="sortKey === 'assignment_avg'" class="text-t-accent">↓</span>
            </th>
            <th>点亮</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in filteredRows" :key="r.user_id" class="is-clickable" @click="openStudent(r.user_id)">
            <td>
              <p class="font-medium text-t-1">{{ r.display_name }}</p>
              <p class="text-[10px] text-t-3">{{ r.username }}</p>
            </td>
            <td>
              <div class="flex items-center gap-2">
                <div class="h-1.5 w-16 overflow-hidden rounded-full bg-t-line/12">
                  <div class="h-full rounded-full" :class="barColor(r.mastery_rate)" :style="{ width: `${r.mastery_rate}%` }" />
                </div>
                <span class="font-mono-tech">{{ r.mastery_rate }}%</span>
              </div>
            </td>
            <td>
              <div class="flex items-center gap-2">
                <div class="h-1.5 w-16 overflow-hidden rounded-full bg-t-line/12">
                  <div class="h-full rounded-full" :class="barColor(r.quiz_accuracy)" :style="{ width: `${r.quiz_accuracy}%` }" />
                </div>
                <span class="font-mono-tech">{{ r.quiz_accuracy }}%</span>
              </div>
            </td>
            <td class="font-mono-tech">{{ r.assignment_avg ?? '—' }}</td>
            <td class="font-mono-tech">{{ r.lit_count }}/{{ r.total_planets }}</td>
          </tr>
        </tbody>
      </table>
      <TeacherEmptyState v-if="!filteredRows.length" class="m-4" title="暂无成绩数据" />
    </section>
  </div>
</template>

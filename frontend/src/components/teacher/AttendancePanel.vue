<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { fetchClassStudyPresence } from '../../api/study';
import { fetchAttendance, setAttendance, type AttendanceRow } from '../../api/teacher';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';
import TeacherStatCard from './TeacherStatCard.vue';
import { useTeacherClassStore } from '../../stores/teacherClass';

const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);

const presence = ref<Array<{ user_id: string; display_name: string; room_name: string; constellation: string }>>([]);
const attendance = ref<AttendanceRow[]>([]);
const recordDate = ref(new Date().toISOString().slice(0, 10));
const loading = ref(false);
const error = ref('');

const studentIds = computed(() => new Set(attendance.value.map((a) => a.student_id)));

const filteredPresence = computed(() =>
  presence.value.filter((p) => studentIds.value.has(p.user_id)),
);

const presentCount = computed(
  () => attendance.value.filter((a) => a.status === 'present' || a.status === 'late').length,
);
const attendanceRate = computed(() => {
  if (!attendance.value.length) return 0;
  return Math.round((presentCount.value / attendance.value.length) * 100);
});

async function load() {
  if (!classId.value) {
    presence.value = [];
    attendance.value = [];
    return;
  }
  loading.value = true;
  error.value = '';
  try {
    try {
      presence.value = await fetchClassStudyPresence();
    } catch {
      presence.value = [];
    }
    attendance.value = await fetchAttendance(classId.value, recordDate.value);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载考勤失败';
  } finally {
    loading.value = false;
  }
}

async function mark(studentId: string, status: string) {
  await setAttendance(classId.value, studentId, status, recordDate.value);
  attendance.value = await fetchAttendance(classId.value, recordDate.value);
}

function statusBtn(active: boolean, activeClass: string) {
  return active ? activeClass : 'text-t-3 hover:bg-t-line/8 hover:text-t-2';
}

watch(classId, () => void load());
watch(recordDate, () => void load());
onMounted(load);
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="考勤管理" subtitle="自习室在线态势与日常考勤登记">
      <template #actions>
        <input v-model="recordDate" type="date" class="t-input w-auto" />
      </template>
    </TeacherPageHeader>

    <div class="grid grid-cols-2 gap-4 lg:grid-cols-3">
      <TeacherStatCard label="应到人数" :value="attendance.length" />
      <TeacherStatCard label="出勤/迟到" :value="presentCount" accent="emerald" />
      <TeacherStatCard label="当日出勤率" :value="`${attendanceRate}%`" accent="sky" />
    </div>

    <TeacherLoading v-if="loading" variant="skeleton" :rows="6" />
    <p v-else-if="error" class="text-sm text-t-danger">{{ error }}</p>

    <template v-else>
      <div class="grid gap-4 xl:grid-cols-2">
        <section class="t-card glass-edge p-5">
          <div class="flex items-baseline justify-between gap-2">
            <h3 class="text-[15px] font-semibold text-t-1">自习室在线态势</h3>
            <span class="t-kicker">Live</span>
          </div>
          <p class="mt-1 text-xs text-t-3">仅显示当前班级学生</p>
          <div class="mt-3 space-y-2">
            <div
              v-for="p in filteredPresence"
              :key="p.user_id"
              class="flex items-center justify-between rounded-xl border border-t-line/10 bg-t-s1/30 px-4 py-2"
            >
              <span class="flex items-center gap-2 text-sm font-medium text-t-1">
                <span class="lz-pulse-dot" aria-hidden="true" />
                {{ p.display_name }}
              </span>
              <span class="text-xs text-t-accent">{{ p.constellation }} · {{ p.room_name }}</span>
            </div>
            <TeacherEmptyState v-if="!filteredPresence.length" title="当前无学生在自习室" />
          </div>
        </section>

        <section class="t-card glass-edge p-5">
          <h3 class="text-[15px] font-semibold text-t-1">考勤登记</h3>
          <div class="mt-3 space-y-2">
            <div
              v-for="a in attendance"
              :key="a.student_id"
              class="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-t-line/10 bg-t-s1/30 px-4 py-2"
            >
              <span class="text-sm font-medium text-t-1">{{ a.display_name }}</span>
              <div class="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  class="rounded-lg px-2.5 py-1 text-xs transition"
                  :class="statusBtn(a.status === 'present', 'bg-t-ok/15 font-medium text-t-ok')"
                  @click="mark(a.student_id, 'present')"
                >
                  出勤
                </button>
                <button
                  type="button"
                  class="rounded-lg px-2.5 py-1 text-xs transition"
                  :class="statusBtn(a.status === 'late', 'bg-t-warn/15 font-medium text-t-warn')"
                  @click="mark(a.student_id, 'late')"
                >
                  迟到
                </button>
                <button
                  type="button"
                  class="rounded-lg px-2.5 py-1 text-xs transition"
                  :class="statusBtn(a.status === 'leave', 'bg-t-accent/15 font-medium text-t-accent')"
                  @click="mark(a.student_id, 'leave')"
                >
                  请假
                </button>
                <button
                  type="button"
                  class="rounded-lg px-2.5 py-1 text-xs transition"
                  :class="statusBtn(a.status === 'absent', 'bg-t-danger/15 font-medium text-t-danger')"
                  @click="mark(a.student_id, 'absent')"
                >
                  缺勤
                </button>
              </div>
            </div>
            <TeacherEmptyState v-if="!attendance.length" title="暂无学生" description="请先在名册中导入学生" />
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

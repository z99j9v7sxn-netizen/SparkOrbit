<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { fetchInterviewRoles, type InterviewJobRole } from '../../api/interview';
import { createAssignment } from '../../api/teacher';
import {
  fetchTeacherInterviewOverview,
  fetchTeacherInterviewSession,
  fetchTeacherInterviewSessions,
  reviewTeacherInterviewReport,
  type InterviewOverview,
  type TeacherInterviewSession,
} from '../../api/teacherSuite';
import type { InterviewSessionDetail } from '../../api/interview';
import { useTeacherClassStore } from '../../stores/teacherClass';
import TeacherPageHeader from './TeacherPageHeader.vue';

const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);

const overview = ref<InterviewOverview | null>(null);
const sessions = ref<TeacherInterviewSession[]>([]);
const selected = ref<InterviewSessionDetail | null>(null);
const roles = ref<InterviewJobRole[]>([]);
const loading = ref(false);
const message = ref('');
const comment = ref('');
const teacherScore = ref('');

const title = ref('模拟面试任务');
const scenario = ref<'job' | 'academic'>('job');
const jobRole = ref('backend');
const difficulty = ref('medium');
const questionCount = ref(4);
const stem = ref('');

const filteredRoles = computed(() => roles.value.filter((r) => r.scenario === scenario.value));

async function load() {
  loading.value = true;
  message.value = '';
  try {
    overview.value = await fetchTeacherInterviewOverview();
    sessions.value = await fetchTeacherInterviewSessions();
  } catch (e) {
    message.value = e instanceof Error ? e.message : '加载失败';
  } finally {
    loading.value = false;
  }
}

async function openSession(id: string) {
  try {
    selected.value = await fetchTeacherInterviewSession(id);
    comment.value = selected.value.report?.teacher_comment || '';
    teacherScore.value = selected.value.report?.teacher_score != null ? String(selected.value.report.teacher_score) : '';
  } catch (e) {
    message.value = e instanceof Error ? e.message : '详情加载失败';
  }
}

async function submitReview() {
  const reportId = selected.value?.report?.id;
  if (!reportId) return;
  try {
    await reviewTeacherInterviewReport(reportId, {
      comment: comment.value,
      score: teacherScore.value ? Number(teacherScore.value) : null,
      status: 'reviewed',
    });
    message.value = '已写回教师评议';
    await openSession(selected.value!.id);
    await load();
  } catch (e) {
    message.value = e instanceof Error ? e.message : '评议失败';
  }
}

async function dispatchTask() {
  if (!classId.value) {
    message.value = '请先选择班级';
    return;
  }
  try {
    await createAssignment({
      class_id: classId.value,
      title: title.value || '模拟面试任务',
      description: stem.value || '请进入学生端「模拟面试区」完成任务。',
      galaxy_slug: 'interview',
      questions: [
        {
          kind: 'interview',
          stem: stem.value || title.value,
          scenario: scenario.value,
          job_role: jobRole.value,
          question_count: questionCount.value,
          difficulty: difficulty.value,
        },
      ],
    });
    message.value = '已下发面试任务';
  } catch (e) {
    message.value = e instanceof Error ? e.message : '下发失败';
  }
}

watch(scenario, () => {
  const first = filteredRoles.value[0];
  if (first) jobRole.value = first.key;
});

onMounted(async () => {
  try {
    roles.value = await fetchInterviewRoles();
    const first = filteredRoles.value[0];
    if (first) jobRole.value = first.key;
  } catch {
    roles.value = [];
  }
  await load();
});
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader
      title="模拟面试督导"
      subtitle="下发求职/升学面试任务，回看班级会话、三视角报告并写回评议。"
      accent="violet"
    >
      <template #actions>
        <button type="button" class="t-btn t-btn--ghost t-btn--sm" @click="load">刷新</button>
      </template>
    </TeacherPageHeader>

    <p v-if="message" class="text-sm text-t-ok">{{ message }}</p>

    <div class="grid gap-3 md:grid-cols-4">
      <div class="t-card p-4">
        <p class="text-xs text-t-3">本班场次</p>
        <p class="mt-1 text-2xl text-t-1">{{ overview?.total ?? 0 }}</p>
      </div>
      <div class="t-card p-4">
        <p class="text-xs text-t-3">已完成</p>
        <p class="mt-1 text-2xl text-t-1">{{ overview?.completed ?? 0 }}</p>
      </div>
      <div class="t-card p-4">
        <p class="text-xs text-t-3">待评议</p>
        <p class="mt-1 text-2xl text-t-1">{{ overview?.pending_review ?? 0 }}</p>
      </div>
      <div class="t-card p-4">
        <p class="text-xs text-t-3">平均分</p>
        <p class="mt-1 text-2xl text-t-1">{{ overview?.avg_score ?? '—' }}</p>
      </div>
    </div>

    <section class="t-card space-y-3 p-4">
      <h3 class="text-sm font-medium text-t-1">下发面试任务</h3>
      <div class="grid gap-3 md:grid-cols-2">
        <label class="text-xs text-t-3">
          标题
          <input v-model="title" class="t-input mt-1 w-full" />
        </label>
        <label class="text-xs text-t-3">
          说明
          <input v-model="stem" class="t-input mt-1 w-full" placeholder="可选：岗位或专业提示" />
        </label>
        <label class="text-xs text-t-3">
          舱别
          <select v-model="scenario" class="t-input mt-1 w-full">
            <option value="job">求职舱</option>
            <option value="academic">升学舱</option>
          </select>
        </label>
        <label class="text-xs text-t-3">
          岗位 / 场景
          <select v-model="jobRole" class="t-input mt-1 w-full">
            <option v-for="role in filteredRoles" :key="role.key" :value="role.key">{{ role.label }}</option>
          </select>
        </label>
        <label class="text-xs text-t-3">
          难度
          <select v-model="difficulty" class="t-input mt-1 w-full">
            <option value="easy">入门</option>
            <option value="medium">标准</option>
            <option value="hard">加压</option>
          </select>
        </label>
        <label class="text-xs text-t-3">
          轮数
          <input v-model.number="questionCount" class="t-input mt-1 w-full" type="number" min="2" max="8" />
        </label>
      </div>
      <button type="button" class="t-btn t-btn--primary t-btn--sm" @click="dispatchTask">下发到当前班级</button>
    </section>

    <div class="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
      <section class="space-y-2">
        <p v-if="loading" class="text-sm text-t-3">加载中…</p>
        <button
          v-for="row in sessions"
          :key="row.id"
          type="button"
          class="t-card flex w-full items-center justify-between p-3 text-left"
          @click="openSession(row.id)"
        >
          <div>
            <p class="text-sm text-t-1">{{ row.student_name || '同学' }} · {{ row.job_role_label }}</p>
            <p class="text-xs text-t-3">{{ row.status }} · {{ row.review_status || '无报告' }}</p>
          </div>
          <span class="text-lg text-t-1">{{ row.overall_score ?? '—' }}</span>
        </button>
      </section>

      <section v-if="selected" class="t-card space-y-3 p-4">
        <h3 class="text-sm font-medium text-t-1">{{ selected.job_role_label }} · {{ selected.student_name }}</h3>
        <p class="text-sm leading-relaxed text-t-2">{{ selected.report?.summary || '报告尚未生成' }}</p>
        <div v-if="selected.report" class="grid gap-2 md:grid-cols-2">
          <article
            v-for="(view, role) in selected.report.council_views"
            :key="role"
            class="rounded-xl border border-t-line/15 p-3 text-xs text-t-2"
          >
            <p class="text-t-1">{{ (view as { role?: string }).role || role }}</p>
            <p class="mt-1">{{ (view as { view?: string }).view }}</p>
          </article>
        </div>
        <label class="block text-xs text-t-3">
          教师评语
          <textarea v-model="comment" class="t-input mt-1 min-h-[5rem] w-full" />
        </label>
        <label class="block text-xs text-t-3">
          教师分数
          <input v-model="teacherScore" class="t-input mt-1 w-32" type="number" min="0" max="100" />
        </label>
        <button type="button" class="t-btn t-btn--primary t-btn--sm" :disabled="!selected.report" @click="submitReview">
          提交评议
        </button>
      </section>
    </div>
  </div>
</template>

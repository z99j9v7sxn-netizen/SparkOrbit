<script setup lang="ts">
import { onMounted, ref } from 'vue';
import {
  fetchTeacherImprovementPending,
  overrideImprovement,
  type ImprovementGrade,
  type RemediationPlanView,
} from '../../api/profiles';
import TeacherPageHeader from './TeacherPageHeader.vue';

const GRADE_LABEL: Record<string, string> = {
  excellent: '优秀',
  pass: '合格',
  fail: '不合格',
};

const items = ref<RemediationPlanView[]>([]);
const loading = ref(false);
const message = ref('');
const feedbackDraft = ref<Record<string, string>>({});
const overridingId = ref<string | null>(null);

async function load() {
  loading.value = true;
  message.value = '';
  try {
    items.value = await fetchTeacherImprovementPending();
  } catch (e) {
    message.value = e instanceof Error ? e.message : '加载失败';
    items.value = [];
  } finally {
    loading.value = false;
  }
}

async function override(item: RemediationPlanView, grade: ImprovementGrade) {
  const submissionId = item.submission?.id;
  if (!submissionId) return;
  overridingId.value = submissionId;
  message.value = '';
  try {
    await overrideImprovement(submissionId, grade, feedbackDraft.value[submissionId] || '');
    message.value = `已覆盖为「${GRADE_LABEL[grade]}」`;
    await load();
  } catch (e) {
    message.value = e instanceof Error ? e.message : '覆盖失败';
  } finally {
    overridingId.value = null;
  }
}

onMounted(() => {
  void load();
});
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader
      title="画像改进复核"
      subtitle="AI 已给出优秀/合格/不合格预评；教师可覆盖并重算维度分数。"
      accent="violet"
    >
      <template #actions>
        <button type="button" class="t-btn t-btn--ghost t-btn--sm" @click="load">刷新</button>
      </template>
    </TeacherPageHeader>

    <div class="flex items-center gap-2">
      <span class="t-badge t-badge--info">待复核 {{ items.length }} 条</span>
      <p v-if="message" class="text-sm text-t-ok">{{ message }}</p>
    </div>

    <p v-if="loading" class="text-sm text-t-3">加载中…</p>
    <p v-else-if="!items.length" class="t-card--flat rounded-2xl border border-dashed border-t-line/15 px-4 py-8 text-center text-sm text-t-3">
      暂无待复核的改进提交。
    </p>

    <div v-else class="space-y-4">
      <article
        v-for="item in items"
        :key="item.submission?.id || item.id"
        class="t-card t-card--hover p-4"
      >
        <div class="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p class="text-sm font-medium text-t-1">{{ item.student_name || '学生' }} · {{ item.topic }}</p>
            <p class="mt-1 text-xs text-t-2">
              目标维 {{ item.target_dimension_label }} · AI
              {{ GRADE_LABEL[item.submission?.ai_grade || ''] || item.submission?.ai_grade }}
              · 已加 {{ item.submission?.applied_delta ?? 0 }} 分
            </p>
          </div>
          <span class="t-badge t-badge--info">待复核</span>
        </div>
        <p v-if="item.root_cause" class="mt-2 text-xs leading-5 text-t-2">错因：{{ item.root_cause }}</p>
        <p v-if="item.submission?.reflection" class="mt-2 text-xs leading-5 text-t-2">
          反思：{{ item.submission.reflection }}
        </p>
        <p v-if="item.submission?.ai_feedback" class="mt-1 text-xs text-t-3">AI 反馈：{{ item.submission.ai_feedback }}</p>
        <ul class="mt-2 space-y-1 text-xs text-t-3">
          <li v-for="step in item.steps" :key="step.index">
            {{ step.index + 1 }}. {{ step.title }}
            <span v-if="step.evidence_text"> — {{ step.evidence_text }}</span>
          </li>
        </ul>
        <textarea
          v-if="item.submission"
          v-model="feedbackDraft[item.submission.id]"
          class="t-input mt-3"
          rows="2"
          placeholder="教师反馈（可选）"
        />
        <div class="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            class="t-btn t-btn--sm border-t-ok/40 bg-t-ok/12 text-t-ok hover:bg-t-ok/20"
            :disabled="!item.submission || overridingId === item.submission.id"
            @click="item.submission && override(item, 'excellent')"
          >
            覆盖为优秀
          </button>
          <button
            type="button"
            class="t-btn t-btn--soft t-btn--sm"
            :disabled="!item.submission || overridingId === item.submission.id"
            @click="item.submission && override(item, 'pass')"
          >
            覆盖为合格
          </button>
          <button
            type="button"
            class="t-btn t-btn--danger t-btn--sm"
            :disabled="!item.submission || overridingId === item.submission.id"
            @click="item.submission && override(item, 'fail')"
          >
            覆盖为不合格
          </button>
        </div>
      </article>
    </div>
  </div>
</template>

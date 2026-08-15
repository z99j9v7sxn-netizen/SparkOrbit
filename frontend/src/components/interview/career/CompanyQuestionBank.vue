<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { LzBadge, LzButton, LzEmptyState, LzSkeleton } from '../../learning/ui';
import { parseApiError } from '../../../api/errors';
import {
  fetchCareerQuestions,
  fetchInterviewRoles,
  type CareerQuestion,
  type InterviewJobRole,
  type InterviewPracticeQuestion,
} from '../../../api/interview';

const emit = defineEmits<{
  (e: 'practice', payload: InterviewPracticeQuestion): void;
}>();

const KIND_LABEL: Record<string, string> = {
  tech: '技术基础',
  project: '项目经验',
  business: '业务理解',
  soft: '软技能',
  research: '科研潜质',
  method: '方法与推导',
  comprehensive: '综合素质',
};

const loading = ref(true);
const error = ref('');
const companies = ref<Array<{ id: string; name: string }>>([]);
const questions = ref<CareerQuestion[]>([]);
const roles = ref<InterviewJobRole[]>([]);
const company = ref('');
const jobRole = ref('');

const filtered = computed(() => questions.value);

onMounted(async () => {
  try {
    const [bank, roleList] = await Promise.all([fetchCareerQuestions(), fetchInterviewRoles()]);
    companies.value = bank.companies;
    questions.value = bank.questions;
    roles.value = roleList;
  } catch (err) {
    error.value = parseApiError(err, '面经加载失败');
  } finally {
    loading.value = false;
  }
});

watch([company, jobRole], async () => {
  try {
    const bank = await fetchCareerQuestions({
      company: company.value || undefined,
      job_role: jobRole.value || undefined,
    });
    questions.value = bank.questions;
  } catch (err) {
    error.value = parseApiError(err, '筛选失败');
  }
});

function practice(item: CareerQuestion) {
  const role = roles.value.find((r) => r.key === item.job_role);
  emit('practice', {
    question: item.question,
    kind: item.kind,
    kind_label: KIND_LABEL[item.kind] || item.kind,
    scenario: item.company_id === 'academic' || item.company_id === 'gwy' ? 'academic' : 'job',
    job_role: item.job_role,
    job_role_label: role?.label || item.job_role,
  });
}
</script>

<template>
  <div class="space-y-3">
    <p class="text-xs text-slate-500">自编常见题，一键进练习舱。不是爬取的面经站内容。</p>
    <div class="flex flex-wrap gap-2">
      <select v-model="company" class="lz-input h-[34px] w-40 text-xs">
        <option value="">全部公司</option>
        <option v-for="c in companies" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>
      <select v-model="jobRole" class="lz-input h-[34px] w-40 text-xs">
        <option value="">全部岗位</option>
        <option v-for="r in roles" :key="r.key" :value="r.key">{{ r.label }}</option>
      </select>
    </div>
    <p v-if="error" class="text-xs text-rose-300">{{ error }}</p>
    <div v-if="loading"><LzSkeleton preset="card" /></div>
    <article v-for="item in filtered" :key="item.id" class="lz-card flex items-start justify-between gap-3 p-4">
      <div class="min-w-0">
        <p class="text-[11px] text-slate-500">
          {{ item.company }} · {{ item.job_role }}
          <LzBadge class="ml-1" tone="warning">{{ KIND_LABEL[item.kind] || item.kind }}</LzBadge>
        </p>
        <p class="mt-1 text-sm leading-relaxed text-slate-100">{{ item.question }}</p>
      </div>
      <LzButton size="sm" variant="primary" @click="practice(item)">练这题</LzButton>
    </article>
    <LzEmptyState v-if="!loading && !filtered.length" title="没有匹配的题目" />
  </div>
</template>

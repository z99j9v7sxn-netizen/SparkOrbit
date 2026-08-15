<script setup lang="ts">
import { ref } from 'vue';
import { generateSimilarQuestions, gradeAnswers, type GradeItemResult, type SimilarQuestionItem } from '../../api/ai';
import { ocrMistakePhoto } from '../../api/zone';
import VoiceInputButton from '../common/VoiceInputButton.vue';
import { LzButton, LzCard, LzInput, LzTabs, LzTextarea } from './ui';

const tab = ref<'similar' | 'grade'>('similar');
const sourceQuestion = ref('');
const subject = ref('');
const similarItems = ref<SimilarQuestionItem[]>([]);
const gradeQuestion = ref('');
const gradeReference = ref('');
const gradeStudent = ref('');
const gradeResults = ref<GradeItemResult[]>([]);
const gradeSummary = ref('');
const loadingSimilar = ref(false);
const loadingGrade = ref(false);
const error = ref('');

function appendVoice(target: 'similar' | 'grade', text: string) {
  if (target === 'similar') sourceQuestion.value += text;
  else gradeQuestion.value += text;
}

async function fillFromPhoto(target: 'similar' | 'grade', ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0];
  if (!file) return;
  error.value = '';
  try {
    const res = await ocrMistakePhoto(file);
    const text = res.question || '';
    if (target === 'similar') sourceQuestion.value = text;
    else gradeQuestion.value = text;
    if (res.subject_guess) subject.value = res.subject_guess;
    if (res.correct_answer_guess && target === 'grade') gradeReference.value = res.correct_answer_guess;
  } catch (e) {
    error.value = e instanceof Error ? e.message : '图片识别失败';
  }
}

async function runSimilar() {
  if (!sourceQuestion.value.trim()) return;
  loadingSimilar.value = true;
  error.value = '';
  try {
    const res = await generateSimilarQuestions(sourceQuestion.value.trim(), 3, subject.value);
    similarItems.value = res.items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : '生成失败';
  } finally {
    loadingSimilar.value = false;
  }
}

async function runGrade() {
  if (!gradeQuestion.value.trim()) return;
  loadingGrade.value = true;
  error.value = '';
  try {
    const res = await gradeAnswers([
      {
        question: gradeQuestion.value.trim(),
        reference_answer: gradeReference.value.trim(),
        student_answer: gradeStudent.value.trim(),
      },
    ]);
    gradeResults.value = res.items;
    gradeSummary.value = res.summary;
  } catch (e) {
    error.value = e instanceof Error ? e.message : '批改失败';
  } finally {
    loadingGrade.value = false;
  }
}
</script>

<template>
  <div class="dock-panel space-y-4">
    <LzTabs
      :items="[
        { key: 'similar', label: '举一反三' },
        { key: 'grade', label: '智能批改' },
      ]"
      :model-value="tab"
      block
      @update:model-value="tab = $event as 'similar' | 'grade'"
    />
    <p v-if="error" class="lz-caption text-rose-300">{{ error }}</p>

    <div v-if="tab === 'similar'" class="space-y-3">
      <LzInput v-model="subject" placeholder="学科/主题（可选）" />
      <LzTextarea v-model="sourceQuestion" :rows="4" placeholder="粘贴或语音输入原题…" />
      <div class="flex gap-2">
        <label class="lz-btn lz-btn--ghost lz-btn--sm cursor-pointer">
          <img class="h-4 w-4" src="/icons/camera.svg" alt="" aria-hidden="true" /> 拍照<input type="file" accept="image/*" class="hidden" @change="fillFromPhoto('similar', $event)" />
        </label>
        <VoiceInputButton @text="(t) => appendVoice('similar', t)" />
      </div>
      <LzButton variant="primary" block :loading="loadingSimilar" @click="runSimilar">
        {{ loadingSimilar ? '生成中…' : '生成同类题' }}
      </LzButton>
      <LzCard v-for="(item, i) in similarItems" :key="i" padding="sm">
        <p class="lz-subtitle">{{ i + 1 }}. {{ item.question }}</p>
        <p class="lz-body mt-2 text-emerald-300">答案：{{ item.answer }}</p>
        <p class="lz-body mt-1 whitespace-pre-wrap">{{ item.explanation }}</p>
      </LzCard>
    </div>

    <div v-else class="space-y-3">
      <LzTextarea v-model="gradeQuestion" :rows="3" placeholder="题目" />
      <LzTextarea v-model="gradeReference" :rows="2" placeholder="参考答案（可选，留空由系统自行判断）" />
      <LzTextarea v-model="gradeStudent" :rows="2" placeholder="你的作答" />
      <div class="flex gap-2">
        <label class="lz-btn lz-btn--ghost lz-btn--sm cursor-pointer">
          <img class="h-4 w-4" src="/icons/camera.svg" alt="" aria-hidden="true" /> 拍照<input type="file" accept="image/*" class="hidden" @change="fillFromPhoto('grade', $event)" />
        </label>
        <VoiceInputButton @text="(t) => appendVoice('grade', t)" />
      </div>
      <LzButton variant="primary" block :loading="loadingGrade" @click="runGrade">
        {{ loadingGrade ? '批改中…' : '开始批改' }}
      </LzButton>
      <p v-if="gradeSummary" class="lz-body">{{ gradeSummary }}</p>
      <LzCard v-for="(item, i) in gradeResults" :key="i" padding="sm">
        <p class="lz-subtitle">{{ item.question }}</p>
        <p class="lz-desc lz-accent-text mt-1">得分 {{ item.score }} · {{ item.is_correct ? '正确' : '待改进' }}</p>
        <p class="lz-body mt-1">{{ item.feedback }}</p>
      </LzCard>
    </div>
  </div>
</template>

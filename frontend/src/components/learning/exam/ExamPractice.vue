<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import {
  checkPracticeAnswer,
  fetchPracticeQuestions,
  logPractice,
  type ExamQuestionItem,
  type PracticeCheckResult,
} from '../../../api/exam';
import { useOrbitStore } from '../../../stores/orbit';
import { LzBadge, LzButton, LzCard, LzEmptyState, LzTextarea } from '../ui';

const props = defineProps<{ examType: string }>();
const emit = defineEmits<{ (e: 'activity'): void }>();

const orbit = useOrbitStore();

const SECTIONS = [
  { key: 'listening', label: '听力' },
  { key: 'reading', label: '阅读' },
  { key: 'cloze', label: '选词填空' },
  { key: 'vocab', label: '词汇' },
  { key: 'translation', label: '翻译' },
  { key: 'writing', label: '写作' },
];

const section = ref('reading');
const loading = ref(false);
const questions = ref<ExamQuestionItem[]>([]);
const index = ref(0);
const picked = ref('');
const textAnswer = ref('');
const result = ref<PracticeCheckResult | null>(null);
const checking = ref(false);
const stats = ref({ total: 0, correct: 0 });
const finished = ref(false);

const current = computed(() => questions.value[index.value] ?? null);
const isObjective = computed(() =>
  ['listening', 'reading', 'cloze', 'vocab'].includes(current.value?.section || ''),
);

watch(
  () => props.examType,
  () => {
    questions.value = [];
    finished.value = false;
    result.value = null;
  },
);

async function start() {
  loading.value = true;
  finished.value = false;
  result.value = null;
  index.value = 0;
  picked.value = '';
  textAnswer.value = '';
  stats.value = { total: 0, correct: 0 };
  try {
    const res = await fetchPracticeQuestions(props.examType, section.value, 5);
    questions.value = res.questions;
  } catch (e) {
    questions.value = [];
    orbit.pushNotification('专项刷题', e instanceof Error ? e.message : '取题失败', 'warning');
  } finally {
    loading.value = false;
  }
}

async function check() {
  if (!current.value || checking.value) return;
  const answer = isObjective.value ? picked.value : textAnswer.value.trim();
  if (!answer) return;
  checking.value = true;
  try {
    result.value = await checkPracticeAnswer(current.value.id, answer);
    stats.value.total += 1;
    if (result.value.correct) stats.value.correct += 1;
    if (result.value.mistake_archived) {
      orbit.pushNotification('错题本', '已自动归档进错题本，进入复习队列', 'info');
    }
  } catch (e) {
    orbit.pushNotification('专项刷题', e instanceof Error ? e.message : '判题失败', 'warning');
  } finally {
    checking.value = false;
  }
}

async function next() {
  result.value = null;
  picked.value = '';
  textAnswer.value = '';
  if (index.value + 1 >= questions.value.length) {
    finished.value = true;
    try {
      await logPractice({
        exam_type: props.examType,
        section: section.value,
        activity: 'practice',
        total: stats.value.total,
        correct: stats.value.correct,
      });
      emit('activity');
    } catch {
      /* 日志失败不阻塞 */
    }
  } else {
    index.value += 1;
  }
}
</script>

<template>
  <div class="space-y-3">
    <div class="flex flex-wrap gap-1.5">
      <button
        v-for="s in SECTIONS"
        :key="s.key"
        type="button"
        class="rounded-full border px-2.5 py-1 text-[11px] transition"
        :class="section === s.key
          ? 'border-amber-400/50 bg-amber-500/15 text-amber-100'
          : 'border-white/10 text-slate-400 hover:text-slate-200'"
        @click="section = s.key"
      >
        {{ s.label }}
      </button>
    </div>

    <template v-if="!questions.length || finished">
      <LzCard v-if="finished" padding="lg" class="text-center">
        <p class="text-3xl">📊</p>
        <p class="lz-title mt-2">本组完成：{{ stats.correct }} / {{ stats.total }}</p>
        <p class="lz-desc mt-1">答错的题已归档进错题本，会按遗忘曲线安排复习</p>
        <LzButton variant="primary" class="mt-4" :loading="loading" @click="start">再来一组</LzButton>
      </LzCard>
      <LzEmptyState
        v-else-if="!loading"
        icon="🎯"
        title="选择题型开始刷题"
        desc="题库不足时会自动 AI 补题，取题可能需要十几秒"
      >
        <LzButton variant="primary" class="mt-3" @click="start">开始刷题</LzButton>
      </LzEmptyState>
      <LzCard v-else padding="lg" class="text-center">
        <p class="lz-desc">正在取题（题库不足时 AI 自动补题，请稍候）…</p>
      </LzCard>
    </template>

    <template v-else-if="current">
      <div class="flex items-center justify-between">
        <LzBadge tone="accent">第 {{ index + 1 }} / {{ questions.length }} 题</LzBadge>
        <span class="lz-caption">{{ current.source === 'import' ? '真题库' : 'AI 模拟题' }}</span>
      </div>

      <LzCard padding="md">
        <p v-if="current.audio_text" class="lz-caption mb-2">🎧 听力材料请在「听力精听」中训练；此处按原文作答</p>
        <p class="whitespace-pre-wrap text-sm leading-relaxed text-slate-100">{{ current.question }}</p>
        <p v-if="current.audio_text" class="lz-desc mt-2 whitespace-pre-wrap border-t border-white/10 pt-2">
          {{ current.audio_text }}
        </p>
      </LzCard>

      <template v-if="isObjective">
        <button
          v-for="(text, key) in current.options"
          :key="key"
          type="button"
          class="flex w-full items-start gap-2 rounded-[var(--radius-card)] border p-3 text-left text-sm transition"
          :class="[
            picked === key ? 'border-sky-400/60 bg-sky-500/15 text-sky-50' : 'border-white/10 text-slate-300 hover:border-white/25',
            result && key === result.answer ? '!border-emerald-400/70 !bg-emerald-500/15' : '',
            result && picked === key && !result.correct ? '!border-rose-400/70 !bg-rose-500/10' : '',
          ]"
          :disabled="Boolean(result)"
          @click="picked = String(key)"
        >
          <span class="font-semibold">{{ key }}.</span>
          <span>{{ text }}</span>
        </button>
      </template>
      <LzTextarea v-else v-model="textAnswer" :rows="5" :disabled="Boolean(result)" placeholder="输入你的译文 / 作文" />

      <LzCard v-if="result" padding="sm" :class="result.correct ? 'border-emerald-400/30' : 'border-rose-400/30'">
        <p class="lz-subtitle" :class="result.correct ? 'text-emerald-200' : 'text-rose-200'">
          {{ result.correct ? '✓ 回答正确' : '✗ 回答有误' }}
        </p>
        <p class="lz-desc mt-1">参考答案：{{ result.answer }}</p>
        <p v-if="result.analysis" class="lz-desc mt-1 whitespace-pre-wrap">{{ result.analysis }}</p>
      </LzCard>

      <div class="flex gap-2">
        <LzButton v-if="!result" variant="primary" block :loading="checking" @click="check">提交答案</LzButton>
        <LzButton v-else variant="primary" block @click="next">
          {{ index + 1 >= questions.length ? '完成本组' : '下一题' }}
        </LzButton>
      </div>
    </template>
  </div>
</template>

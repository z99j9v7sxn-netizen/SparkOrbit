<script setup lang="ts">
import { ref } from 'vue';
import { gradeEssay, type EssayGradeResult } from '../../../api/exam';
import { useOrbitStore } from '../../../stores/orbit';
import { LzBadge, LzButton, LzCard, LzInput, LzProgress, LzTextarea } from '../ui';

const props = defineProps<{ examType: string }>();
const emit = defineEmits<{ (e: 'activity'): void }>();

const orbit = useOrbitStore();
const kind = ref<'writing' | 'translation'>('writing');
const prompt = ref('');
const text = ref('');
const grading = ref(false);
const result = ref<EssayGradeResult | null>(null);

async function grade() {
  if (text.value.trim().length < 10) {
    orbit.pushNotification('写译批改', '内容太短，先写一段吧', 'warning');
    return;
  }
  grading.value = true;
  result.value = null;
  try {
    result.value = await gradeEssay({
      exam_type: props.examType,
      kind: kind.value,
      prompt: prompt.value,
      text: text.value,
    });
    emit('activity');
  } catch (e) {
    orbit.pushNotification('写译批改', e instanceof Error ? e.message : '批改失败', 'warning');
  } finally {
    grading.value = false;
  }
}
</script>

<template>
  <div class="space-y-3">
    <div class="flex gap-1.5">
      <button
        v-for="k in (['writing', 'translation'] as const)"
        :key="k"
        type="button"
        class="rounded-full border px-3 py-1 text-xs transition"
        :class="kind === k ? 'border-violet-400/50 bg-violet-500/15 text-violet-100' : 'border-white/10 text-slate-400'"
        @click="kind = k"
      >
        {{ k === 'writing' ? '写作批改' : '翻译批改' }}
      </button>
    </div>

    <LzInput v-model="prompt" :placeholder="kind === 'writing' ? '作文题目 / 要求（可选）' : '原文（中译英的中文段落，可选）'" />
    <LzTextarea v-model="text" :rows="8" :placeholder="kind === 'writing' ? '在此粘贴或撰写你的作文…' : '在此输入你的译文…'" />
    <LzButton variant="primary" block :loading="grading" @click="grade">
      {{ grading ? 'AI 批改中…' : '提交批改' }}
    </LzButton>

    <template v-if="result">
      <LzCard padding="lg" class="text-center">
        <p class="lz-caption uppercase tracking-widest">综合得分</p>
        <p class="mt-1 text-4xl font-semibold" :class="result.score >= 60 ? 'text-emerald-300' : 'text-rose-300'">
          {{ result.score }}
        </p>
      </LzCard>

      <div class="grid grid-cols-2 gap-2">
        <LzCard v-for="d in result.dimensions" :key="d.name" padding="sm">
          <LzProgress :value="d.score" :label="d.name" show-value />
          <p class="lz-caption mt-1">{{ d.comment }}</p>
        </LzCard>
      </div>

      <template v-if="result.sentence_feedback?.length">
        <p class="lz-subtitle">逐句润色</p>
        <LzCard v-for="(f, i) in result.sentence_feedback" :key="i" padding="sm">
          <p class="text-xs text-rose-200/90 line-through decoration-rose-400/40">{{ f.original }}</p>
          <p class="mt-1 text-xs text-emerald-200">{{ f.revised }}</p>
          <p class="lz-caption mt-1">{{ f.reason }}</p>
        </LzCard>
      </template>

      <template v-if="result.highlights?.length">
        <p class="lz-subtitle">亮点表达</p>
        <div class="flex flex-wrap gap-1.5">
          <LzBadge v-for="(h, i) in result.highlights" :key="i" tone="success">{{ h }}</LzBadge>
        </div>
      </template>

      <template v-if="result.suggestions?.length">
        <p class="lz-subtitle">提升建议</p>
        <ul class="space-y-1">
          <li v-for="(s, i) in result.suggestions" :key="i" class="lz-desc">· {{ s }}</li>
        </ul>
      </template>
    </template>
  </div>
</template>

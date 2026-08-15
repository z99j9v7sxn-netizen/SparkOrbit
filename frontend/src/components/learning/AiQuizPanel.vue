<script setup lang="ts">
import { ref } from 'vue';
import { fetchAiQuiz, submitAiQuiz } from '../../api/zone';
import { useOrbitStore } from '../../stores/orbit';
import { parseApiError } from '../../api/errors';
import { LzButton, LzCard, LzEmptyState, LzSkeleton, LzTextarea } from './ui';

const orbit = useOrbitStore();
const loading = ref(false);
const questions = ref<{ q: string; hint: string }[]>([]);
const topic = ref('');
const slug = ref('');
const answers = ref<Record<number, string>>({});
const submitting = ref<number | null>(null);
const feedback = ref<Record<number, string>>({});
const msg = ref('');

async function load() {
  const planetSlug = orbit.selectedPlanet?.slug;
  if (!planetSlug) {
    topic.value = '请先在星图中选中一颗行星';
    questions.value = [];
    slug.value = '';
    return;
  }
  loading.value = true;
  msg.value = '';
  try {
    const data = await fetchAiQuiz(planetSlug);
    slug.value = data.slug || planetSlug;
    topic.value = data.name || planetSlug;
    questions.value = data.questions || [];
    answers.value = {};
    feedback.value = {};
  } finally {
    loading.value = false;
  }
}

async function submitOne(index: number, selfOk: boolean) {
  if (!slug.value) return;
  submitting.value = index;
  msg.value = '';
  try {
    const res = await submitAiQuiz({
      slug: slug.value,
      question_index: index,
      answer: answers.value[index] || '',
      self_ok: selfOk,
    });
    feedback.value[index] = res.feedback || res.message;
    msg.value = res.message || (res.correct ? '已记入掌握证据' : '已记入薄弱证据');
  } catch (err) {
    msg.value = parseApiError(err, '提交失败');
  } finally {
    submitting.value = null;
  }
}

defineExpose({ load });
</script>

<template>
  <div class="dock-panel space-y-3">
    <div class="flex items-center justify-between gap-2">
      <p class="lz-desc">基于当前知识点生成智能测验；作答后写入随学随新</p>
      <LzButton variant="soft" size="sm" class="shrink-0" @click="load">刷新题目</LzButton>
    </div>
    <LzSkeleton v-if="loading" preset="text" :rows="3" />
    <p v-else-if="topic" class="lz-subtitle">当前知识点：{{ topic }}</p>
    <p v-if="msg" class="lz-caption text-emerald-300">{{ msg }}</p>
    <LzCard v-for="(item, i) in questions" :key="i" padding="sm">
      <p class="lz-body">{{ i + 1 }}. {{ item.q }}</p>
      <p class="lz-caption mt-1">提示：{{ item.hint }}</p>
      <LzTextarea v-model="answers[i]" :rows="2" placeholder="写下你的理解…" class="mt-2" />
      <div class="mt-2 flex flex-wrap gap-2">
        <button
          type="button"
          class="rounded-[var(--radius-ctl)] border border-emerald-400/30 bg-emerald-500/10 px-2.5 py-1 text-[11px] text-emerald-200 transition hover:bg-emerald-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/40 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="submitting === i"
          @click="submitOne(i, true)"
        >
          自评掌握并提交
        </button>
        <LzButton variant="soft" size="sm" :disabled="submitting === i" @click="submitOne(i, false)">
          仍不确定，记入薄弱
        </LzButton>
      </div>
      <p v-if="feedback[i]" class="lz-caption lz-accent-text mt-1.5">{{ feedback[i] }}</p>
    </LzCard>
    <LzEmptyState
      v-if="!loading && !questions.length"
      icon="🪐"
      title="还没有测验题"
      desc="选中星图行星后点击刷新，即可生成测验题。"
      actionText="刷新题目"
      @action="load"
    />
    <p class="lz-caption">答完可去行星面板完成四闸，或回学习路径打卡，形成闭环。</p>
  </div>
</template>

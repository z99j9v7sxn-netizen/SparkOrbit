<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import {
  fetchReviewQueue,
  submitReview,
  type ReviewQueueItem,
  type ReviewResult,
} from '../../api/review';
import { useOrbitStore } from '../../stores/orbit';
import { LzBadge, LzButton, LzCard, LzEmptyState, LzProgress, LzSkeleton } from './ui';

const orbit = useOrbitStore();
const loading = ref(true);
const items = ref<ReviewQueueItem[]>([]);
const index = ref(0);
const revealed = ref(false);
const submitting = ref(false);
const doneCount = ref(0);
const rememberCount = ref(0);
const finished = ref(false);
const counts = ref({ planet: 0, mistake: 0, card: 0 });

const current = computed(() => items.value[index.value] ?? null);
const totalCount = computed(() => items.value.length);
const progressPct = computed(() =>
  totalCount.value ? Math.round((doneCount.value / totalCount.value) * 100) : 0,
);

const TYPE_LABEL: Record<string, string> = {
  planet: '星球固化',
  mistake: '错题回炉',
  word: '词汇',
  card: '知识卡',
};

const wordExtra = computed(() => {
  if (!current.value || current.value.item_type !== 'word') return null;
  try {
    return JSON.parse(String(current.value.meta?.extra || '{}')) as { phonetic?: string; example?: string };
  } catch {
    return null;
  }
});

async function load() {
  loading.value = true;
  finished.value = false;
  index.value = 0;
  doneCount.value = 0;
  rememberCount.value = 0;
  revealed.value = false;
  try {
    const queue = await fetchReviewQueue();
    items.value = queue.items;
    counts.value = queue.counts;
  } catch {
    items.value = [];
  } finally {
    loading.value = false;
  }
}

async function answer(result: ReviewResult) {
  if (!current.value || submitting.value) return;
  submitting.value = true;
  try {
    const res = await submitReview(current.value.item_type, current.value.item_id, result);
    doneCount.value += 1;
    if (result === 'remember') rememberCount.value += 1;
    if (res.supernova) {
      orbit.pushNotification('超新星复习', res.message || '行星已固化为永久恒星', 'success');
    }
    next();
  } catch (e) {
    orbit.pushNotification('复习', e instanceof Error ? e.message : '提交失败', 'warning');
  } finally {
    submitting.value = false;
  }
}

function next() {
  revealed.value = false;
  if (index.value + 1 >= items.value.length) {
    finished.value = true;
  } else {
    index.value += 1;
  }
}

function skip() {
  if (!current.value) return;
  next();
  doneCount.value += 1;
}

onMounted(load);
</script>

<template>
  <div class="dock-panel space-y-4">
    <header class="space-y-1">
      <p class="lz-caption lz-accent-text uppercase tracking-[0.28em]">Review Queue</p>
      <h3 class="lz-title">今日复习</h3>
      <p class="lz-desc">遗忘曲线调度：衰减星球 · 到期错题 · 词汇卡片，按「记得 / 模糊 / 忘了」自动安排下次复习。</p>
    </header>

    <LzSkeleton v-if="loading" preset="list" :rows="4" />

    <template v-else-if="!items.length">
      <LzEmptyState icon="🌤" title="今天没有待复习项" desc="错题、收藏的单词和衰减星球到期后会出现在这里" />
    </template>

    <template v-else-if="finished">
      <LzCard padding="lg" class="text-center">
        <p class="text-3xl">🎉</p>
        <p class="lz-title mt-2">今日复习完成！</p>
        <p class="lz-desc mt-1">共 {{ doneCount }} 项 · 记得 {{ rememberCount }} 项</p>
        <LzButton variant="primary" class="mt-4" @click="load">再刷一遍队列</LzButton>
      </LzCard>
    </template>

    <template v-else-if="current">
      <div class="flex items-center justify-between gap-2">
        <div class="flex items-center gap-2">
          <LzBadge tone="accent">{{ TYPE_LABEL[current.item_type] || current.item_type }}</LzBadge>
          <span class="lz-caption">{{ doneCount + 1 }} / {{ totalCount }}</span>
        </div>
        <span class="lz-caption">星球 {{ counts.planet }} · 错题 {{ counts.mistake }} · 卡片 {{ counts.card }}</span>
      </div>
      <LzProgress :value="progressPct" />

      <LzCard padding="lg" class="min-h-[160px]">
        <p class="whitespace-pre-wrap text-sm leading-relaxed text-slate-100">{{ current.front }}</p>
        <p v-if="wordExtra?.phonetic" class="lz-caption mt-2">/{{ wordExtra.phonetic }}/</p>

        <template v-if="current.item_type !== 'planet'">
          <div v-if="revealed" class="mt-4 border-t border-white/10 pt-3">
            <p class="whitespace-pre-wrap text-sm text-emerald-200">{{ current.back }}</p>
            <p v-if="wordExtra?.example" class="lz-desc mt-2 italic">{{ wordExtra.example }}</p>
            <p v-if="current.meta?.student_answer" class="lz-caption mt-2">
              当时作答：{{ current.meta.student_answer }}
            </p>
          </div>
          <LzButton v-else variant="soft" block class="mt-4" @click="revealed = true">显示答案</LzButton>
        </template>
        <p v-else class="lz-desc mt-3">
          回忆该知识点的核心内容，自信掌握则选「记得」，复习成功将固化为永久恒星。
        </p>
      </LzCard>

      <div v-if="revealed || current.item_type === 'planet'" class="grid grid-cols-3 gap-2">
        <LzButton variant="danger" :disabled="submitting" @click="answer('forgot')">忘了</LzButton>
        <LzButton variant="soft" :disabled="submitting" @click="answer('fuzzy')">模糊</LzButton>
        <LzButton variant="primary" :disabled="submitting" @click="answer('remember')">记得</LzButton>
      </div>
      <button type="button" class="lz-caption w-full text-center opacity-60 hover:opacity-100" @click="skip">
        跳过这项
      </button>
    </template>
  </div>
</template>

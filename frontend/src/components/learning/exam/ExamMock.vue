<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import {
  fetchMockHistory,
  startMock,
  submitMock,
  type MockHistoryItem,
  type MockPaper,
  type MockResult,
} from '../../../api/exam';
import { useOrbitStore } from '../../../stores/orbit';
import { LzBadge, LzButton, LzCard, LzEmptyState, LzTextarea } from '../ui';

const props = defineProps<{ examType: string }>();
const emit = defineEmits<{ (e: 'activity'): void }>();

const orbit = useOrbitStore();
const SECTION_LABELS: Record<string, string> = {
  listening: '听力',
  reading: '阅读',
  cloze: '选词填空',
  vocab: '词汇',
  translation: '翻译',
  writing: '写作',
};

const paper = ref<MockPaper | null>(null);
const answers = ref<Record<string, string>>({});
const starting = ref(false);
const submitting = ref(false);
const result = ref<MockResult | null>(null);
const history = ref<MockHistoryItem[]>([]);
const remainSeconds = ref(0);
let timer: number | null = null;

const answeredCount = computed(() => Object.values(answers.value).filter((v) => v.trim()).length);
const remainLabel = computed(() => {
  const m = Math.floor(remainSeconds.value / 60);
  const s = remainSeconds.value % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
});

watch(
  () => props.examType,
  () => {
    if (!paper.value) void loadHistory();
  },
);

async function loadHistory() {
  history.value = (await fetchMockHistory().catch(() => [])).filter(
    (h) => h.exam_type === props.examType,
  );
}

async function begin() {
  starting.value = true;
  result.value = null;
  try {
    paper.value = await startMock(props.examType);
    answers.value = {};
    remainSeconds.value = (paper.value.duration_minutes || 60) * 60;
    timer = window.setInterval(() => {
      remainSeconds.value -= 1;
      if (remainSeconds.value <= 0) {
        orbit.pushNotification('全真模考', '时间到，自动交卷', 'warning');
        void submit();
      }
    }, 1000);
  } catch (e) {
    orbit.pushNotification('全真模考', e instanceof Error ? e.message : '组卷失败', 'warning');
  } finally {
    starting.value = false;
  }
}

async function submit() {
  if (!paper.value || submitting.value) return;
  stopTimer();
  submitting.value = true;
  try {
    result.value = await submitMock(paper.value.run_id, answers.value);
    paper.value = null;
    emit('activity');
    if (result.value.mistakes_archived) {
      orbit.pushNotification('错题本', `${result.value.mistakes_archived} 道错题已归档，进入复习队列`, 'info');
    }
    await loadHistory();
  } catch (e) {
    orbit.pushNotification('全真模考', e instanceof Error ? e.message : '交卷失败', 'warning');
  } finally {
    submitting.value = false;
  }
}

function stopTimer() {
  if (timer) {
    window.clearInterval(timer);
    timer = null;
  }
}

function isObjective(section: string) {
  return ['listening', 'reading', 'cloze', 'vocab'].includes(section);
}

function questionsOf(section: string, ids: string[]) {
  const map = new Map((paper.value?.questions ?? []).map((q) => [q.id, q]));
  return ids.map((id) => map.get(id)).filter((q) => q != null);
}

onBeforeUnmount(stopTimer);
void loadHistory();
</script>

<template>
  <div class="space-y-3">
    <!-- 考试中 -->
    <template v-if="paper">
      <div class="sticky top-0 z-10 flex items-center justify-between rounded-xl border border-amber-400/25 bg-[#141021]/95 px-3 py-2 backdrop-blur">
        <span class="lz-subtitle">{{ paper.title }}</span>
        <div class="flex items-center gap-3">
          <span class="lz-caption">已答 {{ answeredCount }} / {{ paper.questions.length }}</span>
          <span class="font-mono-tech text-sm" :class="remainSeconds < 300 ? 'text-rose-300' : 'text-amber-200'">
            ⏱ {{ remainLabel }}
          </span>
        </div>
      </div>

      <section v-for="block in paper.structure" :key="block.section" class="space-y-2">
        <LzBadge tone="accent">{{ SECTION_LABELS[block.section] || block.section }}</LzBadge>
        <LzCard v-for="(q, qi) in questionsOf(block.section, block.question_ids)" :key="q!.id" padding="md">
          <p class="lz-caption mb-1">{{ qi + 1 }}.</p>
          <p class="whitespace-pre-wrap text-sm leading-relaxed text-slate-100">{{ q!.question }}</p>
          <p v-if="q!.audio_text" class="lz-desc mt-2 whitespace-pre-wrap border-t border-white/10 pt-2">
            🎧 {{ q!.audio_text }}
          </p>
          <div v-if="isObjective(q!.section)" class="mt-3 grid gap-1.5">
            <button
              v-for="(text, key) in q!.options"
              :key="key"
              type="button"
              class="flex w-full items-start gap-2 rounded-lg border p-2 text-left text-xs transition"
              :class="answers[q!.id] === key
                ? 'border-sky-400/60 bg-sky-500/15 text-sky-50'
                : 'border-white/10 text-slate-300 hover:border-white/25'"
              @click="answers[q!.id] = String(key)"
            >
              <span class="font-semibold">{{ key }}.</span>
              <span>{{ text }}</span>
            </button>
          </div>
          <LzTextarea
            v-else
            :model-value="answers[q!.id] || ''"
            :rows="4"
            placeholder="在此作答"
            @update:model-value="(v: string) => (answers[q!.id] = v)"
          />
        </LzCard>
      </section>

      <LzButton variant="primary" block :loading="submitting" @click="submit">交卷评分</LzButton>
    </template>

    <!-- 成绩单 -->
    <template v-else-if="result">
      <LzCard padding="lg" class="text-center">
        <p class="lz-caption uppercase tracking-widest">总分</p>
        <p class="mt-1 text-4xl font-semibold" :class="result.score >= 60 ? 'text-emerald-300' : 'text-rose-300'">
          {{ result.score }}
        </p>
        <div class="mt-3 flex flex-wrap justify-center gap-2">
          <LzBadge v-for="(s, sec) in result.section_scores" :key="sec" :tone="s.correct / Math.max(s.total, 1) >= 0.6 ? 'success' : 'warning'">
            {{ SECTION_LABELS[sec] || sec }} {{ s.correct }}/{{ s.total }}
          </LzBadge>
        </div>
      </LzCard>
      <details class="lz-card p-3">
        <summary class="lz-subtitle cursor-pointer">逐题解析（{{ result.detail.length }} 题）</summary>
        <div class="mt-2 max-h-80 space-y-2 overflow-auto">
          <div
            v-for="(d, i) in result.detail"
            :key="d.question_id"
            class="rounded-lg border p-2 text-xs"
            :class="d.correct ? 'border-emerald-400/25' : 'border-rose-400/25'"
          >
            <p class="font-semibold" :class="d.correct ? 'text-emerald-200' : 'text-rose-200'">
              {{ i + 1 }}. {{ d.correct ? '✓' : '✗' }} 我的答案：{{ d.my_answer || '未作答' }} · 参考：{{ d.answer }}
            </p>
            <p v-if="d.analysis" class="lz-desc mt-1 whitespace-pre-wrap">{{ d.analysis }}</p>
          </div>
        </div>
      </details>
      <LzButton variant="primary" block :loading="starting" @click="begin">再考一套</LzButton>
    </template>

    <!-- 入口 -->
    <template v-else>
      <LzEmptyState
        icon="📝"
        title="全真模拟考试"
        desc="听力 5 + 阅读 5 + 选词填空 5 + 翻译 1 + 写作 1，限时 60 分钟，客观题自动判分、主观题 AI 评分"
      >
        <LzButton variant="primary" class="mt-3" :loading="starting" @click="begin">
          {{ starting ? '正在组卷（AI 补题中）…' : '开始模考' }}
        </LzButton>
      </LzEmptyState>

      <template v-if="history.length">
        <p class="lz-caption">历史成绩</p>
        <div class="space-y-1.5">
          <div
            v-for="h in history"
            :key="h.run_id"
            class="flex items-center justify-between rounded-lg border border-white/10 px-3 py-2 text-xs"
          >
            <span class="text-slate-300">{{ h.finished_at ? h.finished_at.slice(0, 16).replace('T', ' ') : '' }}</span>
            <span class="font-mono-tech" :class="h.score >= 60 ? 'text-emerald-300' : 'text-rose-300'">{{ h.score }} 分</span>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

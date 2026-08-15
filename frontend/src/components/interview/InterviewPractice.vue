<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { LzBadge, LzButton, LzSkeleton, LzTextarea } from '../learning/ui';
import VoiceInputButton from '../common/VoiceInputButton.vue';
import InterviewScoreRing from './InterviewScoreRing.vue';
import { parseApiError } from '../../api/errors';
import {
  fetchInterviewRoles,
  fetchPracticeHistory,
  fetchPracticeQuestion,
  submitPracticeAnswer,
  type InterviewJobRole,
  type InterviewPracticeAnswer,
  type InterviewPracticeQuestion,
  type InterviewPracticeRecord,
} from '../../api/interview';

const props = defineProps<{
  seedQuestion?: InterviewPracticeQuestion | null;
}>();

const KINDS_JOB = [
  { key: '', label: '随机' },
  { key: 'tech', label: '技术基础' },
  { key: 'project', label: '项目经验' },
  { key: 'business', label: '业务理解' },
  { key: 'soft', label: '软技能' },
];
const KINDS_ACADEMIC = [
  { key: '', label: '随机' },
  { key: 'subject', label: '学科深挖' },
  { key: 'method', label: '方法与推导' },
  { key: 'research', label: '科研潜质' },
  { key: 'comprehensive', label: '综合素质' },
];

const STAR_LABEL: Record<string, string> = {
  situation: 'S 情境',
  task: 'T 任务',
  action: 'A 行动',
  result: 'R 结果',
};

const scenario = ref<'job' | 'academic'>('job');
const roles = ref<InterviewJobRole[]>([]);
const jobRole = ref('backend');
const kind = ref('');
const question = ref<InterviewPracticeQuestion | null>(null);
const answer = ref('');
const drawing = ref(false);
const scoring = ref(false);
const result = ref<InterviewPracticeAnswer | null>(null);
const history = ref<InterviewPracticeRecord[]>([]);
const error = ref('');

const filteredRoles = computed(() => roles.value.filter((r) => r.scenario === scenario.value));
const kindOptions = computed(() => (scenario.value === 'academic' ? KINDS_ACADEMIC : KINDS_JOB));
const avgScore = computed(() => {
  const scores = history.value.map((h) => h.score).filter((s): s is number => s != null);
  if (!scores.length) return null;
  return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
});

function onScenarioChange(next: 'job' | 'academic') {
  scenario.value = next;
  kind.value = '';
  const first = filteredRoles.value[0];
  if (first) jobRole.value = first.key;
}

async function loadHistory() {
  try {
    history.value = await fetchPracticeHistory();
  } catch {
    history.value = [];
  }
}

onMounted(async () => {
  try {
    roles.value = await fetchInterviewRoles();
    const first = filteredRoles.value[0];
    if (first) jobRole.value = first.key;
  } catch (err) {
    error.value = parseApiError(err, '岗位模板加载失败');
  }
  void loadHistory();
  applySeed(props.seedQuestion);
});

watch(
  () => props.seedQuestion,
  (next) => applySeed(next),
);

function applySeed(seed?: InterviewPracticeQuestion | null) {
  if (!seed?.question) return;
  scenario.value = seed.scenario === 'academic' ? 'academic' : 'job';
  if (seed.job_role) jobRole.value = seed.job_role;
  kind.value = seed.kind || '';
  question.value = seed;
  result.value = null;
  answer.value = '';
}

async function draw() {
  drawing.value = true;
  error.value = '';
  result.value = null;
  answer.value = '';
  try {
    question.value = await fetchPracticeQuestion({
      scenario: scenario.value,
      job_role: jobRole.value,
      kind: kind.value,
    });
  } catch (err) {
    error.value = parseApiError(err, '出题失败');
  } finally {
    drawing.value = false;
  }
}

async function submit() {
  if (!question.value || !answer.value.trim()) return;
  scoring.value = true;
  error.value = '';
  try {
    result.value = await submitPracticeAnswer({
      scenario: scenario.value,
      job_role: jobRole.value,
      kind: question.value.kind,
      question: question.value.question,
      transcript: answer.value.trim(),
    });
    void loadHistory();
  } catch (err) {
    error.value = parseApiError(err, '评分失败');
  } finally {
    scoring.value = false;
  }
}

function onVoiceText(text: string, final: boolean) {
  if (final) answer.value = answer.value ? `${answer.value} ${text}` : text;
}

function nextQuestion() {
  void draw();
}
</script>

<template>
  <div class="space-y-4">
  <div class="pc-deck">
    <aside class="pc-rail">
      <p class="lz-hud-label">Studio // 快练</p>
      <div class="mt-3 grid grid-cols-2 gap-2">
        <button
          type="button"
          class="lz-hud-card lz-hud-card--hover p-3 text-left"
          :class="scenario === 'job' ? 'is-picked' : ''"
          @click="onScenarioChange('job')"
        >
          <p class="lz-hud-label">Job</p>
          <p class="mt-1 text-sm text-slate-100">求职</p>
        </button>
        <button
          type="button"
          class="lz-hud-card lz-hud-card--hover p-3 text-left"
          :class="scenario === 'academic' ? 'is-picked' : ''"
          @click="onScenarioChange('academic')"
        >
          <p class="lz-hud-label">Academic</p>
          <p class="mt-1 text-sm text-slate-100">升学</p>
        </button>
      </div>
      <div class="mt-3 space-y-1.5">
        <button
          v-for="role in filteredRoles"
          :key="role.key"
          type="button"
          class="lz-hud-card lz-hud-card--hover w-full p-3 text-left"
          :class="jobRole === role.key ? 'is-picked' : ''"
          @click="jobRole = role.key"
        >
          <p class="text-sm text-slate-100">{{ role.label }}</p>
          <p class="mt-0.5 line-clamp-2 text-[11px] text-slate-500">{{ role.description }}</p>
        </button>
      </div>
      <div class="mt-3 flex flex-wrap gap-1.5">
        <button
          v-for="k in kindOptions"
          :key="k.key"
          type="button"
          class="rounded-full px-2.5 py-1 text-[11px]"
          :class="kind === k.key ? 'bg-amber-400/20 text-amber-100' : 'text-slate-500 hover:text-slate-300'"
          @click="kind = k.key"
        >
          {{ k.label }}
        </button>
      </div>
    </aside>

    <div class="min-w-0 space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <p class="text-[11px] text-slate-500">
          单题快练，不开摄像头、不生成完整报告。全流程请去面试舱。
        </p>
        <LzButton variant="primary" size="sm" :loading="drawing" @click="draw">
          {{ question ? '换一题' : '抽一题' }}
        </LzButton>
      </div>

      <div v-if="drawing" class="p-2"><LzSkeleton preset="card" /></div>

      <template v-else-if="question">
        <div class="lz-hud-card p-4">
          <p class="lz-hud-label">{{ question.job_role_label }} · {{ question.kind_label }}</p>
          <p class="mt-2 text-base leading-relaxed text-slate-100">{{ question.question }}</p>
        </div>

        <div class="space-y-2">
          <LzTextarea
            v-model="answer"
            :rows="5"
            placeholder="口头组织好再写下来，或用语音输入。建议按 STAR：情境 → 任务 → 行动 → 结果。"
          />
          <div class="flex flex-wrap items-center gap-2">
            <VoiceInputButton label="语音作答" @text="onVoiceText" />
            <LzButton variant="primary" size="sm" :loading="scoring" :disabled="!answer.trim() || scoring" @click="submit">
              提交评分
            </LzButton>
          </div>
        </div>
      </template>

      <div v-else class="lz-hud-card border-dashed p-8 text-center text-sm text-slate-500">
        选好岗位与题类，点「抽一题」开始快练
      </div>

      <div v-if="result" class="flex flex-wrap items-start gap-4 lz-hud-card p-4">
        <InterviewScoreRing :score="result.score" :size="88" />
        <div class="min-w-0 flex-1 space-y-2">
          <div class="flex flex-wrap gap-1.5">
            <LzBadge
              v-for="(hit, key) in result.star_hit"
              :key="key"
              :tone="hit ? 'success' : 'neutral'"
            >
              {{ STAR_LABEL[key] || key }} {{ hit ? '✓' : '✗' }}
            </LzBadge>
          </div>
          <p class="text-sm leading-relaxed text-slate-200">{{ result.feedback }}</p>
          <ul v-if="result.reasons.length" class="space-y-0.5 text-xs text-slate-500">
            <li v-for="r in result.reasons" :key="r">· {{ r }}</li>
          </ul>
          <LzButton variant="soft" size="sm" @click="nextQuestion">再来一题</LzButton>
        </div>
      </div>

      <p v-if="error" class="text-xs text-rose-300">{{ error }}</p>
    </div>
  </div>

  <section v-if="history.length" class="lz-hud-card p-4">
    <div class="mb-3 flex items-center justify-between">
      <h4 class="text-sm text-amber-100">最近练习</h4>
      <span v-if="avgScore != null" class="text-xs text-slate-500">近 {{ history.length }} 题均分 <span class="text-amber-200">{{ avgScore }}</span></span>
    </div>
    <ul class="space-y-2">
      <li
        v-for="item in history.slice(0, 8)"
        :key="item.id"
        class="flex items-center gap-3 rounded-xl border border-white/10 px-3 py-2"
      >
        <span class="font-mono-tech w-8 shrink-0 text-center text-sm" :class="(item.score ?? 0) >= 70 ? 'text-emerald-300' : 'text-rose-300'">
          {{ item.score != null ? Math.round(item.score) : '—' }}
        </span>
        <div class="min-w-0 flex-1">
          <p class="truncate text-xs text-slate-200">{{ item.question }}</p>
          <p class="text-[10px] text-slate-500">{{ item.job_role_label }} · {{ item.kind_label }}</p>
        </div>
      </li>
    </ul>
  </section>
  </div>
</template>

<style scoped>
.pc-deck {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.pc-rail {
  position: sticky;
  top: 0;
}
.pc-deck .is-picked {
  box-shadow: inset 0 0 0 1px rgb(var(--lz-accent) / 0.45), 0 0 22px -12px rgb(var(--lz-accent) / 0.5);
}
@media (max-width: 800px) {
  .pc-deck {
    grid-template-columns: 1fr;
  }
  .pc-rail {
    position: static;
  }
}
</style>

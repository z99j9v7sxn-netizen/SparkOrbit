<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import ZoneHeader from '../common/ZoneHeader.vue';
import { LzBadge, LzTabs, type LzTabItem } from '../learning/ui';
import InterviewSetup from './InterviewSetup.vue';
import InterviewStage from './InterviewStage.vue';
import InterviewReport from './InterviewReport.vue';
import InterviewPortrait from './InterviewPortrait.vue';
import InterviewPractice from './InterviewPractice.vue';
import InterviewScoreRing from './InterviewScoreRing.vue';
import InterviewScoreGauge from './InterviewScoreGauge.vue';
import CareerHub from './career/CareerHub.vue';
import {
  deleteInterviewSession,
  fetchInterviewPortrait,
  fetchInterviewSessions,
  fetchInterviewTasks,
  type InterviewPortrait as PortraitData,
  type InterviewPracticeQuestion,
  type InterviewSessionBrief,
  type InterviewTask,
} from '../../api/interview';
import { parseApiError } from '../../api/errors';
import { relativeTime } from '../../utils/relativeTime';
import { useOrbitStore } from '../../stores/orbit';

type CabinPreset = {
  scenario?: 'job' | 'academic';
  job_role?: string;
  difficulty?: string;
  question_count?: number;
};

const TABS: LzTabItem[] = [
  { key: 'cabin', label: '面试舱' },
  { key: 'practice', label: '练习舱' },
  { key: 'career', label: '求职助手' },
  { key: 'portrait', label: '能力画像' },
  { key: 'tasks', label: '我的任务' },
  { key: 'history', label: '我的报告' },
];

const tab = ref('cabin');
const view = ref<'setup' | 'live' | 'report'>('setup');
const activeSessionId = ref('');
const history = ref<InterviewSessionBrief[]>([]);
const tasks = ref<InterviewTask[]>([]);
const portraitBrief = ref<PortraitData | null>(null);
const taskAssignmentId = ref('');
const taskPreset = ref<CabinPreset | null>(null);
const practiceSeed = ref<InterviewPracticeQuestion | null>(null);
const actionError = ref('');
const orbit = useOrbitStore();

const pendingTasks = computed(() => tasks.value.filter((t) => t.my_status !== 'graded'));
const pendingTaskCount = computed(() => pendingTasks.value.length);
const firstPendingTask = computed(() => pendingTasks.value[0] || null);

const scoreScenario = computed(() => {
  const p = portraitBrief.value;
  if (!p) return null;
  if (p.job.count > 0) return p.job;
  if (p.academic.count > 0) return p.academic;
  return p.job;
});

const scoreDims = computed(() => {
  const block = scoreScenario.value;
  if (!block) return [];
  const labels = block.dimension_labels || {};
  const avg = block.dimension_avg || {};
  const keys = Object.keys(avg).length ? Object.keys(avg) : Object.keys(labels);
  return keys
    .map((key) => ({
      key,
      label: labels[key] || key,
      value: Math.round(Number(avg[key] ?? 0)),
    }))
    .sort((a, b) => b.value - a.value);
});

const sessionSubline = computed(() => {
  const latest = portraitBrief.value?.latest;
  if (!latest) return '尚无记录 · 去面试舱开一场';
  const role = latest.job_role_label || (latest.scenario === 'academic' ? '升学舱' : '求职舱');
  return `${role} · ${relativeTime(latest.created_at)}`;
});

const taskSubline = computed(() => firstPendingTask.value?.title || '暂无教师任务');

const AMBIENT: Record<string, [string, string]> = {
  cabin: ['rgba(245, 158, 11, 0.16)', 'rgba(251, 191, 36, 0.10)'],
  practice: ['rgba(252, 211, 77, 0.14)', 'rgba(245, 158, 11, 0.08)'],
  career: ['rgba(249, 115, 22, 0.14)', 'rgba(245, 158, 11, 0.10)'],
  portrait: ['rgba(245, 158, 11, 0.14)', 'rgba(56, 189, 248, 0.10)'],
  tasks: ['rgba(245, 158, 11, 0.12)', 'rgba(251, 191, 36, 0.08)'],
  history: ['rgba(245, 158, 11, 0.12)', 'rgba(148, 163, 184, 0.08)'],
};

const ambientStyle = computed(() => {
  const pair = AMBIENT[tab.value] || AMBIENT.cabin;
  return {
    background: `radial-gradient(ellipse 55% 42% at 22% 0%, ${pair[0]}, transparent 60%), radial-gradient(ellipse 45% 38% at 85% 12%, ${pair[1]}, transparent 58%)`,
  };
});

async function refresh() {
  try {
    history.value = await fetchInterviewSessions();
  } catch {
    history.value = [];
  }
  try {
    tasks.value = await fetchInterviewTasks();
  } catch {
    tasks.value = [];
  }
  try {
    portraitBrief.value = await fetchInterviewPortrait();
  } catch {
    portraitBrief.value = null;
  }
}

onMounted(refresh);

function onReady(sessionId: string) {
  activeSessionId.value = sessionId;
  view.value = 'live';
}

function onFinished(payload: { reportId: string; overallScore: number | null }) {
  view.value = 'report';
  void refresh();
  const score = payload.overallScore;
  orbit.pushNotification(
    '模拟面试',
    score != null ? `报告已生成，综合 ${score} 分` : '报告已生成，可回看能力画像',
    'success',
  );
}

function openHistory(id: string) {
  activeSessionId.value = id;
  tab.value = 'history';
}

function startTask(task: InterviewTask) {
  taskAssignmentId.value = task.assignment_id;
  taskPreset.value = {
    scenario: task.scenario as 'job' | 'academic',
    job_role: task.job_role,
    difficulty: task.difficulty,
    question_count: task.question_count,
  };
  tab.value = 'cabin';
  view.value = 'setup';
}

function openCabin() {
  tab.value = 'cabin';
  view.value = 'setup';
}

function openCabinFromCareer(payload: { job_role?: string }) {
  taskAssignmentId.value = '';
  taskPreset.value = payload.job_role ? { scenario: 'job', job_role: payload.job_role } : null;
  tab.value = 'cabin';
  view.value = 'setup';
}

function openPracticeFromCareer(payload: InterviewPracticeQuestion) {
  practiceSeed.value = payload;
  tab.value = 'practice';
}

function retryWeak(payload: { scenario: 'job' | 'academic'; job_role?: string }) {
  taskAssignmentId.value = '';
  taskPreset.value = {
    scenario: payload.scenario,
    job_role: payload.job_role,
  };
  tab.value = 'cabin';
  view.value = 'setup';
}

function resetCabin() {
  view.value = 'setup';
  taskAssignmentId.value = '';
  taskPreset.value = null;
}

async function removeSession(id: string) {
  actionError.value = '';
  try {
    await deleteInterviewSession(id);
    if (activeSessionId.value === id) activeSessionId.value = '';
    await refresh();
  } catch (err) {
    actionError.value = parseApiError(err, '删除失败');
  }
}

function statusBadge(status: string): { label: string; tone: 'accent' | 'neutral' | 'success' | 'warning' | 'danger' } {
  if (status === 'completed') return { label: '已完成', tone: 'success' };
  if (status === 'failed') return { label: '失败', tone: 'danger' };
  if (status === 'running' || status === 'scoring') return { label: '进行中', tone: 'warning' };
  return { label: '准备中', tone: 'neutral' };
}
</script>

<template>
  <div class="lz-accent-amber absolute inset-0 overflow-auto px-4 pb-24 pt-20">
    <Transition name="iv-ambient">
      <div :key="tab" class="pointer-events-none fixed inset-0" :style="ambientStyle" aria-hidden="true"></div>
    </Transition>
    <div class="relative mx-auto max-w-6xl space-y-5">
      <ZoneHeader
        eyebrow="Mock Interview // Audition Deck"
        title="模拟面试区 · 多模态评测舱"
        desc="求职准备到模拟面试：校招官网、简历工坊、数字人评测与能力画像"
      />

      <div class="lz-bento">
        <button
          type="button"
          class="lz-hud-card lz-hud-card--hover lz-shine col-span-2 p-5 text-left lg:col-span-4 lg:row-span-2"
          @click="tab = 'portrait'"
        >
          <p class="lz-hud-label">Score // 综合均分</p>
          <div class="mt-3 grid gap-4 sm:grid-cols-[9.5rem_minmax(0,1fr)] sm:items-center">
            <InterviewScoreGauge :score="portraitBrief?.avg_score" :size="152" />
            <ul v-if="scoreDims.length" class="iv-hair min-w-0 space-y-2">
              <li v-for="dim in scoreDims" :key="dim.key" class="iv-hair__row">
                <span class="iv-hair__name">{{ dim.label }}</span>
                <span class="iv-hair__track" aria-hidden="true">
                  <span class="iv-hair__fill" :style="{ width: `${dim.value}%` }" />
                </span>
                <span class="iv-hair__val">{{ dim.value }}</span>
              </li>
            </ul>
            <p v-else class="text-xs leading-relaxed text-slate-500">
              {{ portraitBrief?.latest?.job_role_label || '尚无记录 · 去面试舱开一场' }}
            </p>
          </div>
        </button>
        <button
          type="button"
          class="lz-hud-card lz-hud-card--hover col-span-1 p-4 text-left lg:col-span-2"
          @click="tab = 'history'"
        >
          <p class="lz-hud-label">Sessions</p>
          <p class="mt-3 font-mono-tech text-2xl text-amber-200">{{ portraitBrief?.session_count ?? 0 }}</p>
          <p class="mt-1 truncate text-[11px] text-slate-500">{{ sessionSubline }}</p>
        </button>
        <button
          type="button"
          class="lz-hud-card lz-hud-card--hover col-span-1 p-4 text-left lg:col-span-2"
          @click="tab = 'tasks'"
        >
          <p class="lz-hud-label">Tasks</p>
          <p class="mt-3 font-mono-tech text-2xl text-amber-200">{{ pendingTaskCount }}</p>
          <p class="mt-1 truncate text-[11px] text-slate-500">{{ taskSubline }}</p>
        </button>
      </div>

      <LzTabs :items="TABS" :model-value="tab" @update:model-value="tab = $event" />
      <p v-if="actionError" class="text-xs text-rose-300">{{ actionError }}</p>

      <div v-if="tab === 'cabin'">
        <InterviewSetup
          v-if="view === 'setup'"
          :key="`${taskAssignmentId}-${taskPreset?.scenario || ''}-${taskPreset?.job_role || ''}`"
          :assignment-id="taskAssignmentId"
          :preset="taskPreset || undefined"
          @ready="onReady"
        />
        <InterviewStage v-else-if="view === 'live'" :session-id="activeSessionId" @finished="onFinished" />
        <div v-else class="space-y-4">
          <button class="text-xs text-amber-200/80" type="button" @click="resetCabin">← 再开一场</button>
          <InterviewReport :session-id="activeSessionId" />
        </div>
      </div>

      <div v-else-if="tab === 'practice'">
        <InterviewPractice :seed-question="practiceSeed" />
      </div>

      <div v-else-if="tab === 'career'">
        <CareerHub @practice="openPracticeFromCareer" @open-cabin="openCabinFromCareer" />
      </div>

      <div v-else-if="tab === 'portrait'" class="space-y-3">
        <InterviewPortrait
          @open-cabin="openCabin"
          @open-session="openHistory"
          @retry="retryWeak"
        />
      </div>

      <div v-else-if="tab === 'tasks'" class="space-y-3">
        <button
          v-for="task in tasks"
          :key="task.assignment_id"
          type="button"
          class="lz-card flex w-full items-center justify-between gap-3 p-4 text-left"
          @click="startTask(task)"
        >
          <div class="min-w-0">
            <p class="truncate text-sm text-slate-100">{{ task.title }}</p>
            <p class="mt-0.5 text-xs text-slate-500">
              {{ task.scenario === 'academic' ? '升学舱' : '求职舱' }} · {{ task.difficulty }} · {{ task.question_count }} 题
              <span v-if="task.stem"> · {{ task.stem }}</span>
            </p>
          </div>
          <LzBadge :tone="task.my_status === 'graded' ? 'success' : 'warning'">
            {{ task.my_status === 'graded' ? (task.my_score ?? '已评') : '待完成' }}
          </LzBadge>
        </button>
        <p v-if="!tasks.length" class="lz-card p-6 text-center text-sm text-slate-500">暂无教师下发的面试任务</p>
      </div>

      <div v-else class="space-y-4">
        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <article
            v-for="item in history"
            :key="item.id"
            class="iv-history-card lz-card relative p-4"
            :class="activeSessionId === item.id ? 'ring-1 ring-amber-400/60' : ''"
          >
            <button type="button" class="flex w-full items-center gap-3 text-left" @click="openHistory(item.id)">
              <InterviewScoreRing :score="item.overall_score" :size="56" :show-grade="false" />
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm text-slate-100">{{ item.job_role_label }}</p>
                <p class="mt-0.5 text-xs text-slate-500">
                  {{ item.scenario === 'academic' ? '升学舱' : '求职舱' }} · {{ relativeTime(item.created_at) }}
                </p>
                <LzBadge class="mt-1.5" :tone="statusBadge(item.status).tone">{{ statusBadge(item.status).label }}</LzBadge>
              </div>
            </button>
            <button
              type="button"
              class="absolute right-3 top-3 text-xs text-slate-600 transition hover:text-rose-300"
              title="删除会话"
              @click.stop="removeSession(item.id)"
            >
              ✕
            </button>
          </article>
        </div>
        <p v-if="!history.length" class="lz-card p-6 text-center text-sm text-slate-500">
          还没有面试记录，去面试舱开一场吧
        </p>
        <InterviewReport v-if="activeSessionId && tab === 'history'" :session-id="activeSessionId" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.iv-ambient-enter-active,
.iv-ambient-leave-active {
  transition: opacity 0.55s ease;
}
.iv-ambient-enter-from,
.iv-ambient-leave-to {
  opacity: 0;
}

.iv-history-card {
  transition: transform 0.16s ease;
}

.iv-history-card:hover {
  transform: translateY(-2px);
}

.iv-hair__row {
  display: grid;
  grid-template-columns: 4.5rem minmax(0, 1fr) 1.75rem;
  align-items: center;
  gap: 0.5rem;
}
.iv-hair__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  color: #94a3b8;
}
.iv-hair__track {
  display: block;
  height: 1px;
  background: rgba(148, 163, 184, 0.22);
}
.iv-hair__fill {
  display: block;
  height: 1px;
  background: linear-gradient(90deg, #f59e0b, #fb923c);
  transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}
.iv-hair__val {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 11px;
  text-align: right;
  color: #fde68a;
}

@media (prefers-reduced-motion: reduce) {
  .iv-ambient-enter-active,
  .iv-ambient-leave-active {
    transition: none;
  }
  .iv-hair__fill {
    transition: none;
  }
}
</style>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { LzBadge, LzButton, LzInput } from '../learning/ui';
import { parseApiError } from '../../api/errors';
import {
  consumeInterviewPrepStream,
  createInterviewSession,
  fetchInterviewRoles,
  fetchInterviewSession,
  uploadInterviewResume,
  type InterviewJobRole,
  type InterviewPrepIntel,
  type InterviewStreamEvent,
} from '../../api/interview';

const props = defineProps<{
  assignmentId?: string;
  preset?: {
    scenario?: 'job' | 'academic';
    job_role?: string;
    difficulty?: string;
    question_count?: number;
  };
}>();

const emit = defineEmits<{
  (e: 'ready', sessionId: string): void;
}>();

const FAMILY_ICON: Record<string, string> = {
  tech: '⌘',
  biz: '◈',
  grad: '✦',
  admissions: '❖',
};

const STEPS = [
  { n: '01', label: '选择舱位' },
  { n: '02', label: '配置与授权' },
  { n: '03', label: '智能编排' },
];

const DIFFS = [
  { key: 'easy', label: '入门', hint: '弱光校准' },
  { key: 'medium', label: '标准', hint: '常亮金边' },
  { key: 'hard', label: '加压', hint: '高压脉冲' },
];

const step = ref(1);
const scenario = ref<'job' | 'academic'>('job');
const roles = ref<InterviewJobRole[]>([]);
const jobRole = ref('backend');
const difficulty = ref('medium');
const questionCount = ref(4);
const consent = ref(true);
const resumeUrl = ref('');
const resumeProfile = ref<Record<string, unknown>>({});
const resumePreview = ref('');
const resumeName = ref('');
const uploading = ref(false);
const dragging = ref(false);
const starting = ref(false);
const error = ref('');
const prepStatus = ref('');
const prepared = ref(false);
const preparedSessionId = ref('');
const intel = ref<InterviewPrepIntel | null>(null);

type NodeStatus = 'pending' | 'running' | 'done';
const agentNodes = ref<Array<{ role: string; label: string; group: number; status: NodeStatus; note: string }>>([]);

const filteredRoles = computed(() => roles.value.filter((r) => r.scenario === scenario.value));
const selectedRole = computed(() => roles.value.find((r) => r.key === jobRole.value));
const lineHeight = computed(() => `${Math.max(0, (step.value - 1) / 2) * 100}%`);

function goToStep(n: number) {
  if (n < step.value) step.value = n;
}

function buildAgentNodes() {
  const kinds =
    scenario.value === 'academic'
      ? [
          { key: 'subject', label: '学科深挖' },
          { key: 'method', label: '方法与推导' },
          { key: 'research', label: '科研潜质' },
          { key: 'comprehensive', label: '综合素质' },
        ]
      : [
          { key: 'tech', label: '技术基础' },
          { key: 'project', label: '项目经验' },
          { key: 'business', label: '业务理解' },
          { key: 'soft', label: '软技能' },
        ];
  agentNodes.value = [
    { role: 'JobAnalyst', label: '岗位分析官', group: 1, status: 'pending', note: '' },
    { role: 'ProfileParser', label: '候选人画像官', group: 1, status: 'pending', note: '' },
    { role: 'QuestionPlanner', label: '题目规划官', group: 2, status: 'pending', note: '' },
    ...kinds.map((k) => ({ role: `Q-${k.key}`, label: `出题官 · ${k.label}`, group: 3, status: 'pending' as NodeStatus, note: '' })),
  ];
}

function markNode(role: string, status: NodeStatus, note = '') {
  const node = agentNodes.value.find((n) => n.role === role);
  if (!node) return;
  node.status = status;
  if (note) node.note = note;
}

function onPrepEvent(event: InterviewStreamEvent) {
  prepStatus.value = event.content;
  if (event.type === 'start') {
    markNode('JobAnalyst', 'running');
    markNode('ProfileParser', 'running');
    return;
  }
  if (event.type === 'note' || event.type === 'question') {
    markNode(event.role, 'done', event.content);
    if (event.role === 'ProfileParser' || event.role === 'JobAnalyst') {
      const group1Done = agentNodes.value.filter((n) => n.group === 1).every((n) => n.status === 'done');
      if (group1Done) markNode('QuestionPlanner', 'running');
    }
    if (event.role === 'QuestionPlanner') {
      for (const node of agentNodes.value.filter((n) => n.group === 3)) node.status = 'running';
    }
  }
}

function applyPreset() {
  const preset = props.preset;
  if (!preset) return;
  if (preset.scenario) scenario.value = preset.scenario;
  if (preset.difficulty) difficulty.value = preset.difficulty;
  if (preset.question_count) questionCount.value = preset.question_count;
  if (preset.job_role) jobRole.value = preset.job_role;
}

onMounted(async () => {
  applyPreset();
  try {
    roles.value = await fetchInterviewRoles();
    if (props.preset?.job_role) jobRole.value = props.preset.job_role;
    else {
      const first = filteredRoles.value[0];
      if (first) jobRole.value = first.key;
    }
  } catch (err) {
    error.value = parseApiError(err, '岗位模板加载失败');
  }
});

watch(
  () => props.preset,
  () => {
    applyPreset();
    if (props.preset?.job_role) jobRole.value = props.preset.job_role;
    else {
      const first = filteredRoles.value[0];
      if (first) jobRole.value = first.key;
    }
  },
  { deep: true },
);

function onScenarioChange(next: 'job' | 'academic') {
  scenario.value = next;
  const first = filteredRoles.value[0];
  if (first) jobRole.value = first.key;
}

async function ingestResume(file: File) {
  uploading.value = true;
  error.value = '';
  try {
    const result = await uploadInterviewResume(file);
    resumeUrl.value = result.url;
    resumeProfile.value = result.profile;
    resumePreview.value = result.text_preview;
    resumeName.value = file.name;
  } catch (err) {
    error.value = parseApiError(err, '简历解析失败');
  } finally {
    uploading.value = false;
  }
}

async function onPickResume(ev: Event) {
  const input = ev.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  await ingestResume(file);
  input.value = '';
}

function onDrop(ev: DragEvent) {
  ev.preventDefault();
  dragging.value = false;
  const file = ev.dataTransfer?.files?.[0];
  if (file) void ingestResume(file);
}

async function startInterview() {
  if (!consent.value) {
    error.value = '请先确认采集授权后再开始';
    return;
  }
  starting.value = true;
  error.value = '';
  prepared.value = false;
  intel.value = null;
  step.value = 3;
  buildAgentNodes();
  try {
    const session = await createInterviewSession({
      scenario: scenario.value,
      job_role: jobRole.value,
      difficulty: difficulty.value,
      question_count: questionCount.value,
      resume_url: resumeUrl.value,
      resume_profile: resumeProfile.value,
      assignment_id: props.assignmentId || '',
      consent: true,
    });
    preparedSessionId.value = session.id;
    prepStatus.value = '正在并行出题…';
    await consumeInterviewPrepStream(session.id, onPrepEvent);
    for (const node of agentNodes.value) node.status = 'done';
    try {
      const detail = await fetchInterviewSession(session.id);
      intel.value = detail.prep_intel || null;
    } catch {
      intel.value = null;
    }
    prepared.value = true;
    prepStatus.value = '题目已就绪';
  } catch (err) {
    error.value = parseApiError(err, '创建面试失败');
    step.value = 2;
  } finally {
    starting.value = false;
  }
}

function enterInterview() {
  if (preparedSessionId.value) emit('ready', preparedSessionId.value);
}

const hasIntel = computed(() => {
  const i = intel.value;
  return Boolean(i && (i.job?.summary || (i.job?.skills || []).length || (i.topics || []).length));
});
</script>

<template>
  <div class="iv-deck">
    <aside class="iv-slate">
      <p class="lz-hud-label">Slate // 片场</p>
      <p class="iv-role-title">{{ selectedRole?.label || '选择舱位' }}</p>
      <p class="mt-1 text-[11px] text-slate-500">{{ scenario === 'academic' ? '升学舱 · 复试/综评' : '求职舱 · 校招/实习' }}</p>

      <div class="iv-steps">
        <span class="iv-steps__track" aria-hidden="true">
          <i class="iv-steps__fill" :style="{ height: lineHeight }"></i>
        </span>
        <button
          v-for="(item, idx) in STEPS"
          :key="item.n"
          type="button"
          class="iv-step"
          :class="{
            'is-now': step === idx + 1,
            'is-done': step > idx + 1,
          }"
          :disabled="idx + 1 > step"
          @click="goToStep(idx + 1)"
        >
          <span class="iv-step__n">{{ item.n }}</span>
          <span class="iv-step__l">{{ item.label }}</span>
        </button>
      </div>

      <label v-if="step === 2" class="iv-gate">
        <input v-model="consent" type="checkbox" />
        <span>采集麦克风与摄像头关键帧用于转写评分，媒体 30 天后清理。未勾选不能开机。</span>
      </label>
    </aside>

    <div class="iv-stage">
      <Transition name="zone-swap" mode="out-in">
        <div :key="step" class="space-y-4">
          <template v-if="step === 1">
            <div class="grid gap-3 sm:grid-cols-2">
              <button
                type="button"
                class="lz-hud-card lz-hud-card--hover lz-shine p-4 text-left"
                :class="scenario === 'job' ? 'is-picked' : ''"
                @click="onScenarioChange('job')"
              >
                <p class="lz-hud-label">Job</p>
                <p class="mt-2 text-sm text-slate-100">求职舱</p>
                <p class="mt-1 text-[11px] text-slate-500">校招 / 实习</p>
              </button>
              <button
                type="button"
                class="lz-hud-card lz-hud-card--hover lz-shine p-4 text-left"
                :class="scenario === 'academic' ? 'is-picked' : ''"
                @click="onScenarioChange('academic')"
              >
                <p class="lz-hud-label">Academic</p>
                <p class="mt-2 text-sm text-slate-100">升学舱</p>
                <p class="mt-1 text-[11px] text-slate-500">复试 / 综评</p>
              </button>
            </div>
            <div class="grid gap-3 sm:grid-cols-2">
              <button
                v-for="role in filteredRoles"
                :key="role.key"
                type="button"
                class="lz-hud-card lz-hud-card--hover lz-shine flex items-start gap-3 p-4 text-left"
                :class="jobRole === role.key ? 'is-picked' : ''"
                @click="jobRole = role.key"
              >
                <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-amber-400/25 bg-amber-400/10 text-base text-amber-200">
                  {{ FAMILY_ICON[role.family] || '◇' }}
                </span>
                <span class="min-w-0">
                  <span class="block text-sm text-slate-100">{{ role.label }}</span>
                  <span class="mt-1 block text-xs leading-relaxed text-slate-400">{{ role.description }}</span>
                </span>
              </button>
            </div>
            <LzButton variant="primary" @click="step = 2">下一步：配置面试</LzButton>
          </template>

          <template v-else-if="step === 2">
            <p class="lz-hud-label">Voltage // 难度</p>
            <div class="grid grid-cols-3 gap-2">
              <button
                v-for="d in DIFFS"
                :key="d.key"
                type="button"
                class="iv-volt"
                :class="[`iv-volt--${d.key}`, difficulty === d.key ? 'is-on' : '']"
                @click="difficulty = d.key"
              >
                <span v-if="d.key === 'hard'" class="lz-pulse-dot" />
                <span class="iv-volt__label">{{ d.label }}</span>
                <span class="iv-volt__hint">{{ d.hint }}</span>
              </button>
            </div>
            <label class="block text-xs text-slate-400">
              轮数（2–8）
              <LzInput
                class="mt-1"
                :model-value="String(questionCount)"
                @update:model-value="questionCount = Math.min(8, Math.max(2, Number($event) || 4))"
              />
            </label>
            <div
              class="iv-drop"
              :class="{ 'is-drag': dragging, 'lz-edge-glow': dragging }"
              @dragover.prevent="dragging = true"
              @dragleave="dragging = false"
              @drop="onDrop"
            >
              <p class="lz-hud-label">Resume // 可选</p>
              <p class="mt-2 text-xs text-slate-400">拖入或点选 PDF / Word / TXT，用于定制出题</p>
              <label class="iv-file-btn">
                {{ uploading ? '解析中…' : '选择文件' }}
                <input class="hidden" type="file" accept=".pdf,.docx,.txt" :disabled="uploading" @change="onPickResume" />
              </label>
              <p v-if="resumeName" class="mt-2 truncate text-[11px] text-amber-200/80">{{ resumeName }}</p>
              <p v-else-if="uploading" class="mt-2 text-[11px] text-amber-200">正在解析简历…</p>
            </div>
            <p v-if="resumePreview" class="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs text-slate-400">
              已解析：{{ resumePreview }}
            </p>
            <div class="flex gap-2">
              <LzButton variant="ghost" @click="step = 1">上一步</LzButton>
              <LzButton variant="primary" :loading="starting" :disabled="starting || !consent" @click="startInterview">
                启动智能编排
              </LzButton>
            </div>
          </template>

          <template v-else>
            <div class="lz-hud-card p-4">
              <div class="mb-3 flex items-center justify-between">
                <LzBadge tone="warning">{{ prepared ? '准备完成' : prepStatus || '编排中…' }}</LzBadge>
                <span class="font-mono-tech text-[10px] uppercase tracking-widest text-slate-500">Workflow · 3 组并行</span>
              </div>
              <ol class="space-y-1.5">
                <li
                  v-for="node in agentNodes"
                  :key="node.role"
                  class="flex items-center gap-2.5 rounded-lg px-2 py-1.5"
                  :class="node.status === 'running' ? 'bg-amber-400/10' : ''"
                >
                  <span
                    class="h-2 w-2 shrink-0 rounded-full"
                    :class="{
                      'bg-slate-600': node.status === 'pending',
                      'iv-node-running bg-amber-300': node.status === 'running',
                      'bg-emerald-400': node.status === 'done',
                    }"
                    aria-hidden="true"
                  ></span>
                  <span class="w-36 shrink-0 text-xs" :class="node.status === 'pending' ? 'text-slate-500' : 'text-slate-200'">
                    {{ node.label }}
                  </span>
                  <span class="min-w-0 flex-1 truncate text-xs text-slate-500">{{ node.note }}</span>
                </li>
              </ol>
            </div>
            <div v-if="prepared && hasIntel" class="lz-hud-card space-y-3 p-4">
              <h4 class="text-sm text-amber-100">岗位情报 · 面试官会考察什么</h4>
              <p v-if="intel?.job?.summary" class="text-xs leading-relaxed text-slate-300">{{ intel.job.summary }}</p>
              <div v-if="(intel?.job?.skills || []).length" class="flex flex-wrap gap-1.5">
                <LzBadge v-for="skill in intel!.job!.skills" :key="skill" tone="accent">{{ skill }}</LzBadge>
              </div>
              <div v-if="(intel?.topics || []).length">
                <p class="mb-1 text-[11px] text-slate-500">本场考察主题</p>
                <ul class="space-y-0.5 text-xs text-slate-400">
                  <li v-for="topic in intel!.topics" :key="topic">· {{ topic }}</li>
                </ul>
              </div>
              <p v-if="intel?.profile?.summary" class="rounded-lg border border-white/10 p-2.5 text-xs text-slate-400">
                面试官对你的了解：{{ intel.profile.summary }}
              </p>
            </div>
            <div class="flex gap-2">
              <LzButton v-if="prepared" variant="primary" @click="enterInterview">进入面试</LzButton>
              <LzButton v-else variant="ghost" disabled>正在编排…</LzButton>
            </div>
          </template>
        </div>
      </Transition>
      <p v-if="error" class="mt-3 text-xs text-rose-300">{{ error }}</p>
    </div>
  </div>
</template>

<style scoped>
.iv-deck {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
.iv-slate {
  position: sticky;
  top: 0;
  border-radius: 20px;
  border: 1px solid var(--border-soft);
  background:
    linear-gradient(180deg, rgb(var(--lz-accent) / 0.08), transparent 28%),
    rgba(2, 6, 23, 0.55);
  padding: 18px 16px;
  backdrop-filter: blur(18px) saturate(140%);
}
.iv-role-title {
  margin: 10px 0 0;
  font-size: 1.35rem;
  font-weight: 600;
  background: linear-gradient(100deg, #fff 30%, rgb(var(--lz-accent-bright)) 85%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.iv-steps {
  position: relative;
  margin-top: 22px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-left: 4px;
}
.iv-steps__track {
  position: absolute;
  left: 18px;
  top: 18px;
  bottom: 18px;
  width: 1px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.08);
}
.iv-steps__fill {
  display: block;
  width: 1px;
  background: linear-gradient(180deg, rgb(var(--lz-accent-bright)), rgb(var(--lz-accent) / 0.2));
  transition: height 0.45s cubic-bezier(0.22, 1, 0.36, 1);
}
.iv-step {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: baseline;
  gap: 10px;
  text-align: left;
  color: #64748b;
}
.iv-step:disabled {
  cursor: default;
}
.iv-step.is-now,
.iv-step.is-done {
  color: #fde68a;
}
.iv-step__n {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 22px;
  letter-spacing: 0.04em;
  line-height: 1;
}
.iv-step.is-now .iv-step__n {
  text-shadow: 0 0 18px rgb(var(--lz-accent) / 0.7);
}
.iv-step__l {
  font-size: 12px;
}
.iv-gate {
  display: flex;
  gap: 8px;
  margin-top: 22px;
  font-size: 11px;
  line-height: 1.5;
  color: #94a3b8;
}
.iv-stage .is-picked {
  box-shadow: inset 0 0 0 1px rgb(var(--lz-accent) / 0.45), 0 0 28px -12px rgb(var(--lz-accent) / 0.55);
}
.iv-volt {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  min-height: 84px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(2, 6, 23, 0.4);
  padding: 12px;
  text-align: left;
}
.iv-volt__label {
  font-size: 14px;
  color: #e2e8f0;
}
.iv-volt__hint {
  font-size: 10px;
  color: #64748b;
}
.iv-volt--easy.is-on {
  border-color: rgba(252, 211, 77, 0.25);
  box-shadow: 0 0 16px -10px rgba(252, 211, 77, 0.5);
}
.iv-volt--medium.is-on {
  border-color: rgba(245, 158, 11, 0.7);
  box-shadow: 0 0 22px -8px rgba(245, 158, 11, 0.7);
}
.iv-volt--hard.is-on {
  border-color: rgba(251, 191, 36, 0.9);
  box-shadow: 0 0 28px -6px rgba(251, 191, 36, 0.85);
}
.iv-drop {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  border-radius: 16px;
  border: 1px dashed rgba(245, 158, 11, 0.35);
  background: rgba(2, 6, 23, 0.35);
  padding: 18px;
}
.iv-drop.is-drag {
  border-style: solid;
}
.iv-drop::after {
  content: '';
  position: absolute;
  z-index: 0;
  inset: -40%;
  background: conic-gradient(from 0deg, transparent, rgb(var(--lz-accent) / 0.35), transparent 40%);
  opacity: 0;
  animation: iv-spin 6s linear infinite;
  pointer-events: none;
}
.iv-drop:hover::after,
.iv-drop.is-drag::after {
  opacity: 0.22;
}
.iv-drop > * {
  position: relative;
  z-index: 1;
}
.iv-file-btn {
  display: inline-flex;
  margin-top: 12px;
  cursor: pointer;
  border-radius: 999px;
  background: #f59e0b;
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  color: #1c1917;
}
.iv-node-running {
  animation: iv-node-pulse 1s ease-in-out infinite;
}
@keyframes iv-node-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(252, 211, 77, 0.5); }
  50% { box-shadow: 0 0 0 5px rgba(252, 211, 77, 0); }
}
@keyframes iv-spin {
  to { transform: rotate(360deg); }
}
@media (max-width: 800px) {
  .iv-deck {
    grid-template-columns: 1fr;
  }
  .iv-slate {
    position: static;
  }
}
@media (prefers-reduced-motion: reduce) {
  .iv-steps__fill,
  .iv-drop::after,
  .iv-node-running {
    animation: none;
    transition: none;
  }
}
</style>

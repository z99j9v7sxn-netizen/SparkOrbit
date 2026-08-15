<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import type { AgentRunDetail, AgentStepItem } from '../../../api/admin';
import OrbCore, { type OrbState } from '../../common/orb/OrbCore.vue';

const props = defineProps<{
  run: AgentRunDetail | null;
}>();

const emit = defineEmits<{
  (e: 'focus-step', stepIndex: number): void;
}>();

const stageRef = ref<HTMLDivElement | null>(null);
const enterKey = ref(0);

type PipeNode = {
  stepIndex: number;
  label: string;
  status: string;
  group: string;
  summary: string;
  current: boolean;
};

const MODE_META: Record<
  string,
  { title: string; blurb: string; theme: string; bar: string; accent: string }
> = {
  handoff: {
    title: '顺序接力 · Handoff',
    blurb: '子 Agent 单列交接完成任务，互不并行干涉——像接力棒一棒一棒往下传。',
    theme: 'mode-handoff',
    bar: 'border-sky-400/35 bg-sky-500/10',
    accent: 'text-sky-200',
  },
  workflow: {
    title: '流水线编排 · Workflow',
    blurb: '按 DAG 划分 Stage（G1→G2→G3），同组可并行、组间有依赖箭头。',
    theme: 'mode-workflow',
    bar: 'border-cyan-400/35 bg-cyan-500/10',
    accent: 'text-cyan-200',
  },
  supervisor: {
    title: '层级统筹 · Supervisor',
    blurb: '主控先统筹意图与优先级，再把任务派给下属——像层级任务日志。',
    theme: 'mode-supervisor',
    bar: 'border-violet-400/35 bg-violet-500/10',
    accent: 'text-violet-200',
  },
  council: {
    title: '并行评议 · Council',
    blurb: '同一任务多视角并行思考，再 fan-in 汇总成一条建议。',
    theme: 'mode-council',
    bar: 'border-amber-400/35 bg-amber-500/10',
    accent: 'text-amber-200',
  },
};

const modeKey = computed(() => props.run?.mode || 'workflow');
const meta = computed(() => MODE_META[modeKey.value] || MODE_META.workflow);

const nodes = computed<PipeNode[]>(() => {
  const d = props.run;
  if (!d) return [];
  if (d.steps?.length) {
    return d.steps.map((s: AgentStepItem) => ({
      stepIndex: s.step_index,
      label: s.agent_role,
      status: s.status,
      group: s.parallel_group || '',
      summary: s.summary,
      current: d.status === 'running' && d.current_step === s.step_index,
    }));
  }
  const order = (d.graph_plan?.order as string[]) || [];
  return order.map((role, i) => ({
    stepIndex: i,
    label: role,
    status: 'pending',
    group: '',
    summary: '',
    current: false,
  }));
});

const groupKeys = computed(() => {
  const keys: string[] = [];
  for (const n of nodes.value) {
    const k = n.group || `step-${n.stepIndex}`;
    if (!keys.includes(k)) keys.push(k);
  }
  return keys;
});

const grouped = computed(() =>
  groupKeys.value.map((key) => ({
    key,
    nodes: nodes.value.filter((n) => (n.group || `step-${n.stepIndex}`) === key),
  })),
);

const councilPeers = computed(() =>
  nodes.value.filter((x) => x.group !== 'summary' && !x.label.includes('Summarizer')),
);
const councilSummary = computed(() =>
  nodes.value.filter((x) => x.group === 'summary' || x.label.includes('Summarizer')),
);
const supervisorControl = computed(() =>
  nodes.value.filter((x) => x.group === 'control' || x.label === 'Supervisor'),
);
const supervisorWorkers = computed(() =>
  nodes.value.filter((x) => x.group !== 'control' && x.label !== 'Supervisor'),
);

watch(
  () => props.run?.id,
  async () => {
    enterKey.value += 1;
    await nextTick();
    stageRef.value?.scrollTo({ left: 0, behavior: 'smooth' });
  },
);

const runOrbState = computed<OrbState>(() => {
  const status = props.run?.status;
  if (status === 'running') return 'thinking';
  if (status === 'completed') return 'success';
  if (status === 'failed') return 'error';
  return 'idle';
});

/* 节点点亮脉冲：状态从非 completed 变为 completed 时短暂高亮 */
const justDone = ref<Set<number>>(new Set());
let prevStatuses = new Map<number, string>();
let prevRunId: string | null | undefined;

watch(nodes, (list) => {
  const runId = props.run?.id;
  const sameRun = runId === prevRunId;
  const popped: number[] = [];
  if (sameRun) {
    for (const n of list) {
      const prev = prevStatuses.get(n.stepIndex);
      if (prev && prev !== 'completed' && n.status === 'completed') popped.push(n.stepIndex);
    }
  }
  prevRunId = runId;
  prevStatuses = new Map(list.map((n) => [n.stepIndex, n.status]));
  if (!popped.length) return;
  const next = new Set(justDone.value);
  for (const i of popped) next.add(i);
  justDone.value = next;
  window.setTimeout(() => {
    const cleaned = new Set(justDone.value);
    for (const i of popped) cleaned.delete(i);
    justDone.value = cleaned;
  }, 1200);
});

function nodeClass(n: PipeNode) {
  const pop = justDone.value.has(n.stepIndex) ? ' is-just-done' : '';
  if (n.current || n.status === 'running') return `is-running${pop}`;
  if (n.status === 'completed') return `is-done${pop}`;
  if (n.status === 'failed') return `is-fail${pop}`;
  return `is-pending${pop}`;
}
</script>

<template>
  <div class="rounded-2xl border border-white/10 bg-slate-950/45 p-4" :class="run ? meta.theme : ''">
    <div class="mb-3 flex flex-wrap items-start justify-between gap-2">
      <div>
        <p class="font-mono-tech text-[10px] uppercase tracking-[0.3em] text-cyan-300/70">Agent Work Loop</p>
        <h3 class="mt-1 text-sm font-medium text-white">编排流水线</h3>
        <p v-if="run" class="mt-1 text-xs text-slate-500">
          {{ run.user_name }} · {{ run.id }}
        </p>
        <p v-else class="mt-1 text-xs text-slate-500">选择左侧 Episode 渲染四 mode 图</p>
      </div>
      <div class="flex items-center gap-2">
        <OrbCore
          :state="runOrbState"
          palette="violet"
          :size="52"
          :label="`运行状态：${run?.status || '待选择'}`"
        />
        <span class="font-mono-tech text-[10px] uppercase tracking-widest text-slate-500">
          {{ run?.status || 'standby' }}
        </span>
      </div>
    </div>

    <div
      v-if="run"
      class="mb-4 rounded-xl border px-3 py-2.5"
      :class="meta.bar"
    >
      <p class="text-sm font-semibold" :class="meta.accent">{{ meta.title }}</p>
      <p class="mt-1 text-[11px] leading-relaxed text-slate-300/95">{{ meta.blurb }}</p>
    </div>

    <div
      v-if="!run"
      class="flex h-56 items-center justify-center rounded-xl border border-dashed border-white/10 text-sm text-slate-600"
    >
      等待选择运行…
    </div>

    <div v-else :key="enterKey" ref="stageRef" class="pipeline-scroll overflow-x-auto pb-2">
      <!-- workflow: Stage G1/G2/G3 + thick arrows -->
      <div
        v-if="modeKey === 'workflow' || !['handoff', 'council', 'supervisor'].includes(modeKey)"
        class="flex min-w-max items-stretch gap-0 py-2"
      >
        <template v-for="(g, gi) in grouped" :key="g.key">
          <div class="pipeline-stage workflow-stage stagger-in" :style="{ animationDelay: `${gi * 70}ms` }">
            <p class="mb-2 flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[0.2em] text-cyan-300/80">
              <span class="rounded bg-cyan-500/20 px-1.5 py-0.5 text-cyan-100">G{{ gi + 1 }}</span>
              <span class="text-slate-500">{{ g.key }}</span>
            </p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="(n, ni) in g.nodes"
                :key="n.stepIndex"
                type="button"
                class="pipe-node stagger-in"
                :class="nodeClass(n)"
                :style="{ animationDelay: `${gi * 70 + ni * 40}ms` }"
                @click="emit('focus-step', n.stepIndex)"
              >
                <span class="pipe-node__idx">#{{ n.stepIndex }}</span>
                <span class="pipe-node__label">{{ n.label }}</span>
                <span class="pipe-node__status">{{ n.status }}</span>
              </button>
            </div>
          </div>
          <div v-if="gi < grouped.length - 1" class="pipeline-arrow pipeline-arrow--thick" aria-hidden="true">
            <svg width="48" height="28" viewBox="0 0 48 28" fill="none">
              <path d="M2 14h36" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
              <path d="M32 6l12 8-12 8" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </div>
        </template>
      </div>

      <!-- handoff: vertical relay + baton -->
      <div v-else-if="modeKey === 'handoff'" class="handoff-rail mx-auto max-w-sm py-2">
        <template v-for="(n, i) in nodes" :key="n.stepIndex">
          <button
            type="button"
            class="pipe-node pipe-node--wide handoff-node stagger-in w-full"
            :class="nodeClass(n)"
            :style="{ animationDelay: `${i * 70}ms` }"
            @click="emit('focus-step', n.stepIndex)"
          >
            <span class="pipe-node__idx">Relay {{ i + 1 }} · 交接</span>
            <span class="pipe-node__label">{{ n.label }}</span>
            <span class="pipe-node__status">{{ n.status }}</span>
            <span v-if="n.summary" class="mt-0.5 truncate text-[10px] text-slate-500">{{ n.summary }}</span>
          </button>
          <div v-if="i < nodes.length - 1" class="handoff-baton" aria-hidden="true">
            <span class="baton-dot" />
            <span class="baton-line" />
            <span class="baton-label font-mono-tech">handoff ↓</span>
          </div>
        </template>
      </div>

      <!-- council: parallel row + wide summary -->
      <div v-else-if="modeKey === 'council'" class="flex min-w-max flex-col gap-3 py-2">
        <p class="font-mono-tech text-[10px] uppercase tracking-widest text-amber-300/70">并行多视角</p>
        <div class="flex items-stretch gap-3">
          <button
            v-for="(n, i) in councilPeers"
            :key="n.stepIndex"
            type="button"
            class="pipe-node council-peer stagger-in"
            :class="nodeClass(n)"
            :style="{ animationDelay: `${i * 55}ms` }"
            @click="emit('focus-step', n.stepIndex)"
          >
            <span class="pipe-node__idx">视角 {{ i + 1 }}</span>
            <span class="pipe-node__label">{{ n.label }}</span>
            <span class="pipe-node__status">{{ n.status }}</span>
          </button>
        </div>
        <div class="council-fanin flex flex-col items-center gap-1 text-amber-400/60" aria-hidden="true">
          <svg width="280" height="36" viewBox="0 0 280 36" class="w-full max-w-md">
            <path d="M40 4v12h200V4" stroke="currentColor" fill="none" stroke-width="1.5" />
            <path d="M140 16v10" stroke="currentColor" stroke-width="1.5" />
            <path d="M132 22l8 10 8-10" stroke="currentColor" fill="none" stroke-width="1.5" />
          </svg>
          <span class="font-mono-tech text-[10px] uppercase tracking-widest">fan-in · 汇总评议</span>
        </div>
        <button
          v-for="(n, i) in councilSummary"
          :key="n.stepIndex"
          type="button"
          class="pipe-node pipe-node--summary stagger-in w-full max-w-xl"
          :class="nodeClass(n)"
          :style="{ animationDelay: `${220 + i * 40}ms` }"
          @click="emit('focus-step', n.stepIndex)"
        >
          <span class="pipe-node__idx">汇总宽卡</span>
          <span class="pipe-node__label">{{ n.label }}</span>
          <span class="pipe-node__status">{{ n.status }}</span>
        </button>
      </div>

      <!-- supervisor: big control + indented workers -->
      <div v-else class="supervisor-tree min-w-[18rem] py-2">
        <button
          v-for="n in supervisorControl"
          :key="n.stepIndex"
          type="button"
          class="pipe-node pipe-node--boss stagger-in w-full max-w-md"
          :class="nodeClass(n)"
          @click="emit('focus-step', n.stepIndex)"
        >
          <span class="pipe-node__idx">主控 · Supervisor</span>
          <span class="pipe-node__label text-base">{{ n.label }}</span>
          <span class="pipe-node__status">{{ n.status }}</span>
        </button>
        <div class="mt-3 ml-3 border-l-2 border-violet-400/35 pl-4">
          <p class="mb-2 font-mono-tech text-[10px] uppercase tracking-widest text-violet-300/70">
            下属 · priority dispatch
          </p>
          <div class="flex flex-col gap-2">
            <button
              v-for="(n, i) in supervisorWorkers"
              :key="n.stepIndex"
              type="button"
              class="pipe-node pipe-node--worker stagger-in"
              :class="nodeClass(n)"
              :style="{ animationDelay: `${80 + i * 45}ms` }"
              @click="emit('focus-step', n.stepIndex)"
            >
              <span class="pipe-node__idx">P{{ i + 1 }} · worker</span>
              <span class="pipe-node__label">{{ n.label }}</span>
              <span class="pipe-node__status">{{ n.status }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pipeline-scroll {
  scrollbar-width: thin;
  scrollbar-color: #334155 transparent;
}
.pipeline-stage {
  min-width: 11rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 1rem;
  background: linear-gradient(160deg, rgba(15, 23, 42, 0.9), rgba(8, 15, 30, 0.7));
  padding: 0.75rem;
}
.workflow-stage {
  border-color: rgba(34, 211, 238, 0.28);
  box-shadow: inset 0 0 0 1px rgba(34, 211, 238, 0.06);
}
.pipeline-arrow {
  display: flex;
  align-items: center;
  color: #64748b;
  padding: 0 0.15rem;
  margin-top: 1.4rem;
}
.pipeline-arrow--thick {
  color: #22d3ee;
  opacity: 0.85;
}
.handoff-rail {
  display: flex;
  flex-direction: column;
  align-items: stretch;
}
.handoff-node {
  border-color: rgba(56, 189, 248, 0.35) !important;
}
.handoff-baton {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
  padding: 0.35rem 0;
  color: #7dd3fc;
}
.baton-dot {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 999px;
  background: #38bdf8;
  box-shadow: 0 0 12px rgba(56, 189, 248, 0.7);
  animation: baton-pulse 1.4s ease-in-out infinite;
}
.baton-line {
  width: 2px;
  height: 1.1rem;
  background: linear-gradient(180deg, #38bdf8, transparent);
}
.baton-label {
  font-size: 9px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.75;
}
.council-peer {
  min-width: 8.5rem;
  border-color: rgba(251, 191, 36, 0.3) !important;
}
.pipe-node--summary {
  min-width: 16rem;
  border-width: 2px;
  border-color: rgba(251, 191, 36, 0.45) !important;
  background: rgba(245, 158, 11, 0.12) !important;
  padding: 0.85rem 1rem;
}
.pipe-node--boss {
  min-width: 14rem;
  border-width: 2px;
  border-color: rgba(167, 139, 250, 0.55) !important;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.22), rgba(15, 23, 42, 0.8)) !important;
  padding: 0.9rem 1rem;
  box-shadow: 0 0 28px rgba(139, 92, 246, 0.15);
}
.pipe-node--worker {
  border-color: rgba(167, 139, 250, 0.25) !important;
}
.pipe-node {
  display: flex;
  min-width: 7.25rem;
  flex-direction: column;
  gap: 0.15rem;
  border-radius: 0.85rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(2, 6, 23, 0.55);
  padding: 0.55rem 0.7rem;
  text-align: left;
  transition: border-color 0.25s ease, box-shadow 0.25s ease, transform 0.2s ease;
}
.pipe-node--wide {
  min-width: 9rem;
}
.pipe-node:hover {
  transform: translateY(-1px);
}
.pipe-node__idx {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #64748b;
}
.pipe-node__label {
  font-size: 12px;
  font-weight: 600;
  color: #f1f5f9;
}
.pipe-node__status {
  font-size: 10px;
  color: #94a3b8;
}
.pipe-node.is-done {
  border-color: rgba(52, 211, 153, 0.45);
  background: rgba(16, 185, 129, 0.1);
}
.pipe-node.is-fail {
  border-color: rgba(251, 113, 133, 0.45);
  background: rgba(244, 63, 94, 0.1);
}
.pipe-node.is-pending {
  border-color: rgba(255, 255, 255, 0.08);
  opacity: 0.72;
}
.pipe-node.is-running {
  border-color: rgba(251, 191, 36, 0.55);
  background: rgba(245, 158, 11, 0.12);
  box-shadow: 0 0 22px rgba(251, 191, 36, 0.18);
  animation: pulse-ring 1.8s ease-in-out infinite;
}
.pipe-node.is-just-done {
  animation: node-pop 1.1s ease-out;
}
@keyframes node-pop {
  0% {
    transform: scale(1);
    box-shadow: 0 0 0 rgba(52, 211, 153, 0);
  }
  25% {
    transform: scale(1.05);
    box-shadow: 0 0 28px rgba(52, 211, 153, 0.55);
  }
  100% {
    transform: scale(1);
    box-shadow: 0 0 0 rgba(52, 211, 153, 0);
  }
}
@media (prefers-reduced-motion: reduce) {
  .pipe-node.is-running,
  .pipe-node.is-just-done,
  .baton-dot,
  .stagger-in {
    animation: none;
  }
}
@keyframes baton-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.25);
    opacity: 0.75;
  }
}
@keyframes pulse-ring {
  0%,
  100% {
    box-shadow: 0 0 12px rgba(251, 191, 36, 0.12);
  }
  50% {
    box-shadow: 0 0 28px rgba(251, 191, 36, 0.35);
  }
}
.stagger-in {
  animation: fade-up 0.45s ease both;
}
@keyframes fade-up {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>

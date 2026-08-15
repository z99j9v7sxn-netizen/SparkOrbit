<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref } from 'vue';
import { startMirrorSimulation, streamSimulation, type SimEvent } from '../api/simulation';

interface ConsoleLine {
  role: SimEvent['role'];
  type: string;
  text: string;
  full: string;
  done: boolean;
  passed?: boolean;
}

const props = withDefaults(defineProps<{ closable?: boolean; variant?: 'student' | 'teacher'; initialTopic?: string }>(), {
  closable: true,
  variant: 'student',
  initialTopic: '',
});
const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'verdict', passed: boolean): void;
  (e: 'add-mistake', payload: { question: string; subject: string; note: string }): void;
  (e: 'start-focus', minutes: number): void;
  (e: 'complete', payload: { topic: string; pathSteps: string[]; rootCause: string }): void;
}>();

const lines = ref<ConsoleLine[]>([]);
const running = ref(false);
const currentTopic = ref('');
const status = ref('待命');
const bodyRef = ref<HTMLDivElement | null>(null);
const resultCards = ref<{ title: string; body: string; tone: string }[]>([]);
const pathSteps = ref<string[]>([]);
const rootCause = ref('');
const lastQuestion = ref('');

const displayTopic = computed(() => currentTopic.value || props.initialTopic || '');
const emptyHint = computed(() => {
  if (running.value || status.value === '连接中') {
    return '正在连接 Teacher / Mirror / Evaluator / PathPlanner…';
  }
  if (props.variant === 'teacher') {
    return props.initialTopic
      ? `已选知识点「${props.initialTopic}」。调节画像后点击「开始推演」。`
      : '请在上方选择星系与知识点行星，然后点击「开始推演」。';
  }
  return '点击行星面板「让数字替身先预演这颗行星」开始推演；也可在画像页点「预演」。';
});

let abortController: AbortController | null = null;
const queue: SimEvent[] = [];
let draining = false;
let completedEmitted = false;

const ROLE_META: Record<SimEvent['role'], { tag: string; color: string; glyph: string }> = {
  System: { tag: 'SYSTEM', color: 'text-slate-400', glyph: '◇' },
  Teacher: { tag: 'TEACHER', color: 'text-sky-300', glyph: '◆' },
  Mirror: { tag: 'MIRROR', color: 'text-fuchsia-300', glyph: '❖' },
  Evaluator: { tag: 'EVALUATOR', color: 'text-amber-300', glyph: '⬡' },
  PathPlanner: { tag: 'PLANNER', color: 'text-emerald-300', glyph: '✦' },
};

function scrollBottom() {
  void nextTick(() => {
    if (bodyRef.value) bodyRef.value.scrollTop = bodyRef.value.scrollHeight;
  });
}

function typeText(line: ConsoleLine): Promise<void> {
  return new Promise((resolve) => {
    const speed = Math.max(6, Math.min(20, Math.floor(520 / Math.max(line.full.length, 1))));
    const timer = window.setInterval(() => {
      line.text = line.full.slice(0, line.text.length + 2);
      scrollBottom();
      if (line.text.length >= line.full.length) {
        line.text = line.full;
        line.done = true;
        window.clearInterval(timer);
        resolve();
      }
    }, speed);
  });
}

async function drain() {
  if (draining) return;
  draining = true;
  while (queue.length) {
    const ev = queue.shift()!;
    const line = reactive<ConsoleLine>({
      role: ev.role,
      type: ev.type,
      text: '',
      full: ev.content,
      done: false,
      passed: typeof ev.payload?.passed === 'boolean' ? (ev.payload!.passed as boolean) : undefined,
    });
    lines.value.push(line);
    if (ev.type === 'question') {
      lastQuestion.value = ev.content;
      resultCards.value.push({ title: '诊断题', body: ev.content, tone: 'sky' });
    }
    if (ev.type === 'answer') resultCards.value.push({ title: '替身作答', body: ev.content, tone: 'fuchsia' });
    if (ev.type === 'evaluation') resultCards.value.push({ title: '评估结果', body: ev.content, tone: ev.payload?.passed ? 'emerald' : 'amber' });
    if (ev.type === 'root_cause') rootCause.value = String(ev.payload?.root_cause || ev.content);
    if (ev.type === 'learning_path') {
      resultCards.value.push({ title: '补救路径', body: ev.content, tone: 'emerald' });
      const steps = ev.payload?.steps;
      pathSteps.value = Array.isArray(steps) ? steps.map(String) : ev.content.split(/；|;/).map((s) => s.replace(/^\d+\.\s*/, '').trim()).filter(Boolean);
    }
    await typeText(line);
    if (ev.type === 'evaluation' && typeof ev.payload?.passed === 'boolean') {
      emit('verdict', ev.payload.passed as boolean);
    }
    if (ev.type === 'done') {
      running.value = false;
      status.value = ev.payload?.passed ? '预测可通过' : '已锁定风险';
      emitComplete();
    }
  }
  draining = false;
}

function emitComplete() {
  if (completedEmitted) return;
  completedEmitted = true;
  emit('complete', {
    topic: currentTopic.value,
    pathSteps: [...pathSteps.value],
    rootCause: rootCause.value,
  });
  window.dispatchEvent(
    new CustomEvent('sparkorbit:sim-complete', {
      detail: { topic: currentTopic.value, pathSteps: [...pathSteps.value], rootCause: rootCause.value },
    }),
  );
}

async function run(
  topic: string,
  overrides: Record<string, number> = {},
  targetDimension?: string,
  options?: { userId?: string; studentProfileId?: string; planetSlug?: string },
) {
  currentTopic.value = topic;
  lines.value = [];
  resultCards.value = [];
  pathSteps.value = [];
  rootCause.value = '';
  lastQuestion.value = '';
  queue.length = 0;
  completedEmitted = false;
  status.value = '连接中';
  running.value = true;
  abortController?.abort();
  abortController = new AbortController();
  try {
    const { run_id } = await startMirrorSimulation(topic, overrides, targetDimension, options);
    status.value = '推演中';
    await streamSimulation(
      run_id,
      (ev) => {
        queue.push(ev);
        void drain();
      },
      { signal: abortController.signal },
    );
    running.value = false;
    if (status.value === '推演中') status.value = '已完成';
    if (!completedEmitted) emitComplete();
  } catch (e) {
    if (abortController?.signal.aborted) {
      running.value = false;
      return;
    }
    running.value = false;
    status.value = '推演失败';
    const detail = e instanceof Error ? e.message : '推演失败，请稍后再试。';
    let hint = detail;
    if (detail.includes('学生画像') || detail.includes('画像抽取')) {
      hint = `${detail} → 请打开 Mirror「采集 → 首次采集」，发送并更新画像后再重试。`;
    } else if (/落库失败|表结构|Unknown column|重启后端/i.test(detail)) {
      hint = `${detail}（请重启后端以自动迁移 simulation_runs 后重试。）`;
    }
    queue.push({
      role: 'System',
      type: 'boot',
      content: hint,
    });
    void drain();
  }
}

defineExpose({ run });

function addStepToMistake(step: string) {
  emit('add-mistake', {
    question: lastQuestion.value || currentTopic.value,
    subject: currentTopic.value,
    note: `推演补救：${step}${rootCause.value ? `（错因：${rootCause.value}）` : ''}`,
  });
}

function startFocusPlan(step: string) {
  void step;
  emit('start-focus', 25);
}

onBeforeUnmount(() => abortController?.abort());
</script>

<template>
  <div class="glass-strong glass-edge relative flex h-full w-full flex-col overflow-hidden rounded-3xl">
    <!-- 终端头部 -->
    <header class="flex items-center gap-3 border-b border-white/10 px-4 py-3">
      <div class="flex gap-1.5">
        <span class="h-3 w-3 rounded-full bg-rose-400/80"></span>
        <span class="h-3 w-3 rounded-full bg-amber-400/80"></span>
        <span class="h-3 w-3 rounded-full bg-emerald-400/80"></span>
      </div>
      <div class="min-w-0 flex-1">
        <p class="font-mono-tech text-[11px] uppercase tracking-[0.25em] text-sky-300/80">simulation_console</p>
        <p class="truncate text-[11px] text-slate-400">多智能体推演 · {{ displayTopic || '尚未指定知识点' }}</p>
        <span class="mt-1 inline-flex rounded-md border border-sky-400/40 bg-sky-500/15 px-2 py-0.5 text-[10px] text-sky-100">
          编排：顺序接力 handoff
        </span>
      </div>
      <span
        class="rounded-full border px-2.5 py-0.5 font-mono-tech text-[10px]"
        :class="running ? 'border-sky-400/40 bg-sky-400/10 text-sky-200 animate-pulse-ring' : 'border-white/15 bg-white/5 text-slate-300'"
      >{{ status }}</span>
      <button v-if="closable" class="rounded-full border border-white/10 px-2 py-0.5 text-xs text-slate-300 hover:bg-white/5" @click="emit('close')">✕</button>
    </header>

    <!-- 智能体图例 -->
    <div class="flex flex-wrap gap-x-3 gap-y-1 border-b border-white/5 px-4 py-2 font-mono-tech text-[10px]">
      <span v-for="(m, r) in ROLE_META" :key="r" :class="m.color">{{ m.glyph }} {{ m.tag }}</span>
    </div>

    <!-- 流式输出体 -->
    <div ref="bodyRef" class="relative flex-1 space-y-2 overflow-auto px-4 py-3 font-mono-tech text-[12px] leading-relaxed">
      <div v-if="!lines.length" class="text-slate-500">
        <p v-if="running || status === '连接中'">$ connecting multi-agent stream…</p>
        <p v-else>$ awaiting simulation…</p>
        <p class="mt-1 text-slate-600">{{ emptyHint }}</p>
      </div>
      <div v-for="(line, i) in lines" :key="i" class="flex gap-2">
        <span class="shrink-0 text-slate-600">›</span>
        <span :class="ROLE_META[line.role].color" class="shrink-0 whitespace-nowrap">
          {{ ROLE_META[line.role].glyph }} {{ ROLE_META[line.role].tag }}
        </span>
        <span
          class="text-slate-200"
          :class="[
            !line.done ? 'caret' : '',
            line.type === 'evaluation' && line.passed === false ? 'text-rose-200' : '',
            line.type === 'evaluation' && line.passed === true ? 'text-emerald-200' : '',
            line.type === 'learning_path' ? 'text-emerald-100' : '',
          ]"
        >{{ line.text }}</span>
      </div>
    </div>

    <div v-if="pathSteps.length" class="max-h-44 space-y-2 overflow-auto border-t border-white/10 px-4 py-3">
      <p class="text-[10px] uppercase tracking-wider text-emerald-300/80">补救路径 · 可执行</p>
      <article v-for="(step, i) in pathSteps" :key="i" class="rounded-xl border border-emerald-400/20 bg-emerald-500/5 p-2 text-xs">
        <p class="text-white">{{ i + 1 }}. {{ step }}</p>
        <div class="mt-2 flex gap-2">
          <button class="rounded-lg border border-sky-400/20 px-2 py-0.5 text-[10px] text-sky-200" @click="addStepToMistake(step)">加入错题本</button>
          <button class="rounded-lg border border-fuchsia-400/20 px-2 py-0.5 text-[10px] text-fuchsia-200" @click="startFocusPlan(step)">番茄钟 25′</button>
        </div>
      </article>
    </div>

    <div v-else-if="resultCards.length" class="max-h-40 space-y-2 overflow-auto border-t border-white/10 px-4 py-3">
      <article
        v-for="(card, i) in resultCards"
        :key="i"
        class="rounded-xl border border-white/10 bg-white/5 p-2 text-xs"
        :class="card.tone === 'emerald' ? 'border-emerald-400/20' : card.tone === 'amber' ? 'border-amber-400/20' : 'border-sky-400/20'"
      >
        <p class="font-medium text-white">{{ card.title }}</p>
        <p class="mt-1 whitespace-pre-wrap text-slate-300">{{ card.body }}</p>
      </article>
    </div>

    <!-- 底部扫描线装饰 -->
    <div class="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-sky-400/40 to-transparent"></div>
  </div>
</template>

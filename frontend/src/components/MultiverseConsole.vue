<script setup lang="ts">
import { nextTick, onBeforeUnmount, reactive, ref } from 'vue';
import { startMultiverseSimulation, streamSimulation, type SimEvent } from '../api/simulation';

interface ConsoleLine {
  role: SimEvent['role'];
  type: string;
  text: string;
  full: string;
  done: boolean;
}

const emit = defineEmits<{ (e: 'close'): void }>();

const lines = ref<ConsoleLine[]>([]);
const results = ref<{ label: string; passed: boolean; score: number; diagnosis: string }[]>([]);
const recommendation = ref('');
const running = ref(false);
const currentTopic = ref('');
const bodyRef = ref<HTMLDivElement | null>(null);

let abortController: AbortController | null = null;
const queue: SimEvent[] = [];
let draining = false;

function scrollBottom() {
  void nextTick(() => {
    if (bodyRef.value) bodyRef.value.scrollTop = bodyRef.value.scrollHeight;
  });
}

function typeText(line: ConsoleLine): Promise<void> {
  return new Promise((resolve) => {
    const speed = Math.max(6, Math.min(18, Math.floor(480 / Math.max(line.full.length, 1))));
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
    if (ev.type === 'multiverse_result' && ev.payload) {
      results.value.push({
        label: String(ev.payload.label ?? ''),
        passed: Boolean(ev.payload.passed),
        score: Number(ev.payload.score ?? 0),
        diagnosis: String(ev.payload.diagnosis ?? ''),
      });
    }
    if (ev.type === 'recommendation') {
      recommendation.value = ev.content;
    }
    const line = reactive<ConsoleLine>({ role: ev.role, type: ev.type, text: '', full: ev.content, done: false });
    lines.value.push(line);
    await typeText(line);
    if (ev.type === 'done') running.value = false;
  }
  draining = false;
}

async function run(topic: string) {
  currentTopic.value = topic;
  lines.value = [];
  results.value = [];
  recommendation.value = '';
  queue.length = 0;
  running.value = true;
  abortController?.abort();
  abortController = new AbortController();
  try {
    const { run_id } = await startMultiverseSimulation(topic);
    await streamSimulation(
      run_id,
      (ev) => {
        queue.push(ev);
        void drain();
      },
      { signal: abortController.signal },
    );
    running.value = false;
  } catch (e) {
    if (abortController?.signal.aborted) {
      running.value = false;
      return;
    }
    running.value = false;
    queue.push({
      role: 'System',
      type: 'boot',
      content: e instanceof Error ? e.message : '平行宇宙推演失败',
    });
    void drain();
  }
}

defineExpose({ run });
onBeforeUnmount(() => abortController?.abort());
</script>

<template>
  <div class="glass-strong glass-edge flex h-full flex-col overflow-hidden rounded-3xl">
    <header class="flex items-center justify-between border-b border-white/10 px-4 py-3">
      <div>
        <p class="font-mono-tech text-[11px] uppercase tracking-[0.25em] text-purple-300/80">multiverse_console</p>
        <p class="text-[11px] text-slate-400">平行宇宙推演 · {{ currentTopic || '未指定' }}</p>
        <span class="mt-1 inline-flex rounded-md border border-amber-400/40 bg-amber-500/15 px-2 py-0.5 text-[10px] text-amber-100">
          编排：并行评议 council
        </span>
      </div>
      <button class="rounded-full border border-white/10 px-2 py-0.5 text-xs text-slate-300" @click="emit('close')">✕</button>
    </header>

    <div v-if="results.length" class="grid grid-cols-3 gap-2 border-b border-white/5 px-3 py-2">
      <div
        v-for="r in results"
        :key="r.label"
        class="rounded-xl border px-2 py-1.5 text-center text-[10px]"
        :class="r.passed ? 'border-emerald-400/40 bg-emerald-500/10 text-emerald-200' : 'border-rose-400/40 bg-rose-500/10 text-rose-200'"
      >
        <p class="font-semibold">{{ r.label }}</p>
        <p>{{ r.score }}分</p>
      </div>
    </div>

    <div ref="bodyRef" class="flex-1 space-y-1.5 overflow-auto px-4 py-3 font-mono-tech text-[11px] leading-relaxed">
      <div v-for="(line, i) in lines" :key="i" class="text-slate-200">{{ line.text }}</div>
    </div>

    <div v-if="recommendation" class="border-t border-emerald-400/20 bg-emerald-500/10 px-4 py-2 text-xs text-emerald-100">
      {{ recommendation }}
    </div>
    <p v-if="running" class="px-4 py-1 text-[10px] text-sky-300 animate-pulse">正在穿越平行宇宙…</p>
  </div>
</template>

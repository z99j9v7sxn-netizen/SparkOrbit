<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';
import type { AgentStepItem } from '../../../api/admin';

const props = defineProps<{
  steps: AgentStepItem[];
  focusStep?: number | null;
}>();

const openPayload = ref<Record<number, boolean>>({});
const rowRefs = ref<Record<number, HTMLElement | null>>({});

watch(
  () => props.focusStep,
  async (idx) => {
    if (idx == null) return;
    await nextTick();
    const el = rowRefs.value[idx];
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  },
);

function setRowRef(idx: number, el: unknown) {
  rowRefs.value[idx] = (el as HTMLElement) || null;
}

function toggle(idx: number) {
  openPayload.value[idx] = !openPayload.value[idx];
}

function statusClass(status: string) {
  if (status === 'running') return 'text-amber-300 border-amber-400/30 bg-amber-500/10';
  if (status === 'completed') return 'text-emerald-300 border-emerald-400/30 bg-emerald-500/10';
  if (status === 'failed') return 'text-rose-300 border-rose-400/30 bg-rose-500/10';
  return 'text-slate-400 border-white/10 bg-white/5';
}

function fmt(iso: string) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}
</script>

<template>
  <div class="rounded-2xl border border-white/10 bg-slate-950/45">
    <div class="border-b border-white/10 px-4 py-3">
      <p class="font-mono-tech text-[10px] uppercase tracking-[0.3em] text-slate-500">Evidence</p>
      <h3 class="mt-1 text-sm font-medium text-white">步骤证据 · Findings</h3>
      <p class="mt-0.5 text-xs text-slate-500">每条对应 AgentStep 落库记录；缺摘要时显式保留空证据</p>
    </div>

    <div class="max-h-[360px] space-y-2 overflow-auto p-3">
      <article
        v-for="s in steps"
        :key="s.id"
        :ref="(el) => setRowRef(s.step_index, el)"
        class="rounded-xl border px-3 py-3 transition-colors"
        :class="
          focusStep === s.step_index
            ? 'border-cyan-400/40 bg-cyan-500/10'
            : 'border-white/8 bg-white/[0.03]'
        "
      >
        <div class="flex flex-wrap items-start justify-between gap-2">
          <div class="min-w-0">
            <p class="text-sm text-slate-100">
              <span class="font-mono-tech text-cyan-300/80">#{{ s.step_index }}</span>
              {{ s.agent_role }}
              <span v-if="s.parallel_group" class="ml-1 text-[10px] text-slate-500">· {{ s.parallel_group }}</span>
            </p>
            <p class="mt-1 text-xs leading-relaxed text-slate-400">
              {{ s.summary || '（无摘要 · 证据缺失显式标注）' }}
            </p>
          </div>
          <span class="shrink-0 rounded-md border px-2 py-0.5 text-[10px]" :class="statusClass(s.status)">
            {{ s.status }}
          </span>
        </div>
        <div class="mt-2 flex flex-wrap gap-3 font-mono-tech text-[10px] text-slate-600">
          <span>start {{ fmt(s.started_at) }}</span>
          <span>end {{ fmt(s.finished_at) }}</span>
        </div>
        <button
          type="button"
          class="mt-2 text-[11px] text-cyan-300/80 hover:text-cyan-200"
          @click="toggle(s.step_index)"
        >
          {{ openPayload[s.step_index] ? '收起 payload' : '展开 payload' }}
        </button>
        <pre
          v-if="openPayload[s.step_index]"
          class="mt-2 max-h-40 overflow-auto rounded-lg border border-white/5 bg-black/40 p-2 font-mono-tech text-[10px] text-slate-400"
        >{{ JSON.stringify(s.payload || {}, null, 2) }}</pre>
      </article>

      <div v-if="!steps.length" class="py-10 text-center text-sm text-slate-600">暂无步骤证据</div>
    </div>
  </div>
</template>

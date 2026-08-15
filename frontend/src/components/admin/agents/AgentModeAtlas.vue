<script setup lang="ts">
defineProps<{
  activeMode?: string;
  seeding?: boolean;
}>();

const emit = defineEmits<{
  (e: 'select', mode: string): void;
  (e: 'seed'): void;
}>();

const MODES = [
  {
    key: 'handoff',
    title: '顺序接力',
    en: 'Handoff',
    blurb: '子 Agent 顺序交接完成任务，互不并行干涉',
    accent: 'border-sky-400/40 bg-sky-500/10 text-sky-200',
    ring: 'ring-sky-400/40',
  },
  {
    key: 'workflow',
    title: '流水线编排',
    en: 'Workflow',
    blurb: '按 DAG 规划并行组与依赖，流水线完成任务',
    accent: 'border-cyan-400/40 bg-cyan-500/10 text-cyan-200',
    ring: 'ring-cyan-400/40',
  },
  {
    key: 'supervisor',
    title: '层级统筹',
    en: 'Supervisor',
    blurb: '主控统筹全局，按优先级把任务派给下属',
    accent: 'border-violet-400/40 bg-violet-500/10 text-violet-200',
    ring: 'ring-violet-400/40',
  },
  {
    key: 'council',
    title: '并行评议',
    en: 'Council',
    blurb: '同一任务多路并行思考，再汇总评议',
    accent: 'border-amber-400/40 bg-amber-500/10 text-amber-200',
    ring: 'ring-amber-400/40',
  },
] as const;
</script>

<template>
  <div class="space-y-3">
    <div class="flex flex-wrap items-end justify-between gap-2">
      <div>
        <p class="font-mono-tech text-[10px] uppercase tracking-[0.28em] text-slate-500">Mode Atlas</p>
        <h3 class="mt-1 text-sm font-medium text-white">四模式图鉴</h3>
        <p class="mt-0.5 text-xs text-slate-500">点卡片筛选；一键注入后可立刻对比四种流水线</p>
      </div>
      <button
        type="button"
        class="rounded-xl border border-teal-400/30 bg-teal-500/10 px-3 py-2 text-xs text-teal-100 hover:bg-teal-500/20 disabled:opacity-50"
        :disabled="seeding"
        @click="emit('seed')"
      >
        {{ seeding ? '注入中…' : '注入四模式演示数据' }}
      </button>
    </div>
    <div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
      <button
        v-for="m in MODES"
        :key="m.key"
        type="button"
        class="rounded-2xl border p-3 text-left transition-all"
        :class="[
          m.accent,
          activeMode === m.key ? `ring-2 ${m.ring}` : 'opacity-90 hover:opacity-100',
        ]"
        @click="emit('select', m.key)"
      >
        <p class="font-mono-tech text-[10px] uppercase tracking-widest opacity-80">{{ m.en }}</p>
        <p class="mt-1 text-sm font-semibold text-white">{{ m.title }}</p>
        <p class="mt-1.5 text-[11px] leading-relaxed text-slate-300/90">{{ m.blurb }}</p>
      </button>
    </div>
  </div>
</template>

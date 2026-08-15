<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string;
    short: string;
    score: number;
    status: string;
    evidence?: string[];
    expanded?: boolean;
    animate?: boolean;
  }>(),
  { evidence: () => [], expanded: false, animate: true },
);

const emit = defineEmits<{
  (e: 'select'): void;
}>();

function bandLabel(score: number): string {
  if (score < 40) return '偏弱';
  if (score < 60) return '待补';
  if (score < 80) return '均衡';
  return '优势';
}
</script>

<template>
  <button
    type="button"
    class="dim-meter group relative w-full overflow-hidden rounded-[var(--radius-card)] border py-2 pl-2.5 pr-2 text-left transition"
    :class="[
      score < 60
        ? 'border-amber-400/25 bg-amber-500/[0.05] hover:border-amber-400/45 hover:bg-amber-500/[0.08]'
        : 'dim-meter--strong',
      animate ? 'dim-meter--animate' : '',
    ]"
    @click="emit('select')"
  >
    <span
      class="absolute inset-y-2 left-0 w-0.5 rounded-full"
      :class="score < 60 ? 'bg-amber-400/80' : 'bg-[rgb(var(--lz-accent)/0.7)]'"
      aria-hidden="true"
    />
    <div class="flex items-baseline justify-between gap-1.5 pl-1">
      <div class="min-w-0">
        <p class="lz-caption truncate font-medium text-slate-100">{{ label }}</p>
        <p class="lz-caption mt-0.5 text-[9px]">{{ short }}</p>
      </div>
      <div class="flex shrink-0 items-baseline gap-1">
        <span
          class="rounded px-1 py-0.5 text-[8px] font-medium tracking-wide"
          :class="
            score < 60
              ? 'bg-amber-400/15 text-amber-200'
              : score < 80
                ? 'bg-[rgb(var(--lz-accent)/0.12)] lz-accent-text'
                : 'bg-emerald-400/15 text-emerald-200'
          "
        >{{ bandLabel(score) }}</span>
        <span
          class="min-w-[1.5rem] text-right font-mono text-xs font-semibold tabular-nums"
          :class="score < 60 ? 'text-amber-200' : 'lz-accent-text'"
        >{{ score }}</span>
      </div>
    </div>
    <div
      class="dim-meter__track relative mt-1.5 h-2 overflow-hidden rounded-full bg-white/[0.08] shadow-[inset_0_1px_2px_rgba(0,0,0,0.35)]"
    >
      <span
        v-for="tick in [25, 50, 75]"
        :key="tick"
        class="pointer-events-none absolute inset-y-0 w-px bg-white/10"
        :style="{ left: `${tick}%` }"
        aria-hidden="true"
      />
      <div
        class="dim-meter__fill relative h-full rounded-full"
        :class="
          score < 60
            ? 'dim-meter__fill--weak bg-gradient-to-r from-amber-500 to-orange-300'
            : 'dim-meter__fill--strong'
        "
        :style="{ width: `${Math.max(6, Math.min(100, score))}%` }"
      >
        <span
          class="dim-meter__dot absolute right-0 top-1/2 h-1.5 w-1.5 -translate-y-1/2 translate-x-1/2 rounded-full bg-white shadow-[0_0_6px_rgba(255,255,255,0.65)]"
          aria-hidden="true"
        />
      </div>
    </div>
    <div v-if="expanded" class="mt-2 border-t border-white/5 pl-1 pt-2">
      <p class="lz-body">{{ status }}</p>
      <p v-if="evidence?.length" class="lz-caption mt-1">
        证据：{{ evidence.slice(0, 2).join('；') }}
      </p>
    </div>
  </button>
</template>

<style scoped>
.dim-meter--strong {
  border-color: var(--border-soft);
  background: var(--surface-1);
}

.dim-meter--strong:hover {
  border-color: rgb(var(--lz-accent) / 0.35);
  background: rgb(var(--lz-accent) / 0.06);
}

.dim-meter__fill--strong {
  background: linear-gradient(90deg, rgb(var(--lz-accent) / 0.85), rgb(var(--lz-accent-bright)));
}

.dim-meter--animate .dim-meter__fill {
  transition: width 0.55s cubic-bezier(0.22, 1, 0.36, 1);
}

.dim-meter--animate .dim-meter__fill--weak {
  box-shadow: 0 0 14px rgba(251, 191, 36, 0.38);
}

.dim-meter--animate .dim-meter__fill--strong {
  box-shadow: 0 0 14px rgb(var(--lz-accent) / 0.32);
}

.dim-meter:hover .dim-meter__track {
  background-color: rgba(255, 255, 255, 0.11);
}

.dim-meter:hover .dim-meter__dot {
  box-shadow: 0 0 10px rgba(255, 255, 255, 0.85);
}

@media (prefers-reduced-motion: reduce) {
  .dim-meter--animate .dim-meter__fill {
    transition: none;
    box-shadow: none !important;
  }
}
</style>

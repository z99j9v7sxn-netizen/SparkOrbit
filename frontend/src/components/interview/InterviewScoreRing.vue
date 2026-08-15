<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    score: number | null | undefined;
    size?: number;
    showGrade?: boolean;
    label?: string;
  }>(),
  { size: 72, showGrade: true, label: '' },
);

const clamped = computed(() => Math.max(0, Math.min(100, Number(props.score ?? 0))));
const hasScore = computed(() => props.score != null);

const grade = computed(() => {
  if (!hasScore.value) return '—';
  const s = clamped.value;
  if (s >= 90) return 'S';
  if (s >= 80) return 'A';
  if (s >= 70) return 'B';
  if (s >= 60) return 'C';
  return 'D';
});

const gradeColor = computed(() => {
  if (!hasScore.value) return '#64748b';
  const s = clamped.value;
  if (s >= 80) return '#34d399';
  if (s >= 70) return '#fbbf24';
  if (s >= 60) return '#fb923c';
  return '#f87171';
});

const R = 42;
const C = 2 * Math.PI * R;
const dash = computed(() => `${(clamped.value / 100) * C} ${C}`);
</script>

<template>
  <div class="inline-flex flex-col items-center gap-1">
    <div class="relative" :style="{ width: `${size}px`, height: `${size}px` }">
      <svg viewBox="0 0 100 100" class="h-full w-full -rotate-90">
        <circle cx="50" cy="50" :r="R" fill="none" stroke="rgba(148,163,184,0.15)" stroke-width="8" />
        <circle
          v-if="hasScore"
          cx="50"
          cy="50"
          :r="R"
          fill="none"
          :stroke="gradeColor"
          stroke-width="8"
          stroke-linecap="round"
          :stroke-dasharray="dash"
          class="iv-ring-arc"
        />
      </svg>
      <div class="absolute inset-0 flex flex-col items-center justify-center leading-none">
        <span class="font-mono-tech font-semibold" :style="{ color: gradeColor, fontSize: `${size * 0.28}px` }">
          {{ hasScore ? Math.round(clamped) : '—' }}
        </span>
        <span v-if="showGrade && hasScore" class="mt-0.5 text-[10px] tracking-widest" :style="{ color: gradeColor }">
          {{ grade }} 级
        </span>
      </div>
    </div>
    <span v-if="label" class="text-[10px] text-slate-500">{{ label }}</span>
  </div>
</template>

<style scoped>
.iv-ring-arc {
  filter: drop-shadow(0 0 6px currentColor);
  transition: stroke-dasharray 0.6s ease;
}
</style>

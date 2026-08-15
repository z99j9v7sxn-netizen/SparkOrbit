<script setup lang="ts">
import { computed, toRef } from 'vue';
import { useCountUp } from '../../composables/useCountUp';

const props = defineProps<{
  label: string;
  value: string | number;
  accent?: 'default' | 'emerald' | 'rose' | 'amber' | 'sky';
  /** 环比趋势（百分比，正数向上，负数向下） */
  trend?: number;
  /** 趋势说明（如「较上周」） */
  trendLabel?: string;
}>();

const accentClass: Record<string, string> = {
  default: 'text-t-1',
  emerald: 'text-t-ok',
  rose: 'text-t-danger',
  amber: 'text-t-warn',
  sky: 'text-t-accent',
};

const numericValue = computed(() => (typeof props.value === 'number' ? props.value : null));
const animated = useCountUp(toRef(() => numericValue.value));
const display = computed(() => (numericValue.value === null ? props.value : animated.value));
const trendUp = computed(() => (props.trend ?? 0) >= 0);
</script>

<template>
  <div v-glow="{ tilt: true }" class="t-card t-card--hover console-stat p-4">
    <div class="flex items-start justify-between gap-2">
      <p class="text-[11px] font-medium uppercase tracking-[0.14em] text-t-3">{{ label }}</p>
      <span v-if="$slots.icon" class="shrink-0 text-t-accent/80"><slot name="icon" /></span>
    </div>
    <p class="mt-2 font-mono-tech text-2xl font-semibold tabular-nums" :class="accentClass[accent || 'default']">
      {{ display }}
    </p>
    <p v-if="trend !== undefined" class="mt-1.5 flex items-center gap-1 text-[11px]">
      <span
        class="inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 font-medium"
        :class="trendUp ? 'bg-t-ok/12 text-t-ok' : 'bg-t-danger/12 text-t-danger'"
      >
        <svg viewBox="0 0 12 12" class="h-2.5 w-2.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <path v-if="trendUp" d="M2 8.5 6 4l4 4.5M6 4v0" />
          <path v-else d="M2 3.5 6 8l4-4.5" />
        </svg>
        {{ Math.abs(trend).toFixed(1) }}%
      </span>
      <span class="text-t-3">{{ trendLabel || '较上期' }}</span>
    </p>
    <slot />
  </div>
</template>

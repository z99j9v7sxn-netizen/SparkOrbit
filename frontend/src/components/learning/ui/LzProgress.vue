<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    /** 0-100 */
    value: number;
    label?: string;
    showValue?: boolean;
  }>(),
  { label: '', showValue: false },
);

const clamped = computed(() => Math.max(0, Math.min(100, props.value)));
</script>

<template>
  <div>
    <div v-if="label || showValue" class="mb-1 flex items-center justify-between gap-2">
      <span v-if="label" class="lz-caption">{{ label }}</span>
      <span v-if="showValue" class="lz-caption lz-accent-text font-mono-tech">{{ Math.round(clamped) }}%</span>
    </div>
    <div class="lz-progress" role="progressbar" :aria-valuenow="Math.round(clamped)" aria-valuemin="0" aria-valuemax="100">
      <div class="lz-progress__bar" :style="{ width: `${clamped}%` }"></div>
    </div>
  </div>
</template>

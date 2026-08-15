<script setup lang="ts">
import StatusOrb from '../common/orb/StatusOrb.vue';

withDefaults(
  defineProps<{
    label?: string;
    variant?: 'spinner' | 'skeleton';
    rows?: number;
  }>(),
  { label: '', variant: 'skeleton', rows: 4 },
);
</script>

<template>
  <div v-if="variant === 'skeleton'" class="t-card--flat space-y-2 rounded-2xl border border-t-line/10 p-4">
    <div class="flex items-center gap-3">
      <div class="console-skeleton h-9 w-9 rounded-full" />
      <div class="flex-1 space-y-1.5">
        <div class="console-skeleton h-3.5 w-1/3" />
        <div class="console-skeleton h-3 w-1/5 opacity-70" />
      </div>
    </div>
    <div
      v-for="i in rows"
      :key="i"
      class="console-skeleton h-9 w-full"
      :style="{ animationDelay: `${i * 60}ms`, opacity: 1 - i * 0.12 }"
    />
  </div>
  <div v-else class="flex items-center justify-center gap-3 py-16 text-sm text-t-2">
    <StatusOrb state="loading" :size="28" />
    <span>{{ label || '加载中…' }}</span>
  </div>
</template>

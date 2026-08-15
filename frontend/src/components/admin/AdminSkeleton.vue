<script setup lang="ts">
withDefaults(
  defineProps<{
    rows?: number;
    variant?: 'table' | 'cards';
  }>(),
  { rows: 5, variant: 'table' },
);
</script>

<template>
  <div v-if="variant === 'table'" class="space-y-2 rounded-2xl border border-t-line/12 bg-t-s1/30 p-4">
    <div class="console-skeleton h-8 w-full opacity-70" />
    <div v-for="i in rows" :key="i" class="console-skeleton h-10 w-full" :style="{ animationDelay: `${i * 60}ms` }" />
  </div>
  <div v-else class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
    <div v-for="i in rows" :key="i" class="space-y-2 rounded-2xl border border-t-line/12 bg-t-s1/30 p-4">
      <div class="console-skeleton h-4 w-2/3" />
      <div class="console-skeleton h-3 w-1/2" />
      <div class="console-skeleton h-3 w-3/4" />
    </div>
  </div>
</template>

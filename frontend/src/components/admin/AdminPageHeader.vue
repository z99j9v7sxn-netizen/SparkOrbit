<script setup lang="ts">
withDefaults(
  defineProps<{
    kicker?: string;
    title: string;
    subtitle?: string;
  }>(),
  { kicker: '', subtitle: '' },
);
</script>

<template>
  <div class="flex flex-wrap items-end justify-between gap-3">
    <div class="min-w-0">
      <p v-if="kicker" class="t-kicker">{{ kicker }}</p>
      <h2 class="mt-1 text-xl font-semibold text-t-1">{{ title }}</h2>
      <p v-if="subtitle" class="mt-1 text-sm text-t-2">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions" class="flex flex-wrap items-center gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>

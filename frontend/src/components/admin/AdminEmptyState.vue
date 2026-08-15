<script setup lang="ts">
import StatusOrb from '../common/orb/StatusOrb.vue';

withDefaults(
  defineProps<{
    icon?: string;
    title: string;
    hint?: string;
  }>(),
  { icon: '', hint: '' },
);
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-t-line/20 bg-t-s1/20 px-6 py-12 text-center">
    <span v-if="icon" class="text-2xl text-t-3">{{ icon }}</span>
    <StatusOrb v-else state="offline" :size="48" class="opacity-80" />
    <p class="text-sm text-t-2">{{ title }}</p>
    <p v-if="hint" class="text-xs text-t-3">{{ hint }}</p>
    <slot />
  </div>
</template>

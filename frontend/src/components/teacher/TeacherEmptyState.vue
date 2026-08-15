<script setup lang="ts">
import StatusOrb from '../common/orb/StatusOrb.vue';

defineProps<{
  title?: string;
  description?: string;
}>();
</script>

<template>
  <div
    class="flex flex-col items-center justify-center rounded-2xl border border-dashed border-t-line/15 bg-t-s1/30 px-6 py-12 text-center"
  >
    <StatusOrb state="offline" :size="48" class="mb-3 opacity-70" />
    <p class="text-sm font-medium text-t-1/90">{{ title || '暂无数据' }}</p>
    <p v-if="description" class="mt-2 max-w-sm text-xs leading-relaxed text-t-3">{{ description }}</p>
    <div v-if="$slots.default" class="mt-4">
      <slot />
    </div>
  </div>
</template>

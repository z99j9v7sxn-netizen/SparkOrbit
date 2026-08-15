<script setup lang="ts">
withDefaults(
  defineProps<{
    flat?: boolean;
    hover?: boolean;
    active?: boolean;
    padding?: 'none' | 'sm' | 'md' | 'lg';
  }>(),
  { flat: false, hover: false, active: false, padding: 'md' },
);

const PAD: Record<string, string> = { none: '', sm: 'p-2.5', md: 'p-3.5', lg: 'p-5' };
</script>

<template>
  <div
    class="lz-card"
    :class="[
      flat ? 'lz-card--flat' : '',
      hover ? 'lz-card--hover' : '',
      active ? 'lz-card--active' : '',
      PAD[padding],
    ]"
  >
    <slot />
  </div>
</template>

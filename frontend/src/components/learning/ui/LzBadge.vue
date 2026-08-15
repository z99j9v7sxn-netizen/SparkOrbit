<script setup lang="ts">
withDefaults(
  defineProps<{
    tone?: 'accent' | 'neutral' | 'success' | 'warning' | 'danger';
  }>(),
  { tone: 'neutral' },
);
</script>

<template>
  <span class="lz-badge" :class="`lz-badge--${tone}`">
    <slot />
  </span>
</template>

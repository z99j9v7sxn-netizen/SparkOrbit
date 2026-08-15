<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'primary' | 'soft' | 'ghost' | 'danger';
    size?: 'sm' | 'md' | 'lg';
    loading?: boolean;
    disabled?: boolean;
    block?: boolean;
    type?: 'button' | 'submit';
  }>(),
  { variant: 'ghost', size: 'md', loading: false, disabled: false, block: false, type: 'button' },
);
</script>

<template>
  <button
    :type="type"
    class="lz-btn"
    :class="[`lz-btn--${variant}`, `lz-btn--${size}`, block ? 'w-full' : '']"
    :disabled="disabled || loading"
  >
    <span v-if="loading" class="lz-btn__spinner" aria-hidden="true"></span>
    <slot />
  </button>
</template>

<style scoped>
.lz-btn__spinner {
  width: 0.85em;
  height: 0.85em;
  border-radius: 999px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  animation: lz-spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes lz-spin {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .lz-btn__spinner {
    animation-duration: 1.6s;
  }
}
</style>

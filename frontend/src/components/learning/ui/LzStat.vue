<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string;
    value: string | number;
    unit?: string;
    hint?: string;
  }>(),
  { unit: '', hint: '' },
);
</script>

<template>
  <div class="lz-card lz-card--flat p-3">
    <p class="lz-caption">{{ label }}</p>
    <p class="mt-1 flex items-baseline gap-1">
      <span class="lz-stat__value font-mono-tech">{{ value }}</span>
      <span v-if="unit" class="lz-caption">{{ unit }}</span>
    </p>
    <p v-if="hint" class="lz-caption mt-0.5 opacity-80">{{ hint }}</p>
  </div>
</template>

<style scoped>
.lz-stat__value {
  font-size: 20px;
  font-weight: 600;
  line-height: 1.2;
  color: rgb(var(--lz-accent-bright));
  text-shadow: 0 0 16px rgb(var(--lz-accent) / 0.45);
}
</style>

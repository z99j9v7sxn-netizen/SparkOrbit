<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    desc?: string;
    /** 是否包一层卡片背景 */
    boxed?: boolean;
  }>(),
  { desc: '', boxed: false },
);
</script>

<template>
  <section :class="boxed ? 'lz-card p-3.5' : ''">
    <header class="mb-2.5 flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h3 class="lz-subtitle flex items-center gap-2">
          <span class="lz-section__dot" aria-hidden="true"></span>
          <span class="truncate">{{ title }}</span>
        </h3>
        <p v-if="desc" class="lz-caption mt-0.5">{{ desc }}</p>
      </div>
      <div v-if="$slots.actions" class="flex shrink-0 items-center gap-1.5">
        <slot name="actions" />
      </div>
    </header>
    <slot />
  </section>
</template>

<style scoped>
.lz-section__dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: rgb(var(--lz-accent-bright));
  box-shadow: 0 0 10px rgb(var(--lz-accent) / 0.8);
  flex-shrink: 0;
}
</style>

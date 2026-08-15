<script setup lang="ts">
withDefaults(
  defineProps<{
    icon?: string;
    title: string;
    desc?: string;
    actionText?: string;
  }>(),
  { icon: '✦', desc: '', actionText: '' },
);

const emit = defineEmits<{
  (e: 'action'): void;
}>();
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-2 px-4 py-10 text-center">
    <span class="lz-empty__icon" aria-hidden="true">{{ icon }}</span>
    <p class="lz-subtitle">{{ title }}</p>
    <p v-if="desc" class="lz-caption max-w-[26em]">{{ desc }}</p>
    <button v-if="actionText" type="button" class="lz-btn lz-btn--soft lz-btn--sm mt-2" @click="emit('action')">
      {{ actionText }}
    </button>
  </div>
</template>

<style scoped>
.lz-empty__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  border: 1px solid rgb(var(--lz-accent) / 0.25);
  background: rgb(var(--lz-accent) / 0.08);
  color: rgb(var(--lz-accent-bright));
  font-size: 18px;
  box-shadow: 0 0 24px -10px rgb(var(--lz-accent) / 0.5);
}
</style>

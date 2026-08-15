<script setup lang="ts">
import { computed } from 'vue';
import type { PetAction } from '../../api/pet';

const props = defineProps<{
  actions: PetAction[];
  open: boolean;
}>();

const emit = defineEmits<{
  (e: 'select', action: PetAction): void;
  (e: 'close'): void;
}>();

const displayActions = computed(() => props.actions.filter((a) => a.key !== 'idle'));
</script>

<template>
  <transition name="pet-menu">
    <div v-if="open" class="absolute bottom-full right-0 z-40 mb-2 w-56 rounded-2xl border border-sky-400/20 bg-slate-950/95 p-3 shadow-glow-lg backdrop-blur-xl">
      <div class="mb-2 flex items-center justify-between">
        <p class="text-[10px] uppercase tracking-[0.35em] text-sky-300/70">动作轮盘</p>
        <button class="text-xs text-slate-400 hover:text-white" @click="emit('close')">×</button>
      </div>
      <div class="grid grid-cols-3 gap-2">
        <button
          v-for="action in displayActions"
          :key="action.key"
          class="flex flex-col items-center gap-1 rounded-xl border border-white/10 bg-white/5 px-2 py-2 text-center transition hover:border-sky-400/30 hover:bg-sky-500/10"
          @click="emit('select', action)"
        >
          <span class="text-lg">{{ action.icon }}</span>
          <span class="text-[10px] text-slate-200">{{ action.label }}</span>
        </button>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.pet-menu-enter-active,
.pet-menu-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.pet-menu-enter-from,
.pet-menu-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>

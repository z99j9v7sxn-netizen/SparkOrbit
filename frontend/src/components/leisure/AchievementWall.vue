<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { fetchAchievements, type AchievementItem } from '../../api/zone';

const items = ref<AchievementItem[]>([]);
const prevUnlocked = ref<Set<string>>(new Set());
let pollTimer: number | null = null;

async function load() {
  items.value = await fetchAchievements().catch(() => []);
  for (const item of items.value) {
    if (item.unlocked && !prevUnlocked.value.has(item.id)) {
      window.dispatchEvent(new CustomEvent('sparkorbit:achievement-unlock', { detail: { id: item.id } }));
      prevUnlocked.value.add(item.id);
    }
  }
}

watch(items, (next) => {
  for (const item of next) {
    if (item.unlocked && !prevUnlocked.value.has(item.id)) {
      window.dispatchEvent(new CustomEvent('sparkorbit:achievement-unlock', { detail: { id: item.id } }));
      prevUnlocked.value.add(item.id);
    }
  }
}, { deep: true });

onMounted(() => {
  void load();
  pollTimer = window.setInterval(() => void load(), 15000);
});

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer);
});
</script>

<template>
  <div class="dock-panel grid gap-3 sm:grid-cols-2">
    <article
      v-for="item in items"
      :key="item.id"
      class="rounded-2xl border p-4"
      :class="item.unlocked ? 'border-amber-300/30 bg-amber-500/10' : 'border-white/10 bg-white/5 opacity-70'"
    >
      <p class="text-2xl">{{ item.icon }}</p>
      <p class="mt-2 text-sm font-semibold text-white">{{ item.name }}</p>
      <p class="mt-1 text-[11px] text-slate-400">{{ item.description }}</p>
      <div class="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-800">
        <div class="h-full rounded-full bg-gradient-to-r from-sky-400 to-amber-300" :style="{ width: `${Math.min(100, (item.progress / item.target) * 100)}%` }"></div>
      </div>
      <p class="mt-1 text-[10px] text-slate-400">{{ item.progress }}/{{ item.target }}</p>
    </article>
    <p v-if="!items.length" class="col-span-2 py-8 text-center text-sm text-slate-500">成就加载中或暂无数据</p>
  </div>
</template>

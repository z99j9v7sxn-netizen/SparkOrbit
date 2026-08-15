<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { fetchMilestones, type Milestone } from '../../api/zone';

const items = ref<Milestone[]>([]);

onMounted(async () => {
  items.value = await fetchMilestones().catch(() => []);
});
</script>

<template>
  <div class="relative space-y-4 pl-4 before:absolute before:bottom-0 before:left-[7px] before:top-0 before:w-px before:bg-sky-400/20">
    <article v-for="m in items" :key="m.id" class="relative pl-6">
      <span class="absolute left-0 top-1.5 h-3.5 w-3.5 rounded-full border-2 border-sky-400 bg-slate-950" />
      <p class="text-sm font-medium text-white">{{ m.achievement_name }}</p>
      <p class="mt-1 text-[10px] text-slate-500">{{ new Date(m.unlocked_at).toLocaleString() }}</p>
    </article>
    <p v-if="!items.length" class="py-6 text-center text-sm text-slate-500">完成成就后，里程碑会出现在这里</p>
  </div>
</template>

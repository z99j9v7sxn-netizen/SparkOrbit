<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { fetchStudyStreak, type StudyStreak } from '../../api/zone';

const data = ref<StudyStreak | null>(null);

onMounted(async () => {
  data.value = await fetchStudyStreak().catch(() => null);
});
</script>

<template>
  <div class="space-y-3 rounded-2xl border border-white/10 bg-black/20 p-4">
    <div class="flex items-center justify-between">
      <p class="text-xs font-medium text-violet-200">自习打卡日历</p>
      <span class="text-[11px] text-sky-200">连续 {{ data?.streak_days ?? 0 }} 天</span>
    </div>
    <div class="grid grid-cols-7 gap-1">
      <div
        v-for="cell in data?.calendar ?? []"
        :key="cell.day"
        class="aspect-square rounded-md text-center text-[8px] leading-[2rem]"
        :class="cell.studied ? 'bg-emerald-500/30 text-emerald-100' : 'bg-white/5 text-slate-500'"
        :title="cell.day"
      >
        {{ cell.day.slice(-2) }}
      </div>
    </div>
  </div>
</template>

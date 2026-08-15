<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import gsap from 'gsap';
import { fetchPetAffinity } from '../../api/pet';
import { fetchMasteryOverview, type MasteryOverview } from '../../api/learnExtras';
import { fetchAchievements, fetchFocusSummary, fetchMilestones, type AchievementItem, type FocusSummary, type Milestone } from '../../api/zone';
import { useAuthStore } from '../../stores/auth';
import PetStage from '../pet/PetStage.vue';

const emit = defineEmits<{ (e: 'open', dock: string): void }>();

const auth = useAuthStore();
const affinity = ref({ pet_affinity: 0, level: 0, level_name: '陌生' });
const focus = ref<FocusSummary | null>(null);
const mastery = ref<MasteryOverview | null>(null);
const achievements = ref<AchievementItem[]>([]);
const milestones = ref<Milestone[]>([]);

const rootRef = ref<HTMLElement | null>(null);

const unlockedCount = computed(() => achievements.value.filter((a) => a.unlocked).length);
const masteryAvg = computed(() => {
  const list = mastery.value?.by_galaxy ?? [];
  if (!list.length) return 0;
  return Math.round(list.reduce((sum, g) => sum + g.avg_score, 0) / list.length);
});
const topGalaxies = computed(() => (mastery.value?.by_galaxy ?? []).slice(0, 3));
const latestMilestone = computed(() => milestones.value[0] ?? null);

/** GSAP 数字滚动：data-count 元素从 0 滚到目标值 */
function rollNumbers() {
  const root = rootRef.value;
  if (!root) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  root.querySelectorAll<HTMLElement>('[data-count]').forEach((el) => {
    const target = Number(el.dataset.count ?? '0');
    const state = { n: 0 };
    gsap.to(state, {
      n: target,
      duration: 1.1,
      ease: 'power2.out',
      onUpdate: () => { el.textContent = String(Math.round(state.n)); },
    });
  });
}

onMounted(async () => {
  const [aff, foc, mas, ach, mil] = await Promise.all([
    fetchPetAffinity().catch(() => affinity.value),
    fetchFocusSummary().catch(() => null),
    fetchMasteryOverview().catch(() => null),
    fetchAchievements().catch(() => []),
    fetchMilestones().catch(() => []),
  ]);
  affinity.value = aff;
  focus.value = foc;
  mastery.value = mas;
  achievements.value = ach;
  milestones.value = mil;
  rollNumbers();
});
</script>

<template>
  <div ref="rootRef" class="lz-bento">
    <!-- 桌宠主卡：呼吸浮动 -->
    <button
      type="button"
      class="lz-hud-card lz-hud-card--hover lz-shine col-span-2 overflow-hidden p-5 text-left lg:col-span-3 lg:row-span-2"
      @click="emit('open', 'petdex')"
    >
      <p class="lz-hud-label">Companion // 桌宠图鉴</p>
      <div class="lz-float mx-auto mt-4 w-full max-w-[280px]">
        <PetStage :slug="auth.user?.petSlug" :affinity-level="affinity.level" />
      </div>
      <div class="mt-4 flex items-end justify-between gap-3">
        <div>
          <p class="text-lg font-semibold text-white">亲密度 Lv.{{ affinity.level }}</p>
          <p class="mt-0.5 text-xs text-slate-400">{{ affinity.level_name }} · {{ affinity.pet_affinity }} 点</p>
        </div>
        <span class="lz-badge lz-badge--accent">进入图鉴 →</span>
      </div>
    </button>

    <!-- 专注数据 -->
    <button
      type="button"
      class="lz-hud-card lz-hud-card--hover col-span-2 p-5 text-left lg:col-span-3"
      @click="emit('open', 'data')"
    >
      <p class="lz-hud-label">Focus Telemetry // 全景数据</p>
      <div class="mt-3 flex items-baseline gap-6">
        <div>
          <p class="text-3xl font-semibold text-white">
            <span :data-count="focus?.today_minutes ?? 0">0</span><span class="ml-1 text-sm font-normal text-slate-400">分钟</span>
          </p>
          <p class="mt-1 text-xs text-slate-500">今日专注</p>
        </div>
        <div>
          <p class="text-xl font-semibold text-slate-200">
            <span :data-count="focus?.week_minutes ?? 0">0</span><span class="ml-1 text-xs font-normal text-slate-500">分钟</span>
          </p>
          <p class="mt-1 text-xs text-slate-500">本周累计</p>
        </div>
        <div>
          <p class="text-xl font-semibold text-slate-200">
            <span :data-count="focus?.sessions ?? 0">0</span><span class="ml-1 text-xs font-normal text-slate-500">次</span>
          </p>
          <p class="mt-1 text-xs text-slate-500">专注场次</p>
        </div>
      </div>
    </button>

    <!-- 掌握度 -->
    <button
      type="button"
      class="lz-hud-card lz-hud-card--hover col-span-2 p-5 text-left lg:col-span-3"
      @click="emit('open', 'growth')"
    >
      <div class="flex items-center justify-between gap-3">
        <p class="lz-hud-label">Mastery // 成长总览</p>
        <p class="text-2xl font-semibold text-white"><span :data-count="masteryAvg">0</span><span class="text-xs font-normal text-slate-500"> / 100</span></p>
      </div>
      <div class="mt-3 space-y-2">
        <div v-for="g in topGalaxies" :key="g.galaxy_name" class="flex items-center gap-2">
          <span class="w-20 truncate text-[11px] text-slate-400">{{ g.galaxy_name }}</span>
          <div class="lz-progress flex-1">
            <span class="lz-progress__bar" :style="{ width: `${Math.min(100, Math.max(4, g.avg_score))}%` }"></span>
          </div>
          <span class="w-8 text-right text-[11px] text-slate-300">{{ Math.round(g.avg_score) }}</span>
        </div>
        <p v-if="!topGalaxies.length" class="lz-desc">暂无掌握度数据，去学习区点亮第一颗星球吧</p>
      </div>
    </button>

    <!-- 成就 -->
    <button
      type="button"
      class="lz-hud-card lz-hud-card--hover col-span-1 p-5 text-left lg:col-span-2"
      @click="emit('open', 'achievements')"
    >
      <p class="lz-hud-label">Medals // 成就</p>
      <p class="mt-3 text-3xl font-semibold text-white">
        <span :data-count="unlockedCount">0</span><span class="text-sm font-normal text-slate-500"> / {{ achievements.length }}</span>
      </p>
      <div class="lz-progress mt-3">
        <span
          class="lz-progress__bar"
          :style="{ width: `${achievements.length ? Math.round((unlockedCount / achievements.length) * 100) : 0}%` }"
        ></span>
      </div>
      <p class="mt-2 text-[11px] text-slate-500">已点亮成就</p>
    </button>

    <!-- 称号 -->
    <button
      type="button"
      class="lz-hud-card lz-hud-card--hover col-span-1 p-5 text-left lg:col-span-2"
      @click="emit('open', 'titles')"
    >
      <p class="lz-hud-label">Callsign // 称号</p>
      <p class="mt-3 truncate text-lg font-semibold" :class="auth.user?.equippedTitle ? 'text-amber-200' : 'text-slate-500'">
        {{ auth.user?.equippedTitle || '尚未佩戴' }}
      </p>
      <p class="mt-2 text-[11px] text-slate-500">当前佩戴的星际称号</p>
    </button>

    <!-- 里程碑 -->
    <button
      type="button"
      class="lz-hud-card lz-hud-card--hover col-span-2 p-5 text-left lg:col-span-2"
      @click="emit('open', 'milestones')"
    >
      <p class="lz-hud-label">Log // 里程碑</p>
      <template v-if="latestMilestone">
        <p class="mt-3 truncate text-sm font-semibold text-white">{{ latestMilestone.achievement_name }}</p>
        <p class="mt-1 text-[11px] text-slate-500">{{ latestMilestone.unlocked_at.slice(0, 10) }} 解锁</p>
      </template>
      <p v-else class="mt-3 text-sm text-slate-500">还没有里程碑记录</p>
      <p class="mt-2 text-[11px] text-slate-500">共 <span class="text-slate-300">{{ milestones.length }}</span> 条航行日志</p>
    </button>
  </div>
</template>

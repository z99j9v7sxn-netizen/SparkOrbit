<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';
import type { DockItem } from '../common/ZoneDock.vue';
import ZoneHeader from '../common/ZoneHeader.vue';
import MirrorDashboard from '../MirrorDashboard.vue';
import SimulationConsole from '../SimulationConsole.vue';
import PanoramicData from './PanoramicData.vue';
import MasteryGrowthPanel from './MasteryGrowthPanel.vue';
import AchievementWall from '../leisure/AchievementWall.vue';
import PetDex from './PetDex.vue';
import TitleEquip from './TitleEquip.vue';
import AchievementTimeline from './AchievementTimeline.vue';
import DomainOverview from './DomainOverview.vue';

const dock = ref<string>('overview');
const navigationOpen = ref(false);
const showSimConsole = ref(false);
const simConsoleRef = ref<InstanceType<typeof SimulationConsole> | null>(null);
const pendingSimTopic = ref<string | null>(null);
const pendingSimDimension = ref<string | undefined>(undefined);
const lastSimSummary = ref<{ topic: string; pathSteps: string[]; rootCause: string } | null>(null);

const items: DockItem[] = [
  { key: 'overview', iconSrc: '/icons/overview.svg', label: '指挥舱总览' },
  { key: 'petdex', iconSrc: '/icons/pet.svg', label: '桌宠图鉴' },
  { key: 'growth', iconSrc: '/icons/growth.svg', label: '成长总览' },
  { key: 'data', iconSrc: '/icons/data.svg', label: '全景数据' },
  { key: 'titles', iconSrc: '/icons/titles.svg', label: '称号' },
  { key: 'milestones', iconSrc: '/icons/milestones.svg', label: '里程碑' },
  { key: 'achievements', iconSrc: '/icons/medal.svg', label: '成就' },
];

type SimRequest = string | { topic: string; targetDimension?: string; planetSlug?: string };

const pendingSimPlanetSlug = ref<string | undefined>(undefined);

function onSimulate(payload: SimRequest) {
  const topic = typeof payload === 'string' ? payload : payload.topic;
  const dim = typeof payload === 'string' ? undefined : payload.targetDimension;
  const slug = typeof payload === 'string' ? undefined : payload.planetSlug;
  pendingSimTopic.value = topic;
  pendingSimDimension.value = dim;
  pendingSimPlanetSlug.value = slug;
  showSimConsole.value = true;
  void nextTick(() => {
    void nextTick(() => {
      if (simConsoleRef.value && pendingSimTopic.value) {
        const t = pendingSimTopic.value;
        const d = pendingSimDimension.value;
        const s = pendingSimPlanetSlug.value;
        pendingSimTopic.value = null;
        pendingSimDimension.value = undefined;
        pendingSimPlanetSlug.value = undefined;
        void simConsoleRef.value.run(t, {}, d, s ? { planetSlug: s } : undefined);
      }
    });
  });
}

watch(simConsoleRef, (console) => {
  if (console && pendingSimTopic.value) {
    const t = pendingSimTopic.value;
    const d = pendingSimDimension.value;
    const s = pendingSimPlanetSlug.value;
    pendingSimTopic.value = null;
    pendingSimDimension.value = undefined;
    pendingSimPlanetSlug.value = undefined;
    void console.run(t, {}, d, s ? { planetSlug: s } : undefined);
  }
});

function onSimComplete(payload: { topic: string; pathSteps: string[]; rootCause: string }) {
  lastSimSummary.value = payload;
}

function closeSimConsole() {
  showSimConsole.value = false;
}
</script>

<template>
  <div class="lz-accent-sky absolute inset-0 overflow-auto bg-slate-950/80 px-4 pb-24 pt-20 md:pl-24">
    <div class="domain-ambient pointer-events-none fixed inset-0" aria-hidden="true"></div>
    <div class="relative mx-auto max-w-6xl">
      <ZoneHeader
        eyebrow="My Domain // Command Deck"
        title="我的星域 · 个人指挥舱"
        desc="桌宠养成、成长画像、全景数据与成就时间轴"
      />
      <Transition name="zone-swap" mode="out-in">
        <div :key="dock" class="min-h-[32rem]">
          <DomainOverview v-if="dock === 'overview'" @open="dock = $event" />
          <div v-else class="lz-hud-card p-5 md:p-7">
            <PetDex v-if="dock === 'petdex'" />
            <div v-else-if="dock === 'growth'" class="grid gap-4 lg:grid-cols-2">
              <MirrorDashboard :sim-summary="lastSimSummary" @simulate="onSimulate" />
              <MasteryGrowthPanel />
            </div>
            <PanoramicData v-else-if="dock === 'data'" />
            <TitleEquip v-else-if="dock === 'titles'" />
            <AchievementTimeline v-else-if="dock === 'milestones'" />
            <AchievementWall v-else-if="dock === 'achievements'" />
          </div>
        </div>
      </Transition>
    </div>
    <nav
      class="absolute bottom-24 left-0 top-24 z-30 flex items-center"
      aria-label="我的星域功能导航"
      @mouseenter="navigationOpen = true"
      @mouseleave="navigationOpen = false"
    >
      <div
        class="domain-nav flex max-h-full flex-col gap-1.5 overflow-y-auto rounded-r-2xl border border-l-0 border-white/10 bg-slate-950/90 p-2 backdrop-blur-xl transition-[width,transform] duration-300"
        :class="navigationOpen ? 'w-44 translate-x-0' : 'w-16 -translate-x-2'"
      >
        <button
          v-for="item in items"
          :key="item.key"
          type="button"
          class="domain-nav-item flex h-12 shrink-0 items-center gap-3 rounded-xl px-3 text-left transition active:scale-[0.98]"
          :class="dock === item.key ? 'is-active' : ''"
          :title="item.label"
          @click="dock = item.key"
        >
          <img v-if="item.iconSrc" :src="item.iconSrc" alt="" class="h-5 w-5 shrink-0 opacity-90" />
          <span v-else-if="item.icon" class="w-6 shrink-0 text-center text-lg leading-none">{{ item.icon }}</span>
          <span v-if="navigationOpen" class="truncate text-xs tracking-wide">{{ item.label }}</span>
        </button>
      </div>
    </nav>

    <teleport to="body">
      <div
        v-if="showSimConsole"
        class="fixed inset-0 z-[120] flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm"
        @click.self="closeSimConsole"
      >
        <div class="h-[min(640px,90vh)] w-[min(900px,96vw)]">
          <SimulationConsole ref="simConsoleRef" @close="closeSimConsole" @complete="onSimComplete" />
        </div>
      </div>
    </teleport>
  </div>
</template>

<style scoped>
.domain-ambient {
  background:
    radial-gradient(ellipse 60% 40% at 20% -5%, rgb(var(--lz-accent) / 0.09), transparent 60%),
    radial-gradient(ellipse 45% 35% at 90% 10%, rgba(167, 139, 250, 0.06), transparent 55%);
}

.domain-nav {
  box-shadow: 0 0 32px -12px rgb(var(--lz-accent) / 0.35);
}

.domain-nav-item {
  color: rgb(148 163 184);
}

.domain-nav-item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #fff;
}

.domain-nav-item.is-active {
  background: rgb(var(--lz-accent) / 0.16);
  color: #fff;
  box-shadow: inset 0 0 0 1px rgb(var(--lz-accent) / 0.35), 0 0 18px -8px rgb(var(--lz-accent) / 0.6);
}
</style>

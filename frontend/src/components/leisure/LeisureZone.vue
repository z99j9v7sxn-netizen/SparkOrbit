<script setup lang="ts">
import { reactive, ref } from 'vue';
import ZoneDock, { type DockItem } from '../common/ZoneDock.vue';
import ZoneHeader from '../common/ZoneHeader.vue';
import AchievementWall from './AchievementWall.vue';
import MemoryMatchGame from './MemoryMatchGame.vue';
import MeteorDodgeGame from './MeteorDodgeGame.vue';
import PointsShop from './PointsShop.vue';
import StarLinkGame from './StarLinkGame.vue';
import ZodiacFortune from './ZodiacFortune.vue';
import SignInCalendar from './SignInCalendar.vue';
import PetPlayGame from './PetPlayGame.vue';
import FriendChallenge from './FriendChallenge.vue';

const emit = defineEmits<{ (e: 'pet-affinity'): void }>();

const dock = ref<string | null>(null);
const activeGame = ref<string | null>(null);
const items: DockItem[] = [
  { key: 'games', iconSrc: '/icons/games.svg', label: '游戏', accent: 'amber' },
  { key: 'signin', iconSrc: '/icons/calendar.svg', label: '签到', accent: 'amber' },
  { key: 'petplay', iconSrc: '/icons/pet.svg', label: '逗宠', accent: 'amber' },
  { key: 'challenge', iconSrc: '/icons/challenge.svg', label: '挑战', accent: 'amber' },
  { key: 'achievements', iconSrc: '/icons/medal.svg', label: '成就', accent: 'amber' },
  { key: 'shop', iconSrc: '/icons/shop.svg', label: '商城', accent: 'amber' },
  { key: 'fortune', iconSrc: '/icons/moon.svg', label: '运势', accent: 'amber' },
];

/** 每张游戏卡的专属霓虹渐变（Bento 大厅用） */
const games = [
  {
    key: 'memory', title: '星球记忆翻牌', icon: '/icons/planet.svg', desc: '配对星球卡片，训练短时记忆',
    tag: 'MEMORY MATRIX', glow: 'rgba(56, 189, 248, 0.5)',
    bg: 'linear-gradient(135deg, rgba(56, 189, 248, 0.2), rgba(99, 102, 241, 0.12) 55%, transparent)',
  },
  {
    key: 'meteor', title: '陨石躲避', icon: '/icons/meteor.svg', desc: '操控光球躲避陨石，刷新最高分',
    tag: 'METEOR RUSH', glow: 'rgba(251, 113, 133, 0.5)',
    bg: 'linear-gradient(135deg, rgba(251, 113, 133, 0.2), rgba(245, 158, 11, 0.12) 55%, transparent)',
  },
  {
    key: 'starlink', title: '星座连线', icon: '/icons/sparkle.svg', desc: '连接星点，还原星座图案',
    tag: 'CONSTELLATION', glow: 'rgba(167, 139, 250, 0.5)',
    bg: 'linear-gradient(135deg, rgba(167, 139, 250, 0.2), rgba(236, 72, 153, 0.12) 55%, transparent)',
  },
  {
    key: 'wheel', title: '每日星轨轮盘', icon: '/icons/wheel.svg', desc: '签到抽奖，赢取积分与运势',
    tag: 'LUCKY ORBIT', glow: 'rgba(245, 158, 11, 0.5)',
    bg: 'linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(212, 175, 55, 0.12) 55%, transparent)',
  },
  {
    key: 'petplay', title: '逗桌宠', icon: '/icons/pet.svg', desc: '连击小游戏，提升桌宠亲密度',
    tag: 'COMBO PLAY', glow: 'rgba(52, 211, 153, 0.5)',
    bg: 'linear-gradient(135deg, rgba(52, 211, 153, 0.2), rgba(56, 189, 248, 0.12) 55%, transparent)',
  },
];

/** hover 3D 倾斜：跟随鼠标的 rotateX/rotateY */
const tilt = reactive<Record<string, string>>({});
const tiltAllowed =
  typeof window !== 'undefined' &&
  window.matchMedia('(pointer: fine)').matches &&
  !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function onTilt(ev: MouseEvent, key: string) {
  if (!tiltAllowed) return;
  const el = ev.currentTarget as HTMLElement;
  const rect = el.getBoundingClientRect();
  const px = (ev.clientX - rect.left) / rect.width - 0.5;
  const py = (ev.clientY - rect.top) / rect.height - 0.5;
  tilt[key] = `perspective(900px) rotateX(${(-py * 6).toFixed(2)}deg) rotateY(${(px * 8).toFixed(2)}deg) translateY(-3px)`;
}

function resetTilt(key: string) {
  tilt[key] = '';
}

/** Dock 只负责跳转主区，避免与主区同时挂载同一游戏 */
function openGameFromDock(key: string) {
  activeGame.value = key;
  dock.value = null;
}
</script>

<template>
  <div class="lz-accent-amber absolute inset-0 overflow-auto px-4 pb-24 pt-20">
    <div class="arcade-ambient pointer-events-none fixed inset-0" aria-hidden="true"></div>
    <div class="relative mx-auto max-w-5xl">
      <ZoneHeader
        eyebrow="Leisure Zone // Star Arcade"
        title="休闲区 · 星际街机厅"
        desc="游戏 · 签到 · 逗桌宠 · 好友挑战 · 成就商城"
      />

      <Transition name="arcade-swap" mode="out-in">
        <!-- Bento 游戏大厅 -->
        <div v-if="!activeGame" key="lobby" class="grid gap-4 sm:grid-cols-2">
          <button
            v-for="(g, i) in games"
            :key="g.key"
            type="button"
            class="arcade-card group relative overflow-hidden rounded-3xl border border-white/10 p-5 text-left"
            :class="i === 0 ? 'sm:col-span-2 min-h-[180px]' : 'min-h-[160px]'"
            :style="{ transform: tilt[g.key] || '', '--card-glow': g.glow }"
            @mousemove="onTilt($event, g.key)"
            @mouseleave="resetTilt(g.key)"
            @click="activeGame = g.key"
          >
            <span class="arcade-card-bg absolute inset-0" :style="{ background: g.bg }" aria-hidden="true"></span>
            <img class="arcade-card-deco absolute select-none" :class="i === 0 ? '-right-4 -top-8 h-36 w-36' : '-right-3 -top-5 h-24 w-24'" :src="g.icon" alt="" aria-hidden="true" />
            <span class="lz-hud-label relative">{{ g.tag }}</span>
            <div class="relative mt-8 flex h-[calc(100%-2rem)] flex-col justify-end">
              <img class="h-9 w-9" :src="g.icon" alt="" aria-hidden="true" />
              <h3 class="arcade-card-title mt-2 font-semibold text-white" :class="i === 0 ? 'text-2xl' : 'text-lg'">{{ g.title }}</h3>
              <p class="mt-1 text-sm text-slate-400">{{ g.desc }}</p>
              <span class="mt-3 inline-flex items-center gap-1.5 text-xs text-amber-200 opacity-0 transition group-hover:opacity-100">
                INSERT COIN · 点击进入 →
              </span>
            </div>
          </button>
        </div>

        <!-- 上机：单游戏全屏区 -->
        <div v-else key="playing" class="space-y-4">
          <button class="arcade-back inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-xs" @click="activeGame = null">
            <span aria-hidden="true">←</span> 返回街机大厅
          </button>
          <div class="arcade-stage rounded-3xl border border-white/10 p-1">
            <MemoryMatchGame v-if="activeGame === 'memory'" />
            <MeteorDodgeGame v-else-if="activeGame === 'meteor'" />
            <StarLinkGame v-else-if="activeGame === 'starlink'" />
            <ZodiacFortune v-else-if="activeGame === 'wheel'" />
            <PetPlayGame v-else-if="activeGame === 'petplay'" @affinity="emit('pet-affinity')" />
          </div>
        </div>
      </Transition>
    </div>

    <ZoneDock v-model="dock" :items="items">
      <template #games>
        <div class="space-y-2">
          <p class="text-xs text-slate-400">在主区打开游戏，避免重复挂载</p>
          <button
            v-for="g in games"
            :key="g.key"
            type="button"
            class="lz-card lz-card--hover flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left"
            @click="openGameFromDock(g.key)"
          >
            <img class="h-6 w-6 shrink-0" :src="g.icon" alt="" aria-hidden="true" />
            <span>
              <span class="block text-sm text-white">{{ g.title }}</span>
              <span class="block text-[11px] text-slate-400">{{ g.desc }}</span>
            </span>
          </button>
        </div>
      </template>
      <template #signin><SignInCalendar /></template>
      <template #petplay>
        <PetPlayGame
          v-if="activeGame !== 'petplay'"
          @affinity="emit('pet-affinity')"
        />
        <p v-else class="text-xs text-slate-400">正在主区游玩「逗桌宠」，请先返回游戏中心。</p>
      </template>
      <template #challenge><FriendChallenge /></template>
      <template #achievements><AchievementWall /></template>
      <template #shop><PointsShop /></template>
      <template #fortune>
        <ZodiacFortune v-if="activeGame !== 'wheel'" />
        <p v-else class="text-xs text-slate-400">正在主区查看运势轮盘，请先返回游戏中心。</p>
      </template>
    </ZoneDock>
  </div>
</template>

<style scoped>
.arcade-ambient {
  background:
    radial-gradient(ellipse 55% 40% at 15% 0%, rgba(245, 158, 11, 0.09), transparent 60%),
    radial-gradient(ellipse 45% 35% at 90% 8%, rgba(236, 72, 153, 0.06), transparent 55%);
}

/* 霓虹游戏卡 */
.arcade-card {
  background: rgba(2, 6, 23, 0.55);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  transition: transform 0.18s ease-out, border-color 0.25s ease, box-shadow 0.25s ease;
  will-change: transform;
}

.arcade-card:hover {
  border-color: rgba(255, 255, 255, 0.22);
  box-shadow: 0 18px 60px -18px rgba(0, 0, 0, 0.7), 0 0 44px -12px var(--card-glow, rgba(245, 158, 11, 0.5));
}

/* 霓虹描边流光：hover 时旋转的 conic 光带 */
.arcade-card::before {
  content: '';
  position: absolute;
  inset: -60%;
  background: conic-gradient(
    from 0deg,
    transparent 0deg,
    var(--card-glow, rgba(245, 158, 11, 0.5)) 40deg,
    transparent 90deg,
    transparent 360deg
  );
  opacity: 0;
  transition: opacity 0.3s ease;
  animation: arcade-sweep 3.2s linear infinite paused;
  pointer-events: none;
}

.arcade-card::after {
  content: '';
  position: absolute;
  inset: 1.5px;
  border-radius: calc(1.5rem - 1.5px);
  background: rgba(2, 6, 23, 0.82);
  pointer-events: none;
}

.arcade-card:hover::before {
  opacity: 1;
  animation-play-state: running;
}

@keyframes arcade-sweep {
  to { transform: rotate(360deg); }
}

/* 卡片内容置于内衬遮罩（::after）之上，只让流光透出 1.5px 描边 */
.arcade-card > * {
  z-index: 1;
}

.arcade-card-deco {
  opacity: 0.14;
  filter: saturate(1.4);
  transition: transform 0.4s ease, opacity 0.3s ease;
}

.arcade-card:hover .arcade-card-deco {
  transform: rotate(-8deg) scale(1.08);
  opacity: 0.22;
}

.arcade-card-title {
  text-shadow: 0 0 24px var(--card-glow, rgba(245, 158, 11, 0.5));
}

/* 街机风返回胶囊 */
.arcade-back {
  border-color: rgb(var(--lz-accent) / 0.35);
  color: rgb(var(--lz-accent-bright));
  background: rgb(var(--lz-accent) / 0.08);
  transition: background 0.18s ease, box-shadow 0.18s ease;
}

.arcade-back:hover {
  background: rgb(var(--lz-accent) / 0.16);
  box-shadow: 0 0 20px -6px rgb(var(--lz-accent) / 0.6);
}

.arcade-stage {
  background:
    radial-gradient(90% 70% at 50% 0%, rgb(var(--lz-accent) / 0.06), transparent 60%),
    rgba(2, 6, 23, 0.5);
  box-shadow: 0 0 44px -16px rgb(var(--lz-accent) / 0.35);
}

/* 上机 / 返回转场 */
.arcade-swap-enter-active {
  transition: opacity 0.32s cubic-bezier(0.22, 1, 0.36, 1), transform 0.32s cubic-bezier(0.22, 1, 0.36, 1);
}

.arcade-swap-leave-active {
  transition: opacity 0.16s ease, transform 0.16s ease;
}

.arcade-swap-enter-from {
  opacity: 0;
  transform: scale(0.97) translateY(10px);
}

.arcade-swap-leave-to {
  opacity: 0;
  transform: scale(1.015);
}

@media (prefers-reduced-motion: reduce) {
  .arcade-card,
  .arcade-card-deco,
  .arcade-swap-enter-active,
  .arcade-swap-leave-active {
    transition: none;
  }

  .arcade-card::before {
    animation: none;
  }
}
</style>

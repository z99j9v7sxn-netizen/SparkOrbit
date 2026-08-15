<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { fetchClassmates } from '../../api/chat';
import {
  createGameChallenge,
  fetchPendingChallenges,
  respondGameChallenge,
  type GameChallenge,
} from '../../api/zone';
import { useOrbitStore } from '../../stores/orbit';
import MemoryMatchGame from './MemoryMatchGame.vue';
import MeteorDodgeGame from './MeteorDodgeGame.vue';
import StarLinkGame from './StarLinkGame.vue';

const orbit = useOrbitStore();
const classmates = ref<{ id: string; display_name: string }[]>([]);
const pending = ref<GameChallenge[]>([]);
const targetId = ref('');
const game = ref('memory');
const loading = ref(false);

/** challenge = 发起；respond = 应战某条挑战 */
const playMode = ref<'idle' | 'challenge' | 'respond'>('idle');
const activeChallenge = ref<GameChallenge | null>(null);
const playGameKey = ref('memory');
const lastScore = ref<number | null>(null);

const GAME_OPTIONS = [
  { key: 'memory', label: '星球记忆翻牌' },
  { key: 'meteor', label: '陨石躲避' },
  { key: 'starlink', label: '星座连线' },
];

const gameLabel = computed(
  () => GAME_OPTIONS.find((g) => g.key === playGameKey.value)?.label ?? playGameKey.value,
);

async function reload() {
  classmates.value = await fetchClassmates().catch(() => []);
  pending.value = await fetchPendingChallenges().catch(() => []);
}

function startChallengePlay() {
  if (!targetId.value) {
    orbit.pushNotification('好友挑战', '请先选择同学', 'warning');
    return;
  }
  playGameKey.value = game.value;
  lastScore.value = null;
  activeChallenge.value = null;
  playMode.value = 'challenge';
}

function startRespondPlay(ch: GameChallenge) {
  playGameKey.value = ch.game;
  lastScore.value = null;
  activeChallenge.value = ch;
  playMode.value = 'respond';
}

function cancelPlay() {
  playMode.value = 'idle';
  activeChallenge.value = null;
  lastScore.value = null;
}

async function onGameFinished(payload: { score: number; won: boolean }) {
  lastScore.value = payload.score;
  loading.value = true;
  try {
    if (playMode.value === 'challenge') {
      await createGameChallenge(targetId.value, playGameKey.value, payload.score);
      orbit.pushNotification('好友挑战', `已用得分 ${payload.score} 发起挑战`, 'success');
    } else if (playMode.value === 'respond' && activeChallenge.value) {
      await respondGameChallenge(activeChallenge.value.id, payload.score);
      orbit.pushNotification('好友挑战', `应战得分 ${payload.score}，结果已结算`, 'success');
      await reload();
    }
    playMode.value = 'idle';
    activeChallenge.value = null;
  } catch (e) {
    orbit.pushNotification('好友挑战', e instanceof Error ? e.message : '提交失败', 'warning');
  } finally {
    loading.value = false;
  }
}

onMounted(reload);
</script>

<template>
  <div class="dock-panel space-y-3">
    <template v-if="playMode === 'idle'">
      <p class="text-xs text-slate-400">选游戏玩一局，得分自动填入挑战（不可手填刷分）</p>
      <select v-model="targetId" class="cosmic-input w-full rounded-xl px-3 py-2 text-sm outline-none">
        <option value="">选择同学</option>
        <option v-for="c in classmates" :key="c.id" :value="c.id">{{ c.display_name }}</option>
      </select>
      <select v-model="game" class="cosmic-input w-full rounded-xl px-3 py-2 text-sm outline-none">
        <option v-for="g in GAME_OPTIONS" :key="g.key" :value="g.key">{{ g.label }}</option>
      </select>
      <button
        class="w-full rounded-full bg-sky-500/20 px-3 py-2 text-sm text-sky-100 disabled:opacity-40"
        :disabled="loading || !targetId"
        @click="startChallengePlay"
      >
        玩游戏并发起挑战
      </button>

      <div v-if="pending.length" class="space-y-2 border-t border-white/10 pt-3">
        <p class="text-xs text-amber-200">待应战</p>
        <div v-for="ch in pending" :key="ch.id" class="rounded-xl border border-white/10 bg-white/5 p-3 text-sm">
          <p class="text-white">{{ ch.challenger_name }} 挑战你 · {{ ch.game }}</p>
          <p class="mt-1 text-[11px] text-slate-400">对方分数 {{ ch.challenger_score }}</p>
          <button
            class="mt-2 rounded-lg border border-amber-400/20 px-3 py-1 text-[11px] text-amber-100 disabled:opacity-40"
            :disabled="loading"
            @click="startRespondPlay(ch)"
          >
            应战（玩游戏自动计分）
          </button>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="flex items-center justify-between gap-2">
        <p class="text-xs text-slate-300">
          {{ playMode === 'challenge' ? '发起挑战' : '应战' }} · {{ gameLabel }}
          <span v-if="lastScore !== null" class="text-amber-200"> · 得分 {{ lastScore }}</span>
        </p>
        <button
          class="rounded-lg border border-white/10 px-2 py-1 text-[11px] text-slate-400 hover:bg-white/5"
          :disabled="loading"
          @click="cancelPlay"
        >
          取消
        </button>
      </div>
      <p v-if="loading" class="text-center text-xs text-slate-400">正在提交得分…</p>
      <MemoryMatchGame v-else-if="playGameKey === 'memory'" @finished="onGameFinished" />
      <MeteorDodgeGame v-else-if="playGameKey === 'meteor'" @finished="onGameFinished" />
      <StarLinkGame v-else-if="playGameKey === 'starlink'" @finished="onGameFinished" />
      <p v-else class="text-xs text-rose-300">未知游戏：{{ playGameKey }}，请取消后重试</p>
    </template>
  </div>
</template>

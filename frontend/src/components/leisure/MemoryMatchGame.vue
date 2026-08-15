<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue';
import { postLeisureSession } from '../../api/zone';
import { useOrbitStore } from '../../stores/orbit';

const emit = defineEmits<{
  (e: 'finished', payload: { score: number; won: boolean }): void;
}>();

const orbit = useOrbitStore();

const EMOJIS = ['🪐', '⭐', '🌙', '☄️', '🛸', '🌌', '🔭', '🚀'] as const;

interface Card {
  id: number;
  emoji: string;
  flipped: boolean;
  matched: boolean;
}

const cards = ref<Card[]>([]);
const first = ref<number | null>(null);
const lock = ref(false);
const moves = ref(0);
const won = ref(false);
const settling = ref(false);
const resultHint = ref('');
let flipTimer: number | null = null;
let reported = false;

function shuffle<T>(arr: T[]): T[] {
  const out = [...arr];
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

function buildDeck(): Card[] {
  const pairs = EMOJIS.flatMap((emoji, idx) => [
    { id: idx * 2, emoji, flipped: false, matched: false },
    { id: idx * 2 + 1, emoji, flipped: false, matched: false },
  ]);
  return shuffle(pairs);
}

/** 挑战用：步数越少分越高 */
function challengeScore(moveCount: number) {
  return Math.max(1, 120 - moveCount * 5);
}

function clearFlipTimer() {
  if (flipTimer !== null) {
    window.clearTimeout(flipTimer);
    flipTimer = null;
  }
}

function reset() {
  clearFlipTimer();
  cards.value = buildDeck();
  first.value = null;
  lock.value = false;
  moves.value = 0;
  won.value = false;
  settling.value = false;
  resultHint.value = '';
  reported = false;
}

async function onClear() {
  if (reported) return;
  reported = true;
  won.value = true;
  settling.value = true;
  const score = challengeScore(moves.value);
  try {
    const res = await postLeisureSession('memory', score, true);
    resultHint.value = res.message;
    orbit.pushNotification('星球记忆翻牌', res.message, res.points_awarded > 0 ? 'success' : 'info');
  } catch (e) {
    resultHint.value = e instanceof Error ? e.message : '结算失败';
  } finally {
    settling.value = false;
    emit('finished', { score, won: true });
  }
}

function flip(cardId: number) {
  if (lock.value || won.value || settling.value) return;
  const card = cards.value.find((c) => c.id === cardId);
  if (!card || card.flipped || card.matched) return;

  card.flipped = true;
  if (first.value === null) {
    first.value = cardId;
    return;
  }

  moves.value += 1;
  const a = cards.value.find((c) => c.id === first.value)!;
  if (a.emoji === card.emoji) {
    a.matched = true;
    card.matched = true;
    first.value = null;
    if (cards.value.every((c) => c.matched)) void onClear();
    return;
  }

  lock.value = true;
  flipTimer = window.setTimeout(() => {
    a.flipped = false;
    card.flipped = false;
    first.value = null;
    lock.value = false;
    flipTimer = null;
  }, 700);
}

reset();
onBeforeUnmount(clearFlipTimer);
</script>

<template>
  <div class="space-y-4 rounded-3xl border border-white/10 bg-black/20 p-5">
    <header class="flex items-start justify-between gap-3">
      <div>
        <h3 class="text-lg font-semibold text-white">星球记忆翻牌</h3>
        <p class="mt-1 text-sm text-slate-400">
          步数 {{ moves }} · {{ won ? '恭喜通关！' : '找出全部 8 对星球' }}
        </p>
      </div>
      <button
        class="shrink-0 rounded-xl border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-40"
        :disabled="settling"
        @click="reset"
      >
        重开
      </button>
    </header>

    <div class="grid grid-cols-4 gap-3">
      <button
        v-for="card in cards"
        :key="card.id"
        type="button"
        class="flex aspect-square items-center justify-center rounded-2xl border text-2xl transition"
        :class="card.flipped || card.matched
          ? 'border-sky-400/30 bg-sky-500/10'
          : 'border-white/10 bg-black/30 hover:bg-white/5'"
        :disabled="lock || won || settling"
        @click="flip(card.id)"
      >
        {{ card.flipped || card.matched ? card.emoji : '?' }}
      </button>
    </div>

    <p v-if="resultHint" class="text-center text-xs text-slate-400">{{ resultHint }}</p>
  </div>
</template>

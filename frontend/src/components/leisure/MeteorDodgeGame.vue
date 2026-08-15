<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { postLeisureSession } from '../../api/zone';
import { useOrbitStore } from '../../stores/orbit';

const emit = defineEmits<{
  (e: 'finished', payload: { score: number; won: boolean }): void;
}>();

const orbit = useOrbitStore();

const W = 360;
const H = 240;
const PLAYER_R = 14;
const PLAYER_Y = H - 24;
const MOVE_SPEED = 220;

const canvasRef = ref<HTMLCanvasElement | null>(null);
const score = ref(0);
const playing = ref(false);
const settling = ref(false);
const resultHint = ref('');

let raf = 0;
let playerX = W / 2;
let meteors: { x: number; y: number; r: number; vy: number }[] = [];
let spawnAcc = 0;
let lastTs = 0;
let reported = false;
let keys = { left: false, right: false };

function endGame() {
  if (reported || !playing.value) return;
  reported = true;
  playing.value = false;
  cancelAnimationFrame(raf);
  raf = 0;
  settling.value = true;
  const finalScore = score.value;
  const won = finalScore >= 5;
  void postLeisureSession('meteor', finalScore, won)
    .then((res) => {
      resultHint.value = res.message;
      orbit.pushNotification('陨石躲避', res.message, res.points_awarded > 0 ? 'success' : 'info');
    })
    .catch((e: unknown) => {
      resultHint.value = e instanceof Error ? e.message : '结算失败';
    })
    .finally(() => {
      settling.value = false;
      emit('finished', { score: finalScore, won });
    });
}

function loop(ts: number) {
  const canvas = canvasRef.value;
  if (!canvas || !playing.value) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const dt = lastTs ? Math.min(0.05, (ts - lastTs) / 1000) : 0;
  lastTs = ts;

  if (keys.left) playerX -= MOVE_SPEED * dt;
  if (keys.right) playerX += MOVE_SPEED * dt;
  playerX = Math.max(PLAYER_R, Math.min(W - PLAYER_R, playerX));

  spawnAcc += dt;
  if (spawnAcc > 0.85) {
    spawnAcc = 0;
    meteors.push({
      x: Math.random() * (W - 24) + 12,
      y: -12,
      r: 8 + Math.random() * 10,
      vy: 90 + Math.random() * 120,
    });
  }

  ctx.fillStyle = '#050818';
  ctx.fillRect(0, 0, W, H);

  ctx.fillStyle = '#7dd3fc';
  ctx.beginPath();
  ctx.arc(playerX, PLAYER_Y, PLAYER_R, 0, Math.PI * 2);
  ctx.fill();

  let hit = false;
  meteors = meteors.filter((m) => {
    m.y += m.vy * dt;
    ctx.fillStyle = '#f472b6';
    ctx.beginPath();
    ctx.arc(m.x, m.y, m.r, 0, Math.PI * 2);
    ctx.fill();
    if (Math.hypot(m.x - playerX, m.y - PLAYER_Y) < m.r + PLAYER_R) {
      hit = true;
      return false;
    }
    if (m.y > H + 20) {
      score.value += 1;
      return false;
    }
    return true;
  });

  ctx.fillStyle = '#94a3b8';
  ctx.font = '12px sans-serif';
  ctx.fillText(`得分 ${score.value}`, 12, 20);

  if (hit) {
    endGame();
    return;
  }
  raf = requestAnimationFrame(loop);
}

function start() {
  if (settling.value) return;
  cancelAnimationFrame(raf);
  score.value = 0;
  meteors = [];
  playerX = W / 2;
  spawnAcc = 0;
  lastTs = 0;
  reported = false;
  resultHint.value = '';
  playing.value = true;
  raf = requestAnimationFrame(loop);
}

function setXFromClient(clientX: number) {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const scaleX = W / rect.width;
  playerX = Math.max(PLAYER_R, Math.min(W - PLAYER_R, (clientX - rect.left) * scaleX));
}

function onPointerMove(event: PointerEvent) {
  if (!playing.value) return;
  setXFromClient(event.clientX);
}

function onKeyDown(event: KeyboardEvent) {
  if (event.key === 'ArrowLeft' || event.key === 'a' || event.key === 'A') keys.left = true;
  if (event.key === 'ArrowRight' || event.key === 'd' || event.key === 'D') keys.right = true;
}

function onKeyUp(event: KeyboardEvent) {
  if (event.key === 'ArrowLeft' || event.key === 'a' || event.key === 'A') keys.left = false;
  if (event.key === 'ArrowRight' || event.key === 'd' || event.key === 'D') keys.right = false;
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown);
  window.addEventListener('keyup', onKeyUp);
});

onBeforeUnmount(() => {
  cancelAnimationFrame(raf);
  window.removeEventListener('keydown', onKeyDown);
  window.removeEventListener('keyup', onKeyUp);
});
</script>

<template>
  <div class="space-y-4 rounded-3xl border border-white/10 bg-black/20 p-5">
    <header class="flex items-start justify-between gap-3">
      <div>
        <h3 class="text-lg font-semibold text-white">陨石躲避</h3>
        <p class="mt-1 text-sm text-slate-400">触控 / 鼠标拖动，或 ← → / A D 控制光球</p>
      </div>
      <button
        class="shrink-0 rounded-xl border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-40"
        :disabled="playing || settling"
        @click="start"
      >
        {{ playing ? '进行中' : settling ? '结算中…' : score > 0 ? '再来一局' : '开始' }}
      </button>
    </header>

    <canvas
      ref="canvasRef"
      :width="W"
      :height="H"
      class="w-full touch-none rounded-2xl border border-white/10"
      :class="playing ? 'cursor-none' : 'cursor-default'"
      @pointermove="onPointerMove"
      @pointerdown="onPointerMove"
    />

    <p v-if="!playing && score > 0" class="text-center text-sm text-rose-300">游戏结束 · 得分 {{ score }}</p>
    <p v-if="resultHint" class="text-center text-xs text-slate-400">{{ resultHint }}</p>
  </div>
</template>

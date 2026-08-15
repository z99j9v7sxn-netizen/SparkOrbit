<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';
import { bumpPetAffinity } from '../../api/pet';
import { postLeisureSession } from '../../api/zone';
import { useAuthStore } from '../../stores/auth';
import { useOrbitStore } from '../../stores/orbit';
import PetStage from '../pet/PetStage.vue';

const emit = defineEmits<{ (e: 'affinity', delta: number): void }>();
const orbit = useOrbitStore();
const auth = useAuthStore();
const petStageRef = ref<InstanceType<typeof PetStage> | null>(null);

/** 与后端 record_leisure_session 中 pet-play 门槛保持一致 */
const MIN_SCORE = 15;
const MAX_SCORE = 40;
const ROUND_SECONDS = 15;

const score = ref(0);
const timeLeft = ref(ROUND_SECONDS);
const running = ref(false);
const settling = ref(false);
const resultHint = ref('');
let timer: number | null = null;
let finished = false;

const progressPct = computed(() => Math.min(100, (score.value / MIN_SCORE) * 100));
const rewardReady = computed(() => score.value >= MIN_SCORE);
const petSlug = computed(() => auth.user?.petSlug || 'boxcat');

function clearTimer() {
  if (timer) {
    window.clearInterval(timer);
    timer = null;
  }
}

function spawnTarget() {
  if (!running.value || finished || settling.value) return;
  score.value += 1;
  petStageRef.value?.playActionByKey('jump');
  if (score.value >= MAX_SCORE) finish(true);
}

function finish(won: boolean) {
  if (finished) return;
  finished = true;
  running.value = false;
  settling.value = true;
  clearTimer();

  void postLeisureSession('pet-play', score.value, won).then(async (res) => {
    resultHint.value = res.message;
    const kind = res.points_awarded > 0 ? 'success' : 'info';
    orbit.pushNotification('逗桌宠', res.message, kind);
    if (res.pet_affinity_delta) {
      emit('affinity', res.pet_affinity_delta);
      await bumpPetAffinity(res.pet_affinity_delta, 'pet-play');
    }
  }).finally(() => {
    settling.value = false;
  });
}

function start() {
  if (running.value || settling.value) return;
  clearTimer();
  finished = false;
  score.value = 0;
  timeLeft.value = ROUND_SECONDS;
  resultHint.value = '';
  running.value = true;
  timer = window.setInterval(() => {
    timeLeft.value -= 1;
    if (timeLeft.value <= 0) finish(score.value >= MIN_SCORE);
  }, 1000);
}

onBeforeUnmount(clearTimer);
</script>

<template>
  <div class="space-y-4 rounded-3xl border border-white/10 bg-black/20 p-5">
    <header>
      <h3 class="text-lg font-semibold text-white">逗桌宠 · 星尘连击</h3>
      <p class="mt-1 text-sm text-slate-400">{{ ROUND_SECONDS }} 秒内连击桌宠 · 至少 {{ MIN_SCORE }} 下才可获得积分</p>
    </header>
    <div class="flex items-center justify-between text-sm">
      <span class="text-sky-200">连击 {{ score }} / {{ MIN_SCORE }}</span>
      <span class="text-amber-200">剩余 {{ timeLeft }}s</span>
    </div>
    <div class="h-1.5 overflow-hidden rounded-full bg-slate-800">
      <div
        class="h-full rounded-full transition-all"
        :class="rewardReady ? 'bg-emerald-400' : 'bg-sky-400'"
        :style="{ width: `${progressPct}%` }"
      />
    </div>
    <p class="text-center text-[11px]" :class="rewardReady ? 'text-emerald-300' : 'text-slate-500'">
      {{ rewardReady ? '已达积分门槛，继续连击可获得更多奖励' : `还差 ${Math.max(0, MIN_SCORE - score)} 下解锁积分` }}
    </p>
    <div
      class="mx-auto flex h-32 w-32 cursor-pointer items-center justify-center rounded-full border border-sky-400/30 bg-sky-500/10 transition active:scale-95"
      :class="{ 'opacity-40 pointer-events-none': !running || settling }"
      role="button"
      tabindex="0"
      @click="spawnTarget"
      @keyup.enter="spawnTarget"
    >
      <PetStage ref="petStageRef" :slug="petSlug" class="pointer-events-none scale-90" />
    </div>
    <p v-if="resultHint && !running" class="text-center text-xs text-slate-400">{{ resultHint }}</p>
    <button
      class="w-full rounded-full bg-white px-4 py-2.5 text-sm font-semibold text-slate-900 disabled:opacity-50"
      :disabled="running || settling"
      @click="start"
    >
      {{ running ? '连击中…' : settling ? '结算中…' : '开始游戏' }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import {
  fetchGalaxies,
  fetchGalaxyDetail,
  startChallenge,
  submitChallenge,
  type Challenge,
  type Planet,
} from '../../api/orbit';
import { useOrbitStore } from '../../stores/orbit';
import { LzButton, LzSkeleton } from '../learning/ui';

withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false });
const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'fire-laser', isCorrect: boolean): void;
}>();

type Meteor = { x: number; y: number; speed: number; size: number; trail: number; alpha: number };
type Spark = { x: number; y: number; vx: number; vy: number; life: number; color: string };

const orbit = useOrbitStore();
const canvasRef = ref<HTMLCanvasElement | null>(null);
const challenge = ref<Challenge | null>(null);
const selected = ref('');
const result = ref<{ correct: boolean; answerKey: string; explanation: string } | null>(null);
const loading = ref(false);
const countdown = ref(18);
const shield = ref(100);
const score = ref(0);
const streak = ref(0);
const questionNumber = ref(0);
const error = ref('');
const sourcePlanets = ref<Planet[]>([]);
let sourceIndex = 0;
let raf = 0;
let timer = 0;
let lastFrame = 0;
let meteors: Meteor[] = [];
let sparks: Spark[] = [];
let laser = 0;
let impactFlash = 0;

const statusText = computed(() => {
  if (loading.value) return '正在锁定下一目标';
  if (result.value?.correct) return '目标已粉碎';
  if (result.value) return '护盾受损';
  return '陨石群正在逼近';
});

function seedMeteor(resetY = false): Meteor {
  return {
    x: 0.15 + Math.random() * 0.95,
    y: resetY ? -0.25 - Math.random() * 0.8 : Math.random() * 1.2 - 0.4,
    speed: 0.08 + Math.random() * 0.13,
    size: 2.5 + Math.random() * 5,
    trail: 35 + Math.random() * 80,
    alpha: 0.45 + Math.random() * 0.5,
  };
}

function resizeCanvas() {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const dpr = Math.min(window.devicePixelRatio, 2);
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
}

function spawnImpact(correct: boolean) {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const cx = canvas.width * 0.64;
  const cy = canvas.height * 0.38;
  const color = correct ? '#bfe9ff' : '#ff746c';
  for (let i = 0; i < 54; i++) {
    const angle = Math.random() * Math.PI * 2;
    const speed = 1 + Math.random() * 7;
    sparks.push({ x: cx, y: cy, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed, life: 30 + Math.random() * 28, color });
  }
  laser = correct ? 1 : 0;
  impactFlash = 1;
}

function draw(now: number) {
  const canvas = canvasRef.value;
  const ctx = canvas?.getContext('2d');
  if (!canvas || !ctx) return;
  const dt = Math.min((now - lastFrame) / 1000 || 0.016, 0.04);
  lastFrame = now;
  const w = canvas.width;
  const h = canvas.height;
  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0, '#03070f');
  g.addColorStop(1, '#071421');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);

  for (let i = 0; i < 100; i++) {
    const x = (i * 137.5) % w;
    const y = (i * 61.3) % h;
    ctx.fillStyle = `rgba(190,225,244,${0.12 + (i % 4) * 0.06})`;
    ctx.fillRect(x, y, 1.2, 1.2);
  }

  meteors.forEach((m) => {
    m.x -= m.speed * dt * 0.46;
    m.y += m.speed * dt;
    if (m.y > 1.2 || m.x < -0.2) Object.assign(m, seedMeteor(true));
    const x = m.x * w;
    const y = m.y * h;
    const length = m.trail * (w / 900);
    const trail = ctx.createLinearGradient(x + length, y - length, x, y);
    trail.addColorStop(0, 'rgba(125,211,252,0)');
    trail.addColorStop(0.72, `rgba(125,211,252,${m.alpha * 0.45})`);
    trail.addColorStop(1, `rgba(255,235,196,${m.alpha})`);
    ctx.strokeStyle = trail;
    ctx.lineWidth = Math.max(1, m.size * 0.35);
    ctx.beginPath();
    ctx.moveTo(x + length, y - length);
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.fillStyle = '#fff1ce';
    ctx.beginPath();
    ctx.arc(x, y, m.size * (w / 900), 0, Math.PI * 2);
    ctx.fill();
  });

  if (laser > 0) {
    ctx.strokeStyle = `rgba(150,225,255,${laser})`;
    ctx.lineWidth = 4;
    ctx.shadowColor = '#38bdf8';
    ctx.shadowBlur = 18;
    ctx.beginPath();
    ctx.moveTo(w * 0.08, h * 0.88);
    ctx.lineTo(w * 0.64, h * 0.38);
    ctx.stroke();
    ctx.shadowBlur = 0;
    laser = Math.max(0, laser - dt * 2.8);
  }

  sparks = sparks.filter((p) => {
    p.x += p.vx;
    p.y += p.vy;
    p.vy += 0.025;
    p.life -= 1;
    ctx.globalAlpha = Math.max(0, p.life / 58);
    ctx.fillStyle = p.color;
    ctx.fillRect(p.x, p.y, 2.4, 2.4);
    ctx.globalAlpha = 1;
    return p.life > 0;
  });

  if (impactFlash > 0) {
    ctx.fillStyle = `rgba(${result.value?.correct ? '180,230,255' : '255,70,70'},${impactFlash * 0.13})`;
    ctx.fillRect(0, 0, w, h);
    impactFlash = Math.max(0, impactFlash - dt * 2.4);
  }
  raf = requestAnimationFrame(draw);
}

async function prepareSources() {
  if (orbit.selectedPlanet) {
    sourcePlanets.value = [orbit.selectedPlanet];
    return;
  }
  if (orbit.currentGalaxy?.planets?.length) {
    sourcePlanets.value = orbit.currentGalaxy.planets.filter((p) => p.status !== 'locked');
    return;
  }
  const galaxies = await fetchGalaxies();
  if (!galaxies.length) return;
  const detail = await fetchGalaxyDetail(galaxies[0].slug);
  sourcePlanets.value = detail.planets.filter((p) => p.status !== 'locked');
}

async function loadNextQuestion() {
  loading.value = true;
  error.value = '';
  result.value = null;
  selected.value = '';
  countdown.value = 18;
  window.clearInterval(timer);
  try {
    if (!sourcePlanets.value.length) await prepareSources();
    const planet = sourcePlanets.value[sourceIndex % sourcePlanets.value.length];
    if (!planet) throw new Error('暂无可挑战的学习星球');
    sourceIndex += 1;
    challenge.value = await startChallenge(planet.slug);
    questionNumber.value += 1;
    timer = window.setInterval(() => {
      countdown.value -= 1;
      if (countdown.value <= 0) {
        window.clearInterval(timer);
        result.value = { correct: false, answerKey: '', explanation: '目标突破防线，系统已切换下一波。' };
        shield.value = Math.max(0, shield.value - 15);
        streak.value = 0;
        spawnImpact(false);
        emit('fire-laser', false);
      }
    }, 1000);
  } catch (e) {
    error.value = e instanceof Error ? e.message : '题目加载失败';
  } finally {
    loading.value = false;
  }
}

async function fire() {
  if (!challenge.value || !selected.value || result.value || loading.value) return;
  loading.value = true;
  window.clearInterval(timer);
  try {
    const response = await submitChallenge(challenge.value.challenge_id, selected.value);
    result.value = {
      correct: response.correct,
      answerKey: response.answer_key,
      explanation: response.explanation,
    };
    if (response.correct) {
      score.value += response.points || 50;
      streak.value += 1;
    } else {
      shield.value = Math.max(0, shield.value - 20);
      streak.value = 0;
    }
    spawnImpact(response.correct);
    emit('fire-laser', response.correct);
  } catch (e) {
    error.value = e instanceof Error ? e.message : '判定失败';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  meteors = Array.from({ length: 24 }, () => seedMeteor());
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);
  raf = requestAnimationFrame(draw);
  void loadNextQuestion();
});
onBeforeUnmount(() => {
  cancelAnimationFrame(raf);
  window.clearInterval(timer);
  window.removeEventListener('resize', resizeCanvas);
});
</script>

<template>
  <div class="flex h-full min-h-[560px] w-full flex-col overflow-hidden">
    <div class="grid min-h-0 flex-1 gap-4 lg:grid-cols-[1.2fr_.8fr]">
      <section
        class="relative min-h-[300px] overflow-hidden rounded-[var(--radius-panel)] border border-[rgb(var(--lz-accent)/0.15)] bg-[#03070f]"
      >
        <canvas ref="canvasRef" class="absolute inset-0 h-full w-full" />
        <div class="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between bg-gradient-to-b from-black/70 to-transparent p-5">
          <div>
            <p class="lz-caption lz-accent-text tracking-[0.32em] opacity-70">METEOR DEFENSE</p>
            <p class="lz-body mt-2">{{ statusText }}</p>
          </div>
          <div class="grid grid-cols-3 gap-5 text-right text-xs">
            <div>
              <span class="lz-caption block text-[9px]">SHIELD</span>
              <strong class="font-mono-tech text-rose-200">{{ shield }}</strong>
            </div>
            <div>
              <span class="lz-caption block text-[9px]">STREAK</span>
              <strong class="lz-accent-text font-mono-tech">{{ streak }}</strong>
            </div>
            <div>
              <span class="lz-caption block text-[9px]">SCORE</span>
              <strong class="lz-accent-text font-mono-tech">{{ score }}</strong>
            </div>
          </div>
        </div>
        <div class="pointer-events-none absolute bottom-5 left-5 right-5 flex items-end justify-between">
          <span class="lz-desc">第 {{ questionNumber }} 波</span>
          <span
            class="font-mono-tech text-4xl font-light text-slate-100 [text-shadow:0_0_32px_rgb(var(--lz-accent)/0.4)]"
          >
            {{ String(countdown).padStart(2, '0') }}
          </span>
        </div>
      </section>

      <section class="lz-card flex min-h-0 flex-col p-5">
        <div v-if="loading && !challenge" class="flex-1 py-4">
          <LzSkeleton preset="text" :rows="4" />
        </div>
        <template v-else-if="challenge">
          <p class="lz-caption tracking-[0.28em]">{{ challenge.planet_name }} / {{ challenge.difficulty }}</p>
          <h3 class="lz-title mt-3 leading-7">{{ challenge.question }}</h3>
          <div class="mt-4 space-y-2">
            <button
              v-for="option in challenge.options"
              :key="option.key"
              type="button"
              class="lz-card lz-card--hover flex w-full items-start gap-3 p-3 text-left text-sm text-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--lz-accent)/0.4)]"
              :class="[
                selected === option.key ? 'lz-card--active text-white' : '',
                result && option.key === result.answerKey ? '!border-emerald-300/50 !bg-emerald-300/10' : '',
                result && selected === option.key && !result.correct ? '!border-rose-300/50 !bg-rose-300/10' : '',
              ]"
              :disabled="Boolean(result)"
              @click="selected = option.key"
            >
              <span class="lz-accent-text font-mono-tech">{{ option.key }}</span>
              <span>{{ option.text }}</span>
            </button>
          </div>
          <p v-if="result" class="mt-4 text-xs leading-5" :class="result.correct ? 'text-emerald-200' : 'text-rose-200'">{{ result.explanation }}</p>
          <LzButton
            v-if="!result"
            variant="primary"
            size="lg"
            block
            class="mt-auto"
            :disabled="!selected || loading"
            @click="fire"
          >
            锁定并拦截
          </LzButton>
          <LzButton v-else variant="ghost" size="lg" block class="mt-auto" @click="loadNextQuestion">
            进入下一波
          </LzButton>
        </template>
        <p v-if="error" class="mt-3 text-xs text-rose-300">{{ error }}</p>
      </section>
    </div>
  </div>
</template>

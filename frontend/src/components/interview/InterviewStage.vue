<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { LzBadge, LzButton, LzInput, LzProgress } from '../learning/ui';
import { synthesizeSpeech } from '../../api/tts';
import { useAvatarVms } from '../../composables/useAvatarVms';
import { useInterviewSession } from '../../composables/useInterviewSession';
import { useInterviewVision } from '../../composables/useInterviewVision';

const props = defineProps<{ sessionId: string }>();
const emit = defineEmits<{ (e: 'finished', payload: { reportId: string; overallScore: number | null }): void }>();

const session = useInterviewSession();
const vms = useAvatarVms();
const {
  previewRef,
  error: visionError,
  captured,
  start: startVision,
  stop: stopVision,
  setMicOpen,
} = useInterviewVision();
const fallbackText = ref('');
const elapsed = ref(0);
const avatarRef = ref<HTMLDivElement | null>(null);
const avatarReady = ref(false);
const vmsStatusText = computed(() => vms.statusText.value);
const stageReady = ref(false);
let tick: number | null = null;
let audioEl: HTMLAudioElement | null = null;
let speakTimer: number | null = null;

watch(
  () => props.sessionId,
  (id) => {
    if (id && stageReady.value) session.connect(id);
  },
);

watch(
  () => session.question.value,
  async (q) => {
    if (!q?.text) return;
    await speak(q.text);
  },
);

watch(
  () => session.reportId.value,
  (id) => {
    if (id) emit('finished', { reportId: id, overallScore: session.overallScore.value });
  },
);

watch(
  () => session.sessionEnded.value,
  (ended) => {
    if (!ended) return;
    stopVision();
    session.stopMic();
    void vms.disable('面试结束，已断开数字人');
    clearSpeakTimer();
    audioEl?.pause();
    window.speechSynthesis?.cancel();
  },
);

watch(
  () => session.micGate.value,
  (gate) => {
    if (tick) window.clearInterval(tick);
    tick = null;
    elapsed.value = 0;
    setMicOpen(gate === 'open');
    if (gate === 'open') {
      tick = window.setInterval(() => {
        elapsed.value += 1;
      }, 1000);
    }
  },
);

function clearSpeakTimer() {
  if (speakTimer) window.clearTimeout(speakTimer);
  speakTimer = null;
}

function estimateSpeakMs(text: string) {
  return Math.min(22000, Math.max(2800, text.length * 260 + 800));
}

async function speak(text: string) {
  session.speaking.value = true;
  clearSpeakTimer();
  audioEl?.pause();
  window.speechSynthesis?.cancel();
  if (avatarReady.value) {
    try {
      const ok = await vms.speak(text);
      if (ok) {
        speakTimer = window.setTimeout(() => {
          void session.notifySpeakDone();
        }, estimateSpeakMs(text));
        return;
      }
    } catch {
      /* fall through to TTS */
    }
  }
  try {
    const blob = await synthesizeSpeech(text);
    const url = URL.createObjectURL(blob);
    audioEl = new Audio(url);
    audioEl.onended = () => {
      URL.revokeObjectURL(url);
      void session.notifySpeakDone();
    };
    await audioEl.play();
  } catch {
    if ('speechSynthesis' in window) {
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = 'zh-CN';
      utter.onend = () => {
        void session.notifySpeakDone();
      };
      window.speechSynthesis.speak(utter);
    } else {
      void session.notifySpeakDone();
    }
  }
}

onMounted(async () => {
  await nextTick();
  if (avatarRef.value) {
    try {
      await vms.enable(avatarRef.value);
      avatarReady.value = true;
    } catch {
      avatarReady.value = false;
    }
  }
  await startVision((dataUrl) => session.sendFrame(dataUrl));
  stageReady.value = true;
  if (props.sessionId) session.connect(props.sessionId);
});

onBeforeUnmount(() => {
  if (tick) window.clearInterval(tick);
  clearSpeakTimer();
  audioEl?.pause();
  window.speechSynthesis?.cancel();
  void vms.disable('面试结束，已断开数字人');
});
</script>

<template>
  <div v-if="session.sessionEnded.value" class="lz-card space-y-4 p-8 text-center">
    <LzBadge tone="warning">本场已结束</LzBadge>
    <h3 class="text-lg text-slate-100">正在生成三视角报告…</h3>
    <p class="text-sm text-slate-400">{{ session.progressText.value || session.statusHint.value }}</p>
    <ul class="mx-auto max-w-md space-y-1 text-left text-xs text-slate-500">
      <li v-for="(item, idx) in session.agentLog.value" :key="idx">{{ item.role }} · {{ item.content }}</li>
    </ul>
  </div>
  <div v-else class="space-y-4">
    <!-- 题目进度点 -->
    <div v-if="session.question.value" class="flex items-center gap-3">
      <div class="flex items-center gap-1.5">
        <span
          v-for="i in session.question.value.total"
          :key="i"
          class="h-1.5 rounded-full transition-all"
          :class="
            i - 1 < session.question.value.index
              ? 'w-5 bg-emerald-400/80'
              : i - 1 === session.question.value.index
                ? 'iv-dot-active w-8 bg-amber-300'
                : 'w-5 bg-white/10'
          "
          aria-hidden="true"
        ></span>
      </div>
      <span class="font-mono-tech text-[11px] tracking-widest text-slate-500">
        Q{{ session.question.value.index + 1 }}/{{ session.question.value.total }}
      </span>
      <span v-if="session.followupHint.value" class="rounded-full bg-rose-400/15 px-2 py-0.5 text-[10px] text-rose-200">
        追问轮
      </span>
    </div>

    <div class="grid gap-4 lg:grid-cols-[1.25fr_0.75fr]">
      <!-- 主画面：数字人 + 考生小窗 -->
      <section class="space-y-3">
        <div class="iv-stage-screen relative overflow-hidden rounded-2xl border border-amber-400/20 bg-slate-950">
          <div ref="avatarRef" class="min-h-[400px] w-full" />
          <p
            v-if="!avatarReady"
            class="pointer-events-none absolute inset-0 flex items-center justify-center text-xs text-slate-500"
          >
            {{ vmsStatusText || '数字人未连接，将使用语音播报' }}
          </p>
          <div class="pointer-events-none absolute inset-x-0 top-0 flex items-center justify-between px-4 py-3">
            <span class="rounded-full bg-slate-950/70 px-2.5 py-1 font-mono-tech text-[10px] tracking-widest text-amber-200/90">
              AI INTERVIEWER
            </span>
            <span
              class="flex items-center gap-1.5 rounded-full bg-slate-950/70 px-2.5 py-1 text-[10px]"
              :class="session.micGate.value === 'open' ? 'text-emerald-300' : 'text-slate-400'"
            >
              <span
                class="h-1.5 w-1.5 rounded-full"
                :class="session.micGate.value === 'open' ? 'iv-mic-live bg-emerald-400' : 'bg-slate-600'"
              ></span>
              {{ session.micGate.value === 'open' ? 'REC · 请开始回答' : '面试官讲话中' }}
            </span>
          </div>
          <video
            ref="previewRef"
            class="absolute bottom-3 right-3 h-28 w-20 rounded-xl border border-white/20 object-cover shadow-lg"
            muted
            playsinline
          />
          <!-- 字幕条 -->
          <div class="absolute inset-x-3 bottom-3 mr-24">
            <p
              v-if="session.caption.value"
              class="iv-caption rounded-xl bg-slate-950/80 px-3 py-2 text-sm leading-relaxed text-slate-100"
            >
              {{ session.caption.value }}
            </p>
          </div>
        </div>

        <div class="lz-card space-y-2 p-4">
          <p class="text-xs uppercase tracking-[0.2em] text-slate-500">{{ session.question.value?.kind_label || 'STANDBY' }}</p>
          <h3 class="text-lg leading-relaxed text-slate-100">{{ session.question.value?.text || '正在接入面试官…' }}</h3>
          <p v-if="session.followupHint.value" class="text-xs text-amber-200/90">追问：{{ session.followupHint.value }}</p>
          <p v-if="session.error.value" class="text-xs text-rose-300">{{ session.error.value }}</p>
          <p v-if="visionError" class="text-xs text-slate-500">视觉：{{ visionError }}（不影响语音作答）</p>
        </div>
      </section>

      <!-- 实时 HUD -->
      <section class="lz-card relative space-y-4 p-4">
        <div
          v-if="session.phase.value === 'scoring'"
          class="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 rounded-2xl bg-slate-950/85 px-6 text-center"
        >
          <LzProgress :value="62" label="评分中" />
          <p class="text-sm text-amber-100">{{ session.progressText.value || '正在并行评分…' }}</p>
          <p class="text-xs text-slate-500">语义与仪态同时进行，大约十几秒</p>
        </div>

        <p class="font-mono-tech text-[10px] uppercase tracking-widest text-slate-500">Live HUD</p>
        <div class="grid grid-cols-3 gap-2 text-center">
          <div class="rounded-xl border border-white/10 p-2">
            <p class="font-mono-tech text-lg text-amber-200">{{ elapsed }}s</p>
            <p class="text-[10px] text-slate-500">作答时长</p>
          </div>
          <div class="rounded-xl border border-white/10 p-2">
            <p class="font-mono-tech text-lg text-amber-200">{{ captured }}/4</p>
            <p class="text-[10px] text-slate-500">关键帧</p>
          </div>
          <div class="rounded-xl border border-white/10 p-2">
            <p class="font-mono-tech text-lg" :class="session.micGate.value === 'open' ? 'text-emerald-300' : 'text-slate-500'">
              {{ session.micGate.value === 'open' ? 'ON' : 'OFF' }}
            </p>
            <p class="text-[10px] text-slate-500">麦克风</p>
          </div>
        </div>

        <p class="text-xs text-slate-400">{{ session.statusHint.value }}</p>

        <div v-if="session.lastTurn.value?.fused_score != null" class="space-y-2 rounded-xl border border-amber-400/20 bg-amber-400/5 p-3">
          <p class="text-sm text-amber-100">
            第 {{ (session.lastTurn.value.turn_index ?? 0) + 1 }} 题 · 综合 {{ session.lastTurn.value.fused_score }} 分
          </p>
          <div class="space-y-1.5">
            <LzProgress
              v-if="session.lastTurn.value.semantic_score != null"
              :value="Number(session.lastTurn.value.semantic_score)"
              label="语义"
              show-value
            />
            <LzProgress
              v-if="session.lastTurn.value.prosody_score != null"
              :value="Number(session.lastTurn.value.prosody_score)"
              label="语调"
              show-value
            />
            <LzProgress
              v-if="session.lastTurn.value.visual_score != null"
              :value="Number(session.lastTurn.value.visual_score)"
              label="仪态"
              show-value
            />
          </div>
          <p v-if="session.lastTurn.value.feedback" class="text-xs leading-relaxed text-slate-400">
            {{ session.lastTurn.value.feedback }}
          </p>
        </div>

        <div class="flex flex-wrap gap-2">
          <LzButton variant="primary" :disabled="session.micGate.value !== 'open'" @click="session.submitAnswer()">
            回答完毕
          </LzButton>
          <LzButton variant="ghost" :disabled="!session.question.value || session.phase.value === 'scoring'" @click="session.notifySpeakDone()">
            跳过播报，直接作答
          </LzButton>
        </div>
        <div class="flex gap-2">
          <LzInput v-model="fallbackText" placeholder="语音不可用时，在此输入回答后提交" />
          <LzButton variant="soft" :disabled="!fallbackText.trim() || session.phase.value === 'scoring'" @click="session.submitTextFallback(fallbackText); fallbackText = ''">
            文本提交
          </LzButton>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.iv-stage-screen {
  box-shadow: 0 0 48px rgba(245, 158, 11, 0.08) inset;
}

.iv-dot-active {
  box-shadow: 0 0 10px rgba(252, 211, 77, 0.7);
}

.iv-mic-live {
  animation: iv-mic-pulse 1.1s ease-in-out infinite;
}

.iv-caption {
  backdrop-filter: blur(6px);
}

@keyframes iv-mic-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.6);
  }
  50% {
    box-shadow: 0 0 0 5px rgba(52, 211, 153, 0);
  }
}
</style>

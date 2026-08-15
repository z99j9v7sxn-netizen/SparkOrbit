<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from 'vue';
import { submitOralAudio, submitOralPractice, type OralPracticeResult } from '../../api/zone';
import { CANTONESE_MIME_CANDIDATES, DEFAULT_MIME_CANDIDATES, useAudioRecorder } from '../../composables/useAudioRecorder';
import { LzButton, LzInput, LzProgress } from '../learning/ui';

type Cabin = {
  id: string;
  name: string;
  description: string;
  speechLang: string;
  mode: 'speaking' | 'listening';
};

const CANTONESE_OPENING = '請用粵語講三句自我介紹，包括你嘅名字、興趣同今日做咗咩。';

const props = withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false });
const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'speak', text: string): void;
}>();

const cabins: Cabin[] = [
  { id: 'cet4-speaking', name: '英语四级口语舱', description: '校园与日常主题问答', speechLang: 'en-US', mode: 'speaking' },
  { id: 'cet6-speaking', name: '英语六级口语舱', description: '观点陈述与深入追问', speechLang: 'en-US', mode: 'speaking' },
  { id: 'ielts-speaking', name: '雅思口语舱', description: 'Part 1-3 模拟对话', speechLang: 'en-GB', mode: 'speaking' },
  { id: 'daily-english', name: '日常英语角', description: '生活场景自由交流', speechLang: 'en-US', mode: 'speaking' },
  { id: 'cet4-listening', name: '英语四级听力舱', description: '听材料后语音作答', speechLang: 'en-US', mode: 'listening' },
  { id: 'cantonese', name: '粤语学习舱', description: '原声录制 + 粤语发音评测', speechLang: 'zh-HK', mode: 'speaking' },
];

const selectedCabin = ref<Cabin | null>(null);
const userText = ref('');
const aiReply = ref('');
const coachPrompt = ref('');
const feedback = ref('');
const score = ref<number | null>(null);
const pronunciation = ref<OralPracticeResult['pronunciation']>(null);
const submittedAudioUrl = ref('');
const lastTranscript = ref('');
const sending = ref(false);
const statusHint = ref('');
const cameraActive = ref(false);
const cameraError = ref('');
const videoRef = ref<HTMLVideoElement | null>(null);
let cameraStream: MediaStream | null = null;

const isCantoneseCabin = computed(() => selectedCabin.value?.id === 'cantonese');

const {
  recording,
  elapsedSec,
  blob,
  objectUrl,
  error: recorderError,
  formatElapsed,
  start: startRecorder,
  stop: stopRecorder,
  reset: resetRecorder,
} = useAudioRecorder({
  preferMimeTypes: () => (isCantoneseCabin.value ? CANTONESE_MIME_CANDIDATES : DEFAULT_MIME_CANDIDATES),
});

function cabinOpening(cabin: Cabin) {
  if (cabin.mode === 'listening') {
    return 'Listening session ready. Tap “播放首题” to hear the first question.';
  }
  if (cabin.id === 'cantonese') return CANTONESE_OPENING;
  return 'Connection established. Record your answer, play it back, then upload.';
}

function applyCoachResult(result: OralPracticeResult) {
  aiReply.value = result.reply;
  feedback.value = result.feedback;
  score.value = result.score;
  coachPrompt.value = result.next_prompt?.trim() || result.reply?.trim() || coachPrompt.value;
}

function chooseCabin(cabin: Cabin) {
  selectedCabin.value = cabin;
  resetRecorder();
  submittedAudioUrl.value = '';
  lastTranscript.value = '';
  statusHint.value = '';
  const opening = cabinOpening(cabin);
  aiReply.value = opening;
  coachPrompt.value = cabin.id === 'cantonese' ? CANTONESE_OPENING : opening;
  feedback.value = '';
  score.value = null;
  pronunciation.value = null;
}

async function toggleCamera() {
  if (cameraActive.value) {
    cameraStream?.getTracks().forEach((track) => track.stop());
    cameraStream = null;
    cameraActive.value = false;
    return;
  }
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    cameraError.value = '视频预览需要 HTTPS 或 localhost 安全连接';
    return;
  }
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
    cameraActive.value = true;
    cameraError.value = '';
    await nextTick();
    if (videoRef.value) {
      videoRef.value.srcObject = cameraStream;
      await videoRef.value.play();
    }
  } catch (error) {
    const name = error instanceof DOMException ? error.name : '';
    cameraError.value = name === 'NotAllowedError' ? '摄像头权限被拒绝，请重新授权' : '无法启动视频预览';
  }
}

function speak(text: string) {
  if (!selectedCabin.value || !('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = selectedCabin.value.speechLang;
  utterance.rate = selectedCabin.value.mode === 'listening' ? 0.9 : 1;
  window.speechSynthesis.speak(utterance);
  emit('speak', text);
}

async function sendMsg(message = userText.value) {
  if (!selectedCabin.value || !message.trim() || sending.value) return;
  sending.value = true;
  feedback.value = '';
  statusHint.value = '';
  try {
    const result = await submitOralPractice(selectedCabin.value.id, message.trim(), selectedCabin.value.mode);
    applyCoachResult(result);
    userText.value = '';
    speak(result.reply);
  } catch (error) {
    feedback.value = error instanceof Error ? error.message : '通讯失败，请稍后重试';
  } finally {
    sending.value = false;
  }
}

async function uploadRecording() {
  if (!selectedCabin.value || !blob.value || sending.value) return;
  sending.value = true;
  feedback.value = '';
  lastTranscript.value = '';
  pronunciation.value = null;
  statusHint.value = '正在上传并评测录音…';
  const refText = coachPrompt.value || aiReply.value;
  try {
    const result = await submitOralAudio(
      selectedCabin.value.id,
      selectedCabin.value.mode,
      blob.value,
      elapsedSec.value,
      '',
      refText,
    );
    applyCoachResult(result);
    lastTranscript.value = result.transcript || '';
    pronunciation.value = result.pronunciation ?? null;
    submittedAudioUrl.value = result.audio_url || '';
    speak(result.reply);
    statusHint.value = '';
  } catch (error) {
    feedback.value = error instanceof Error ? error.message : '录音上传失败，请稍后重试';
    statusHint.value = '';
  } finally {
    sending.value = false;
  }
}

function toggleRecord() {
  if (recording.value) {
    stopRecorder();
    return;
  }
  void startRecorder();
}

function startListeningQuestion() {
  if (!selectedCabin.value) return;
  const prompt = 'Listen carefully. A student missed the bus because she left home late. Why did the student miss the bus?';
  aiReply.value = prompt;
  coachPrompt.value = prompt;
  speak(prompt);
}

onBeforeUnmount(() => {
  resetRecorder();
  window.speechSynthesis?.cancel();
  cameraStream?.getTracks().forEach((track) => track.stop());
});
</script>

<template>
  <component
    :is="embedded ? 'div' : 'aside'"
    :class="embedded ? 'flex h-full w-full flex-col' : 'cosmic-drawer absolute bottom-0 left-0 z-20 flex h-[640px] w-[720px] max-w-[94vw] flex-col rounded-tr-3xl border-r border-t border-white/10 p-5 shadow-2xl'"
  >
    <header v-if="!embedded" class="mb-4 flex items-center justify-between">
      <div>
        <h2 class="text-lg font-bold text-white text-glow">星际通讯舱</h2>
        <p class="lz-caption lz-accent-text uppercase tracking-widest opacity-80">Interstellar Comms</p>
      </div>
      <LzButton variant="ghost" size="sm" @click="emit('close')">✕</LzButton>
    </header>

    <div v-if="!selectedCabin" class="flex-1 overflow-auto">
      <div class="mb-5">
        <p class="lz-title">选择训练舱</p>
        <p class="lz-desc mt-1">录音后由后端完成转写与发音评测，教练给出综合点评。</p>
      </div>
      <div class="grid gap-3 md:grid-cols-2">
        <button
          v-for="cabin in cabins"
          :key="cabin.id"
          type="button"
          class="lz-card lz-card--hover p-4 text-left active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--lz-accent)/0.4)]"
          @click="chooseCabin(cabin)"
        >
          <span class="lz-subtitle block">{{ cabin.name }}</span>
          <span class="lz-desc mt-2 block">{{ cabin.description }}</span>
        </button>
      </div>
    </div>

    <div v-else class="grid min-h-0 flex-1 gap-4 overflow-auto lg:grid-cols-[280px_1fr]">
      <aside class="space-y-3">
        <div class="lz-card lz-card--flat relative aspect-video overflow-hidden bg-slate-950">
          <video
            v-if="cameraActive"
            ref="videoRef"
            class="h-full w-full scale-x-[-1] object-cover"
            autoplay
            muted
            playsinline
          ></video>
          <div v-else class="flex h-full flex-col items-center justify-center gap-3 text-center">
            <span class="text-3xl text-slate-600">◉</span>
            <LzButton variant="ghost" size="sm" @click="toggleCamera">开启视频预览</LzButton>
          </div>
          <button
            v-if="cameraActive"
            type="button"
            class="lz-caption absolute bottom-2 right-2 rounded-lg bg-slate-950/80 px-2 py-1 text-slate-200 hover:text-white"
            @click="toggleCamera"
          >
            关闭
          </button>
        </div>
        <p v-if="cameraError" class="text-[11px] text-amber-300">{{ cameraError }}</p>
        <div class="rounded-[var(--radius-card)] border border-[rgb(var(--lz-accent)/0.15)] bg-[rgb(var(--lz-accent)/0.06)] p-4">
          <div class="flex items-center gap-3">
            <div class="flex h-12 w-12 items-center justify-center rounded-full border border-[rgb(var(--lz-accent)/0.25)] bg-slate-950 text-xl">语</div>
            <div class="min-w-0">
              <p class="lz-subtitle">语言教练</p>
              <p class="lz-caption lz-accent-text truncate opacity-70">{{ selectedCabin.name }}</p>
            </div>
          </div>
          <div v-if="sending" class="mt-4 flex h-6 items-end gap-1" aria-label="教练正在回答">
            <span
              v-for="height in [8, 18, 12, 22, 10, 16]"
              :key="height"
              class="w-1 animate-pulse rounded-full bg-[rgb(var(--lz-accent-bright)/0.7)]"
              :style="{ height: `${height}px` }"
            ></span>
          </div>
          <p v-if="statusHint" class="lz-caption lz-accent-text mt-3 opacity-80">{{ statusHint }}</p>
        </div>
        <button
          type="button"
          class="lz-caption w-full text-left transition hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--lz-accent)/0.4)]"
          @click="selectedCabin = null; resetRecorder()"
        >
          ← 更换训练舱
        </button>
      </aside>

      <section class="flex min-h-[420px] flex-col">
        <div class="lz-card lz-card--flat flex-1 space-y-3 overflow-auto p-4">
          <div class="max-w-[90%] rounded-[var(--radius-card)] rounded-tl-sm border border-[rgb(var(--lz-accent)/0.15)] bg-[rgb(var(--lz-accent)/0.06)] p-4">
            <p class="text-sm leading-7 text-slate-100">{{ aiReply }}</p>
            <button
              type="button"
              class="lz-caption lz-accent-text mt-2 opacity-80 transition hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--lz-accent)/0.4)]"
              @click="speak(aiReply)"
            >
              重新播放
            </button>
          </div>
          <div v-if="feedback" class="lz-card ml-auto max-w-[90%] rounded-tr-sm p-4">
            <div class="flex items-center justify-between gap-3">
              <p class="lz-subtitle">教练点评</p>
              <span v-if="score !== null" class="lz-accent-text font-mono-tech text-sm font-semibold">{{ score }} 分</span>
            </div>
            <p class="lz-desc mt-2 leading-6">{{ feedback }}</p>
            <div v-if="pronunciation && pronunciation.total != null" class="lz-card lz-card--flat mt-3 space-y-2 px-2.5 py-2">
              <div class="flex items-center justify-between text-[11px]">
                <span class="lz-caption">发音总分</span>
                <span class="lz-accent-text font-mono-tech font-semibold">{{ pronunciation.total }}</span>
              </div>
              <div v-if="pronunciation.expected_jyutping" class="lz-caption leading-5">
                <span class="text-slate-500">标准粤拼：</span>{{ pronunciation.expected_jyutping }}
              </div>
              <div v-if="pronunciation.transcribed_jyutping" class="lz-caption leading-5">
                <span class="text-slate-500">识别粤拼：</span>{{ pronunciation.transcribed_jyutping }}
              </div>
              <LzProgress v-if="pronunciation.accuracy != null" :value="pronunciation.accuracy" label="准确度" show-value />
              <LzProgress v-if="pronunciation.fluency != null" :value="pronunciation.fluency" label="流利度" show-value />
              <LzProgress v-if="pronunciation.integrity != null" :value="pronunciation.integrity" label="完整度" show-value />
            </div>
            <p v-if="lastTranscript" class="lz-card lz-card--flat lz-caption mt-2 px-2.5 py-2 leading-5">
              转写：{{ lastTranscript }}
            </p>
            <a
              v-if="submittedAudioUrl"
              :href="submittedAudioUrl"
              target="_blank"
              class="lz-caption lz-accent-text mt-2 inline-block opacity-80 hover:opacity-100"
            >已提交录音链接</a>
          </div>
        </div>

        <div class="lz-card mt-3 p-3">
          <div class="flex flex-wrap items-center gap-2">
            <LzButton
              v-if="selectedCabin.mode === 'listening'"
              variant="ghost"
              size="md"
              class="shrink-0"
              @click="startListeningQuestion"
            >
              播放首题
            </LzButton>
            <LzButton
              :variant="recording ? 'danger' : 'soft'"
              size="md"
              class="shrink-0"
              :disabled="sending"
              @click="toggleRecord"
            >
              <span v-if="recording" class="inline-flex items-center gap-2">
                <span class="h-2 w-2 animate-pulse rounded-full bg-rose-400"></span>
                停止录音
              </span>
              <span v-else>{{ blob ? '重新录音' : '开始录音' }}</span>
            </LzButton>
            <span v-if="recording" class="text-sm font-medium tabular-nums text-rose-200">
              录音中 {{ formatElapsed(elapsedSec) }}
            </span>
            <span v-else-if="blob" class="lz-desc">
              已录 {{ formatElapsed(elapsedSec) }} · 可回放后上传
            </span>
          </div>

          <div v-if="objectUrl && !recording" class="mt-3 space-y-2">
            <audio :src="objectUrl" controls class="w-full"></audio>
            <div class="flex flex-wrap gap-2">
              <LzButton variant="primary" size="md" :disabled="sending || !blob" @click="uploadRecording">
                {{ sending ? (statusHint || '上传中…') : '上传作答' }}
              </LzButton>
              <LzButton variant="ghost" size="md" :disabled="sending" @click="resetRecorder">清除</LzButton>
            </div>
          </div>
          <p v-if="recorderError" class="mt-2 text-[11px] text-amber-300">{{ recorderError }}</p>
        </div>

        <div class="mt-2 flex gap-2">
          <LzInput
            v-model="userText"
            type="text"
            placeholder="也可以输入文字作为降级方式"
            class="min-w-0 flex-1"
            @enter="sendMsg()"
          />
          <LzButton variant="primary" size="md" :disabled="sending || !userText.trim()" @click="sendMsg()">
            发送
          </LzButton>
        </div>
      </section>
    </div>
  </component>
</template>

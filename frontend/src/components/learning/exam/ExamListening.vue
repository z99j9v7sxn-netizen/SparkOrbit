<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';
import {
  fetchListeningMaterial,
  logPractice,
  ttsToDataUrl,
  type ListeningMaterial,
} from '../../../api/exam';
import { useOrbitStore } from '../../../stores/orbit';
import { LzBadge, LzButton, LzCard, LzEmptyState, LzInput } from '../ui';

const props = defineProps<{ examType: string }>();
const emit = defineEmits<{ (e: 'activity'): void }>();

const orbit = useOrbitStore();
const material = ref<ListeningMaterial | null>(null);
const loading = ref(false);
const topic = ref('');
const showTranscript = ref(false);
const speed = ref(1.0);
const playing = ref(false);
const loopSentence = ref<number | null>(null);

// 听写模式
const dictation = ref(false);
const blankInputs = ref<Record<number, string>>({});
const dictationResult = ref<Record<number, boolean> | null>(null);

let audioEl: HTMLAudioElement | null = null;
const audioCache = new Map<string, string>();

const SPEEDS = [0.75, 1.0, 1.25, 1.5];

const maskedSentences = computed(() => {
  if (!material.value) return [];
  const blanks = material.value.blanks || [];
  return (material.value.sentences || []).map((s, i) => {
    let text = s;
    for (const b of blanks) {
      if (b.sentence_index === i && b.word) {
        const re = new RegExp(b.word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
        text = text.replace(re, '＿'.repeat(Math.max(3, b.word.length)));
      }
    }
    return text;
  });
});

async function generate() {
  loading.value = true;
  material.value = null;
  dictation.value = false;
  dictationResult.value = null;
  showTranscript.value = false;
  audioCache.clear();
  try {
    material.value = await fetchListeningMaterial(props.examType, topic.value);
  } catch (e) {
    orbit.pushNotification('听力精听', e instanceof Error ? e.message : '材料生成失败', 'warning');
  } finally {
    loading.value = false;
  }
}

async function play(text: string, key: string) {
  if (playing.value) {
    audioEl?.pause();
    playing.value = false;
    return;
  }
  playing.value = true;
  try {
    let url = audioCache.get(key);
    if (!url) {
      url = await ttsToDataUrl(text);
      audioCache.set(key, url);
    }
    audioEl?.pause();
    audioEl = new Audio(url);
    audioEl.playbackRate = speed.value;
    audioEl.onended = () => {
      if (loopSentence.value !== null && key === `s${loopSentence.value}` && audioEl) {
        audioEl.currentTime = 0;
        void audioEl.play();
      } else {
        playing.value = false;
      }
    };
    await audioEl.play();
  } catch {
    playing.value = false;
    orbit.pushNotification('听力精听', 'TTS 暂不可用，请查看原文训练', 'warning');
  }
}

function playFull() {
  if (!material.value) return;
  loopSentence.value = null;
  void play(material.value.transcript, 'full');
}

function playSentence(i: number) {
  if (!material.value) return;
  loopSentence.value = null;
  void play(material.value.sentences[i], `s${i}`);
}

function toggleLoop(i: number) {
  if (loopSentence.value === i) {
    loopSentence.value = null;
    audioEl?.pause();
    playing.value = false;
  } else {
    loopSentence.value = i;
    void play(material.value!.sentences[i], `s${i}`);
  }
}

function setSpeed(s: number) {
  speed.value = s;
  if (audioEl) audioEl.playbackRate = s;
}

async function checkDictation() {
  if (!material.value) return;
  const blanks = material.value.blanks || [];
  const result: Record<number, boolean> = {};
  let correct = 0;
  blanks.forEach((b, i) => {
    const ok = (blankInputs.value[i] || '').trim().toLowerCase() === b.word.trim().toLowerCase();
    result[i] = ok;
    if (ok) correct += 1;
  });
  dictationResult.value = result;
  try {
    await logPractice({
      exam_type: props.examType,
      section: 'listening',
      activity: 'dictation',
      total: blanks.length,
      correct,
    });
    emit('activity');
  } catch {
    /* 忽略 */
  }
  orbit.pushNotification('听写填空', `${correct} / ${blanks.length} 正确`, correct === blanks.length ? 'success' : 'info');
}

onBeforeUnmount(() => audioEl?.pause());
</script>

<template>
  <div class="space-y-3">
    <template v-if="!material">
      <LzEmptyState
        v-if="!loading"
        icon="🎧"
        title="听力精听训练"
        desc="AI 生成考试风格听力短文 + 讯飞语音合成，支持倍速、逐句循环与听写填空"
      >
        <div class="mt-3 flex w-full max-w-sm flex-col gap-2">
          <LzInput v-model="topic" placeholder="题材偏好（可选，如：校园生活 / 科技新闻）" />
          <LzButton variant="primary" @click="generate">生成精听材料</LzButton>
        </div>
      </LzEmptyState>
      <LzCard v-else padding="lg" class="text-center">
        <p class="lz-desc">正在生成听力材料…</p>
      </LzCard>
    </template>

    <template v-else>
      <div class="flex items-center justify-between gap-2">
        <p class="lz-subtitle">{{ material.title }}</p>
        <LzButton size="sm" variant="ghost" @click="generate">换一篇</LzButton>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <LzButton size="sm" variant="primary" @click="playFull">{{ playing ? '⏸ 暂停' : '▶ 全文播放' }}</LzButton>
        <div class="flex items-center gap-1">
          <button
            v-for="s in SPEEDS"
            :key="s"
            type="button"
            class="rounded-full border px-2 py-0.5 text-[10px] transition"
            :class="speed === s ? 'border-sky-400/60 bg-sky-500/20 text-sky-100' : 'border-white/10 text-slate-400'"
            @click="setSpeed(s)"
          >
            {{ s }}x
          </button>
        </div>
        <LzButton size="sm" variant="soft" @click="showTranscript = !showTranscript">
          {{ showTranscript ? '隐藏原文' : '原文对照' }}
        </LzButton>
        <LzButton size="sm" :variant="dictation ? 'soft' : 'ghost'" @click="dictation = !dictation">
          {{ dictation ? '退出听写' : '听写填空' }}
        </LzButton>
      </div>

      <!-- 听写模式 -->
      <template v-if="dictation">
        <LzCard padding="md" class="space-y-2">
          <p class="lz-desc">听音频，把挖空的关键词填回去：</p>
          <p class="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">
            {{ maskedSentences.join(' ') }}
          </p>
        </LzCard>
        <div class="space-y-1.5">
          <div v-for="(b, i) in material.blanks" :key="i" class="flex items-center gap-2">
            <LzBadge :tone="dictationResult ? (dictationResult[i] ? 'success' : 'danger') : 'neutral'">
              空 {{ i + 1 }}
            </LzBadge>
            <LzInput
              :model-value="blankInputs[i] || ''"
              placeholder="填写听到的词"
              class="flex-1"
              @update:model-value="(v: string) => (blankInputs[i] = v)"
            />
            <span v-if="dictationResult && !dictationResult[i]" class="lz-caption text-rose-300">{{ b.word }}</span>
          </div>
        </div>
        <LzButton variant="primary" block @click="checkDictation">核对答案</LzButton>
      </template>

      <!-- 逐句精听 -->
      <div v-else class="space-y-1.5">
        <div
          v-for="(s, i) in material.sentences"
          :key="i"
          class="flex items-start gap-2 rounded-lg border border-white/10 p-2"
          :class="loopSentence === i ? 'border-sky-400/40 bg-sky-500/10' : ''"
        >
          <div class="flex shrink-0 gap-1">
            <button type="button" class="rounded border border-white/10 px-1.5 py-0.5 text-[10px] text-slate-300 hover:bg-white/10" @click="playSentence(i)">▶</button>
            <button
              type="button"
              class="rounded border px-1.5 py-0.5 text-[10px] transition"
              :class="loopSentence === i ? 'border-sky-400/60 bg-sky-500/20 text-sky-100' : 'border-white/10 text-slate-400'"
              @click="toggleLoop(i)"
            >
              🔁
            </button>
          </div>
          <p class="text-xs leading-relaxed" :class="showTranscript ? 'text-slate-200' : 'text-transparent select-none blur-sm'">
            {{ s }}
          </p>
        </div>
        <p v-if="!showTranscript" class="lz-caption text-center">句子已模糊处理 — 先精听，再开「原文对照」核对</p>
      </div>

      <details v-if="showTranscript && material.translation" class="lz-card p-3">
        <summary class="lz-caption cursor-pointer">中文翻译</summary>
        <p class="lz-desc mt-2 whitespace-pre-wrap">{{ material.translation }}</p>
      </details>
    </template>
  </div>
</template>

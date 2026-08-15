<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import {
  collectWord,
  fetchWords,
  logPractice,
  seedWords,
  ttsToDataUrl,
  type ExamWord,
} from '../../../api/exam';
import { useOrbitStore } from '../../../stores/orbit';
import { LzBadge, LzButton, LzCard, LzEmptyState, LzInput } from '../ui';

const props = defineProps<{ examType: string }>();
const emit = defineEmits<{ (e: 'activity'): void }>();

const orbit = useOrbitStore();
const words = ref<ExamWord[]>([]);
const total = ref(0);
const offset = ref(0);
const loading = ref(false);
const seeding = ref(false);
const collected = ref<Set<string>>(new Set());

// 打字训练态
const typingMode = ref(false);
const typingIndex = ref(0);
const typed = ref('');
const typingStats = ref({ total: 0, correct: 0, startedAt: 0, chars: 0 });
const typingFeedback = ref<'idle' | 'correct' | 'wrong'>('idle');
const playingAudio = ref(false);
let audioEl: HTMLAudioElement | null = null;

const PAGE = 10;
const currentWord = computed(() => words.value[typingIndex.value] ?? null);
const wpm = computed(() => {
  if (!typingStats.value.startedAt || !typingStats.value.chars) return 0;
  const minutes = (Date.now() - typingStats.value.startedAt) / 60000;
  return minutes > 0 ? Math.round(typingStats.value.chars / 5 / minutes) : 0;
});

watch(
  () => props.examType,
  () => {
    offset.value = 0;
    typingMode.value = false;
    void load();
  },
  { immediate: true },
);

async function load() {
  loading.value = true;
  try {
    const res = await fetchWords(props.examType, offset.value, PAGE);
    words.value = res.words;
    total.value = res.total;
  } catch {
    words.value = [];
  } finally {
    loading.value = false;
  }
}

async function seed() {
  seeding.value = true;
  try {
    const res = await seedWords(props.examType, 30);
    orbit.pushNotification('词书', `已生成 ${res.added} 个高频词`, 'success');
    await load();
  } catch (e) {
    orbit.pushNotification('词书', e instanceof Error ? e.message : '生成失败', 'warning');
  } finally {
    seeding.value = false;
  }
}

async function collect(w: ExamWord) {
  try {
    await collectWord(w.id);
    collected.value = new Set([...collected.value, w.id]);
    orbit.pushNotification('生词本', `「${w.word}」已加入复习队列`, 'success');
  } catch (e) {
    orbit.pushNotification('生词本', e instanceof Error ? e.message : '收藏失败', 'warning');
  }
}

async function playWord(text: string) {
  if (playingAudio.value) return;
  playingAudio.value = true;
  try {
    const url = await ttsToDataUrl(text);
    audioEl?.pause();
    audioEl = new Audio(url);
    await audioEl.play();
  } catch {
    orbit.pushNotification('发音', 'TTS 暂不可用', 'warning');
  } finally {
    playingAudio.value = false;
  }
}

function startTyping() {
  if (!words.value.length) return;
  typingMode.value = true;
  typingIndex.value = 0;
  typed.value = '';
  typingFeedback.value = 'idle';
  typingStats.value = { total: 0, correct: 0, startedAt: Date.now(), chars: 0 };
  void playWord(words.value[0].word);
}

async function submitTyped() {
  const w = currentWord.value;
  if (!w || typingFeedback.value !== 'idle') return;
  const input = typed.value.trim().toLowerCase();
  if (!input) return;
  const correct = input === w.word.trim().toLowerCase();
  typingStats.value.total += 1;
  typingStats.value.chars += w.word.length;
  if (correct) {
    typingStats.value.correct += 1;
    typingFeedback.value = 'correct';
  } else {
    typingFeedback.value = 'wrong';
  }
  window.setTimeout(() => void nextTyping(), correct ? 600 : 1600);
}

async function nextTyping() {
  typed.value = '';
  typingFeedback.value = 'idle';
  if (typingIndex.value + 1 >= words.value.length) {
    typingMode.value = false;
    try {
      await logPractice({
        exam_type: props.examType,
        section: 'vocab',
        activity: 'typing',
        total: typingStats.value.total,
        correct: typingStats.value.correct,
        meta: { wpm: wpm.value },
      });
      emit('activity');
    } catch {
      /* 忽略 */
    }
    orbit.pushNotification(
      '单词打字',
      `完成 ${typingStats.value.total} 词 · 正确 ${typingStats.value.correct} · ${wpm.value} WPM`,
      'success',
    );
  } else {
    typingIndex.value += 1;
    void playWord(words.value[typingIndex.value].word);
  }
}

onBeforeUnmount(() => audioEl?.pause());
</script>

<template>
  <div class="space-y-3">
    <!-- 打字训练 -->
    <template v-if="typingMode && currentWord">
      <div class="flex items-center justify-between">
        <LzBadge tone="accent">单词打字 {{ typingIndex + 1 }} / {{ words.length }}</LzBadge>
        <span class="lz-caption font-mono-tech">{{ wpm }} WPM · 正确 {{ typingStats.correct }}/{{ typingStats.total }}</span>
      </div>
      <LzCard padding="lg" class="text-center">
        <p class="lz-desc">听发音，拼写单词</p>
        <p class="mt-2 text-lg text-slate-100">{{ currentWord.meaning }}</p>
        <p v-if="currentWord.phonetic" class="lz-caption mt-1">/{{ currentWord.phonetic }}/</p>
        <div class="mt-3 flex justify-center gap-2">
          <LzButton size="sm" variant="soft" :disabled="playingAudio" @click="playWord(currentWord.word)">
            🔊 再听一遍
          </LzButton>
        </div>
        <div class="mt-4">
          <LzInput
            v-model="typed"
            placeholder="键入拼写后回车"
            :disabled="typingFeedback !== 'idle'"
            class="text-center font-mono-tech"
            @keyup.enter="submitTyped"
          />
        </div>
        <p v-if="typingFeedback === 'correct'" class="mt-2 text-sm text-emerald-300">✓ 正确！</p>
        <p v-else-if="typingFeedback === 'wrong'" class="mt-2 text-sm text-rose-300">
          ✗ 正确拼写：<span class="font-mono-tech">{{ currentWord.word }}</span>
        </p>
      </LzCard>
      <LzButton variant="ghost" block size="sm" @click="typingMode = false">退出训练</LzButton>
    </template>

    <!-- 词书列表 -->
    <template v-else>
      <div class="flex items-center justify-between gap-2">
        <p class="lz-caption">词书共 {{ total }} 词</p>
        <div class="flex gap-2">
          <LzButton size="sm" variant="soft" :loading="seeding" @click="seed">AI 扩充词书</LzButton>
          <LzButton size="sm" variant="primary" :disabled="!words.length" @click="startTyping">开始打字训练</LzButton>
        </div>
      </div>

      <LzEmptyState
        v-if="!words.length && !loading"
        icon="📖"
        title="词书还是空的"
        desc="点击「AI 扩充词书」生成第一批高频考纲词"
      />

      <div v-else class="space-y-1.5">
        <LzCard v-for="w in words" :key="w.id" padding="sm" hover>
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <p class="text-sm font-semibold text-slate-100">
                {{ w.word }}
                <span v-if="w.phonetic" class="lz-caption ml-1 font-normal">/{{ w.phonetic }}/</span>
              </p>
              <p class="lz-desc mt-0.5">{{ w.meaning }}</p>
              <p v-if="w.example" class="lz-caption mt-1 italic">{{ w.example }}</p>
            </div>
            <div class="flex shrink-0 flex-col gap-1">
              <LzButton size="sm" variant="ghost" :disabled="playingAudio" @click="playWord(w.word)">🔊</LzButton>
              <LzButton
                size="sm"
                :variant="collected.has(w.id) ? 'soft' : 'ghost'"
                :disabled="collected.has(w.id)"
                @click="collect(w)"
              >
                {{ collected.has(w.id) ? '已收藏' : '＋生词本' }}
              </LzButton>
            </div>
          </div>
        </LzCard>
      </div>

      <div class="flex items-center justify-between">
        <LzButton size="sm" variant="ghost" :disabled="offset === 0" @click="offset = Math.max(0, offset - PAGE); load()">
          上一页
        </LzButton>
        <span class="lz-caption">{{ Math.floor(offset / PAGE) + 1 }} / {{ Math.max(1, Math.ceil(total / PAGE)) }}</span>
        <LzButton size="sm" variant="ghost" :disabled="offset + PAGE >= total" @click="offset += PAGE; load()">
          下一页
        </LzButton>
      </div>
    </template>
  </div>
</template>

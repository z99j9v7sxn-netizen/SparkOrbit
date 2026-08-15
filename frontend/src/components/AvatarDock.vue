<script setup lang="ts">
import gsap from 'gsap';
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import type { AvatarState } from '../api/orbit';
import { generateAvatar } from '../api/orbit';
import { useOrbitStore } from '../stores/orbit';
import MiniChart from './MiniChart.vue';

const props = defineProps<{ state: AvatarState | null }>();
const emit = defineEmits<{ (e: 'avatar-generated'): void }>();

const orbit = useOrbitStore();

const avatarRef = ref<HTMLDivElement | null>(null);
const loading = ref(false);
const loadingStep = ref('');
const errorMsg = ref('');
const fileInputRef = ref<HTMLInputElement | null>(null);
const description = ref('');
const previewUrl = ref('');

let emotionTween: gsap.core.Timeline | null = null;

const moodMeta = computed(() => {
  const mood = props.state?.mood ?? 'calm';
  const map: Record<string, { emoji: string; label: string; color: string }> = {
    celebrate: { emoji: '🥳', label: '状态火热', color: 'from-amber-400/30 to-orange-500/20' },
    confused: { emoji: '😟', label: '有点困惑', color: 'from-rose-400/30 to-purple-500/20' },
    calm: { emoji: '🙂', label: '平稳前行', color: 'from-sky-400/30 to-indigo-500/20' },
  };
  return map[mood] ?? map.calm;
});

const cartoonUrl = computed(() => previewUrl.value || props.state?.avatar_cartoon_url || '');
const hasAvatar = computed(() => Boolean(cartoonUrl.value));
const weekLabels = computed(() => orbit.learningWeekLabels);

watch(
  () => props.state?.avatar_cartoon_url,
  (url) => {
    if (url) previewUrl.value = url;
  },
  { immediate: true },
);

watch(
  () => props.state?.mood,
  (mood) => {
    if (!mood) return;
    playEmotion(mood);
  },
);

function playEmotion(mood: string) {
  const wrap = avatarRef.value;
  if (!wrap) return;
  emotionTween?.kill();
  if (mood === 'celebrate') {
    emotionTween = gsap.timeline()
      .to(wrap, { y: -8, scale: 1.08, duration: 0.25, ease: 'power2.out' })
      .to(wrap, { y: 0, scale: 1, duration: 0.4, ease: 'bounce.out' });
  } else if (mood === 'confused') {
    emotionTween = gsap.timeline()
      .to(wrap, { x: -4, duration: 0.08, repeat: 5, yoyo: true })
      .to(wrap, { x: 0, duration: 0.1 });
  }
}

onBeforeUnmount(() => {
  emotionTween?.kill();
});

function pickPhoto() {
  fileInputRef.value?.click();
}

async function onPhotoSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  input.value = '';

  if (file.size > 20 * 1024 * 1024) {
    errorMsg.value = '图片过大，请上传 20MB 以内的 JPG/PNG 自拍';
    return;
  }

  loading.value = true;
  errorMsg.value = '';
  loadingStep.value = 'DeepSeek 定制指令 → Qwen 生成 2D 卡通形象，约需 30 秒…';
  try {
    const result = await generateAvatar(file, description.value);
    if (result.cartoon_url) {
      previewUrl.value = result.cartoon_url;
    }
    emit('avatar-generated');
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '分身生成失败';
  } finally {
    loading.value = false;
    loadingStep.value = '';
  }
}
</script>

<template>
  <div class="glass glass-edge rounded-3xl p-4">
    <p class="text-[10px] uppercase tracking-[0.35em] text-sky-300/70">数字分身 · 2D 卡通形象</p>

    <div class="mt-3 flex items-start gap-3">
      <div
        ref="avatarRef"
        class="relative h-20 w-20 shrink-0 overflow-hidden rounded-2xl border border-white/10 glass-card"
      >
        <img
          v-if="hasAvatar"
          :src="cartoonUrl"
          alt="2D 卡通分身"
          class="h-full w-full object-cover"
        />
        <div
          v-else
          class="flex h-full w-full items-center justify-center bg-gradient-to-br text-4xl"
          :class="moodMeta.color"
        >
          {{ moodMeta.emoji }}
        </div>
        <div
          v-if="loading"
          class="absolute inset-0 flex items-center justify-center glass-overlay text-[10px] text-sky-200"
        >
          生成中…
        </div>
      </div>

      <div class="min-w-0 flex-1">
        <p class="text-base font-semibold text-white">{{ state?.display_name ?? '星轨学习者' }}</p>
        <p class="text-xs text-sky-300">{{ moodMeta.label }} · 连续 {{ state?.streak_days ?? 0 }} 天</p>
        <p v-if="loadingStep" class="mt-1 text-[10px] text-cyan-300">{{ loadingStep }}</p>
        <p v-if="errorMsg" class="mt-1 text-[10px] text-rose-300">{{ errorMsg }}</p>
      </div>
    </div>

    <div class="mt-3 space-y-2">
      <input
        v-model="description"
        type="text"
        placeholder="可选：描述你的学习风格或形象偏好"
        class="glass-card w-full rounded-xl border border-white/10 px-3 py-2 text-xs text-white placeholder:text-slate-500 focus:border-sky-400/50 focus:outline-none"
      />
      <button
        type="button"
        class="w-full rounded-xl glass-btn px-3 py-2 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-50"
        :disabled="loading"
        @click="pickPhoto"
      >
        {{ loading ? '正在生成 2D 卡通形象…' : hasAvatar ? '重新生成我的分身' : '上传自拍 · 生成 2D 卡通分身' }}
      </button>
      <input ref="fileInputRef" type="file" accept="image/jpeg,image/png,image/webp" class="hidden" @change="onPhotoSelected" />
    </div>

    <div class="mt-4 grid grid-cols-3 gap-2 text-center">
      <div class="rounded-xl border border-white/10 glass-card py-2">
        <p class="text-[10px] text-slate-400">积分</p>
        <p class="text-sm font-semibold text-amber-300">{{ state?.points ?? 0 }}</p>
      </div>
      <div class="rounded-xl border border-white/10 glass-card py-2">
        <p class="text-[10px] text-slate-400">点亮</p>
        <p class="text-sm font-semibold text-emerald-300">{{ state?.lit_count ?? 0 }}/{{ state?.total_planets ?? 0 }}</p>
      </div>
      <div class="rounded-xl border border-white/10 glass-card py-2">
        <p class="text-[10px] text-slate-400">掌握率</p>
        <p class="text-sm font-semibold text-sky-300">{{ state?.mastery_rate ?? 0 }}%</p>
      </div>
    </div>

    <div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-800">
      <div class="h-full rounded-full bg-gradient-to-r from-sky-400 via-cyan-300 to-purple-400" :style="{ width: `${state?.mastery_rate ?? 0}%` }" />
    </div>

    <div class="mt-3 glass-card rounded-xl p-2">
      <p class="mb-1 text-[10px] text-slate-400">近 7 天学习时长（小时）</p>
      <MiniChart type="bar" :data="orbit.learningWeeklyHours" :labels="weekLabels" height="48px" color="#7dd3fc" />
    </div>
  </div>
</template>

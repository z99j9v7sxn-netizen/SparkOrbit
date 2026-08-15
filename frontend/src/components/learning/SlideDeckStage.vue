<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import gsap from 'gsap';
import type { MistakeSlide } from '../../api/digitalTutor';

const props = withDefaults(
  defineProps<{
    slides: MistakeSlide[];
    /** 外部控制当前幕；不传则内部自管 */
    index?: number;
    /** 是否自动按间隔轮播（错题场景通常关闭，改由虚拟人驱动） */
    autoplay?: boolean;
    /** 自动轮播间隔（秒） */
    intervalSec?: number;
    /** 是否使用浏览器 speechSynthesis（错题+虚拟人时必须 false） */
    speakNarration?: boolean;
    compact?: boolean;
  }>(),
  {
    autoplay: false,
    intervalSec: 6,
    speakNarration: false,
    compact: false,
  },
);

const emit = defineEmits<{
  'update:index': [n: number];
  change: [n: number, slide: MistakeSlide];
}>();

const rootRef = ref<HTMLElement | null>(null);
const internalIndex = ref(0);
let tween: gsap.core.Tween | null = null;

const controlled = computed(() => props.index != null);
const currentIndex = computed(() => {
  if (!props.slides.length) return 0;
  const i = controlled.value ? Number(props.index) : internalIndex.value;
  return ((i % props.slides.length) + props.slides.length) % props.slides.length;
});
const current = computed(() => props.slides[currentIndex.value] || null);
const total = computed(() => props.slides.length);

function killTween() {
  tween?.kill();
  tween = null;
  if (typeof window !== 'undefined') window.speechSynthesis?.cancel();
}

function animateIn() {
  const el = rootRef.value?.querySelector('.slide-deck-panel');
  if (!el) return;
  gsap.fromTo(
    el,
    { opacity: 0, y: 14 },
    { opacity: 1, y: 0, duration: 0.45, ease: 'power2.out' },
  );
}

function maybeSpeak(slide: MistakeSlide) {
  if (!props.speakNarration || !slide.narration) return;
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(slide.narration);
  u.lang = 'zh-CN';
  window.speechSynthesis.speak(u);
}

function goTo(n: number) {
  if (!props.slides.length) return;
  const next = ((n % props.slides.length) + props.slides.length) % props.slides.length;
  if (!controlled.value) internalIndex.value = next;
  emit('update:index', next);
  const slide = props.slides[next];
  if (slide) emit('change', next, slide);
}

function next() {
  goTo(currentIndex.value + 1);
}

function prev() {
  goTo(currentIndex.value - 1);
}

function scheduleAutoplay() {
  killTween();
  if (!props.autoplay || props.slides.length < 2) return;
  const sec = Math.max(2, props.intervalSec || 6);
  tween = gsap.delayedCall(sec, function tick() {
    next();
    tween = gsap.delayedCall(sec, tick);
  });
}

watch(
  () => [props.slides, currentIndex.value] as const,
  () => {
    animateIn();
    if (current.value) maybeSpeak(current.value);
  },
  { immediate: true },
);

watch(
  () => [props.autoplay, props.intervalSec, props.slides.length] as const,
  () => scheduleAutoplay(),
  { immediate: true },
);

watch(
  () => props.index,
  (v) => {
    if (v == null) return;
    // 外部切幕时重置自动轮播计时
    if (props.autoplay) scheduleAutoplay();
  },
);

onBeforeUnmount(() => killTween());

defineExpose({ next, prev, goTo, currentIndex });
</script>

<template>
  <div
    ref="rootRef"
    class="slide-deck"
    :class="compact ? 'slide-deck--compact' : ''"
  >
    <div v-if="!slides.length" class="slide-deck-empty">
      暂无分镜内容
    </div>
    <template v-else>
      <div class="slide-deck-meta">
        <span>分镜 {{ currentIndex + 1 }} / {{ total }}</span>
        <span v-if="current?.visual_hint" class="slide-deck-hint">{{ current.visual_hint }}</span>
      </div>
      <div class="slide-deck-panel">
        <h4 class="slide-deck-title">{{ current?.title }}</h4>
        <p class="slide-deck-narration">{{ current?.narration }}</p>
        <ul v-if="current?.bullet_points?.length" class="slide-deck-bullets">
          <li v-for="(b, i) in current.bullet_points" :key="i">{{ b }}</li>
        </ul>
      </div>
      <div class="slide-deck-nav">
        <button type="button" class="slide-deck-btn" :disabled="total < 2" @click="prev">上一幕</button>
        <button type="button" class="slide-deck-btn" :disabled="total < 2" @click="next">下一幕</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.slide-deck {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: 180px;
  border-radius: 1rem;
  border: 1px solid rgba(125, 211, 252, 0.22);
  background:
    radial-gradient(120% 80% at 10% 0%, rgba(56, 189, 248, 0.14), transparent 55%),
    radial-gradient(90% 70% at 100% 100%, rgba(16, 185, 129, 0.1), transparent 50%),
    linear-gradient(160deg, rgba(15, 23, 42, 0.92), rgba(2, 6, 23, 0.95));
  padding: 0.9rem 1rem 1rem;
}

.slide-deck--compact {
  min-height: 140px;
  padding: 0.7rem 0.85rem;
}

.slide-deck-empty {
  display: flex;
  min-height: 120px;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  color: rgb(148 163 184);
}

.slide-deck-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgb(125 211 252 / 0.85);
}

.slide-deck-hint {
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: rgb(167 243 208 / 0.9);
  text-transform: none;
  letter-spacing: 0;
}

.slide-deck-panel {
  will-change: transform, opacity;
}

.slide-deck-title {
  font-size: 1.05rem;
  font-weight: 600;
  color: #fff;
}

.slide-deck-narration {
  margin-top: 0.65rem;
  font-size: 0.875rem;
  line-height: 1.65;
  color: rgb(203 213 225);
}

.slide-deck-bullets {
  margin-top: 0.75rem;
  list-style: disc;
  padding-left: 1.15rem;
  font-size: 0.75rem;
  line-height: 1.55;
  color: rgb(125 211 252);
}

.slide-deck-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.slide-deck-btn {
  border-radius: 0.65rem;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.05);
  padding: 0.35rem 0.75rem;
  font-size: 11px;
  color: rgb(226 232 240);
}

.slide-deck-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
}

.slide-deck-btn:disabled {
  opacity: 0.4;
}
</style>

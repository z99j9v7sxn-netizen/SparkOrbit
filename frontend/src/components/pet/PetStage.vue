<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { fetchPets, type PetAction, type PetManifest } from '../../api/pet';

const props = defineProps<{
  slug?: string;
  bonusFps?: number;
  forcedAction?: PetAction | null;
  affinityLevel?: number;
}>();

const emit = defineEmits<{
  (e: 'action-complete', key: string): void;
  (e: 'open-menu'): void;
}>();

const manifest = ref<PetManifest | null>(null);
const frameIndex = ref(0);
const currentAction = ref<PetAction | null>(null);
let rafId = 0;
let lastTick = 0;
let actionTimer = 0;

const columns = computed(() => Math.max(manifest.value?.columns ?? 1, 1));
const rows = computed(() => Math.max(manifest.value?.rows ?? 1, 1));
const isCodex = computed(() => manifest.value?.format === 'codex');

const activeAction = computed(() => {
  if (props.forcedAction) return props.forcedAction;
  if (currentAction.value) return currentAction.value;
  const idle = manifest.value?.actions?.find((a) => a.key === 'idle');
  if (idle) return idle;
  return {
    key: 'idle',
    label: '待机',
    icon: '💤',
    animation_row: manifest.value?.animation_row ?? 0,
    frame_count: manifest.value?.frame_count ?? 6,
    fps: manifest.value?.fps ?? 8,
    loop: true,
    route: '',
  } satisfies PetAction;
});

const frameCount = computed(() => Math.max(activeAction.value.frame_count, 1));
const fps = computed(() => (activeAction.value.fps || manifest.value?.fps || 8) + (props.bonusFps ?? 0));

const stageStyle = computed(() => {
  const cw = manifest.value?.cell_width ?? 0;
  const ch = manifest.value?.cell_height ?? 0;
  if (cw > 0 && ch > 0) return { aspectRatio: `${cw} / ${ch}` };
  return {};
});

function spritePosition(col: number, row: number) {
  const xPct = columns.value > 1 ? (col / (columns.value - 1)) * 100 : 0;
  const yPct = rows.value > 1 ? (row / (rows.value - 1)) * 100 : 0;
  return { xPct, yPct };
}

const spriteStyle = computed(() => {
  if (!manifest.value?.sprite_url) return {};
  let col = frameIndex.value % columns.value;
  let row = Math.floor(frameIndex.value / columns.value);
  if (isCodex.value) {
    col = frameIndex.value % Math.max(frameCount.value, 1);
    row = activeAction.value.animation_row;
  }
  const { xPct, yPct } = spritePosition(col, row);
  return {
    backgroundImage: `url(${manifest.value.sprite_url})`,
    backgroundSize: `${columns.value * 100}% ${rows.value * 100}%`,
    backgroundPosition: `${xPct}% ${yPct}%`,
    backgroundRepeat: 'no-repeat',
  };
});

const glowClass = computed(() => {
  if ((props.affinityLevel ?? 0) >= 3) return 'ring-2 ring-amber-300/40 shadow-[0_0_24px_rgba(251,191,36,0.35)]';
  if ((props.affinityLevel ?? 0) >= 2) return 'ring-1 ring-sky-400/30';
  return '';
});

async function loadManifest() {
  if (!props.slug) {
    manifest.value = null;
    return;
  }
  const pets = await fetchPets();
  manifest.value = pets.find((p) => p.slug === props.slug) ?? null;
  frameIndex.value = 0;
}

function tick(now: number) {
  rafId = requestAnimationFrame(tick);
  if (!manifest.value) return;
  const interval = 1000 / fps.value;
  if (now - lastTick >= interval) {
    lastTick = now;
    const max = Math.max(frameCount.value, 1);
    if (activeAction.value.loop) {
      frameIndex.value = (frameIndex.value + 1) % max;
    } else if (frameIndex.value < max - 1) {
      frameIndex.value += 1;
    }
  }
}

function startAnim() {
  cancelAnimationFrame(rafId);
  lastTick = performance.now();
  rafId = requestAnimationFrame(tick);
}

function stopAnim() {
  cancelAnimationFrame(rafId);
}

function playAction(action: PetAction) {
  window.clearTimeout(actionTimer);
  currentAction.value = action;
  frameIndex.value = 0;
  if (!action.loop) {
    const duration = Math.max(800, (action.frame_count / Math.max(action.fps, 1)) * 1000);
    actionTimer = window.setTimeout(() => {
      const key = action.key;
      currentAction.value = null;
      frameIndex.value = 0;
      emit('action-complete', key);
    }, duration);
  }
}

function onClick() {
  emit('open-menu');
}

function playActionByKey(key: string) {
  const action = manifest.value?.actions?.find((a) => a.key === key);
  if (action) playAction(action);
}

defineExpose({ playAction, playActionByKey });

watch(() => props.slug, () => { void loadManifest().then(startAnim); }, { immediate: true });
watch(() => props.forcedAction, (next) => {
  if (next) playAction(next);
});

onBeforeUnmount(() => {
  stopAnim();
  window.clearTimeout(actionTimer);
});
</script>

<template>
  <div class="pointer-events-auto relative w-28" :style="stageStyle">
    <button
      v-if="manifest"
      type="button"
      class="relative w-full overflow-hidden rounded-2xl border border-white/10 bg-black/20 transition hover:border-sky-400/30"
      :class="[isCodex ? 'min-h-[7.25rem]' : 'h-28', glowClass]"
      :style="spriteStyle"
      :title="manifest.name"
      @click="onClick"
    />
    <div v-else class="flex h-28 w-full items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/5 text-3xl">🐾</div>
    <p v-if="manifest" class="pointer-events-none absolute -bottom-5 left-1/2 -translate-x-1/2 whitespace-nowrap text-[10px] text-sky-200/80">{{ manifest.name }}</p>
  </div>
</template>

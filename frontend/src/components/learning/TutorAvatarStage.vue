<script setup lang="ts">
/**
 * 伴学舱虚拟人舞台：仅讯飞实时虚拟人（按需连接）。
 * 未开启时显示引导；不再使用几何体占位。
 */
import { computed, nextTick, onBeforeUnmount, ref } from 'vue';
import { useAvatarVms } from '../../composables/useAvatarVms';
import { synthesizeSpeech } from '../../api/tts';

const vmsWrapperRef = ref<HTMLDivElement | null>(null);
const vmsBusy = ref(false);
const statusText = ref('点击开启虚拟人');
const vms = useAvatarVms();

const live = computed(() => vms.enabled.value && vms.status.value === 'live');
const vmsStatus = computed(() => vms.status.value);
const vmsStatusText = computed(() => vms.statusText.value);
const vmsError = computed(() => vms.error.value);
const vmsNeedGesture = computed(() => vms.needGesture.value);

let audioEl: HTMLAudioElement | null = null;
let objectUrl: string | null = null;

function stopAudio() {
  if (audioEl) {
    audioEl.pause();
    audioEl.onended = null;
    audioEl.onerror = null;
    audioEl = null;
  }
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  }
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}

async function playAudio(blob: Blob) {
  stopAudio();
  objectUrl = URL.createObjectURL(blob);
  const el = new Audio(objectUrl);
  audioEl = el;
  statusText.value = '口播中…';
  await new Promise<void>((resolve, reject) => {
    el.onended = () => {
      statusText.value = live.value ? vmsStatusText.value : '讲解完成';
      resolve();
    };
    el.onerror = () => reject(new Error('音频播放失败'));
    void el.play().catch(reject);
  });
}

function speakWithBrowser(text: string) {
  stopAudio();
  if (typeof window === 'undefined' || !window.speechSynthesis || !text.trim()) return;
  const u = new SpeechSynthesisUtterance(text.slice(0, 800));
  u.lang = 'zh-CN';
  u.rate = 1.05;
  statusText.value = '浏览器朗读中…';
  u.onend = () => {
    statusText.value = live.value ? vmsStatusText.value : '讲解完成';
  };
  window.speechSynthesis.speak(u);
}

async function toggleVms() {
  if (vmsBusy.value) return;
  vmsBusy.value = true;
  try {
    if (live.value || vms.enabled.value) {
      stopAudio();
      await vms.disable('已关闭虚拟人（停止计费）');
      statusText.value = '点击开启虚拟人';
      return;
    }
    await nextTick();
    if (!vmsWrapperRef.value) throw new Error('虚拟人容器未就绪');
    stopAudio();
    await vms.enable(vmsWrapperRef.value);
    statusText.value = vms.statusText.value;
  } catch (e) {
    statusText.value = e instanceof Error ? e.message : '虚拟人连接失败';
  } finally {
    vmsBusy.value = false;
  }
}

async function speakLive(text: string): Promise<boolean> {
  if (!live.value) return false;
  stopAudio();
  try {
    return await vms.speak(text);
  } catch {
    return false;
  }
}

/** 未开虚拟人时走 TTS；已开启则 writeText */
async function speakText(text: string) {
  if (!text.trim()) return;
  if (live.value) {
    const ok = await speakLive(text);
    if (ok) return;
  }
  try {
    const blob = await synthesizeSpeech(text);
    await playAudio(blob);
  } catch {
    speakWithBrowser(text);
  }
}

function disconnectVms() {
  void vms.disable('已断开虚拟人');
}

onBeforeUnmount(() => {
  stopAudio();
  disconnectVms();
});

defineExpose({
  playAudio,
  speakWithBrowser,
  speakLive,
  speakText,
  stopAudio,
  disconnectVms,
  isLive: live,
});
</script>

<template>
  <div class="tutor-avatar-stage relative overflow-hidden rounded-2xl border border-[rgb(var(--lz-accent)/0.4)] bg-slate-950">
    <div
      ref="vmsWrapperRef"
      class="vms-stage relative w-full bg-slate-950"
      @click="vmsNeedGesture && vms.resumePlayback()"
    />

    <div
      v-if="!live && vmsStatus !== 'connecting'"
      class="guide-layer pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-3"
    >
      <p class="guide-title">讯飞虚拟人</p>
      <p class="px-4 text-center text-xs text-slate-300">{{ statusText }}</p>
      <button
        type="button"
        class="guide-btn pointer-events-auto rounded-xl border border-[rgb(var(--lz-accent)/0.6)] bg-[rgb(var(--lz-accent)/0.22)] px-4 py-2 text-sm text-white disabled:opacity-50"
        :disabled="vmsBusy"
        @click="toggleVms"
      >
        {{ vmsBusy ? '连接中…' : '开启虚拟人' }}
      </button>
    </div>

    <button
      v-if="vmsNeedGesture"
      type="button"
      class="absolute inset-0 z-20 flex items-center justify-center text-sm text-white"
      style="background: rgba(0, 0, 0, 0.6)"
      @click="vms.resumePlayback()"
    >
      点击开启画面与声音
    </button>

    <div class="absolute inset-x-0 bottom-0 z-10 flex items-center justify-between gap-2 px-3 pb-2.5 pt-8 footer-bar">
      <div class="min-w-0">
        <p class="guide-title">Live Avatar</p>
        <p class="truncate text-xs text-slate-200">{{ live || vmsStatus === 'connecting' ? vmsStatusText : statusText }}</p>
      </div>
      <button
        v-if="live || vmsStatus === 'connecting'"
        type="button"
        class="shrink-0 rounded-lg border border-rose-400 bg-rose-900 px-2.5 py-1 text-xs text-rose-50 disabled:opacity-50"
        :disabled="vmsBusy"
        @click="toggleVms"
      >
        {{ vmsBusy || vmsStatus === 'connecting' ? '…' : '关闭' }}
      </button>
    </div>
    <p v-if="vmsError" class="absolute left-2 right-2 top-2 z-10 rounded bg-amber-900 px-2 py-1 text-xs text-amber-100">
      {{ vmsError }}
    </p>
  </div>
</template>

<style scoped>
.vms-stage,
.vms-stage :deep(#xvideo) {
  width: 100% !important;
  height: 360px !important;
  min-height: 360px !important;
  position: relative !important;
}
.vms-stage :deep(video),
.vms-stage :deep(canvas) {
  width: 100% !important;
  height: 100% !important;
  object-fit: contain !important;
  background: #0b1220 !important;
}
.guide-layer {
  background: #070b14;
}
.guide-title {
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: rgb(var(--lz-accent-bright));
}
.guide-btn:hover {
  background: rgb(var(--lz-accent) / 0.35);
}
.footer-bar {
  background: linear-gradient(to top, rgba(0, 0, 0, 0.9), transparent);
}
</style>

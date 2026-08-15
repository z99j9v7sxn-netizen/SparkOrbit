<script setup lang="ts">
import gsap from 'gsap';
import { nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { useOrbitStore } from '../stores/orbit';

const orbit = useOrbitStore();
const toastRefs = ref<Record<string, HTMLElement | null>>({});
const timers = new Map<string, ReturnType<typeof setTimeout>>();

function setRef(id: string, el: unknown) {
  toastRefs.value[id] = (el as HTMLElement) ?? null;
}

function animateIn(id: string) {
  const el = toastRefs.value[id];
  if (!el) return;
  gsap.fromTo(el, { x: 80, opacity: 0 }, { x: 0, opacity: 1, duration: 0.45, ease: 'power3.out' });
}

function animateOut(id: string, onDone: () => void) {
  const el = toastRefs.value[id];
  if (!el) {
    onDone();
    return;
  }
  gsap.to(el, {
    x: 80,
    opacity: 0,
    duration: 0.35,
    ease: 'power2.in',
    onComplete: onDone,
  });
}

function dismiss(id: string) {
  const timer = timers.get(id);
  if (timer) clearTimeout(timer);
  timers.delete(id);
  animateOut(id, () => orbit.dismissNotification(id));
}

function goLearn(note: { id: string; planetSlug?: string }) {
  if (note.planetSlug) {
    window.dispatchEvent(
      new CustomEvent('sparkorbit:jump-planet', { detail: { planetSlug: note.planetSlug } }),
    );
  }
  dismiss(note.id);
}

function scheduleDismiss(id: string) {
  const timer = setTimeout(() => dismiss(id), 5000);
  timers.set(id, timer);
}

watch(
  () => orbit.notifications.map((n) => n.id).join(','),
  async () => {
    await nextTick();
    for (const note of orbit.notifications) {
      if (!timers.has(note.id)) {
        animateIn(note.id);
        scheduleDismiss(note.id);
      }
    }
  },
);

onBeforeUnmount(() => {
  timers.forEach((t) => clearTimeout(t));
  timers.clear();
});

const typeStyle: Record<string, string> = {
  info: 'border-sky-400/30 bg-sky-500/10',
  warning: 'border-amber-400/40 bg-amber-500/10',
  success: 'border-emerald-400/40 bg-emerald-500/10',
};
</script>

<template>
  <div class="pointer-events-none fixed right-5 top-20 z-50 flex w-72 flex-col gap-2">
    <div
      v-for="note in orbit.notifications"
      :key="note.id"
      :ref="(el) => setRef(note.id, el)"
      class="glass pointer-events-auto rounded-2xl border px-4 py-3 shadow-glow"
      :class="typeStyle[note.type] ?? typeStyle.info"
    >
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0">
          <p class="text-xs font-semibold text-white">{{ note.title }}</p>
          <p class="mt-0.5 text-[11px] leading-5 text-slate-300">{{ note.message }}</p>
          <button
            v-if="note.planetSlug"
            type="button"
            class="mt-1.5 rounded-lg border border-cyan-400/30 px-2 py-0.5 text-[10px] text-cyan-200 hover:bg-cyan-400/10"
            @click="goLearn(note)"
          >
            {{ note.actionLabel || '去学习' }}
          </button>
        </div>
        <button
          class="shrink-0 rounded-full px-1.5 text-slate-400 transition hover:bg-white/10 hover:text-white"
          @click="dismiss(note.id)"
        >✕</button>
      </div>
    </div>
  </div>
</template>

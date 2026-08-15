<script setup lang="ts">
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { onBeforeUnmount, onMounted, ref } from 'vue';
import StellarArchive from '../archive/StellarArchive.vue';
import AsteroidChallenge from '../trial/AsteroidChallenge.vue';
import OrbitNavigator from '../learning/OrbitNavigator.vue';
import InterstellarComms from '../comms/InterstellarComms.vue';

gsap.registerPlugin(ScrollTrigger);

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'scan'): void;
  (e: 'fire-laser', isCorrect: boolean): void;
  (e: 'navigate', target: { galaxySlug: string; galaxyName: string; planetSlug: string; planetName: string }): void;
  (e: 'speak', text: string): void;
}>();

const scrollerRef = ref<HTMLDivElement | null>(null);
const activeSection = ref(0);

const sections = [
  { id: 'archive', label: '恒星档案馆', kicker: 'STELLAR ARCHIVE' },
  { id: 'challenge', label: '流星雨试炼', kicker: 'ASTEROID CHALLENGE' },
  { id: 'navigator', label: '星轨导航仪', kicker: 'ORBIT NAVIGATOR' },
  { id: 'comms', label: '星际通讯舱', kicker: 'INTERSTELLAR COMMS' },
] as const;

let sectionTriggers: ScrollTrigger[] = [];

function scrollToSection(index: number) {
  const el = scrollerRef.value;
  if (!el) return;
  const section = el.querySelectorAll('.cms-section')[index] as HTMLElement | undefined;
  section?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

onMounted(() => {
  const el = scrollerRef.value;
  if (!el) return;

  const sectionEls = el.querySelectorAll('.cms-section');
  sectionEls.forEach((section, i) => {
    const trigger = ScrollTrigger.create({
      trigger: section,
      scroller: el,
      start: 'top center',
      end: 'bottom center',
      onEnter: () => { activeSection.value = i; },
      onEnterBack: () => { activeSection.value = i; },
    });
    sectionTriggers.push(trigger);
  });
});

onBeforeUnmount(() => {
  sectionTriggers.forEach((t) => t.kill());
  sectionTriggers = [];
});
</script>

<template>
  <div class="cms-overlay pointer-events-auto absolute inset-0 z-40 flex animate-fade-in">
    <nav class="flex w-14 flex-col items-center justify-center gap-4 border-r border-white/10 bg-black/30 backdrop-blur-xl">
      <button
        v-for="(s, i) in sections"
        :key="s.id"
        class="group relative flex flex-col items-center gap-1"
        :title="s.label"
        @click="scrollToSection(i)"
      >
        <span
          class="h-3 w-3 rounded-full transition-all duration-300"
          :class="activeSection === i ? 'scale-125 bg-sky-400 shadow-[0_0_12px_#38bdf8]' : 'bg-white/20 hover:bg-white/50'"
        />
        <span class="hidden text-[8px] text-slate-500 group-hover:block">{{ i + 1 }}</span>
      </button>
    </nav>

    <div ref="scrollerRef" class="cms-scroller h-full flex-1 overflow-y-auto snap-y snap-mandatory scroll-smooth">
      <section
        v-for="(s, i) in sections"
        :key="s.id"
        class="cms-section flex h-screen snap-start snap-always items-stretch px-4 py-6 md:px-10 md:py-10"
      >
        <div class="glass-strong mx-auto flex h-full w-full max-w-5xl flex-col overflow-hidden rounded-3xl border border-white/10 p-6 md:p-10">
          <p class="text-[10px] uppercase tracking-[0.55em] text-slate-400">{{ s.kicker }}</p>
          <h2 class="mt-3 text-3xl font-light tracking-widest text-white text-glow md:text-5xl">{{ s.label }}</h2>
          <div class="mt-6 min-h-0 flex-1 overflow-auto">
            <StellarArchive v-if="s.id === 'archive'" embedded @scan="emit('scan')" />
            <AsteroidChallenge v-else-if="s.id === 'challenge'" embedded @fire-laser="emit('fire-laser', $event)" />
            <OrbitNavigator v-else-if="s.id === 'navigator'" embedded @navigate="emit('navigate', $event)" />
            <InterstellarComms v-else-if="s.id === 'comms'" embedded @speak="emit('speak', $event)" />
          </div>
          <p v-if="i < sections.length - 1" class="mt-4 text-center text-[10px] tracking-[0.45em] text-slate-500">
            向下滚动 · SCROLL DOWN
          </p>
        </div>
      </section>
    </div>

    <button
      class="absolute right-6 top-6 z-50 rounded-full border border-white/10 bg-black/50 px-4 py-2 text-xs text-slate-300 backdrop-blur-xl transition hover:bg-white/10"
      @click="emit('close')"
    >
      返回探索 ✕
    </button>
  </div>
</template>

<style scoped>
.cms-scroller {
  scroll-behavior: smooth;
  scrollbar-width: thin;
}
.cms-scroller::-webkit-scrollbar {
  width: 4px;
}
.cms-scroller::-webkit-scrollbar-thumb {
  background: rgba(125, 211, 252, 0.3);
  border-radius: 999px;
}
@keyframes fade-in {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-fade-in {
  animation: fade-in 0.45s ease-out;
}
</style>

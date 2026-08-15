<script setup lang="ts">
import { onMounted, ref } from 'vue';
import gsap from 'gsap';

defineProps<{
  /** HUD 等宽字眉标，如 `MY DOMAIN // COMMAND DECK` */
  eyebrow: string;
  title: string;
  desc?: string;
}>();

const rootRef = ref<HTMLElement | null>(null);

onMounted(() => {
  const root = rootRef.value;
  if (!root) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  gsap.fromTo(
    root.querySelectorAll('[data-zh]'),
    { opacity: 0, y: 12 },
    { opacity: 1, y: 0, duration: 0.55, stagger: 0.08, ease: 'power3.out' },
  );
});
</script>

<template>
  <header ref="rootRef" class="zone-header mb-6">
    <div class="flex items-center gap-3" data-zh>
      <span class="lz-pulse-dot shrink-0" aria-hidden="true"></span>
      <p class="lz-hud-label">{{ eyebrow }}</p>
      <span class="zone-header-line" aria-hidden="true"></span>
    </div>
    <h2 class="zone-header-title mt-2 text-2xl font-semibold md:text-3xl" data-zh>{{ title }}</h2>
    <p v-if="desc" class="mt-1.5 text-sm text-slate-400" data-zh>{{ desc }}</p>
  </header>
</template>

<style scoped>
.zone-header-line {
  flex: 1;
  height: 1px;
  max-width: 220px;
  background: linear-gradient(90deg, rgb(var(--lz-accent) / 0.5), transparent);
}

.zone-header-title {
  background: linear-gradient(100deg, #fff 30%, rgb(var(--lz-accent-bright)) 85%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  text-shadow: 0 0 32px rgb(var(--lz-accent) / 0.25);
  letter-spacing: 0.01em;
}
</style>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';

const lines = ref<{ ts: string; msg: string }[]>([]);
let timer: number | null = null;
let tick = 0;

const MESSAGES = [
  'boot://sparkorbit kernel 0.9.4',
  'mount /orbit/cognitive_twin … ok',
  'sync particle_field density=0.42',
  'handshake auth_gate → waiting',
  'mirror agent idle · queue=0',
  'load constellation map … 56 planets',
  'telemetry uplink established',
  'scan access_tokens · purged stale',
  'profiler channel standby',
  'rail_nav ready · latency 12ms',
  'awaiting human credential stream',
  'geometry_core spin=0.3rpm',
];

function stamp() {
  const d = new Date();
  return [d.getHours(), d.getMinutes(), d.getSeconds()]
    .map((n) => String(n).padStart(2, '0'))
    .join(':');
}

function pushLine() {
  const msg = MESSAGES[tick % MESSAGES.length];
  tick += 1;
  lines.value = [...lines.value.slice(-14), { ts: stamp(), msg }];
}

onMounted(() => {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  for (let i = 0; i < 6; i++) pushLine();
  if (!reduce) {
    timer = window.setInterval(pushLine, 1800);
  }
});

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer);
});
</script>

<template>
  <div class="pointer-events-none absolute inset-0 z-10 flex flex-col justify-end p-6 sm:p-10">
    <p class="mb-3 text-[10px] tracking-[0.3em] text-[var(--term-muted)]">系统日志 // LIVE</p>
    <div class="max-h-full space-y-1 overflow-hidden font-mono text-[11px] leading-relaxed">
      <p v-for="(line, i) in lines" :key="i" class="truncate text-[var(--term-muted)]">
        <span class="text-[var(--term-line-bright)]">{{ line.ts }}</span>
        <span class="mx-2 text-[var(--term-line)]">·</span>
        <span>{{ line.msg }}</span>
      </p>
    </div>
  </div>
</template>

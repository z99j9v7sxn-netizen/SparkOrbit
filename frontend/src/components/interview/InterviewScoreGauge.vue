<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    score: number | null | undefined;
    size?: number;
  }>(),
  { size: 168 },
);

const clamped = computed(() => Math.max(0, Math.min(100, Number(props.score ?? 0))));
const hasScore = computed(() => props.score != null);

const grade = computed(() => {
  if (!hasScore.value) return '—';
  const s = clamped.value;
  if (s >= 90) return 'S';
  if (s >= 80) return 'A';
  if (s >= 70) return 'B';
  if (s >= 60) return 'C';
  return 'D';
});

const CX = 80;
const CY = 86;
const R = 58;
const START = 225;

function polar(deg: number, radius = R) {
  const rad = ((deg - 90) * Math.PI) / 180;
  return [CX + radius * Math.cos(rad), CY + radius * Math.sin(rad)] as const;
}

function horseshoe(radius: number) {
  const [sx, sy] = polar(START, radius);
  const [ex, ey] = polar(START + 270, radius);
  return `M ${sx.toFixed(2)} ${sy.toFixed(2)} A ${radius} ${radius} 0 1 1 ${ex.toFixed(2)} ${ey.toFixed(2)}`;
}

const track = horseshoe(R);
const ticks = computed(() =>
  Array.from({ length: 10 }, (_, i) => {
    const deg = START + 27 * (i + 1);
    const [x1, y1] = polar(deg, R - 5);
    const [x2, y2] = polar(deg, R + (i % 5 === 4 ? 6 : 3));
    return { i, x1, y1, x2, y2, major: i % 5 === 4 };
  }),
);
</script>

<template>
  <div class="iv-gauge" :style="{ width: `${size}px` }" role="img" :aria-label="hasScore ? `综合均分 ${Math.round(clamped)}` : '暂无分数'">
    <svg viewBox="0 0 160 148" class="h-auto w-full">
      <defs>
        <linearGradient id="ivGaugeArc" x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#f59e0b" />
          <stop offset="100%" stop-color="#fb923c" />
        </linearGradient>
      </defs>
      <path :d="track" fill="none" stroke="rgba(148,163,184,0.18)" stroke-width="3.5" stroke-linecap="butt" />
      <path
        v-if="hasScore"
        class="iv-gauge__arc"
        :d="track"
        fill="none"
        stroke="url(#ivGaugeArc)"
        stroke-width="5"
        stroke-linecap="butt"
        pathLength="100"
        :stroke-dasharray="`${clamped} 100`"
      />
      <line
        v-for="t in ticks"
        :key="t.i"
        :x1="t.x1"
        :y1="t.y1"
        :x2="t.x2"
        :y2="t.y2"
        :stroke="t.major ? 'rgba(252,211,77,0.55)' : 'rgba(148,163,184,0.35)'"
        :stroke-width="t.major ? 1.1 : 0.6"
      />
      <text
        :x="CX"
        :y="CY + 6"
        text-anchor="middle"
        class="iv-gauge__num"
      >{{ hasScore ? Math.round(clamped) : '—' }}</text>
      <text
        :x="CX + 22"
        :y="CY + 18"
        text-anchor="start"
        class="iv-gauge__unit"
      >{{ hasScore ? `分 · ${grade}` : '暂无' }}</text>
    </svg>
  </div>
</template>

<style scoped>
.iv-gauge__num {
  fill: #f8fafc;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 28px;
  font-weight: 600;
}
.iv-gauge__unit {
  fill: #94a3b8;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 9px;
  letter-spacing: 0.12em;
}
.iv-gauge__arc {
  transition: stroke-dasharray 0.7s cubic-bezier(0.22, 1, 0.36, 1);
}
@media (prefers-reduced-motion: reduce) {
  .iv-gauge__arc {
    transition: none;
  }
}
</style>

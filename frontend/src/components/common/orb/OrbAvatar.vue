<script setup lang="ts">
import { computed } from 'vue';

/** OrbAvatar：CSS 呼吸辉光球形头像，作为身份锚点（教师青色 / 管理紫色）。 */
const props = withDefaults(
  defineProps<{
    palette?: 'cyan' | 'violet' | 'neon';
    size?: number;
    label?: string;
  }>(),
  { palette: 'cyan', size: 36, label: '' },
);

const COLORS: Record<string, [string, string]> = {
  cyan: ['#38bdf8', '#22d3ee'],
  violet: ['#a78bfa', '#8b5cf6'],
  neon: ['#00ff9d', '#34d399'],
};

const style = computed(() => {
  const [a, b] = COLORS[props.palette] ?? COLORS.cyan;
  return {
    width: `${props.size}px`,
    height: `${props.size}px`,
    '--orb-a': a,
    '--orb-b': b,
  };
});

const initial = computed(() => (props.label || '').trim().slice(0, 1).toUpperCase());
</script>

<template>
  <div class="orb-avatar" :style="style" role="img" :aria-label="label || '身份标识'">
    <span class="orb-avatar__ring" aria-hidden="true" />
    <span class="orb-avatar__core">
      <span v-if="initial" class="orb-avatar__initial">{{ initial }}</span>
    </span>
  </div>
</template>

<style scoped>
.orb-avatar {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 9999px;
}

.orb-avatar__ring {
  position: absolute;
  inset: -2px;
  border-radius: 9999px;
  background: conic-gradient(from 0deg, var(--orb-a), transparent 30%, var(--orb-b) 55%, transparent 80%, var(--orb-a));
  animation: orb-avatar-spin 7s linear infinite;
  opacity: 0.8;
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 2.5px), #000 calc(100% - 2px));
  mask: radial-gradient(farthest-side, transparent calc(100% - 2.5px), #000 calc(100% - 2px));
}

.orb-avatar:hover .orb-avatar__ring {
  animation-duration: 2.2s;
}

.orb-avatar__core {
  position: absolute;
  inset: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 9999px;
  background:
    radial-gradient(circle at 32% 30%, color-mix(in srgb, var(--orb-b) 75%, white), var(--orb-a) 55%, rgba(2, 6, 23, 0.9) 95%);
  box-shadow: 0 0 14px color-mix(in srgb, var(--orb-a) 45%, transparent);
  animation: orb-avatar-breathe 4.5s ease-in-out infinite;
}

.orb-avatar__initial {
  font-size: 0.65em;
  font-weight: 700;
  color: rgba(2, 6, 23, 0.85);
  font-family: 'JetBrains Mono', ui-monospace, monospace;
}

@keyframes orb-avatar-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes orb-avatar-breathe {
  0%,
  100% {
    box-shadow: 0 0 10px color-mix(in srgb, var(--orb-a) 35%, transparent);
  }
  50% {
    box-shadow: 0 0 20px color-mix(in srgb, var(--orb-a) 65%, transparent);
  }
}

@media (prefers-reduced-motion: reduce) {
  .orb-avatar__ring,
  .orb-avatar__core {
    animation: none;
  }
}
</style>

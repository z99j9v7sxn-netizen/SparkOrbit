<script setup lang="ts">
import { computed } from 'vue';
import { ZODIAC_ELEMENT_META, type ZodiacConstellation } from '../../three/zodiac-data';

const props = defineProps<{
  constellation: ZodiacConstellation;
  occupancy?: number;
  roomCount?: number;
  isMine?: boolean;
}>();

const elementMeta = computed(() => ZODIAC_ELEMENT_META[props.constellation.element]);
</script>

<template>
  <div class="glass-gold pointer-events-none w-64 rounded-2xl p-4">
    <div class="flex items-start justify-between">
      <div class="flex items-center gap-3">
        <span
          class="flex h-11 w-11 items-center justify-center rounded-full border border-astro-gold/40 bg-astro-gold/10 text-xl text-astro-bright"
        >
          {{ constellation.symbol }}
        </span>
        <div>
          <p class="font-serif-astro text-base text-astro-cream">{{ constellation.name }}</p>
          <p class="font-mono-tech text-[10px] tracking-widest text-astro-dusk">{{ constellation.dateRange }}</p>
        </div>
      </div>
      <span
        v-if="isMine"
        class="rounded-full border border-astro-bright/50 bg-astro-gold/15 px-2 py-0.5 text-[10px] text-astro-bright"
      >
        我的星座
      </span>
    </div>

    <div class="astro-divider my-3"></div>

    <p class="font-serif-astro text-xs leading-relaxed text-astro-cream/85">{{ constellation.motto }}</p>

    <div class="mt-3 flex items-center justify-between text-[11px]">
      <span
        class="rounded-full border px-2 py-0.5"
        :style="{ borderColor: `${elementMeta.css}66`, color: elementMeta.css }"
      >
        {{ elementMeta.label }}
      </span>
      <span class="font-mono-tech text-astro-cream/70">
        <template v-if="roomCount !== undefined">{{ roomCount }} 间自习室 · </template>
        <span class="text-astro-bright">{{ occupancy ?? 0 }}</span> 人在学
      </span>
    </div>

    <p class="mt-3 text-center font-mono-tech text-[10px] uppercase tracking-[0.3em] text-astro-dusk">
      点击进入星座
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

const ZODIAC = [
  { slug: 'aries', name: '白羊座', symbol: '♈' },
  { slug: 'taurus', name: '金牛座', symbol: '♉' },
  { slug: 'gemini', name: '双子座', symbol: '♊' },
  { slug: 'cancer', name: '巨蟹座', symbol: '♋' },
  { slug: 'leo', name: '狮子座', symbol: '♌' },
  { slug: 'virgo', name: '处女座', symbol: '♍' },
  { slug: 'libra', name: '天秤座', symbol: '♎' },
  { slug: 'scorpio', name: '天蝎座', symbol: '♏' },
  { slug: 'sagittarius', name: '射手座', symbol: '♐' },
  { slug: 'capricorn', name: '摩羯座', symbol: '♑' },
  { slug: 'aquarius', name: '水瓶座', symbol: '♒' },
  { slug: 'pisces', name: '双鱼座', symbol: '♓' },
];

const tips = [
  '今日适合整理错题本，把知识残片重新点亮。',
  '把一个难题拆成三颗小行星，逐一点亮更稳。',
  '适合约同学进入自习星，共享一段 25 分钟专注。',
  '复习前先用画像追问一次自己的薄弱维度。',
  '用举一反三生成 2 道变式题，检验真掌握。',
  '保持番茄节奏，桌宠也会更活泼地陪你。',
];

const slug = ref(localStorage.getItem('sparkorbit_zodiac') || 'leo');

function hash(s: string) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

const fortune = computed(() => {
  const day = new Date().toISOString().slice(0, 10);
  const h = hash(`${slug.value}-${day}`);
  const score = 55 + (h % 40);
  const tip = tips[h % tips.length];
  const z = ZODIAC.find((x) => x.slug === slug.value) || ZODIAC[0];
  return { score, tip, z };
});

function onChange() {
  localStorage.setItem('sparkorbit_zodiac', slug.value);
}
</script>

<template>
  <div class="space-y-4">
    <select v-model="slug" class="w-full rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white outline-none" @change="onChange">
      <option v-for="z in ZODIAC" :key="z.slug" :value="z.slug">{{ z.symbol }} {{ z.name }}</option>
    </select>
    <div class="rounded-2xl border border-violet-400/20 bg-violet-500/10 p-5 text-center">
      <p class="text-3xl">{{ fortune.z.symbol }}</p>
      <p class="mt-2 text-lg font-semibold text-white">{{ fortune.z.name }} · 学习运势</p>
      <p class="mt-3 text-4xl font-semibold text-amber-200">{{ fortune.score }}</p>
      <p class="mt-3 text-sm leading-6 text-slate-300">{{ fortune.tip }}</p>
    </div>
  </div>
</template>

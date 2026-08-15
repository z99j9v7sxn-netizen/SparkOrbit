<script setup lang="ts">
import { ref } from 'vue';
import { fetchGalaxies, fetchGalaxyDetail, type PlanetStatus } from '../../api/orbit';
import { LzButton, LzEmptyState } from './ui';

withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false });
export interface NavigationTarget {
  galaxySlug: string;
  galaxyName: string;
  planetSlug: string;
  planetName: string;
}
const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'navigate', target: NavigationTarget): void;
}>();

type RouteNode = NavigationTarget & {
  description: string;
  status: PlanetStatus;
  score: number;
};

const loading = ref(false);
const generated = ref(false);
const route = ref<RouteNode[]>([]);
const error = ref('');

function priority(status: PlanetStatus) {
  if (status === 'meteor' || status === 'fading') return 0;
  if (status === 'dim') return 1;
  if (status === 'lit') return 2;
  return 3;
}

async function generatePath() {
  loading.value = true;
  error.value = '';
  try {
    const galaxies = await fetchGalaxies();
    const details = await Promise.all(galaxies.map((galaxy) => fetchGalaxyDetail(galaxy.slug)));
    route.value = details
      .flatMap((galaxy) => galaxy.planets
        .filter((planet) => planet.status !== 'locked')
        .map((planet) => ({
          galaxySlug: galaxy.slug,
          galaxyName: galaxy.name,
          planetSlug: planet.slug,
          planetName: planet.name,
          status: planet.status,
          score: planet.score,
          description: planet.status === 'meteor' || planet.status === 'fading'
            ? '记忆正在衰减，建议优先复习'
            : planet.status === 'dim'
              ? '尚未掌握，适合作为下一学习目标'
              : '已点亮，可用于巩固与迁移',
        })))
      .sort((a, b) => priority(a.status) - priority(b.status) || a.score - b.score)
      .slice(0, 5);
    generated.value = true;
  } catch (e) {
    error.value = e instanceof Error ? e.message : '路线生成失败';
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="flex h-full w-full flex-col">
    <div class="border-b border-[var(--border-soft)] pb-4">
      <h3 class="lz-title">下一程，从薄弱处开始</h3>
      <p class="lz-desc mt-2 max-w-[54ch]">按掌握状态排序下一程目标，一键跃迁到 3D 星图（与学习路径的计划打卡互补）。</p>
    </div>

    <div v-if="!generated" class="flex flex-1 flex-col items-center justify-center py-16 text-center">
      <div class="h-24 w-24 rounded-full border border-[rgb(var(--lz-accent)/0.15)] bg-[radial-gradient(circle,rgb(var(--lz-accent)/0.18),transparent_65%)]"></div>
      <LzButton variant="primary" size="lg" class="mt-7" :loading="loading" @click="generatePath">
        {{ loading ? '正在计算学习轨道' : '生成真实学习路线' }}
      </LzButton>
    </div>

    <div v-else class="mt-4 min-h-0 flex-1 overflow-auto">
      <div v-if="route.length" class="space-y-2">
        <article v-for="(node, index) in route" :key="node.planetSlug" class="lz-card lz-card--hover grid grid-cols-[36px_1fr_auto] items-center gap-3 p-3">
          <span class="lz-caption font-mono">{{ String(index + 1).padStart(2, '0') }}</span>
          <div class="min-w-0">
            <p class="lz-subtitle truncate">{{ node.planetName }}</p>
            <p class="lz-caption mt-1 truncate">{{ node.galaxyName }} / {{ node.description }}</p>
          </div>
          <LzButton variant="soft" size="sm" @click="emit('navigate', node)">跃迁</LzButton>
        </article>
      </div>
      <LzEmptyState
        v-else
        icon="🛰️"
        title="当前没有可推荐的行星"
        desc="先去星图解锁几颗行星，再回来生成学习路线"
      />
      <LzButton variant="ghost" size="sm" block class="mt-4" @click="generatePath">重新计算</LzButton>
    </div>
    <p v-if="error" class="lz-caption mt-3 text-rose-300">{{ error }}</p>
  </div>
</template>

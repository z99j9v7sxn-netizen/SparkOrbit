<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { fetchGalaxyDetail } from '../../api/orbit';
import { deletePlanet, forgeTeacherGalaxy } from '../../api/teacher';
import TeacherPageHeader from './TeacherPageHeader.vue';

const title = ref('');
const msg = ref('');
const forging = ref(false);
const result = ref<{ galaxy_name?: string; planet_count?: number; galaxy_slug?: string } | null>(null);
const planets = ref<Array<{ slug: string; name: string }>>([]);
const loadingPlanets = ref(false);

async function loadPlanets() {
  if (!result.value?.galaxy_slug) {
    planets.value = [];
    return;
  }
  loadingPlanets.value = true;
  try {
    const detail = await fetchGalaxyDetail(result.value.galaxy_slug);
    planets.value = detail.planets.map((planet) => ({ slug: planet.slug, name: planet.name }));
  } catch {
    planets.value = [];
  } finally {
    loadingPlanets.value = false;
  }
}

async function handleForge(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  forging.value = true;
  msg.value = '正在解析 PDF 并生成星系…';
  result.value = null;
  planets.value = [];
  try {
    const res = await forgeTeacherGalaxy(file, title.value.trim() || file.name);
    result.value = {
      galaxy_name: (res.galaxy_name as string) || undefined,
      planet_count: Number(res.planet_count ?? 0),
      galaxy_slug: (res.galaxy_slug as string) || undefined,
    };
    msg.value = `星系「${result.value.galaxy_name || '未命名'}」已生成，共 ${result.value.planet_count ?? 0} 颗行星`;
    title.value = '';
    await loadPlanets();
  } catch (err) {
    msg.value = err instanceof Error ? err.message : 'PDF 星系锻造失败';
  } finally {
    forging.value = false;
    input.value = '';
  }
}

async function removePlanet(slug: string, name: string) {
  if (!confirm(`确认删除行星「${name}」？`)) return;
  try {
    await deletePlanet(slug);
    msg.value = `已删除行星 ${name}`;
    await loadPlanets();
    if (result.value) {
      result.value.planet_count = planets.value.length;
    }
  } catch (err) {
    msg.value = err instanceof Error ? err.message : '删除失败';
  }
}

watch(() => result.value?.galaxy_slug, () => {
  void loadPlanets();
});

onMounted(() => {
  if (result.value?.galaxy_slug) void loadPlanets();
});
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="星系锻造" subtitle="上传 PDF 课件，AI 自动拆解为知识星系与行星" accent="violet" />

    <section class="t-card glass-edge p-5">
      <div class="flex items-baseline justify-between gap-2">
        <h3 class="text-[15px] font-semibold text-t-1">从 PDF 锻造星系</h3>
        <span class="t-kicker">Forge</span>
      </div>
      <p class="mt-1 text-xs text-t-3">支持教学讲义、教材章节等 PDF 文件</p>
      <input v-model="title" placeholder="星系标题提示（可选）" class="t-input mt-4 md:max-w-md" />
      <label
        class="mt-4 flex cursor-pointer flex-col items-center gap-2 rounded-xl border border-dashed border-t-accent2/35 bg-t-accent2/5 px-4 py-12 text-sm text-t-accent2 transition hover:bg-t-accent2/10"
        :class="forging ? 'pointer-events-none opacity-60' : ''"
      >
        <svg viewBox="0 0 24 24" class="h-8 w-8 opacity-80" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3.2" />
          <path d="M12 5.5c4.6 0 8.5 1.4 8.5 3.2 0 1-1.3 1.9-3.3 2.5M12 5.5c-4.6 0-8.5 1.4-8.5 3.2 0 1 1.3 1.9 3.3 2.5M12 18.5c4.6 0 8.5-1.4 8.5-3.2 0-1-1.3-1.9-3.3-2.5M12 18.5c-4.6 0-8.5-1.4-8.5-3.2 0-1 1.3-1.9 3.3-2.5" />
        </svg>
        <span>{{ forging ? '锻造中，请稍候…' : '点击选择 PDF 文件' }}</span>
        <input type="file" accept=".pdf,application/pdf" class="hidden" @change="handleForge" />
      </label>
      <p v-if="msg" class="mt-3 text-sm" :class="msg.includes('失败') ? 'text-t-danger' : 'text-t-accent'">{{ msg }}</p>

      <div v-if="result" class="mt-5 grid gap-3 sm:grid-cols-3">
        <div class="t-card--flat rounded-xl border border-t-line/10 px-4 py-3">
          <p class="text-xs text-t-3">星系名称</p>
          <p class="mt-1 text-sm font-medium text-t-1">{{ result.galaxy_name || '—' }}</p>
        </div>
        <div class="t-card--flat rounded-xl border border-t-line/10 px-4 py-3">
          <p class="text-xs text-t-3">行星数量</p>
          <p class="mt-1 font-mono-tech text-sm font-medium text-t-ok">{{ planets.length || result.planet_count || 0 }}</p>
        </div>
        <div class="t-card--flat rounded-xl border border-t-line/10 px-4 py-3">
          <p class="text-xs text-t-3">Slug</p>
          <p class="mt-1 font-mono-tech text-xs text-t-2">{{ result.galaxy_slug || '—' }}</p>
        </div>
      </div>

      <div v-if="result?.galaxy_slug" class="mt-6">
        <div class="flex items-center justify-between">
          <h4 class="text-sm font-medium text-t-1">行星管理</h4>
          <button type="button" class="t-btn t-btn--ghost t-btn--sm" :disabled="loadingPlanets" @click="loadPlanets">
            {{ loadingPlanets ? '刷新中…' : '刷新列表' }}
          </button>
        </div>
        <div v-if="planets.length" class="mt-3 space-y-2">
          <div
            v-for="planet in planets"
            :key="planet.slug"
            class="flex items-center justify-between rounded-xl border border-t-line/10 bg-t-s1/30 px-3 py-2 text-sm"
          >
            <div>
              <p class="font-medium text-t-1">{{ planet.name }}</p>
              <p class="font-mono-tech text-[10px] text-t-3">{{ planet.slug }}</p>
            </div>
            <button type="button" class="t-btn t-btn--danger t-btn--sm" @click="removePlanet(planet.slug, planet.name)">
              删除
            </button>
          </div>
        </div>
        <p v-else class="mt-3 text-xs text-t-3">暂无行星或列表加载中</p>
      </div>
    </section>
  </div>
</template>

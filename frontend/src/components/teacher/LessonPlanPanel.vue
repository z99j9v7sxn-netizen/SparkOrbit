<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { fetchGalaxies, fetchGalaxyDetail, generateLessonPlan, type Galaxy, type LessonPlan, type Planet } from '../../api/orbit';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';

const galaxies = ref<Galaxy[]>([]);
const planets = ref<Planet[]>([]);
const selectedGalaxy = ref('');
const selectedPlanet = ref('');
const plan = ref<LessonPlan | null>(null);
const loadingGalaxies = ref(false);
const loadingPlanets = ref(false);
const generating = ref(false);
const error = ref('');
const copyMsg = ref('');

async function loadGalaxies() {
  loadingGalaxies.value = true;
  try {
    galaxies.value = await fetchGalaxies();
    if (!selectedGalaxy.value && galaxies.value[0]) {
      selectedGalaxy.value = galaxies.value[0].slug;
    }
  } finally {
    loadingGalaxies.value = false;
  }
}

async function loadPlanets() {
  if (!selectedGalaxy.value) {
    planets.value = [];
    return;
  }
  loadingPlanets.value = true;
  plan.value = null;
  selectedPlanet.value = '';
  try {
    const detail = await fetchGalaxyDetail(selectedGalaxy.value);
    planets.value = detail.planets || [];
  } catch {
    planets.value = [];
  } finally {
    loadingPlanets.value = false;
  }
}

async function handleGenerate(slug?: string) {
  const target = slug || selectedPlanet.value;
  if (!target) return;
  selectedPlanet.value = target;
  generating.value = true;
  error.value = '';
  plan.value = null;
  try {
    plan.value = await generateLessonPlan(target);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '生成教案失败';
  } finally {
    generating.value = false;
  }
}

function toMarkdown(p: LessonPlan) {
  const lines = [
    `# ${p.planet_name} 教案`,
    '',
    '## 学习目标',
    ...p.learning_goals.map((g) => `- ${g}`),
    '',
    '## 教学思路',
    p.teaching_approach,
    '',
    '## 例题',
    ...p.example_problems.map((g, i) => `${i + 1}. ${g}`),
    '',
    '## 常见错误',
    ...p.common_mistakes.map((g) => `- ${g}`),
    '',
    '## 练习计划',
    ...p.practice_plan.map((g) => `- ${g}`),
    '',
    '## 自检清单',
    ...p.self_check.map((g) => `- ${g}`),
  ];
  return lines.join('\n');
}

async function copyMarkdown() {
  if (!plan.value) return;
  await navigator.clipboard.writeText(toMarkdown(plan.value));
  copyMsg.value = '已复制 Markdown';
  setTimeout(() => (copyMsg.value = ''), 2000);
}

function downloadMarkdown() {
  if (!plan.value) return;
  const blob = new Blob([toMarkdown(plan.value)], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${plan.value.planet_name || '教案'}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

watch(selectedGalaxy, () => void loadPlanets());
onMounted(async () => {
  await loadGalaxies();
  await loadPlanets();
});
</script>

<template>
  <div class="space-y-5">
    <TeacherPageHeader title="AI 教案生成" subtitle="选择知识点行星，一键生成结构化教案" />

    <div class="grid gap-5 lg:grid-cols-[280px_1fr]">
      <section class="glass space-y-4 rounded-2xl p-5">
        <div>
          <label class="text-xs text-slate-400">星系</label>
          <select
            v-model="selectedGalaxy"
            class="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
          >
            <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
          </select>
        </div>
        <TeacherLoading v-if="loadingGalaxies || loadingPlanets" label="加载行星…" />
        <div v-else class="max-h-[28rem] space-y-1 overflow-y-auto">
          <button
            v-for="p in planets"
            :key="p.slug"
            type="button"
            class="flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition"
            :class="selectedPlanet === p.slug ? 'bg-sky-500/20 text-sky-100' : 'text-slate-300 hover:bg-white/5'"
            @click="handleGenerate(p.slug)"
          >
            <span>{{ p.name }}</span>
            <span class="text-[10px] text-slate-500">{{ p.difficulty }}</span>
          </button>
          <TeacherEmptyState v-if="!planets.length" title="该星系暂无行星" />
        </div>
      </section>

      <section class="glass rounded-2xl p-5">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h3 class="text-base font-semibold text-white">
            {{ plan?.planet_name ? `${plan.planet_name} · 教案` : '教案预览' }}
          </h3>
          <div v-if="plan" class="flex gap-2">
            <button type="button" class="rounded-lg border border-white/10 px-3 py-1 text-xs text-slate-200" @click="copyMarkdown">
              复制 Markdown
            </button>
            <button type="button" class="rounded-lg border border-sky-300/20 px-3 py-1 text-xs text-sky-100" @click="downloadMarkdown">
              导出 .md
            </button>
          </div>
        </div>
        <p v-if="copyMsg" class="mt-1 text-xs text-emerald-300">{{ copyMsg }}</p>
        <p v-if="error" class="mt-2 text-sm text-rose-300">{{ error }}</p>
        <TeacherLoading v-if="generating" label="AI 正在生成教案…" />

        <div v-else-if="plan" class="mt-4 space-y-4 text-sm text-slate-300">
          <div>
            <h4 class="text-xs uppercase tracking-wider text-sky-300/80">学习目标</h4>
            <ul class="mt-2 list-inside list-disc space-y-1">
              <li v-for="(g, i) in plan.learning_goals" :key="i">{{ g }}</li>
            </ul>
          </div>
          <div>
            <h4 class="text-xs uppercase tracking-wider text-sky-300/80">教学思路</h4>
            <p class="mt-2 whitespace-pre-wrap">{{ plan.teaching_approach }}</p>
          </div>
          <div>
            <h4 class="text-xs uppercase tracking-wider text-sky-300/80">例题</h4>
            <ol class="mt-2 list-inside list-decimal space-y-1">
              <li v-for="(g, i) in plan.example_problems" :key="i">{{ g }}</li>
            </ol>
          </div>
          <div>
            <h4 class="text-xs uppercase tracking-wider text-sky-300/80">常见错误</h4>
            <ul class="mt-2 list-inside list-disc space-y-1">
              <li v-for="(g, i) in plan.common_mistakes" :key="i">{{ g }}</li>
            </ul>
          </div>
          <div>
            <h4 class="text-xs uppercase tracking-wider text-sky-300/80">练习计划</h4>
            <ul class="mt-2 list-inside list-disc space-y-1">
              <li v-for="(g, i) in plan.practice_plan" :key="i">{{ g }}</li>
            </ul>
          </div>
          <div>
            <h4 class="text-xs uppercase tracking-wider text-sky-300/80">自检清单</h4>
            <ul class="mt-2 list-inside list-disc space-y-1">
              <li v-for="(g, i) in plan.self_check" :key="i">{{ g }}</li>
            </ul>
          </div>
        </div>
        <TeacherEmptyState
          v-else-if="!generating"
          class="mt-8"
          title="选择左侧行星生成教案"
          description="点击行星名称即可调用 AI 生成结构化教案"
        />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { fetchGalaxies, fetchGalaxyDetail, type Galaxy, type Planet } from '../api/orbit';
import {
  fetchGradebook,
  fetchStudentDetail,
  type GradebookRow,
} from '../api/teacher';
import { useTeacherClassStore } from '../stores/teacherClass';
import SimulationConsole from './SimulationConsole.vue';

interface DimSlider {
  key: string;
  label: string;
  value: number;
}

const consoleRef = ref<InstanceType<typeof SimulationConsole> | null>(null);
const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);

const galaxies = ref<Galaxy[]>([]);
const planets = ref<Planet[]>([]);
const selectedGalaxy = ref('');
const selectedPlanetSlug = ref('');
const loadingGalaxies = ref(false);
const loadingPlanets = ref(false);
const running = ref(false);

const roster = ref<GradebookRow[]>([]);
const selectedStudentId = ref('');
const selectedProfileId = ref('');
const selectedStudentName = ref('');
const loadingStudent = ref(false);
const studentHint = ref('');

const dims = reactive<DimSlider[]>([
  { key: 'major_background', label: '专业背景', value: 68 },
  { key: 'prior_knowledge', label: '前置知识', value: 55 },
  { key: 'cognitive_style', label: '认知风格', value: 78 },
  { key: 'mistake_tendency', label: '易错倾向', value: 42 },
  { key: 'learning_goal', label: '学习目标', value: 82 },
  { key: 'time_flexibility', label: '时间弹性', value: 61 },
  { key: 'modality_preference', label: '资源模态偏好', value: 55 },
  { key: 'motivation_level', label: '学习动机强度', value: 60 },
]);

const selectedPlanet = computed(() => planets.value.find((p) => p.slug === selectedPlanetSlug.value) || null);
const topicName = computed(() => selectedPlanet.value?.name || '');
const portraitLabel = computed(() => {
  if (selectedStudentId.value && selectedStudentName.value) {
    return `真实学生 · ${selectedStudentName.value}`;
  }
  return '手动合成画像';
});

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
    selectedPlanetSlug.value = '';
    return;
  }
  loadingPlanets.value = true;
  selectedPlanetSlug.value = '';
  try {
    const detail = await fetchGalaxyDetail(selectedGalaxy.value);
    planets.value = detail.planets || [];
    if (planets.value[0]) selectedPlanetSlug.value = planets.value[0].slug;
  } catch {
    planets.value = [];
  } finally {
    loadingPlanets.value = false;
  }
}

async function loadRoster() {
  if (!classId.value) {
    roster.value = [];
    return;
  }
  try {
    roster.value = await fetchGradebook(classId.value);
  } catch {
    roster.value = [];
  }
}

function dimScoreFromRaw(raw: unknown): number {
  if (raw && typeof raw === 'object' && 'score' in raw) {
    return Math.max(0, Math.min(100, Number((raw as { score?: number }).score ?? 50)));
  }
  if (typeof raw === 'number') return Math.max(0, Math.min(100, raw));
  return 50;
}

async function onStudentChange() {
  selectedProfileId.value = '';
  selectedStudentName.value = '';
  if (!selectedStudentId.value) {
    return;
  }
  loadingStudent.value = true;
  studentHint.value = '';
  try {
    const detail = await fetchStudentDetail(selectedStudentId.value, classId.value || '');
    selectedStudentName.value = detail.display_name || detail.username;
    selectedProfileId.value = detail.profile_id || detail.profile?.id || '';
    if (detail.profile?.dimensions) {
      dims.forEach((d) => {
        d.value = dimScoreFromRaw(detail.profile!.dimensions[d.key]);
      });
      studentHint.value = '已载入该学生真实六维分数，可微调后推演。';
    } else {
      studentHint.value = '该学生暂无画像，可手动调分后以合成方式推演。';
    }
  } catch (err) {
    studentHint.value = err instanceof Error ? err.message : '加载学生画像失败';
    selectedStudentId.value = '';
  } finally {
    loadingStudent.value = false;
  }
}

function preset(kind: 'pass' | 'goal' | 'weak') {
  selectedStudentId.value = '';
  selectedProfileId.value = '';
  selectedStudentName.value = '';
  studentHint.value = '已切换为预设合成画像';
  if (kind === 'pass') dims.forEach((d) => (d.value = 90));
  if (kind === 'weak') dims.forEach((d) => (d.value = 35));
  if (kind === 'goal') {
    const g = dims.find((d) => d.key === 'learning_goal');
    if (g) g.value = 100;
  }
}

function startSimulation() {
  if (!selectedPlanet.value || running.value) return;
  running.value = true;
  const overrides: Record<string, number> = {};
  dims.forEach((d) => (overrides[d.key] = d.value));
  void consoleRef.value?.run(selectedPlanet.value.name, overrides, undefined, {
    userId: selectedStudentId.value || undefined,
    studentProfileId: selectedProfileId.value || undefined,
    planetSlug: selectedPlanet.value.slug || undefined,
  });
  window.setTimeout(() => {
    running.value = false;
  }, 1200);
}

watch(selectedGalaxy, () => void loadPlanets());
watch(classId, () => {
  selectedStudentId.value = '';
  selectedProfileId.value = '';
  selectedStudentName.value = '';
  studentHint.value = '';
  void loadRoster();
});
watch(selectedStudentId, () => void onStudentChange());
onMounted(async () => {
  await Promise.all([loadGalaxies(), loadRoster()]);
  await loadPlanets();
});
</script>

<template>
  <section class="t-card glass-edge p-5">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 class="text-[15px] font-semibold text-t-1">多智能体推演沙盘</h2>
        <p class="mt-1 text-xs leading-5 text-t-3">
          选择星系与知识点行星，载入真实学生六维或调节合成画像，一键启动 Teacher / Mirror / Evaluator / Planner 推演。
        </p>
      </div>
      <div class="flex flex-wrap gap-1.5 text-[11px]">
        <button type="button" class="t-btn t-btn--sm border-t-ok/30 bg-t-ok/10 text-t-ok hover:bg-t-ok/18" @click="preset('pass')">
          拉满全维度
        </button>
        <button type="button" class="t-btn t-btn--sm border-t-warn/30 bg-t-warn/10 text-t-warn hover:bg-t-warn/18" @click="preset('goal')">
          目标→满分
        </button>
        <button type="button" class="t-btn t-btn--danger t-btn--sm" @click="preset('weak')">
          模拟薄弱生
        </button>
      </div>
    </div>

    <div class="mt-4 grid gap-4 lg:grid-cols-[280px_1fr_1.1fr]">
      <!-- 知识点选择 -->
      <div class="t-card--flat space-y-3 rounded-xl border border-t-line/10 p-3">
        <div>
          <label class="text-[11px] text-t-3">星系</label>
          <select v-model="selectedGalaxy" class="t-input mt-1 cursor-pointer" :disabled="loadingGalaxies">
            <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
          </select>
        </div>
        <p v-if="loadingPlanets" class="text-xs text-t-3">加载知识点…</p>
        <div v-else class="max-h-72 space-y-1 overflow-y-auto">
          <button
            v-for="p in planets"
            :key="p.slug"
            type="button"
            class="flex w-full flex-col rounded-xl px-3 py-2 text-left text-sm transition"
            :class="selectedPlanetSlug === p.slug ? 'bg-t-accent/12 text-t-1 ring-1 ring-t-accent/30' : 'text-t-2 hover:bg-t-line/5'"
            @click="selectedPlanetSlug = p.slug"
          >
            <span class="flex items-center justify-between gap-2">
              <span class="truncate font-medium">{{ p.name }}</span>
              <span class="shrink-0 text-[10px] text-t-3">{{ p.difficulty }}</span>
            </span>
            <span v-if="p.description" class="mt-0.5 line-clamp-2 text-[10px] text-t-3">{{ p.description }}</span>
          </button>
          <p v-if="!planets.length" class="px-2 py-4 text-center text-xs text-t-3">该星系暂无知识点</p>
        </div>
      </div>

      <!-- 画像滑杆 + 启动 -->
      <div class="space-y-3">
        <div class="t-card--flat rounded-xl border border-t-line/10 px-3 py-2">
          <p class="text-[11px] text-t-3">当前知识点</p>
          <p class="mt-1 text-sm font-medium text-t-1">{{ topicName || '请先选择行星' }}</p>
          <p v-if="selectedPlanet" class="mt-0.5 font-mono-tech text-[10px] text-t-3">{{ selectedPlanet.slug }}</p>
        </div>

        <div class="t-card--flat rounded-xl border border-t-line/10 px-3 py-2">
          <label class="text-[11px] text-t-3">学生六维来源</label>
          <select v-model="selectedStudentId" class="t-input mt-1 cursor-pointer" :disabled="loadingStudent || !classId">
            <option value="">手动合成（默认）</option>
            <option v-for="s in roster" :key="s.user_id" :value="s.user_id">
              {{ s.display_name }}（{{ s.username }}）
            </option>
          </select>
          <p class="mt-1 text-[10px] text-t-3">{{ portraitLabel }}</p>
          <p v-if="!classId" class="mt-1 text-[10px] text-t-warn">请先在顶部选择班级以加载学生列表</p>
          <p v-else-if="loadingStudent" class="mt-1 text-[10px] text-t-3">正在载入真实六维…</p>
          <p v-else-if="studentHint" class="mt-1 text-[10px] text-t-accent">{{ studentHint }}</p>
        </div>

        <div class="space-y-2">
          <div v-for="d in dims" :key="d.key" class="t-card--flat rounded-xl border border-t-line/10 px-3 py-2">
            <div class="flex items-center justify-between text-[11px]">
              <span class="text-t-2">{{ d.label }}</span>
              <span class="font-mono-tech tabular-nums text-t-accent">{{ d.value }}</span>
            </div>
            <input v-model.number="d.value" type="range" min="0" max="100" class="t-check mt-1 w-full" />
          </div>
        </div>
        <button
          type="button"
          class="t-btn t-btn--primary t-btn--md w-full"
          :disabled="!selectedPlanet || running"
          @click="startSimulation"
        >
          {{ running ? '推演启动中…' : '开始推演' }}
        </button>
        <p v-if="!selectedPlanet" class="text-center text-[11px] text-t-warn">请先在左侧选择知识点行星</p>
      </div>

      <!-- 推演终端 -->
      <div class="h-[480px] min-h-[320px]">
        <SimulationConsole
          ref="consoleRef"
          :closable="false"
          variant="teacher"
          :initial-topic="topicName"
        />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import {
  createBilibiliAsset,
  deleteStarAsset,
  listStarAssets,
  uploadStarlibPdf,
  type StarAsset,
} from '../../api/challengeSprint';
import {
  consumeResourceStream,
  fetchDeckTemplates,
  fetchLearnResources,
  startResourceGeneration,
  type DeckTemplateMeta,
  type GeneratedResource,
  type ResourceKind,
  type ResourceStreamEvent,
} from '../../api/learnExtras';
import { fetchGalaxies, fetchGalaxyDetail, generateLessonPlan, type LessonPlan } from '../../api/orbit';
import {
  createTeacherResourceFromText,
  deleteTeacherResource,
  fetchLessonResources,
  promoteGeneratedResource,
  promoteTeacherResource,
  uploadTeacherResource,
  type LessonResourceItem,
} from '../../api/zone';
import MarkdownView from '../common/MarkdownView.vue';
import PdfViewer from '../learning/PdfViewer.vue';
import { buildResourceDownload, triggerResourceDownload } from '../../lib/resourceDownload';
import { useTeacherClassStore } from '../../stores/teacherClass';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';

type TabKey = 'materials' | 'ai' | 'starlib';

const KIND_LABELS: Record<string, string> = {
  book: '书本',
  deck: '课件',
  quiz: '题库',
  plan: '教案',
  video: '视频',
  other: '其他',
};

const AI_KINDS: { id: ResourceKind; label: string }[] = [
  { id: 'deck', label: '教学课件 PPT' },
  { id: 'quiz', label: '练习题' },
  { id: 'doc', label: '讲义文档' },
  { id: 'mindmap', label: '思维导图' },
];

const QUIZ_TYPE_OPTIONS: { id: string; label: string }[] = [
  { id: 'choice', label: '选择题' },
  { id: 'blank', label: '填空题' },
  { id: 'essay', label: '大题' },
  { id: 'code', label: '程序题' },
];

const QUIZ_TYPE_LABELS: Record<string, string> = {
  choice: '选择题',
  blank: '填空题',
  essay: '大题',
  case: '大题',
  code: '程序题',
};

type MaterialsView = 'galaxy' | 'kind';

type DeckSlide = {
  title?: string;
  bullet_points?: string[];
  bullets?: string[];
  narration?: string;
};

type DeckPack = {
  title: string;
  slides: DeckSlide[];
  pptx_url?: string;
  export_error?: string;
};

const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);

const tab = ref<TabKey>('materials');
const galaxies = ref<{ slug: string; name: string }[]>([]);
const planets = ref<{ slug: string; name: string }[]>([]);
const msg = ref('');
const materialsView = ref<MaterialsView>('galaxy');
const llmInfo = ref<{ available: boolean; label: string; model: string; provider: string }>({
  available: false,
  label: '检测中…',
  model: '',
  provider: '',
});

// —— 资料库 ——
const resources = ref<LessonResourceItem[]>([]);
const loadingMaterials = ref(false);
const filterGalaxy = ref('');
const filterKind = ref('');
const title = ref('');
const uploadGalaxy = ref('');
const uploadKind = ref('other');
const uploading = ref(false);
const promoteBusy = ref('');
const collapsedGroups = ref<Record<string, boolean>>({});

// —— AI 工坊 ——
const aiMode = ref<'plan' | 'workshop'>('plan');
const selectedGalaxy = ref('');
const selectedPlanet = ref('');
const plan = ref<LessonPlan | null>(null);
const generatingPlan = ref(false);
const selectedKinds = ref<ResourceKind[]>(['deck', 'quiz', 'doc']);
const selectedQuizTypes = ref<string[]>(['choice', 'blank', 'essay', 'code']);
const extraReq = ref('');
const generating = ref(false);
const deckTemplate = ref('orbit');
const deckTemplates = ref<DeckTemplateMeta[]>([]);
const streamLog = ref<string[]>([]);
const workshopResources = ref<GeneratedResource[]>([]);
const activeResource = ref<GeneratedResource | null>(null);
const aiMsg = ref('');
const deckIndex = ref(0);

// —— 班级星库 ——
const starAssets = ref<StarAsset[]>([]);
const loadingStar = ref(false);
const activeStar = ref<StarAsset | null>(null);
const starTitle = ref('');
const starGalaxy = ref('');
const starAssetType = ref('book');
const starBusy = ref(false);
const starMsg = ref('');
const deletingStarId = ref('');
const biliBvid = ref('');
const biliTitle = ref('');
const biliGalaxy = ref('');
const biliBusy = ref(false);
const biliMsg = ref('');

const galaxyNameMap = computed(() => Object.fromEntries(galaxies.value.map((g) => [g.slug, g.name])));

const filteredMaterials = computed(() => {
  let list = resources.value;
  if (classId.value) list = list.filter((r) => !r.class_id || r.class_id === classId.value);
  if (filterGalaxy.value) list = list.filter((r) => r.galaxy_slug === filterGalaxy.value);
  if (filterKind.value) list = list.filter((r) => (r.resource_kind || 'other') === filterKind.value);
  return list;
});

type MaterialGroup = { key: string; label: string; items: LessonResourceItem[] };

const materialGroups = computed<MaterialGroup[]>(() => {
  const list = filteredMaterials.value;
  const map = new Map<string, LessonResourceItem[]>();
  if (materialsView.value === 'galaxy') {
    for (const r of list) {
      const key = r.galaxy_slug || '__none__';
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(r);
    }
    return [...map.entries()]
      .map(([key, items]) => ({
        key: `g:${key}`,
        label: key === '__none__' ? '未关联星系' : galaxyNameMap.value[key] || key,
        items,
      }))
      .sort((a, b) => a.label.localeCompare(b.label, 'zh'));
  }
  for (const r of list) {
    const kind = r.resource_kind || 'other';
    if (!map.has(kind)) map.set(kind, []);
    map.get(kind)!.push(r);
  }
  const order = ['plan', 'deck', 'quiz', 'video', 'book', 'other'];
  return order
    .filter((k) => map.has(k))
    .map((k) => ({
      key: `k:${k}`,
      label: KIND_LABELS[k] || k,
      items: map.get(k)!,
    }));
});

function toggleGroup(key: string) {
  collapsedGroups.value = { ...collapsedGroups.value, [key]: !collapsedGroups.value[key] };
}

async function loadLlmStatus() {
  try {
    const res = await fetch('/api/public/health-capabilities');
    const data = await res.json();
    const llm = data?.llm || {};
    llmInfo.value = {
      available: !!llm.configured,
      label: llm.label || (llm.configured ? '已配置' : '未配置'),
      model: llm.model || '',
      provider: llm.provider || '',
    };
  } catch {
    llmInfo.value = { available: false, label: '无法检测', model: '', provider: '' };
  }
}

async function loadGalaxies() {
  galaxies.value = (await fetchGalaxies()).map((g) => ({ slug: g.slug, name: g.name }));
  if (!selectedGalaxy.value && galaxies.value[0]) selectedGalaxy.value = galaxies.value[0].slug;
}

async function loadPlanets() {
  if (!selectedGalaxy.value) {
    planets.value = [];
    return;
  }
  try {
    const detail = await fetchGalaxyDetail(selectedGalaxy.value);
    planets.value = (detail.planets || []).map((p) => ({ slug: p.slug, name: p.name }));
    if (!selectedPlanet.value && planets.value[0]) selectedPlanet.value = planets.value[0].slug;
  } catch {
    planets.value = [];
  }
}

async function loadMaterials() {
  loadingMaterials.value = true;
  try {
    resources.value = await fetchLessonResources(filterGalaxy.value);
  } catch {
    resources.value = [];
  } finally {
    loadingMaterials.value = false;
  }
}

async function loadStarlib() {
  loadingStar.value = true;
  try {
    const all = await listStarAssets(filterGalaxy.value);
    starAssets.value = classId.value
      ? all.filter((a) => !a.class_id || a.class_id === classId.value)
      : all;
  } catch {
    starAssets.value = [];
  } finally {
    loadingStar.value = false;
  }
}

async function removeStarAsset(a: StarAsset) {
  if (!window.confirm(`确定从星库删除「${a.title}」？`)) return;
  deletingStarId.value = a.id;
  starMsg.value = '正在删除…';
  try {
    await deleteStarAsset(a.id);
    starAssets.value = starAssets.value.filter((x) => x.id !== a.id);
    if (activeStar.value?.id === a.id) activeStar.value = null;
    starMsg.value = `已删除：${a.title}`;
  } catch (e) {
    starMsg.value = e instanceof Error ? e.message : '删除失败';
  } finally {
    deletingStarId.value = '';
  }
}

async function loadWorkshopHistory() {
  try {
    workshopResources.value = await fetchLearnResources(selectedPlanet.value || '');
  } catch {
    workshopResources.value = [];
  }
}

async function handleUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file || !classId.value) {
    msg.value = classId.value ? '请选择文件' : '请先选择班级';
    return;
  }
  uploading.value = true;
  msg.value = '正在上传…';
  try {
    const res = await uploadTeacherResource(
      file,
      title.value.trim() || file.name,
      uploadGalaxy.value,
      classId.value,
      uploadKind.value,
    );
    msg.value = `资料「${res.title}」已上传`;
    title.value = '';
    await loadMaterials();
  } catch {
    msg.value = '上传失败';
  } finally {
    uploading.value = false;
    input.value = '';
  }
}

async function handlePromote(r: LessonResourceItem) {
  if (!classId.value) {
    msg.value = '请先选择班级';
    return;
  }
  if (r.promoted_asset_id) {
    msg.value = '该资料已发布到星库';
    return;
  }
  promoteBusy.value = r.id;
  try {
    await promoteTeacherResource(r.id, {
      class_id: classId.value,
      galaxy_slug: r.galaxy_slug,
      asset_type: r.resource_kind === 'book' ? 'book' : r.resource_kind === 'quiz' ? 'problem_doc' : 'note_pack',
    });
    msg.value = `「${r.title}」已发布到班级星库`;
    await loadMaterials();
    if (tab.value === 'starlib') await loadStarlib();
  } catch (e) {
    msg.value = e instanceof Error ? e.message : '发布失败';
  } finally {
    promoteBusy.value = '';
  }
}

async function handleDelete(r: LessonResourceItem) {
  if (!confirm(`确定删除「${r.title}」？`)) return;
  try {
    await deleteTeacherResource(r.id);
    msg.value = '已删除';
    await loadMaterials();
  } catch {
    msg.value = '删除失败';
  }
}

function planToMarkdown(p: LessonPlan) {
  return [
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
  ].join('\n');
}

async function handleGeneratePlan() {
  if (!selectedPlanet.value) return;
  generatingPlan.value = true;
  aiMsg.value = '';
  plan.value = null;
  try {
    plan.value = await generateLessonPlan(selectedPlanet.value);
  } catch (e) {
    aiMsg.value = e instanceof Error ? e.message : '生成教案失败';
  } finally {
    generatingPlan.value = false;
  }
}

async function savePlanToMaterials() {
  if (!plan.value || !classId.value) {
    aiMsg.value = '请先选择班级并生成教案';
    return;
  }
  try {
    await createTeacherResourceFromText({
      title: `${plan.value.planet_name} 教案`,
      content: planToMarkdown(plan.value),
      galaxy_slug: selectedGalaxy.value,
      class_id: classId.value,
      resource_kind: 'plan',
    });
    aiMsg.value = '教案已存入资料库';
    await loadMaterials();
  } catch (e) {
    aiMsg.value = e instanceof Error ? e.message : '存入失败';
  }
}

function downloadPlan() {
  if (!plan.value) return;
  const blob = new Blob([planToMarkdown(plan.value)], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${plan.value.planet_name || '教案'}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

async function handleWorkshopGenerate() {
  if (!selectedPlanet.value || !selectedKinds.value.length) {
    aiMsg.value = '请选择行星与生成类型';
    return;
  }
  if (!llmInfo.value.available) {
    aiMsg.value = '未检测到可用大模型（请配置 DeepSeek 或豆包 ARK_CHAT_MODEL）';
    return;
  }
  generating.value = true;
  streamLog.value = [];
  aiMsg.value = `正在通过 ${llmInfo.value.label} 生成…`;
  let gotComplete = false;
  let createdCount = 0;
  try {
    const quizTypes =
      selectedKinds.value.includes('quiz') && selectedQuizTypes.value.length
        ? [...selectedQuizTypes.value]
        : [];
    const { run_id } = await startResourceGeneration(
      selectedPlanet.value,
      selectedKinds.value,
      extraReq.value.trim(),
      quizTypes,
      selectedKinds.value.includes('deck') ? deckTemplate.value : 'orbit',
    );
    await consumeResourceStream(run_id, (ev: ResourceStreamEvent) => {
      const line = String(ev.content || '').slice(0, 160);
      if (ev.type === 'error') {
        streamLog.value.push(`[错误] ${line}`);
        aiMsg.value = line || '生成出错';
      } else if (line && ['start', 'agent_start', 'agent_done', 'resource_done', 'complete', 'quality_retry'].includes(ev.type)) {
        streamLog.value.push(`[${ev.type}] ${line}`);
      }
      if (ev.type === 'complete') gotComplete = true;
      if (ev.type === 'resource_done' && ev.payload?.resource_id) {
        createdCount += 1;
        const r: GeneratedResource = {
          id: String(ev.payload.resource_id),
          planet_slug: selectedPlanet.value,
          planet_name: planets.value.find((p) => p.slug === selectedPlanet.value)?.name || '',
          kind: (ev.payload.kind as ResourceKind) || 'doc',
          title: String(ev.payload.title || ''),
          content: String(ev.payload.content || ''),
          meta_json: (ev.payload.meta as Record<string, unknown>) || {},
          created_at: new Date().toISOString(),
        };
        workshopResources.value = [r, ...workshopResources.value.filter((x) => x.id !== r.id)];
        if (!activeResource.value) activeResource.value = r;
      }
    });
    await loadWorkshopHistory();
    if (createdCount > 0 || workshopResources.value.length > 0) {
      aiMsg.value = `生成完成（${llmInfo.value.label}）· ${createdCount || workshopResources.value.length} 项`;
    } else if (gotComplete) {
      aiMsg.value = '生成结束，但未收到资源，请查看日志或重试';
    } else {
      aiMsg.value = '生成中断：未收到完成事件（后端可能报错，请重启后端后重试）';
    }
  } catch (e) {
    aiMsg.value = e instanceof Error ? e.message : '生成失败';
  } finally {
    generating.value = false;
  }
}

async function saveResourceToMaterials(r: GeneratedResource) {
  if (!classId.value) {
    aiMsg.value = '请先选择班级';
    return;
  }
  const kindMap: Record<string, string> = { deck: 'deck', quiz: 'quiz', doc: 'plan', mindmap: 'other' };
  try {
    await createTeacherResourceFromText({
      title: r.title || `${r.kind} · ${r.planet_name}`,
      content: r.content || '',
      galaxy_slug: selectedGalaxy.value,
      class_id: classId.value,
      resource_kind: kindMap[r.kind] || 'other',
    });
    aiMsg.value = `「${r.title}」已存入资料库`;
    await loadMaterials();
  } catch (e) {
    aiMsg.value = e instanceof Error ? e.message : '存入失败';
  }
}

async function publishResourceToStarlib(r: GeneratedResource) {
  if (!classId.value) {
    aiMsg.value = '请先选择班级';
    return;
  }
  try {
    await promoteGeneratedResource(r.id, {
      class_id: classId.value,
      galaxy_slug: selectedGalaxy.value,
      planet_slug: r.planet_slug,
    });
    aiMsg.value = `「${r.title}」已发布到班级星库`;
    await loadMaterials();
    await loadStarlib();
  } catch (e) {
    aiMsg.value = e instanceof Error ? e.message : '发布失败';
  }
}

function downloadActiveResource() {
  if (!activeResource.value) return;
  const err = triggerResourceDownload(activeResource.value);
  if (err) aiMsg.value = err;
}

const activeDownload = computed(() =>
  activeResource.value ? buildResourceDownload(activeResource.value) : null,
);

function resolveMediaUrl(url?: string): string {
  if (!url) return '';
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('blob:')) return url;
  return url.startsWith('/') ? url : `/${url}`;
}

function deckPack(r: GeneratedResource): DeckPack {
  const meta = (r.meta_json || {}) as { pptx_url?: string; export_error?: string };
  try {
    const parsed = JSON.parse(r.content) as DeckPack;
    return {
      title: parsed.title || r.title,
      slides: Array.isArray(parsed.slides) ? parsed.slides : [],
      pptx_url: meta.pptx_url || parsed.pptx_url,
      export_error: meta.export_error || parsed.export_error,
    };
  } catch {
    return { title: r.title, slides: [], pptx_url: meta.pptx_url, export_error: meta.export_error };
  }
}

function deckThemeOf(r: GeneratedResource | null): DeckTemplateMeta | undefined {
  const id = String((r?.meta_json || {}).deck_template || deckTemplate.value || 'orbit');
  return deckTemplates.value.find((t) => t.id === id) || deckTemplates.value[0];
}

function deckPptxUrl(r: GeneratedResource): string {
  return resolveMediaUrl(deckPack(r).pptx_url);
}

function deckExportError(r: GeneratedResource): string {
  const pack = deckPack(r);
  if (pack.pptx_url) return '';
  return String(pack.export_error || 'PPT 导出失败（请确认已安装 python-pptx）');
}

const deckSlides = computed(() =>
  activeResource.value?.kind === 'deck' ? deckPack(activeResource.value).slides : [],
);
const deckCurrent = computed(() => deckSlides.value[deckIndex.value] || null);
const deckCurrentBullets = computed(() => {
  const s = deckCurrent.value;
  if (!s) return [] as string[];
  return s.bullet_points || s.bullets || [];
});

watch(activeResource, () => {
  deckIndex.value = 0;
});

function deckPrev() {
  if (deckIndex.value > 0) deckIndex.value -= 1;
}

function deckNext() {
  if (deckIndex.value < deckSlides.value.length - 1) deckIndex.value += 1;
}

function quizQuestions(r: GeneratedResource): Array<Record<string, unknown>> {
  try {
    const parsed = JSON.parse(r.content) as { questions?: Array<Record<string, unknown>> };
    return Array.isArray(parsed.questions) ? parsed.questions : [];
  } catch {
    return [];
  }
}

function quizTypeLabel(type: unknown): string {
  const key = String(type || '').toLowerCase();
  return QUIZ_TYPE_LABELS[key] || key || '题目';
}

function quizOptionsText(options: unknown): string {
  if (Array.isArray(options)) return options.map(String).join(' · ');
  return options ? String(options) : '';
}

function previewContent(r: GeneratedResource): string {
  if (r.kind === 'quiz' || r.kind === 'deck') return '';
  if (r.kind === 'mindmap') {
    try {
      const parsed = JSON.parse(r.content);
      if (parsed.tree) {
        return '```json\n' + JSON.stringify(parsed.tree, null, 2).slice(0, 4000) + '\n```';
      }
      return '```json\n' + JSON.stringify(parsed, null, 2).slice(0, 4000) + '\n```';
    } catch {
      return r.content.slice(0, 4000);
    }
  }
  return r.content;
}

async function handleStarlibPdfUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) {
    starMsg.value = '请选择 PDF 文件';
    return;
  }
  starBusy.value = true;
  starMsg.value = '正在上传并解析进星库…';
  try {
    const res = await uploadStarlibPdf({
      file,
      title: starTitle.value.trim() || file.name.replace(/\.pdf$/i, ''),
      galaxy_slug: starGalaxy.value || undefined,
      asset_type: starAssetType.value || 'book',
      description: '教师知识库星库入库',
      class_id: classId.value || undefined,
    });
    starMsg.value = `已入库：${res.title}（${res.page_count || 0} 页）`;
    starTitle.value = '';
    await loadStarlib();
  } catch (e) {
    starMsg.value = e instanceof Error ? e.message : '上传失败';
  } finally {
    starBusy.value = false;
    input.value = '';
  }
}

async function handleBilibiliMount() {
  const bvid = biliBvid.value.trim().replace(/^https?:\/\/.*?(BV[\w]+).*$/i, '$1');
  const match = bvid.match(/BV[\w]+/i);
  const clean = match ? match[0] : bvid;
  if (!clean) {
    biliMsg.value = '请填写 BV 号';
    return;
  }
  biliBusy.value = true;
  try {
    const res = await createBilibiliAsset({
      title: biliTitle.value.trim() || `B站 · ${clean}`,
      bvid: clean,
      galaxy_slug: biliGalaxy.value || undefined,
      description: '教师知识库挂载',
      class_id: classId.value || undefined,
    });
    biliMsg.value = `已挂载：${res.title || clean}`;
    biliBvid.value = '';
    biliTitle.value = '';
    await loadStarlib();
  } catch (e) {
    biliMsg.value = e instanceof Error ? e.message : '挂载失败';
  } finally {
    biliBusy.value = false;
  }
}

function isPdfAsset(a: StarAsset) {
  return ['book', 'pdf', 'problem_doc', 'note_pack'].includes(a.asset_type) && !!a.file_url?.match(/\.pdf($|\?)/i);
}

watch(selectedGalaxy, () => {
  selectedPlanet.value = '';
  void loadPlanets();
});
watch(selectedPlanet, () => {
  if (tab.value === 'ai') void loadWorkshopHistory();
});
watch(tab, (t) => {
  if (t === 'materials') void loadMaterials();
  if (t === 'starlib') void loadStarlib();
  if (t === 'ai') {
    void loadWorkshopHistory();
    void loadLlmStatus();
  }
});
watch([classId, filterGalaxy], () => {
  void loadMaterials();
  if (tab.value === 'starlib') void loadStarlib();
});

onMounted(async () => {
  await loadGalaxies();
  await loadPlanets();
  await loadMaterials();
  await loadLlmStatus();
  try {
    const data = await fetchDeckTemplates();
    deckTemplates.value = data.templates || [];
  } catch {
    deckTemplates.value = [];
  }
});
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="教师知识库" subtitle="资料管理 · AI 生成 · 发布到班级星库">
      <template #actions>
        <div class="t-tabs">
          <button
            v-for="t in [
              { key: 'materials', label: '资料库' },
              { key: 'ai', label: 'AI 工坊' },
              { key: 'starlib', label: '班级星库' },
            ]"
            :key="t.key"
            type="button"
            class="t-tab"
            :class="{ 'is-active': tab === t.key }"
            @click="tab = t.key as TabKey"
          >
            {{ t.label }}
          </button>
        </div>
      </template>
    </TeacherPageHeader>

    <!-- 资料库 -->
    <template v-if="tab === 'materials'">
      <section class="t-card glass-edge p-5">
        <div class="flex items-baseline justify-between gap-2">
          <h3 class="text-[15px] font-semibold text-t-1">上传资料</h3>
          <span class="t-kicker">Upload</span>
        </div>
        <div class="mt-3 grid gap-3 md:grid-cols-3">
          <input v-model="title" placeholder="资料标题（可选）" class="t-input" />
          <select v-model="uploadGalaxy" class="t-input cursor-pointer">
            <option value="">目标星系（可选）</option>
            <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
          </select>
          <select v-model="uploadKind" class="t-input cursor-pointer">
            <option v-for="(label, key) in KIND_LABELS" :key="key" :value="key">{{ label }}</option>
          </select>
        </div>
        <label
          class="mt-3 flex cursor-pointer flex-col items-center gap-1 rounded-xl border border-dashed border-t-accent/35 bg-t-accent/5 px-4 py-8 text-sm text-t-accent transition hover:bg-t-accent/10"
          :class="uploading ? 'pointer-events-none opacity-60' : ''"
        >
          <svg viewBox="0 0 24 24" class="h-6 w-6 opacity-80" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 16V4m0 0 4 4m-4-4-4 4" />
            <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
          </svg>
          <span>{{ uploading ? '上传中…' : '点击上传书本 / 课件 / 题库 / 教案 / 视频（PDF·PPT·DOC·MD·ZIP）' }}</span>
          <input type="file" accept=".pdf,.md,.doc,.docx,.ppt,.pptx,.zip,.mp4,.webm" class="hidden" @change="handleUpload" />
        </label>
        <p v-if="msg" class="mt-2 text-xs text-t-accent">{{ msg }}</p>
      </section>

      <section class="t-card glass-edge p-5">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <h3 class="text-[15px] font-semibold text-t-1">资料列表</h3>
          <div class="flex flex-wrap items-center gap-2">
            <div class="t-tabs">
              <button type="button" class="t-tab" :class="{ 'is-active': materialsView === 'galaxy' }" @click="materialsView = 'galaxy'">
                按星系分类
              </button>
              <button type="button" class="t-tab" :class="{ 'is-active': materialsView === 'kind' }" @click="materialsView = 'kind'">
                按类型分类
              </button>
            </div>
            <select v-model="filterGalaxy" class="t-input w-auto cursor-pointer py-1.5">
              <option value="">全部星系</option>
              <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
            </select>
            <select v-model="filterKind" class="t-input w-auto cursor-pointer py-1.5">
              <option value="">全部分类</option>
              <option v-for="(label, key) in KIND_LABELS" :key="key" :value="key">{{ label }}</option>
            </select>
          </div>
        </div>
        <TeacherLoading v-if="loadingMaterials" :rows="4" />
        <div v-else class="mt-3 space-y-3">
          <div v-for="group in materialGroups" :key="group.key" class="overflow-hidden rounded-xl border border-t-line/10">
            <button
              type="button"
              class="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm font-medium text-t-1 transition hover:bg-t-line/5"
              @click="toggleGroup(group.key)"
            >
              <span>
                {{ group.label }}
                <span class="ml-2 text-[11px] font-normal text-t-3">{{ group.items.length }} 项</span>
              </span>
              <span class="text-xs text-t-3">{{ collapsedGroups[group.key] ? '展开' : '收起' }}</span>
            </button>
            <div v-if="!collapsedGroups[group.key]" class="space-y-2 border-t border-t-line/8 px-3 py-3">
              <div
                v-for="r in group.items"
                :key="r.id"
                class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-t-line/10 bg-t-s1/30 px-4 py-3 transition hover:border-t-accent/25"
              >
                <div>
                  <p class="flex flex-wrap items-center gap-1.5 text-sm font-medium text-t-1">
                    {{ r.title }}
                    <span class="t-badge t-badge--neutral">{{ KIND_LABELS[r.resource_kind || 'other'] || '其他' }}</span>
                    <span v-if="r.galaxy_slug && materialsView === 'kind'" class="t-badge t-badge--neutral">
                      {{ galaxyNameMap[r.galaxy_slug] || r.galaxy_slug }}
                    </span>
                    <span v-if="r.promoted_asset_id" class="t-badge t-badge--ok">已发布星库</span>
                  </p>
                  <p class="mt-1 text-[11px] text-t-3">
                    {{ r.created_at?.slice(0, 16)?.replace('T', ' ') || '—' }}
                  </p>
                </div>
                <div class="flex flex-wrap gap-2">
                  <a v-if="r.file_url" :href="r.file_url" target="_blank" class="t-btn t-btn--ghost t-btn--sm">打开</a>
                  <button
                    type="button"
                    class="t-btn t-btn--soft t-btn--sm"
                    :disabled="!!r.promoted_asset_id || promoteBusy === r.id"
                    @click="handlePromote(r)"
                  >
                    {{ r.promoted_asset_id ? '已发布' : promoteBusy === r.id ? '发布中…' : '发布到星库' }}
                  </button>
                  <button type="button" class="t-btn t-btn--danger t-btn--sm" @click="handleDelete(r)">删除</button>
                </div>
              </div>
            </div>
          </div>
          <TeacherEmptyState v-if="!materialGroups.length" title="暂无资料" description="上传后可按星系或类型浏览，并发布到班级星库" />
        </div>
      </section>
    </template>

    <!-- AI 工坊 -->
    <template v-else-if="tab === 'ai'">
      <section class="t-card glass-edge p-5">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="t-tabs">
            <button type="button" class="t-tab" :class="{ 'is-active': aiMode === 'plan' }" @click="aiMode = 'plan'">
              AI 教案
            </button>
            <button type="button" class="t-tab" :class="{ 'is-active': aiMode === 'workshop' }" @click="aiMode = 'workshop'">
              课件 / 题目 / 讲义
            </button>
          </div>
          <span class="t-kicker hidden sm:inline">AI Workshop</span>
        </div>
        <p class="mt-3 text-[11px]" :class="llmInfo.available ? 'text-t-ok' : 'text-t-warn'">
          文本模型：{{ llmInfo.label }}
          <template v-if="llmInfo.model"> · {{ llmInfo.model }}</template>
          <template v-if="!llmInfo.available">（请配置 DEEPSEEK_API_KEY 或 ARK_CHAT_MODEL）</template>
        </p>
        <div class="mt-4 grid gap-3 md:grid-cols-2">
          <select v-model="selectedGalaxy" class="t-input cursor-pointer">
            <option value="">选择星系</option>
            <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
          </select>
          <select v-model="selectedPlanet" class="t-input cursor-pointer">
            <option value="">选择行星</option>
            <option v-for="p in planets" :key="p.slug" :value="p.slug">{{ p.name }}</option>
          </select>
        </div>
        <p v-if="aiMsg" class="mt-2 text-xs text-t-accent">{{ aiMsg }}</p>
      </section>

      <template v-if="aiMode === 'plan'">
        <section class="t-card glass-edge p-5">
          <button
            type="button"
            class="t-btn t-btn--primary t-btn--md"
            :disabled="!selectedPlanet || generatingPlan"
            @click="handleGeneratePlan"
          >
            {{ generatingPlan ? '生成中…' : '生成结构化教案' }}
          </button>
          <div v-if="plan" class="mt-4 space-y-3">
            <div class="flex flex-wrap gap-2">
              <button type="button" class="t-btn t-btn--ghost t-btn--sm" @click="downloadPlan">下载 Markdown</button>
              <button
                type="button"
                class="t-btn t-btn--sm border-t-ok/40 bg-t-ok/12 text-t-ok hover:bg-t-ok/20"
                @click="savePlanToMaterials"
              >
                存入资料库
              </button>
            </div>
            <div class="t-card--flat rounded-xl border border-t-line/10 p-4 text-sm text-t-2">
              <p class="font-semibold text-t-1">{{ plan.planet_name }} 教案</p>
              <p class="mt-2 text-xs text-t-3">学习目标</p>
              <ul class="mt-1 list-disc pl-5 text-xs">
                <li v-for="(g, i) in plan.learning_goals" :key="i">{{ g }}</li>
              </ul>
              <p class="mt-3 text-xs text-t-3">教学思路</p>
              <p class="mt-1 text-xs leading-relaxed">{{ plan.teaching_approach }}</p>
            </div>
          </div>
          <TeacherEmptyState v-else-if="!generatingPlan" class="mt-4" title="选择行星后生成教案" />
        </section>
      </template>

      <template v-else>
        <section class="t-card glass-edge p-5">
          <div class="flex flex-wrap gap-2">
            <label
              v-for="k in AI_KINDS"
              :key="k.id"
              class="flex cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition"
              :class="selectedKinds.includes(k.id) ? 'border-t-accent/40 bg-t-accent/10 text-t-1' : 'border-t-line/12 text-t-2 hover:border-t-line/25'"
            >
              <input v-model="selectedKinds" type="checkbox" :value="k.id" class="t-check" />
              {{ k.label }}
            </label>
          </div>
          <div v-if="selectedKinds.includes('quiz')" class="mt-3 rounded-xl border border-t-accent/20 bg-t-accent/5 p-3">
            <p class="text-[11px] text-t-accent">练习题题型（至少选一种，默认全选）</p>
            <div class="mt-2 flex flex-wrap gap-2">
              <label
                v-for="t in QUIZ_TYPE_OPTIONS"
                :key="t.id"
                class="flex cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs transition"
                :class="selectedQuizTypes.includes(t.id) ? 'border-t-accent/40 bg-t-accent/10 text-t-1' : 'border-t-line/12 text-t-2 hover:border-t-line/25'"
              >
                <input v-model="selectedQuizTypes" type="checkbox" :value="t.id" class="t-check" />
                {{ t.label }}
              </label>
            </div>
          </div>
          <div v-if="selectedKinds.includes('deck') && deckTemplates.length" class="mt-3 space-y-2">
            <p class="text-[11px] text-t-accent">课件 PPT 模板</p>
            <div class="grid gap-2 sm:grid-cols-3 lg:grid-cols-5">
              <button
                v-for="tpl in deckTemplates"
                :key="tpl.id"
                type="button"
                class="rounded-lg border p-2 text-left text-xs transition"
                :class="
                  deckTemplate === tpl.id
                    ? 'border-t-accent/40 bg-t-accent/10 text-t-1'
                    : 'border-t-line/12 text-t-2 hover:border-t-line/25'
                "
                @click="deckTemplate = tpl.id"
              >
                <span class="mb-1.5 flex h-7 overflow-hidden rounded">
                  <i class="flex-1" :style="{ background: tpl.colors.bg }" />
                  <i class="w-2" :style="{ background: tpl.colors.accent }" />
                  <i class="flex-1" :style="{ background: tpl.colors.bar }" />
                </span>
                <p>{{ tpl.name }}</p>
                <p class="mt-0.5 text-[10px] text-t-3">{{ tpl.suitable }}</p>
              </button>
            </div>
          </div>
          <textarea
            v-model="extraReq"
            rows="2"
            placeholder="额外要求（可选），如：侧重考研真题风格、配套 10 道选择题…"
            class="t-input mt-3"
          />
          <button
            type="button"
            class="t-btn t-btn--primary t-btn--md mt-3"
            :disabled="generating || !selectedPlanet || (selectedKinds.includes('quiz') && !selectedQuizTypes.length)"
            @click="handleWorkshopGenerate"
          >
            {{ generating ? '多智能体生成中…' : '开始 AI 生成' }}
          </button>
          <ul v-if="streamLog.length" class="mt-3 max-h-24 space-y-1 overflow-y-auto font-mono-tech text-[11px] text-t-3">
            <li v-for="(line, i) in streamLog.slice(-8)" :key="i">{{ line }}</li>
          </ul>
        </section>

        <section class="t-card glass-edge grid gap-4 p-5 lg:grid-cols-[280px_1fr]">
          <div>
            <h3 class="text-sm font-semibold text-t-1">生成历史</h3>
            <div class="mt-2 max-h-[420px] space-y-1 overflow-y-auto">
              <button
                v-for="r in workshopResources"
                :key="r.id"
                type="button"
                class="block w-full rounded-lg border px-3 py-2 text-left text-xs transition"
                :class="
                  activeResource?.id === r.id
                    ? 'border-t-accent/40 bg-t-accent/10 text-t-1'
                    : 'border-t-line/10 text-t-2 hover:bg-t-line/5'
                "
                @click="activeResource = r"
              >
                <span class="font-mono-tech text-[10px] uppercase text-t-3">{{ r.kind }}</span>
                <p class="mt-0.5 truncate">{{ r.title }}</p>
              </button>
              <TeacherEmptyState v-if="!workshopResources.length" title="暂无生成物" />
            </div>
          </div>
          <div v-if="activeResource">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <h3 class="text-sm font-semibold text-t-1">{{ activeResource.title }}</h3>
              <div class="flex flex-wrap gap-2">
                <button
                  v-if="activeDownload && !activeDownload.error"
                  type="button"
                  class="t-btn t-btn--primary t-btn--sm"
                  @click="downloadActiveResource"
                >
                  {{ activeDownload.label }}
                </button>
                <button
                  type="button"
                  class="t-btn t-btn--sm border-t-ok/40 bg-t-ok/12 text-t-ok hover:bg-t-ok/20"
                  @click="saveResourceToMaterials(activeResource)"
                >
                  存入资料库
                </button>
                <button type="button" class="t-btn t-btn--soft t-btn--sm" @click="publishResourceToStarlib(activeResource)">
                  发布到星库
                </button>
              </div>
            </div>

            <!-- 练习题卡片预览 -->
            <div
              v-if="activeResource.kind === 'quiz'"
              class="t-card--flat mt-3 max-h-[480px] space-y-3 overflow-y-auto rounded-xl border border-t-line/10 p-4"
            >
              <div
                v-for="(q, i) in quizQuestions(activeResource)"
                :key="i"
                class="rounded-lg border border-t-line/10 bg-t-s2/40 p-3 text-xs text-t-2"
              >
                <p class="font-medium text-t-1">
                  <span class="t-badge t-badge--info mr-1.5">{{ quizTypeLabel(q.type) }}</span>
                  {{ q.question }}
                </p>
                <p v-if="quizOptionsText(q.options)" class="mt-2 text-t-3">{{ quizOptionsText(q.options) }}</p>
                <p class="mt-2 text-t-ok">答案：{{ q.answer }}</p>
                <p v-if="q.explanation" class="mt-1 text-t-3">{{ q.explanation }}</p>
              </div>
              <p v-if="!quizQuestions(activeResource).length" class="text-xs text-t-3">暂无题目内容</p>
            </div>

            <!-- 课件幻灯片翻页 + PPT 下载 -->
            <div
              v-else-if="activeResource.kind === 'deck'"
              class="t-card--flat mt-3 space-y-3 rounded-xl border border-t-line/10 p-4"
            >
              <div class="flex flex-wrap items-center justify-between gap-2">
                <p class="font-mono-tech text-[11px] text-t-accent2">
                  教学课件 · {{ deckIndex + 1 }}/{{ Math.max(deckSlides.length, 1) }}
                </p>
                <button
                  v-if="deckPptxUrl(activeResource)"
                  type="button"
                  class="t-btn t-btn--primary t-btn--sm"
                  @click="downloadActiveResource"
                >
                  下载 PPT (.pptx)
                </button>
              </div>
              <p
                v-if="!deckPptxUrl(activeResource)"
                class="rounded-lg border border-t-warn/30 bg-t-warn/10 px-3 py-2 text-[11px] text-t-warn"
              >
                PPT 导出失败：{{ deckExportError(activeResource) }}
              </p>
              <div
                v-if="deckCurrent"
                class="min-h-[180px] rounded-xl border p-4"
                :style="
                  deckThemeOf(activeResource)
                    ? {
                        background: deckThemeOf(activeResource)!.colors.bg,
                        color: deckThemeOf(activeResource)!.colors.body,
                        borderColor: deckThemeOf(activeResource)!.colors.accent,
                      }
                    : undefined
                "
              >
                <p class="text-base font-semibold" :style="{ color: deckThemeOf(activeResource)?.colors.title }">
                  {{ deckCurrent.title }}
                </p>
                <ul v-if="deckCurrentBullets.length" class="mt-3 space-y-1.5 text-sm text-t-2">
                  <li v-for="(b, i) in deckCurrentBullets" :key="i" class="flex gap-2">
                    <span class="text-t-accent2">•</span>
                    <span>{{ b }}</span>
                  </li>
                </ul>
                <p v-if="deckCurrent.narration" class="mt-4 text-xs leading-5 text-t-3">
                  {{ deckCurrent.narration }}
                </p>
              </div>
              <p v-else class="text-xs text-t-3">暂无幻灯片内容</p>
              <div class="flex flex-wrap gap-2">
                <button type="button" class="t-btn t-btn--ghost t-btn--sm" :disabled="deckIndex <= 0" @click="deckPrev">
                  上一页
                </button>
                <button
                  type="button"
                  class="t-btn t-btn--ghost t-btn--sm"
                  :disabled="deckIndex >= deckSlides.length - 1"
                  @click="deckNext"
                >
                  下一页
                </button>
              </div>
            </div>

            <div v-else class="t-card--flat mt-3 max-h-[480px] overflow-y-auto rounded-xl border border-t-line/10 p-4">
              <MarkdownView :content="previewContent(activeResource)" />
            </div>
          </div>
          <TeacherEmptyState v-else title="选择左侧生成物预览" />
        </section>
      </template>
    </template>

    <!-- 班级星库 -->
    <template v-else>
      <div class="grid gap-4 xl:grid-cols-2">
        <section class="t-card glass-edge p-5">
          <div class="flex items-baseline justify-between gap-2">
            <h3 class="text-[15px] font-semibold text-t-1">上传 PDF 到星库</h3>
            <span class="t-kicker">PDF</span>
          </div>
          <div class="mt-3 grid gap-3 md:grid-cols-3">
            <input v-model="starTitle" placeholder="标题（可选）" class="t-input" />
            <select v-model="starGalaxy" class="t-input cursor-pointer">
              <option value="">关联星系</option>
              <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
            </select>
            <select v-model="starAssetType" class="t-input cursor-pointer">
              <option value="book">教材 book</option>
              <option value="pdf">讲义 pdf</option>
              <option value="problem_doc">题集 problem_doc</option>
            </select>
          </div>
          <label
            class="mt-3 flex cursor-pointer flex-col items-center gap-1 rounded-xl border border-dashed border-t-accent2/35 bg-t-accent2/5 px-4 py-6 text-sm text-t-accent2 transition hover:bg-t-accent2/10"
            :class="starBusy ? 'pointer-events-none opacity-60' : ''"
          >
            <span>{{ starBusy ? '解析入库中…' : '选择 PDF 上传到班级星库' }}</span>
            <input type="file" accept=".pdf,application/pdf" class="hidden" @change="handleStarlibPdfUpload" />
          </label>
          <p v-if="starMsg" class="mt-2 text-xs text-t-accent2">{{ starMsg }}</p>
        </section>

        <section class="t-card glass-edge p-5">
          <div class="flex items-baseline justify-between gap-2">
            <h3 class="text-[15px] font-semibold text-t-1">B 站视频挂载</h3>
            <span class="t-kicker">Video</span>
          </div>
          <div class="mt-3 grid gap-3 md:grid-cols-3">
            <input v-model="biliBvid" placeholder="BV 号或链接" class="t-input" />
            <input v-model="biliTitle" placeholder="标题（可选）" class="t-input" />
            <select v-model="biliGalaxy" class="t-input cursor-pointer">
              <option value="">关联星系</option>
              <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
            </select>
          </div>
          <button type="button" class="t-btn t-btn--soft t-btn--md mt-3" :disabled="biliBusy" @click="handleBilibiliMount">
            {{ biliBusy ? '挂载中…' : '挂载进星库' }}
          </button>
          <p v-if="biliMsg" class="mt-2 text-xs text-t-accent2">{{ biliMsg }}</p>
        </section>
      </div>

      <section class="t-card glass-edge grid gap-4 p-5 lg:grid-cols-[320px_1fr]">
        <div>
          <div class="flex items-center justify-between gap-2">
            <h3 class="text-[15px] font-semibold text-t-1">星库资产</h3>
            <button type="button" class="text-[11px] text-t-accent transition hover:opacity-80" @click="loadStarlib">刷新</button>
          </div>
          <TeacherLoading v-if="loadingStar" :rows="4" />
          <div v-else class="mt-2 max-h-[520px] space-y-1 overflow-y-auto">
            <button
              v-for="a in starAssets"
              :key="a.id"
              type="button"
              class="block w-full rounded-lg border px-3 py-2 text-left text-xs transition"
              :class="
                activeStar?.id === a.id
                  ? 'border-t-accent/40 bg-t-accent/10 text-t-1'
                  : 'border-t-line/10 text-t-2 hover:bg-t-line/5'
              "
              @click="activeStar = a"
            >
              <span class="font-mono-tech text-[10px] text-t-3">{{ a.asset_type }}</span>
              <p class="mt-0.5 truncate text-sm">{{ a.title }}</p>
              <p v-if="a.owner_id" class="mt-0.5 truncate text-[10px] text-t-3">owner · {{ a.owner_id.slice(0, 8) }}</p>
            </button>
            <TeacherEmptyState v-if="!starAssets.length" title="星库为空" description="上传 PDF 或从资料库发布" />
          </div>
        </div>
        <div v-if="activeStar" class="min-h-[360px]">
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <h3 class="text-sm font-semibold text-t-1">{{ activeStar.title }}</h3>
              <p class="mt-1 text-[11px] text-t-3">
                {{ activeStar.asset_type }}
                <template v-if="activeStar.galaxy_slug"> · {{ galaxyNameMap[activeStar.galaxy_slug] || activeStar.galaxy_slug }}</template>
                <template v-if="activeStar.class_id"> · 班级共享</template>
                <template v-else> · 校本/全局</template>
              </p>
            </div>
            <button
              type="button"
              class="t-btn t-btn--danger t-btn--sm shrink-0"
              :disabled="deletingStarId === activeStar.id"
              @click="removeStarAsset(activeStar)"
            >
              {{ deletingStarId === activeStar.id ? '删除中…' : '删除' }}
            </button>
          </div>
          <div v-if="isPdfAsset(activeStar)" class="mt-3 h-[520px] overflow-hidden rounded-xl border border-t-line/10">
            <PdfViewer :src="activeStar.file_url" />
          </div>
          <div v-else-if="activeStar.asset_type === 'video_bilibili' && activeStar.bilibili_bvid" class="mt-3 aspect-video overflow-hidden rounded-xl border border-t-line/10">
            <iframe
              class="h-full w-full"
              :src="`https://player.bilibili.com/player.html?bvid=${activeStar.bilibili_bvid}&high_quality=1`"
              allowfullscreen
            />
          </div>
          <div v-else-if="activeStar.file_url" class="mt-3">
            <a :href="activeStar.file_url" target="_blank" class="text-sm text-t-accent hover:underline">打开文件</a>
            <p v-if="activeStar.description" class="mt-2 whitespace-pre-wrap text-xs text-t-2">{{ activeStar.description }}</p>
          </div>
          <TeacherEmptyState v-else class="mt-4" title="无法预览该资产" />
        </div>
        <TeacherEmptyState v-else title="选择左侧资产预览" />
      </section>
    </template>
  </div>
</template>

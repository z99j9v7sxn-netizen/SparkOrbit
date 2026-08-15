<script setup lang="ts">
import * as echarts from 'echarts';
import { gsap } from 'gsap';
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { fetchGalaxies, fetchGalaxyDetail } from '../../api/orbit';
import {
  consumeResourceStream,
  fetchDeckTemplates,
  fetchLearnResources,
  fetchLearningPath,
  mountPathStep,
  startResourceGeneration,
  type DeckTemplateMeta,
  type GeneratedResource,
  type ResourceKind,
  type ResourceStreamEvent,
} from '../../api/learnExtras';
import { ingestWorkshopToVault } from '../../api/vault';
import { synthesizeSpeech } from '../../api/tts';
import { selectionAsk } from '../../api/challengeSprint';
import { companionChat } from '../../api/orbit';
import MarkdownView from '../common/MarkdownView.vue';
import MindmapCanvas from './MindmapCanvas.vue';
import { buildResourceDownload, triggerResourceDownload } from '../../lib/resourceDownload';
import {
  clearPendingResourceStream,
  takePendingResourceStream,
  writePendingResourceStream,
} from '../../lib/pendingResourceStream';
import { useOrbitStore } from '../../stores/orbit';
import { storeToRefs } from 'pinia';
import { LzBadge, LzButton, LzSection } from './ui';
import ResourceGenerationStatus from './resource/ResourceGenerationStatus.vue';
import ResourceLibraryList from './resource/ResourceLibraryList.vue';
import { qualityOf } from './resource/resourceMeta';
const KIND_OPTIONS: { id: ResourceKind; label: string; agent: string }[] = [
  { id: 'doc', label: '讲解文档', agent: 'DocAgent' },
  { id: 'mindmap', label: '思维导图', agent: 'MindAgent' },
  { id: 'quiz', label: '练习题', agent: 'QuizAgent' },
  { id: 'reading', label: '拓展阅读', agent: 'ReadAgent' },
  { id: 'media', label: '教学视频', agent: 'MediaAgent' },
  { id: 'deck', label: '教学课件', agent: 'DeckAgent' },
  { id: 'code', label: '代码实操', agent: 'CodeAgent' },
];

const orbitStore = useOrbitStore();
const { planetSnapshots } = storeToRefs(orbitStore);
const mindmapMasteryMap = computed(() => {
  const map: Record<string, string> = {};
  const raw = planetSnapshots.value || {};
  for (const [slug, info] of Object.entries(raw)) {
    map[slug] = String(info?.status || 'dim');
  }
  return map;
});

const galaxies = ref<{ slug: string; name: string }[]>([]);
const planets = ref<{ slug: string; name: string }[]>([]);
const galaxySlug = ref('');
const planetSlug = ref('');
const selectedKinds = ref<ResourceKind[]>(['doc', 'mindmap', 'quiz', 'reading', 'media', 'deck', 'code']);
const extraReq = ref('');
const deckTemplate = ref('orbit');
const deckTemplates = ref<DeckTemplateMeta[]>([]);
const generating = ref(false);
const streamLog = ref<ResourceStreamEvent[]>([]);
const streamPreview = ref('');
const resources = ref<GeneratedResource[]>([]);
const activeResource = ref<GeneratedResource | null>(null);
const videoError = ref('');
const videoPlaying = ref(false);
const activeCaption = ref('');
const mindmapTip = ref('');
const mindmapAsk = ref('');
const mindmapBusy = ref(false);
const selectedMindNode = ref('');
const deckIndex = ref(0);
const vaultSaving = ref(false);
const vaultSaveTip = ref('');
const downloadTip = ref('');
const autoMountEnabled = ref(true);
const mountTip = ref('');
const focusTip = ref('');

const deckSpeaking = ref(false);

type MediaCaption = { start: number; end: number; text: string };
type SourcePage = { book: string; page: number; snippet?: string };
type MediaSlide = {
  title: string;
  narration: string;
  bullet_points?: string[];
  source_pages?: SourcePage[];
};

const mindmapTree = computed(() => {
  const r = activeResource.value;
  if (!r || r.kind !== 'mindmap') return { name: '思维导图' };
  try {
    const parsed = JSON.parse(r.content);
    return parsed.tree || parsed;
  } catch {
    return { name: r.planet_name || '思维导图' };
  }
});

async function onMindmapNode(name: string) {
  selectedMindNode.value = name;
  mindmapTip.value = `已选节点：${name}`;
  mindmapAsk.value = '';
}

async function mindmapAskNode() {
  if (!selectedMindNode.value || mindmapBusy.value) return;
  mindmapBusy.value = true;
  mindmapAsk.value = '追问中…';
  try {
    const res = await selectionAsk({
      quote: selectedMindNode.value,
      planet_slug: planetSlug.value || undefined,
      question: `围绕脑图节点「${selectedMindNode.value}」用苏格拉底式追问，帮助我深化理解。`,
    });
    mindmapAsk.value = res.answer || '暂无回复';
  } catch (e) {
    mindmapAsk.value = e instanceof Error ? e.message : '追问失败';
  } finally {
    mindmapBusy.value = false;
  }
}

async function mindmapQuizFromNode() {
  if (!selectedMindNode.value || !planetSlug.value || mindmapBusy.value) return;
  mindmapBusy.value = true;
  mindmapAsk.value = '正在根据节点出题…';
  try {
    const res = await companionChat(
      `请针对脑图节点「${selectedMindNode.value}」出一道选择题（含选项与简要解析），服务知识点 ${planetSlug.value}。`,
      'tutor',
      planetSlug.value,
      false,
    );
    mindmapAsk.value = res.reply;
  } catch (e) {
    mindmapAsk.value = e instanceof Error ? e.message : '出题失败';
  } finally {
    mindmapBusy.value = false;
  }
}

function mindmapFocusPlanet() {
  if (!selectedMindNode.value) return;
  const hit = planets.value.find(
    (p) => p.name.includes(selectedMindNode.value) || selectedMindNode.value.includes(p.name),
  );
  if (hit) {
    planetSlug.value = hit.slug;
    mindmapTip.value = `已切换到行星：${hit.name}`;
    void loadLibrary();
  } else {
    mindmapTip.value = `未匹配到同名行星，已记录节点「${selectedMindNode.value}」`;
  }
}

async function mindmapMountToPath() {
  if (!selectedMindNode.value || !activeResource.value || mindmapBusy.value) return;
  mindmapBusy.value = true;
  try {
    const path = await fetchLearningPath();
    if (!path?.steps?.length) {
      mindmapTip.value = '请先在「学习路径」生成计划后再挂载';
      return;
    }
    const matchIdx = path.steps.findIndex((s) => s.planet_slug && s.planet_slug === planetSlug.value);
    const stepIndex = matchIdx >= 0 ? matchIdx : 0;
    const rid = activeResource.value.id || 'mindmap';
    await mountPathStep(stepIndex, {
      kind: 'mindmap',
      id: `${rid}:${selectedMindNode.value}`,
      title: `脑图 · ${selectedMindNode.value}`,
      reason: `资源工坊节点 · ${activeResource.value.title || rid}`,
    });
    mindmapTip.value = `已挂到路径第 ${stepIndex + 1} 步：${selectedMindNode.value}`;
  } catch (e) {
    mindmapTip.value = e instanceof Error ? e.message : '挂到路径失败';
  } finally {
    mindmapBusy.value = false;
  }
}

const mindmapRef = ref<HTMLDivElement | null>(null);
const mediaRef = ref<HTMLDivElement | null>(null);
const videoEl = ref<HTMLVideoElement | null>(null);
let mindChart: echarts.ECharts | null = null;
let mediaTween: gsap.core.Tween | null = null;

const agentStatus = computed(() => {
  const map = new Map<string, 'waiting' | 'running' | 'done'>();
  for (const k of KIND_OPTIONS) map.set(k.agent, 'waiting');
  for (const e of streamLog.value) {
    if (e.type === 'agent_start') map.set(e.role, 'running');
    if (e.type === 'resource_done') map.set(e.role, 'done');
  }
  return map;
});

async function loadGalaxies() {
  galaxies.value = (await fetchGalaxies()).map((g) => ({ slug: g.slug, name: g.name }));
  if (!galaxySlug.value && galaxies.value[0]) galaxySlug.value = galaxies.value[0].slug;
}

async function loadPlanets() {
  if (!galaxySlug.value) return;
  const detail = await fetchGalaxyDetail(galaxySlug.value);
  planets.value = (detail.planets || []).map((p) => ({ slug: p.slug, name: p.name }));
  if (!planetSlug.value && planets.value[0]) planetSlug.value = planets.value[0].slug;
}

async function loadLibrary() {
  resources.value = await fetchLearnResources(planetSlug.value);
}

const streamDegraded = ref(false);
const streamError = ref('');
const queuedAfterBusy = ref(false);

type StreamKick = { runId: string; planetSlug?: string; kinds?: string[] };

function applyStreamMeta(detail: StreamKick) {
  if (detail.planetSlug) planetSlug.value = detail.planetSlug;
  if (detail.kinds?.length) {
    selectedKinds.value = detail.kinds as ResourceKind[];
  }
}

async function beginExternalStream(detail: StreamKick) {
  if (!detail.runId) return;
  if (generating.value) {
    // 只写 pending，不广播，避免 setPending→dispatch→再进本函数导致栈溢出
    writePendingResourceStream(detail);
    queuedAfterBusy.value = true;
    streamError.value = '';
    focusTip.value = '当前正在生成中，完成后将自动接续伴学任务…';
    return;
  }
  // 同步抢占，堵住与 handleGenerate / 二次事件的双流窗口
  generating.value = true;
  clearPendingResourceStream();
  applyStreamMeta(detail);
  focusTip.value = `伴学已启动资源流 ${detail.runId}`;
  await consumeRun(detail.runId);
}

async function consumeRun(run_id: string) {
  generating.value = true;
  streamLog.value = [];
  streamPreview.value = '';
  streamDegraded.value = false;
  streamError.value = '';
  activeResource.value = null;
  mountTip.value = '';
  const createdIds: string[] = [];
  try {
    await consumeResourceStream(run_id, (data) => {
      streamLog.value.push(data);
      if (data.payload?.degraded) streamDegraded.value = true;
      if (data.type === 'error') {
        streamError.value = data.content || '资源生成出错';
      }
      if (data.type === 'token') streamPreview.value += data.content;
      if (data.type === 'resource_done' && data.payload?.resource_id) {
        const r: GeneratedResource = {
          id: String(data.payload.resource_id),
          planet_slug: planetSlug.value,
          planet_name: planets.value.find((p) => p.slug === planetSlug.value)?.name || '',
          kind: data.payload.kind as ResourceKind,
          title: String(data.payload.title || ''),
          content: String(data.payload.content || ''),
          meta_json: (data.payload.meta as Record<string, unknown>) || {},
          created_at: new Date().toISOString(),
        };
        resources.value = [r, ...resources.value.filter((x) => x.id !== r.id)];
        createdIds.push(r.id);
        if (!activeResource.value) openResource(r);
      }
    });
    await loadLibrary();
    if (autoMountEnabled.value && createdIds.length) {
      try {
        const path = await fetchLearningPath();
        if (path?.steps?.length) {
          const matchIdx = path.steps.findIndex((s) => s.planet_slug && s.planet_slug === planetSlug.value);
          const stepIndex = matchIdx >= 0 ? matchIdx : path.steps.findIndex((s) => !s.completed);
          const idx = stepIndex >= 0 ? stepIndex : 0;
          for (const id of createdIds) {
            const r = resources.value.find((x) => x.id === id);
            if (!r) continue;
            await mountPathStep(idx, {
              kind: r.kind,
              id: r.id,
              title: r.title,
              reason: '资源工坊生成并自动挂载',
            });
          }
          mountTip.value = `已自动挂载 ${createdIds.length} 个资源到路径第 ${idx + 1} 步`;
        } else {
          mountTip.value = '资源已生成。尚未有学习路径时，可先生成路径再挂载。';
        }
      } catch (e) {
        mountTip.value = e instanceof Error ? e.message : '自动挂载失败';
      }
    }
  } catch (e) {
    streamError.value = e instanceof Error ? e.message : '生成中断，请重试';
    focusTip.value = streamError.value;
  } finally {
    generating.value = false;
    // 若生成中又排入了伴学任务，接续执行
    if (queuedAfterBusy.value) {
      queuedAfterBusy.value = false;
      const next = takePendingResourceStream();
      if (next?.runId) {
        void beginExternalStream({
          runId: next.runId,
          planetSlug: next.planetSlug,
          kinds: next.kinds,
        });
      }
    }
  }
}

async function handleGenerate() {
  if (!planetSlug.value || !selectedKinds.value.length || generating.value) return;
  generating.value = true;
  streamError.value = '';
  try {
    const { run_id } = await startResourceGeneration(
      planetSlug.value,
      selectedKinds.value,
      extraReq.value,
      [],
      selectedKinds.value.includes('deck') ? deckTemplate.value : 'orbit',
    );
    await consumeRun(run_id);
  } catch (e) {
    focusTip.value = e instanceof Error ? e.message : '启动资源生成失败';
    streamError.value = focusTip.value;
    generating.value = false;
    // 启动失败时若已有排队任务，尝试接续
    if (queuedAfterBusy.value) {
      queuedAfterBusy.value = false;
      const next = takePendingResourceStream();
      if (next?.runId) {
        void beginExternalStream({
          runId: next.runId,
          planetSlug: next.planetSlug,
          kinds: next.kinds,
        });
      }
    }
  }
}

async function focusById(resourceId: string) {
  if (!resourceId) return;
  let r = resources.value.find((x) => x.id === resourceId);
  if (!r) {
    try {
      const { fetchLearnResource } = await import('../../api/learnExtras');
      r = await fetchLearnResource(resourceId);
      if (r) resources.value = [r, ...resources.value.filter((x) => x.id !== r!.id)];
    } catch {
      focusTip.value = '未找到对应资源';
      return;
    }
  }
  if (r) {
    if (r.planet_slug) planetSlug.value = r.planet_slug;
    openResource(r);
    focusTip.value = `已打开：${r.title}`;
  }
}

function profileReasonOf(r: GeneratedResource): string {
  const m = r.meta_json || {};
  return typeof m.profile_reason === 'string' ? m.profile_reason : '';
}

async function saveActiveToVault() {
  if (!activeResource.value?.id || vaultSaving.value) return;
  vaultSaving.value = true;
  vaultSaveTip.value = '';
  try {
    const res = await ingestWorkshopToVault(activeResource.value.id);
    vaultSaveTip.value = `已保存到知识库：${res.path}`;
  } catch (e) {
    vaultSaveTip.value = e instanceof Error ? e.message : '保存失败';
  } finally {
    vaultSaving.value = false;
  }
}

function openResource(r: GeneratedResource) {
  activeResource.value = r;
  vaultSaveTip.value = '';

  videoError.value = '';
  videoPlaying.value = false;
  activeCaption.value = '';
  deckIndex.value = 0;
  stopDeckSpeech();
  void nextTick(() => {
    if (r.kind === 'mindmap') renderMindmap(r);
    if (r.kind === 'media') {
      playMedia(r);
      // 强制重新挂载 src，避免侧栏滚动层下 controls 假死
      if (videoEl.value) {
        const url = resolveMediaUrl(mediaMeta(r).media_url);
        videoEl.value.pause();
        videoEl.value.src = url;
        videoEl.value.load();
        syncCaptionFromVideo();
      }
    }
  });
}

function resolveMediaUrl(url?: string): string {
  if (!url) return '';
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('blob:')) return url;
  return url.startsWith('/') ? url : `/${url}`;
}

function onVideoError() {
  const url = activeResource.value ? mediaMeta(activeResource.value).media_url : '';
  videoError.value = `视频加载失败。请确认后端已启动，并访问 ${url || '/static/media/...'}（Vite 需代理 /static）。`;
}

async function toggleVideoPlay() {
  const el = videoEl.value;
  if (!el) return;
  videoError.value = '';
  try {
    if (el.paused) {
      await el.play();
      videoPlaying.value = true;
    } else {
      el.pause();
      videoPlaying.value = false;
    }
  } catch (err) {
    videoError.value = `无法播放：${err instanceof Error ? err.message : '浏览器拦截或文件不可读'}。可点下方「新窗口打开」验证文件。`;
    videoPlaying.value = false;
  }
}

function openMediaInNewTab() {
  const url = resolveMediaUrl(mediaMeta(activeResource.value!).media_url);
  if (url) window.open(url, '_blank', 'noopener');
}

function mediaKnowledgeId(r: GeneratedResource): string {
  const meta = (r.meta_json || {}) as { knowledge_point_id?: string };
  if (meta.knowledge_point_id) return meta.knowledge_point_id;
  try {
    const parsed = JSON.parse(r.content) as { knowledge_point_id?: string };
    return parsed.knowledge_point_id || r.planet_slug || '';
  } catch {
    return r.planet_slug || '';
  }
}

function renderMindmap(r: GeneratedResource) {
  if (!mindmapRef.value) return;
  let tree: { name: string; children?: unknown[] } = { name: r.planet_name };
  try {
    const parsed = JSON.parse(r.content);
    tree = parsed.tree || parsed;
  } catch {
    /* use default */
  }
  if (!mindChart) mindChart = echarts.init(mindmapRef.value);
  mindChart.setOption({
    backgroundColor: 'transparent',
    series: [{ type: 'tree', data: [tree], top: '5%', left: '10%', bottom: '5%', right: '20%', symbolSize: 8, label: { color: '#cbd5e1', fontSize: 11 }, lineStyle: { color: 'rgba(148,163,184,0.4)' } }],
  });
}

function mediaMeta(r: GeneratedResource): {
  media_url?: string;
  provider?: string;
  slides?: MediaSlide[];
  captions?: MediaCaption[];
  duration?: number;
  degraded?: boolean;
  degraded_label?: string;
  fallback_reason?: string;
} {
  const fromMeta = (r.meta_json || {}) as {
    media_url?: string;
    provider?: string;
    captions?: MediaCaption[];
    duration?: number;
    degraded?: boolean;
    degraded_label?: string;
    fallback_reason?: string;
  };
  try {
    const parsed = JSON.parse(r.content) as {
      media_url?: string;
      provider?: string;
      slides?: MediaSlide[];
      captions?: MediaCaption[];
      duration?: number;
      degraded?: boolean;
      degraded_label?: string;
      fallback_reason?: string;
    };
    return {
      media_url: fromMeta.media_url || parsed.media_url,
      provider: fromMeta.provider || parsed.provider,
      slides: parsed.slides || [],
      captions: fromMeta.captions || parsed.captions || [],
      duration: fromMeta.duration || parsed.duration,
      degraded: fromMeta.degraded ?? parsed.degraded,
      degraded_label: fromMeta.degraded_label || parsed.degraded_label,
      fallback_reason: fromMeta.fallback_reason || parsed.fallback_reason,
    };
  } catch {
    return {
      media_url: fromMeta.media_url,
      provider: fromMeta.provider,
      slides: [],
      captions: fromMeta.captions || [],
      duration: fromMeta.duration,
      degraded: fromMeta.degraded,
      degraded_label: fromMeta.degraded_label,
      fallback_reason: fromMeta.fallback_reason,
    };
  }
}

function resolveCaptions(r: GeneratedResource): MediaCaption[] {
  const meta = mediaMeta(r);
  if (meta.captions?.length) return meta.captions;
  const slides = meta.slides || [];
  if (!slides.length) return [];
  const dur = Math.max(2, Number(meta.duration) || 12);
  const slot = dur / slides.length;
  return slides.map((s, i) => {
    const text = [s.title, s.narration].filter(Boolean).join('：');
    return {
      start: i * slot,
      end: i === slides.length - 1 ? dur : (i + 1) * slot,
      text: text.slice(0, 100),
    };
  });
}

function syncCaptionFromVideo() {
  const el = videoEl.value;
  const r = activeResource.value;
  if (!el || !r || r.kind !== 'media') {
    activeCaption.value = '';
    return;
  }
  const t = el.currentTime || 0;
  const cue = resolveCaptions(r).find((c) => t >= c.start && t < c.end);
  activeCaption.value = cue?.text || '';
}

function slideProvenance(s: MediaSlide): string {
  const refs = s.source_pages || [];
  if (!refs.length) return '未溯源·已降级';
  return refs.map((r) => `${r.book} p.${r.page}`).join(' · ');
}

function mediaSlides(r: GeneratedResource): MediaSlide[] {
  return mediaMeta(r).slides || [];
}

function mediaHasMissingProvenance(r: GeneratedResource): boolean {
  const slides = mediaSlides(r);
  if (!slides.length) return true;
  return slides.some((s) => !s.source_pages?.length);
}

type DeckPack = {
  title: string;
  slides: MediaSlide[];
  pptx_url?: string;
};

function deckPack(r: GeneratedResource): DeckPack {
  const meta = (r.meta_json || {}) as { pptx_url?: string; deck_template?: string };
  try {
    const parsed = JSON.parse(r.content) as DeckPack;
    return {
      title: parsed.title || r.title,
      slides: Array.isArray(parsed.slides) ? parsed.slides : [],
      pptx_url: meta.pptx_url || parsed.pptx_url,
    };
  } catch {
    return { title: r.title, slides: [], pptx_url: meta.pptx_url };
  }
}

function deckThemeOf(r: GeneratedResource | null): DeckTemplateMeta | undefined {
  const id = String((r?.meta_json || {}).deck_template || deckTemplate.value || 'orbit');
  return deckTemplates.value.find((t) => t.id === id) || deckTemplates.value[0];
}

const deckSlides = computed(() =>
  activeResource.value?.kind === 'deck' ? deckPack(activeResource.value).slides : [],
);
const deckCurrent = computed(() => deckSlides.value[deckIndex.value] || null);
const deckPptxUrl = computed(() =>
  activeResource.value?.kind === 'deck' ? resolveMediaUrl(deckPack(activeResource.value).pptx_url) : '',
);

let deckAudio: HTMLAudioElement | null = null;
let deckObjectUrl: string | null = null;

function stopDeckSpeech() {
  deckSpeaking.value = false;
  if (deckAudio) {
    deckAudio.pause();
    deckAudio = null;
  }
  if (deckObjectUrl) {
    URL.revokeObjectURL(deckObjectUrl);
    deckObjectUrl = null;
  }
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}

function deckPrev() {
  stopDeckSpeech();
  if (deckIndex.value > 0) deckIndex.value -= 1;
}

function deckNext() {
  stopDeckSpeech();
  if (deckIndex.value < deckSlides.value.length - 1) deckIndex.value += 1;
}

async function speakDeckSlide() {
  const slide = deckCurrent.value;
  if (!slide) return;
  const text = [slide.title, slide.narration].filter(Boolean).join('。');
  if (!text.trim()) return;
  stopDeckSpeech();
  deckSpeaking.value = true;
  try {
    const blob = await synthesizeSpeech(text);
    deckObjectUrl = URL.createObjectURL(blob);
    const el = new Audio(deckObjectUrl);
    deckAudio = el;
    await new Promise<void>((resolve, reject) => {
      el.onended = () => resolve();
      el.onerror = () => reject(new Error('播放失败'));
      void el.play().catch(reject);
    });
  } catch {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      const u = new SpeechSynthesisUtterance(text.slice(0, 800));
      u.lang = 'zh-CN';
      await new Promise<void>((resolve) => {
        u.onend = () => resolve();
        u.onerror = () => resolve();
        window.speechSynthesis.speak(u);
      });
    }
  } finally {
    deckSpeaking.value = false;
  }
}

async function autoPlayDeck() {
  if (!deckSlides.value.length) return;
  for (let i = deckIndex.value; i < deckSlides.value.length; i += 1) {
    deckIndex.value = i;
    await speakDeckSlide();
    if (!deckSpeaking.value && i < deckSlides.value.length - 1) {
      // speakDeckSlide clears speaking in finally; continue
    }
  }
}

function providerLabel(p?: string) {
  if (p === 'seedance_1_0_pro_fast' || p === 'seedance_1_5_pro') return 'Seedance 生成';
  if (p === 'deepseek_gsap') return 'DeepSeek 分镜动画（降级）';
  if (p === 'cache_mp4') return '本地缓存加速';
  return p || 'unknown';
}

function playMedia(r: GeneratedResource) {
  mediaTween?.kill();
  window.speechSynthesis?.cancel();
  const meta = mediaMeta(r);
  // 有 media_url 时由模板 <video> 播放；下方展示完整字幕稿
  if (meta.media_url) {
    if (mediaRef.value) {
      const caps = resolveCaptions(r);
      const lines = caps.length
        ? caps.map((c) => `<p class="text-xs text-slate-200"><span class="text-sky-300">${c.start.toFixed(0)}s</span> ${c.text}</p>`).join('')
        : '<p class="text-xs text-slate-500">暂无字幕稿</p>';
      const slideLines = (meta.slides || [])
        .map(
          (s) =>
            `<p class="text-[10px] ${s.source_pages?.length ? 'text-emerald-300' : 'text-rose-300'}">${s.title} · 溯源：${slideProvenance(s)}</p>`,
        )
        .join('');
      mediaRef.value.innerHTML = `<p class="mb-2 text-[10px] text-emerald-300">可播放短视频 · ${meta.provider || 'seed_mp4'} · 知识点 ${String((r.meta_json as { knowledge_point_id?: string })?.knowledge_point_id || '')}${mediaHasMissingProvenance(r) ? ' · <span class="text-rose-300">未溯源·已降级</span>' : ''}</p><div class="space-y-1.5">${lines}</div><div class="mt-2 space-y-1 border-t border-white/10 pt-2">${slideLines || '<p class="text-[10px] text-slate-500">无分镜溯源</p>'}</div>`;
    }
    syncCaptionFromVideo();
    return;
  }
  if (!mediaRef.value) return;
  const slides = meta.slides || [];
  if (!slides.length) {
    mediaRef.value.innerHTML = '<p class="text-xs text-slate-500">暂无分镜内容</p>';
    return;
  }
  let idx = 0;
  const render = () => {
    const s = slides[idx % slides.length];
    if (!mediaRef.value) return;
    mediaRef.value.innerHTML = `<div class="media-slide"><h4 class="text-lg font-semibold text-white">${s.title}</h4><p class="mt-3 text-sm text-slate-300">${s.narration}</p><ul class="mt-3 list-disc pl-5 text-xs text-sky-200">${(s.bullet_points || []).map((b) => `<li>${b}</li>`).join('')}</ul><p class="mt-2 text-[10px] ${s.source_pages?.length ? 'text-emerald-300' : 'text-rose-300'}">溯源：${slideProvenance(s)}</p></div>`;
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(s.narration);
      u.lang = 'zh-CN';
      window.speechSynthesis.speak(u);
    }
    idx += 1;
  };
  render();
  mediaTween = gsap.delayedCall(6, function tick() {
    render();
    mediaTween = gsap.delayedCall(6, tick);
  });
}

function downloadActiveResource() {
  if (!activeResource.value) return;
  downloadTip.value = '';
  const err = triggerResourceDownload(activeResource.value);
  if (err) downloadTip.value = err;
}

const activeDownload = computed(() =>
  activeResource.value ? buildResourceDownload(activeResource.value) : null,
);

function quizQuestions(r: GeneratedResource) {
  try {
    return (JSON.parse(r.content).questions || []) as Array<Record<string, string>>;
  } catch {
    return [];
  }
}

function codeCase(r: GeneratedResource) {
  try {
    return JSON.parse(r.content) as { language?: string; code?: string; explanation?: string; exercise?: string };
  } catch {
    return {};
  }
}

function readingPack(r: GeneratedResource) {
  try {
    return JSON.parse(r.content) as { materials?: Array<Record<string, string>>; article?: string };
  } catch {
    return {};
  }
}

onMounted(async () => {
  await loadGalaxies();
  await loadPlanets();
  await loadLibrary();
  try {
    const data = await fetchDeckTemplates();
    deckTemplates.value = data.templates || [];
  } catch {
    deckTemplates.value = [];
  }
  const onFocus = (ev: Event) => {
    const detail = (ev as CustomEvent).detail as { resourceId?: string } | undefined;
    if (detail?.resourceId) void focusById(detail.resourceId);
  };
  const onStartStream = (ev: Event) => {
    const detail = (ev as CustomEvent).detail as {
      runId?: string;
      planetSlug?: string;
      kinds?: string[];
    } | undefined;
    if (!detail?.runId) return;
    void beginExternalStream({
      runId: detail.runId,
      planetSlug: detail.planetSlug,
      kinds: detail.kinds,
    });
  };
  window.addEventListener('sparkorbit:focus-resource', onFocus as EventListener);
  window.addEventListener('sparkorbit:start-resource-stream', onStartStream as EventListener);
  (window as unknown as { __sparkorbitFocusResource?: EventListener }).__sparkorbitFocusResource = onFocus as EventListener;
  (window as unknown as { __sparkorbitStartResourceStream?: EventListener }).__sparkorbitStartResourceStream =
    onStartStream as EventListener;

  // 挂载后消费伴学留下的 pending（解决 dock 未就绪时的竞态）
  await nextTick();
  const pending = takePendingResourceStream();
  if (pending?.runId) {
    void beginExternalStream({
      runId: pending.runId,
      planetSlug: pending.planetSlug,
      kinds: pending.kinds,
    });
  }
});

onBeforeUnmount(() => {
  mindChart?.dispose();
  mediaTween?.kill();
  stopDeckSpeech();
  window.speechSynthesis?.cancel();
  const onFocus = (window as unknown as { __sparkorbitFocusResource?: EventListener }).__sparkorbitFocusResource;
  if (onFocus) window.removeEventListener('sparkorbit:focus-resource', onFocus);
  const onStart = (window as unknown as { __sparkorbitStartResourceStream?: EventListener })
    .__sparkorbitStartResourceStream;
  if (onStart) window.removeEventListener('sparkorbit:start-resource-stream', onStart);
});
</script>

<template>
  <div class="dock-panel space-y-4">
    <div>
      <p class="lz-accent-text text-[10px] uppercase tracking-[0.35em] opacity-80">Resource Studio</p>
      <div class="mt-1 flex flex-wrap items-center gap-2">
        <h3 class="lz-title">多智能体资源工坊</h3>
        <LzBadge tone="accent">编排：流水线 workflow</LzBadge>
      </div>
      <p class="lz-desc mt-1">选择知识点，由多类专业 Agent 协同生成个性化学习资源（含教学课件）</p>
      <label class="lz-caption mt-2 flex items-center gap-2">
        <input v-model="autoMountEnabled" type="checkbox" class="rounded border-white/20" />
        生成后自动挂到当前学习路径步骤
      </label>
      <p v-if="mountTip" class="mt-1 text-[11px] text-emerald-300">{{ mountTip }}</p>
      <p v-if="focusTip" class="lz-accent-text mt-1 text-[11px]">{{ focusTip }}</p>
      <p v-if="streamError" class="mt-1 text-[11px] text-rose-300">{{ streamError }}</p>
    </div>

    <LzSection title="生成配置" desc="选择知识点与需要的资源类型" boxed>
      <div class="space-y-3">
        <div class="grid gap-2 sm:grid-cols-2">
          <select v-model="galaxySlug" class="lz-input h-[34px] px-2.5" @change="loadPlanets">
            <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
          </select>
          <select v-model="planetSlug" class="lz-input h-[34px] px-2.5" @change="loadLibrary">
            <option v-for="p in planets" :key="p.slug" :value="p.slug">{{ p.name }}</option>
          </select>
        </div>

        <div class="flex flex-wrap gap-2">
          <label
            v-for="k in KIND_OPTIONS"
            :key="k.id"
            class="flex cursor-pointer items-center gap-1.5 rounded-[var(--radius-ctl)] border px-2 py-1 text-xs transition"
            :class="
              selectedKinds.includes(k.id)
                ? 'border-[rgb(var(--lz-accent)/0.4)] bg-[rgb(var(--lz-accent)/0.12)] text-white'
                : 'border-[var(--border-soft)] text-slate-400 hover:text-slate-200'
            "
          >
            <input v-model="selectedKinds" type="checkbox" :value="k.id" class="rounded" />
            {{ k.label }}
          </label>
        </div>

        <input v-model="extraReq" placeholder="补充要求（可选）" class="lz-input h-[34px] w-full px-3" />

        <div v-if="selectedKinds.includes('deck')" class="space-y-2">
          <p class="lz-caption">课件 PPT 模板</p>
          <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
            <button
              v-for="tpl in deckTemplates"
              :key="tpl.id"
              type="button"
              class="rounded-[var(--radius-ctl)] border p-2 text-left text-xs transition"
              :class="
                deckTemplate === tpl.id
                  ? 'border-[rgb(var(--lz-accent)/0.5)] bg-[rgb(var(--lz-accent)/0.12)]'
                  : 'border-[var(--border-soft)]'
              "
              @click="deckTemplate = tpl.id"
            >
              <span class="mb-1.5 flex h-8 overflow-hidden rounded">
                <i class="flex-1" :style="{ background: tpl.colors.bg }" />
                <i class="w-2" :style="{ background: tpl.colors.accent }" />
                <i class="flex-1" :style="{ background: tpl.colors.bar }" />
              </span>
              <p class="text-slate-100">{{ tpl.name }}</p>
              <p class="mt-0.5 text-[10px] text-slate-500">{{ tpl.suitable }}</p>
            </button>
          </div>
        </div>

        <LzButton variant="primary" size="lg" block :loading="generating" @click="handleGenerate">
          {{ generating ? '多 Agent 协同生成中…' : '启动资源生成' }}
        </LzButton>
      </div>
    </LzSection>

    <ResourceGenerationStatus
      v-if="generating || streamLog.length"
      :generating="generating"
      :degraded="streamDegraded"
      :error="streamError"
      :preview="streamPreview"
      :items="KIND_OPTIONS.map((k) => ({ agent: k.agent, status: agentStatus.get(k.agent) || 'waiting' }))"
      :expected="selectedKinds.length"
    />

    <ResourceLibraryList
      :resources="resources"
      :active-id="activeResource?.id"
      @open="openResource"
      @generate="handleGenerate"
    />

    <section v-if="activeResource" class="lz-card lz-card--active p-4">
      <div class="flex flex-wrap items-start justify-between gap-2">
        <h4 class="lz-title text-sm">{{ activeResource.title }}</h4>
        <div class="flex flex-wrap gap-2">
          <LzButton
            v-if="activeDownload && !activeDownload.error"
            variant="soft"
            size="sm"
            @click="downloadActiveResource"
          >
            {{ activeDownload.label }}
          </LzButton>
          <LzButton
            variant="ghost"
            size="sm"
            :loading="vaultSaving"
            :disabled="!activeResource.id"
            @click="saveActiveToVault"
          >
            {{ vaultSaving ? '保存中…' : '保存到知识库' }}
          </LzButton>
        </div>
      </div>
      <p v-if="downloadTip" class="mt-1 text-[11px] text-amber-200">{{ downloadTip }}</p>
      <p v-else-if="activeDownload?.error" class="mt-1 text-[11px] text-amber-200">{{ activeDownload.error }}</p>
      <p v-if="vaultSaveTip" class="mt-1 text-[11px] text-emerald-200/90">{{ vaultSaveTip }}</p>
      <p v-if="profileReasonOf(activeResource)" class="lz-accent-text mt-1 text-[11px] opacity-90">
        {{ profileReasonOf(activeResource) }}
      </p>
      <p v-if="qualityOf(activeResource)" class="mt-1 text-[11px] text-amber-100/90">
        质量评分 A{{ qualityOf(activeResource)?.accuracy }}
        · 画像贴合 {{ qualityOf(activeResource)?.profile_fit }}
        · 完整 {{ qualityOf(activeResource)?.completeness }}
        · 幻觉风险 {{ qualityOf(activeResource)?.hallucination_risk }}
        <span v-if="qualityOf(activeResource)?.needs_review" class="text-rose-300"> · 待复核</span>
        <span v-if="qualityOf(activeResource)?.rationale" class="block text-slate-400">{{ qualityOf(activeResource)?.rationale }}</span>
      </p>

      <MarkdownView v-if="activeResource.kind === 'doc'" class="mt-3" :content="activeResource.content" />

      <div v-else-if="activeResource.kind === 'mindmap'" class="mt-3">
        <MindmapCanvas
          :tree="mindmapTree"
          :mastery-map="mindmapMasteryMap"
          @node-click="onMindmapNode"
        />
        <div v-if="selectedMindNode" class="mt-2 flex flex-wrap gap-2">
          <LzButton variant="soft" size="sm" :disabled="mindmapBusy" @click="mindmapAskNode">
            追问此节点
          </LzButton>
          <LzButton variant="ghost" size="sm" :disabled="mindmapBusy || !planetSlug" @click="mindmapQuizFromNode">
            据此出题
          </LzButton>
          <LzButton variant="ghost" size="sm" @click="mindmapFocusPlanet">
            定位行星
          </LzButton>
          <LzButton variant="ghost" size="sm" :disabled="mindmapBusy" @click="mindmapMountToPath">
            挂到路径
          </LzButton>
        </div>
        <p v-if="mindmapTip" class="lz-accent-text mt-2 text-xs">{{ mindmapTip }}</p>
        <p v-if="mindmapAsk" class="lz-card lz-card--flat lz-body mt-2 whitespace-pre-wrap p-2 text-xs">{{ mindmapAsk }}</p>
      </div>

      <div v-else-if="activeResource.kind === 'quiz'" class="mt-3 space-y-3">
        <div v-for="(q, i) in quizQuestions(activeResource)" :key="i" class="lz-card lz-card--flat p-3 text-xs text-slate-300">
          <p class="font-medium text-white">[{{ q.type }}] {{ q.question }}</p>
          <p v-if="q.options" class="mt-1 text-slate-400">{{ Array.isArray(q.options) ? q.options.join(' · ') : q.options }}</p>
          <p class="mt-1 text-emerald-300">答案：{{ q.answer }}</p>
          <p class="lz-caption mt-1">{{ q.explanation }}</p>
        </div>
      </div>

      <div v-else-if="activeResource.kind === 'reading'" class="mt-3 space-y-3 text-sm">
        <div v-for="(m, i) in readingPack(activeResource).materials || []" :key="i" class="lz-card lz-card--flat p-2 text-xs text-slate-400">
          <p class="lz-accent-text">{{ m.title }}</p>
          <p>{{ m.summary }}</p>
        </div>
        <MarkdownView :content="readingPack(activeResource).article || ''" />
      </div>

      <div v-else-if="activeResource.kind === 'media'" class="relative z-10 mt-3 space-y-3" @pointerdown.stop @click.stop>
        <p v-if="mediaMeta(activeResource).media_url" class="text-[11px] text-emerald-200">
          教学短视频 · 知识点
          <span class="font-mono text-sky-200">{{ mediaKnowledgeId(activeResource) }}</span>
          · {{ providerLabel(mediaMeta(activeResource).provider) }}
          <span v-if="mediaHasMissingProvenance(activeResource)" class="text-rose-300"> · 未溯源·已降级</span>
        </p>
        <p
          v-else-if="mediaMeta(activeResource).degraded || mediaMeta(activeResource).degraded_label"
          class="text-[11px] text-amber-200"
        >
          {{ String(mediaMeta(activeResource).degraded_label || '动画预览（Seedance 不可用时的分镜降级，非故障）') }}
          <span v-if="mediaMeta(activeResource).fallback_reason" class="text-slate-500">
            · {{ String(mediaMeta(activeResource).fallback_reason).slice(0, 80) }}
          </span>
        </p>
        <div v-if="mediaSlides(activeResource).length" class="lz-card lz-card--flat space-y-1 p-2">
          <p class="lz-caption uppercase tracking-wider">分镜溯源</p>
          <div v-for="(s, i) in mediaSlides(activeResource)" :key="i" class="text-[11px]">
            <span class="text-slate-200">{{ s.title }}</span>
            <span class="ml-2" :class="s.source_pages?.length ? 'text-emerald-300' : 'text-rose-300'">
              {{ slideProvenance(s) }}
            </span>
          </div>
        </div>
        <div
          v-if="mediaMeta(activeResource).media_url"
          class="relative isolate overflow-hidden rounded-lg border border-white/10 bg-slate-900"
          style="pointer-events: auto"
        >
          <video
            ref="videoEl"
            class="relative z-10 block w-full bg-black"
            style="pointer-events: auto"
            controls
            playsinline
            webkit-playsinline
            preload="auto"
            :src="resolveMediaUrl(mediaMeta(activeResource).media_url)"
            @error="onVideoError"
            @play="videoPlaying = true"
            @pause="videoPlaying = false"
            @timeupdate="syncCaptionFromVideo"
            @seeked="syncCaptionFromVideo"
            @click.stop
          />
          <div
            v-if="activeCaption"
            class="pointer-events-none absolute inset-x-0 bottom-10 z-30 flex justify-center px-4"
          >
            <p class="max-w-[92%] rounded bg-black/70 px-3 py-2 text-center text-sm leading-relaxed text-white shadow-lg">
              {{ activeCaption }}
            </p>
          </div>
          <button
            v-if="!videoPlaying"
            type="button"
            class="absolute inset-0 z-20 flex items-center justify-center bg-black/35 text-white transition hover:bg-black/45"
            style="pointer-events: auto"
            @click.stop.prevent="toggleVideoPlay"
          >
            <span class="rounded-full bg-sky-500/90 px-5 py-2 text-sm font-semibold shadow-lg">▶ 点击播放</span>
          </button>
        </div>
        <div class="flex flex-wrap gap-2">
          <LzButton variant="soft" size="sm" @click.stop="toggleVideoPlay">
            {{ videoPlaying ? '暂停' : '播放' }}
          </LzButton>
          <LzButton variant="ghost" size="sm" @click.stop="openMediaInNewTab">
            新窗口打开
          </LzButton>
          <LzButton
            v-if="activeDownload && !activeDownload.error"
            variant="soft"
            size="sm"
            @click.stop="downloadActiveResource"
          >
            {{ activeDownload.label }}
          </LzButton>
        </div>
        <p v-if="videoError" class="rounded-[var(--radius-ctl)] border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-[11px] text-rose-200">
          {{ videoError }}
        </p>
        <div ref="mediaRef" class="lz-card lz-card--flat min-h-[40px] p-3" />
      </div>

      <div v-else-if="activeResource.kind === 'deck'" class="mt-3 space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <p class="lz-accent-text text-[11px]">
            教学课件 · {{ deckIndex + 1 }}/{{ Math.max(deckSlides.length, 1) }}
          </p>
          <LzButton v-if="deckPptxUrl" variant="soft" size="sm" @click="downloadActiveResource">
            下载 PPT
          </LzButton>
        </div>

        <div
          v-if="deckCurrent"
          class="lz-card min-h-[200px] p-4"
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
          <ul v-if="deckCurrent.bullet_points?.length" class="mt-3 space-y-1.5 text-sm" :style="{ color: deckThemeOf(activeResource)?.colors.body }">
            <li v-for="(b, i) in deckCurrent.bullet_points" :key="i" class="flex gap-2">
              <span class="lz-accent-text">•</span>
              <span>{{ b }}</span>
            </li>
          </ul>
          <p class="lz-desc mt-4">{{ deckCurrent.narration }}</p>
          <p class="mt-2 text-[10px]" :class="deckCurrent.source_pages?.length ? 'text-emerald-300' : 'text-rose-300'">
            {{ slideProvenance(deckCurrent) }}
          </p>
        </div>
        <p v-else class="lz-desc">暂无幻灯片内容</p>

        <div class="flex flex-wrap gap-2">
          <LzButton variant="ghost" size="sm" :disabled="deckIndex <= 0" @click="deckPrev">
            上一页
          </LzButton>
          <LzButton variant="ghost" size="sm" :disabled="deckIndex >= deckSlides.length - 1" @click="deckNext">
            下一页
          </LzButton>
          <LzButton variant="soft" size="sm" :disabled="deckSpeaking || !deckCurrent" @click="speakDeckSlide">
            {{ deckSpeaking ? '讲解中…' : '讲解本页' }}
          </LzButton>
          <LzButton variant="soft" size="sm" :disabled="deckSpeaking || !deckSlides.length" @click="autoPlayDeck">
            自动讲解全部
          </LzButton>
          <LzButton variant="danger" size="sm" @click="stopDeckSpeech">
            停止
          </LzButton>
        </div>
      </div>

      <div v-else-if="activeResource.kind === 'code'" class="mt-3 space-y-2 text-sm">
        <pre class="overflow-x-auto rounded-[var(--radius-ctl)] bg-black/50 p-3 text-xs text-emerald-200"><code>{{ codeCase(activeResource).code }}</code></pre>
        <p class="lz-desc text-sm">{{ codeCase(activeResource).explanation }}</p>
        <p class="lz-accent-text">练习：{{ codeCase(activeResource).exercise }}</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import {
  clipNote,
  createBilibiliAsset,
  deleteStarAsset,
  listStarAssets,
  listStarLectures,
  markStarProgress,
  recommendBilibili,
  selectionAsk,
  uploadStarlibPdf,
  type StarAsset,
} from '../../api/challengeSprint';
import { fetchLearningPath, mountPathStep } from '../../api/learnExtras';
import { useAuthStore } from '../../stores/auth';
import { useOrbitStore } from '../../stores/orbit';
import PdfViewer, { type RegionCapturePayload } from './PdfViewer.vue';
import TextSelectionQa from './starlib/TextSelectionQa.vue';
import { LzBadge, LzButton, LzEmptyState, LzInput, LzSkeleton, LzTabs } from './ui';

type LibMode = 'yuanishu' | 'kaoyan';
type KaoyanSub = 'book' | 'video';
type BiliRec = {
  title: string;
  reason: string;
  search_url: string;
  bvid?: string;
  embed_url?: string;
  open_in_app?: boolean;
};
type LectureFolderInfo = {
  subject: string;
  chapter: string;
  fileStem: string;
  galaxySlug: string;
};
type LectureChapterGroup = {
  key: string;
  label: string;
  items: StarAsset[];
};
type LectureSubjectGroup = {
  key: string;
  label: string;
  galaxySlug: string;
  chapters: LectureChapterGroup[];
};

const SUBJECT_ORDER = ['数据结构', '计算机组成原理', '操作系统', '计算机网络'];
const GALAXY_SUBJECT_LABEL: Record<string, string> = {
  'data-structure': '数据结构',
  'computer-organization': '计算机组成原理',
  'operating-system': '操作系统',
  'computer-network': '计算机网络',
};

const orbit = useOrbitStore();
const auth = useAuthStore();
const galaxySlug = computed(() => orbit.currentGalaxy?.slug || '');
const planetName = computed(() => orbit.selectedPlanet?.name || '数据结构');
const planetSlug = computed(() => orbit.selectedPlanet?.slug || '');
const myUserId = computed(() => auth.user?.id || '');
const myRole = computed(() => auth.user?.role || 'student');
const myClassId = computed(() => auth.user?.classId || '');
const canManageLibrary = computed(() => Boolean(auth.user));

const mode = ref<LibMode>('yuanishu');
const kaoyanSub = ref<KaoyanSub>('book');
const assets = ref<StarAsset[]>([]);
const lectures = ref<StarAsset[]>([]);
const active = ref<StarAsset | null>(null);
const recommends = ref<BiliRec[]>([]);
const status = ref('');
const loading = ref(false);
const mountingBvid = ref('');
const mountingPathId = ref('');
const sidebarCollapsed = ref(false);
const askDrawerOpen = ref(false);
const immersive = ref(false);
const pageHasSelectableText = ref(true);
const uploadBusy = ref(false);
const deletingId = ref('');
const biliMountTitle = ref('');
const biliMountBvid = ref('');
const biliMountBusy = ref(false);
/** 考研视频目录树展开状态 */
const expandedSubjects = ref<Record<string, boolean>>({});
const expandedChapters = ref<Record<string, boolean>>({});

/** 划词 / 剪藏（提问为可选） */
const quoteText = ref('');
const askQuestion = ref('');
const askAnswer = ref('');
const askLoading = ref(false);
const pageNo = ref<number | undefined>(undefined);
/** 画笔裁切预览（data URL） */
const regionPreview = ref('');
const regionImageBase64 = ref('');
const regionImageMime = ref('image/jpeg');
/** 与伴学舱一致：费曼 / 苏格拉底 */
const feynmanMode = ref(false);
const socraticMode = ref(true);
/** 剪藏时无星球归属：弹出星系内选择器 */
const clipPlanetPickerOpen = ref(false);
const pendingClipPlanetSlug = ref('');
const galaxyPlanets = computed(() => orbit.currentGalaxy?.planets ?? []);

function parseDataUrl(dataUrl: string): { mime: string; b64: string } | null {
  const m = /^data:([^;]+);base64,(.+)$/s.exec(dataUrl);
  if (!m) return null;
  return { mime: m[1] || 'image/jpeg', b64: m[2] };
}

const viewer = ref<{
  kind: 'pdf' | 'video' | 'bilibili' | 'none';
  title: string;
  src: string;
  bvid?: string;
} | null>(null);

function isKaoyanGuide(a: StarAsset): boolean {
  const cat = a.meta_json?.category;
  if (cat === 'kaoyan_guide') return true;
  try {
    return /考研复习指导书/.test(decodeURIComponent(a.file_url || ''));
  } catch {
    return /考研复习指导书/.test(a.file_url || '');
  }
}

function isPdfLike(a: StarAsset): boolean {
  const t = a.asset_type;
  if (t === 'video_local' || t === 'video_bilibili') return false;
  if (a.file_url && /\.pdf($|\?)/i.test(a.file_url)) return true;
  return t === 'pdf' || t === 'book' || t === 'problem_doc';
}

const listForMode = computed(() => {
  if (mode.value === 'yuanishu') {
    return assets.value.filter((a) => a.asset_type !== 'video_local' && !isKaoyanGuide(a));
  }
  if (kaoyanSub.value === 'book') {
    return assets.value.filter((a) => isKaoyanGuide(a) && isPdfLike(a));
  }
  return lectures.value;
});

const showLectureTree = computed(
  () => mode.value === 'kaoyan' && kaoyanSub.value === 'video',
);

function lectureFolderInfo(a: StarAsset): LectureFolderInfo {
  const meta = (a.meta_json || {}) as Record<string, unknown>;
  const sourcePath = typeof meta.source_path === 'string' ? meta.source_path : '';
  let subject = typeof meta.subject === 'string' ? meta.subject.trim() : '';
  let chapter = typeof meta.chapter === 'string' ? meta.chapter.trim() : '';
  let fileStem = typeof meta.file_stem === 'string' ? meta.file_stem.trim() : '';

  if (sourcePath) {
    const parts = sourcePath.split('/').filter(Boolean);
    // 考研讲义视频 / 科目 / [章节] / file.mp4
    if (!subject && parts.length >= 2) subject = parts[1];
    if (!chapter && parts.length >= 4) chapter = parts.slice(2, -1).join(' · ');
    if (!fileStem && parts.length) {
      fileStem = parts[parts.length - 1].replace(/\.mp4$/i, '').replace(/[_]+/g, ' ').trim();
    }
  }

  if (!subject) {
    subject = GALAXY_SUBJECT_LABEL[a.galaxy_slug] || a.galaxy_slug || '未分科目';
  }
  if (!fileStem) {
    const idx = a.title.lastIndexOf(' · ');
    fileStem = idx >= 0 ? a.title.slice(idx + 3).trim() : a.title;
  }
  return { subject, chapter, fileStem, galaxySlug: a.galaxy_slug || '' };
}

function subjectSortKey(label: string): number {
  const i = SUBJECT_ORDER.indexOf(label);
  return i >= 0 ? i : 100;
}

const lectureTree = computed((): LectureSubjectGroup[] => {
  const subjectMap = new Map<string, LectureSubjectGroup>();
  for (const a of lectures.value) {
    const info = lectureFolderInfo(a);
    const subjectKey = info.subject || '未分科目';
    let subject = subjectMap.get(subjectKey);
    if (!subject) {
      subject = {
        key: subjectKey,
        label: subjectKey,
        galaxySlug: info.galaxySlug,
        chapters: [],
      };
      subjectMap.set(subjectKey, subject);
    }
    if (!subject.galaxySlug && info.galaxySlug) subject.galaxySlug = info.galaxySlug;
    const chapterKey = info.chapter || '_root';
    const chapterLabel = info.chapter || '未分章节';
    let chapter = subject.chapters.find((c) => c.key === chapterKey);
    if (!chapter) {
      chapter = { key: chapterKey, label: chapterLabel, items: [] };
      subject.chapters.push(chapter);
    }
    chapter.items.push(a);
  }

  const groups = [...subjectMap.values()];
  groups.sort((a, b) => subjectSortKey(a.label) - subjectSortKey(b.label) || a.label.localeCompare(b.label, 'zh'));
  for (const g of groups) {
    g.chapters.sort((a, b) => a.label.localeCompare(b.label, 'zh'));
    for (const c of g.chapters) {
      c.items.sort((a, b) => lectureFolderInfo(a).fileStem.localeCompare(lectureFolderInfo(b).fileStem, 'zh'));
    }
  }
  return groups;
});

function isSubjectExpanded(key: string): boolean {
  if (key in expandedSubjects.value) return expandedSubjects.value[key];
  // 默认展开当前星系对应科目，否则展开第一科
  const currentLabel = GALAXY_SUBJECT_LABEL[galaxySlug.value];
  if (currentLabel) return key === currentLabel;
  return lectureTree.value[0]?.key === key;
}

function isChapterExpanded(subjectKey: string, chapterKey: string): boolean {
  const id = `${subjectKey}::${chapterKey}`;
  if (id in expandedChapters.value) return expandedChapters.value[id];
  return true;
}

function toggleSubject(key: string) {
  expandedSubjects.value = { ...expandedSubjects.value, [key]: !isSubjectExpanded(key) };
}

function toggleChapter(subjectKey: string, chapterKey: string) {
  const id = `${subjectKey}::${chapterKey}`;
  expandedChapters.value = { ...expandedChapters.value, [id]: !isChapterExpanded(subjectKey, chapterKey) };
}

function lectureItemLabel(a: StarAsset): string {
  return lectureFolderInfo(a).fileStem || a.title;
}

function canDeleteAsset(a: StarAsset): boolean {
  if (!auth.user) return false;
  if (myRole.value === 'admin' || myRole.value === 'teacher') return true;
  return Boolean(a.owner_id && a.owner_id === myUserId.value);
}

function ownershipLabel(a: StarAsset): string {
  if (a.owner_id && a.owner_id === myUserId.value) return '我的';
  if (a.class_id && myClassId.value && a.class_id === myClassId.value) return '班级';
  if (!a.class_id) return '校本';
  return '班级';
}

async function removeAsset(a: StarAsset) {
  if (!canDeleteAsset(a)) return;
  if (!window.confirm(`确定删除「${a.title}」？`)) return;
  deletingId.value = a.id;
  try {
    await deleteStarAsset(a.id);
    assets.value = assets.value.filter((x) => x.id !== a.id);
    lectures.value = lectures.value.filter((x) => x.id !== a.id);
    if (active.value?.id === a.id) {
      active.value = null;
      viewer.value = null;
    }
    status.value = `已删除：${a.title}`;
  } catch (e) {
    status.value = e instanceof Error ? e.message : '删除失败';
  } finally {
    deletingId.value = '';
  }
}

async function onUploadPdf(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file) return;
  if (myRole.value === 'student' && !myClassId.value) {
    status.value = '请先加入班级后再上传';
    return;
  }
  uploadBusy.value = true;
  status.value = '正在上传并解析…';
  try {
    const res = await uploadStarlibPdf({
      file,
      title: file.name.replace(/\.pdf$/i, ''),
      galaxy_slug: galaxySlug.value,
      planet_slug: planetSlug.value,
      asset_type: 'book',
      description: myRole.value === 'student' ? '学生星库上传' : '星库上传',
      class_id: myClassId.value || undefined,
    });
    assets.value = await listStarAssets(galaxySlug.value);
    status.value = `已入库：${res.title}`;
    await openAsset(res, false);
  } catch (e) {
    status.value = e instanceof Error ? e.message : '上传失败';
  } finally {
    uploadBusy.value = false;
  }
}

async function mountManualBili() {
  const bvid = biliMountBvid.value.trim();
  if (!bvid) {
    status.value = '请填写 BV 号或链接';
    return;
  }
  if (myRole.value === 'student' && !myClassId.value) {
    status.value = '请先加入班级后再挂载';
    return;
  }
  biliMountBusy.value = true;
  try {
    const res = await createBilibiliAsset({
      title: biliMountTitle.value.trim() || `B站 ${bvid}`,
      bvid,
      galaxy_slug: galaxySlug.value,
      planet_slug: planetSlug.value,
      description: '星库手动挂载',
      class_id: myClassId.value || undefined,
    });
    assets.value = await listStarAssets(galaxySlug.value);
    biliMountBvid.value = '';
    biliMountTitle.value = '';
    status.value = `已挂载：${res.title}`;
    await openAsset(res, false);
  } catch (e) {
    status.value = e instanceof Error ? e.message : '挂载失败';
  } finally {
    biliMountBusy.value = false;
  }
}

async function load() {
  loading.value = true;
  status.value = '';
  try {
    const [a, lec, rec] = await Promise.all([
      listStarAssets(galaxySlug.value),
      // 考研讲义视频按磁盘目录浏览：拉全量，不按当前星系过滤
      listStarLectures(''),
      recommendBilibili(planetName.value),
    ]);
    assets.value = a;
    lectures.value = lec;
    recommends.value = rec as BiliRec[];
    if (!active.value) {
      const prefer =
        listForMode.value.find((x) => !planetSlug.value || x.planet_slug === planetSlug.value) ||
        listForMode.value[0];
      if (prefer) await openAsset(prefer, false);
    }
  } catch (e) {
    status.value = e instanceof Error ? e.message : '星库加载失败';
  } finally {
    loading.value = false;
  }
}

function resolveMediaUrl(url: string) {
  if (!url) return '';
  if (url.startsWith('http') || url.startsWith('blob:')) return url;
  return url.startsWith('/') ? url : `/${url}`;
}

/** 星库 PDF 有限 Range 预热：不全量下载，单本约 1–2MB */
const PREFETCH_HEAD = 65536;
const PREFETCH_TAIL = 524288;
const PREFETCH_MAX_CONCURRENT = 2;
const warmedPdfUrls = new Set<string>();
const prefetchControllers = new Set<AbortController>();
let prefetchInFlight = 0;
const prefetchQueue: string[] = [];
const hoverPrefetchTimers = new Map<string, number>();

function isPdfAsset(a: StarAsset): boolean {
  if (!a.file_url) return false;
  const t = a.asset_type;
  return /\.pdf($|\?)/i.test(a.file_url) || t === 'pdf' || t === 'book' || t === 'problem_doc';
}

async function warmPdfUrl(url: string) {
  if (!url || warmedPdfUrls.has(url)) return;
  warmedPdfUrls.add(url);
  const ac = new AbortController();
  prefetchControllers.add(ac);
  try {
    await fetch(url, {
      headers: { Range: `bytes=0-${PREFETCH_HEAD - 1}` },
      signal: ac.signal,
      credentials: 'same-origin',
    });
    if (ac.signal.aborted) return;
    const head = await fetch(url, { method: 'HEAD', signal: ac.signal, credentials: 'same-origin' });
    const len = Number(head.headers.get('content-length') || 0);
    if (len > PREFETCH_TAIL + PREFETCH_HEAD) {
      const start = len - PREFETCH_TAIL;
      await fetch(url, {
        headers: { Range: `bytes=${start}-${len - 1}` },
        signal: ac.signal,
        credentials: 'same-origin',
      });
    }
  } catch {
    warmedPdfUrls.delete(url);
  } finally {
    prefetchControllers.delete(ac);
  }
}

function pumpPrefetchQueue() {
  while (prefetchInFlight < PREFETCH_MAX_CONCURRENT && prefetchQueue.length) {
    const url = prefetchQueue.shift()!;
    if (warmedPdfUrls.has(url)) continue;
    prefetchInFlight += 1;
    void warmPdfUrl(url).finally(() => {
      prefetchInFlight -= 1;
      pumpPrefetchQueue();
    });
  }
}

function enqueuePdfPrefetch(url: string, priority = false) {
  if (!url || warmedPdfUrls.has(url) || prefetchQueue.includes(url)) return;
  if (priority) prefetchQueue.unshift(url);
  else prefetchQueue.push(url);
  pumpPrefetchQueue();
}

function scheduleVisiblePdfPrefetch() {
  const urls = listForMode.value.filter(isPdfAsset).map((a) => resolveMediaUrl(a.file_url)).filter(Boolean);
  for (const u of urls.slice(0, 6)) enqueuePdfPrefetch(u);
}

function onAssetHoverStart(a: StarAsset) {
  if (!isPdfAsset(a)) return;
  const url = resolveMediaUrl(a.file_url);
  const prev = hoverPrefetchTimers.get(a.id);
  if (prev) window.clearTimeout(prev);
  hoverPrefetchTimers.set(
    a.id,
    window.setTimeout(() => {
      hoverPrefetchTimers.delete(a.id);
      enqueuePdfPrefetch(url, true);
    }, 300),
  );
}

function onAssetHoverEnd(a: StarAsset) {
  const t = hoverPrefetchTimers.get(a.id);
  if (t) {
    window.clearTimeout(t);
    hoverPrefetchTimers.delete(a.id);
  }
}

function cancelAllPdfPrefetch() {
  for (const t of hoverPrefetchTimers.values()) window.clearTimeout(t);
  hoverPrefetchTimers.clear();
  prefetchQueue.length = 0;
  for (const ac of prefetchControllers) ac.abort();
  prefetchControllers.clear();
}

async function openAsset(a: StarAsset, mark = true) {
  active.value = a;
  const t = a.asset_type;
  if (t === 'video_local' || (a.file_url && /\.mp4($|\?)/i.test(a.file_url))) {
    viewer.value = { kind: 'video', title: a.title, src: resolveMediaUrl(a.file_url) };
  } else if (t === 'video_bilibili' || a.bilibili_bvid) {
    viewer.value = {
      kind: 'bilibili',
      title: a.title,
      src: `https://player.bilibili.com/player.html?bvid=${a.bilibili_bvid}&high_quality=1`,
      bvid: a.bilibili_bvid,
    };
  } else if (a.file_url && (/\.pdf($|\?)/i.test(a.file_url) || t === 'pdf' || t === 'book' || t === 'problem_doc')) {
    viewer.value = { kind: 'pdf', title: a.title, src: resolveMediaUrl(a.file_url) };
  } else if (a.file_url) {
    viewer.value = { kind: 'pdf', title: a.title, src: resolveMediaUrl(a.file_url) };
  } else {
    viewer.value = { kind: 'none', title: a.title, src: '' };
  }
  if (mark) {
    try {
      await markStarProgress(a.id, 1, 45);
      status.value = '已记录学习进度，可计入学闸';
    } catch {
      /* ignore */
    }
  }
}

function openBiliRec(r: BiliRec) {
  if (r.bvid || r.embed_url) {
    viewer.value = {
      kind: 'bilibili',
      title: r.title,
      src: r.embed_url || `https://player.bilibili.com/player.html?bvid=${r.bvid}&high_quality=1`,
      bvid: r.bvid,
    };
    status.value = '已在星库内打开 B 站推荐（不跳出页面）';
    return;
  }
  viewer.value = {
    kind: 'bilibili',
    title: r.title,
    src: r.search_url,
  };
  status.value = '已在星库内打开相关视频搜索';
}

async function mountToPath(a: StarAsset) {
  mountingPathId.value = a.id;
  try {
    const path = await fetchLearningPath();
    if (!path?.steps?.length) {
      status.value = '请先在「学习路径」生成计划后再挂载';
      return;
    }
    const matchIdx = path.steps.findIndex((s) => s.planet_slug && s.planet_slug === planetSlug.value);
    const stepIndex = matchIdx >= 0 ? matchIdx : 0;
    await mountPathStep(stepIndex, {
      kind: 'starlib',
      id: a.id,
      title: a.title,
      reason: `星库 · ${a.asset_type}`,
    });
    status.value = `已挂到路径第 ${stepIndex + 1} 步：${a.title}`;
  } catch (e) {
    status.value = e instanceof Error ? e.message : '挂到路径失败';
  } finally {
    mountingPathId.value = '';
  }
}

async function mountBiliRec(r: BiliRec) {
  if (!r.bvid) {
    status.value = '该推荐无 BV 号，无法挂载';
    return;
  }
  mountingBvid.value = r.bvid;
  try {
    await createBilibiliAsset({
      title: r.title,
      bvid: r.bvid,
      galaxy_slug: galaxySlug.value,
      planet_slug: planetSlug.value,
      description: r.reason,
    });
    assets.value = await listStarAssets(galaxySlug.value);
    status.value = `已挂载进星库：${r.title}`;
  } catch (e) {
    status.value = e instanceof Error ? e.message : '挂载失败';
  } finally {
    mountingBvid.value = '';
  }
}

function switchMode(m: LibMode) {
  mode.value = m;
  viewer.value = null;
  active.value = null;
  quoteText.value = '';
  askAnswer.value = '';
  askDrawerOpen.value = false;
  clipPlanetPickerOpen.value = false;
  pendingClipPlanetSlug.value = '';
  const prefer =
    listForMode.value.find((x) => !planetSlug.value || x.planet_slug === planetSlug.value) ||
    listForMode.value[0];
  if (prefer) void openAsset(prefer, false);
}

function switchKaoyanSub(s: KaoyanSub) {
  kaoyanSub.value = s;
  viewer.value = null;
  active.value = null;
  const prefer =
    listForMode.value.find((x) => !planetSlug.value || x.planet_slug === planetSlug.value) ||
    listForMode.value[0];
  if (prefer) void openAsset(prefer, false);
}

async function askSelection() {
  const quote = quoteText.value.trim();
  const hasImage = Boolean(regionImageBase64.value);
  if (!quote && !hasImage) {
    status.value = '请先划词、粘贴文字，或用画笔框选区域';
    return;
  }
  askLoading.value = true;
  askAnswer.value = '';
  try {
    const mode = feynmanMode.value ? 'feynman' : 'tutor';
    const res = await selectionAsk({
      quote: quote || undefined,
      asset_id: active.value?.id,
      page_no: pageNo.value,
      planet_slug: planetSlug.value || active.value?.planet_slug,
      question: askQuestion.value.trim() || undefined,
      image_base64: hasImage ? regionImageBase64.value : undefined,
      image_mime: hasImage ? regionImageMime.value : undefined,
      mode,
      socratic: socraticMode.value && !feynmanMode.value,
    });
    askAnswer.value = res.answer;
    if (mode === 'feynman' && typeof res.explain_score === 'number') {
      const slug = planetSlug.value || active.value?.planet_slug || '';
      if (slug) orbit.setExplainScore(slug, res.explain_score);
      status.value = `费曼评分 ${(res.explain_score * 100).toFixed(0)} 分`;
    } else {
      status.value = res.gates ? '已记录划词提问学闸证据' : '伴学回复已生成';
    }
  } catch (e) {
    status.value = e instanceof Error ? e.message : '划词提问失败';
  } finally {
    askLoading.value = false;
  }
}

function resolveClipPlanetSlug(): string {
  return planetSlug.value || active.value?.planet_slug || pendingClipPlanetSlug.value || '';
}

async function performClipNote(slug: string) {
  try {
    await clipNote(
      slug,
      {
        kind: 'quote',
        text: quoteText.value.trim() || '（画笔框选区域）',
        asset_id: active.value?.id,
        page_no: pageNo.value,
        source: 'starlib',
        has_region_image: Boolean(regionPreview.value),
      },
      active.value?.title ? `划词 · ${active.value.title}` : '星库划词',
    );
    status.value = '已写入星轨知识库 · 划词剪藏';
    clipPlanetPickerOpen.value = false;
    pendingClipPlanetSlug.value = '';
  } catch (e) {
    status.value = e instanceof Error ? e.message : '划词剪藏失败';
  }
}

async function collectWordToReview() {
  const quote = quoteText.value.trim();
  if (!quote) {
    status.value = '请先划词再加入生词本';
    return;
  }
  try {
    const { addReviewCard } = await import('../../api/review');
    await addReviewCard({
      kind: 'word',
      front: quote.slice(0, 200),
      back: askAnswer.value.trim().slice(0, 2000),
      source_id: '',
    });
    status.value = '已加入生词本，进入今日复习队列';
    orbit.pushNotification('生词本', `「${quote.slice(0, 20)}」已加入复习队列`, 'success');
  } catch (e) {
    status.value = e instanceof Error ? e.message : '加入生词本失败';
  }
}

async function clipQuoteToNote() {
  if (!quoteText.value.trim() && !regionPreview.value) {
    status.value = '无可剪藏的划词/框选内容';
    return;
  }
  const slug = resolveClipPlanetSlug();
  if (slug) {
    await performClipNote(slug);
    return;
  }
  if (!galaxyPlanets.value.length) {
    status.value = '请先进入星系或选择行星';
    clipPlanetPickerOpen.value = false;
    return;
  }
  clipPlanetPickerOpen.value = true;
  status.value = '请选择划词归属的知识点星球';
}

async function confirmClipPlanet() {
  const slug = pendingClipPlanetSlug.value.trim();
  if (!slug) {
    status.value = '请选择归属星球';
    return;
  }
  const galaxy = orbit.currentGalaxy;
  const planet = galaxy?.planets.find((p) => p.slug === slug);
  if (galaxy && planet) {
    orbit.selectPlanet(planet, galaxy);
  }
  await performClipNote(slug);
}

function onTextSelect(text: string, p: number) {
  quoteText.value = text;
  pageNo.value = p;
  regionPreview.value = '';
  regionImageBase64.value = '';
  askDrawerOpen.value = true;
}

function onSelectableChange(hasText: boolean, p: number) {
  pageHasSelectableText.value = hasText;
  pageNo.value = p;
  if (!hasText && askDrawerOpen.value) {
    status.value = '本页无可选文字 · 可用涂抹笔/圈选笔框选后问伴学';
  }
}

function onRegionCapture(payload: RegionCapturePayload) {
  const parsed = parseDataUrl(payload.dataUrl);
  if (!parsed) {
    status.value = '区域截图失败，请重试';
    return;
  }
  regionPreview.value = payload.dataUrl;
  regionImageBase64.value = parsed.b64;
  regionImageMime.value = parsed.mime;
  pageNo.value = payload.page;
  askDrawerOpen.value = true;
  status.value =
    payload.mode === 'smear'
      ? '已涂抹选区，可补充说明后点「问伴学」'
      : '已圈选区域，可补充说明后点「问伴学」';
}

function clearRegionCapture() {
  regionPreview.value = '';
  regionImageBase64.value = '';
}

onMounted(() => void load());
onBeforeUnmount(() => cancelAllPdfPrefetch());
watch(galaxySlug, () => void load());
watch(planetName, () => {
  void recommendBilibili(planetName.value).then((r) => {
    recommends.value = r as BiliRec[];
  });
});
watch(listForMode, () => {
  const ric = (window as Window & { requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number })
    .requestIdleCallback;
  if (typeof ric === 'function') ric(() => scheduleVisiblePdfPrefetch(), { timeout: 2500 });
  else window.setTimeout(() => scheduleVisiblePdfPrefetch(), 800);
});
</script>

<template>
  <div class="flex h-full min-h-[min(70vh,720px)] flex-col gap-3 text-slate-200">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p class="lz-caption lz-accent-text uppercase tracking-[0.3em]">Star Library</p>
        <div class="flex items-center gap-2">
          <h3 class="lz-title">星库</h3>
          <LzBadge v-if="mode === 'kaoyan'" tone="warning">考研模式</LzBadge>
        </div>
        <p class="mt-1 lz-caption">站内阅读 · 原书 / 考研讲义 · 打开即成问答上下文与学闸证据</p>
      </div>
      <LzTabs
        :items="[
          { key: 'yuanishu', label: '原书拓展' },
          { key: 'kaoyan', label: '考研讲义' },
        ]"
        :model-value="mode"
        @update:model-value="(v) => switchMode(v as LibMode)"
      />
    </div>

    <p class="lz-card lz-card--flat px-3 py-2 lz-caption leading-5">
      <template v-if="mode === 'yuanishu'">
        原书模式：教材课本 PDF 站内预览；视频走 B 站相关推荐（站内嵌入，不跳出）。
      </template>
      <template v-else>
        考研讲义：王道等复习指导书阅读 + 本地精讲视频观看。
      </template>
    </p>

    <LzTabs
      v-if="mode === 'kaoyan'"
      class="self-start"
      :items="[
        { key: 'book', label: '书本阅读' },
        { key: 'video', label: '视频观看' },
      ]"
      :model-value="kaoyanSub"
      @update:model-value="(v) => switchKaoyanSub(v as KaoyanSub)"
    />

    <div
      class="grid min-h-0 flex-1 gap-3"
      :class="sidebarCollapsed ? 'grid-cols-1' : showLectureTree ? 'lg:grid-cols-[280px_1fr]' : 'lg:grid-cols-[240px_1fr]'"
    >
      <div v-show="!sidebarCollapsed" class="space-y-2 overflow-auto">
        <div class="flex items-center justify-between">
          <p class="lz-caption uppercase tracking-wider">
            {{
              mode === 'kaoyan'
                ? kaoyanSub === 'book'
                  ? '考研指导书'
                  : '本地讲义视频'
                : '教材与资料'
            }}
          </p>
          <LzButton variant="ghost" size="sm" @click="sidebarCollapsed = true">收起</LzButton>
        </div>

        <div
          v-if="canManageLibrary && (mode === 'yuanishu' || (mode === 'kaoyan' && kaoyanSub === 'book'))"
          class="lz-card space-y-2 p-2.5"
        >
          <label
            class="lz-btn lz-btn--soft lz-btn--sm w-full cursor-pointer"
            :class="uploadBusy ? 'pointer-events-none opacity-60' : ''"
          >
            <input type="file" accept="application/pdf,.pdf" class="hidden" :disabled="uploadBusy" @change="onUploadPdf" />
            {{ uploadBusy ? '上传解析中…' : '上传 PDF 到星库' }}
          </label>
          <div class="space-y-1.5">
            <LzInput v-model="biliMountTitle" size="sm" placeholder="标题（可选）" />
            <LzInput v-model="biliMountBvid" size="sm" placeholder="BV 号或链接" />
            <LzButton variant="soft" size="sm" block :loading="biliMountBusy" @click="mountManualBili">
              {{ biliMountBusy ? '挂载中…' : '挂载 B 站' }}
            </LzButton>
          </div>
        </div>

        <!-- 考研视频：按 科目 → 章节 目录树 -->
        <template v-if="showLectureTree">
          <div v-for="subj in lectureTree" :key="subj.key" class="space-y-1">
            <button
              type="button"
              class="lz-card lz-card--hover flex w-full items-center gap-1.5 px-2.5 py-2 text-left text-[11px] font-semibold text-white"
              @click="toggleSubject(subj.key)"
            >
              <span class="lz-accent-text inline-block w-3">{{ isSubjectExpanded(subj.key) ? '▾' : '▸' }}</span>
              <span class="min-w-0 flex-1 truncate">{{ subj.label }}</span>
              <span class="shrink-0 text-[10px] font-normal text-slate-500">
                {{ subj.chapters.reduce((n, c) => n + c.items.length, 0) }}
              </span>
            </button>
            <div v-show="isSubjectExpanded(subj.key)" class="ml-1 space-y-1 border-l border-[var(--border-soft)] pl-2">
              <div v-for="ch in subj.chapters" :key="ch.key" class="space-y-1">
                <button
                  type="button"
                  class="flex w-full items-center gap-1.5 rounded-[var(--radius-ctl)] px-2 py-1.5 text-left text-[10px] font-medium text-slate-300 transition hover:bg-white/5"
                  @click="toggleChapter(subj.key, ch.key)"
                >
                  <span class="inline-block w-3 text-slate-500">{{ isChapterExpanded(subj.key, ch.key) ? '▾' : '▸' }}</span>
                  <span class="min-w-0 flex-1 truncate">{{ ch.label }}</span>
                  <span class="shrink-0 text-slate-500">{{ ch.items.length }}</span>
                </button>
                <div v-show="isChapterExpanded(subj.key, ch.key)" class="space-y-1.5 pl-1">
                  <div
                    v-for="a in ch.items"
                    :key="a.id"
                    role="button"
                    tabindex="0"
                    class="lz-card w-full cursor-pointer px-3 py-2.5 text-left text-xs"
                    :class="active?.id === a.id ? 'lz-card--active' : 'lz-card--hover'"
                    @click="openAsset(a)"
                    @keydown.enter="openAsset(a)"
                  >
                    <p class="lz-subtitle">{{ lectureItemLabel(a) }}</p>
                    <p class="mt-1 lz-caption">
                      video_local · {{ ownershipLabel(a) }}
                    </p>
                    <div class="mt-2 flex flex-wrap gap-1.5">
                      <LzButton
                        variant="soft"
                        size="sm"
                        :disabled="mountingPathId === a.id"
                        @click.stop="mountToPath(a)"
                      >
                        {{ mountingPathId === a.id ? '挂载中…' : '挂到路径' }}
                      </LzButton>
                      <LzButton
                        v-if="canDeleteAsset(a)"
                        variant="danger"
                        size="sm"
                        :disabled="deletingId === a.id"
                        @click.stop="removeAsset(a)"
                      >
                        {{ deletingId === a.id ? '删除中…' : '删除' }}
                      </LzButton>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- 书本 / 原书：扁平列表 -->
        <template v-else>
          <div
            v-for="a in listForMode"
            :key="a.id"
            role="button"
            tabindex="0"
            class="lz-card w-full cursor-pointer px-3 py-3 text-left text-xs"
            :class="active?.id === a.id ? 'lz-card--active' : 'lz-card--hover'"
            @mouseenter="onAssetHoverStart(a)"
            @mouseleave="onAssetHoverEnd(a)"
            @click="openAsset(a)"
            @keydown.enter="openAsset(a)"
          >
            <p class="lz-subtitle">{{ a.title }}</p>
            <p class="mt-1 lz-caption">
              {{ a.asset_type }}
              <span v-if="a.page_count"> · {{ a.page_count }} 页</span>
              · {{ ownershipLabel(a) }}
            </p>
            <div class="mt-2 flex flex-wrap gap-1.5">
              <LzButton
                variant="soft"
                size="sm"
                :disabled="mountingPathId === a.id"
                @click.stop="mountToPath(a)"
              >
                {{ mountingPathId === a.id ? '挂载中…' : '挂到路径' }}
              </LzButton>
              <LzButton
                v-if="canDeleteAsset(a)"
                variant="danger"
                size="sm"
                :disabled="deletingId === a.id"
                @click.stop="removeAsset(a)"
              >
                {{ deletingId === a.id ? '删除中…' : '删除' }}
              </LzButton>
            </div>
          </div>
        </template>
        <LzSkeleton v-if="loading && !listForMode.length" preset="list" :rows="4" />
        <LzEmptyState
          v-if="!listForMode.length && !loading"
          icon="📚"
          :title="
            mode === 'kaoyan'
              ? kaoyanSub === 'book'
                ? '暂无考研指导书 PDF'
                : '暂无本地讲义视频'
              : '暂无星库资产'
          "
          :desc="
            mode === 'kaoyan'
              ? kaoyanSub === 'book'
                ? '可在上方上传，或运行资料导入脚本。'
                : '可将 MP4 放入 资料/考研讲义视频/<科目>/<章节>/ 后运行导入脚本。'
              : '可在上方上传 PDF / 挂载 B 站。'
          "
        />

        <template v-if="mode === 'yuanishu'">
          <p class="pt-2 lz-caption uppercase tracking-wider">AI 相关 B 站推荐</p>
          <div
            v-for="(r, i) in recommends"
            :key="i"
            class="lz-card lz-card--hover w-full px-3 py-2.5 text-left text-xs"
          >
            <button type="button" class="w-full text-left transition hover:text-white" @click="openBiliRec(r)">
              <span class="lz-subtitle">{{ r.title }}</span>
              <span class="mt-1 block lz-caption">{{ r.reason }}</span>
            </button>
            <LzButton
              v-if="r.bvid"
              variant="soft"
              size="sm"
              class="mt-2"
              :disabled="mountingBvid === r.bvid"
              @click="mountBiliRec(r)"
            >
              {{ mountingBvid === r.bvid ? '挂载中…' : '挂载进星库' }}
            </LzButton>
          </div>
        </template>
      </div>

      <div class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[var(--radius-panel)] border border-[var(--border-soft)] bg-black/50">
        <div v-if="viewer" class="flex items-center justify-between gap-2 border-b border-[var(--border-soft)] px-4 py-2.5">
          <div class="flex min-w-0 items-center gap-2">
            <LzButton
              v-if="sidebarCollapsed"
              variant="ghost"
              size="sm"
              class="shrink-0"
              @click="sidebarCollapsed = false"
            >
              目录
            </LzButton>
            <p class="lz-subtitle truncate">{{ viewer.title }}</p>
          </div>
          <div class="flex shrink-0 items-center gap-1.5">
            <LzBadge tone="neutral">
              {{
                viewer.kind === 'pdf'
                  ? 'PDF 阅读器'
                  : viewer.kind === 'video'
                    ? '本地视频'
                    : viewer.kind === 'bilibili'
                      ? 'B站内嵌'
                      : '预览'
              }}
            </LzBadge>
            <LzButton
              v-if="viewer.kind === 'pdf'"
              variant="soft"
              size="sm"
              @click="immersive = true"
            >
              沉浸阅读
            </LzButton>
            <LzButton
              v-if="viewer.kind === 'pdf'"
              variant="ghost"
              size="sm"
              @click="askDrawerOpen = !askDrawerOpen"
            >
              {{ askDrawerOpen ? '收起划词' : '划词' }}
            </LzButton>
          </div>
        </div>
        <div class="relative min-h-0 flex-1 bg-slate-950">
          <PdfViewer
            v-if="viewer?.kind === 'pdf' && viewer.src && !immersive"
            class="h-full w-full"
            :src="viewer.src"
            @page-change="(p) => { pageNo = p }"
            @text-select="onTextSelect"
            @selectable-change="onSelectableChange"
            @region-capture="onRegionCapture"
          />
          <video
            v-else-if="viewer?.kind === 'video' && viewer.src"
            class="h-full w-full object-contain"
            :src="viewer.src"
            controls
            playsinline
            @play="status = '正在观看本地讲义…'"
          />
          <iframe
            v-else-if="viewer?.kind === 'bilibili' && viewer.src"
            class="h-full w-full min-h-[320px]"
            :src="viewer.src"
            allowfullscreen
            referrerpolicy="no-referrer"
          />
          <div v-else class="flex h-full min-h-[280px] items-center justify-center p-6">
            <LzSkeleton v-if="loading" preset="card" :rows="2" class="w-full max-w-md" />
            <LzEmptyState
              v-else
              icon="🛰"
              title="尚未打开内容"
              desc="从左侧选择教材 / 讲义 / 推荐视频，在此站内打开"
            />
          </div>
        </div>

        <TextSelectionQa
          v-if="viewer?.kind === 'pdf' && askDrawerOpen && !immersive"
          v-model:quote-text="quoteText"
          v-model:ask-question="askQuestion"
          v-model:page-no="pageNo"
          v-model:feynman-mode="feynmanMode"
          v-model:socratic-mode="socraticMode"
          v-model:pending-planet-slug="pendingClipPlanetSlug"
          :page-has-selectable-text="pageHasSelectableText"
          :region-preview="regionPreview"
          :ask-answer="askAnswer"
          :ask-loading="askLoading"
          :clip-picker-open="clipPlanetPickerOpen"
          :planets="galaxyPlanets"
          @ask="askSelection"
          @clip="clipQuoteToNote"
          @collect-word="collectWordToReview"
          @clear-region="clearRegionCapture"
          @confirm-clip="confirmClipPlanet"
          @cancel-clip="clipPlanetPickerOpen = false; pendingClipPlanetSlug = ''"
        />
      </div>
    </div>

    <p v-if="status" class="text-xs text-emerald-300">{{ status }}</p>

    <Teleport to="body">
      <div
        v-if="immersive && viewer?.kind === 'pdf' && viewer.src"
        class="lz-accent-sky fixed inset-0 z-[115] flex flex-col bg-slate-950"
      >
        <div class="flex items-center justify-between gap-2 border-b border-[var(--border-soft)] px-4 py-2">
          <p class="lz-subtitle truncate">{{ viewer.title }} · 沉浸阅读</p>
          <div class="flex shrink-0 items-center gap-1.5">
            <LzButton variant="soft" size="sm" @click="askDrawerOpen = !askDrawerOpen">
              {{ askDrawerOpen ? '收起划词' : '划词' }}
            </LzButton>
            <LzButton variant="ghost" size="sm" @click="immersive = false">退出沉浸</LzButton>
          </div>
        </div>
        <PdfViewer
          class="min-h-0 flex-1"
          :src="viewer.src"
          @page-change="(p) => { pageNo = p }"
          @text-select="onTextSelect"
          @selectable-change="onSelectableChange"
          @region-capture="onRegionCapture"
        />
        <TextSelectionQa
          v-if="askDrawerOpen"
          compact
          v-model:quote-text="quoteText"
          v-model:ask-question="askQuestion"
          v-model:page-no="pageNo"
          v-model:feynman-mode="feynmanMode"
          v-model:socratic-mode="socraticMode"
          v-model:pending-planet-slug="pendingClipPlanetSlug"
          :page-has-selectable-text="pageHasSelectableText"
          :region-preview="regionPreview"
          :ask-answer="askAnswer"
          :ask-loading="askLoading"
          :clip-picker-open="clipPlanetPickerOpen"
          :planets="galaxyPlanets"
          @ask="askSelection"
          @clip="clipQuoteToNote"
          @collect-word="collectWordToReview"
          @clear-region="clearRegionCapture"
          @confirm-clip="confirmClipPlanet"
          @cancel-clip="clipPlanetPickerOpen = false; pendingClipPlanetSlug = ''"
        />
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import {
  analyzeVault,
  applyVaultTemplate,
  createDailyNote,
  createVaultFile,
  deleteVaultFile,
  downloadVaultZip,
  fetchVaultBacklinks,
  fetchVaultBookmarks,
  fetchVaultFile,
  fetchVaultGraph,
  fetchVaultMeta,
  fetchVaultOpenHint,
  fetchVaultTemplates,
  fetchVaultTree,
  migrateVaultNotes,
  previewVaultNote,
  saveVaultFile,
  searchVault,
  toggleVaultBookmark,
  type VaultBacklinks,
  type VaultFile,
  type VaultGraph,
  type VaultOpenHint,
  type VaultSearchHit,
  type VaultTreeNode,
} from '../../../api/vault';
import { useOrbitStore } from '../../../stores/orbit';
import { LzButton, LzSkeleton } from '../ui';
import VaultTreeList from '../VaultTreeList.vue';
import {
  pathMatchesSection,
  VAULT_SECTIONS,
  type VaultSectionId,
} from './sections';
import VaultConnectDialog from './VaultConnectDialog.vue';
import VaultEditor from './VaultEditor.vue';
import VaultInspector from './VaultInspector.vue';
import VaultNoteList from './VaultNoteList.vue';
import VaultSectionNav from './VaultSectionNav.vue';

const props = withDefaults(
  defineProps<{
    open: boolean;
    planetSlug?: string;
    galaxySlug?: string;
  }>(),
  { planetSlug: '', galaxySlug: '' },
);

const emit = defineEmits<{
  (e: 'close'): void;
}>();

const orbit = useOrbitStore();
const status = ref('');
const loading = ref(false);
const saving = ref(false);
const dirty = ref(false);
const section = ref<VaultSectionId>('recent');
const tree = ref<VaultTreeNode[]>([]);
const allHits = ref<VaultSearchHit[]>([]);
const activePath = ref('');
const file = ref<VaultFile | null>(null);
const draft = ref('');
const query = ref('');
const searchHits = ref<VaultSearchHit[]>([]);
const graphMode = ref<'local' | 'global'>('local');
const graphDepth = ref(2);
const graph = ref<VaultGraph | null>(null);
const backlinks = ref<VaultBacklinks | null>(null);
const openHint = ref<VaultOpenHint | null>(null);
const showConnect = ref(false);
const moreOpen = ref(false);
const templates = ref<Array<{ path: string; name: string }>>([]);
const bookmarks = ref<Array<{ path: string; title: string }>>([]);
const inspectorCollapsed = ref(false);
const cmdOpen = ref(false);
const cmdQuery = ref('');
const hover = ref<{ x: number; y: number; title: string; snippet: string } | null>(null);
const timelapseOn = ref(false);
const timelapseIdx = ref(0);
const noteCount = ref(0);
const linkCount = ref(0);
const metaName = ref('星轨知识库');
let timelapseTimer: number | null = null;
let autosaveTimer: number | null = null;
const inspectorRef = ref<InstanceType<typeof VaultInspector> | null>(null);

const isBookmarked = computed(() => bookmarks.value.some((b) => b.path === activePath.value));

const sectionCounts = computed(() => {
  const counts: Record<string, number> = {
    recent: allHits.value.length,
    bookmarks: bookmarks.value.length,
    all: allHits.value.length,
  };
  for (const s of VAULT_SECTIONS) {
    if (!s.folder) continue;
    counts[s.id] = allHits.value.filter((h) => pathMatchesSection(h.path, s)).length;
  }
  return counts;
});

const listItems = computed(() => {
  if (query.value.trim() && searchHits.value.length) return searchHits.value;
  if (section.value === 'recent') return allHits.value.slice(0, 40);
  if (section.value === 'bookmarks') {
    const set = new Set(bookmarks.value.map((b) => b.path));
    return allHits.value.filter((h) => set.has(h.path));
  }
  if (section.value === 'all') return allHits.value;
  const sec = VAULT_SECTIONS.find((s) => s.id === section.value);
  if (!sec?.folder) return allHits.value;
  return allHits.value.filter((h) => pathMatchesSection(h.path, sec));
});

const showTree = computed(() => section.value === 'all' && !query.value.trim());

const sectionEmptyHint = computed(() => {
  if (section.value === 'bookmarks') return '还没有收藏，打开笔记后点☆即可';
  if (section.value === 'clips') return '去星库划词或演武舱剪藏后会出现在这里';
  if (section.value === 'canvas') return '画布文件不在笔记列表中，点下方打开默认思维画布';
  return '这个分区还没有笔记';
});

const cmdItems = computed(() => {
  const q = cmdQuery.value.trim().toLowerCase();
  const all = [
    { id: 'save', label: '保存当前笔记', run: () => void save() },
    { id: 'new', label: '新建笔记', run: () => void createNote() },
    { id: 'daily', label: '打开今日日记', run: () => void onDaily() },
    { id: 'analyze', label: 'AI 刷新画像', run: () => void onAnalyze() },
    { id: 'export', label: '导出 Vault zip', run: () => void onExport() },
    { id: 'obsidian', label: '接入本地 Obsidian', run: () => { showConnect.value = true; } },
    { id: 'migrate', label: '导入旧笔记', run: () => void onMigrate() },
    ...templates.value.map((t) => ({
      id: `tpl-${t.path}`,
      label: `模板：${t.name}`,
      run: () => void applyTemplate(t.path),
    })),
  ];
  if (!q) return all;
  return all.filter((x) => x.label.toLowerCase().includes(q));
});

function firstFile(nodes: VaultTreeNode[]): string {
  for (const n of nodes) {
    if (n.type === 'file') return n.path;
    if (n.children?.length) {
      const f = firstFile(n.children);
      if (f) return f;
    }
  }
  return '';
}

function findPathEnding(nodes: VaultTreeNode[], suffix: string): string {
  for (const n of nodes) {
    if (n.type === 'file' && n.path.endsWith(suffix)) return n.path;
    if (n.children?.length) {
      const f = findPathEnding(n.children, suffix);
      if (f) return f;
    }
  }
  return '';
}

async function bootstrap() {
  loading.value = true;
  status.value = '';
  try {
    const [t, hint, tpls, bms, hits, meta, g] = await Promise.all([
      fetchVaultTree(),
      fetchVaultOpenHint(),
      fetchVaultTemplates(),
      fetchVaultBookmarks(),
      searchVault(''),
      fetchVaultMeta(),
      fetchVaultGraph({ mode: 'global', show_orphans: true }),
    ]);
    tree.value = t.tree || [];
    openHint.value = hint;
    templates.value = tpls || [];
    bookmarks.value = bms || [];
    allHits.value = hits || [];
    noteCount.value = hits?.length || 0;
    linkCount.value = g?.edges?.length || 0;
    metaName.value = meta.vault_name || hint.vault_name || '星轨知识库';
    const prefer =
      (props.planetSlug && findPathEnding(tree.value, `${props.planetSlug}.md`)) ||
      findPathEnding(tree.value, 'README.md') ||
      firstFile(tree.value);
    if (prefer) await openPath(prefer);
    else status.value = '知识库已就绪，可以从下方引导开始';
  } catch (e) {
    status.value = e instanceof Error ? e.message : '知识库加载失败';
  } finally {
    loading.value = false;
  }
}

async function openPath(path: string) {
  try {
    if (path.endsWith('.canvas')) {
      status.value = `画布 ${path}`;
      inspectorCollapsed.value = false;
      await nextTick();
      inspectorRef.value?.openCanvas?.();
      return;
    }
    const f = await fetchVaultFile(path);
    file.value = f;
    draft.value = f.content;
    activePath.value = path;
    dirty.value = false;
    await Promise.all([reloadGraph(), reloadBacklinks()]);
  } catch (e) {
    status.value = e instanceof Error ? e.message : '打开失败';
  }
}

function openDefaultCanvas() {
  inspectorCollapsed.value = false;
  void nextTick(() => {
    inspectorRef.value?.openCanvas?.();
    status.value = '已打开默认思维画布';
  });
}

async function reloadTree() {
  tree.value = (await fetchVaultTree()).tree || [];
  allHits.value = (await searchVault('')) || [];
  noteCount.value = allHits.value.length;
}

async function reloadGraph() {
  graph.value = await fetchVaultGraph({
    mode: graphMode.value,
    path: activePath.value || undefined,
    depth: graphDepth.value,
    show_orphans: true,
  });
  linkCount.value = graph.value?.edges?.length || linkCount.value;
  await nextTick();
  inspectorRef.value?.renderGraph?.();
}

async function reloadBacklinks() {
  if (!activePath.value) {
    backlinks.value = null;
    return;
  }
  backlinks.value = await fetchVaultBacklinks(activePath.value);
}

async function save() {
  if (!activePath.value) return;
  saving.value = true;
  try {
    file.value = await saveVaultFile(activePath.value, draft.value);
    draft.value = file.value.content;
    dirty.value = false;
    status.value = '已保存到云端知识库';
    await Promise.all([reloadTree(), reloadGraph(), reloadBacklinks()]);
  } catch (e) {
    status.value = e instanceof Error ? e.message : '保存失败';
  } finally {
    saving.value = false;
  }
}

function scheduleAutosave() {
  dirty.value = true;
  if (autosaveTimer) clearTimeout(autosaveTimer);
  autosaveTimer = window.setTimeout(() => {
    if (dirty.value && activePath.value) void save();
  }, 1500);
}

async function createNote() {
  const g = props.galaxySlug || orbit.currentGalaxy?.slug || 'misc';
  const p = props.planetSlug || orbit.selectedPlanet?.slug || '';
  const name = p || `笔记-${Date.now().toString(36)}`;
  const path = p ? `10-Planets/${g}/${name}.md` : `00-Inbox/${name}.md`;
  try {
    const created = await createVaultFile(
      path,
      `---\ntitle: ${name}\ngalaxy_slug: ${g}\nplanet_slug: ${p}\ntags: [note]\n---\n\n# ${name}\n\n`,
    );
    await reloadTree();
    section.value = p ? 'planets' : 'inbox';
    await openPath(created.path);
    status.value = `已新建 ${created.path}`;
  } catch (e) {
    status.value = e instanceof Error ? e.message : '新建失败';
  }
}

async function onDaily() {
  const f = await createDailyNote();
  await reloadTree();
  section.value = 'daily';
  await openPath(f.path);
  status.value = `日记 ${f.path}`;
}

async function applyTemplate(templatePath: string) {
  const g = props.galaxySlug || orbit.currentGalaxy?.slug || 'misc';
  const p = props.planetSlug || orbit.selectedPlanet?.slug || '';
  const title = p || templates.value.find((t) => t.path === templatePath)?.name || '未命名';
  const dest = p ? `10-Planets/${g}/${title}-tpl.md` : `00-Inbox/${title}-${Date.now().toString(36)}.md`;
  const created = await applyVaultTemplate({
    template_path: templatePath,
    dest_path: dest,
    vars: { title, galaxy_slug: g, planet_slug: p },
  });
  await reloadTree();
  await openPath(created.path);
  status.value = `已从模板创建 ${created.path}`;
  moreOpen.value = false;
}

async function onToggleBookmark() {
  if (!activePath.value) return;
  const res = await toggleVaultBookmark(activePath.value, file.value?.title || '');
  bookmarks.value = res.bookmarks || [];
  status.value = res.added ? '已加入书签' : '已取消书签';
}

async function removeCurrent() {
  if (!activePath.value || activePath.value === 'README.md') return;
  if (!confirm(`删除 ${activePath.value}？`)) return;
  await deleteVaultFile(activePath.value);
  activePath.value = '';
  file.value = null;
  draft.value = '';
  dirty.value = false;
  await reloadTree();
  status.value = '已删除';
}

async function onSearch() {
  const q = query.value.trim();
  if (!q) {
    searchHits.value = [];
    return;
  }
  searchHits.value = await searchVault(q);
}

async function onMigrate() {
  const r = await migrateVaultNotes();
  await reloadTree();
  status.value = `已导入旧笔记 ${r.imported} 篇（跳过 ${r.skipped}）`;
  moreOpen.value = false;
}

async function onAnalyze() {
  status.value = 'AI 正在分析知识库…';
  moreOpen.value = false;
  const r = await analyzeVault();
  status.value = r.profile_refreshed
    ? `画像已更新：${r.summary} · 可到「画像」查看证据链`
    : `已记录学情：${r.summary}（${r.status === 'already_fresh' ? '已是最新' : '累积事件后会自动刷新'}）`;
  await reloadTree();
}

async function onExport() {
  await downloadVaultZip();
  status.value = '已下载 Vault zip';
  moreOpen.value = false;
}

function insertWiki() {
  const name = window.prompt('双链目标笔记名（不含 .md）');
  if (!name) return;
  draft.value += `[[${name.trim()}]]`;
  scheduleAutosave();
}

async function onEditorMouseMove(ev: MouseEvent) {
  const ta = ev.target as HTMLTextAreaElement;
  if (!ta || typeof ta.selectionStart !== 'number') return;
  const pos = ta.selectionStart;
  const slice = draft.value.slice(Math.max(0, pos - 40), pos + 40);
  const m = slice.match(/\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]/);
  if (!m) {
    hover.value = null;
    return;
  }
  const target = m[1].trim();
  try {
    const prev = await previewVaultNote(target);
    hover.value = {
      x: ev.clientX + 12,
      y: ev.clientY + 12,
      title: prev.title,
      snippet: prev.snippet,
    };
  } catch {
    hover.value = null;
  }
}

function toggleTimelapse() {
  if (timelapseOn.value) {
    stopTimelapse();
    return;
  }
  if (!graph.value?.nodes?.length) return;
  const times = graph.value.nodes
    .map((n) => n.created_at || '')
    .filter(Boolean)
    .sort();
  if (!times.length) {
    status.value = '暂无创建时间，无法播放时间线';
    return;
  }
  timelapseOn.value = true;
  timelapseIdx.value = 0;
  status.value = '图谱时间线播放中…';
  timelapseTimer = window.setInterval(() => {
    if (!times.length) return;
    const t = times[Math.min(timelapseIdx.value, times.length - 1)];
    inspectorRef.value?.renderGraph?.(t);
    timelapseIdx.value += 1;
    if (timelapseIdx.value >= times.length) {
      stopTimelapse();
      status.value = '时间线播放结束';
      inspectorRef.value?.renderGraph?.();
    }
  }, 700);
}

function stopTimelapse() {
  timelapseOn.value = false;
  if (timelapseTimer) {
    clearInterval(timelapseTimer);
    timelapseTimer = null;
  }
}

function onKeydown(ev: KeyboardEvent) {
  if (!props.open) return;
  if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'k') {
    ev.preventDefault();
    cmdOpen.value = !cmdOpen.value;
    cmdQuery.value = '';
  }
  if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 's') {
    ev.preventDefault();
    void save();
  }
  if (ev.key === 'Escape') {
    if (cmdOpen.value) {
      cmdOpen.value = false;
      return;
    }
    if (showConnect.value) {
      showConnect.value = false;
      return;
    }
    emit('close');
  }
}

function runCmd(item: { run: () => void }) {
  cmdOpen.value = false;
  item.run();
}

watch(graphMode, () => void reloadGraph());
watch(graphDepth, () => void reloadGraph());
watch(section, (id) => {
  if (id === 'canvas') openDefaultCanvas();
});
watch(
  () => props.open,
  (v) => {
    if (v) void bootstrap();
    else {
      stopTimelapse();
      if (autosaveTimer) clearTimeout(autosaveTimer);
    }
  },
);
watch(
  () => [props.planetSlug, props.galaxySlug, props.open] as const,
  ([, , open]) => {
    if (open) void bootstrap();
  },
);

onMounted(() => {
  window.addEventListener('keydown', onKeydown);
  if (props.open) void bootstrap();
});
onBeforeUnmount(() => {
  stopTimelapse();
  if (autosaveTimer) clearTimeout(autosaveTimer);
  window.removeEventListener('keydown', onKeydown);
});
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="lz-accent-emerald fixed inset-0 z-[110] flex flex-col bg-slate-950/95 text-slate-100 backdrop-blur-xl"
      role="dialog"
      aria-modal="true"
      aria-label="星轨知识库"
    >
      <!-- 顶栏 -->
      <header class="flex flex-wrap items-center gap-3 border-b border-[var(--border-soft)] bg-gradient-to-r from-[rgb(var(--lz-accent)/0.1)] via-transparent to-transparent px-4 py-3">
        <div class="min-w-0">
          <p class="lz-caption lz-accent-text uppercase tracking-[0.28em]">Star Vault</p>
          <h2 class="lz-title truncate">{{ metaName }}</h2>
          <p class="lz-caption">
            {{ noteCount }} 篇笔记 · {{ linkCount }} 条双链
          </p>
        </div>

        <div class="mx-auto flex w-full max-w-xl items-center gap-2 sm:w-auto sm:flex-1">
          <input
            v-model="query"
            type="search"
            placeholder="搜索标题、标签或正文…（Ctrl+K 命令面板）"
            class="lz-input h-[34px] px-3"
            @keyup.enter="onSearch"
            @input="onSearch"
          />
        </div>

        <div class="ml-auto flex flex-wrap items-center gap-1.5">
          <LzButton variant="primary" size="sm" @click="createNote">新建笔记</LzButton>
          <LzButton variant="ghost" size="sm" @click="onDaily">今日日记</LzButton>
          <button
            type="button"
            class="rounded-[var(--radius-ctl)] border px-3 py-1.5 text-xs transition disabled:cursor-not-allowed disabled:opacity-45"
            :class="isBookmarked
              ? 'border-amber-400/40 bg-amber-500/20 text-amber-50'
              : 'border-[var(--border-soft)] bg-white/5 text-slate-300 hover:bg-white/10'"
            :disabled="!activePath"
            @click="onToggleBookmark"
          >
            {{ isBookmarked ? '★ 已收藏' : '☆ 收藏' }}
          </button>
          <div class="relative">
            <LzButton variant="ghost" size="sm" @click="moreOpen = !moreOpen">更多 ▾</LzButton>
            <div
              v-if="moreOpen"
              class="absolute right-0 z-20 mt-1 w-48 overflow-hidden rounded-[var(--radius-card)] border border-[var(--border-strong)] bg-slate-950 shadow-2xl"
            >
              <button
                v-for="t in templates"
                :key="t.path"
                type="button"
                class="block w-full px-3 py-2 text-left text-xs hover:bg-[rgb(var(--lz-accent)/0.15)]"
                @click="applyTemplate(t.path)"
              >
                模板：{{ t.name }}
              </button>
              <button type="button" class="block w-full px-3 py-2 text-left text-xs hover:bg-[rgb(var(--lz-accent)/0.15)]" @click="onExport">
                导出 zip
              </button>
              <button
                type="button"
                class="block w-full px-3 py-2 text-left text-xs hover:bg-[rgb(var(--lz-accent)/0.15)]"
                @click="moreOpen = false; showConnect = true"
              >
                接入 Obsidian
              </button>
              <button type="button" class="block w-full px-3 py-2 text-left text-xs hover:bg-[rgb(var(--lz-accent)/0.15)]" @click="onAnalyze">
                AI 刷新画像
              </button>
              <button type="button" class="block w-full px-3 py-2 text-left text-xs hover:bg-[rgb(var(--lz-accent)/0.15)]" @click="onMigrate">
                导入旧笔记
              </button>
              <button
                type="button"
                class="block w-full px-3 py-2 text-left text-xs hover:bg-[rgb(var(--lz-accent)/0.15)]"
                @click="cmdOpen = true; moreOpen = false"
              >
                命令面板 ⌘K
              </button>
            </div>
          </div>
          <LzButton variant="ghost" size="sm" @click="emit('close')">关闭</LzButton>
        </div>
      </header>

      <!-- 主体 -->
      <div class="flex min-h-0 flex-1 gap-0">
        <aside class="w-[220px] shrink-0 border-r border-[var(--border-soft)] bg-slate-950/60">
          <VaultSectionNav v-model="section" :counts="sectionCounts" />
        </aside>

        <aside class="flex w-[300px] shrink-0 flex-col border-r border-[var(--border-soft)] bg-slate-950/40">
          <div v-if="showTree" class="min-h-0 flex-1 overflow-auto p-2 text-[11px]">
            <LzSkeleton v-if="loading" preset="list" :rows="6" class="p-2" />
            <VaultTreeList v-else :nodes="tree" :active="activePath" @open="openPath" />
          </div>
          <VaultNoteList
            v-else
            :items="listItems"
            :active-path="activePath"
            :loading="loading"
            :empty-hint="sectionEmptyHint"
            @open="openPath"
          >
            <template #empty>
              <div v-if="section === 'canvas'" class="mt-2 grid w-full max-w-xs gap-2">
                <LzButton variant="soft" size="sm" block @click="openDefaultCanvas">
                  打开默认思维画布
                </LzButton>
              </div>
              <div v-else-if="section === 'clips'" class="mt-2 max-w-xs lz-caption leading-4">
                在星库 PDF 划词/画笔后点「划词剪藏」，或在演武舱点「划词剪藏」。
              </div>
              <div v-else-if="!allHits.length" class="mt-2 grid w-full max-w-xs gap-2">
                <LzButton variant="soft" size="sm" block @click="createNote">
                  从当前行星开始记笔记
                </LzButton>
                <LzButton variant="ghost" size="sm" block @click="onDaily">
                  写今日学习日记
                </LzButton>
                <LzButton v-if="templates[0]" variant="ghost" size="sm" block @click="applyTemplate(templates[0].path)">
                  用模板：{{ templates[0].name }}
                </LzButton>
              </div>
            </template>
          </VaultNoteList>
        </aside>

        <div class="flex min-w-0 flex-1 flex-col gap-2 p-3">
          <VaultEditor
            :path="activePath"
            :title="file?.title || ''"
            :model-value="draft"
            :saving="saving"
            :dirty="dirty"
            :updated-at="file?.updated_at"
            @update:model-value="(v) => { draft = v; scheduleAutosave(); }"
            @save="save"
            @delete="removeCurrent"
            @insert-wiki="insertWiki"
            @mousemove="onEditorMouseMove"
            @mouseleave="hover = null"
          />
          <p v-if="status" class="text-[11px] text-emerald-300/90">{{ status }}</p>
        </div>

        <div class="flex h-full min-h-0 shrink-0 border-l border-[var(--border-soft)] p-2">
          <VaultInspector
            ref="inspectorRef"
            v-model:collapsed="inspectorCollapsed"
            v-model:graph-mode="graphMode"
            v-model:graph-depth="graphDepth"
            :graph="graph"
            :backlinks="backlinks"
            :timelapse-on="timelapseOn"
            @toggle-timelapse="toggleTimelapse"
            @open-file="openPath"
            @status="(m) => (status = m)"
          />
        </div>
      </div>

      <!-- wikilink hover -->
      <div
        v-if="hover"
        class="pointer-events-none fixed z-[120] max-w-xs rounded-[var(--radius-card)] border border-[var(--border-strong)] bg-slate-950/95 p-3 text-[11px] shadow-2xl"
        :style="{ left: hover.x + 'px', top: hover.y + 'px' }"
      >
        <p class="lz-subtitle">{{ hover.title }}</p>
        <pre class="mt-1 whitespace-pre-wrap lz-caption">{{ hover.snippet }}</pre>
      </div>

      <!-- command palette -->
      <div
        v-if="cmdOpen"
        class="fixed inset-0 z-[125] flex items-start justify-center bg-black/50 pt-[12vh]"
        @click.self="cmdOpen = false"
      >
        <div class="w-full max-w-lg overflow-hidden rounded-[var(--radius-panel)] border border-[var(--border-strong)] bg-slate-950 shadow-2xl">
          <input
            v-model="cmdQuery"
            autofocus
            placeholder="命令面板…（日记 / 模板 / AI / Obsidian）"
            class="w-full border-b border-[var(--border-soft)] bg-transparent px-4 py-3 text-sm outline-none"
          />
          <div class="max-h-72 overflow-auto p-1">
            <button
              v-for="item in cmdItems"
              :key="item.id"
              type="button"
              class="block w-full rounded-[var(--radius-ctl)] px-3 py-2 text-left text-sm text-slate-200 hover:bg-[rgb(var(--lz-accent)/0.15)]"
              @click="runCmd(item)"
            >
              {{ item.label }}
            </button>
          </div>
        </div>
      </div>

      <VaultConnectDialog
        :open="showConnect"
        :hint="openHint"
        @close="showConnect = false"
        @updated="(h) => { openHint = h; metaName = h.vault_name; }"
        @status="(m) => (status = m)"
      />
    </div>
  </Teleport>
</template>

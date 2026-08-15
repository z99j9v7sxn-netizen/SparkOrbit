<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import {
  createNote,
  createForumPost,
  deleteNote,
  fetchLessonResources,
  fetchNotes,
  updateNote,
  uploadNoteAttachment,
  type LessonResourceItem,
  type NoteItem,
} from '../../api/zone';
import { aiSummaryNote } from '../../api/challengeSprint';
import { useOrbitStore } from '../../stores/orbit';

const props = withDefaults(
  defineProps<{
    /** planet=小笔记 · galaxy=中笔记 · global=大笔记；可被内部切换覆盖 */
    scope?: 'planet' | 'galaxy' | 'global';
    compact?: boolean;
    allowScopeSwitch?: boolean;
  }>(),
  { scope: 'global', compact: false, allowScopeSwitch: true },
);

const emit = defineEmits<{
  (e: 'jump-planet', slug: string): void;
}>();

const orbit = useOrbitStore();
const activeScope = ref<'planet' | 'galaxy' | 'global'>(props.scope);
const tab = ref<'notes' | 'resources'>('notes');
const notes = ref<NoteItem[]>([]);
const resources = ref<LessonResourceItem[]>([]);
const title = ref('');
const content = ref('');
const attachmentUrl = ref('');
const uploading = ref(false);
const loading = ref(false);
const aiBusy = ref(false);
const tip = ref('');
const search = ref('');
const filterPlanet = ref('');
const editingId = ref<string | null>(null);
const editTitle = ref('');
const editContent = ref('');
const saveTimer = ref<number | null>(null);

const planetSlug = computed(() => orbit.selectedPlanet?.slug ?? '');
const planetLabel = computed(() => orbit.selectedPlanet?.name ?? '未选行星');
const galaxySlug = computed(() => orbit.currentGalaxy?.slug ?? '');
const galaxyLabel = computed(() => orbit.currentGalaxy?.name ?? '当前星系');

const scopeLabel = computed(() => {
  if (activeScope.value === 'planet') return `小笔记本 · ${planetLabel.value}`;
  if (activeScope.value === 'galaxy') return `中笔记本 · ${galaxyLabel.value}`;
  return '大笔记本 · 全部星系';
});

const scopeHint = computed(() => {
  if (activeScope.value === 'planet') return '仅当前行星笔记，互不可见其它行星';
  if (activeScope.value === 'galaxy') return '汇总本星系下各行星笔记，可按行星筛选';
  return '跨星系全局笔记中心，支持全文检索与跳转';
});

const grouped = computed(() => {
  const map = new Map<string, NoteItem[]>();
  for (const n of notes.value) {
    const key =
      activeScope.value === 'global'
        ? n.galaxy_slug || '未归类星系'
        : n.planet_slug || '通用';
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(n);
  }
  return [...map.entries()];
});

const planetOptions = computed(() => {
  const set = new Set(notes.value.map((n) => n.planet_slug).filter(Boolean));
  return [...set];
});

async function loadNotes() {
  loading.value = true;
  tip.value = '';
  try {
    if (activeScope.value === 'planet') {
      if (!planetSlug.value) {
        notes.value = [];
        return;
      }
      notes.value = await fetchNotes({ planet_slug: planetSlug.value, q: search.value });
    } else if (activeScope.value === 'galaxy') {
      if (!galaxySlug.value) {
        notes.value = [];
        return;
      }
      const all = await fetchNotes({ galaxy_slug: galaxySlug.value, q: search.value });
      notes.value = filterPlanet.value
        ? all.filter((n) => n.planet_slug === filterPlanet.value)
        : all;
    } else {
      notes.value = await fetchNotes({ q: search.value });
    }
  } catch {
    notes.value = [];
  } finally {
    loading.value = false;
  }
}

async function loadResources() {
  try {
    resources.value = await fetchLessonResources(galaxySlug.value);
  } catch {
    resources.value = [];
  }
}

async function saveNote() {
  if (!content.value.trim()) return;
  await createNote({
    title: title.value.trim() || '学习笔记',
    content: content.value.trim(),
    planet_slug: planetSlug.value || filterPlanet.value,
    galaxy_slug: galaxySlug.value,
    attachment_url: attachmentUrl.value,
  });
  title.value = '';
  content.value = '';
  attachmentUrl.value = '';
  tip.value = '已保存（持久化）';
  await loadNotes();
}

function startEdit(item: NoteItem) {
  editingId.value = item.id;
  editTitle.value = item.title;
  editContent.value = item.content;
}

function scheduleSave() {
  if (!editingId.value) return;
  if (saveTimer.value) window.clearTimeout(saveTimer.value);
  saveTimer.value = window.setTimeout(() => void persistEdit(), 600);
}

async function persistEdit() {
  if (!editingId.value) return;
  try {
    const updated = await updateNote(editingId.value, {
      title: editTitle.value,
      content: editContent.value,
    });
    const idx = notes.value.findIndex((n) => n.id === updated.id);
    if (idx >= 0) notes.value[idx] = updated;
    tip.value = '已自动保存修改';
  } catch (e) {
    tip.value = e instanceof Error ? e.message : '保存失败';
  }
}

async function finishEdit() {
  await persistEdit();
  editingId.value = null;
}

async function removeNote(id: string) {
  await deleteNote(id);
  if (editingId.value === id) editingId.value = null;
  await loadNotes();
}

async function onAttachmentPick(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0];
  if (!file) return;
  uploading.value = true;
  try {
    const res = await uploadNoteAttachment(file);
    attachmentUrl.value = res.url;
  } finally {
    uploading.value = false;
  }
}

async function publishToForum(item: NoteItem) {
  const t = (item.title || '学习笔记').trim();
  const b = (item.content || '').trim();
  if (!b) return;
  try {
    await createForumPost({
      title: t,
      body: b,
      kind: item.attachment_url ? 'file' : 'note',
      file_url: item.attachment_url || '',
    });
    tip.value = '已发布到资料站';
  } catch (e) {
    tip.value = String(e);
  }
}

async function genAiSummary() {
  if (!planetSlug.value) {
    tip.value = '请先在星图中选择一颗行星';
    return;
  }
  aiBusy.value = true;
  tip.value = '';
  try {
    await aiSummaryNote(planetSlug.value);
    tip.value = '已生成随堂笔记（计入学闸，可后续编辑）';
    await loadNotes();
  } catch (e) {
    tip.value = String(e);
  } finally {
    aiBusy.value = false;
  }
}

function switchTab(next: 'notes' | 'resources') {
  tab.value = next;
  if (next === 'resources') void loadResources();
}

function jump(slug: string) {
  if (!slug) return;
  emit('jump-planet', slug);
}

type NoteBlock = {
  kind?: string;
  text?: string;
  content?: string;
  quote?: string;
  title?: string;
  planet_slug?: string;
  page?: number;
  [key: string]: unknown;
};

function asBlock(b: unknown): NoteBlock {
  return b && typeof b === 'object' ? (b as NoteBlock) : {};
}

function blockKindLabel(b: unknown) {
  const kind = String(asBlock(b).kind || 'note');
  const map: Record<string, string> = {
    viz_clip: '演武剪藏',
    quote: '划词摘录',
    feynman: '费曼讲解',
    code_clip: '代码剪藏',
    ai_summary: 'AI 随堂',
    media_clip: '资源剪藏',
  };
  return map[kind] || kind;
}

function blockCardClass(b: unknown) {
  const kind = String(asBlock(b).kind || '');
  if (kind === 'viz_clip') return 'border-lime-400/25 bg-lime-500/10';
  if (kind === 'quote') return 'border-violet-400/25 bg-violet-500/10';
  if (kind === 'feynman') return 'border-fuchsia-400/25 bg-fuchsia-500/10';
  if (kind === 'code_clip') return 'border-emerald-400/25 bg-emerald-500/10';
  return 'border-white/10 bg-white/[0.04]';
}

function blockBody(b: unknown) {
  const x = asBlock(b);
  return String(x.text || x.content || x.quote || x.title || JSON.stringify(x)).slice(0, 600);
}

function blockMeta(b: unknown) {
  const x = asBlock(b);
  const bits = [
    x.planet_slug ? `行星 ${x.planet_slug}` : '',
    typeof x.page === 'number' && x.page > 0 ? `p.${x.page}` : '',
  ].filter(Boolean);
  return bits.join(' · ');
}

watch(
  () => props.scope,
  (s) => {
    activeScope.value = s;
  },
);
watch([activeScope, planetSlug, galaxySlug], () => void loadNotes());
watch(filterPlanet, () => void loadNotes());

onMounted(() => {
  activeScope.value = props.scope;
  void loadNotes();
});
</script>

<template>
  <div class="space-y-4" :class="compact ? 'text-sm' : ''">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div>
        <p class="text-xs uppercase tracking-[0.35em] text-sky-300/70">Notebook</p>
        <h3 class="text-lg font-semibold text-white">{{ scopeLabel }}</h3>
        <p class="text-[11px] text-slate-400">{{ scopeHint }}</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <div v-if="allowScopeSwitch" class="inline-flex rounded-xl border border-white/15 bg-black/40 p-0.5 text-[11px]">
          <button type="button" class="rounded-lg px-2.5 py-1 font-semibold" :class="activeScope === 'planet' ? 'bg-sky-500/25 text-sky-50' : 'text-slate-400'" @click="activeScope = 'planet'">小</button>
          <button type="button" class="rounded-lg px-2.5 py-1 font-semibold" :class="activeScope === 'galaxy' ? 'bg-violet-500/25 text-violet-50' : 'text-slate-400'" @click="activeScope = 'galaxy'">中</button>
          <button type="button" class="rounded-lg px-2.5 py-1 font-semibold" :class="activeScope === 'global' ? 'bg-amber-500/25 text-amber-50' : 'text-slate-400'" @click="activeScope = 'global'">大</button>
        </div>
        <template v-if="!compact">
          <button
            class="rounded-full border px-3 py-1.5 text-xs font-semibold"
            :class="tab === 'notes' ? 'border-sky-400/50 bg-sky-400/15 text-sky-50' : 'border-white/10 text-slate-400'"
            @click="switchTab('notes')"
          >我的笔记</button>
          <button
            class="rounded-full border px-3 py-1.5 text-xs font-semibold"
            :class="tab === 'resources' ? 'border-violet-400/50 bg-violet-400/15 text-violet-50' : 'border-white/10 text-slate-400'"
            @click="switchTab('resources')"
          >教师资料</button>
        </template>
      </div>
    </div>

    <div v-if="tab === 'notes'" class="space-y-3">
      <div class="flex flex-wrap gap-2">
        <input
          v-model="search"
          placeholder="搜索标题 / 正文 / 行星…"
          class="cosmic-input min-w-[180px] flex-1 rounded-xl px-3 py-2 text-sm text-slate-200"
          @keydown.enter.prevent="loadNotes"
        />
        <select
          v-if="activeScope === 'galaxy' || activeScope === 'global'"
          v-model="filterPlanet"
          class="rounded-xl border border-white/15 bg-black/40 px-2 py-2 text-xs text-slate-200"
          @change="loadNotes"
        >
          <option value="">全部行星</option>
          <option v-for="p in planetOptions" :key="p" :value="p">{{ p }}</option>
        </select>
        <button class="cosmic-primary-btn rounded-xl px-3 py-2 text-xs" @click="loadNotes">搜索</button>
      </div>

      <template v-if="activeScope === 'planet' || planetSlug">
        <input
          v-model="title"
          placeholder="笔记标题（可选）"
          class="cosmic-input w-full rounded-xl px-4 py-2 text-sm text-slate-200"
        />
        <textarea
          v-model="content"
          rows="4"
          placeholder="写下本知识点的心得…支持后续反复修改"
          class="cosmic-input w-full rounded-2xl px-4 py-3 text-sm text-slate-200"
        />
        <div class="flex flex-wrap items-center gap-2">
          <label class="cursor-pointer rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs text-slate-200 hover:bg-white/10">
            {{ uploading ? '上传中…' : '添加附件' }}
            <input type="file" class="hidden" @change="onAttachmentPick" />
          </label>
          <button class="cosmic-primary-btn ml-auto rounded-xl px-4 py-2 text-sm" @click="saveNote">保存笔记</button>
          <button
            class="rounded-xl border border-fuchsia-400/40 bg-fuchsia-500/15 px-4 py-2 text-sm font-semibold text-fuchsia-50"
            :disabled="aiBusy"
            @click="genAiSummary"
          >{{ aiBusy ? '生成中…' : 'AI 随堂笔记' }}</button>
        </div>
      </template>
      <p v-else class="text-xs text-amber-200/80">选择一颗行星后可新建；中/大笔记本可浏览与编辑已有内容。</p>

      <p v-if="tip" class="text-xs text-emerald-300">{{ tip }}</p>
      <p v-if="loading" class="text-xs text-slate-500">加载中…</p>

      <div v-else class="max-h-[420px] space-y-3 overflow-auto pr-1">
        <section v-for="[group, items] in grouped" :key="group" class="space-y-2">
          <button
            v-if="activeScope !== 'planet'"
            type="button"
            class="sticky top-0 z-[1] w-full rounded-lg border border-white/10 bg-slate-950/90 px-2 py-1 text-left text-[11px] font-semibold tracking-wide text-sky-200/90 backdrop-blur"
            @click="jump(items[0]?.planet_slug || '')"
          >
            {{ group }} · {{ items.length }} 条
            <span v-if="items[0]?.planet_slug" class="ml-2 font-normal text-slate-500">点击跳转行星</span>
          </button>
          <article
            v-for="item in items"
            :key="item.id"
            class="rounded-xl border border-white/10 bg-white/[0.03] p-3"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-white">{{ item.title }}</p>
                <p class="mt-1 text-[11px] text-slate-500">
                  {{ item.updated_at.slice(0, 16) }}
                  · {{ item.galaxy_slug || '—' }} / {{ item.planet_slug || '通用' }}
                  · {{ item.source || 'manual' }}
                </p>
              </div>
              <div class="flex shrink-0 gap-2">
                <button
                  v-if="item.planet_slug && activeScope !== 'planet'"
                  class="text-[11px] text-sky-300 hover:underline"
                  @click="jump(item.planet_slug)"
                >跳转</button>
                <button class="text-[11px] text-amber-200 hover:underline" @click="startEdit(item)">编辑</button>
                <button class="text-[11px] text-sky-300 hover:underline" @click="publishToForum(item)">发布到资料站</button>
                <button class="text-[11px] text-rose-300 hover:underline" @click="removeNote(item.id)">删除</button>
              </div>
            </div>

            <div v-if="editingId === item.id" class="mt-2 space-y-2">
              <input
                v-model="editTitle"
                class="cosmic-input w-full rounded-lg px-3 py-1.5 text-sm"
                @input="scheduleSave"
              />
              <textarea
                v-model="editContent"
                rows="6"
                class="cosmic-input w-full rounded-xl px-3 py-2 text-sm leading-6"
                @input="scheduleSave"
              />
              <button class="rounded-lg border border-emerald-400/40 px-3 py-1 text-xs text-emerald-100" @click="finishEdit">完成编辑</button>
            </div>
            <p v-else class="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">{{ item.content }}</p>

            <div v-if="item.blocks_json?.length" class="mt-3 space-y-2">
              <article
                v-for="(b, i) in item.blocks_json"
                :key="i"
                class="rounded-xl border px-3 py-2 text-xs leading-5"
                :class="blockCardClass(b)"
              >
                <p class="text-[10px] font-semibold uppercase tracking-wider opacity-80">{{ blockKindLabel(b) }}</p>
                <p class="mt-1 whitespace-pre-wrap text-slate-200">{{ blockBody(b) }}</p>
                <p v-if="blockMeta(b)" class="mt-1 text-[10px] text-slate-500">{{ blockMeta(b) }}</p>
              </article>
            </div>
            <a v-if="item.attachment_url" :href="item.attachment_url" target="_blank" class="mt-2 inline-block text-xs text-sky-300 hover:underline">查看附件</a>
          </article>
        </section>
        <p v-if="!notes.length" class="text-sm text-slate-500">还没有笔记。学完演武可一键剪藏，或在此新建。</p>
      </div>
    </div>

    <div v-else class="max-h-96 space-y-2 overflow-auto pr-1">
      <article
        v-for="item in resources"
        :key="item.id"
        class="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3"
      >
        <div>
          <p class="text-sm text-white">{{ item.title }}</p>
          <p class="text-[11px] text-slate-500">{{ item.created_at.slice(0, 16) }} · {{ item.galaxy_slug || '全星系' }}</p>
        </div>
        <a :href="item.file_url" target="_blank" class="rounded-lg border border-violet-400/30 px-3 py-1 text-xs text-violet-100 hover:bg-violet-400/10">下载</a>
      </article>
      <p v-if="!resources.length" class="text-sm text-slate-500">老师尚未上传本星系资料。</p>
    </div>
  </div>
</template>

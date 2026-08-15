<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import {
  createForumPost,
  fetchForumAttachable,
  fetchForumPosts,
  likeForumPost,
  promoteForumPost,
  uploadNoteAttachment,
  type ForumAttachableItem,
  type ForumPostItem,
} from '../../api/zone';
import { fetchVaultFile } from '../../api/vault';
import { useAuthStore } from '../../stores/auth';

type KindFilter = 'all' | 'note' | 'link' | 'file';
type FileSource = 'local' | 'vault' | 'workshop' | 'video';

const auth = useAuthStore();
const items = ref<ForumPostItem[]>([]);
const title = ref('');
const body = ref('');
const kind = ref<'note' | 'link' | 'file'>('note');
const fileUrl = ref('');
const fileName = ref('');
const sourceType = ref('');
const sourceId = ref('');
const fileSource = ref<FileSource>('local');
const loading = ref(false);
const uploading = ref(false);
const tip = ref('');
const tipError = ref(false);
const composerOpen = ref(false);
const query = ref('');
const filter = ref<KindFilter>('all');
const expandedId = ref<string | null>(null);
const pickerOpen = ref(false);
const attachable = ref<ForumAttachableItem[]>([]);
const attachLoading = ref(false);

const isTeacher = computed(
  () => auth.user?.role === 'teacher' || auth.user?.role === 'admin',
);

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase();
  return items.value.filter((item) => {
    if (filter.value !== 'all' && item.kind !== filter.value) return false;
    if (!q) return true;
    return (
      item.title.toLowerCase().includes(q) ||
      item.body.toLowerCase().includes(q) ||
      item.author_name.toLowerCase().includes(q)
    );
  });
});

const pickerItems = computed(() => {
  const want =
    fileSource.value === 'vault'
      ? 'vault'
      : fileSource.value === 'video'
        ? 'video'
        : 'workshop';
  return attachable.value.filter((a) => a.source_type === want);
});

async function load() {
  items.value = await fetchForumPosts().catch(() => []);
}

async function loadAttachable() {
  attachLoading.value = true;
  try {
    const res = await fetchForumAttachable();
    attachable.value = res.items || [];
  } catch {
    attachable.value = [];
  } finally {
    attachLoading.value = false;
  }
}

async function publish() {
  if (!title.value.trim() || !body.value.trim()) return;
  if (kind.value === 'link' && !fileUrl.value.trim()) {
    tip.value = '请填写链接地址';
    tipError.value = true;
    return;
  }
  if (kind.value === 'file' && !fileUrl.value.trim() && !body.value.trim()) {
    tip.value = '请先选择本地文件、知识库、工坊文档或视频';
    tipError.value = true;
    return;
  }
  if (kind.value === 'file' && fileSource.value !== 'local' && !fileUrl.value.trim() && kind.value === 'file') {
    // 无 URL 的文档类：降为笔记发布正文快照
  }
  loading.value = true;
  tip.value = '';
  tipError.value = false;
  try {
    let publishKind = kind.value;
    let publishUrl = kind.value === 'note' ? '' : fileUrl.value.trim();
    if (publishKind === 'file' && !publishUrl) {
      publishKind = 'note';
    }
    await createForumPost({
      title: title.value.trim(),
      body: body.value.trim(),
      kind: publishKind,
      file_url: publishUrl,
      source_type: sourceType.value || (kind.value === 'file' ? fileSource.value : ''),
      source_id: sourceId.value,
    });
    title.value = '';
    body.value = '';
    fileUrl.value = '';
    fileName.value = '';
    sourceType.value = '';
    sourceId.value = '';
    kind.value = 'note';
    fileSource.value = 'local';
    composerOpen.value = false;
    pickerOpen.value = false;
    tip.value = '已发布到资料站';
    tipError.value = false;
    await load();
  } catch (err) {
    tip.value = err instanceof Error ? err.message : '发布失败';
    tipError.value = true;
  } finally {
    loading.value = false;
  }
}

async function onFilePick(ev: Event) {
  const input = ev.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  uploading.value = true;
  tip.value = '';
  tipError.value = false;
  try {
    const res = await uploadNoteAttachment(file);
    fileUrl.value = res.url;
    fileName.value = file.name;
    sourceType.value = 'local';
    sourceId.value = '';
    tip.value = `已上传：${file.name}`;
    tipError.value = false;
  } catch (err) {
    tip.value = err instanceof Error ? err.message : '上传失败';
    tipError.value = true;
  } finally {
    uploading.value = false;
    input.value = '';
  }
}

async function openPicker(src: FileSource) {
  fileSource.value = src;
  if (src === 'local') {
    pickerOpen.value = false;
    return;
  }
  pickerOpen.value = true;
  if (!attachable.value.length) await loadAttachable();
}

async function pickAttachable(item: ForumAttachableItem) {
  sourceType.value = item.source_type;
  sourceId.value = item.id;
  fileName.value = item.title;
  kind.value = (item.suggested_kind as 'note' | 'file') || 'file';
  if (!title.value.trim()) title.value = item.title;

  if (item.source_type === 'vault') {
    try {
      const f = await fetchVaultFile(item.id);
      body.value = (f.content || item.content_preview || body.value || item.title).slice(0, 8000);
      fileUrl.value = '';
      kind.value = 'note';
      tip.value = `已选取知识库：${item.title}`;
    } catch {
      body.value = item.content_preview || item.subtitle || item.title;
      tip.value = `已选取知识库（预览）：${item.title}`;
    }
  } else if (item.source_type === 'video') {
    fileUrl.value = item.file_url;
    body.value =
      body.value.trim() ||
      item.content_preview ||
      `账号生成视频：${item.title}${item.subtitle ? `（${item.subtitle}）` : ''}`;
    kind.value = 'file';
    tip.value = `已选取视频：${item.title}`;
  } else {
    fileUrl.value = item.file_url || '';
    body.value =
      body.value.trim() ||
      item.content_preview ||
      `来自资源工坊：${item.title}\n${item.subtitle}`;
    kind.value = item.file_url ? 'file' : 'note';
    tip.value = `已选取工坊：${item.title}`;
  }
  tipError.value = false;
  pickerOpen.value = false;
}

async function like(id: string) {
  await likeForumPost(id);
  await load();
}

async function promote(post: ForumPostItem) {
  if (post.promoted_asset_id) return;
  if (!window.confirm(`收录「${post.title}」到星库？`)) return;
  try {
    await promoteForumPost(post.id);
    tip.value = '已收录至星库';
    tipError.value = false;
    await load();
  } catch (err) {
    tip.value = err instanceof Error ? err.message : '收录失败';
    tipError.value = true;
  }
}

function kindLabel(k: string): string {
  if (k === 'link') return '链接';
  if (k === 'file') return '文件';
  return '笔记';
}

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id;
}

function openComposer() {
  composerOpen.value = true;
}

function formatTime(iso: string): string {
  if (!iso) return '';
  return iso.slice(0, 16).replace('T', ' ');
}

watch(kind, (k) => {
  if (k !== 'file') pickerOpen.value = false;
});

onMounted(load);
</script>

<template>
  <div class="flex h-full min-h-0 flex-col gap-4">
    <div class="flex flex-wrap items-center gap-2">
      <input
        v-model="query"
        class="cosmic-input min-w-0 flex-1 rounded-xl px-3 py-2 text-sm text-slate-200 outline-none"
        placeholder="搜索标题、正文或作者…"
      />
      <div class="flex shrink-0 gap-1 rounded-xl border border-white/[0.08] bg-white/[0.03] p-1">
        <button
          v-for="opt in ([
            { id: 'all', label: '全部' },
            { id: 'note', label: '笔记' },
            { id: 'link', label: '链接' },
            { id: 'file', label: '文件' },
          ] as const)"
          :key="opt.id"
          type="button"
          class="rounded-lg px-2.5 py-1 text-xs transition"
          :class="
            filter === opt.id
              ? 'bg-sky-500/20 text-sky-100 ring-1 ring-sky-400/30'
              : 'text-slate-500 hover:text-slate-300'
          "
          @click="filter = opt.id"
        >
          {{ opt.label }}
        </button>
      </div>
      <button
        type="button"
        class="cosmic-primary-btn shrink-0 rounded-xl px-3 py-2 text-xs font-semibold text-white"
        @click="composerOpen = !composerOpen"
      >
        {{ composerOpen ? '收起发布' : '分享资料' }}
      </button>
    </div>

    <p class="text-[11px] text-slate-500">分享学习笔记、链接与资料，教师可收录至星库。</p>

    <div
      v-if="composerOpen"
      class="space-y-2.5 rounded-xl border border-white/[0.08] bg-white/[0.03] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
    >
      <input
        v-model="title"
        class="cosmic-input w-full rounded-xl px-3 py-2 text-sm text-slate-200 outline-none"
        placeholder="标题"
      />
      <textarea
        v-model="body"
        rows="3"
        class="cosmic-input w-full resize-none rounded-xl px-3 py-2 text-sm text-slate-200 outline-none"
        placeholder="正文内容…"
      />
      <div class="flex flex-wrap items-center gap-2">
        <select v-model="kind" class="cosmic-input rounded-xl px-2 py-1.5 text-xs text-slate-200 outline-none">
          <option value="note">笔记</option>
          <option value="link">链接</option>
          <option value="file">文件</option>
        </select>
        <input
          v-if="kind === 'link'"
          v-model="fileUrl"
          class="cosmic-input min-w-0 flex-1 rounded-xl px-3 py-1.5 text-xs text-slate-200 outline-none"
          placeholder="https://…"
        />
        <template v-if="kind === 'file'">
          <div class="flex flex-wrap gap-1">
            <button
              v-for="opt in ([
                { id: 'local', label: '本地' },
                { id: 'vault', label: '知识库' },
                { id: 'workshop', label: '工坊' },
                { id: 'video', label: '我的视频' },
              ] as const)"
              :key="opt.id"
              type="button"
              class="rounded-lg px-2 py-1 text-[11px] transition"
              :class="
                fileSource === opt.id
                  ? 'bg-violet-500/20 text-violet-100 ring-1 ring-violet-400/30'
                  : 'border border-white/10 text-slate-400 hover:bg-white/5'
              "
              @click="openPicker(opt.id)"
            >
              {{ opt.label }}
            </button>
          </div>
          <label
            v-if="fileSource === 'local'"
            class="cursor-pointer rounded-xl border border-white/[0.08] bg-white/[0.04] px-3 py-1.5 text-xs text-sky-200 transition hover:bg-white/[0.08]"
          >
            {{ uploading ? '上传中…' : '选择文件' }}
            <input type="file" class="hidden" :disabled="uploading" @change="onFilePick" />
          </label>
          <span v-if="fileName" class="truncate text-[11px] text-slate-400">{{ fileName }}</span>
          <input
            v-if="fileSource === 'local'"
            v-model="fileUrl"
            class="cosmic-input min-w-0 flex-1 rounded-xl px-3 py-1.5 text-xs text-slate-200 outline-none"
            placeholder="或粘贴文件 URL"
          />
        </template>
      </div>

      <div
        v-if="kind === 'file' && pickerOpen && fileSource !== 'local'"
        class="max-h-44 space-y-1 overflow-y-auto rounded-xl border border-white/10 bg-black/20 p-2"
      >
        <p v-if="attachLoading" class="text-[11px] text-slate-500">加载中…</p>
        <button
          v-for="a in pickerItems"
          :key="`${a.source_type}-${a.id}`"
          type="button"
          class="block w-full rounded-lg px-2 py-1.5 text-left hover:bg-white/5"
          @click="pickAttachable(a)"
        >
          <span class="text-xs text-slate-100">{{ a.title }}</span>
          <span class="mt-0.5 block truncate text-[10px] text-slate-500">
            {{ a.kind_label }} · {{ a.subtitle }}
          </span>
        </button>
        <p v-if="!attachLoading && !pickerItems.length" class="text-[11px] text-slate-500">
          暂无可选内容
        </p>
      </div>

      <button
        type="button"
        class="cosmic-primary-btn w-full rounded-xl px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
        :disabled="loading || uploading"
        @click="publish"
      >
        {{ loading ? '发布中…' : '发布资料' }}
      </button>
    </div>

    <p
      v-if="tip"
      class="text-xs"
      :class="tipError ? 'text-rose-300' : 'text-emerald-300/90'"
    >
      {{ tip }}
    </p>

    <div class="min-h-0 flex-1 space-y-2 overflow-y-auto pr-0.5">
      <article
        v-for="item in filtered"
        :key="item.id"
        class="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3 transition hover:bg-white/[0.05]"
      >
        <button type="button" class="w-full text-left" @click="toggleExpand(item.id)">
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <p class="truncate text-sm font-medium text-slate-100">{{ item.title }}</p>
                <span class="rounded-lg border border-white/[0.08] px-1.5 py-0.5 text-[10px] text-slate-500">
                  {{ kindLabel(item.kind) }}
                </span>
                <span
                  v-if="item.source_type"
                  class="rounded-lg border border-sky-400/20 px-1.5 py-0.5 text-[10px] text-sky-200/80"
                >
                  {{ item.source_type }}
                </span>
                <span
                  v-if="item.promoted_asset_id"
                  class="rounded-lg border border-amber-400/25 bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-200/90"
                >
                  已入星库
                </span>
              </div>
              <p class="mt-0.5 text-[10px] text-slate-500">
                {{ item.author_name }} · {{ formatTime(item.created_at) }}
              </p>
              <p
                class="mt-2 text-sm leading-5 text-slate-400"
                :class="expandedId === item.id ? 'whitespace-pre-wrap' : 'line-clamp-2'"
              >
                {{ item.body }}
              </p>
            </div>
            <button
              type="button"
              class="shrink-0 rounded-lg px-2 py-1 text-[11px] text-amber-200/80 transition hover:bg-amber-500/10"
              @click.stop="like(item.id)"
            >
              ★ {{ item.like_count }}
            </button>
          </div>
        </button>

        <div v-if="expandedId === item.id" class="mt-3 space-y-2 border-t border-white/[0.06] pt-3">
          <a
            v-if="item.file_url"
            :href="item.file_url"
            target="_blank"
            rel="noopener"
            class="inline-flex text-xs text-sky-300/90 hover:underline"
            @click.stop
          >
            {{ item.kind === 'link' ? '打开链接' : '打开附件' }}
          </a>
          <button
            v-if="isTeacher && !item.promoted_asset_id"
            type="button"
            class="w-full rounded-xl border border-amber-400/25 px-2 py-1.5 text-[11px] text-amber-100/90 transition hover:bg-amber-500/10"
            @click.stop="promote(item)"
          >
            收录到星库
          </button>
        </div>
      </article>

      <div
        v-if="!items.length"
        class="flex flex-col items-center justify-center gap-3 py-16 text-center"
      >
        <p class="text-sm text-slate-500">还没有资料，做第一条分享吧</p>
        <button
          type="button"
          class="cosmic-primary-btn rounded-xl px-4 py-2 text-xs font-semibold text-white"
          @click="openComposer"
        >
          分享资料
        </button>
      </div>
      <p
        v-else-if="!filtered.length"
        class="py-12 text-center text-sm text-slate-500"
      >
        没有匹配的资料，试试其他关键词或类型
      </p>
    </div>
  </div>
</template>

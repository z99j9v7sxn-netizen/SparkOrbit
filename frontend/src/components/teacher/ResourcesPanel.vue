<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { fetchGalaxies } from '../../api/orbit';
import { createBilibiliAsset, uploadStarlibPdf } from '../../api/challengeSprint';
import { fetchLessonResources, uploadTeacherResource, type LessonResourceItem } from '../../api/zone';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';
import { useTeacherClassStore } from '../../stores/teacherClass';

const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);

const resources = ref<LessonResourceItem[]>([]);
const galaxies = ref<{ slug: string; name: string }[]>([]);
const filterGalaxy = ref('');
const title = ref('');
const uploadGalaxy = ref('');
const msg = ref('');
const loading = ref(false);
const uploading = ref(false);

const biliBvid = ref('');
const biliTitle = ref('');
const biliGalaxy = ref('');
const biliBusy = ref(false);
const biliMsg = ref('');

const starTitle = ref('');
const starGalaxy = ref('');
const starAssetType = ref('book');
const starBusy = ref(false);
const starMsg = ref('');

const galaxyNameMap = computed(() => Object.fromEntries(galaxies.value.map((g) => [g.slug, g.name])));

const filtered = computed(() => {
  let list = resources.value;
  if (classId.value) list = list.filter((r) => !r.class_id || r.class_id === classId.value);
  if (filterGalaxy.value) list = list.filter((r) => r.galaxy_slug === filterGalaxy.value);
  return list;
});

async function load() {
  loading.value = true;
  try {
    resources.value = await fetchLessonResources(filterGalaxy.value);
  } catch {
    resources.value = [];
  } finally {
    loading.value = false;
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
    );
    msg.value = `资料「${res.title}」已上传`;
    title.value = '';
    await load();
  } catch {
    msg.value = '上传失败';
  } finally {
    uploading.value = false;
    input.value = '';
  }
}

async function handleStarlibPdfUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) {
    starMsg.value = '请选择 PDF 文件';
    return;
  }
  starBusy.value = true;
  starMsg.value = '正在上传并解析进星库（大文件可能较慢）…';
  try {
    const res = await uploadStarlibPdf({
      file,
      title: starTitle.value.trim() || file.name.replace(/\.pdf$/i, ''),
      galaxy_slug: starGalaxy.value || undefined,
      asset_type: starAssetType.value || 'book',
      description: '教师端星库 PDF 入库',
    });
    starMsg.value = `已入库星库：${res.title}（${res.page_count || 0} 页 / ${res.chunk_count || 0} 块）`;
    starTitle.value = '';
  } catch (e) {
    starMsg.value = e instanceof Error ? e.message : '星库 PDF 上传失败';
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
    biliMsg.value = '请填写 BV 号（如 BV1xx…）';
    return;
  }
  biliBusy.value = true;
  biliMsg.value = '正在挂载进星库…';
  try {
    const res = await createBilibiliAsset({
      title: biliTitle.value.trim() || `B站 · ${clean}`,
      bvid: clean,
      galaxy_slug: biliGalaxy.value || undefined,
      description: '教师端资料站入库',
    });
    biliMsg.value = `已挂载进星库：${res.title || clean}`;
    biliBvid.value = '';
    biliTitle.value = '';
  } catch (e) {
    biliMsg.value = e instanceof Error ? e.message : 'B 站入库失败';
  } finally {
    biliBusy.value = false;
  }
}

watch([classId, filterGalaxy], () => void load());
onMounted(async () => {
  galaxies.value = (await fetchGalaxies()).map((g) => ({ slug: g.slug, name: g.name }));
  await load();
});
</script>

<template>
  <div class="space-y-5">
    <TeacherPageHeader title="教学资料" subtitle="上传教案 / 讲义，学生可在学习区下载">
      <template #actions>
        <select v-model="filterGalaxy" class="rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100">
          <option value="">全部星系</option>
          <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
        </select>
      </template>
    </TeacherPageHeader>

    <section class="glass rounded-2xl p-5">
      <h3 class="text-base font-semibold text-white">上传资料</h3>
      <div class="mt-3 grid gap-3 md:grid-cols-2">
        <input
          v-model="title"
          placeholder="资料标题（可选，默认文件名）"
          class="rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 outline-none"
        />
        <select v-model="uploadGalaxy" class="rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100">
          <option value="">目标星系（可选）</option>
          <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
        </select>
      </div>
      <label
        class="mt-3 flex cursor-pointer flex-col items-center rounded-xl border border-dashed border-sky-400/30 bg-sky-500/5 px-4 py-8 text-sm text-sky-200 hover:bg-sky-500/10"
        :class="uploading ? 'pointer-events-none opacity-60' : ''"
      >
        <span>{{ uploading ? '上传中…' : '点击上传教案 / 讲义 / PDF' }}</span>
        <input type="file" accept=".pdf,.md,.doc,.docx,.ppt,.pptx,.zip" class="hidden" @change="handleUpload" />
      </label>
      <p v-if="msg" class="mt-2 text-xs text-sky-300">{{ msg }}</p>
    </section>

    <section class="glass rounded-2xl p-5">
      <h3 class="text-base font-semibold text-white">上传 PDF 到星库</h3>
      <p class="mt-1 text-[11px] text-slate-400">
        写入星库原书模式并做分页 RAG；大体积教材建议用脚本
        <code class="text-slate-300">scripts/import_materials_to_starlib.py</code>
        。
      </p>
      <div class="mt-3 grid gap-3 md:grid-cols-3">
        <input
          v-model="starTitle"
          placeholder="标题（可选，默认文件名）"
          class="rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 outline-none"
        />
        <select v-model="starGalaxy" class="rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100">
          <option value="">关联星系（可选）</option>
          <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
        </select>
        <select v-model="starAssetType" class="rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100">
          <option value="book">教材 book</option>
          <option value="pdf">讲义 pdf</option>
          <option value="problem_doc">题集 problem_doc</option>
        </select>
      </div>
      <label
        class="mt-3 flex cursor-pointer flex-col items-center rounded-xl border border-dashed border-violet-400/30 bg-violet-500/5 px-4 py-6 text-sm text-violet-100 hover:bg-violet-500/10"
        :class="starBusy ? 'pointer-events-none opacity-60' : ''"
      >
        <span>{{ starBusy ? '解析入库中…' : '点击选择 PDF 上传到星库' }}</span>
        <input type="file" accept=".pdf,application/pdf" class="hidden" @change="handleStarlibPdfUpload" />
      </label>
      <p v-if="starMsg" class="mt-2 text-xs text-violet-200/90">{{ starMsg }}</p>
    </section>

    <section class="glass rounded-2xl p-5">
      <h3 class="text-base font-semibold text-white">B 站视频挂载星库</h3>
      <p class="mt-1 text-[11px] text-slate-400">填写 BV 号一键入库，学生可在星库浏览（不做开放搜索）。</p>
      <div class="mt-3 grid gap-3 md:grid-cols-3">
        <input
          v-model="biliBvid"
          placeholder="BV 号或含 BV 的链接"
          class="rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 outline-none"
        />
        <input
          v-model="biliTitle"
          placeholder="标题（可选）"
          class="rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 outline-none"
        />
        <select v-model="biliGalaxy" class="rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100">
          <option value="">关联星系（可选）</option>
          <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
        </select>
      </div>
      <button
        type="button"
        class="mt-3 rounded-xl border border-pink-300/30 bg-pink-500/15 px-4 py-2 text-sm text-pink-50 hover:bg-pink-500/25 disabled:opacity-50"
        :disabled="biliBusy"
        @click="handleBilibiliMount"
      >
        {{ biliBusy ? '挂载中…' : '挂载进星库' }}
      </button>
      <p v-if="biliMsg" class="mt-2 text-xs text-pink-200/90">{{ biliMsg }}</p>
    </section>

    <section class="glass rounded-2xl p-5">
      <h3 class="text-base font-semibold text-white">资料列表</h3>
      <TeacherLoading v-if="loading" />
      <div v-else class="mt-3 space-y-2">
        <div
          v-for="r in filtered"
          :key="r.id"
          class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 px-4 py-3"
        >
          <div>
            <p class="text-sm text-white">{{ r.title }}</p>
            <p class="mt-1 text-[11px] text-slate-400">
              <template v-if="r.galaxy_slug">{{ galaxyNameMap[r.galaxy_slug] || r.galaxy_slug }} · </template>
              {{ r.created_at?.slice(0, 16)?.replace('T', ' ') || '—' }}
            </p>
          </div>
          <a
            v-if="r.file_url"
            :href="r.file_url"
            target="_blank"
            class="rounded-lg border border-sky-300/20 px-3 py-1 text-xs text-sky-100 hover:bg-sky-500/10"
          >
            下载 / 打开
          </a>
        </div>
        <TeacherEmptyState v-if="!filtered.length" title="暂无资料" description="上传后学生即可在笔记面板下载" />
      </div>
    </section>
  </div>
</template>

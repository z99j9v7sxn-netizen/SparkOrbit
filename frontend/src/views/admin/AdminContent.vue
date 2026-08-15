<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import {
  deleteAdminFile,
  deleteAdminPlanet,
  fetchAdminFiles,
  fetchAdminGalaxies,
  fetchAdminPlanets,
  forgeGalaxyFromPdf,
  type AdminFilesOut,
  type GalaxyBrief,
  type PlanetBrief,
} from '../../api/admin';
import { parseApiError } from '../../api/errors';
import AdminEmptyState from '../../components/admin/AdminEmptyState.vue';
import AdminPageHeader from '../../components/admin/AdminPageHeader.vue';
import AdminSkeleton from '../../components/admin/AdminSkeleton.vue';
import { useCountUp } from '../../composables/useCountUp';

const galaxies = ref<GalaxyBrief[]>([]);
const planets = ref<PlanetBrief[]>([]);
const galaxySlug = ref('');
const msg = ref('');
const msgTone = ref<'ok' | 'err'>('ok');
const loading = ref(true);

// 删除二次确认：输入行星名
const confirmTarget = ref<PlanetBrief | null>(null);
const confirmInput = ref('');
const deleting = ref(false);

// PDF 锻造上传
const fileInputRef = ref<HTMLInputElement | null>(null);
const dragOver = ref(false);
const forging = ref(false);

const galaxyCount = computed(() => galaxies.value.length);
const planetTotal = computed(() => galaxies.value.reduce((acc, g) => acc + g.planet_count, 0));
const galaxyAnim = useCountUp(galaxyCount);
const planetAnim = useCountUp(planetTotal);

const DIFFICULTY_BADGE: Record<string, string> = {
  easy: 't-badge--ok',
  medium: 't-badge--warn',
  hard: 't-badge--danger',
};

async function loadGalaxies() {
  loading.value = true;
  try {
    galaxies.value = await fetchAdminGalaxies();
    if (!galaxySlug.value && galaxies.value.length) {
      galaxySlug.value = galaxies.value[0].slug;
    }
    await loadPlanets();
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '加载失败');
  } finally {
    loading.value = false;
  }
}

async function loadPlanets() {
  planets.value = await fetchAdminPlanets(galaxySlug.value);
}

function selectGalaxy(slug: string) {
  if (galaxySlug.value === slug) return;
  galaxySlug.value = slug;
  void loadPlanets();
}

function askRemove(planet: PlanetBrief) {
  confirmTarget.value = planet;
  confirmInput.value = '';
}

async function confirmRemove() {
  const target = confirmTarget.value;
  if (!target || confirmInput.value.trim() !== target.name) return;
  deleting.value = true;
  try {
    await deleteAdminPlanet(target.slug);
    msgTone.value = 'ok';
    msg.value = `已删除 ${target.name}`;
    confirmTarget.value = null;
    await loadGalaxies();
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '删除失败');
  } finally {
    deleting.value = false;
  }
}

async function forge(file: File) {
  if (forging.value) return;
  if (!/\.pdf$/i.test(file.name)) {
    msgTone.value = 'err';
    msg.value = '仅支持 PDF 文件';
    return;
  }
  forging.value = true;
  msg.value = '';
  try {
    await forgeGalaxyFromPdf(file);
    msgTone.value = 'ok';
    msg.value = `已从 ${file.name} 发起星系锻造`;
    await loadGalaxies();
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '锻造失败');
  } finally {
    forging.value = false;
  }
}

function onFilePick(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) void forge(file);
  input.value = '';
}

function onDrop(event: DragEvent) {
  dragOver.value = false;
  const file = event.dataTransfer?.files?.[0];
  if (file) void forge(file);
}

/* ---- 文件与存储管理 ---- */
const tab = ref<'content' | 'files'>('content');
const filesData = ref<AdminFilesOut | null>(null);
const filesLoading = ref(false);
const categoryFilter = ref('');

const filteredFiles = computed(() => {
  if (!filesData.value) return [];
  if (!categoryFilter.value) return filesData.value.files;
  return filesData.value.files.filter((f) => f.category === categoryFilter.value);
});

function formatSize(bytes: number) {
  if (bytes >= 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}

async function loadFiles() {
  filesLoading.value = true;
  try {
    filesData.value = await fetchAdminFiles();
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '文件列表加载失败');
  } finally {
    filesLoading.value = false;
  }
}

function setTab(value: 'content' | 'files') {
  if (tab.value === value) return;
  tab.value = value;
  if (value === 'files' && !filesData.value) void loadFiles();
}

async function removeFile(path: string) {
  if (!window.confirm(`确认删除文件 ${path}？此操作不可恢复。`)) return;
  try {
    await deleteAdminFile(path);
    msgTone.value = 'ok';
    msg.value = `已删除 ${path}`;
    await loadFiles();
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '删除失败');
  }
}

onMounted(loadGalaxies);
</script>

<template>
  <div class="space-y-5">
    <AdminPageHeader kicker="Curriculum" title="内容管理" subtitle="星系与行星治理、上传物料与磁盘占用">
      <template #actions>
        <div class="t-tabs" role="tablist" aria-label="管理类型">
          <button type="button" role="tab" class="t-tab" :class="{ 'is-active': tab === 'content' }" @click="setTab('content')">
            星系内容
          </button>
          <button type="button" role="tab" class="t-tab" :class="{ 'is-active': tab === 'files' }" @click="setTab('files')">
            文件存储
          </button>
        </div>
        <button
          type="button"
          class="t-btn t-btn--md t-btn--ghost"
          :disabled="loading || filesLoading"
          @click="tab === 'content' ? loadGalaxies() : loadFiles()"
        >
          {{ loading || filesLoading ? '刷新中…' : '刷新' }}
        </button>
      </template>
    </AdminPageHeader>

    <div v-if="tab === 'content'" class="grid gap-4 sm:grid-cols-2">
      <div class="adm-kpi p-4">
        <p class="text-xs text-t-2">星系数</p>
        <p class="adm-kpi__value mt-2">{{ galaxyAnim }}</p>
      </div>
      <div class="adm-kpi adm-kpi--accent2 p-4">
        <p class="text-xs text-t-2">行星总数</p>
        <p class="adm-kpi__value mt-2">{{ planetAnim }}</p>
      </div>
    </div>

    <p
      v-if="msg"
      class="rounded-xl border px-4 py-2.5 text-sm"
      :class="msgTone === 'ok' ? 'border-t-accent/20 bg-t-accent/8 text-t-accent' : 'border-t-danger/25 bg-t-danger/10 text-t-danger'"
    >
      {{ msg }}
    </p>

    <!-- 星系卡片网格 + PDF 锻造上传卡 -->
    <div v-if="tab === 'content'" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <button
        v-for="galaxy in galaxies"
        :key="galaxy.id"
        type="button"
        class="t-card t-card--hover p-4 text-left"
        :class="galaxySlug === galaxy.slug ? '!border-t-accent/45 shadow-[0_0_20px_-8px_rgb(var(--t-accent)/0.4)]' : ''"
        @click="selectGalaxy(galaxy.slug)"
      >
        <div class="flex items-start justify-between gap-2">
          <p class="min-w-0 truncate text-sm font-medium text-t-1">{{ galaxy.name }}</p>
          <span class="t-badge shrink-0" :class="galaxy.is_active ? 't-badge--ok' : 't-badge--neutral'">
            {{ galaxy.is_active ? '启用' : '停用' }}
          </span>
        </div>
        <p class="mt-1 truncate font-mono text-[11px] text-t-3">{{ galaxy.slug }}</p>
        <p class="mt-2 line-clamp-2 text-xs text-t-2">{{ galaxy.description || '暂无描述' }}</p>
        <p class="mt-2 text-[11px] text-t-3">
          <span class="font-mono text-t-accent">{{ galaxy.planet_count }}</span> 颗行星
        </p>
      </button>

      <!-- PDF 锻造入口 -->
      <button
        type="button"
        class="flex min-h-[132px] flex-col items-center justify-center gap-1.5 rounded-2xl border border-dashed p-4 text-center transition"
        :class="
          dragOver
            ? 'border-t-accent/60 bg-t-accent/10'
            : 'border-t-line/25 bg-t-s1/20 hover:border-t-accent/40 hover:bg-t-accent/5'
        "
        :disabled="forging"
        @click="fileInputRef?.click()"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="onDrop"
      >
        <svg viewBox="0 0 16 16" class="h-5 w-5 text-t-accent/80" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">
          <path d="M8 10.5v-7M5.2 6.3 8 3.5l2.8 2.8" />
          <path d="M2.5 10.5v2a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-2" />
        </svg>
        <p class="text-xs font-medium text-t-1">{{ forging ? '锻造中…' : 'PDF 锻造新星系' }}</p>
        <p class="text-[11px] text-t-3">{{ forging ? '解析教材内容，请稍候' : '点击或拖入 PDF 教材' }}</p>
      </button>
      <input ref="fileInputRef" type="file" accept=".pdf,application/pdf" class="hidden" @change="onFilePick" />
    </div>

    <!-- 行星表格 -->
    <AdminSkeleton v-if="tab === 'content' && loading" :rows="6" />
    <AdminEmptyState
      v-else-if="tab === 'content' && !planets.length"
      title="该星系暂无行星"
      hint="可通过 PDF 锻造或教师端星系锻造添加内容"
    />
    <transition v-else-if="tab === 'content'" name="fade-scale" appear>
      <div class="t-table-wrap">
        <table class="t-table">
          <thead>
            <tr>
              <th>行星</th>
              <th>所属星系</th>
              <th>难度</th>
              <th>轨道</th>
              <th class="text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="planet in planets" :key="planet.id">
              <td>
                <p class="text-[13px] text-t-1/90">{{ planet.name }}</p>
                <p class="mt-0.5 truncate font-mono text-[11px] text-t-3">{{ planet.slug }}</p>
              </td>
              <td class="text-[13px] text-t-2">{{ planet.galaxy_name }}</td>
              <td>
                <span class="t-badge" :class="DIFFICULTY_BADGE[planet.difficulty] || 't-badge--neutral'">
                  {{ planet.difficulty || '—' }}
                </span>
              </td>
              <td class="font-mono text-[12px] text-t-2">{{ planet.orbit_index }}</td>
              <td class="text-right">
                <button type="button" class="t-btn t-btn--sm t-btn--danger" @click="askRemove(planet)">
                  删除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </transition>

    <!-- 文件与存储管理 -->
    <template v-if="tab === 'files'">
      <AdminSkeleton v-if="filesLoading" :rows="6" />
      <template v-else-if="filesData">
        <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div class="adm-kpi p-4">
            <p class="text-xs text-t-2">文件总数</p>
            <p class="adm-kpi__value mt-2">{{ filesData.total_files }}</p>
          </div>
          <div class="adm-kpi adm-kpi--accent2 p-4">
            <p class="text-xs text-t-2">磁盘占用</p>
            <p class="adm-kpi__value mt-2">{{ formatSize(filesData.total_size) }}</p>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="t-tab"
            :class="{ 'is-active': !categoryFilter }"
            @click="categoryFilter = ''"
          >
            全部
          </button>
          <button
            v-for="cat in filesData.categories"
            :key="cat.name"
            type="button"
            class="t-tab"
            :class="{ 'is-active': categoryFilter === cat.name }"
            @click="categoryFilter = cat.name"
          >
            {{ cat.name }}（{{ cat.file_count }} · {{ formatSize(cat.total_size) }}）
          </button>
        </div>

        <AdminEmptyState v-if="!filteredFiles.length" title="暂无文件" hint="上传的头像、资料、笔记附件将在此显示" />
        <div v-else class="t-table-wrap">
          <table class="t-table">
            <thead>
              <tr>
                <th>文件路径</th>
                <th>分类</th>
                <th>大小</th>
                <th>修改时间</th>
                <th class="text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="f in filteredFiles" :key="f.path">
                <td class="max-w-md truncate font-mono text-[12px] text-t-1/90" :title="f.path">{{ f.path }}</td>
                <td><span class="t-badge t-badge--neutral">{{ f.category }}</span></td>
                <td class="font-mono text-[12px] text-t-2">{{ formatSize(f.size) }}</td>
                <td class="text-[12px] text-t-3">{{ f.modified_at.slice(0, 10) }}</td>
                <td class="text-right">
                  <button type="button" class="t-btn t-btn--sm t-btn--danger" @click="removeFile(f.path)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="text-[11px] text-t-3">仅展示最大的前 200 个文件；删除操作会写入审计日志。</p>
      </template>
    </template>

    <teleport to="body">
      <transition name="fade-scale">
        <div
          v-if="confirmTarget"
          class="t-cmdk-overlay !items-center !p-4"
          @click.self="confirmTarget = null"
        >
          <div class="t-cmdk max-w-md p-6">
            <p class="t-kicker !text-t-danger">Danger Zone</p>
            <h3 class="mt-1 text-lg font-semibold text-t-1">删除行星</h3>
            <p class="mt-2 text-sm text-t-2">
              此操作不可恢复。输入行星名
              <span class="font-semibold text-t-danger">{{ confirmTarget.name }}</span>
              以确认删除。
            </p>
            <input
              v-model="confirmInput"
              type="text"
              :placeholder="confirmTarget.name"
              class="t-input mt-4"
              @keyup.enter="confirmRemove"
            />
            <div class="mt-4 flex justify-end gap-2">
              <button type="button" class="t-btn t-btn--md t-btn--ghost" @click="confirmTarget = null">
                取消
              </button>
              <button
                type="button"
                class="t-btn t-btn--md t-btn--danger"
                :disabled="confirmInput.trim() !== confirmTarget.name || deleting"
                @click="confirmRemove"
              >
                {{ deleting ? '删除中…' : '确认删除' }}
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>
  </div>
</template>

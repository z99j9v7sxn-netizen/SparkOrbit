<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import {
  fetchVaultCanvas,
  saveVaultCanvas,
  searchVault,
  type VaultCanvasData,
  type VaultSearchHit,
} from '../../api/vault';
import { LzButton, LzSkeleton } from './ui';

const props = withDefaults(defineProps<{ path?: string }>(), {
  path: '60-Canvas/默认画布.canvas',
});

const emit = defineEmits<{
  openFile: [path: string];
  status: [msg: string];
}>();

const data = ref<VaultCanvasData>({ nodes: [], edges: [] });
const saving = ref(false);
const selected = ref('');
const dragId = ref('');
const offset = ref({ x: 0, y: 0 });
const clipPickerOpen = ref(false);
const recentClips = ref<VaultSearchHit[]>([]);
const clipsLoading = ref(false);
const pickerMode = ref<'clips' | 'workshop'>('clips');
const zoom = ref(0.7);
const scrollHostRef = ref<HTMLDivElement | null>(null);

const ZOOM_MIN = 0.4;
const ZOOM_MAX = 1.5;
const BOARD_W = 960;
const BOARD_H = 640;

function setZoom(next: number) {
  zoom.value = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(next * 100) / 100));
}
function zoomIn() {
  setZoom(zoom.value + 0.1);
}
function zoomOut() {
  setZoom(zoom.value - 0.1);
}
function zoomReset() {
  setZoom(0.7);
}
function onBoardWheel(ev: WheelEvent) {
  if (!ev.ctrlKey && !ev.metaKey) return;
  ev.preventDefault();
  setZoom(zoom.value + (ev.deltaY < 0 ? 0.08 : -0.08));
}

function clientToBoard(ev: PointerEvent) {
  const host = scrollHostRef.value;
  if (!host) return { x: ev.clientX / zoom.value, y: ev.clientY / zoom.value };
  const rect = host.getBoundingClientRect();
  return {
    x: (ev.clientX - rect.left + host.scrollLeft) / zoom.value,
    y: (ev.clientY - rect.top + host.scrollTop) / zoom.value,
  };
}

const nodes = computed(() => data.value.nodes || []);
const edges = computed(() => data.value.edges || []);
const groupNodes = computed(() => nodes.value.filter((n) => n.type === 'group'));
const cardNodes = computed(() => nodes.value.filter((n) => n.type !== 'group'));

const GROUP_COLORS: Record<string, string> = {
  '1': 'rgba(244, 63, 94, 0.12)',
  '3': 'rgba(52, 211, 153, 0.12)',
  '4': 'rgba(56, 189, 248, 0.12)',
  '5': 'rgba(167, 139, 250, 0.12)',
};

function groupBg(color?: string) {
  return GROUP_COLORS[color || ''] || 'rgba(148, 163, 184, 0.08)';
}

function seedZonesIfNeeded() {
  // 旧画布数据可能只有卡片没有分区框，缺分区时补种，保证「按分区整理」可用
  if (data.value.nodes?.some((n) => n.type === 'group')) return;
  data.value.nodes = [
    { id: 'g-planets', type: 'group', label: '行星主线', x: 40, y: 40, width: 420, height: 280, color: '4' },
    { id: 'g-clips', type: 'group', label: '剪藏与证据', x: 500, y: 40, width: 420, height: 280, color: '5' },
    { id: 'g-workshop', type: 'group', label: '工坊产出', x: 40, y: 360, width: 420, height: 280, color: '3' },
    { id: 'g-weak', type: 'group', label: '薄弱与行动', x: 500, y: 360, width: 420, height: 280, color: '1' },
    ...(data.value.nodes || []),
  ];
}

/** 卡片坐标可能为负（历史数据/越界拖拽），负区在 overflow 容器里永远不可见，统一夹回画板内 */
function clampNode(n: { x: number; y: number; width?: number; height?: number }) {
  const w = Math.min(n.width || 160, BOARD_W);
  const h = Math.min(n.height || 70, BOARD_H);
  n.x = Math.min(Math.max(0, n.x), BOARD_W - w);
  n.y = Math.min(Math.max(0, n.y), BOARD_H - h);
}

async function load() {
  const res = await fetchVaultCanvas(props.path);
  data.value = res.data || { nodes: [], edges: [] };
  seedZonesIfNeeded();
  data.value.nodes.forEach(clampNode);
  if (!res.data?.nodes?.length) void persist();
}

async function openWorkshopPicker() {
  pickerMode.value = 'workshop';
  clipPickerOpen.value = true;
  clipsLoading.value = true;
  try {
    const hits = (await searchVault('70-Workshop')) || [];
    recentClips.value = hits.filter((h) => h.path.startsWith('70-Workshop/')).slice(0, 12);
    if (!recentClips.value.length) {
      recentClips.value = ((await searchVault('')) || [])
        .filter((h) => h.path.startsWith('70-Workshop/'))
        .slice(0, 12);
    }
  } catch (e) {
    recentClips.value = [];
    emit('status', e instanceof Error ? e.message : '加载工坊产物失败');
  } finally {
    clipsLoading.value = false;
  }
}

async function persist() {
  saving.value = true;
  try {
    const res = await saveVaultCanvas(props.path, data.value);
    data.value = res.data;
    emit('status', '画布已保存');
  } catch (e) {
    emit('status', e instanceof Error ? e.message : '画布保存失败');
  } finally {
    saving.value = false;
  }
}

function addTextCard() {
  const id = `n-${Date.now().toString(36)}`;
  data.value.nodes.push({
    id,
    type: 'text',
    x: 80 + Math.random() * 120,
    y: 60 + Math.random() * 80,
    width: 180,
    height: 80,
    text: '新卡片',
  });
  void persist();
}

function pushFileNode(filePath: string, label?: string) {
  const id = `n-${Date.now().toString(36)}`;
  data.value.nodes.push({
    id,
    type: 'file',
    x: 100 + Math.random() * 100,
    y: 100 + Math.random() * 60,
    width: 200,
    height: 72,
    file: filePath,
    label: label || filePath.split('/').pop() || filePath,
  });
  void persist();
}

function addFileCard() {
  const file = window.prompt('关联笔记路径（如 00-Inbox/demo.md）');
  if (!file) return;
  pushFileNode(file.trim());
}

async function openClipPicker() {
  pickerMode.value = 'clips';
  clipPickerOpen.value = true;
  clipsLoading.value = true;
  try {
    const hits = (await searchVault('')) || [];
    recentClips.value = hits
      .filter((h) => h.path.startsWith('20-Clips/'))
      .slice(0, 12);
  } catch (e) {
    recentClips.value = [];
    emit('status', e instanceof Error ? e.message : '加载剪藏失败');
  } finally {
    clipsLoading.value = false;
  }
}

function addClipCard(hit: VaultSearchHit) {
  pushFileNode(hit.path, hit.title || hit.path.split('/').pop());
  clipPickerOpen.value = false;
  emit('status', `已加入剪藏卡：${hit.title || hit.path}`);
}

function addOtherPathFromPicker() {
  clipPickerOpen.value = false;
  addFileCard();
}

function connectSelected() {
  if (!selected.value) {
    emit('status', '先点选一张卡片作为起点，再点另一张连接');
    return;
  }
  const to = window.prompt('连接到哪个节点 id？（可先看卡片角落 id）');
  if (!to || to === selected.value) return;
  data.value.edges.push({
    id: `e-${Date.now().toString(36)}`,
    fromNode: selected.value,
    toNode: to,
  });
  void persist();
}

function removeSelected() {
  if (!selected.value) return;
  data.value.nodes = data.value.nodes.filter((n) => n.id !== selected.value);
  data.value.edges = data.value.edges.filter(
    (e) => e.fromNode !== selected.value && e.toNode !== selected.value,
  );
  selected.value = '';
  void persist();
}

function onPointerDown(ev: PointerEvent, id: string) {
  const n = data.value.nodes.find((x) => x.id === id);
  if (!n) return;
  selected.value = id;
  dragId.value = id;
  const pt = clientToBoard(ev);
  offset.value = { x: pt.x - n.x, y: pt.y - n.y };
  (ev.target as HTMLElement).setPointerCapture?.(ev.pointerId);
}

function arrangeIntoZones() {
  const zones = {
    planets: groupNodes.value.find((g) => g.id === 'g-planets' || g.label?.includes('行星')),
    clips: groupNodes.value.find((g) => g.id === 'g-clips' || g.label?.includes('剪藏')),
    workshop: groupNodes.value.find((g) => g.id === 'g-workshop' || g.label?.includes('工坊')),
    weak: groupNodes.value.find((g) => g.id === 'g-weak' || g.label?.includes('薄弱')),
  };
  let pi = 0;
  let ci = 0;
  let wi = 0;
  let oi = 0;
  for (const n of cardNodes.value) {
    const file = n.file || '';
    let z = zones.weak;
    let idx = oi++;
    if (file.startsWith('10-Planets/')) {
      z = zones.planets;
      idx = pi++;
    } else if (file.startsWith('20-Clips/')) {
      z = zones.clips;
      idx = ci++;
    } else if (file.startsWith('70-Workshop/')) {
      z = zones.workshop;
      idx = wi++;
    }
    if (!z) continue;
    n.x = (z.x || 0) + 16 + (idx % 2) * 190;
    n.y = (z.y || 0) + 36 + Math.floor(idx / 2) * 84;
  }
  void persist();
  emit('status', '已按分区整理卡片');
}

function onPointerMove(ev: PointerEvent) {
  if (!dragId.value) return;
  const n = data.value.nodes.find((x) => x.id === dragId.value);
  if (!n) return;
  const pt = clientToBoard(ev);
  n.x = pt.x - offset.value.x;
  n.y = pt.y - offset.value.y;
  clampNode(n);
}

function onPointerUp() {
  if (dragId.value) {
    dragId.value = '';
    void persist();
  }
}

function nodeCenter(id: string) {
  const n = data.value.nodes.find((x) => x.id === id);
  if (!n) return { x: 0, y: 0 };
  return { x: n.x + (n.width || 160) / 2, y: n.y + (n.height || 70) / 2 };
}

watch(() => props.path, () => void load());
onMounted(() => void load());
</script>

<template>
  <div class="relative flex h-full min-h-[280px] flex-col gap-2">
    <div class="flex flex-wrap items-center gap-1.5">
      <LzButton variant="soft" size="sm" @click="openClipPicker">从剪藏加卡</LzButton>
      <LzButton variant="soft" size="sm" @click="openWorkshopPicker">从工坊加卡</LzButton>
      <LzButton variant="ghost" size="sm" @click="addTextCard">加文本卡</LzButton>
      <LzButton variant="ghost" size="sm" @click="addFileCard">加笔记卡</LzButton>
      <span class="mx-1 h-4 w-px bg-white/10" aria-hidden="true" />
      <LzButton variant="ghost" size="sm" @click="arrangeIntoZones">按分区整理</LzButton>
      <LzButton variant="ghost" size="sm" @click="connectSelected">连线</LzButton>
      <LzButton variant="danger" size="sm" :disabled="!selected" @click="removeSelected">删除选中</LzButton>
      <span class="mx-1 h-4 w-px bg-white/10" aria-hidden="true" />
      <LzButton variant="ghost" size="sm" title="缩小" @click="zoomOut">−</LzButton>
      <LzButton variant="ghost" size="sm" title="重置缩放" @click="zoomReset">{{ Math.round(zoom * 100) }}%</LzButton>
      <LzButton variant="ghost" size="sm" title="放大" @click="zoomIn">+</LzButton>
      <span class="lz-caption ml-auto truncate">{{ saving ? '保存中…' : path }}</span>
    </div>
    <div
      ref="scrollHostRef"
      class="relative min-h-[260px] flex-1 overflow-auto rounded-xl border border-white/10 bg-[radial-gradient(circle_at_1px_1px,rgba(148,163,184,0.15)_1px,transparent_0)] bg-[length:16px_16px]"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @wheel="onBoardWheel"
    >
      <div
        class="relative"
        :style="{
          width: BOARD_W * zoom + 'px',
          height: BOARD_H * zoom + 'px',
        }"
      >
        <div
          class="relative origin-top-left"
          :style="{
            width: BOARD_W + 'px',
            height: BOARD_H + 'px',
            transform: `scale(${zoom})`,
            transformOrigin: '0 0',
          }"
        >
        <div
          v-for="g in groupNodes"
          :key="g.id"
          class="absolute rounded-2xl border border-dashed border-white/20"
          :style="{
            left: g.x + 'px',
            top: g.y + 'px',
            width: (g.width || 400) + 'px',
            height: (g.height || 260) + 'px',
            background: groupBg(g.color),
          }"
          @pointerdown="onPointerDown($event, g.id)"
        >
          <p class="px-3 pt-2 text-[11px] font-semibold tracking-wide text-slate-300">{{ g.label || '分区' }}</p>
        </div>
        <svg class="pointer-events-none absolute inset-0 h-full w-full">
          <line
            v-for="e in edges"
            :key="e.id"
            :x1="nodeCenter(e.fromNode).x"
            :y1="nodeCenter(e.fromNode).y"
            :x2="nodeCenter(e.toNode).x"
            :y2="nodeCenter(e.toNode).y"
            class="stroke-[rgb(var(--lz-accent)/0.55)]"
            stroke-width="2"
          />
        </svg>
        <div
          v-for="n in cardNodes"
          :key="n.id"
          class="absolute cursor-grab rounded-xl border px-2 py-1.5 text-[11px] shadow-lg active:cursor-grabbing"
          :class="
            selected === n.id
              ? 'border-[rgb(var(--lz-accent)/0.5)] bg-[rgb(var(--lz-accent)/0.2)] text-white'
              : 'border-white/15 bg-slate-900/90 text-slate-100'
          "
          :style="{
            left: n.x + 'px',
            top: n.y + 'px',
            width: (n.width || 160) + 'px',
            minHeight: (n.height || 70) + 'px',
          }"
          @pointerdown="onPointerDown($event, n.id)"
          @dblclick="n.file ? emit('openFile', n.file) : undefined"
        >
          <div class="text-[9px] text-slate-500">{{ n.id }}</div>
          <div v-if="n.type === 'file'" class="flex items-center gap-1 font-medium text-[rgb(var(--lz-accent-bright))]">
            <img class="h-3.5 w-3.5 shrink-0" src="/icons/file.svg" alt="" aria-hidden="true" />
            <span class="truncate">{{ n.label || n.file }}</span>
          </div>
          <textarea
            v-else
            v-model="n.text"
            class="mt-1 w-full resize-none bg-transparent text-[11px] outline-none"
            rows="3"
            @change="persist"
          />
        </div>
        <p v-if="!cardNodes.length" class="absolute inset-0 flex items-center justify-center text-xs text-slate-500">
          四分区已就绪 — 从剪藏/工坊加卡，或点「按分区整理」
        </p>
        </div>
      </div>
    </div>

    <div
      v-if="clipPickerOpen"
      class="absolute inset-x-2 top-10 z-20 max-h-64 overflow-hidden rounded-[var(--radius-card)] border border-[rgb(var(--lz-accent)/0.3)] bg-slate-950/95 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-white/10 px-3 py-2">
        <p class="lz-subtitle">
          {{ pickerMode === 'workshop' ? '从工坊产物加卡' : '从最近划词剪藏加卡' }}
        </p>
        <button type="button" class="lz-caption transition hover:text-slate-200" @click="clipPickerOpen = false">
          关闭
        </button>
      </div>
      <div class="max-h-48 overflow-auto p-2">
        <div v-if="clipsLoading" class="px-2 py-3">
          <LzSkeleton preset="text" :rows="3" />
        </div>
        <p v-else-if="!recentClips.length" class="lz-caption px-2 py-3 leading-4">
          {{
            pickerMode === 'workshop'
              ? '暂无工坊入库文件，可先在资源工坊点「保存到知识库」。'
              : '暂无划词剪藏，可先在星库或演武舱点「划词剪藏」。'
          }}
        </p>
        <button
          v-for="hit in recentClips"
          :key="hit.path"
          type="button"
          class="lz-card lz-card--flat lz-card--hover mb-1 w-full px-2.5 py-2 text-left"
          @click="addClipCard(hit)"
        >
          <p class="truncate text-[11px] font-medium text-slate-100">{{ hit.title || hit.path }}</p>
          <p v-if="hit.snippet" class="lz-caption mt-0.5 line-clamp-2">{{ hit.snippet }}</p>
        </button>
      </div>
      <div class="border-t border-white/10 px-2 py-1.5">
        <button
          type="button"
          class="lz-caption w-full rounded-lg px-2 py-1.5 text-left transition hover:bg-white/5 hover:text-slate-200"
          @click="addOtherPathFromPicker"
        >
          输入其他路径…
        </button>
      </div>
    </div>
  </div>
</template>

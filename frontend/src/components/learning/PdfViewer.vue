<script setup lang="ts">
/**
 * 轻量 PDF.js 阅读器：站内渲染 + 选区划词 + 涂抹/圈选画笔裁切。
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

type FitMode = 'manual' | 'width' | 'page';
type BrushMode = 'none' | 'smear' | 'circle';

export type RegionCapturePayload = {
  dataUrl: string;
  page: number;
  mode: 'smear' | 'circle';
};

const props = defineProps<{
  src: string;
}>();

const emit = defineEmits<{
  (e: 'page-change', page: number): void;
  (e: 'text-select', text: string, page: number): void;
  (e: 'selectable-change', hasText: boolean, page: number): void;
  (e: 'region-capture', payload: RegionCapturePayload): void;
}>();

const hostRef = ref<HTMLDivElement | null>(null);
const rootRef = ref<HTMLDivElement | null>(null);
const loading = ref(false);
const error = ref('');
const page = ref(1);
const pageCount = ref(0);
const scale = ref(1.15);
const fitMode = ref<FitMode>('width');
const pageInput = ref(1);
const hasSelectableText = ref(true);
const brushMode = ref<BrushMode>('none');

let pdfDoc: any = null;
let pdfjsLib: any = null;
let renderToken = 0;
let resizeObs: ResizeObserver | null = null;
let basePageWidth = 0;
let basePageHeight = 0;
let activeTextLayer: { cancel: () => void } | null = null;
/** 当前页光栅 canvas（用于裁切） */
let pageCanvas: HTMLCanvasElement | null = null;
let pageWrap: HTMLDivElement | null = null;
let drawCanvas: HTMLCanvasElement | null = null;

type Pt = { x: number; y: number };
let drawing = false;
let smearPoints: Pt[] = [];
let circleStart: Pt | null = null;
let circleEnd: Pt | null = null;

const PDFJS_LOCAL_WORKER = '/pdf.worker.min.mjs';
const PDFJS_CDN_WORKER =
  'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.8.69/pdf.worker.min.mjs';

async function loadPdfJs() {
  try {
    const mod = await import('pdfjs-dist');
    const pdfjs = mod.default || mod;
    if (pdfjs.GlobalWorkerOptions) {
      // 生产：同源 public/pdf.worker.min.mjs，避免国外 CDN 与 hashed .mjs 加载失败
      pdfjs.GlobalWorkerOptions.workerSrc = import.meta.env.PROD
        ? PDFJS_LOCAL_WORKER
        : (() => {
            try {
              return new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString();
            } catch {
              return PDFJS_LOCAL_WORKER;
            }
          })();
    }
    return pdfjs;
  } catch {
    // @ts-expect-error dynamic CDN
    const pdfjs = await import('https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.8.69/pdf.min.mjs');
    pdfjs.GlobalWorkerOptions.workerSrc = PDFJS_CDN_WORKER;
    return pdfjs;
  }
}

function computeFitScale(): number {
  if (!hostRef.value || !basePageWidth) return scale.value;
  const pad = 16;
  const cw = Math.max(120, hostRef.value.clientWidth - pad);
  const ch = Math.max(120, hostRef.value.clientHeight - pad);
  if (fitMode.value === 'width') {
    return Math.min(4, Math.max(0.5, cw / basePageWidth));
  }
  if (fitMode.value === 'page') {
    const sw = cw / basePageWidth;
    const sh = ch / basePageHeight;
    return Math.min(4, Math.max(0.5, Math.min(sw, sh)));
  }
  return scale.value;
}

async function ensureBaseSize() {
  if (!pdfDoc || basePageWidth) return;
  const pdfPage = await pdfDoc.getPage(1);
  const vp = pdfPage.getViewport({ scale: 1 });
  basePageWidth = vp.width;
  basePageHeight = vp.height;
}

function countTextItems(textContent: { items?: Array<{ str?: string }> }): number {
  let n = 0;
  for (const item of textContent.items || []) {
    if (item.str?.trim()) n += 1;
  }
  return n;
}

function clearBrushStroke() {
  drawing = false;
  smearPoints = [];
  circleStart = null;
  circleEnd = null;
  const ctx = drawCanvas?.getContext('2d');
  if (ctx && drawCanvas) ctx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
}

function syncDrawCanvasSize() {
  if (!pageCanvas || !pageWrap || !drawCanvas) return;
  const w = pageCanvas.clientWidth || parseFloat(pageCanvas.style.width) || 0;
  const h = pageCanvas.clientHeight || parseFloat(pageCanvas.style.height) || 0;
  if (!w || !h) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  drawCanvas.width = Math.floor(w * dpr);
  drawCanvas.height = Math.floor(h * dpr);
  drawCanvas.style.width = `${w}px`;
  drawCanvas.style.height = `${h}px`;
  const ctx = drawCanvas.getContext('2d');
  if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function ensureDrawOverlay(): HTMLCanvasElement | null {
  if (!pageWrap) return null;
  if (!drawCanvas) {
    drawCanvas = document.createElement('canvas');
    drawCanvas.className = 'pdf-brush-layer';
    pageWrap.appendChild(drawCanvas);
  } else if (drawCanvas.parentElement !== pageWrap) {
    pageWrap.appendChild(drawCanvas);
  }
  syncDrawCanvasSize();
  updateOverlayPointer();
  return drawCanvas;
}

function updateOverlayPointer() {
  if (!drawCanvas) return;
  const active = brushMode.value !== 'none';
  drawCanvas.style.pointerEvents = active ? 'auto' : 'none';
  drawCanvas.style.cursor = active ? 'crosshair' : 'default';
  const textLayer = pageWrap?.querySelector('.textLayer') as HTMLElement | null;
  if (textLayer) {
    textLayer.style.pointerEvents = active ? 'none' : 'auto';
  }
}

function setBrushMode(mode: BrushMode) {
  if (brushMode.value === mode) {
    brushMode.value = 'none';
  } else {
    brushMode.value = mode;
  }
  clearBrushStroke();
  ensureDrawOverlay();
  updateOverlayPointer();
}

function localPoint(ev: PointerEvent): Pt | null {
  if (!drawCanvas) return null;
  const rect = drawCanvas.getBoundingClientRect();
  return { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
}

function paintSmearPreview() {
  if (!drawCanvas) return;
  const ctx = drawCanvas.getContext('2d');
  if (!ctx) return;
  const w = drawCanvas.clientWidth;
  const h = drawCanvas.clientHeight;
  ctx.clearRect(0, 0, w, h);
  if (smearPoints.length < 1) return;
  ctx.strokeStyle = 'rgba(250, 204, 21, 0.55)';
  ctx.fillStyle = 'rgba(250, 204, 21, 0.22)';
  ctx.lineWidth = 22;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.beginPath();
  ctx.moveTo(smearPoints[0].x, smearPoints[0].y);
  for (let i = 1; i < smearPoints.length; i++) {
    ctx.lineTo(smearPoints[i].x, smearPoints[i].y);
  }
  ctx.stroke();
}

function paintCirclePreview() {
  if (!drawCanvas || !circleStart || !circleEnd) return;
  const ctx = drawCanvas.getContext('2d');
  if (!ctx) return;
  const w = drawCanvas.clientWidth;
  const h = drawCanvas.clientHeight;
  ctx.clearRect(0, 0, w, h);
  const cx = (circleStart.x + circleEnd.x) / 2;
  const cy = (circleStart.y + circleEnd.y) / 2;
  const rx = Math.abs(circleEnd.x - circleStart.x) / 2;
  const ry = Math.abs(circleEnd.y - circleStart.y) / 2;
  if (rx < 2 && ry < 2) return;
  ctx.strokeStyle = 'rgba(56, 189, 248, 0.9)';
  ctx.fillStyle = 'rgba(56, 189, 248, 0.12)';
  ctx.lineWidth = 2;
  ctx.setLineDash([6, 4]);
  ctx.beginPath();
  ctx.ellipse(cx, cy, Math.max(rx, 1), Math.max(ry, 1), 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.setLineDash([]);
}

function boundsFromSmear(pad = 12): { x: number; y: number; w: number; h: number } | null {
  if (!drawCanvas || smearPoints.length < 2) return null;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const p of smearPoints) {
    minX = Math.min(minX, p.x);
    minY = Math.min(minY, p.y);
    maxX = Math.max(maxX, p.x);
    maxY = Math.max(maxY, p.y);
  }
  const half = 11;
  minX = Math.max(0, minX - half - pad);
  minY = Math.max(0, minY - half - pad);
  maxX = Math.min(drawCanvas.clientWidth, maxX + half + pad);
  maxY = Math.min(drawCanvas.clientHeight, maxY + half + pad);
  const w = maxX - minX;
  const h = maxY - minY;
  if (w < 8 || h < 8) return null;
  return { x: minX, y: minY, w, h };
}

function boundsFromCircle(pad = 8): { x: number; y: number; w: number; h: number } | null {
  if (!drawCanvas || !circleStart || !circleEnd) return null;
  const minX = Math.max(0, Math.min(circleStart.x, circleEnd.x) - pad);
  const minY = Math.max(0, Math.min(circleStart.y, circleEnd.y) - pad);
  const maxX = Math.min(drawCanvas.clientWidth, Math.max(circleStart.x, circleEnd.x) + pad);
  const maxY = Math.min(drawCanvas.clientHeight, Math.max(circleStart.y, circleEnd.y) + pad);
  const w = maxX - minX;
  const h = maxY - minY;
  if (w < 12 || h < 12) return null;
  return { x: minX, y: minY, w, h };
}

function cropPageRegion(box: { x: number; y: number; w: number; h: number }): string | null {
  if (!pageCanvas || !drawCanvas) return null;
  const cssW = pageCanvas.clientWidth || parseFloat(pageCanvas.style.width);
  const cssH = pageCanvas.clientHeight || parseFloat(pageCanvas.style.height);
  if (!cssW || !cssH) return null;
  const sx = (box.x / cssW) * pageCanvas.width;
  const sy = (box.y / cssH) * pageCanvas.height;
  const sw = (box.w / cssW) * pageCanvas.width;
  const sh = (box.h / cssH) * pageCanvas.height;
  if (sw < 4 || sh < 4) return null;
  const out = document.createElement('canvas');
  out.width = Math.max(1, Math.floor(sw));
  out.height = Math.max(1, Math.floor(sh));
  const ctx = out.getContext('2d');
  if (!ctx) return null;
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, out.width, out.height);
  ctx.drawImage(pageCanvas, sx, sy, sw, sh, 0, 0, out.width, out.height);
  try {
    return out.toDataURL('image/jpeg', 0.88);
  } catch {
    return null;
  }
}

function finishBrushCapture() {
  const mode = brushMode.value;
  if (mode !== 'smear' && mode !== 'circle') return;
  const box = mode === 'smear' ? boundsFromSmear() : boundsFromCircle();
  if (!box) {
    clearBrushStroke();
    return;
  }
  const dataUrl = cropPageRegion(box);
  clearBrushStroke();
  if (!dataUrl) return;
  emit('region-capture', { dataUrl, page: page.value, mode });
}

function onBrushPointerDown(ev: PointerEvent) {
  if (brushMode.value === 'none') return;
  const pt = localPoint(ev);
  if (!pt) return;
  drawing = true;
  drawCanvas?.setPointerCapture?.(ev.pointerId);
  if (brushMode.value === 'smear') {
    smearPoints = [pt];
    paintSmearPreview();
  } else {
    circleStart = pt;
    circleEnd = pt;
    paintCirclePreview();
  }
  ev.preventDefault();
}

function onBrushPointerMove(ev: PointerEvent) {
  if (!drawing || brushMode.value === 'none') return;
  const pt = localPoint(ev);
  if (!pt) return;
  if (brushMode.value === 'smear') {
    smearPoints.push(pt);
    paintSmearPreview();
  } else {
    circleEnd = pt;
    paintCirclePreview();
  }
  ev.preventDefault();
}

function onBrushPointerUp(ev: PointerEvent) {
  if (!drawing) return;
  drawing = false;
  try {
    drawCanvas?.releasePointerCapture?.(ev.pointerId);
  } catch {
    /* ignore */
  }
  finishBrushCapture();
  ev.preventDefault();
}

async function renderPage(n: number) {
  if (!pdfDoc || !hostRef.value) return;
  const token = ++renderToken;
  activeTextLayer?.cancel();
  activeTextLayer = null;
  pageCanvas = null;
  pageWrap = null;
  drawCanvas = null;
  clearBrushStroke();
  await ensureBaseSize();
  if (fitMode.value !== 'manual') {
    scale.value = computeFitScale();
  }
  const pdfPage = await pdfDoc.getPage(n);
  if (token !== renderToken) return;
  // 扫描版大图：再压低 DPR，优先首屏速度
  const dpr = Math.min(window.devicePixelRatio || 1, 1.25);
  const viewport = pdfPage.getViewport({ scale: scale.value });
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  canvas.width = Math.floor(viewport.width * dpr);
  canvas.height = Math.floor(viewport.height * dpr);
  canvas.style.width = `${viewport.width}px`;
  canvas.style.height = `${viewport.height}px`;
  canvas.className = 'block bg-white shadow';
  canvas.style.pointerEvents = 'none';
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  await pdfPage.render({ canvasContext: ctx, viewport }).promise;
  if (token !== renderToken) return;

  const wrap = document.createElement('div');
  wrap.className = 'pdf-page relative mx-auto';
  wrap.style.width = `${viewport.width}px`;
  wrap.style.height = `${viewport.height}px`;
  wrap.appendChild(canvas);

  // 先出图，立刻结束「加载中」
  hostRef.value.innerHTML = '';
  hostRef.value.appendChild(wrap);
  pageCanvas = canvas;
  pageWrap = wrap;
  loading.value = false;
  const brushLayer = ensureDrawOverlay();
  if (brushLayer) {
    brushLayer.addEventListener('pointerdown', onBrushPointerDown);
    brushLayer.addEventListener('pointermove', onBrushPointerMove);
    brushLayer.addEventListener('pointerup', onBrushPointerUp);
    brushLayer.addEventListener('pointercancel', onBrushPointerUp);
  }

  // 文字层异步挂载，不挡首屏
  void (async () => {
    let selectable = false;
    try {
      const textContent = await pdfPage.getTextContent();
      if (token !== renderToken) return;
      selectable = countTextItems(textContent) > 0;
      if (selectable && pdfjsLib?.TextLayer && pageWrap === wrap) {
        const layer = document.createElement('div');
        layer.className = 'textLayer';
        layer.style.setProperty('--scale-factor', String(viewport.scale));
        wrap.appendChild(layer);
        const textLayer = new pdfjsLib.TextLayer({
          textContentSource: textContent,
          container: layer,
          viewport,
        });
        activeTextLayer = textLayer;
        await textLayer.render();
        if (token !== renderToken) {
          textLayer.cancel();
          return;
        }
      }
    } catch {
      selectable = false;
    }
    if (token !== renderToken) return;
    hasSelectableText.value = selectable;
    emit('selectable-change', selectable, n);
  })();
}

async function open(src: string) {
  if (!src) return;
  loading.value = true;
  error.value = '';
  pdfDoc = null;
  page.value = 1;
  pageInput.value = 1;
  pageCount.value = 0;
  basePageWidth = 0;
  basePageHeight = 0;
  hasSelectableText.value = true;
  pageCanvas = null;
  pageWrap = null;
  drawCanvas = null;
  try {
    pdfjsLib = await loadPdfJs();
    const task = pdfjsLib.getDocument({
      url: src,
      // 官方：disableAutoFetch 需同时 disableStream，才会真正按 Range 按需拉取
      rangeChunkSize: 65536,
      disableAutoFetch: true,
      disableStream: true,
    });
    pdfDoc = await task.promise;
    pageCount.value = pdfDoc.numPages || 0;
    await renderPage(1);
    emit('page-change', 1);
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'PDF 加载失败';
    loading.value = false;
  }
}

async function go(delta: number) {
  const next = Math.min(pageCount.value, Math.max(1, page.value + delta));
  if (next === page.value) return;
  page.value = next;
  pageInput.value = next;
  await renderPage(next);
  emit('page-change', next);
}

async function jumpToPage() {
  const n = Math.min(pageCount.value, Math.max(1, Number(pageInput.value) || 1));
  pageInput.value = n;
  if (n === page.value) return;
  page.value = n;
  await renderPage(n);
  emit('page-change', n);
}

function zoomBy(delta: number) {
  fitMode.value = 'manual';
  scale.value = Math.min(4, Math.max(0.5, Math.round((scale.value + delta) * 100) / 100));
  void renderPage(page.value);
}

function setFit(mode: FitMode) {
  fitMode.value = mode;
  void renderPage(page.value);
}

function onMouseUp() {
  if (brushMode.value !== 'none') return;
  const sel = window.getSelection?.()?.toString().trim() || '';
  if (sel.length >= 1) emit('text-select', sel, page.value);
}

function onKey(ev: KeyboardEvent) {
  const tag = (ev.target as HTMLElement)?.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA') return;
  if (ev.key === 'Escape' && brushMode.value !== 'none') {
    brushMode.value = 'none';
    clearBrushStroke();
    updateOverlayPointer();
    return;
  }
  if (ev.key === 'ArrowLeft' || ev.key === 'PageUp') {
    ev.preventDefault();
    void go(-1);
  } else if (ev.key === 'ArrowRight' || ev.key === 'PageDown') {
    ev.preventDefault();
    void go(1);
  }
}

watch(
  () => props.src,
  (s) => {
    void open(s);
  },
  { immediate: true },
);

onMounted(() => {
  window.addEventListener('keydown', onKey);
  if (hostRef.value) {
    resizeObs = new ResizeObserver(() => {
      if (fitMode.value !== 'manual' && pdfDoc) void renderPage(page.value);
    });
    resizeObs.observe(hostRef.value);
  }
});

onBeforeUnmount(() => {
  renderToken += 1;
  activeTextLayer?.cancel();
  activeTextLayer = null;
  pdfDoc = null;
  pageCanvas = null;
  pageWrap = null;
  drawCanvas = null;
  resizeObs?.disconnect();
  window.removeEventListener('keydown', onKey);
});
</script>

<template>
  <div ref="rootRef" class="flex h-full min-h-0 flex-col bg-slate-950">
    <div class="flex flex-wrap items-center gap-2 border-b border-white/10 px-3 py-2 text-[11px] text-slate-300">
      <button type="button" class="rounded border border-white/15 px-2 py-0.5 disabled:opacity-40" :disabled="page <= 1" @click="go(-1)">
        上一页
      </button>
      <input
        v-model.number="pageInput"
        type="number"
        min="1"
        :max="pageCount || 1"
        class="w-14 rounded border border-white/15 bg-black/40 px-1 py-0.5 text-center tabular-nums"
        @change="jumpToPage"
        @keyup.enter="jumpToPage"
      />
      <span class="tabular-nums">/ {{ pageCount || '—' }}</span>
      <button
        type="button"
        class="rounded border border-white/15 px-2 py-0.5 disabled:opacity-40"
        :disabled="page >= pageCount"
        @click="go(1)"
      >
        下一页
      </button>
      <button type="button" class="rounded border border-white/15 px-2 py-0.5" @click="zoomBy(-0.1)">缩小</button>
      <button type="button" class="rounded border border-white/15 px-2 py-0.5" @click="zoomBy(0.1)">放大</button>
      <button
        type="button"
        class="rounded border px-2 py-0.5"
        :class="fitMode === 'width' ? 'border-[rgb(var(--lz-accent)/0.5)] bg-[rgb(var(--lz-accent)/0.2)] text-white' : 'border-white/15'"
        @click="setFit('width')"
      >
        适应宽度
      </button>
      <button
        type="button"
        class="rounded border px-2 py-0.5"
        :class="fitMode === 'page' ? 'border-[rgb(var(--lz-accent)/0.5)] bg-[rgb(var(--lz-accent)/0.2)] text-white' : 'border-white/15'"
        @click="setFit('page')"
      >
        适应页高
      </button>
      <span class="mx-0.5 h-3 w-px bg-white/15" />
      <button
        type="button"
        class="rounded border px-2 py-0.5"
        :class="brushMode === 'smear' ? 'border-amber-400/60 bg-amber-500/25 text-amber-50' : 'border-white/15'"
        title="涂抹笔：涂过的区域松手后预览，点「问伴学」提问"
        @click="setBrushMode('smear')"
      >
        涂抹笔
      </button>
      <button
        type="button"
        class="rounded border px-2 py-0.5"
        :class="brushMode === 'circle' ? 'border-sky-400/60 bg-sky-500/25 text-sky-50' : 'border-white/15'"
        title="圈选笔：圈内区域松手后预览，点「问伴学」提问"
        @click="setBrushMode('circle')"
      >
        圈选笔
      </button>
      <span class="tabular-nums text-slate-500">{{ Math.round(scale * 100) }}%</span>
      <span v-if="loading" class="text-slate-500">加载中…</span>
      <span v-if="error" class="text-amber-200">{{ error }}</span>
      <span v-else-if="brushMode !== 'none'" class="text-sky-200/90">
        {{ brushMode === 'smear' ? '涂抹后松手预览，点「问伴学」提问' : '拖出椭圆圈后松手预览，点「问伴学」提问' }}（Esc 取消）
      </span>
      <span v-else-if="!loading && !hasSelectableText" class="text-amber-200/90">本页无可选文字 · 请用画笔框选</span>
    </div>
    <div ref="hostRef" class="relative min-h-0 flex-1 overflow-auto p-2" @mouseup="onMouseUp" />
  </div>
</template>

<style>
/* pdf.js TextLayer — 与 canvas 对齐的透明可选文字层 */
.pdf-page .textLayer {
  position: absolute;
  inset: 0;
  overflow: clip;
  opacity: 1;
  line-height: 1;
  text-align: initial;
  -webkit-text-size-adjust: none;
  text-size-adjust: none;
  transform-origin: 0 0;
  z-index: 1;
  pointer-events: auto;
}

.pdf-page .textLayer :is(span, br) {
  color: transparent;
  position: absolute;
  white-space: pre;
  cursor: text;
  transform-origin: 0% 0%;
}

.pdf-page .textLayer ::selection {
  background: rgba(99, 102, 241, 0.35);
}

.pdf-page .textLayer ::-moz-selection {
  background: rgba(99, 102, 241, 0.35);
}

.pdf-page .textLayer .endOfContent {
  display: block;
  position: absolute;
  inset: 100% 0 0;
  z-index: 0;
  cursor: default;
  user-select: none;
}

.pdf-page .textLayer.selecting .endOfContent {
  top: 0;
}

.pdf-page .pdf-brush-layer {
  position: absolute;
  inset: 0;
  z-index: 2;
  touch-action: none;
}
</style>

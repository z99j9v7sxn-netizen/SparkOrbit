<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import {
  explainMistakeTutor,
  fetchSavedDigitalTutor,
  fetchSavedMistakeTutor,
  startDigitalTutor,
  type DigitalTutorCitation,
  type DigitalTutorTask,
  type MistakeSlide,
  type MistakeTutorPayload,
} from '../../api/digitalTutor';
import { useOrbitStore } from '../../stores/orbit';
import { useAvatarVms } from '../../composables/useAvatarVms';
import SlideDeckStage from './SlideDeckStage.vue';
import { LzBadge, LzButton, LzEmptyState, LzSkeleton, LzTextarea } from './ui';

const props = defineProps<{
  planetSlug?: string;
  planetName?: string;
  autoStart?: boolean;
  /** 错题上下文：有则进入错题讲因模式 */
  mistake?: MistakeTutorPayload | null;
}>();

const orbit = useOrbitStore();
const vms = useAvatarVms();
const vmsWrapperRef = ref<HTMLDivElement | null>(null);
const vmsBusy = ref(false);
const live = computed(() => vms.enabled.value && vms.status.value === 'live');
const vmsStatus = computed(() => vms.status.value);
const vmsStatusText = computed(() => vms.statusText.value);
const vmsNeedGesture = computed(() => vms.needGesture.value);

const slug = computed(
  () => props.mistake?.planet_slug || props.planetSlug || orbit.selectedPlanet?.slug || '',
);
const name = computed(() => {
  if (props.mistake?.question) {
    const q = props.mistake.question.trim();
    return q.length > 28 ? `${q.slice(0, 28)}…` : q;
  }
  return props.planetName || orbit.selectedPlanet?.name || slug.value || '错题讲解';
});
const isMistakeMode = computed(() => !!props.mistake?.question);

const prompt = ref('');
const loading = ref(false);
const loadingSaved = ref(false);
const task = ref<DigitalTutorTask | null>(null);
const error = ref('');
const progressHint = ref('');
const waitedSec = ref(0);
const slideIndex = ref(0);
const explaining = ref(false);
const explainPaused = ref(false);
let abortPoll = false;
let abortExplain = false;
/** 讲解轮次 token：停止后立刻再开讲时作废旧循环，避免叠播 */
let explainGen = 0;
let waitTimer: ReturnType<typeof setInterval> | null = null;
let loadSeq = 0;

const slides = computed<MistakeSlide[]>(() => {
  const list = task.value?.slides;
  return Array.isArray(list) ? list.filter((s) => s && (s.title || s.narration)) : [];
});
const hasSlides = computed(() => slides.value.length > 0);
const citations = computed<DigitalTutorCitation[]>(() => task.value?.citations || []);
const hasVideo = computed(() => !!task.value?.video_url);
const isCached = computed(
  () =>
    !!task.value?.cached ||
    (!!task.value?.slides && task.value.slides.length > 0 && task.value?.status === 'succeeded') ||
    (!!task.value?.video_url && task.value?.status === 'succeeded'),
);
const statusLabel = computed(() => {
  const st = (task.value?.status || '').toLowerCase();
  if (loading.value && (st === 'processing' || st === 'queued' || !st)) return '分析中';
  if (explaining.value) return '讲解中';
  if (st === 'succeeded') return isCached.value ? '已缓存' : '已完成';
  if (st === 'fallback') return '文案兜底';
  if (st === 'failed' || st === 'error') return '失败';
  if (st === 'empty') return '未生成';
  return task.value?.message || '待开始';
});

const waitLabel = computed(() => {
  if (!loading.value) return '';
  const m = Math.floor(waitedSec.value / 60);
  const s = waitedSec.value % 60;
  return m > 0 ? `已等待 ${m} 分 ${s} 秒` : `已等待 ${s} 秒`;
});

function clearWaitTimer() {
  if (waitTimer) {
    clearInterval(waitTimer);
    waitTimer = null;
  }
}

function startWaitTimer() {
  clearWaitTimer();
  waitedSec.value = 0;
  waitTimer = setInterval(() => {
    waitedSec.value += 1;
  }, 1000);
}

function estimateSpeakMs(text: string) {
  const n = text.replace(/\s+/g, '').length;
  // 中文约 3.5 字/秒，最少 2.8s，最多 28s
  return Math.min(28000, Math.max(2800, Math.round((n / 3.5) * 1000) + 600));
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, ms);
  });
}

/** 可被暂停/停止打断的等待；暂停时挂起，停止时提前结束 */
async function interruptibleSpeakWait(ms: number, gen: number) {
  const deadline = Date.now() + ms;
  while (Date.now() < deadline) {
    if (gen !== explainGen || abortExplain) return;
    while (explainPaused.value && !abortExplain && gen === explainGen) {
      await sleep(200);
    }
    if (gen !== explainGen || abortExplain) return;
    await sleep(Math.min(200, Math.max(0, deadline - Date.now())));
  }
}

async function ensureLiveVms() {
  if (live.value) return true;
  await nextTick();
  if (!vmsWrapperRef.value) throw new Error('虚拟人容器未就绪');
  vmsWrapperRef.value.style.height = '420px';
  vmsWrapperRef.value.style.minHeight = '420px';
  await vms.enable(vmsWrapperRef.value);
  return live.value;
}

async function loadSaved() {
  const seq = ++loadSeq;
  loadingSaved.value = true;
  error.value = '';
  try {
    let saved: DigitalTutorTask | null = null;
    if (isMistakeMode.value && props.mistake?.mistake_id) {
      saved = await fetchSavedMistakeTutor(props.mistake.mistake_id);
    } else if (!isMistakeMode.value && slug.value) {
      saved = await fetchSavedDigitalTutor(slug.value);
    }
    if (seq !== loadSeq) return;
    const hasPlanetSlides = Array.isArray(saved?.slides) && (saved?.slides?.length || 0) > 0;
    if (
      saved &&
      saved.status === 'succeeded' &&
      ((isMistakeMode.value && Array.isArray(saved.slides) && saved.slides.length > 0) ||
        hasPlanetSlides ||
        saved.video_url)
    ) {
      task.value = saved;
      slideIndex.value = 0;
      progressHint.value =
        saved.message ||
        (isMistakeMode.value || hasPlanetSlides ? '已加载分镜讲稿缓存' : '已加载缓存视频');
    } else {
      task.value = null;
      progressHint.value = isMistakeMode.value
        ? '本题尚无分镜缓存，点「生成并讲解」即可即时分析'
        : '本行星尚无分镜缓存，点「生成并讲解」即可即时出稿';
    }
  } catch (e) {
    if (seq !== loadSeq) return;
    task.value = null;
    progressHint.value = '';
    error.value = e instanceof Error ? e.message : '读取缓存失败';
  } finally {
    if (seq === loadSeq) loadingSaved.value = false;
  }
}

async function playSlidesWithVms(fromIndex = 0) {
  if (!hasSlides.value) {
    error.value = '暂无分镜可讲解';
    return;
  }
  const gen = ++explainGen;
  abortExplain = false;
  explainPaused.value = false;
  explaining.value = true;
  error.value = '';
  try {
    if (!live.value) {
      progressHint.value = '正在开启实时虚拟人…';
      vmsBusy.value = true;
      try {
        await ensureLiveVms();
      } finally {
        vmsBusy.value = false;
      }
      if (!live.value) {
        progressHint.value = '虚拟人未就绪，可手动开启后点「继续讲解」';
        return;
      }
    }
    for (let i = Math.max(0, fromIndex); i < slides.value.length; i++) {
      if (gen !== explainGen || abortExplain) break;
      while (explainPaused.value && !abortExplain && gen === explainGen) {
        await sleep(200);
      }
      if (gen !== explainGen || abortExplain) break;
      slideIndex.value = i;
      const slide = slides.value[i];
      const line = (slide.narration || slide.title || '').trim();
      progressHint.value = `正在讲解第 ${i + 1}/${slides.value.length} 幕：${slide.title || ''}`;
      if (line && live.value) {
        try {
          await vms.speak(line);
        } catch (e) {
          error.value = e instanceof Error ? e.message : '虚拟人播报失败';
        }
      }
      if (gen !== explainGen || abortExplain) break;
      await interruptibleSpeakWait(estimateSpeakMs(line || slide.title || ''), gen);
    }
    if (gen === explainGen && !abortExplain) {
      progressHint.value = '本轮分镜讲解已完成';
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '同步讲解失败';
  } finally {
    if (gen === explainGen) {
      explaining.value = false;
    }
  }
}

function stopExplain() {
  explainGen += 1;
  abortExplain = true;
  explainPaused.value = false;
  explaining.value = false;
  progressHint.value = '已停止讲解';
  void vms.interrupt();
}

function pauseExplain() {
  explainPaused.value = true;
  progressHint.value = '讲解已暂停';
  void vms.interrupt();
}

function resumeExplain() {
  if (!hasSlides.value) return;
  if (explaining.value) {
    explainPaused.value = false;
    progressHint.value = '继续讲解…';
    return;
  }
  void playSlidesWithVms(slideIndex.value);
}

async function generateMistake(force = false) {
  if (loading.value || !props.mistake?.question) return;
  if (!force && hasSlides.value) {
    progressHint.value = '已有分镜讲稿；将直接开始同步讲解。如需重分析请点「重新分析」';
    void playSlidesWithVms(0);
    return;
  }
  loading.value = true;
  error.value = '';
  explainGen += 1;
  abortExplain = true;
  explainPaused.value = false;
  void vms.interrupt();
  progressHint.value = force ? '正在重新分析错题分镜…' : 'DeepSeek 正在分析错题并生成分镜讲稿…';
  if (force) {
    task.value = null;
    slideIndex.value = 0;
  }
  startWaitTimer();
  try {
    const started = await explainMistakeTutor(
      {
        ...props.mistake,
        note: [props.mistake.note, prompt.value.trim()].filter(Boolean).join('；'),
        planet_slug: props.mistake.planet_slug || slug.value,
      },
      { force },
    );
    task.value = started;
    slideIndex.value = 0;
    if (!started.slides?.length) {
      error.value = started.error || '未生成分镜';
      progressHint.value = started.message || '分析失败';
      return;
    }
    progressHint.value = started.message || '分镜已就绪，开始同步讲解';
    clearWaitTimer();
    loading.value = false;
    await playSlidesWithVms(0);
  } catch (e) {
    error.value = e instanceof Error ? e.message : '错题分析失败';
    progressHint.value = '分析失败，请稍后重试';
  } finally {
    loading.value = false;
    clearWaitTimer();
  }
}

async function generatePlanet(force = false) {
  if (loading.value || !slug.value) return;
  if (!force && hasSlides.value) {
    progressHint.value = '已有分镜讲稿；将直接开始同步讲解。如需重分析请点「重新分析」';
    void playSlidesWithVms(0);
    return;
  }
  loading.value = true;
  error.value = '';
  explainGen += 1;
  abortExplain = true;
  explainPaused.value = false;
  void vms.interrupt();
  progressHint.value = force ? '正在重新生成行星分镜…' : '正在检索校本资料并生成分镜讲稿…';
  if (force) {
    task.value = null;
    slideIndex.value = 0;
  }
  startWaitTimer();
  try {
    const started = await startDigitalTutor(slug.value, prompt.value.trim(), { force });
    task.value = started;
    slideIndex.value = 0;
    if (!started.slides?.length) {
      // 兼容旧缓存仅有讲稿/视频
      if (started.script) {
        progressHint.value = started.message || '讲稿已就绪，可开启虚拟人后点「读讲稿」';
        return;
      }
      error.value = started.error || '未生成分镜';
      progressHint.value = started.message || '分析失败';
      return;
    }
    progressHint.value = started.message || '分镜已就绪，开始同步讲解';
    clearWaitTimer();
    loading.value = false;
    await playSlidesWithVms(0);
  } catch (e) {
    error.value = e instanceof Error ? e.message : '行星讲解失败';
    progressHint.value = '分析失败，请稍后重试';
  } finally {
    loading.value = false;
    clearWaitTimer();
  }
}

async function generate(force = false) {
  if (isMistakeMode.value) return generateMistake(force);
  return generatePlanet(force);
}

async function toggleLiveVms() {
  if (vmsBusy.value) return;
  vmsBusy.value = true;
  try {
    if (live.value || vms.enabled.value) {
      stopExplain();
      await vms.disable('已关闭实时虚拟人');
      return;
    }
    await ensureLiveVms();
  } catch (e) {
    error.value = e instanceof Error ? e.message : '实时虚拟人连接失败';
  } finally {
    vmsBusy.value = false;
  }
}

async function speakScriptLive() {
  const script = (task.value?.script || '').trim();
  if (!script) {
    error.value = '暂无讲稿可播报';
    return;
  }
  if (!live.value) {
    error.value = '请先开启实时虚拟人';
    return;
  }
  try {
    await vms.speak(script);
  } catch (e) {
    error.value = e instanceof Error ? e.message : '虚拟人播报失败';
  }
}

async function onManualSlide(n: number) {
  slideIndex.value = n;
  if (!explaining.value && live.value) {
    const slide = slides.value[n];
    if (slide?.narration) {
      try {
        await vms.speak(slide.narration);
      } catch {
        /* ignore */
      }
    }
  }
}

watch(
  () => [slug.value, props.mistake?.mistake_id, props.mistake?.question] as const,
  async () => {
    abortPoll = true;
    explainGen += 1;
    abortExplain = true;
    explainPaused.value = false;
    void vms.interrupt();
    clearWaitTimer();
    loading.value = false;
    task.value = null;
    slideIndex.value = 0;
    if (vms.enabled.value) {
      await vms.disable('已切换题目，断开虚拟人');
    }
    await loadSaved();
    const current = task.value as DigitalTutorTask | null;
    const ready = Boolean(current && current.slides && current.slides.length > 0);
    if (props.autoStart && !ready && (isMistakeMode.value || slug.value)) {
      abortPoll = false;
      void generate(false);
    }
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  abortPoll = true;
  abortExplain = true;
  clearWaitTimer();
  void vms.disable('离开讲因面板，已断开虚拟人');
});
</script>

<template>
  <div class="digital-tutor space-y-4">
    <header class="space-y-1">
      <p class="lz-caption lz-accent-text uppercase tracking-[0.28em]">Digital Tutor</p>
      <h3 class="lz-title">
        {{ isMistakeMode ? '错题同步讲解' : '虚拟人讲解' }} · {{ name }}
      </h3>
      <p class="lz-desc">
        <template v-if="isMistakeMode">
          DeepSeek 分析出分镜讲稿，实时虚拟人朗读，GSAP 分镜同屏切换——无需等待短视频。
        </template>
        <template v-else>
          基于校本资料即时生成分镜讲稿，实时虚拟人朗读并切幕——无需等待短视频。多轮对话请用「对话伴学」。
        </template>
      </p>
    </header>

    <div v-if="isMistakeMode && mistake" class="rounded-[var(--radius-ctl)] border border-rose-400/20 bg-rose-500/5 px-3 py-2 text-xs text-slate-300">
      <p><span class="text-rose-200">你的作答：</span>{{ mistake.student_answer || '未作答' }}</p>
      <p class="mt-1"><span class="text-emerald-200">正解：</span>{{ mistake.correct_answer || '见解析' }}</p>
    </div>

    <div class="space-y-2">
      <LzTextarea
        v-model="prompt"
        :rows="2"
        :placeholder="isMistakeMode ? '可选：补充错因备注（重新分析时生效）' : `可选侧重，例如「用例子讲清 ${name}」`"
        :disabled="loading || explaining"
      />
      <div class="flex flex-wrap gap-2">
        <LzButton
          variant="primary"
          size="lg"
          class="min-w-[9rem] flex-1"
          :disabled="loadingSaved || explaining || (!isMistakeMode && !slug) || (isMistakeMode && !mistake?.question)"
          :loading="loading"
          @click="generate(false)"
        >
          <template v-if="loading">{{ isMistakeMode ? '分析中…' : '生成分镜中…' }}</template>
          <template v-else-if="isMistakeMode">
            {{ hasSlides ? '开始讲解' : '生成并讲解' }}
          </template>
          <template v-else>
            {{ hasSlides ? '开始讲解' : '生成并讲解' }}
          </template>
        </LzButton>
        <LzButton
          v-if="hasSlides"
          variant="soft"
          size="lg"
          :disabled="loading || explaining || (!isMistakeMode && !slug)"
          @click="generate(true)"
        >
          重新分析
        </LzButton>
      </div>
      <p v-if="!isMistakeMode && !slug" class="text-[11px] text-amber-200/90">请先选择行星，或从错题本打开本题讲解。</p>
      <LzSkeleton v-if="loadingSaved" preset="text" :rows="2" />
      <p v-if="progressHint" class="lz-caption lz-accent-text">
        {{ progressHint }}
        <span v-if="waitLabel" class="ml-2 text-slate-400">{{ waitLabel }}</span>
      </p>
      <p v-if="error" class="rounded-[var(--radius-ctl)] border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
        {{ error }}
      </p>
    </div>

    <section class="lz-card space-y-2 p-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p class="lz-subtitle flex flex-wrap items-center gap-2">
            实时虚拟人 · 分镜同步
            <LzBadge :tone="statusLabel === '失败' ? 'danger' : statusLabel === '已完成' || statusLabel === '已缓存' ? 'success' : 'accent'">
              {{ statusLabel }}
            </LzBadge>
          </p>
          <p class="lz-caption mt-0.5">{{ vmsStatusText }}</p>
        </div>
        <div class="flex flex-wrap gap-2">
          <LzButton
            :variant="live ? 'ghost' : 'primary'"
            size="sm"
            :disabled="vmsBusy || vmsStatus === 'connecting'"
            :loading="vmsBusy || vmsStatus === 'connecting'"
            @click="toggleLiveVms"
          >
            {{ vmsBusy || vmsStatus === 'connecting' ? '连接中…' : live ? '关闭虚拟人' : '开启虚拟人' }}
          </LzButton>
          <LzButton
            v-if="explaining && !explainPaused"
            variant="ghost"
            size="sm"
            @click="pauseExplain"
          >
            暂停
          </LzButton>
          <LzButton
            v-if="hasSlides && (!explaining || explainPaused)"
            variant="soft"
            size="sm"
            :disabled="loading"
            @click="resumeExplain"
          >
            {{ explainPaused ? '继续讲解' : '从当前幕讲解' }}
          </LzButton>
          <LzButton
            v-if="explaining"
            variant="danger"
            size="sm"
            @click="stopExplain"
          >
            停止
          </LzButton>
          <LzButton
            v-if="!hasSlides && task?.script"
            variant="soft"
            size="sm"
            :disabled="!live"
            @click="speakScriptLive"
          >
            读讲稿
          </LzButton>
        </div>
      </div>

      <div class="grid gap-3 lg:grid-cols-2">
        <div
          ref="vmsWrapperRef"
          class="vms-stage relative h-[420px] w-full overflow-hidden rounded-xl border border-white/10 bg-[#0b1220]"
          @click="vmsNeedGesture && vms.resumePlayback()"
        >
          <div
            v-if="!live && vmsStatus !== 'connecting'"
            class="pointer-events-none absolute inset-0 z-[1] flex items-center justify-center text-xs text-slate-400"
          >
            开启后将在此显示虚拟人形象
          </div>
          <button
            v-if="vmsNeedGesture"
            type="button"
            class="absolute inset-0 z-10 flex items-center justify-center bg-black/55 text-sm text-white"
            @click.stop="vms.resumePlayback()"
          >
            点击此处开启虚拟人画面与声音
          </button>
        </div>

        <div class="min-h-[180px]">
          <SlideDeckStage
            v-if="hasSlides"
            :index="slideIndex"
            :slides="slides"
            :autoplay="false"
            :speak-narration="false"
            @update:index="onManualSlide"
          />
          <div v-else class="lz-card lz-card--flat flex min-h-[180px] items-center justify-center">
            <LzEmptyState icon="🎬" title="暂无分镜" desc="生成分镜后将在此同步切换" />
          </div>
          <p v-if="task?.summary" class="lz-caption mt-2">
            {{ task.summary }}
          </p>
        </div>
      </div>
      <p class="lz-caption">
        旁白仅由实时虚拟人朗读；分镜动画静音，随讲切换。关闭虚拟人或返回列表将断开连接并停止计费。
      </p>
    </section>

    <!-- 校本引用（行星） / 错题题干 -->
    <div v-if="!isMistakeMode && task && (citations.length || task.script)" class="grid gap-3 lg:grid-cols-[1.2fr_0.8fr]">
      <section v-if="task.script" class="lz-card lz-card--flat p-3">
        <p class="lz-caption uppercase tracking-wider">汇总讲稿</p>
        <p class="mt-1.5 whitespace-pre-wrap text-sm leading-6 text-slate-100">{{ task.script }}</p>
      </section>
      <aside class="lz-card p-3">
        <p class="lz-subtitle">校本引用</p>
        <p class="lz-caption mt-1">讲解依据，便于核对页码</p>
        <ul v-if="citations.length" class="mt-3 space-y-2">
          <li
            v-for="(c, i) in citations"
            :key="i"
            class="lz-card lz-card--flat px-2.5 py-2"
          >
            <p class="lz-caption lz-accent-text font-semibold">{{ c.citation || c.book || `引用 ${i + 1}` }}</p>
            <p class="lz-caption mt-1">{{ c.snippet || c.text }}</p>
          </li>
        </ul>
        <LzEmptyState v-else icon="📚" title="暂无引用片段" desc="生成讲解后会在此列出校本依据" />
      </aside>
    </div>

    <aside
      v-if="isMistakeMode && mistake"
      class="lz-card p-3"
    >
      <p class="lz-subtitle">错题题干</p>
      <p class="lz-card lz-card--flat mt-2 px-2.5 py-2 text-[11px] leading-5 text-slate-300">
        {{ mistake.question }}
      </p>
      <div v-if="task?.script" class="mt-3">
        <p class="lz-caption uppercase tracking-wider">汇总讲稿</p>
        <p class="mt-1.5 whitespace-pre-wrap text-sm leading-6 text-slate-100">{{ task.script }}</p>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.vms-stage,
.vms-stage :deep(#xvideo) {
  width: 100% !important;
  height: 420px !important;
  min-height: 420px !important;
  position: relative !important;
}
.vms-stage :deep(video),
.vms-stage :deep(canvas) {
  width: 100% !important;
  height: 100% !important;
  object-fit: contain !important;
  background: #0b1220 !important;
}
</style>

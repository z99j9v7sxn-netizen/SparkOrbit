<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { companionChat, type TutorSourceRef } from '../../api/orbit';
import { synthesizeSpeech } from '../../api/tts';
import { executeNextAction, type NextAction } from '../../lib/executeNextAction';
import { useOrbitStore } from '../../stores/orbit';
import { useVoiceInput } from '../../composables/useVoiceInput';
import MarkdownView from '../common/MarkdownView.vue';
import DigitalTutorPanel from './DigitalTutorPanel.vue';
import TutorAvatarStage from './TutorAvatarStage.vue';
import { LzBadge, LzButton, LzEmptyState, LzSkeleton, LzTabs, LzTextarea } from './ui';

const props = defineProps<{
  planetSlug?: string;
  planetName?: string;
  initialMode?: 'feynman' | 'socratic';
  initialTab?: 'chat' | 'avatar';
}>();

const orbit = useOrbitStore();
const slug = computed(() => props.planetSlug || orbit.selectedPlanet?.slug || '');
const name = computed(
  () => props.planetName || orbit.selectedPlanet?.name || slug.value || '当前知识点',
);

const labTab = ref<'chat' | 'avatar'>(props.initialTab === 'avatar' ? 'avatar' : 'chat');
watch(
  () => props.initialTab,
  (t) => {
    if (t === 'avatar' || t === 'chat') labTab.value = t;
  },
);

const feynmanMode = ref(props.initialMode === 'feynman');
const socraticMode = ref(props.initialMode !== 'feynman');
watch(
  () => props.initialMode,
  (m) => {
    if (m === 'feynman') {
      feynmanMode.value = true;
      socraticMode.value = false;
    } else if (m === 'socratic') {
      feynmanMode.value = false;
      socraticMode.value = true;
    }
  },
);

type TutorMessage = {
  role: 'user' | 'tutor';
  content: string;
  sources?: TutorSourceRef[];
  supervised?: boolean;
  next_actions?: NextAction[];
};
const messages = ref<TutorMessage[]>([]);
const question = ref('');
const loading = ref(false);
const speakReply = ref(true);
const voiceHint = ref('');
const actionTip = ref('');
const avatarRef = ref<InstanceType<typeof TutorAvatarStage> | null>(null);

const { hint: asrHint, listening, start: startVoice, stop: stopVoice } = useVoiceInput();

function wantsSupervise(_text: string, isFeynman: boolean) {
  // 非费曼默认走 supervisor，保证伴学可在观测里看到层级统筹
  return !isFeynman;
}

const placeholder = computed(() => {
  if (messages.value.length) return '继续回答教练的问题…';
  if (feynmanMode.value) return `用自己的话讲解「${name.value}」…`;
  return `例如：我卡在「${name.value}」——能先问我一个启发问题吗？`;
});

const latestSources = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i -= 1) {
    const m = messages.value[i];
    if (m.role === 'tutor' && m.sources?.length) return m.sources;
  }
  return [] as TutorSourceRef[];
});

async function speak(text: string) {
  if (!speakReply.value || !text.trim()) return;
  const stage = avatarRef.value;
  if (stage && 'speakText' in stage && typeof stage.speakText === 'function') {
    await stage.speakText(text);
    return;
  }
  if (stage) {
    const liveOk = await stage.speakLive(text);
    if (liveOk) return;
  }
  try {
    const blob = await synthesizeSpeech(text);
    if (stage) {
      await stage.playAudio(blob);
      return;
    }
  } catch {
    // fallback
  }
  stage?.speakWithBrowser(text);
}

async function ask(textOverride?: string) {
  const text = (textOverride ?? question.value).trim();
  if (!text || loading.value) return;
  messages.value.push({ role: 'user', content: text });
  question.value = '';
  loading.value = true;
  try {
    const mode = feynmanMode.value ? 'feynman' : 'tutor';
    const supervise = wantsSupervise(text, mode === 'feynman');
    const res = await companionChat(
      text,
      mode,
      slug.value || undefined,
      socraticMode.value && !feynmanMode.value,
      supervise,
    );
    messages.value.push({
      role: 'tutor',
      content: res.reply,
      sources: res.sources || [],
      supervised: supervise,
      next_actions: res.next_actions || [],
    });
    if (mode === 'feynman' && typeof res.explain_score === 'number') {
      orbit.setExplainScore(slug.value || '', res.explain_score);
    }
    void speak(res.reply);
  } catch {
    messages.value.push({ role: 'tutor', content: '答疑服务暂不可用，请稍后再试。' });
  } finally {
    loading.value = false;
  }
}

function runNextAction(action: NextAction) {
  void executeNextAction(action, {
    planetSlug: slug.value,
    onFeynman: () => {
      feynmanMode.value = true;
      socraticMode.value = false;
    },
    onAsk: (text) => void ask(text),
    onTip: (msg) => {
      actionTip.value = msg;
    },
  });
}

async function toggleVoice() {
  if (listening.value) {
    stopVoice();
    voiceHint.value = '';
    return;
  }
  voiceHint.value = '请说话…';
  await startVoice((text, final) => {
    if (!text.trim()) return;
    question.value = text.trim();
    voiceHint.value = final ? '识别完成，正在提问…' : `识别中：${text}`;
    if (final) {
      stopVoice();
      void ask(text.trim());
    }
  });
}

onBeforeUnmount(() => {
  stopVoice();
  avatarRef.value?.stopAudio();
  avatarRef.value?.disconnectVms();
});
</script>

<template>
  <div class="tutor-lab space-y-4">
    <header class="space-y-2">
      <div class="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p class="lz-caption lz-accent-text uppercase tracking-[0.28em]">Tutor Lab</p>
          <h3 class="lz-title">伴学舱 · {{ name }}</h3>
        </div>
        <LzBadge :tone="feynmanMode ? 'neutral' : 'accent'">
          {{ feynmanMode ? '编排：直聊 feynman' : '编排：层级统筹 supervisor' }}
        </LzBadge>
      </div>
      <LzTabs
        :items="[
          { key: 'chat', label: '对话伴学' },
          { key: 'avatar', label: '虚拟人讲课' },
        ]"
        :model-value="labTab"
        @update:model-value="labTab = $event as 'chat' | 'avatar'"
      />
      <p class="lz-desc">
        {{
          labTab === 'chat'
            ? '多轮问答与费曼讲解。点「开启虚拟人」可连接形象口播。'
            : '行星通识实时虚拟人讲解；错题即时讲解请从「错题本」进入。'
        }}
      </p>
      <p v-if="actionTip" class="lz-caption lz-accent-text">{{ actionTip }}</p>
    </header>

    <DigitalTutorPanel
      v-if="labTab === 'avatar'"
      :planet-slug="slug"
      :planet-name="name"
      :auto-start="false"
    />

    <template v-else>
    <div class="grid gap-3 lg:grid-cols-[minmax(0,240px)_minmax(0,1fr)]">
      <TutorAvatarStage ref="avatarRef" />

      <div class="space-y-3 min-w-0">
        <div class="lz-desc flex flex-wrap items-center gap-3">
          <label class="flex items-center gap-1.5">
            <input
              v-model="feynmanMode"
              type="checkbox"
              class="rounded"
              @change="() => { if (feynmanMode) socraticMode = false; }"
            />
            费曼讲解
          </label>
          <label v-if="!feynmanMode" class="flex items-center gap-1.5">
            <input v-model="socraticMode" type="checkbox" class="rounded" />
            苏格拉底引导
          </label>
          <label class="flex items-center gap-1.5">
            <input v-model="speakReply" type="checkbox" class="rounded" />
            回复口播
          </label>
          <LzButton variant="ghost" size="sm" @click="messages = []; avatarRef?.stopAudio()">
            清空对话
          </LzButton>
        </div>

        <div v-if="messages.length" class="lz-card lz-card--flat max-h-56 space-y-2 overflow-y-auto p-3">
          <div
            v-for="(m, i) in messages"
            :key="`tm-${i}`"
            class="rounded-[var(--radius-ctl)] border px-3 py-2 text-xs leading-5"
            :class="m.role === 'user'
              ? 'ml-4 border-[rgb(var(--lz-accent)/0.35)] bg-[rgb(var(--lz-accent)/0.15)] text-slate-100'
              : 'mr-4 border-[var(--border-soft)] bg-[var(--surface-2)] text-slate-200'"
          >
            <p class="mb-1 flex flex-wrap items-center gap-2 text-[10px] font-semibold" :class="m.role === 'user' ? 'lz-accent-text' : 'text-slate-400'">
              <span>{{ m.role === 'user' ? '你' : 'Tutor' }}</span>
              <LzBadge v-if="m.role === 'tutor' && m.supervised" tone="accent">Supervisor 统筹</LzBadge>
            </p>
            <MarkdownView v-if="m.role === 'tutor'" :content="m.content" />
            <p v-else class="whitespace-pre-wrap">{{ m.content }}</p>
            <div v-if="m.role === 'tutor' && m.next_actions?.length" class="mt-2 flex flex-wrap gap-1.5">
              <LzButton
                v-for="(a, ai) in m.next_actions"
                :key="`${i}-na-${ai}`"
                variant="soft"
                size="sm"
                :disabled="loading"
                @click="runNextAction(a)"
              >
                {{ a.label || a.type }}
              </LzButton>
            </div>
          </div>
          <div v-if="loading" class="mr-4 rounded-[var(--radius-ctl)] border border-[var(--border-soft)] bg-[var(--surface-2)] px-3 py-2">
            <LzSkeleton preset="text" :rows="2" />
          </div>
        </div>
        <div v-else class="lz-card lz-card--flat">
          <LzEmptyState icon="✧" title="尚未开始对话" desc="向左侧星轨讲师提问，开始多轮伴学" />
        </div>
      </div>
    </div>

    <LzTextarea
      v-model="question"
      :rows="3"
      :placeholder="placeholder"
      :disabled="loading"
      @keydown.enter.exact.prevent="ask()"
    />

    <div class="flex flex-wrap gap-2">
      <LzButton
        variant="primary"
        size="lg"
        class="min-w-[8rem] flex-1"
        :disabled="!question.trim()"
        :loading="loading"
        @click="ask()"
      >
        {{
          loading
            ? (feynmanMode ? '点评中…' : '引导中…')
            : feynmanMode
              ? (messages.length ? '继续讲解' : '开始费曼讲解')
              : (messages.length ? (socraticMode ? '发送回答' : '继续提问') : (socraticMode ? '开始引导提问' : '向教练提问'))
        }}
      </LzButton>
      <LzButton
        :variant="listening ? 'danger' : 'soft'"
        size="lg"
        :disabled="loading"
        @click="toggleVoice"
      >
        {{ listening ? '停止录音' : '语音提问' }}
      </LzButton>
    </div>

    <p v-if="asrHint || voiceHint" class="lz-caption">{{ voiceHint || asrHint }}</p>

    <div v-if="latestSources.length" class="lz-card lz-card--flat px-3 py-2">
      <p class="lz-caption lz-accent-text font-semibold">依据来源</p>
      <ul class="mt-1 space-y-1">
        <li v-for="(s, i) in latestSources" :key="`src-${i}`" class="lz-caption">
          <span class="lz-accent-text">{{ s.knowledge_point_id || s.source }}</span>
          — {{ s.snippet }}
        </li>
      </ul>
    </div>

    <p v-if="!slug" class="text-[11px] text-amber-200/80">未选行星时仍可对话；绑定行星后引用更准。</p>
    </template>
  </div>
</template>

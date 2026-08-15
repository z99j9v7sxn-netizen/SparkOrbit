<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue';
import { companionChat } from '../api/orbit';
import { companionChatStream } from '../api/learnExtras';
import { executeNextAction, type NextAction } from '../lib/executeNextAction';
import { useOrbitStore } from '../stores/orbit';
import MarkdownView from './common/MarkdownView.vue';

interface Msg {
  role: 'me' | 'ai' | 'rescue';
  text: string;
  streaming?: boolean;
  supervised?: boolean;
  next_actions?: NextAction[];
}

const orbit = useOrbitStore();
const messages = ref<Msg[]>([
  { role: 'ai', text: '嘿，我是你的领航员～ 学累了、卡住了都可以找我聊聊。想挑战哪颗行星，也可以让我帮你打气！' },
]);
const input = ref('');
const loading = ref(false);
/** 默认走 Supervisor；勾选流式则退回直聊流（无编排落库） */
const useStream = ref(false);
const actionTip = ref('');
const listRef = ref<HTMLDivElement | null>(null);

async function scrollToBottom() {
  await nextTick();
  if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight;
}

async function send(textOverride?: string) {
  const text = (textOverride ?? input.value).trim();
  if (!text || loading.value) return;
  messages.value.push({ role: 'me', text });
  if (!textOverride) input.value = '';
  loading.value = true;
  await scrollToBottom();

  const planetSlug = orbit.selectedPlanet?.slug || '';

  if (useStream.value) {
    const idx = messages.value.length;
    messages.value.push({ role: 'ai', text: '', streaming: true });
    actionTip.value = '当前为流式直聊：无 Supervisor / next_actions';
    try {
      await companionChatStream(text, 'companion', planetSlug, (token) => {
        messages.value[idx].text += token;
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message.trim() : '';
      messages.value[idx].text = msg || '我这会儿有点走神，网络似乎不太稳，稍后再聊好吗？';
    } finally {
      messages.value[idx].streaming = false;
      loading.value = false;
      await scrollToBottom();
    }
    return;
  }

  try {
    const res = await companionChat(text, 'companion', planetSlug || undefined, true, true);
    messages.value.push({
      role: 'ai',
      text: res.reply,
      supervised: true,
      next_actions: res.next_actions || [],
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message.trim() : '';
    messages.value.push({
      role: 'ai',
      text: msg || '我这会儿有点走神，网络似乎不太稳，稍后再聊好吗？',
    });
  } finally {
    loading.value = false;
    await scrollToBottom();
  }
}

function runNextAction(action: NextAction) {
  void executeNextAction(action, {
    planetSlug: orbit.selectedPlanet?.slug || action.planet_slug || '',
    onAsk: (text) => void send(text),
    onTip: (msg) => {
      actionTip.value = msg;
    },
  });
}

onMounted(() => scrollToBottom());
</script>

<template>
  <div class="glass-strong glass-edge flex h-full flex-col rounded-3xl">
    <header class="border-b border-white/10 px-4 py-3">
      <p class="text-[10px] uppercase tracking-[0.35em] text-purple-200/70">Companion Agent</p>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="text-sm font-semibold text-white text-glow">知心领航员</h3>
        <div class="flex items-center gap-2">
          <span
            class="rounded-md border px-2 py-0.5 text-[10px]"
            :class="
              useStream
                ? 'border-white/15 bg-white/5 text-slate-400'
                : 'border-violet-400/40 bg-violet-500/15 text-violet-100'
            "
          >
            {{ useStream ? '编排：流式直聊' : '编排：层级统筹 supervisor' }}
          </span>
          <label class="flex items-center gap-1 text-[10px] text-slate-400">
            <input v-model="useStream" type="checkbox" class="rounded" />
            流式
          </label>
        </div>
      </div>
      <p v-if="actionTip" class="mt-1 text-[10px] text-violet-200">{{ actionTip }}</p>
      <p v-if="orbit.selectedPlanet" class="mt-1 text-[10px] text-slate-500">
        当前行星：{{ orbit.selectedPlanet.name }}
      </p>
    </header>
    <div ref="listRef" class="flex-1 space-y-3 overflow-auto px-4 py-3">
      <div v-for="(m, i) in messages" :key="i" class="flex" :class="m.role === 'me' ? 'justify-end' : 'justify-start'">
        <div
          class="max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-6"
          :class="m.role === 'me' ? 'bg-sky-500/20 text-sky-50' : m.role === 'rescue' ? 'border border-purple-400/30 bg-purple-500/15 text-purple-100' : 'bg-white/5 text-slate-200'"
        >
          <p v-if="m.role === 'ai' && m.supervised" class="mb-1 text-[10px] font-semibold text-violet-300">
            Supervisor 统筹
          </p>
          <MarkdownView v-if="m.role === 'ai' && m.text" :content="m.text" />
          <span v-else-if="m.role !== 'ai'">{{ m.text }}</span>
          <span v-if="m.streaming" class="ml-1 inline-block h-3 w-1 animate-pulse bg-sky-400" />
          <div v-if="m.next_actions?.length" class="mt-2 flex flex-wrap gap-1.5">
            <button
              v-for="(a, ai) in m.next_actions"
              :key="`${i}-a-${ai}`"
              type="button"
              class="rounded-lg border border-violet-400/30 bg-violet-500/10 px-2 py-1 text-[10px] text-violet-100 hover:bg-violet-500/20"
              :disabled="loading"
              @click="runNextAction(a)"
            >
              {{ a.label || a.type }}
            </button>
          </div>
        </div>
      </div>
      <p v-if="loading && !messages.some((m) => m.streaming)" class="text-xs text-slate-500">领航员正在回复…</p>
    </div>
    <div class="border-t border-white/10 p-3">
      <div class="flex gap-2">
        <input
          v-model="input"
          class="flex-1 rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 outline-none"
          placeholder="我今天学不进去了… 或：帮我规划路径"
          @keyup.enter="send()"
        />
        <button
          class="rounded-xl bg-gradient-to-r from-purple-500 to-sky-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          :disabled="loading"
          @click="send()"
        >
          发送
        </button>
      </div>
    </div>
  </div>
</template>

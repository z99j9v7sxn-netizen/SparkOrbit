<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { fetchMyFeedback, submitFeedback, type MyFeedbackItem } from '../../api/feedback';

const open = ref(false);
const category = ref('suggestion');
const content = ref('');
const submitting = ref(false);
const msg = ref('');
const msgTone = ref<'ok' | 'err'>('ok');
const mine = ref<MyFeedbackItem[]>([]);

const CATEGORIES = [
  { value: 'bug', label: '问题反馈' },
  { value: 'suggestion', label: '功能建议' },
  { value: 'content', label: '内容纠错' },
];

const STATUS_LABEL: Record<string, string> = { open: '待处理', processing: '处理中', closed: '已关闭' };

async function loadMine() {
  try {
    mine.value = await fetchMyFeedback();
  } catch {
    /* 静默失败，不打扰用户 */
  }
}

async function submit() {
  if (!content.value.trim()) return;
  submitting.value = true;
  msg.value = '';
  try {
    await submitFeedback(category.value, content.value.trim());
    msgTone.value = 'ok';
    msg.value = '感谢反馈！管理员处理后会通过站内通知回复你。';
    content.value = '';
    await loadMine();
  } catch {
    msgTone.value = 'err';
    msg.value = '提交失败，请稍后重试';
  } finally {
    submitting.value = false;
  }
}

function toggle() {
  open.value = !open.value;
  if (open.value) void loadMine();
}

onMounted(() => {
  /* 面板打开时才拉取数据 */
});
</script>

<template>
  <div class="fixed bottom-5 right-5 z-40">
    <!-- 弹出面板 -->
    <transition name="feedback-pop">
      <div
        v-if="open"
        class="absolute bottom-14 right-0 w-80 rounded-2xl border border-slate-600/40 bg-slate-900/95 p-4 shadow-2xl backdrop-blur"
      >
        <div class="flex items-center justify-between">
          <p class="text-sm font-semibold text-slate-100">意见反馈</p>
          <button type="button" class="text-slate-400 transition hover:text-slate-200" aria-label="关闭" @click="open = false">
            ✕
          </button>
        </div>

        <div class="mt-3 flex gap-1.5">
          <button
            v-for="c in CATEGORIES"
            :key="c.value"
            type="button"
            class="rounded-lg px-2.5 py-1 text-xs transition"
            :class="category === c.value ? 'bg-sky-500/25 text-sky-300' : 'bg-slate-800 text-slate-400 hover:text-slate-200'"
            @click="category = c.value"
          >
            {{ c.label }}
          </button>
        </div>

        <textarea
          v-model="content"
          rows="3"
          maxlength="2000"
          placeholder="描述你遇到的问题或建议…"
          class="mt-3 w-full resize-none rounded-xl border border-slate-600/40 bg-slate-800/70 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-500/50 focus:outline-none"
        />

        <button
          type="button"
          class="mt-2 w-full rounded-xl bg-sky-500/85 py-2 text-sm font-medium text-white transition hover:bg-sky-400 disabled:opacity-50"
          :disabled="submitting || !content.trim()"
          @click="submit"
        >
          {{ submitting ? '提交中…' : '提交反馈' }}
        </button>

        <p v-if="msg" class="mt-2 text-xs" :class="msgTone === 'ok' ? 'text-emerald-400' : 'text-rose-400'">
          {{ msg }}
        </p>

        <!-- 我的反馈 -->
        <div v-if="mine.length" class="mt-3 max-h-40 space-y-2 overflow-y-auto border-t border-slate-700/50 pt-3">
          <p class="text-[11px] font-semibold text-slate-400">我的反馈</p>
          <div v-for="item in mine" :key="item.id" class="rounded-lg bg-slate-800/60 p-2">
            <div class="flex items-center gap-2">
              <span class="line-clamp-1 flex-1 text-xs text-slate-200">{{ item.content }}</span>
              <span
                class="shrink-0 rounded px-1.5 py-0.5 text-[10px]"
                :class="item.status === 'closed' ? 'bg-emerald-500/15 text-emerald-400' : item.status === 'processing' ? 'bg-amber-500/15 text-amber-400' : 'bg-slate-600/30 text-slate-400'"
              >
                {{ STATUS_LABEL[item.status] || item.status }}
              </span>
            </div>
            <p v-if="item.reply" class="mt-1 rounded bg-sky-500/10 px-1.5 py-1 text-[11px] text-sky-300">
              回复：{{ item.reply }}
            </p>
          </div>
        </div>
      </div>
    </transition>

    <!-- 浮动按钮 -->
    <button
      type="button"
      class="flex h-11 w-11 items-center justify-center rounded-full border border-slate-600/40 bg-slate-900/90 text-slate-300 shadow-lg backdrop-blur transition hover:border-sky-500/50 hover:text-sky-300"
      :aria-label="open ? '关闭反馈面板' : '打开反馈面板'"
      @click="toggle"
    >
      <svg viewBox="0 0 16 16" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">
        <path d="M2.5 3.5h11v7.5H8.5L5.5 13.5v-2.5h-3v-7.5Z" />
        <path d="M5.5 6.2h5M5.5 8.4h3.5" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.feedback-pop-enter-active,
.feedback-pop-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.feedback-pop-enter-from,
.feedback-pop-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.97);
}
</style>

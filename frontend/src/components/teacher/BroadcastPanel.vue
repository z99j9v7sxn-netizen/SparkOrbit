<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRoute } from 'vue-router';
import { fetchBroadcasts, sendBroadcast, type BroadcastItem } from '../../api/teacher';
import {
  fetchDmConversations,
  fetchDmMessages,
  sendDm,
  type DmConversation,
  type DmMessage,
} from '../../api/teacherSuite';
import { parseApiError } from '../../api/errors';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';
import { useTeacherClassStore } from '../../stores/teacherClass';

const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);
const route = useRoute();

const activeTab = ref<'broadcast' | 'dm'>('broadcast');

// ---- 班级广播 ----
const title = ref('教师通知');
const body = ref('');
const msg = ref('');
const history = ref<BroadcastItem[]>([]);
const loading = ref(false);
const sending = ref(false);

const sortedHistory = computed(() =>
  [...history.value].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')),
);

async function load() {
  if (!classId.value) {
    history.value = [];
    return;
  }
  loading.value = true;
  try {
    history.value = await fetchBroadcasts(classId.value);
  } finally {
    loading.value = false;
  }
}

async function handleSend() {
  if (!body.value.trim() || !classId.value) return;
  msg.value = '';
  sending.value = true;
  try {
    const res = await sendBroadcast(classId.value, title.value, body.value);
    msg.value = `已发送给 ${res.recipient_count} 名学生`;
    body.value = '';
    await load();
  } catch {
    msg.value = '发送失败';
  } finally {
    sending.value = false;
  }
}

// ---- 学生私信 ----
const conversations = ref<DmConversation[]>([]);
const dmLoading = ref(false);
const activeStudentId = ref('');
const dmMessages = ref<DmMessage[]>([]);
const dmDraft = ref('');
const dmSending = ref(false);
const dmMsg = ref('');
const dmListRef = ref<HTMLDivElement | null>(null);

const activeStudent = computed(() => conversations.value.find((c) => c.student_id === activeStudentId.value) ?? null);

async function loadConversations() {
  dmLoading.value = true;
  try {
    conversations.value = await fetchDmConversations(classId.value || '');
  } catch (e) {
    dmMsg.value = parseApiError(e, '加载会话失败');
  } finally {
    dmLoading.value = false;
  }
}

async function openConversation(studentId: string) {
  activeStudentId.value = studentId;
  dmMsg.value = '';
  try {
    dmMessages.value = await fetchDmMessages(studentId);
    await nextTick();
    dmListRef.value?.scrollTo({ top: dmListRef.value.scrollHeight });
  } catch (e) {
    dmMsg.value = parseApiError(e, '加载消息失败');
  }
}

async function handleSendDm() {
  if (!dmDraft.value.trim() || !activeStudentId.value) return;
  dmSending.value = true;
  dmMsg.value = '';
  try {
    await sendDm(activeStudentId.value, dmDraft.value);
    dmDraft.value = '';
    await openConversation(activeStudentId.value);
    await loadConversations();
  } catch (e) {
    dmMsg.value = parseApiError(e, '发送失败');
  } finally {
    dmSending.value = false;
  }
}

function fmt(ts: string) {
  return ts?.slice(0, 16)?.replace('T', ' ') || '';
}

watch(classId, () => {
  void load();
  void loadConversations();
  activeStudentId.value = '';
  dmMessages.value = [];
});

onMounted(async () => {
  await Promise.all([load(), loadConversations()]);
  const target = String(route.query.student_id || '');
  if (target) {
    activeTab.value = 'dm';
    await openConversation(target);
  }
});
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="消息中心" subtitle="班级广播 + 学生一对一私信，均推送到学生端通知中心">
      <template #actions>
        <div class="t-tabs">
          <button type="button" class="t-tab" :class="{ 'is-active': activeTab === 'broadcast' }" @click="activeTab = 'broadcast'">
            班级广播
          </button>
          <button type="button" class="t-tab" :class="{ 'is-active': activeTab === 'dm' }" @click="activeTab = 'dm'">
            学生私信
          </button>
        </div>
      </template>
    </TeacherPageHeader>

    <!-- 班级广播 -->
    <div v-if="activeTab === 'broadcast'" class="grid gap-4 xl:grid-cols-2">
      <section class="t-card glass-edge p-5">
        <div class="flex items-baseline justify-between gap-2">
          <h3 class="text-[15px] font-semibold text-t-1">发送通知</h3>
          <span class="t-kicker">Broadcast</span>
        </div>
        <input v-model="title" class="t-input mt-3" placeholder="标题" />
        <textarea v-model="body" rows="6" class="t-input mt-2" placeholder="通知内容" />
        <button type="button" class="t-btn t-btn--primary t-btn--md mt-3" :disabled="sending" @click="handleSend">
          {{ sending ? '发送中…' : '发送通知' }}
        </button>
        <p v-if="msg" class="mt-2 text-xs" :class="msg.includes('失败') ? 'text-t-danger' : 'text-t-ok'">{{ msg }}</p>
      </section>

      <section class="t-card glass-edge p-5">
        <div class="flex items-baseline justify-between gap-2">
          <h3 class="text-[15px] font-semibold text-t-1">发送历史</h3>
          <span class="t-kicker">History</span>
        </div>
        <TeacherLoading v-if="loading" :rows="3" />
        <div v-else class="relative mt-3 max-h-[28rem] space-y-3 overflow-y-auto pl-4">
          <span class="absolute inset-y-1 left-1 w-px bg-t-line/15" aria-hidden="true" />
          <div v-for="h in sortedHistory" :key="h.id" class="relative rounded-xl border border-t-line/10 bg-t-s1/30 px-4 py-3">
            <span class="absolute -left-[13.5px] top-4 h-2 w-2 rounded-full bg-t-accent shadow-[0_0_8px_rgb(var(--t-accent)/0.6)]" aria-hidden="true" />
            <p class="text-sm font-medium text-t-1">{{ h.title }}</p>
            <p class="mt-1 text-xs text-t-2">{{ h.body }}</p>
            <p class="mt-1 text-[10px] text-t-3">{{ fmt(h.created_at) }} · {{ h.recipient_count }} 人</p>
          </div>
          <TeacherEmptyState v-if="!sortedHistory.length" title="暂无发送记录" />
        </div>
      </section>
    </div>

    <!-- 学生私信 -->
    <div v-else class="grid gap-4 xl:grid-cols-[minmax(260px,0.8fr)_1.4fr]">
      <section class="t-card glass-edge p-4">
        <div class="flex items-baseline justify-between gap-2">
          <h3 class="text-[15px] font-semibold text-t-1">会话列表</h3>
          <span class="t-kicker">{{ conversations.length }} 人</span>
        </div>
        <TeacherLoading v-if="dmLoading" class="mt-3" :rows="4" />
        <div v-else class="mt-3 max-h-[32rem] space-y-1.5 overflow-y-auto">
          <button
            v-for="c in conversations"
            :key="c.student_id"
            type="button"
            class="flex w-full items-center justify-between gap-2 rounded-xl border px-3 py-2.5 text-left transition"
            :class="activeStudentId === c.student_id ? 'border-t-accent/40 bg-t-accent/8' : 'border-t-line/10 bg-t-s1/30 hover:border-t-accent/25'"
            @click="openConversation(c.student_id)"
          >
            <div class="min-w-0">
              <p class="truncate text-sm font-medium text-t-1">{{ c.student_name }}</p>
              <p class="mt-0.5 truncate text-[10px] text-t-3">{{ c.last_body || '尚未发送私信' }}</p>
            </div>
            <span v-if="c.message_count" class="t-badge t-badge--neutral shrink-0">{{ c.message_count }}</span>
          </button>
          <TeacherEmptyState v-if="!conversations.length" title="班级暂无学生" />
        </div>
      </section>

      <section class="t-card glass-edge flex min-h-[420px] flex-col p-4">
        <div class="flex items-baseline justify-between gap-2">
          <h3 class="text-[15px] font-semibold text-t-1">
            {{ activeStudent ? `与 ${activeStudent.student_name} 的私信` : '选择学生开始私信' }}
          </h3>
          <span class="t-kicker">Direct Message</span>
        </div>

        <div ref="dmListRef" class="mt-3 flex-1 space-y-2 overflow-y-auto pr-1" style="max-height: 26rem">
          <div v-for="m in dmMessages" :key="m.id" class="flex" :class="m.sender_role === 'teacher' ? 'justify-end' : 'justify-start'">
            <div
              class="max-w-[78%] rounded-2xl px-3.5 py-2"
              :class="m.sender_role === 'teacher' ? 'bg-t-accent/15 text-t-1' : 'bg-t-s1/60 text-t-2'"
            >
              <p class="whitespace-pre-wrap text-sm">{{ m.body }}</p>
              <p class="mt-1 text-right text-[9px] text-t-3">{{ fmt(m.created_at) }}</p>
            </div>
          </div>
          <TeacherEmptyState v-if="activeStudentId && !dmMessages.length" title="暂无消息" description="发送第一条私信，学生将在通知中心收到" />
        </div>

        <div v-if="activeStudentId" class="mt-3 flex items-end gap-2">
          <textarea
            v-model="dmDraft"
            rows="2"
            class="t-input flex-1"
            placeholder="输入私信内容，Ctrl+Enter 发送"
            @keydown.ctrl.enter="handleSendDm"
          />
          <button type="button" class="t-btn t-btn--primary t-btn--md shrink-0" :disabled="dmSending || !dmDraft.trim()" @click="handleSendDm">
            {{ dmSending ? '发送中…' : '发送' }}
          </button>
        </div>
        <p v-if="dmMsg" class="mt-2 text-xs text-t-danger">{{ dmMsg }}</p>
      </section>
    </div>
  </div>
</template>

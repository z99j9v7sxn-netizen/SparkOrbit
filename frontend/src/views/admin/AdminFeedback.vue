<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { fetchAdminFeedback, updateAdminFeedback, type FeedbackItem } from '../../api/admin';
import { parseApiError } from '../../api/errors';
import AdminEmptyState from '../../components/admin/AdminEmptyState.vue';
import AdminPageHeader from '../../components/admin/AdminPageHeader.vue';
import AdminSkeleton from '../../components/admin/AdminSkeleton.vue';
import { relativeTime } from '../../utils/relativeTime';
import { useCountUp } from '../../composables/useCountUp';

const items = ref<FeedbackItem[]>([]);
const openCount = ref(0);
const loading = ref(true);
const msg = ref('');
const msgTone = ref<'ok' | 'err'>('ok');
const statusFilter = ref('');
const replyingId = ref('');
const replyText = ref('');
const submitting = ref(false);

const STATUS_TABS = [
  { value: '', label: '全部' },
  { value: 'open', label: '待处理' },
  { value: 'processing', label: '处理中' },
  { value: 'closed', label: '已关闭' },
];

const CATEGORY_LABEL: Record<string, string> = { bug: '问题', suggestion: '建议', content: '内容纠错' };
const CATEGORY_BADGE: Record<string, string> = {
  bug: 't-badge--danger',
  suggestion: 't-badge--info',
  content: 't-badge--warn',
};
const STATUS_LABEL: Record<string, string> = { open: '待处理', processing: '处理中', closed: '已关闭' };
const STATUS_BADGE: Record<string, string> = {
  open: 't-badge--danger',
  processing: 't-badge--warn',
  closed: 't-badge--ok',
};
const ROLE_LABEL: Record<string, string> = { student: '学生', teacher: '教师', admin: '管理员' };

const openAnim = useCountUp(computed(() => openCount.value));

async function load() {
  loading.value = true;
  msg.value = '';
  try {
    const page = await fetchAdminFeedback({ status_filter: statusFilter.value, limit: 100 });
    items.value = page.items;
    openCount.value = page.open_count;
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '加载失败');
  } finally {
    loading.value = false;
  }
}

function setStatus(value: string) {
  if (statusFilter.value === value) return;
  statusFilter.value = value;
  void load();
}

function startReply(item: FeedbackItem) {
  replyingId.value = item.id;
  replyText.value = item.reply || '';
}

async function patch(item: FeedbackItem, payload: { status?: string; reply?: string }) {
  submitting.value = true;
  try {
    const updated = await updateAdminFeedback(item.id, payload);
    items.value = items.value.map((f) => (f.id === updated.id ? updated : f));
    msgTone.value = 'ok';
    msg.value = payload.reply ? '已回复并通过站内通知送达用户' : `已更新状态为「${STATUS_LABEL[payload.status || ''] || payload.status}」`;
    replyingId.value = '';
    replyText.value = '';
    await load();
  } catch (err) {
    msgTone.value = 'err';
    msg.value = parseApiError(err, '操作失败');
  } finally {
    submitting.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="space-y-5">
    <AdminPageHeader kicker="Tickets" title="反馈工单" subtitle="学生 / 教师反馈收集、处理与回复闭环">
      <template #actions>
        <button type="button" class="t-btn t-btn--md t-btn--ghost" :disabled="loading" @click="load">
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </template>
    </AdminPageHeader>

    <div class="flex flex-wrap items-center gap-2.5">
      <div class="adm-kpi adm-kpi--warn px-4 py-3">
        <span class="text-xs text-t-2">待处理工单</span>
        <span class="ml-3 font-mono text-xl font-semibold text-t-1">{{ openAnim }}</span>
      </div>
      <div class="t-tabs ml-auto" role="tablist" aria-label="按状态筛选">
        <button
          v-for="t in STATUS_TABS"
          :key="t.value"
          type="button"
          role="tab"
          class="t-tab"
          :class="{ 'is-active': statusFilter === t.value }"
          @click="setStatus(t.value)"
        >
          {{ t.label }}
        </button>
      </div>
    </div>

    <p
      v-if="msg"
      class="rounded-xl border px-4 py-2.5 text-sm"
      :class="msgTone === 'ok' ? 'border-t-accent/20 bg-t-accent/8 text-t-accent' : 'border-t-danger/25 bg-t-danger/10 text-t-danger'"
    >
      {{ msg }}
    </p>

    <AdminSkeleton v-if="loading" :rows="5" variant="cards" />
    <AdminEmptyState v-else-if="!items.length" title="暂无反馈" hint="学生与教师可通过右下角反馈按钮提交工单" />
    <transition v-else name="fade-scale" appear>
      <div class="space-y-3">
        <article v-for="item in items" :key="item.id" class="t-card p-4">
          <div class="flex flex-wrap items-center gap-2">
            <span class="adm-avatar">{{ (item.user_name || '?').slice(0, 1).toUpperCase() }}</span>
            <span class="text-[13px] text-t-1/90">{{ item.user_name }}</span>
            <span class="t-badge t-badge--neutral">{{ ROLE_LABEL[item.role] || item.role }}</span>
            <span class="t-badge" :class="CATEGORY_BADGE[item.category] || 't-badge--neutral'">
              {{ CATEGORY_LABEL[item.category] || item.category }}
            </span>
            <span class="ml-auto flex items-center gap-2">
              <span class="t-badge" :class="STATUS_BADGE[item.status] || 't-badge--neutral'">
                {{ STATUS_LABEL[item.status] || item.status }}
              </span>
              <span class="text-[11px] text-t-3" :title="item.created_at">{{ relativeTime(item.created_at) }}</span>
            </span>
          </div>

          <p class="mt-2 whitespace-pre-wrap text-sm text-t-2">{{ item.content }}</p>

          <div v-if="item.reply" class="mt-3 rounded-xl border border-t-accent/20 bg-t-accent/5 p-3">
            <p class="text-xs font-semibold text-t-accent">管理员回复</p>
            <p class="mt-1 whitespace-pre-wrap text-xs text-t-2">{{ item.reply }}</p>
          </div>

          <!-- 回复表单 -->
          <div v-if="replyingId === item.id" class="mt-3 space-y-2">
            <textarea
              v-model="replyText"
              rows="3"
              class="t-input w-full text-sm"
              placeholder="回复内容将通过站内通知送达用户"
            />
            <div class="flex gap-2">
              <button
                type="button"
                class="t-btn t-btn--sm t-btn--soft"
                :disabled="submitting || !replyText.trim()"
                @click="patch(item, { reply: replyText, status: item.status === 'open' ? 'processing' : undefined })"
              >
                {{ submitting ? '发送中…' : '发送回复' }}
              </button>
              <button type="button" class="t-btn t-btn--sm t-btn--ghost" @click="replyingId = ''">取消</button>
            </div>
          </div>

          <div v-else class="mt-3 flex flex-wrap items-center gap-2 border-t border-t-line/10 pt-3">
            <button type="button" class="t-btn t-btn--sm t-btn--soft" @click="startReply(item)">
              {{ item.reply ? '再次回复' : '回复' }}
            </button>
            <button
              v-if="item.status === 'open'"
              type="button"
              class="t-btn t-btn--sm t-btn--ghost"
              @click="patch(item, { status: 'processing' })"
            >
              标记处理中
            </button>
            <button
              v-if="item.status !== 'closed'"
              type="button"
              class="t-btn t-btn--sm t-btn--ghost"
              @click="patch(item, { status: 'closed' })"
            >
              关闭工单
            </button>
            <button
              v-else
              type="button"
              class="t-btn t-btn--sm t-btn--ghost"
              @click="patch(item, { status: 'open' })"
            >
              重新打开
            </button>
          </div>
        </article>
      </div>
    </transition>
  </div>
</template>

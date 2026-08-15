<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import {
  fetchStudentGeneratedResources,
  recommendGeneratedResource,
  reviewGeneratedResource,
  type StudentGeneratedResource,
} from '../../api/teacherSuite';
import { parseApiError } from '../../api/errors';
import MarkdownView from '../common/MarkdownView.vue';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';
import { useTeacherClassStore } from '../../stores/teacherClass';

const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);

const resources = ref<StudentGeneratedResource[]>([]);
const loading = ref(false);
const msg = ref('');
const filterStatus = ref('pending');
const expandedId = ref('');
const commentDrafts = ref<Record<string, string>>({});
const acting = ref('');

const statusLabel: Record<string, string> = {
  '': '未审核',
  approved: '已通过',
  rejected: '已驳回',
  recommended: '已推荐星库',
};

const kindLabel: Record<string, string> = {
  doc: '讲义',
  mindmap: '导图',
  quiz: '测验',
  reading: '拓展阅读',
  media: '媒体',
  deck: '闪卡',
  code: '代码',
};

const pendingCount = computed(() => resources.value.filter((r) => !r.review_status).length);

async function load() {
  loading.value = true;
  msg.value = '';
  try {
    resources.value = await fetchStudentGeneratedResources(classId.value || '', filterStatus.value);
  } catch (e) {
    msg.value = parseApiError(e, '加载学生资源失败');
  } finally {
    loading.value = false;
  }
}

async function handleReview(r: StudentGeneratedResource, status: 'approved' | 'rejected') {
  acting.value = r.id;
  msg.value = '';
  try {
    await reviewGeneratedResource(r.id, status, commentDrafts.value[r.id] || '');
    msg.value = status === 'approved' ? `已通过「${r.title}」` : `已驳回「${r.title}」`;
    await load();
  } catch (e) {
    msg.value = parseApiError(e, '审核失败');
  } finally {
    acting.value = '';
  }
}

async function handleRecommend(r: StudentGeneratedResource) {
  acting.value = r.id;
  msg.value = '';
  try {
    await recommendGeneratedResource(r.id, classId.value || '');
    msg.value = `已将「${r.title}」推荐进班级星库`;
    await load();
  } catch (e) {
    msg.value = parseApiError(e, '推荐失败');
  } finally {
    acting.value = '';
  }
}

watch(classId, () => void load());
watch(filterStatus, () => void load());
onMounted(() => void load());
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="资源审核" subtitle="审核学生在资源工坊生成的 AI 产物 · 优质内容一键推荐进班级星库">
      <template #actions>
        <select v-model="filterStatus" class="t-input t-input--fit cursor-pointer">
          <option value="pending">待审核</option>
          <option value="">全部</option>
          <option value="approved">已通过</option>
          <option value="rejected">已驳回</option>
          <option value="recommended">已推荐</option>
        </select>
        <button type="button" class="t-btn t-btn--ghost t-btn--sm" @click="load">刷新</button>
      </template>
    </TeacherPageHeader>

    <p v-if="msg" class="text-xs" :class="msg.includes('失败') ? 'text-t-danger' : 'text-t-ok'">{{ msg }}</p>

    <TeacherLoading v-if="loading" :rows="5" />
    <div v-else class="space-y-3">
      <div v-for="r in resources" :key="r.id" class="t-card glass-edge p-5">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <span class="t-badge t-badge--info">{{ kindLabel[r.kind] || r.kind }}</span>
              <span
                class="t-badge"
                :class="
                  r.review_status === 'recommended'
                    ? 't-badge--ok'
                    : r.review_status === 'approved'
                      ? 't-badge--ok'
                      : r.review_status === 'rejected'
                        ? 't-badge--danger'
                        : 't-badge--warn'
                "
              >
                {{ statusLabel[r.review_status] || r.review_status }}
              </span>
              <p class="text-sm font-medium text-t-1">{{ r.title || '未命名资源' }}</p>
            </div>
            <p class="mt-1 text-[11px] text-t-3">
              {{ r.student_name }} · {{ r.planet_name || r.planet_slug || '未关联行星' }} ·
              {{ r.created_at?.slice(0, 16)?.replace('T', ' ') }}
            </p>
            <p v-if="r.review_comment" class="mt-1 text-[11px] text-t-2">审核意见：{{ r.review_comment }}</p>
          </div>
          <div class="flex shrink-0 flex-wrap gap-2">
            <button type="button" class="t-btn t-btn--ghost t-btn--sm" @click="expandedId = expandedId === r.id ? '' : r.id">
              {{ expandedId === r.id ? '收起' : '预览内容' }}
            </button>
            <template v-if="r.review_status !== 'recommended'">
              <button
                type="button"
                class="t-btn t-btn--sm border-t-ok/40 bg-t-ok/12 text-t-ok hover:bg-t-ok/20"
                :disabled="acting === r.id"
                @click="handleReview(r, 'approved')"
              >
                通过
              </button>
              <button
                type="button"
                class="t-btn t-btn--sm border-t-danger/40 bg-t-danger/10 text-t-danger hover:bg-t-danger/18"
                :disabled="acting === r.id"
                @click="handleReview(r, 'rejected')"
              >
                驳回
              </button>
              <button
                type="button"
                class="t-btn t-btn--primary t-btn--sm"
                :disabled="acting === r.id"
                @click="handleRecommend(r)"
              >
                推荐进星库
              </button>
            </template>
          </div>
        </div>

        <div v-if="expandedId === r.id" class="mt-3 space-y-2">
          <div class="t-card--flat max-h-80 overflow-y-auto rounded-xl border border-t-line/10 p-4">
            <MarkdownView :content="r.content || r.content_preview" />
          </div>
          <input
            v-model="commentDrafts[r.id]"
            placeholder="审核意见（可选，通过/驳回时保存）"
            class="t-input"
          />
        </div>
      </div>

      <TeacherEmptyState
        v-if="!resources.length"
        :title="filterStatus === 'pending' ? '暂无待审核资源' : '暂无学生生成资源'"
        description="学生在资源工坊生成 AI 资源后会出现在这里"
      />
    </div>
    <p v-if="!loading && filterStatus === 'pending' && pendingCount" class="text-[11px] text-t-3">
      共 {{ pendingCount }} 条待审核
    </p>
  </div>
</template>

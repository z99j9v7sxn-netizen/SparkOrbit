<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import type { AgentRunDetail, AgentRunSummary } from '../../api/admin';
import { fetchTeacherAgentRunDetail, fetchTeacherAgentRuns } from '../../api/teacherSuite';
import { parseApiError } from '../../api/errors';
import AgentEpisodeList from '../admin/agents/AgentEpisodeList.vue';
import AgentOrchestrationPipeline from '../admin/agents/AgentOrchestrationPipeline.vue';
import AgentStepEvidence from '../admin/agents/AgentStepEvidence.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';
import { useTeacherClassStore } from '../../stores/teacherClass';

const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);

const runs = ref<AgentRunSummary[]>([]);
const selected = ref<AgentRunDetail | null>(null);
const loading = ref(false);
const detailLoading = ref(false);
const msg = ref('');
const filterScene = ref('');
const filterMode = ref('');
const filterStatus = ref('');
let timer: number | undefined;

function stopPolling() {
  if (timer) {
    window.clearInterval(timer);
    timer = undefined;
  }
}

function startPolling() {
  stopPolling();
  timer = window.setInterval(() => {
    if (document.hidden) return;
    void loadList({ silent: true });
    if (selected.value?.status === 'running') void openRun(selected.value.id, { silent: true });
  }, 5000);
}

function onVisibility() {
  if (document.hidden) {
    stopPolling();
    return;
  }
  startPolling();
}

async function loadList(opts: { silent?: boolean } = {}) {
  if (!opts.silent) loading.value = true;
  if (!opts.silent) msg.value = '';
  try {
    runs.value = await fetchTeacherAgentRuns({
      class_id: classId.value || '',
      limit: 80,
      scene: filterScene.value,
      mode: filterMode.value,
      status_filter: filterStatus.value,
    });
    if (selected.value && !runs.value.some((r) => r.id === selected.value!.id)) {
      selected.value = null;
    }
  } catch (err) {
    msg.value = parseApiError(err, '加载 Agent 运行失败');
  } finally {
    if (!opts.silent) loading.value = false;
  }
}

async function openRun(id: string, opts: { silent?: boolean } = {}) {
  if (!opts.silent) detailLoading.value = true;
  if (!opts.silent) msg.value = '';
  try {
    selected.value = await fetchTeacherAgentRunDetail(id);
  } catch (err) {
    msg.value = parseApiError(err, '加载详情失败');
  } finally {
    if (!opts.silent) detailLoading.value = false;
  }
}

watch(classId, () => {
  selected.value = null;
  void loadList();
});

onMounted(() => {
  void loadList();
  startPolling();
  document.addEventListener('visibilitychange', onVisibility);
});

onBeforeUnmount(() => {
  stopPolling();
  document.removeEventListener('visibilitychange', onVisibility);
});
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader
      title="AI 学习动态"
      subtitle="回放本班学生的资源工坊 / 镜像预演 / 平行宇宙 / 伴学 Agent 运行过程"
    >
      <template #actions>
        <button type="button" class="t-btn t-btn--ghost t-btn--sm" :disabled="loading" @click="loadList()">
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </template>
    </TeacherPageHeader>

    <div class="flex flex-wrap items-center gap-2">
      <select v-model="filterScene" class="t-input t-input--fit" @change="loadList()">
        <option value="">全部场景</option>
        <option value="resource">资源工坊</option>
        <option value="simulation">镜像预演</option>
        <option value="multiverse">平行宇宙</option>
        <option value="companion">伴学 Supervisor</option>
        <option value="closed_loop">成长闭环</option>
      </select>
      <select v-model="filterMode" class="t-input t-input--fit" @change="loadList()">
        <option value="">全部模式</option>
        <option value="workflow">workflow · 流水线</option>
        <option value="handoff">handoff · 接力</option>
        <option value="council">council · 评议</option>
        <option value="supervisor">supervisor · 统筹</option>
        <option value="loop">loop · 评估闭环</option>
      </select>
      <select v-model="filterStatus" class="t-input t-input--fit" @change="loadList()">
        <option value="">全部状态</option>
        <option value="running">running</option>
        <option value="completed">completed</option>
        <option value="failed">failed</option>
      </select>
    </div>

    <p v-if="msg" class="rounded-xl border border-t-danger/25 bg-t-danger/10 px-4 py-3 text-sm text-t-danger">{{ msg }}</p>

    <div class="grid gap-4 xl:grid-cols-[minmax(280px,0.95fr)_1.35fr]">
      <div class="min-h-[420px] xl:max-h-[720px]">
        <AgentEpisodeList
          class="h-full max-h-[640px] xl:max-h-[720px]"
          :runs="runs"
          :selected-id="selected?.id"
          :loading="loading"
          @select="openRun"
        />
      </div>

      <div class="space-y-4">
        <div class="relative">
          <span v-if="detailLoading" class="absolute right-3 top-3 z-10 font-mono-tech text-[10px] text-t-3">LOADING</span>
          <AgentOrchestrationPipeline :run="selected" />
        </div>
        <AgentStepEvidence v-if="selected" :steps="selected.steps || []" :focus-step="null" />
        <div
          v-else
          class="flex h-40 items-center justify-center rounded-2xl border border-dashed border-t-line/15 text-sm text-t-3"
        >
          选择左侧运行记录，回放学生的 Agent 步骤
        </div>
      </div>
    </div>
  </div>
</template>

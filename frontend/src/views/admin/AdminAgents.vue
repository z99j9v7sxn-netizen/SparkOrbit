<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import {
  fetchAdminAgentRunDetail,
  fetchAdminAgentRuns,
  fetchAdminDemoHealth,
  seedAdminAgentModes,
  type AgentRunDetail,
  type AgentRunSummary,
  type DemoHealth,
} from '../../api/admin';
import { parseApiError } from '../../api/errors';
import AdminPageHeader from '../../components/admin/AdminPageHeader.vue';
import AgentEpisodeList from '../../components/admin/agents/AgentEpisodeList.vue';
import AgentModeAtlas from '../../components/admin/agents/AgentModeAtlas.vue';
import AgentOrchestrationPipeline from '../../components/admin/agents/AgentOrchestrationPipeline.vue';
import AgentRunKpiBar from '../../components/admin/agents/AgentRunKpiBar.vue';
import AgentStepEvidence from '../../components/admin/agents/AgentStepEvidence.vue';

const runs = ref<AgentRunSummary[]>([]);
const selected = ref<AgentRunDetail | null>(null);
const loading = ref(false);
const detailLoading = ref(false);
const seeding = ref(false);
const msg = ref('');
const okMsg = ref('');
const filterMode = ref('');
const filterScene = ref('');
const filterStatus = ref('');
const filterUser = ref('');
const userOptions = ref<Array<{ id: string; name: string }>>([]);
const focusStep = ref<number | null>(null);
const demoHealth = ref<DemoHealth | null>(null);
const healthError = ref('');
let timer: number | undefined;

const userDatalistId = 'admin-agent-user-options';

const mergedUserOptions = computed(() => {
  const map = new Map<string, string>();
  for (const u of userOptions.value) map.set(u.id, u.name);
  for (const r of runs.value) {
    if (r.user_id) map.set(r.user_id, r.user_name || r.user_id);
  }
  return [...map.entries()].map(([id, name]) => ({ id, name }));
});

function rememberUsers(list: AgentRunSummary[]) {
  const map = new Map(userOptions.value.map((u) => [u.id, u.name]));
  for (const r of list) {
    if (r.user_id) map.set(r.user_id, r.user_name || r.user_id);
  }
  userOptions.value = [...map.entries()].map(([id, name]) => ({ id, name }));
}

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
  }, 4000);
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
    runs.value = await fetchAdminAgentRuns({
      limit: 80,
      mode: filterMode.value,
      scene: filterScene.value,
      status_filter: filterStatus.value,
      user_id: filterUser.value.trim(),
    });
    rememberUsers(runs.value);
    if (selected.value) {
      const still = runs.value.find((r) => r.id === selected.value!.id);
      if (!still) {
        selected.value = null;
        focusStep.value = null;
      }
    }
  } catch (err) {
    msg.value = parseApiError(err, '加载 Agent 运行失败');
  } finally {
    if (!opts.silent) loading.value = false;
  }
}

async function openRun(id: string, opts: { silent?: boolean } = {}) {
  if (!opts.silent) detailLoading.value = true;
  if (!opts.silent) {
    msg.value = '';
    focusStep.value = null;
  }
  try {
    selected.value = await fetchAdminAgentRunDetail(id);
  } catch (err) {
    msg.value = parseApiError(err, '加载详情失败');
  } finally {
    if (!opts.silent) detailLoading.value = false;
  }
}

async function onSelectMode(mode: string) {
  const next = filterMode.value === mode ? '' : mode;
  filterMode.value = next;
  await loadList();
  if (!next) return;
  const hit = runs.value.find((r) => r.mode === next);
  if (hit) await openRun(hit.id);
}

async function loadHealth() {
  healthError.value = '';
  try {
    demoHealth.value = await fetchAdminDemoHealth();
  } catch (err) {
    demoHealth.value = null;
    healthError.value = parseApiError(err, 'Demo 预检加载失败');
  }
}

async function onSeed() {
  seeding.value = true;
  msg.value = '';
  okMsg.value = '';
  try {
    const res = await seedAdminAgentModes();
    okMsg.value = `已注入 ${res.count} 条四模式演示数据`;
    filterMode.value = '';
    await loadList();
    const prefer = ['workflow', 'handoff', 'supervisor', 'council'];
    for (const m of prefer) {
      const hit = runs.value.find((r) => r.mode === m && r.user_id === 'demo-four-modes');
      if (hit) {
        await openRun(hit.id);
        break;
      }
    }
  } catch (err) {
    msg.value = parseApiError(err, '注入演示数据失败');
  } finally {
    seeding.value = false;
  }
}

onMounted(() => {
  void loadList();
  void loadHealth();
  startPolling();
  document.addEventListener('visibilitychange', onVisibility);
});

onBeforeUnmount(() => {
  stopPolling();
  document.removeEventListener('visibilitychange', onVisibility);
});
</script>

<template>
  <div class="space-y-5">
    <AdminPageHeader
      kicker="Agent Observatory"
      title="Agent 运行观测"
      subtitle="先看清四模式，再回放每一位同学的步骤与 Agent"
    />

    <!-- 筛选工具条 -->
    <div class="flex flex-wrap items-center gap-2">
      <select v-model="filterScene" class="t-input t-input--fit" @change="loadList()">
        <option value="">全部场景</option>
        <option value="resource">资源生成</option>
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
      <div class="w-44">
        <input
          v-model="filterUser"
          :list="userDatalistId"
          placeholder="同学 user_id / 姓名"
          class="t-input"
          @change="loadList()"
          @keyup.enter="loadList()"
        />
      </div>
      <datalist :id="userDatalistId">
        <option v-for="u in mergedUserOptions" :key="u.id" :value="u.id">{{ u.name }}</option>
      </datalist>
      <button
        type="button"
        class="t-btn t-btn--md t-btn--ghost"
        :disabled="loading || seeding"
        @click="loadList()"
      >
        {{ loading ? '刷新中…' : '刷新' }}
      </button>
    </div>

    <p v-if="msg" class="rounded-xl border border-t-danger/25 bg-t-danger/10 px-4 py-3 text-sm text-t-danger">{{ msg }}</p>
    <p v-if="okMsg" class="rounded-xl border border-t-ok/25 bg-t-ok/10 px-4 py-3 text-sm text-t-ok">{{ okMsg }}</p>

    <div
      v-if="demoHealth || healthError"
      class="space-y-2 rounded-2xl border px-3 py-2 text-xs"
      :class="
        healthError
          ? 'border-t-danger/30 bg-t-danger/8 text-t-danger'
          : demoHealth?.ok
            ? 'border-t-ok/25 bg-t-ok/8 text-t-ok'
            : 'border-t-warn/30 bg-t-warn/8 text-t-warn'
      "
    >
      <div class="flex flex-wrap items-center gap-2">
        <span class="font-mono-tech text-[10px] uppercase tracking-widest opacity-80">Demo Health</span>
        <p v-if="healthError" class="text-[11px]">{{ healthError }}</p>
        <template v-else-if="demoHealth">
          <span
            v-for="c in demoHealth.checks"
            :key="c.id"
            class="t-badge"
            :class="c.advisory ? 't-badge--neutral' : c.ok ? 't-badge--ok' : 't-badge--danger'"
            :title="c.detail"
          >
            {{ c.advisory ? '◇' : c.ok ? '●' : '○' }} {{ c.label }}
          </span>
        </template>
        <button type="button" class="ml-auto text-[10px] underline opacity-70 hover:opacity-100" @click="loadHealth">
          刷新预检
        </button>
      </div>
      <ul v-if="demoHealth?.tips?.length" class="list-inside list-disc text-[10px] text-t-2">
        <li v-for="(t, i) in demoHealth.tips" :key="`tip-${i}`">{{ t }}</li>
      </ul>
    </div>

    <AgentModeAtlas :active-mode="filterMode" :seeding="seeding" @select="onSelectMode" @seed="onSeed" />

    <AgentRunKpiBar :runs="runs" />

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
          <span
            v-if="detailLoading"
            class="absolute right-3 top-3 z-10 font-mono-tech text-[10px] text-t-3"
          >LOADING</span>
          <AgentOrchestrationPipeline :run="selected" @focus-step="(i) => (focusStep = i)" />
        </div>
        <AgentStepEvidence
          v-if="selected"
          :steps="selected.steps || []"
          :focus-step="focusStep"
        />
        <div
          v-else
          class="flex h-40 items-center justify-center rounded-2xl border border-dashed border-t-line/15 text-sm text-t-3"
        >
          选择 Episode 或先「注入四模式演示数据」
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AgentRunSummary } from '../../../api/admin';
import StatusOrb, { type StatusOrbState } from '../../common/orb/StatusOrb.vue';

const props = defineProps<{
  runs: AgentRunSummary[];
  selectedId?: string;
  loading?: boolean;
}>();

const emit = defineEmits<{
  (e: 'select', id: string): void;
}>();

const MODE_LABEL: Record<string, string> = {
  handoff: '顺序接力',
  workflow: '流水线编排',
  supervisor: '层级统筹',
  council: '并行评议',
};

const MODE_BADGE: Record<string, string> = {
  handoff: 'border-sky-400/35 bg-sky-500/15 text-sky-200',
  workflow: 'border-cyan-400/35 bg-cyan-500/15 text-cyan-200',
  supervisor: 'border-violet-400/35 bg-violet-500/15 text-violet-200',
  council: 'border-amber-400/35 bg-amber-500/15 text-amber-200',
};

function initials(name: string) {
  const t = (name || '?').trim();
  return t.slice(0, 1).toUpperCase();
}

function relTime(iso: string) {
  if (!iso) return '—';
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso.slice(0, 16);
  const diff = Date.now() - t;
  if (diff < 60_000) return '刚刚';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`;
  return `${Math.floor(diff / 86_400_000)} 天前`;
}

function statusOrbState(status: string): StatusOrbState {
  if (status === 'running') return 'thinking';
  if (status === 'completed') return 'success';
  if (status === 'failed') return 'error';
  return 'offline';
}
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden rounded-2xl border border-white/10 bg-slate-950/45">
    <div class="border-b border-white/10 px-4 py-3">
      <div class="flex items-center justify-between gap-2">
        <div>
          <h3 class="text-sm font-medium text-white">Task Episodes</h3>
          <p class="mt-0.5 text-xs text-slate-500">仿 Better Harness 任务片段 · {{ runs.length }} 条 · 约 4s 刷新</p>
        </div>
        <span v-if="loading" class="font-mono-tech text-[10px] text-cyan-300/70">SYNC</span>
      </div>
    </div>

    <div class="flex-1 space-y-2 overflow-auto p-3" style="max-height: min(640px, 70vh)">
      <button
        v-for="r in runs"
        :key="r.id"
        type="button"
        class="episode-card group w-full rounded-xl border px-3 py-3 text-left transition-all duration-300"
        :class="
          selectedId === r.id
            ? 'border-cyan-400/50 bg-cyan-500/10 shadow-[0_0_24px_rgba(34,211,238,0.12)]'
            : 'border-white/8 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.055]'
        "
        @click="emit('select', r.id)"
      >
        <div class="flex items-start gap-3">
          <div
            class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/10 bg-slate-900 text-sm font-semibold text-cyan-200"
          >
            {{ initials(r.user_name || r.user_id) }}
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center justify-between gap-2">
              <p class="truncate text-sm font-medium text-slate-100">{{ r.user_name || r.user_id.slice(0, 8) }}</p>
              <StatusOrb :state="statusOrbState(r.status)" :size="18" :label="r.status" />
            </div>
            <p class="mt-0.5 truncate text-xs text-slate-400">{{ r.topic || '未命名任务' }}</p>
            <div class="mt-2 flex flex-wrap items-center gap-1.5">
              <span
                class="rounded-md border px-1.5 py-0.5 text-[10px]"
                :class="MODE_BADGE[r.mode] || 'border-white/15 bg-white/5 text-slate-300'"
              >
                {{ MODE_LABEL[r.mode] || r.mode }}
              </span>
              <span class="rounded-md border border-white/10 bg-black/30 px-1.5 py-0.5 font-mono-tech text-[10px] text-slate-400">
                {{ r.scene }}
              </span>
              <span v-if="r.current_agent" class="truncate text-[10px] text-slate-500">
                #{{ r.current_step }} {{ r.current_agent }}
              </span>
            </div>
            <p class="mt-1.5 font-mono-tech text-[10px] text-slate-600">{{ relTime(r.created_at) }} · {{ r.id }}</p>
          </div>
        </div>
      </button>

      <div
        v-if="!runs.length && !loading"
        class="flex h-48 items-center justify-center rounded-xl border border-dashed border-white/10 px-4 text-center text-sm text-slate-500"
      >
        暂无运行片段。学生触发资源生成 / 镜像预演 / 伴学 Supervisor 后会出现在此。
      </div>
    </div>
  </div>
</template>

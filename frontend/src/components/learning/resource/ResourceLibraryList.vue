<script setup lang="ts">
import type { GeneratedResource } from '../../../api/learnExtras';
import { LzBadge, LzEmptyState, LzSection } from '../ui';
import { qualityOf } from './resourceMeta';

defineProps<{
  resources: GeneratedResource[];
  activeId?: string;
}>();

const emit = defineEmits<{
  (e: 'open', resource: GeneratedResource): void;
  (e: 'generate'): void;
}>();
</script>

<template>
  <LzSection title="我的资源库" :desc="`共 ${resources.length} 项`">
    <LzEmptyState
      v-if="!resources.length"
      icon="✦"
      title="资源库还是空的"
      desc="选择知识点与资源类型后，让多智能体为你生成第一批学习资源。"
      action-text="启动资源生成"
      @action="emit('generate')"
    />
    <div v-else class="max-h-40 space-y-1.5 overflow-y-auto pr-1">
      <button
        v-for="r in resources"
        :key="r.id"
        type="button"
        class="lz-card lz-card--hover flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
        :class="activeId === r.id ? 'lz-card--active' : ''"
        @click="emit('open', r)"
      >
        <span class="lz-body truncate">{{ r.title }}</span>
        <span class="flex shrink-0 items-center gap-1.5">
          <LzBadge tone="neutral">{{ r.kind }}</LzBadge>
          <span v-if="qualityOf(r)" class="lz-caption text-amber-200/90">
            A{{ qualityOf(r)?.accuracy }}/H{{ qualityOf(r)?.hallucination_risk }}
          </span>
        </span>
      </button>
    </div>
  </LzSection>
</template>

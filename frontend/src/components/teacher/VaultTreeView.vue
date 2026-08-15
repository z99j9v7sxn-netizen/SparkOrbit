<script setup lang="ts">
import type { VaultTreeNode } from '../../api/teacher';

defineOptions({ name: 'VaultTreeView' });

const props = defineProps<{
  nodes: VaultTreeNode[];
  activePath?: string;
  depth?: number;
}>();

const emit = defineEmits<{
  (e: 'open', path: string): void;
}>();

function isDir(n: VaultTreeNode) {
  return n.type === 'dir' || (!!n.children && n.children.length > 0);
}
</script>

<template>
  <div class="space-y-0.5">
    <template v-for="n in props.nodes" :key="n.path || n.name">
      <div v-if="isDir(n)">
        <p
          class="px-2 py-1 text-[11px] font-medium text-t-3"
          :style="{ paddingLeft: `${(props.depth || 0) * 12}px` }"
        >
          {{ n.name || '文件夹' }}
        </p>
        <VaultTreeView
          :nodes="n.children || []"
          :active-path="props.activePath"
          :depth="(props.depth || 0) + 1"
          @open="(path) => emit('open', path)"
        />
      </div>
      <button
        v-else
        type="button"
        class="block w-full rounded-lg border px-3 py-1.5 text-left text-xs transition"
        :class="
          props.activePath === n.path
            ? 'border-t-accent/40 bg-t-accent/10 text-t-1'
            : 'border-transparent text-t-2 hover:border-t-line/10 hover:bg-t-line/5'
        "
        :style="{ paddingLeft: `${(props.depth || 0) * 12}px` }"
        @click="n.path && emit('open', n.path)"
      >
        {{ n.name || n.path }}
      </button>
    </template>
  </div>
</template>

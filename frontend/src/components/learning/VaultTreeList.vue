<script setup lang="ts">
import type { VaultTreeNode } from '../../api/vault';

defineProps<{
  nodes: VaultTreeNode[];
  active: string;
  depth?: number;
}>();

defineEmits<{
  open: [path: string];
}>();
</script>

<template>
  <ul :class="depth ? 'ml-2 border-l border-white/5 pl-2' : ''">
    <li v-for="n in nodes" :key="n.path" class="py-0.5">
      <template v-if="n.type === 'dir'">
        <div class="flex items-center gap-1 truncate text-slate-500">
          <img class="h-3.5 w-3.5 shrink-0" src="/icons/folder.svg" alt="" aria-hidden="true" />
          <span class="truncate">{{ n.name }}</span>
        </div>
        <VaultTreeList
          v-if="n.children?.length"
          :nodes="n.children"
          :active="active"
          :depth="(depth || 0) + 1"
          @open="$emit('open', $event)"
        />
      </template>
      <button
        v-else
        type="button"
        class="block w-full truncate rounded px-1 py-0.5 text-left hover:bg-white/5"
        :class="active === n.path ? 'bg-[rgb(var(--lz-accent)/0.2)] text-[rgb(var(--lz-accent-bright))]' : 'text-slate-300'"
        @click="$emit('open', n.path)"
      >
        {{ n.name.replace(/\.md$/i, '') }}
      </button>
    </li>
  </ul>
</template>

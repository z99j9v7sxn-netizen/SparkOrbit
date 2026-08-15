<script setup lang="ts">
withDefaults(
  defineProps<{
    /** list: 多行列表；card: 卡片块；text: 文本行 */
    preset?: 'list' | 'card' | 'text';
    rows?: number;
  }>(),
  { preset: 'list', rows: 3 },
);
</script>

<template>
  <div aria-busy="true" aria-live="polite" class="space-y-2.5">
    <template v-if="preset === 'list'">
      <div v-for="i in rows" :key="i" class="flex items-center gap-3">
        <div class="console-skeleton h-9 w-9 shrink-0 rounded-xl"></div>
        <div class="min-w-0 flex-1 space-y-1.5">
          <div class="console-skeleton h-3" :style="{ width: `${72 - (i % 3) * 14}%` }"></div>
          <div class="console-skeleton h-2.5" :style="{ width: `${44 - (i % 2) * 10}%` }"></div>
        </div>
      </div>
    </template>
    <template v-else-if="preset === 'card'">
      <div v-for="i in rows" :key="i" class="console-skeleton h-24 rounded-2xl"></div>
    </template>
    <template v-else>
      <div v-for="i in rows" :key="i" class="console-skeleton h-3" :style="{ width: `${90 - (i % 4) * 16}%` }"></div>
    </template>
  </div>
</template>

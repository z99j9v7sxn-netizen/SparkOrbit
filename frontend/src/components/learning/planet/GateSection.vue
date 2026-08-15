<script setup lang="ts">
import { ref } from 'vue';

withDefaults(
  defineProps<{
    /** 写入 data-gate，供面板 querySelector 滚动定位 */
    gateId: string;
    title: string;
    /** 标题下方的说明 / 解锁条件文案 */
    hint?: string;
    /** 闸门切换后的短暂定位闪烁（ring-2） */
    flash?: boolean;
    /** 当前激活闸门的常驻描边（ring-1） */
    highlight?: boolean;
  }>(),
  { hint: '', flash: false, highlight: false },
);

const rootEl = ref<HTMLElement | null>(null);

defineExpose({
  scrollIntoView(options?: ScrollIntoViewOptions) {
    rootEl.value?.scrollIntoView(options);
  },
});
</script>

<template>
  <section
    ref="rootEl"
    :data-gate="gateId"
    class="lz-card p-4 transition"
    :class="[
      highlight ? 'ring-1 ring-[rgb(var(--lz-accent)/0.35)]' : '',
      flash ? 'ring-2 ring-[rgb(var(--lz-accent)/0.6)]' : '',
    ]"
  >
    <div class="flex items-start justify-between gap-3">
      <h3 class="lz-subtitle min-w-0">{{ title }}</h3>
      <div v-if="$slots.actions" class="flex shrink-0 items-center gap-1.5">
        <slot name="actions" />
      </div>
    </div>
    <p v-if="hint" class="lz-desc mt-1">{{ hint }}</p>
    <slot />
  </section>
</template>

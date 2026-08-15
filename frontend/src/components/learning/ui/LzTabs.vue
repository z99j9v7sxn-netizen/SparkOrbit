<script setup lang="ts">
export interface LzTabItem {
  key: string;
  label: string;
  icon?: string;
  disabled?: boolean;
}

defineProps<{
  items: LzTabItem[];
  modelValue: string;
  block?: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
}>();
</script>

<template>
  <div class="lz-tabs" :class="block ? 'flex w-full' : ''" role="tablist">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      role="tab"
      class="lz-tab"
      :class="[modelValue === item.key ? 'is-active' : '', block ? 'flex-1' : '']"
      :aria-selected="modelValue === item.key"
      :disabled="item.disabled"
      @click="emit('update:modelValue', item.key)"
    >
      <span v-if="item.icon" aria-hidden="true">{{ item.icon }}</span>
      {{ item.label }}
    </button>
  </div>
</template>

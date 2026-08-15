<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue: string;
    type?: string;
    placeholder?: string;
    size?: 'sm' | 'md';
    disabled?: boolean;
  }>(),
  { type: 'text', placeholder: '', size: 'md', disabled: false },
);

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
  (e: 'enter'): void;
}>();
</script>

<template>
  <input
    :value="modelValue"
    :type="type"
    :placeholder="placeholder"
    :disabled="disabled"
    class="lz-input"
    :class="size === 'sm' ? 'h-8 px-2.5' : 'h-[34px] px-3'"
    @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    @keydown.enter="emit('enter')"
  />
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue';

const props = withDefaults(
  defineProps<{
    modelValue: string;
    label: string;
    type?: string;
    placeholder?: string;
    done?: boolean;
    active?: boolean;
    disabled?: boolean;
    autocomplete?: string;
    error?: string;
  }>(),
  {
    type: 'text',
    placeholder: '',
    done: false,
    active: true,
    disabled: false,
    autocomplete: 'off',
    error: '',
  },
);

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
  (e: 'submit'): void;
}>();

const inputRef = ref<HTMLInputElement | null>(null);

function focus() {
  void nextTick(() => inputRef.value?.focus());
}

onMounted(() => {
  if (props.active && !props.done) focus();
});

watch(
  () => props.active,
  (v) => {
    if (v && !props.done) focus();
  },
);

defineExpose({ focus });

function onKeydown(ev: KeyboardEvent) {
  if (ev.key === 'Enter') {
    ev.preventDefault();
    if (props.disabled || props.done) return;
    emit('submit');
  }
}
</script>

<template>
  <div
    class="terminal-field group relative py-2 transition-opacity duration-300"
    :class="done ? 'opacity-60' : active ? 'opacity-100' : 'pointer-events-none opacity-0'"
  >
    <div class="mb-1.5 flex items-center justify-between gap-3">
      <label class="text-[11px] tracking-wider text-[var(--term-muted)]">{{ label }}</label>
      <span v-if="done" class="text-[11px] tracking-wider text-[var(--term-accent)]">[OK]</span>
    </div>

    <div class="relative flex items-center gap-2">
      <span class="shrink-0 text-[var(--term-accent)]">&gt;</span>
      <input
        ref="inputRef"
        :value="modelValue"
        :type="type"
        :placeholder="placeholder"
        :autocomplete="autocomplete"
        :disabled="done || disabled"
        :readonly="done || disabled"
        class="terminal-input w-full bg-transparent py-2 text-sm text-[var(--term-fg)] outline-none placeholder:text-[var(--term-muted)]/50 disabled:opacity-70"
        @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        @keydown="onKeydown"
      />
    </div>

    <div class="relative mt-0 h-px w-full bg-[var(--term-line)]">
      <div
        class="terminal-underline absolute bottom-0 left-0 h-px bg-[var(--term-accent)] transition-all duration-500"
        :class="done || active ? 'w-full' : 'w-0 group-focus-within:w-full'"
      />
    </div>

    <p v-if="error" class="mt-2 text-[11px] tracking-wide text-[var(--term-err)]">错误：{{ error }}</p>
  </div>
</template>

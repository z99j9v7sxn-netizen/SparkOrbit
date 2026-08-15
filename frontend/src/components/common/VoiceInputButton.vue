<script setup lang="ts">
import { useVoiceInput } from '../../composables/useVoiceInput';

const props = withDefaults(
  defineProps<{
    disabled?: boolean;
    label?: string;
  }>(),
  { label: '' },
);

const emit = defineEmits<{ (e: 'text', value: string, final: boolean): void }>();

const { hint, listening, start } = useVoiceInput();

function onClick() {
  if (props.disabled || listening.value) return;
  void start((text, final) => emit('text', text, final));
}
</script>

<template>
  <div class="inline-flex flex-col items-start gap-1">
    <button
      type="button"
      class="inline-flex items-center gap-1 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs transition"
      :class="listening ? 'border-sky-400/40 bg-sky-500/15 text-sky-100' : 'text-slate-300 hover:bg-white/5'"
      :disabled="disabled || listening"
      :title="disabled ? '语音识别未配置' : '语音输入'"
      @click="onClick"
    >
      <template v-if="listening">聆听中…</template>
      <template v-else>
        <img class="h-4 w-4" src="/icons/mic.svg" alt="" aria-hidden="true" />
        <span v-if="label">{{ label }}</span>
      </template>
    </button>
    <p v-if="hint" class="text-[10px] text-slate-500">{{ hint }}</p>
  </div>
</template>

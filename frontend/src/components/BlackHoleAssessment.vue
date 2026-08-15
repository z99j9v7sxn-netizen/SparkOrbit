<script setup lang="ts">
import { ref } from 'vue';
import { startAssessment, submitAssessment, type AssessmentState } from '../api/orbit';

const props = defineProps<{ galaxySlug: string; galaxyName: string }>();
const emit = defineEmits<{ (e: 'done', litPlanets: string[]): void; (e: 'close'): void }>();

const state = ref<AssessmentState | null>(null);
const selected = ref('');
const loading = ref(false);
const error = ref('');
const finished = ref(false);

async function begin() {
  loading.value = true;
  error.value = '';
  try {
    state.value = await startAssessment(props.galaxySlug);
    selected.value = '';
  } catch (e) {
    error.value = e instanceof Error ? e.message : '初测启动失败';
  } finally {
    loading.value = false;
  }
}

async function submit() {
  if (!state.value || !selected.value) return;
  loading.value = true;
  try {
    const res = await submitAssessment(props.galaxySlug, state.value.assessment_id, selected.value);
    if (res.done) {
      finished.value = true;
      state.value = { ...state.value, ...res };
      emit('done', res.lit_planets ?? []);
    } else {
      state.value = { ...state.value, ...res };
      selected.value = '';
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '提交失败';
  } finally {
    loading.value = false;
  }
}

void begin();
</script>

<template>
  <div class="glass-overlay fixed inset-0 z-50 flex items-center justify-center p-4">
    <div class="glass-edge w-full max-w-lg rounded-3xl p-6">
      <div class="text-center">
        <div class="mx-auto mb-4 h-24 w-24 rounded-full bg-gradient-to-br from-purple-900 via-black to-sky-900 shadow-[0_0_60px_rgba(125,211,252,0.4)] animate-pulse-ring">
          <div class="flex h-full items-center justify-center text-4xl">🕳️</div>
        </div>
        <p class="text-[10px] uppercase tracking-[0.4em] text-sky-300/70">引力黑洞初测</p>
        <h2 class="mt-1 text-xl font-semibold text-white text-glow">{{ galaxyName }}</h2>
        <p class="mt-1 text-xs text-slate-400">5 道连环问答，测探初始实力并点亮初始行星</p>
      </div>

      <p v-if="error" class="mt-4 rounded-xl border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-100">{{ error }}</p>

      <template v-if="state && !finished">
        <div class="mt-4 flex items-center justify-between text-xs text-slate-400">
          <span>第 {{ (state.current_index ?? 0) + 1 }} / {{ state.total }} 题</span>
          <span class="text-sky-300">{{ state.planet_name }}</span>
        </div>
        <p class="mt-3 text-sm leading-6 text-slate-100">{{ state.question }}</p>
        <div class="mt-3 space-y-2">
          <label
            v-for="opt in state.options"
            :key="opt.key"
            class="glass-card flex cursor-pointer items-center gap-2 rounded-xl border border-white/10 px-3 py-2 text-sm transition hover:border-sky-400/40"
            :class="selected === opt.key ? 'border-sky-400/60 bg-sky-400/10' : ''"
          >
            <input v-model="selected" type="radio" :value="opt.key" />
            <span><b class="text-sky-300">{{ opt.key }}.</b> {{ opt.text }}</span>
          </label>
        </div>
        <button
          class="glass-btn mt-4 w-full rounded-xl py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          :disabled="!selected || loading"
          @click="submit"
        >{{ loading ? '判定中…' : '提交答案' }}</button>
      </template>

      <div v-if="finished" class="mt-4 space-y-3 text-center">
        <p class="text-lg font-semibold text-emerald-200">初测完成！</p>
        <p class="text-sm text-slate-300">{{ state?.message }}</p>
        <p v-if="state?.lit_planets?.length" class="text-xs text-sky-300">已点亮：{{ state.lit_planets.join('、') }}</p>
        <button class="rounded-xl border border-white/15 px-6 py-2 text-sm text-slate-200" @click="emit('close')">进入星系</button>
      </div>

      <button v-if="!finished" class="mt-3 w-full text-xs text-slate-500 hover:text-slate-300" @click="emit('close')">跳过初测</button>
    </div>
  </div>
</template>

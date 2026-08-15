<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { fetchGalaxies } from '../../api/orbit';
import { fetchGatePolicy, runReviewScan, saveGatePolicy, type GatePolicy } from '../../api/teacher';
import { parseApiError } from '../../api/errors';
import { useTeacherClassStore } from '../../stores/teacherClass';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';

const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);

const galaxies = ref<Array<{ slug: string; name: string }>>([]);
const galaxySlug = ref('');
const loading = ref(false);
const saving = ref(false);
const scanning = ref(false);
const msg = ref('');
const form = reactive({
  practice_questions: 5,
  practice_min_correct: 4,
  explain_pass_threshold: 0.7,
  apply_required_default: true,
  learn_evidence_min: 1,
  decay_fading: 7,
  decay_meteor: 14,
  decay_dim: 30,
});

function applyPolicy(p: GatePolicy) {
  form.practice_questions = p.practice_questions;
  form.practice_min_correct = p.practice_min_correct;
  form.explain_pass_threshold = p.explain_pass_threshold;
  form.apply_required_default = p.apply_required_default;
  form.learn_evidence_min = p.learn_evidence_min;
  form.decay_fading = p.decay_days?.fading ?? 7;
  form.decay_meteor = p.decay_days?.meteor ?? 14;
  form.decay_dim = p.decay_days?.dim ?? 30;
}

async function load() {
  if (!classId.value) return;
  loading.value = true;
  msg.value = '';
  try {
    const p = await fetchGatePolicy(classId.value, galaxySlug.value);
    applyPolicy(p);
  } catch (err) {
    msg.value = parseApiError(err, '加载门控策略失败');
  } finally {
    loading.value = false;
  }
}

async function save() {
  if (!classId.value) return;
  saving.value = true;
  msg.value = '';
  try {
    const p = await saveGatePolicy({
      class_id: classId.value,
      galaxy_slug: galaxySlug.value,
      practice_questions: form.practice_questions,
      practice_min_correct: form.practice_min_correct,
      explain_pass_threshold: form.explain_pass_threshold,
      apply_required_default: form.apply_required_default,
      learn_evidence_min: form.learn_evidence_min,
      decay_days: {
        fading: form.decay_fading,
        meteor: form.decay_meteor,
        dim: form.decay_dim,
      },
    });
    applyPolicy(p);
    msg.value = '门控策略已保存';
  } catch (err) {
    msg.value = parseApiError(err, '保存失败');
  } finally {
    saving.value = false;
  }
}

async function scanReviews() {
  if (!classId.value) return;
  scanning.value = true;
  msg.value = '';
  try {
    const res = await runReviewScan(classId.value);
    msg.value = `复习扫描完成：扫描 ${res.students_scanned} 人，需复习 ${res.students_needing_review} 人，新建任务 ${res.tasks_created}，预警行星 ${res.planets_flagged}`;
  } catch (err) {
    msg.value = parseApiError(err, '复习扫描失败');
  } finally {
    scanning.value = false;
  }
}

watch(classId, () => void load());
watch(galaxySlug, () => void load());

onMounted(async () => {
  galaxies.value = (await fetchGalaxies().catch(() => [])).map((g) => ({ slug: g.slug, name: g.name }));
  await load();
});
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="通关门控策略" subtitle="配置练闸题量、讲闸阈值、用闸默认与遗忘衰减天数">
      <template #actions>
        <select v-model="galaxySlug" class="t-input w-auto cursor-pointer">
          <option value="">全星系默认</option>
          <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
        </select>
      </template>
    </TeacherPageHeader>

    <TeacherEmptyState v-if="!classId" title="请先选择班级" />
    <TeacherLoading v-else-if="loading" :rows="4" />

    <form v-else class="t-card glass-edge space-y-5 p-5" @submit.prevent="save">
      <div class="grid gap-4 sm:grid-cols-2">
        <label class="block text-xs text-t-2">
          练闸题量
          <input v-model.number="form.practice_questions" type="number" min="1" max="20" class="t-input mt-1" />
        </label>
        <label class="block text-xs text-t-2">
          练闸最少答对
          <input v-model.number="form.practice_min_correct" type="number" min="1" max="20" class="t-input mt-1" />
        </label>
        <label class="block text-xs text-t-2">
          讲闸通过阈值 (0–1)
          <input v-model.number="form.explain_pass_threshold" type="number" min="0" max="1" step="0.05" class="t-input mt-1" />
        </label>
        <label class="block text-xs text-t-2">
          学闸最少证据条数
          <input v-model.number="form.learn_evidence_min" type="number" min="1" max="10" class="t-input mt-1" />
        </label>
      </div>

      <label class="flex items-center gap-2 text-sm text-t-2">
        <input v-model="form.apply_required_default" type="checkbox" class="t-check rounded" />
        默认要求「用」闸（代码/难题行星仍会强制开启）
      </label>

      <div>
        <p class="text-xs font-medium text-t-2">遗忘衰减天数</p>
        <div class="mt-2 grid gap-3 sm:grid-cols-3">
          <label class="block text-[11px] text-t-3">
            变暗 fading
            <input v-model.number="form.decay_fading" type="number" min="1" class="t-input mt-1" />
          </label>
          <label class="block text-[11px] text-t-3">
            陨石 meteor
            <input v-model.number="form.decay_meteor" type="number" min="1" class="t-input mt-1" />
          </label>
          <label class="block text-[11px] text-t-3">
            暗淡 dim
            <input v-model.number="form.decay_dim" type="number" min="1" class="t-input mt-1" />
          </label>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <button type="submit" class="t-btn t-btn--primary t-btn--md" :disabled="saving">
          {{ saving ? '保存中…' : '保存策略' }}
        </button>
        <button
          type="button"
          class="t-btn t-btn--md border-t-warn/35 bg-t-warn/10 text-t-warn hover:bg-t-warn/18"
          :disabled="scanning || saving"
          @click="scanReviews"
        >
          {{ scanning ? '扫描中…' : '今日复习扫描并派发' }}
        </button>
        <p v-if="msg" class="text-xs" :class="msg.includes('失败') ? 'text-t-danger' : 'text-t-ok'">
          {{ msg }}
        </p>
      </div>
      <p class="text-[11px] text-t-3">
        「复习扫描」会按上方衰减天数刷新班级掌握度，并为 fading/meteor/dim 行星写入学生每日任务与站内通知。
      </p>
    </form>
  </div>
</template>

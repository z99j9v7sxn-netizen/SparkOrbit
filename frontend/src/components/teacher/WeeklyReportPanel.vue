<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { fetchWeeklyReport, type WeeklyReport } from '../../api/teacherSuite';
import { parseApiError } from '../../api/errors';
import MarkdownView from '../common/MarkdownView.vue';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';
import TeacherStatCard from './TeacherStatCard.vue';
import { useTeacherClassStore } from '../../stores/teacherClass';

const classStore = useTeacherClassStore();
const { classId, currentClassName } = storeToRefs(classStore);

const report = ref<WeeklyReport | null>(null);
const loading = ref(false);
const error = ref('');

async function load() {
  if (!classId.value) {
    report.value = null;
    return;
  }
  loading.value = true;
  error.value = '';
  try {
    report.value = await fetchWeeklyReport(classId.value);
  } catch (e) {
    error.value = parseApiError(e, '生成周报失败');
  } finally {
    loading.value = false;
  }
}

function downloadMarkdown() {
  if (!report.value) return;
  const blob = new Blob([report.value.markdown], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${currentClassName.value || '班级'}周报_${report.value.period.replace(/ ~ /g, '_')}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

async function copyMarkdown() {
  if (!report.value) return;
  await navigator.clipboard.writeText(report.value.markdown);
}

watch(classId, () => void load());
onMounted(() => void load());
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="教学周报" subtitle="自动汇总近 7 日班级学情 · 支持下载 Markdown 存档或发给家长">
      <template #actions>
        <button type="button" class="t-btn t-btn--ghost t-btn--sm" :disabled="loading" @click="load">
          {{ loading ? '生成中…' : '重新生成' }}
        </button>
        <button type="button" class="t-btn t-btn--soft t-btn--sm" :disabled="!report" @click="copyMarkdown">复制</button>
        <button type="button" class="t-btn t-btn--primary t-btn--sm" :disabled="!report" @click="downloadMarkdown">
          下载 .md
        </button>
      </template>
    </TeacherPageHeader>

    <TeacherLoading v-if="loading" :rows="6" />
    <p v-else-if="error" class="rounded-xl border border-t-danger/30 bg-t-danger/10 px-4 py-3 text-sm text-t-danger">{{ error }}</p>

    <template v-else-if="report">
      <div class="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <TeacherStatCard label="班级人数" :value="report.stats.total_students" />
        <TeacherStatCard label="平均掌握率" :value="`${report.stats.avg_mastery_rate}%`" accent="emerald" />
        <TeacherStatCard label="本周作业" :value="report.stats.assignments_this_week" accent="sky" />
        <TeacherStatCard label="高风险学生" :value="report.stats.high_risk_count" accent="rose" />
        <TeacherStatCard label="激励发放" :value="report.stats.praise_count" accent="amber" />
      </div>

      <section class="t-card glass-edge p-6">
        <div class="flex items-baseline justify-between gap-2">
          <span class="t-kicker">{{ report.period }}</span>
          <span class="text-[10px] text-t-3">生成于 {{ report.generated_at?.slice(0, 16)?.replace('T', ' ') }}</span>
        </div>
        <div class="mt-3">
          <MarkdownView :content="report.markdown" />
        </div>
      </section>
    </template>
    <TeacherEmptyState v-else title="请先选择班级" description="选择班级后自动生成本周教学周报" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import {
  challengeCheckin,
  fetchChallengeStatus,
  fetchExamMeta,
  joinChallenge,
  type ChallengeStatus,
  type ExamTypeMeta,
} from '../../../api/exam';
import { useOrbitStore } from '../../../stores/orbit';
import { LzBadge, LzButton, LzCard, LzProgress, LzTabs, type LzTabItem } from '../ui';
import ExamPractice from './ExamPractice.vue';
import ExamMock from './ExamMock.vue';
import ExamVocab from './ExamVocab.vue';
import ExamListening from './ExamListening.vue';
import ExamEssay from './ExamEssay.vue';

const orbit = useOrbitStore();
const examTypes = ref<ExamTypeMeta[]>([]);
const examType = ref('cet4');
const tab = ref('practice');
const challenge = ref<ChallengeStatus>({ active: false });
const checkinBusy = ref(false);

const TABS: LzTabItem[] = [
  { key: 'practice', label: '专项刷题' },
  { key: 'mock', label: '全真模考' },
  { key: 'vocab', label: '词汇训练' },
  { key: 'listening', label: '听力精听' },
  { key: 'essay', label: '写译批改' },
];

async function loadMeta() {
  try {
    const meta = await fetchExamMeta();
    examTypes.value = meta.exam_types;
  } catch {
    examTypes.value = [
      { key: 'cet4', label: 'CET-4' },
      { key: 'cet6', label: 'CET-6' },
    ];
  }
}

async function loadChallenge() {
  challenge.value = await fetchChallengeStatus().catch(() => ({ active: false }));
}

async function onJoinChallenge() {
  try {
    await joinChallenge(examType.value);
    orbit.pushNotification('21 天挑战', '已加入备考挑战，每天完成学习任务后记得打卡！', 'success');
    await loadChallenge();
  } catch (e) {
    orbit.pushNotification('21 天挑战', e instanceof Error ? e.message : '加入失败', 'warning');
  }
}

async function onCheckin() {
  checkinBusy.value = true;
  try {
    const res = await challengeCheckin();
    if (res.finished) {
      orbit.pushNotification('21 天挑战', `🎉 全程挑战完成！奖励 ${res.points_earned} 积分`, 'success');
    } else {
      orbit.pushNotification('21 天挑战', `打卡成功（第 ${res.days_done} 天）+${res.points_earned} 积分`, 'success');
    }
    await loadChallenge();
  } catch (e) {
    orbit.pushNotification('21 天挑战', e instanceof Error ? e.message : '打卡失败', 'warning');
  } finally {
    checkinBusy.value = false;
  }
}

onMounted(() => {
  void loadMeta();
  void loadChallenge();
});
</script>

<template>
  <div class="dock-panel space-y-4">
    <header class="space-y-1">
      <p class="lz-caption lz-accent-text uppercase tracking-[0.28em]">Exam Center</p>
      <h3 class="lz-title">考级中心</h3>
      <p class="lz-desc">四六级 / 雅思 / 粤语备考：刷题、模考、词汇、精听、写译批改一站式训练。口语训练在「星际通讯舱」。</p>
    </header>

    <div class="flex flex-wrap items-center gap-2">
      <button
        v-for="t in examTypes"
        :key="t.key"
        type="button"
        class="rounded-full border px-3 py-1 text-xs transition"
        :class="examType === t.key
          ? 'border-sky-400/50 bg-sky-500/20 text-sky-100'
          : 'border-white/10 text-slate-400 hover:text-slate-200'"
        @click="examType = t.key"
      >
        {{ t.label }}
      </button>
    </div>

    <!-- 21 天挑战卡 -->
    <LzCard padding="sm">
      <template v-if="challenge.active">
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <LzBadge tone="accent">21 天挑战</LzBadge>
            <span class="lz-caption">第 {{ (challenge.days_done ?? 0) + (challenge.checked_today ? 0 : 1) }} / {{ challenge.days_total }} 天</span>
          </div>
          <LzButton
            v-if="!challenge.checked_today"
            size="sm"
            :variant="challenge.can_checkin ? 'primary' : 'soft'"
            :disabled="!challenge.can_checkin || checkinBusy"
            @click="onCheckin"
          >
            {{ challenge.can_checkin ? '今日打卡' : `进度 ${challenge.today_progress}/${challenge.today_goal}` }}
          </LzButton>
          <LzBadge v-else tone="success">今日已打卡</LzBadge>
        </div>
        <LzProgress
          class="mt-2"
          :value="((challenge.days_done ?? 0) / (challenge.days_total || 21)) * 100"
          :label="`已坚持 ${challenge.days_done} 天 · 每日目标：完成 ${challenge.today_goal} 个学习条目`"
        />
      </template>
      <div v-else class="flex items-center justify-between gap-2">
        <p class="lz-desc">加入 21 天打卡挑战：每天完成 10 个学习条目（做题 / 背词 / 复习），全勤额外 +100 积分</p>
        <LzButton size="sm" variant="primary" @click="onJoinChallenge">加入挑战</LzButton>
      </div>
    </LzCard>

    <LzTabs v-model="tab" :items="TABS" block />

    <ExamPractice v-if="tab === 'practice'" :exam-type="examType" @activity="loadChallenge" />
    <ExamMock v-else-if="tab === 'mock'" :exam-type="examType" @activity="loadChallenge" />
    <ExamVocab v-else-if="tab === 'vocab'" :exam-type="examType" @activity="loadChallenge" />
    <ExamListening v-else-if="tab === 'listening'" :exam-type="examType" @activity="loadChallenge" />
    <ExamEssay v-else-if="tab === 'essay'" :exam-type="examType" @activity="loadChallenge" />
  </div>
</template>

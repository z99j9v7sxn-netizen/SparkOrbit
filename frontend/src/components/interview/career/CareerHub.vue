<script setup lang="ts">
import { ref } from 'vue';
import { LzTabs, type LzTabItem } from '../../learning/ui';
import type { InterviewPracticeQuestion } from '../../../api/interview';
import CampusPortalBoard from './CampusPortalBoard.vue';
import ResumeStudio from './ResumeStudio.vue';
import ApplicationTracker from './ApplicationTracker.vue';
import CompanyQuestionBank from './CompanyQuestionBank.vue';

const emit = defineEmits<{
  (e: 'practice', payload: InterviewPracticeQuestion): void;
  (e: 'open-cabin', payload: { job_role?: string }): void;
}>();

const SECTIONS: LzTabItem[] = [
  { key: 'portals', label: '校招门户' },
  { key: 'resume', label: '简历工坊' },
  { key: 'tracker', label: '投递看板' },
  { key: 'qa', label: '企业面经' },
];

const section = ref('portals');
const trackerKey = ref(0);

function onTracked() {
  trackerKey.value += 1;
}

function gotoTracker() {
  trackerKey.value += 1;
  section.value = 'tracker';
}
</script>

<template>
  <div class="space-y-4">
    <LzTabs :items="SECTIONS" :model-value="section" block @update:model-value="section = $event" />
    <CampusPortalBoard
      v-if="section === 'portals'"
      @tracked="onTracked"
      @goto-tracker="gotoTracker"
    />
    <ResumeStudio v-else-if="section === 'resume'" @open-cabin="emit('open-cabin', $event)" />
    <ApplicationTracker v-else-if="section === 'tracker'" :refresh-key="trackerKey" />
    <CompanyQuestionBank v-else @practice="emit('practice', $event)" />
  </div>
</template>

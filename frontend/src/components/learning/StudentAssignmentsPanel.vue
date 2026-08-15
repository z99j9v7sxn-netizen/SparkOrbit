<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { fetchStudentAssignments, submitAssignment, type AssignmentItem } from '../../api/teacher';
import { LzBadge, LzButton, LzCard, LzEmptyState, LzSection, LzTextarea } from './ui';

const items = ref<AssignmentItem[]>([]);
const contentMap = ref<Record<string, string>>({});
const msg = ref('');

async function load() {
  items.value = await fetchStudentAssignments();
}

async function handleSubmit(item: AssignmentItem) {
  const content = contentMap.value[item.id]?.trim();
  if (!content) return;
  msg.value = '';
  try {
    await submitAssignment(item.id, content);
    msg.value = '提交成功';
    await load();
  } catch {
    msg.value = '提交失败';
  }
}

onMounted(load);
</script>

<template>
  <LzSection title="班级作业" class="p-2">
    <div class="space-y-3">
      <p v-if="msg" class="lz-caption text-emerald-300">{{ msg }}</p>
      <LzCard v-for="a in items" :key="a.id" padding="sm">
        <div class="flex items-start justify-between gap-2">
          <p class="lz-subtitle min-w-0 truncate">{{ a.title }}</p>
          <LzBadge :tone="a.my_status === 'graded' ? 'success' : a.my_status === 'submitted' ? 'accent' : 'neutral'">
            {{ a.my_status || 'pending' }}
          </LzBadge>
        </div>
        <p class="lz-desc mt-1">{{ a.description || '暂无说明' }}</p>
        <p class="lz-caption mt-1">截止 {{ a.due_at?.slice(0, 10) || '无' }}</p>
        <LzTextarea
          v-if="a.my_status !== 'graded' && a.my_status !== 'submitted'"
          v-model="contentMap[a.id]"
          :rows="3"
          placeholder="在此填写作业内容"
          class="mt-2"
        />
        <LzButton
          v-if="a.my_status !== 'graded' && a.my_status !== 'submitted'"
          variant="primary"
          size="sm"
          class="mt-2"
          @click="handleSubmit(a)"
        >
          提交
        </LzButton>
        <p v-if="a.my_score != null" class="lz-caption mt-2 text-emerald-300">得分 {{ a.my_score }}</p>
      </LzCard>
      <LzEmptyState v-if="!items.length" icon="📝" title="暂无作业" desc="老师布置班级作业后会出现在这里" />
    </div>
  </LzSection>
</template>

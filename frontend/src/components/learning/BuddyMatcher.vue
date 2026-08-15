<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { createPrivateChat } from '../../api/chat';
import { inviteStudyBuddy } from '../../api/study';
import { fetchBuddyMatches, type BuddyMatch } from '../../api/zone';
import { useOrbitStore } from '../../stores/orbit';
import { LzBadge, LzButton, LzCard, LzEmptyState } from './ui';

const orbit = useOrbitStore();
const matches = ref<BuddyMatch[]>([]);
const invitingId = ref('');

onMounted(async () => {
  matches.value = await fetchBuddyMatches().catch(() => []);
});

async function contact(m: BuddyMatch) {
  try {
    await createPrivateChat(m.user_id);
    orbit.pushNotification('学习搭子', `已发起与 ${m.display_name} 的私聊`, 'success');
    window.dispatchEvent(new CustomEvent('sparkorbit:open-chat'));
  } catch (e) {
    orbit.pushNotification('学习搭子', e instanceof Error ? e.message : '私聊失败', 'warning');
  }
}

async function inviteStudy(m: BuddyMatch) {
  invitingId.value = m.user_id;
  try {
    const res = await inviteStudyBuddy(m.user_id);
    const tip = res.room_name
      ? `已邀请 ${m.display_name} 来「${res.room_name}」共学`
      : `已邀请 ${m.display_name} 一起去自习区`;
    orbit.pushNotification('共学邀请', tip, 'success');
  } catch (e) {
    orbit.pushNotification('共学邀请', e instanceof Error ? e.message : '邀请失败', 'warning');
  } finally {
    invitingId.value = '';
  }
}

function goStudyZone() {
  window.dispatchEvent(new CustomEvent('sparkorbit:enter-zone', { detail: { zone: 'study' } }));
}
</script>

<template>
  <div class="dock-panel space-y-3">
    <div class="flex items-start justify-between gap-2">
      <p class="lz-desc">基于班级专注节奏，推荐互补学习搭子</p>
      <LzButton variant="ghost" size="sm" @click="goStudyZone">去自习区</LzButton>
    </div>
    <LzCard v-for="m in matches" :key="m.user_id" hover padding="sm">
      <div class="flex items-center justify-between gap-2">
        <div class="min-w-0">
          <p class="lz-subtitle truncate">{{ m.display_name }}</p>
          <p class="lz-caption mt-1">{{ m.reason }}</p>
        </div>
        <LzBadge tone="accent">匹配 {{ m.complement_score }}</LzBadge>
      </div>
      <div class="mt-3 flex flex-wrap gap-2">
        <LzButton variant="primary" size="sm" :loading="invitingId === m.user_id" @click="inviteStudy(m)">
          邀请共学
        </LzButton>
        <LzButton variant="soft" size="sm" @click="contact(m)">发起私聊</LzButton>
      </div>
    </LzCard>
    <LzEmptyState
      v-if="!matches.length"
      icon="🤝"
      title="暂无同班搭子推荐"
      desc="等同班同学积累一些专注记录后，会为你匹配互补搭子"
    />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import {
  fetchNotifications,
  fetchUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
  type AppNotification,
} from '../api/notifications';

const emit = defineEmits<{ (e: 'open-chat', roomId: string): void }>();

const open = ref(false);
const unread = ref(0);
const items = ref<AppNotification[]>([]);
let timer: number | null = null;

async function refresh() {
  const [count, list] = await Promise.all([
    fetchUnreadCount().catch(() => ({ count: 0 })),
    fetchNotifications().catch(() => []),
  ]);
  unread.value = count.count;
  items.value = list;
}

async function onClickItem(item: AppNotification) {
  await markNotificationRead(item.id).catch(() => null);
  if (item.link.startsWith('chat:')) {
    emit('open-chat', item.link.replace('chat:', ''));
  }
  open.value = false;
  void refresh();
}

async function readAll() {
  await markAllNotificationsRead().catch(() => null);
  void refresh();
}

onMounted(() => {
  void refresh();
  timer = window.setInterval(refresh, 15000);
});

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer);
});

defineExpose({ refresh });
</script>

<template>
  <div class="relative">
    <button
      class="cosmic-nav-btn relative flex h-9 w-9 items-center justify-center rounded-full text-sm"
      @click="open = !open"
    >
      <img class="h-5 w-5" src="/icons/bell.svg" alt="通知" />
      <span
        v-if="unread > 0"
        class="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] text-white"
      >
        {{ unread > 9 ? '9+' : unread }}
      </span>
    </button>

    <div
      v-if="open"
      class="absolute right-0 top-11 z-50 w-80 overflow-hidden rounded-2xl border border-white/10 bg-black/85 shadow-deep-glass backdrop-blur-xl"
    >
      <div class="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <p class="text-sm font-medium text-white">消息中心</p>
        <button class="text-[11px] text-sky-300" @click="readAll">全部已读</button>
      </div>
      <div class="max-h-80 overflow-y-auto">
        <button
          v-for="item in items"
          :key="item.id"
          class="flex w-full flex-col gap-1 border-b border-white/5 px-4 py-3 text-left hover:bg-white/5"
          :class="item.is_read ? 'opacity-70' : ''"
          @click="onClickItem(item)"
        >
          <p class="text-xs font-medium text-white">{{ item.title }}</p>
          <p class="text-[11px] text-slate-400">{{ item.body }}</p>
        </button>
        <p v-if="!items.length" class="px-4 py-8 text-center text-xs text-slate-500">暂无消息</p>
      </div>
    </div>
  </div>
</template>

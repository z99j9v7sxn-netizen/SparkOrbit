<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import gsap from 'gsap';
import {
  chatWsUrl,
  createGroupChat,
  createPrivateChat,
  createTopicRoom,
  deleteTopicRoom,
  fetchChatMessages,
  fetchChatRooms,
  fetchChatSummary,
  fetchClassmates,
  inviteToGroup,
  sendChatMessage,
  toggleMessageReaction,
  type ChatMessage,
  type ChatRoom,
} from '../../api/chat';
import { useAuthStore } from '../../stores/auth';
import SocialPanel from '../SocialPanel.vue';
import WishWall from './WishWall.vue';
import ResourceStation from './ResourceStation.vue';

type ExploreApp = 'social' | 'wishes' | 'resources';

const auth = useAuthStore();
const rooms = ref<ChatRoom[]>([]);
const activeRoomId = ref('');
const messages = ref<ChatMessage[]>([]);
const draft = ref('');
const classmates = ref<{ id: string; display_name: string }[]>([]);
const loading = ref(false);
/** 右侧主区：null=聊天，否则为探索应用 */
const activeApp = ref<ExploreApp | null>(null);
const summary = ref('');
const summaryOpen = ref(false);
const topicDraft = ref('');
const groupDraft = ref('');
const selectedMembers = ref<string[]>([]);
const reactionEmojis = ['👍', '❤️', '🔥'];
const emojis = ['✨', '🪐', '🔥', '📚', '💪', '⭐'];
const unread = ref<Record<string, number>>({});
const lastSeen = ref<Record<string, string>>({});
let ws: WebSocket | null = null;
let roomPollTimer: number | null = null;
const listRef = ref<HTMLDivElement | null>(null);

const exploreItems: { key: ExploreApp; iconSrc: string; label: string }[] = [
  { key: 'social', iconSrc: '/icons/social.svg', label: '社交' },
  { key: 'wishes', iconSrc: '/icons/wishes.svg', label: '星愿' },
  { key: 'resources', iconSrc: '/icons/resources.svg', label: '资料站' },
];

const exploreTitle = computed(() => {
  if (!activeApp.value) return '';
  return exploreItems.find((i) => i.key === activeApp.value)?.label ?? '';
});

function openExplore(key: ExploreApp) {
  activeApp.value = activeApp.value === key ? null : key;
}

async function selectRoom(id: string) {
  activeApp.value = null;
  activeRoomId.value = id;
  unread.value[id] = 0;
  await loadMessages();
  void loadSummary();
}

const activeRoom = computed(() => rooms.value.find((r) => r.id === activeRoomId.value));

const onlineCount = computed(() => {
  if (!activeRoom.value) return 0;
  if (activeRoom.value.room_type === 'class') return Math.max(classmates.value.length + 1, 2);
  return 2;
});

const displayMessages = computed(() => {
  const out: Array<ChatMessage & { showHeader: boolean; showTime: boolean }> = [];
  messages.value.forEach((msg, i) => {
    const prev = messages.value[i - 1];
    const sameSender = prev?.sender_id === msg.sender_id;
    const gap = prev && msg.created_at && prev.created_at
      ? new Date(msg.created_at).getTime() - new Date(prev.created_at).getTime() > 5 * 60 * 1000
      : true;
    out.push({
      ...msg,
      showHeader: !sameSender || gap,
      showTime: gap || i === messages.value.length - 1,
    });
  });
  return out;
});

function roomIcon(room: ChatRoom): string {
  if (room.room_type === 'class') return '/icons/galaxy.svg';
  if (room.room_type === 'topic') return '/icons/hash.svg';
  if (room.room_type === 'group') return '/icons/users.svg';
  return '/icons/messages.svg';
}

const topicRooms = computed(() => rooms.value.filter((r) => r.room_type === 'topic'));
const groupRooms = computed(() => rooms.value.filter((r) => r.room_type === 'group'));
const mainRooms = computed(() => rooms.value.filter((r) => r.room_type !== 'topic' && r.room_type !== 'group'));

const roomTypeLabel = computed(() => {
  const t = activeRoom.value?.room_type;
  if (t === 'class') return 'CLASS // 班级频道';
  if (t === 'topic') return 'TOPIC // 话题频道';
  if (t === 'group') return 'GROUP // 星际群组';
  return 'DM // 私聊航道';
});

function formatTime(iso?: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function isSystemMessage(content: string): boolean {
  return content.startsWith('📚') || content.startsWith('⏱️') || content.startsWith('🎉');
}

async function loadRooms() {
  loading.value = true;
  try {
    rooms.value = await fetchChatRooms();
    if (!activeRoomId.value && rooms.value.length) {
      activeRoomId.value = rooms.value[0].id;
      await loadMessages();
    }
    classmates.value = await fetchClassmates();
  } finally {
    loading.value = false;
  }
}

async function loadMessages() {
  if (!activeRoomId.value) return;
  messages.value = await fetchChatMessages(activeRoomId.value);
  unread.value[activeRoomId.value] = 0;
  if (messages.value.length) {
    lastSeen.value[activeRoomId.value] = messages.value[messages.value.length - 1].created_at;
  }
  await nextTick();
  if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight;
  connectWs();
}

function connectWs() {
  ws?.close();
  if (!activeRoomId.value) return;
  ws = new WebSocket(chatWsUrl(activeRoomId.value));
  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.type === 'message' && data.message) {
        const msg = data.message as ChatMessage;
        if (msg.room_id === activeRoomId.value) {
          messages.value.push(msg);
          void nextTick(() => {
            if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight;
          });
        } else {
          unread.value[msg.room_id] = (unread.value[msg.room_id] || 0) + 1;
          if (msg.sender_id !== auth.user?.id) {
            window.dispatchEvent(new CustomEvent('sparkorbit:new-chat-message'));
          }
        }
      }
    } catch {
      /* ignore */
    }
  };
}

async function loadSummary() {
  if (!activeRoomId.value) return;
  const res = await fetchChatSummary(activeRoomId.value).catch(() => null);
  summary.value = res?.summary ?? '';
}

async function requestSummary() {
  await loadSummary();
  summaryOpen.value = true;
}

async function createTopic() {
  if (!topicDraft.value.trim()) return;
  const room = await createTopicRoom(topicDraft.value.trim());
  await loadRooms();
  topicDraft.value = '';
  await selectRoom(room.id);
}

async function removeTopic(room: ChatRoom, event: Event) {
  event.stopPropagation();
  if (room.created_by !== auth.user?.id) return;
  if (!window.confirm(`确定删除话题「${room.title}」？此操作不可恢复。`)) return;
  try {
    await deleteTopicRoom(room.id);
    const wasActive = activeRoomId.value === room.id;
    await loadRooms();
    if (wasActive) {
      const fallback = rooms.value.find((r) => r.room_type === 'class') || rooms.value[0];
      activeRoomId.value = fallback?.id || '';
      if (activeRoomId.value) await loadMessages();
      else {
        messages.value = [];
        ws?.close();
      }
    }
  } catch (err) {
    window.alert(err instanceof Error ? err.message : '删除失败');
  }
}

async function createGroup() {
  if (!groupDraft.value.trim()) return;
  const room = await createGroupChat(groupDraft.value.trim(), selectedMembers.value);
  await loadRooms();
  groupDraft.value = '';
  selectedMembers.value = [];
  await selectRoom(room.id);
}

function toggleMember(userId: string) {
  if (selectedMembers.value.includes(userId)) {
    selectedMembers.value = selectedMembers.value.filter((id) => id !== userId);
  } else {
    selectedMembers.value = [...selectedMembers.value, userId];
  }
}

async function inviteMember(userId: string) {
  if (!activeRoomId.value || activeRoom.value?.room_type !== 'group') return;
  await inviteToGroup(activeRoomId.value, userId);
  await loadRooms();
}

/** 反应 emoji 点击时的粒子迸发 */
function spawnBurst(ev: MouseEvent, emoji: string) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const count = 6;
  for (let i = 0; i < count; i += 1) {
    const el = document.createElement('span');
    el.textContent = emoji;
    el.style.cssText = `position:fixed;left:${ev.clientX}px;top:${ev.clientY}px;pointer-events:none;z-index:200;font-size:14px;will-change:transform,opacity;`;
    document.body.appendChild(el);
    const angle = (Math.PI * 2 * i) / count + Math.random() * 0.6;
    const dist = 26 + Math.random() * 26;
    gsap.to(el, {
      x: Math.cos(angle) * dist,
      y: Math.sin(angle) * dist - 22,
      opacity: 0,
      scale: 0.5 + Math.random() * 0.7,
      duration: 0.7,
      ease: 'power2.out',
      onComplete: () => el.remove(),
    });
  }
}

async function react(msg: ChatMessage, emoji: string, ev?: MouseEvent) {
  if (ev) spawnBurst(ev, emoji);
  const reactions = await toggleMessageReaction(msg.id, emoji);
  msg.reactions = reactions;
}

async function submitMessage() {
  if (!draft.value.trim() || !activeRoomId.value) return;
  const content = draft.value.trim();
  draft.value = '';
  try {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'send', token: auth.token, content }));
    } else {
      const msg = await sendChatMessage(activeRoomId.value, content);
      messages.value.push(msg);
    }
  } catch {
    draft.value = content;
  }
}

function onDraftKeydown(ev: KeyboardEvent) {
  if (ev.key === 'Enter' && !ev.shiftKey) {
    ev.preventDefault();
    void submitMessage();
  }
}

function insertEmoji(e: string) {
  draft.value += e;
}

async function checkinBroadcast() {
  draft.value = `📚 学习打卡：今天继续点亮星轨！${new Date().toLocaleTimeString()}`;
  await submitMessage();
}

async function startPrivate(userId: string) {
  const room = await createPrivateChat(userId);
  if (!rooms.value.find((r) => r.id === room.id)) rooms.value.unshift(room);
  await selectRoom(room.id);
}

function onCheckin(ev: Event) {
  const detail = (ev as CustomEvent).detail as { minutes?: number };
  draft.value = `⏱️ 完成专注 ${detail?.minutes ?? 25} 分钟，星轨能量+1`;
  void submitMessage();
}

function onSelectChatRoom(ev: Event) {
  const roomId = (ev as CustomEvent).detail?.roomId as string | undefined;
  if (roomId) void selectRoom(roomId);
}

onMounted(() => {
  void loadRooms();
  roomPollTimer = window.setInterval(() => {
    void loadRooms();
  }, 20000);
  window.addEventListener('sparkorbit:checkin', onCheckin as EventListener);
  window.addEventListener('sparkorbit:select-chat-room', onSelectChatRoom as EventListener);
});
onBeforeUnmount(() => {
  ws?.close();
  if (roomPollTimer) window.clearInterval(roomPollTimer);
  window.removeEventListener('sparkorbit:checkin', onCheckin as EventListener);
  window.removeEventListener('sparkorbit:select-chat-room', onSelectChatRoom as EventListener);
});
</script>
<template>
  <div class="lz-accent-emerald absolute inset-0 flex px-4 pb-24 pt-20">
    <!-- 左栏：频道舱 -->
    <aside class="chat-rail mr-4 hidden w-72 shrink-0 flex-col overflow-hidden rounded-2xl md:flex">
      <div class="min-h-0 flex-1 overflow-y-auto p-4">
        <div class="chat-rail-section-title">
          <span class="lz-hud-label">Channels // 会话</span>
        </div>
        <div class="mt-3 space-y-1.5">
          <button
            v-for="room in mainRooms"
            :key="room.id"
            class="chat-room-item relative w-full rounded-xl px-3 py-2.5 text-left"
            :class="{ 'is-active': !activeApp && activeRoomId === room.id }"
            @click="selectRoom(room.id)"
          >
            <div class="flex items-start gap-3">
              <span class="chat-room-avatar flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"><img class="h-5 w-5" :src="roomIcon(room)" alt="" aria-hidden="true" /></span>
              <div class="min-w-0 flex-1">
                <div class="flex items-center justify-between gap-2">
                  <p class="truncate text-sm font-medium">{{ room.title }}</p>
                  <span v-if="unread[room.id]" class="chat-unread shrink-0">{{ unread[room.id] > 9 ? '9+' : unread[room.id] }}</span>
                </div>
                <p class="truncate text-[11px] text-slate-500">{{ room.last_message || '暂无消息' }}</p>
              </div>
            </div>
          </button>
        </div>

        <div class="chat-rail-section mt-5">
          <div class="chat-rail-section-title">
            <span class="lz-hud-label">Squads // 星际群组</span>
          </div>
          <button
            v-for="room in groupRooms"
            :key="room.id"
            class="chat-room-item mt-1.5 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm"
            :class="{ 'is-active': !activeApp && activeRoomId === room.id }"
            @click="selectRoom(room.id)"
          >
            <span v-if="unread[room.id]" class="chat-unread shrink-0">{{ unread[room.id] > 9 ? '9+' : unread[room.id] }}</span>
            <span class="truncate text-emerald-200/90">{{ room.title }}</span>
          </button>
          <input v-model="groupDraft" class="lz-input mt-2 px-2.5 py-1.5 text-xs" placeholder="群聊名称" />
          <div class="mt-2 max-h-28 space-y-1 overflow-y-auto">
            <label
              v-for="mate in classmates"
              :key="`group-${mate.id}`"
              class="flex items-center gap-2 rounded-lg px-2 py-1 text-xs text-slate-500"
            >
              <input type="checkbox" :checked="selectedMembers.includes(mate.id)" @change="toggleMember(mate.id)" />
              {{ mate.display_name }}
            </label>
          </div>
          <button class="lz-btn lz-btn--soft lz-btn--sm mt-2 w-full" @click="createGroup">建群聊</button>
        </div>

        <div class="chat-rail-section mt-5">
          <div class="chat-rail-section-title">
            <span class="lz-hud-label">Topics // 话题频道</span>
          </div>
          <div
            v-for="room in topicRooms"
            :key="room.id"
            class="chat-room-item mt-1.5 flex w-full items-center gap-1 rounded-xl px-2 py-1.5 text-left text-sm"
            :class="{ 'is-active': !activeApp && activeRoomId === room.id }"
          >
            <button class="min-w-0 flex-1 truncate text-left text-violet-300/90" @click="selectRoom(room.id)">
              {{ room.title }}
            </button>
            <button
              v-if="room.created_by === auth.user?.id"
              class="shrink-0 rounded-lg px-2 py-1 text-[10px] text-rose-300/70 hover:bg-rose-500/15 hover:text-rose-200"
              title="删除话题"
              @click="removeTopic(room, $event)"
            >
              删除
            </button>
          </div>
          <div class="mt-2 flex gap-2">
            <input v-model="topicDraft" class="lz-input flex-1 px-2.5 py-1.5 text-xs" placeholder="新建 #话题" />
            <button class="lz-btn lz-btn--soft lz-btn--sm shrink-0" @click="createTopic">+</button>
          </div>
        </div>

        <div class="chat-rail-section mt-5">
          <div class="chat-rail-section-title">
            <span class="lz-hud-label">Crew // 私聊与邀请</span>
          </div>
          <button
            v-for="mate in classmates"
            :key="mate.id"
            class="chat-room-item mt-1.5 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm text-slate-400"
            @click="activeRoom?.room_type === 'group' ? inviteMember(mate.id) : startPrivate(mate.id)"
          >
            <span class="chat-room-avatar flex h-7 w-7 items-center justify-center rounded-full"><img class="h-4 w-4" src="/icons/profile.svg" alt="" aria-hidden="true" /></span>
            {{ mate.display_name }}
            <span v-if="activeRoom?.room_type === 'group'" class="ml-auto text-[10px] text-emerald-300/80">邀请</span>
          </button>
        </div>
      </div>

      <!-- 舱门：探索应用入口 -->
      <div class="chat-hatch-bar shrink-0 border-t border-white/[0.08] p-3">
        <p class="lz-hud-label mb-2 px-1">Airlock // 探索</p>
        <div class="grid grid-cols-3 gap-2">
          <button
            v-for="item in exploreItems"
            :key="item.key"
            type="button"
            class="chat-hatch flex flex-col items-center gap-1.5 rounded-xl px-2 py-2.5"
            :class="{ 'is-active': activeApp === item.key }"
            @click="openExplore(item.key)"
          >
            <span class="chat-hatch-ring flex h-9 w-9 items-center justify-center rounded-full">
              <img :src="item.iconSrc" alt="" class="h-4 w-4 opacity-90" />
            </span>
            <span class="text-[10px] tracking-wide">{{ item.label }}</span>
          </button>
        </div>
      </div>
    </aside>

    <Transition name="hatch" mode="out-in">
      <!-- 探索应用（舱门展开） -->
      <section
        v-if="activeApp"
        :key="`app-${activeApp}`"
        class="cosmic-panel flex min-w-0 flex-1 flex-col overflow-hidden rounded-2xl"
      >
        <div class="chat-main-head flex items-center justify-between border-b border-white/[0.08] px-4 py-3">
          <div class="flex items-center gap-2.5">
            <span class="lz-pulse-dot" aria-hidden="true"></span>
            <img
              :src="exploreItems.find((i) => i.key === activeApp)?.iconSrc"
              alt=""
              class="h-5 w-5 opacity-80"
            />
            <h2 class="text-sm font-semibold text-slate-100">{{ exploreTitle }}</h2>
            <span class="lz-hud-label hidden sm:inline">Airlock Open</span>
          </div>
          <button
            type="button"
            class="lz-btn lz-btn--ghost lz-btn--sm"
            @click="activeApp = null"
          >
            返回聊天
          </button>
        </div>
        <div
          class="min-h-0 flex-1 p-4"
          :class="activeApp === 'resources' ? 'overflow-hidden' : 'overflow-y-auto'"
        >
          <SocialPanel v-if="activeApp === 'social'" />
          <WishWall v-else-if="activeApp === 'wishes'" />
          <div v-else-if="activeApp === 'resources'" class="h-full min-h-0">
            <ResourceStation />
          </div>
        </div>
      </section>

      <!-- 主聊天 -->
      <section v-else key="chat" class="cosmic-panel flex min-w-0 flex-1 flex-col rounded-2xl p-4">
        <div class="chat-main-head -mx-4 -mt-4 mb-0 flex items-center justify-between rounded-t-2xl border-b border-white/[0.08] px-4 py-3">
          <div class="min-w-0">
            <div class="flex items-center gap-2.5">
              <span class="lz-pulse-dot shrink-0" aria-hidden="true"></span>
              <h2 class="truncate text-lg font-semibold text-slate-100">{{ activeRoom?.title || '聊天区' }}</h2>
              <span class="lz-badge lz-badge--success shrink-0">在线 {{ onlineCount }}</span>
            </div>
            <p class="lz-hud-label mt-1">{{ roomTypeLabel }}</p>
          </div>
          <button
            v-if="activeRoom?.room_type === 'class'"
            class="lz-btn lz-btn--soft lz-btn--sm shrink-0"
            @click="requestSummary"
          >
            星际简报
          </button>
        </div>
        <Transition name="zone-swap">
          <div v-if="summary && summaryOpen" class="lz-edge-glow relative mt-3 rounded-xl bg-white/[0.03] px-3 py-2.5">
            <p class="lz-hud-label mb-1">Briefing // 会话速览</p>
            <p class="pr-6 text-xs leading-relaxed text-slate-300">{{ summary }}</p>
            <button
              class="absolute right-2 top-2 rounded-lg px-1.5 text-xs text-slate-500 hover:bg-white/[0.06] hover:text-slate-300"
              title="收起简报"
              @click="summaryOpen = false"
            >
              ×
            </button>
          </div>
        </Transition>

        <div ref="listRef" class="flex-1 space-y-2 overflow-y-auto py-4">
          <div v-if="loading" class="flex h-full flex-col items-center justify-center gap-2 text-sm text-slate-500">
            <span class="text-2xl">✨</span>
            <span>星轨信号连接中…</span>
          </div>
          <div v-else-if="!messages.length" class="flex h-full flex-col items-center justify-center gap-2 text-center text-sm text-slate-500">
            <span class="text-3xl opacity-60">🪐</span>
            <p>还没有消息，发送第一条星轨问候吧</p>
          </div>
          <template v-else>
            <div
              v-for="msg in displayMessages"
              :key="msg.id"
              class="chat-msg flex"
              :class="isSystemMessage(msg.content) ? 'justify-center' : msg.sender_id === auth.user?.id ? 'justify-end' : 'justify-start'"
            >
              <div
                v-if="isSystemMessage(msg.content)"
                class="chat-sysmsg flex max-w-[85%] items-center gap-3 text-xs text-slate-400"
              >
                <span class="chat-sysmsg-line" aria-hidden="true"></span>
                <span class="shrink-0 max-w-[70%] text-center">{{ msg.content }}</span>
                <span class="chat-sysmsg-line" aria-hidden="true"></span>
              </div>
              <div
                v-else
                class="flex max-w-[78%] gap-2"
                :class="msg.sender_id === auth.user?.id ? 'flex-row-reverse' : 'flex-row'"
              >
                <div class="chat-msg-avatar mt-1 h-8 w-8 shrink-0 overflow-hidden rounded-full">
                  <img v-if="msg.sender_avatar" :src="msg.sender_avatar" class="h-full w-full object-cover" />
                  <div v-else class="flex h-full w-full items-center justify-center text-xs text-slate-400">
                    {{ (msg.sender_name || '?').slice(0, 1) }}
                  </div>
                </div>
                <div class="flex flex-col" :class="msg.sender_id === auth.user?.id ? 'items-end' : 'items-start'">
                  <p v-if="msg.showHeader && msg.sender_id !== auth.user?.id" class="mb-1 text-[10px] text-slate-500">{{ msg.sender_name }}</p>
                  <div
                    class="rounded-2xl px-4 py-2.5 text-sm"
                    :class="msg.sender_id === auth.user?.id
                      ? 'chat-bubble-mine lz-edge-glow rounded-br-md'
                      : 'chat-bubble-theirs rounded-bl-md'"
                  >
                    <p class="whitespace-pre-wrap leading-relaxed">{{ msg.content }}</p>
                  </div>
                  <p v-if="msg.showTime" class="mt-1 text-[10px] text-slate-500" :class="msg.sender_id === auth.user?.id ? 'text-right' : ''">
                    {{ formatTime(msg.created_at) }}
                  </p>
                  <div class="mt-1 flex flex-wrap gap-1">
                    <button
                      v-for="emoji in reactionEmojis"
                      :key="emoji"
                      class="chat-reaction rounded-full border border-white/[0.06] px-1.5 py-0.5 text-[10px]"
                      :class="msg.reactions?.find((r) => r.emoji === emoji)?.reacted_by_me ? 'is-mine' : 'text-slate-500'"
                      @click="react(msg, emoji, $event)"
                    >
                      {{ emoji }}
                      <span v-if="msg.reactions?.find((r) => r.emoji === emoji)?.count">{{ msg.reactions?.find((r) => r.emoji === emoji)?.count }}</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>

        <div class="flex flex-wrap items-center gap-1 border-t border-white/[0.08] pt-2">
          <button v-for="e in emojis" :key="e" class="rounded-xl px-2 py-1 text-sm transition hover:bg-white/[0.05]" @click="insertEmoji(e)">{{ e }}</button>
          <button class="lz-btn lz-btn--soft lz-btn--sm ml-auto" @click="checkinBroadcast">学习打卡</button>
        </div>
        <div class="mt-2 flex gap-2">
          <textarea
            v-model="draft"
            rows="2"
            class="cosmic-input flex-1 resize-none rounded-xl px-4 py-3 text-sm text-slate-100 outline-none"
            placeholder="输入消息… Enter 发送 · Shift+Enter 换行"
            @keydown="onDraftKeydown"
          />
          <button class="lz-btn lz-btn--primary lz-btn--lg self-end" @click="submitMessage">发送</button>
        </div>
      </section>
    </Transition>
  </div>
</template>

<style scoped>
/* 频道舱左栏 */
.chat-rail {
  background:
    linear-gradient(180deg, rgb(var(--lz-accent) / 0.05), transparent 20%),
    rgba(2, 6, 23, 0.6);
  border: 1px solid var(--border-soft);
  backdrop-filter: blur(20px) saturate(150%);
  -webkit-backdrop-filter: blur(20px) saturate(150%);
}

.chat-rail-section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.chat-rail-section-title::after {
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, rgb(var(--lz-accent) / 0.25), transparent);
}

.chat-room-item {
  color: rgb(148 163 184);
  transition: background 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;
}

.chat-room-item:hover {
  background: rgba(255, 255, 255, 0.04);
  color: rgb(226 232 240);
}

.chat-room-item.is-active {
  background: rgb(var(--lz-accent) / 0.1);
  color: #fff;
  box-shadow: inset 0 0 0 1px rgb(var(--lz-accent) / 0.3), 0 0 18px -8px rgb(var(--lz-accent) / 0.4);
}

.chat-room-avatar {
  background: rgba(255, 255, 255, 0.04);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.07);
}

.chat-room-item.is-active .chat-room-avatar {
  box-shadow: inset 0 0 0 1px rgb(var(--lz-accent) / 0.45), 0 0 14px -4px rgb(var(--lz-accent) / 0.6);
}

/* 未读脉冲徽标 */
.chat-unread {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  font-size: 9px;
  font-weight: 700;
  color: #022c22;
  background: rgb(var(--lz-accent-bright));
  box-shadow: 0 0 10px rgb(var(--lz-accent) / 0.8);
  animation: chat-unread-pulse 2s ease-in-out infinite;
}

@keyframes chat-unread-pulse {
  0%, 100% { box-shadow: 0 0 6px rgb(var(--lz-accent) / 0.6); }
  50% { box-shadow: 0 0 14px rgb(var(--lz-accent) / 1); }
}

/* 舱门入口 */
.chat-hatch-bar {
  background: linear-gradient(0deg, rgb(var(--lz-accent) / 0.05), transparent);
}

.chat-hatch {
  color: rgb(148 163 184);
  transition: background 0.18s ease, color 0.18s ease;
}

.chat-hatch:hover {
  background: rgba(255, 255, 255, 0.04);
  color: rgb(226 232 240);
}

.chat-hatch-ring {
  background: rgba(255, 255, 255, 0.04);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.1);
  transition: box-shadow 0.22s ease, transform 0.22s ease;
}

.chat-hatch:hover .chat-hatch-ring {
  transform: scale(1.06);
}

.chat-hatch.is-active {
  color: rgb(var(--lz-accent-bright));
}

.chat-hatch.is-active .chat-hatch-ring {
  box-shadow: inset 0 0 0 1px rgb(var(--lz-accent) / 0.6), 0 0 16px -4px rgb(var(--lz-accent) / 0.7);
}

/* 主区头部 HUD 状态条 */
.chat-main-head {
  background: linear-gradient(90deg, rgb(var(--lz-accent) / 0.08), transparent 60%);
}

/* 消息气泡 */
.chat-msg {
  animation: chat-msg-in 0.3s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes chat-msg-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.chat-msg-avatar {
  background: rgba(255, 255, 255, 0.06);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.1);
}

.chat-bubble-mine {
  color: #ecfdf5;
  background: linear-gradient(135deg, rgb(var(--lz-accent) / 0.22), rgb(56 189 248 / 0.14));
}

.chat-bubble-theirs {
  color: rgb(226 232 240);
  background: rgba(255, 255, 255, 0.05);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.06);
}

/* 系统消息：居中细线嵌章 */
.chat-sysmsg {
  width: 100%;
  max-width: 32rem;
}

.chat-sysmsg-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.14), transparent);
}

/* 反应按钮 */
.chat-reaction {
  transition: background 0.15s ease, border-color 0.15s ease, transform 0.12s ease;
}

.chat-reaction:hover {
  background: rgba(255, 255, 255, 0.05);
  transform: scale(1.08);
}

.chat-reaction:active {
  transform: scale(0.92);
}

.chat-reaction.is-mine {
  border-color: rgb(var(--lz-accent) / 0.4);
  color: rgb(var(--lz-accent-bright));
  background: rgb(var(--lz-accent) / 0.1);
}

/* 舱门展开转场 */
.hatch-enter-active {
  transition: opacity 0.32s cubic-bezier(0.22, 1, 0.36, 1), transform 0.32s cubic-bezier(0.22, 1, 0.36, 1), clip-path 0.32s cubic-bezier(0.22, 1, 0.36, 1);
}

.hatch-leave-active {
  transition: opacity 0.16s ease, transform 0.16s ease;
}

.hatch-enter-from {
  opacity: 0;
  transform: scale(0.985);
  clip-path: inset(12% 0 12% 0 round 16px);
}

.hatch-enter-to {
  clip-path: inset(0 0 0 0 round 16px);
}

.hatch-leave-to {
  opacity: 0;
  transform: scale(0.99);
}

@media (prefers-reduced-motion: reduce) {
  .chat-msg,
  .chat-unread {
    animation: none;
  }

  .hatch-enter-active,
  .hatch-leave-active,
  .chat-reaction,
  .chat-hatch-ring {
    transition: none;
  }
}
</style>

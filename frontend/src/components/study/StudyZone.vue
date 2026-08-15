<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { createPrivateChat, fetchClassmates } from '../../api/chat';
import { inviteStudyBuddy } from '../../api/study';
import {
  fetchRoomPomodoro,
  fetchStudyOccupants,
  joinStudyRoom,
  leaveStudyRoom,
  startRoomPomodoro,
  stopRoomPomodoro,
  studyWsUrl,
  updateStudyStatus,
  type RoomPomodoro,
  type StudyOccupant,
  type StudyRoom,
} from '../../api/study';
import { fetchFocusLeaderboard, fetchShopOwned, postFocusSession, type FocusLeaderboardItem } from '../../api/zone';
import { useAuthStore } from '../../stores/auth';
import { useOrbitStore } from '../../stores/orbit';
import { ZODIAC_CONSTELLATIONS } from '../../three/zodiac-data';
import StudyGalaxy3D from './StudyGalaxy3D.vue';
import StudyStreakCalendar from './StudyStreakCalendar.vue';
import { equipStudyTheme } from '../../api/zone';
import { useCameraSupervisor } from '../../composables/useCameraSupervisor';

const auth = useAuthStore();
const orbit = useOrbitStore();
const {
  active: cameraActive,
  warning,
  mediaStream: cameraStream,
  start: startCamera,
  stop: stopCamera,
} = useCameraSupervisor((msg) => {
  orbit.pushNotification('智能小老师', msg, 'warning');
});
const cameraPreviewRef = ref<HTMLVideoElement | null>(null);

const emit = defineEmits<{
  (e: 'depth-change', label: string | null): void;
}>();

const step = ref<'galaxy' | 'room'>('galaxy');
const galaxyRef = ref<InstanceType<typeof StudyGalaxy3D> | null>(null);
const activeConstellation = ref({ slug: '', name: '' });
const activeRoom = ref<StudyRoom | null>(null);
const occupants = ref<StudyOccupant[]>([]);
const error = ref('');
const loading = ref(false);
const sharedFocus = ref(0);
const focusRunning = ref(false);
const audioTrack = ref<'none' | 'rain' | 'nebula'>('none');
const ownedAudio = ref<string[]>([]);
let ws: WebSocket | null = null;
let heartbeatTimer: number | null = null;
let focusTimer: number | null = null;
const studyTheme = ref(auth.user?.studyTheme || 'theme-gold');
const companionActive = ref(false);
const myStatus = ref<'focus' | 'break' | 'help'>('focus');
const boardTab = ref<'global' | 'room'>('global');

type StudyStatus = 'focus' | 'break' | 'help';

const statusMeta: Record<StudyStatus, { label: string; color: string; activeClass: string }> = {
  focus: {
    label: '专注中',
    color: '#f5d76e',
    activeClass: 'border-astro-bright/60 bg-astro-gold/15 text-astro-bright',
  },
  break: {
    label: '休息中',
    color: '#fb923c',
    activeClass: 'border-orange-400/60 bg-orange-400/10 text-orange-200',
  },
  help: {
    label: '求助中',
    color: '#fb7185',
    activeClass: 'border-rose-400/60 bg-rose-400/10 text-rose-200',
  },
};

const activeZodiac = computed(
  () => ZODIAC_CONSTELLATIONS.find((c) => c.slug === activeConstellation.value.slug) ?? null,
);

function occupantStatusLabel(person: StudyOccupant) {
  const s = (person.status || 'focus') as StudyStatus;
  const label = statusMeta[s]?.label || '专注中';
  if (person.user_id === auth.user?.id) return `你 · ${label}`;
  return label;
}

function occupantStatusColor(person: StudyOccupant) {
  const s = (person.status || 'focus') as StudyStatus;
  return statusMeta[s]?.color ?? statusMeta.focus.color;
}

async function setMyStatus(next: StudyStatus) {
  if (!activeRoom.value) return;
  const prev = myStatus.value;
  myStatus.value = next;
  try {
    await updateStudyStatus(activeRoom.value.id, next);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'status', status: next, token: auth.token }));
    }
  } catch (e) {
    myStatus.value = prev;
    error.value = e instanceof Error ? e.message : '状态更新失败，请重试';
  }
}

let reconnectTimer: number | null = null;
let intentionalClose = false;
let focusStartedAt = 0;

function disconnectWs() {
  intentionalClose = true;
  if (heartbeatTimer) window.clearInterval(heartbeatTimer);
  heartbeatTimer = null;
  if (reconnectTimer) window.clearTimeout(reconnectTimer);
  reconnectTimer = null;
  ws?.close();
  ws = null;
}

function connectWs(roomId: string) {
  if (heartbeatTimer) window.clearInterval(heartbeatTimer);
  heartbeatTimer = null;
  if (reconnectTimer) window.clearTimeout(reconnectTimer);
  reconnectTimer = null;
  intentionalClose = false;
  ws?.close();
  ws = new WebSocket(studyWsUrl(roomId));
  ws.onopen = () => {
    ws?.send(JSON.stringify({ type: 'join', token: auth.token }));
    if (myStatus.value) {
      ws?.send(JSON.stringify({ type: 'status', status: myStatus.value, token: auth.token }));
    }
  };
  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data) as {
      type: string;
      occupants?: StudyOccupant[];
      action?: string;
    } & RoomPomodoro;
    if (data.type === 'presence' && data.occupants) {
      const prev = new Set(occupants.value.map((o) => o.user_id));
      occupants.value = data.occupants;
      const me = data.occupants.find((o) => o.user_id === auth.user?.id);
      if (me?.status) myStatus.value = me.status;
      const newbie = data.occupants.find((o) => !prev.has(o.user_id) && o.user_id !== auth.user?.id);
      if (newbie) orbit.pushNotification('自习室', `${newbie.display_name} 加入了自习室`, 'info');
    } else if (data.type === 'pomodoro') {
      if (data.action === 'start') {
        roomPomodoro.value = { ...data, active: true };
        if (data.started_by !== auth.user?.id) {
          orbit.pushNotification(
            '集体番茄钟',
            `${data.started_by_name || '同学'} 发起了 ${data.minutes} 分钟集体专注，点击加入！`,
            'info',
          );
        }
      } else if (data.action === 'stop') {
        roomPomodoro.value = { active: false };
        orbit.pushNotification('集体番茄钟', '本轮集体专注已结束', 'info');
      }
    }
  };
  ws.onclose = () => {
    if (intentionalClose || step.value !== 'room' || !activeRoom.value) return;
    reconnectTimer = window.setTimeout(async () => {
      if (!activeRoom.value || step.value !== 'room') return;
      try {
        const result = await joinStudyRoom(activeRoom.value.id);
        occupants.value = result.occupants;
        const me = result.occupants.find((o) => o.user_id === auth.user?.id);
        if (me?.status) myStatus.value = me.status;
        connectWs(activeRoom.value.id);
      } catch {
        try {
          occupants.value = await fetchStudyOccupants(activeRoom.value.id);
        } catch {
          /* ignore */
        }
      }
    }, 1500);
  };
  heartbeatTimer = window.setInterval(() => {
    ws?.send(JSON.stringify({ type: 'heartbeat', token: auth.token }));
  }, 25000);
}

const globalLeaderboard = ref<FocusLeaderboardItem[]>([]);
const roomLeaderboard = ref<FocusLeaderboardItem[]>([]);

const shownLeaderboard = computed(() =>
  boardTab.value === 'global' ? globalLeaderboard.value : roomLeaderboard.value,
);

async function refreshLeaderboards() {
  const roomId = activeRoom.value?.id || '';
  const [globalRows, roomRows] = await Promise.all([
    fetchFocusLeaderboard().catch(() => []),
    roomId ? fetchFocusLeaderboard(roomId).catch(() => []) : Promise.resolve([]),
  ]);
  globalLeaderboard.value = globalRows;
  roomLeaderboard.value = roomRows;
}

async function onSelectRoom(room: StudyRoom) {
  loading.value = true;
  error.value = '';
  try {
    const result = await joinStudyRoom(room.id);
    activeRoom.value = result.room;
    occupants.value = result.occupants;
    const me = result.occupants.find((o) => o.user_id === auth.user?.id);
    myStatus.value = me?.status || 'focus';
    step.value = 'room';
    emit('depth-change', '返回星座');
    companionActive.value = true;
    window.dispatchEvent(new CustomEvent('sparkorbit:study-companion'));
    connectWs(room.id);
    await refreshLeaderboards();
    roomPomodoro.value = await fetchRoomPomodoro(room.id).catch(() => ({ active: false }));
    if (pomodoroTicker) window.clearInterval(pomodoroTicker);
    pomodoroTicker = window.setInterval(tickPomodoro, 1000);
    orbit.pushNotification('自习室', `已进入 ${room.name}`, 'success');
  } catch (e) {
    error.value = e instanceof Error ? e.message : '进入失败';
  } finally {
    loading.value = false;
  }
}

const hasRain = computed(() => ownedAudio.value.includes('audio-rain'));
const hasNebula = computed(() => ownedAudio.value.includes('audio-nebula'));

async function loadOwnedAudio() {
  try {
    const items = await fetchShopOwned();
    ownedAudio.value = items.filter((i) => i.kind === 'audio').map((i) => i.item_id);
  } catch {
    ownedAudio.value = [];
  }
}
const audioHint = computed(() => {
  if (audioTrack.value === 'rain') return '雨声白噪音播放中';
  if (audioTrack.value === 'nebula') return '星云脉冲播放中';
  if (!hasRain.value && !hasNebula.value) return '在休闲区商城兑换音轨后解锁';
  return '选择白噪音助你专注';
});

// Web Audio 简单白噪音合成，无需外部音轨文件
let audioCtx: AudioContext | null = null;
let noiseNode: AudioBufferSourceNode | null = null;
let gainNode: GainNode | null = null;

function stopAudio() {
  noiseNode?.stop();
  noiseNode?.disconnect();
  gainNode?.disconnect();
  noiseNode = null;
  gainNode = null;
  audioTrack.value = 'none';
}

function playNoise(kind: 'rain' | 'nebula') {
  if (kind === 'rain' && !hasRain.value) {
    orbit.pushNotification('白噪音', '请先在休闲区商城兑换「雨声白噪音」', 'info');
    return;
  }
  if (kind === 'nebula' && !hasNebula.value) {
    orbit.pushNotification('白噪音', '请先在休闲区商城兑换「星云脉冲」', 'info');
    return;
  }
  stopAudio();
  audioCtx = audioCtx || new AudioContext();
  const bufferSize = audioCtx.sampleRate * 2;
  const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < bufferSize; i++) {
    const white = Math.random() * 2 - 1;
    data[i] = kind === 'rain' ? white * 0.25 : white * 0.12 * Math.sin(i / 800);
  }
  noiseNode = audioCtx.createBufferSource();
  noiseNode.buffer = buffer;
  noiseNode.loop = true;
  gainNode = audioCtx.createGain();
  gainNode.gain.value = 0.18;
  noiseNode.connect(gainNode);
  gainNode.connect(audioCtx.destination);
  noiseNode.start();
  audioTrack.value = kind;
}

async function exitRoom() {
  if (!activeRoom.value) return;
  if (focusRunning.value) await completeSharedFocus();
  stopCamera();
  await leaveStudyRoom(activeRoom.value.id);
  disconnectWs();
  stopAudio();
  if (pomodoroTicker) window.clearInterval(pomodoroTicker);
  pomodoroTicker = null;
  roomPomodoro.value = { active: false };
  invitePickerOpen.value = false;
  activeRoom.value = null;
  occupants.value = [];
  companionActive.value = false;
  step.value = 'galaxy';
  emit('depth-change', '返回黄道十二宫');
}

// ---- 搭子邀请 ----
const invitePickerOpen = ref(false);
const classmates = ref<{ id: string; display_name: string; username: string }[]>([]);
const invitedIds = ref<Set<string>>(new Set());

async function toggleInvitePicker() {
  invitePickerOpen.value = !invitePickerOpen.value;
  if (invitePickerOpen.value && !classmates.value.length) {
    const rows = await fetchClassmates().catch(() => []);
    const inRoom = new Set(occupants.value.map((o) => o.user_id));
    classmates.value = rows.filter((c) => c.id !== auth.user?.id && !inRoom.has(c.id));
  }
}

async function inviteBuddy(buddyId: string, name: string) {
  try {
    await inviteStudyBuddy(buddyId);
    invitedIds.value = new Set([...invitedIds.value, buddyId]);
    orbit.pushNotification('搭子邀请', `已邀请 ${name} 来共学`, 'success');
  } catch (e) {
    error.value = e instanceof Error ? e.message : '邀请失败';
  }
}

function onGalaxyDepth(label: string | null) {
  emit('depth-change', label);
}

function backOneLevel() {
  if (step.value === 'room') {
    void exitRoom();
    return;
  }
  galaxyRef.value?.backToRing();
}

defineExpose({ backOneLevel });

// ---- 集体番茄钟 ----
const roomPomodoro = ref<RoomPomodoro>({ active: false });
const pomodoroRemain = ref(0);
let pomodoroTicker: number | null = null;

const pomodoroRemainLabel = computed(() => {
  const m = Math.floor(pomodoroRemain.value / 60).toString().padStart(2, '0');
  const s = (pomodoroRemain.value % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
});

function tickPomodoro() {
  if (!roomPomodoro.value.active || !roomPomodoro.value.ends_at_ts) {
    pomodoroRemain.value = 0;
    return;
  }
  const remain = Math.max(0, Math.floor(roomPomodoro.value.ends_at_ts - Date.now() / 1000));
  pomodoroRemain.value = remain;
  if (remain <= 0) roomPomodoro.value = { active: false };
}

async function launchGroupPomodoro() {
  if (!activeRoom.value) return;
  try {
    const state = await startRoomPomodoro(activeRoom.value.id, 25);
    roomPomodoro.value = { ...state, active: true };
    if (!focusRunning.value) startSharedFocus();
    orbit.pushNotification('集体番茄钟', '已发起 25 分钟集体专注，房间成员都能看到', 'success');
  } catch (e) {
    error.value = e instanceof Error ? e.message : '发起失败';
  }
}

function joinGroupPomodoro() {
  if (!focusRunning.value) startSharedFocus();
}

async function cancelGroupPomodoro() {
  if (!activeRoom.value) return;
  try {
    await stopRoomPomodoro(activeRoom.value.id);
    roomPomodoro.value = { active: false };
  } catch (e) {
    error.value = e instanceof Error ? e.message : '结束失败';
  }
}

const FOCUS_TOTAL = 25 * 60;

function startSharedFocus() {
  if (focusRunning.value) return;
  focusRunning.value = true;
  focusStartedAt = Date.now();
  sharedFocus.value = FOCUS_TOTAL;
  void setMyStatus('focus');
  focusTimer = window.setInterval(() => {
    if (sharedFocus.value <= 0) {
      void completeSharedFocus();
      return;
    }
    sharedFocus.value -= 1;
    if (companionActive.value && sharedFocus.value === 5 * 60) {
      window.dispatchEvent(new CustomEvent('sparkorbit:study-companion'));
      orbit.pushNotification('桌宠提醒', '还有 5 分钟，坚持住！', 'info');
    }
  }, 1000);
}

async function applyTheme(theme: string) {
  studyTheme.value = theme;
  await equipStudyTheme(theme).catch(() => null);
  if (auth.user) auth.setAuth(auth.token, { ...auth.user, studyTheme: theme });
}

async function completeSharedFocus() {
  focusRunning.value = false;
  if (focusTimer) window.clearInterval(focusTimer);
  focusTimer = null;
  const elapsedSec = focusStartedAt ? Math.max(60, Math.floor((Date.now() - focusStartedAt) / 1000)) : FOCUS_TOTAL;
  const mins = Math.max(1, Math.round(elapsedSec / 60));
  sharedFocus.value = 0;
  focusStartedAt = 0;
  try {
    await postFocusSession(mins, 'study_room', activeRoom.value?.id || '');
    await refreshLeaderboards();
    orbit.pushNotification('共享专注', `完成 ${mins} 分钟自习专注`, 'success');
  } catch {
    /* ignore */
  }
}

const focusDisplay = computed(() => {
  const remain = focusRunning.value ? sharedFocus.value : FOCUS_TOTAL;
  const m = Math.floor(remain / 60).toString().padStart(2, '0');
  const s = (remain % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
});

// SVG 圆环计时器
const RING_R = 84;
const RING_CIRC = 2 * Math.PI * RING_R;
const ringOffset = computed(() => {
  if (!focusRunning.value) return 0;
  const progress = sharedFocus.value / FOCUS_TOTAL;
  return RING_CIRC * (1 - progress);
});

const roomOverlayClass = computed(() => {
  if (studyTheme.value === 'theme-aurora') return 'bg-gradient-to-b from-emerald-950/40 to-[#020617]/72';
  if (studyTheme.value === 'theme-violet') return 'bg-gradient-to-b from-violet-950/40 to-[#020617]/72';
  return 'bg-gradient-to-b from-[#1a1206]/45 to-[#050302]/74';
});

async function privateChat(userId: string, name: string) {
  try {
    const room = await createPrivateChat(userId);
    orbit.pushNotification('私聊', `已开启与 ${name} 的私聊`, 'success');
    window.dispatchEvent(new CustomEvent('sparkorbit:open-chat', { detail: { roomId: room.id } }));
  } catch (e) {
    error.value = e instanceof Error ? e.message : '私聊失败';
  }
}

onMounted(() => {
  void loadOwnedAudio();
  window.addEventListener('sparkorbit:shop-updated', loadOwnedAudio as EventListener);
});

watch([cameraStream, cameraActive], async ([stream, active]) => {
  await nextTick();
  if (!cameraPreviewRef.value) return;
  cameraPreviewRef.value.srcObject = stream;
  if (stream && active) await cameraPreviewRef.value.play().catch(() => undefined);
});

onBeforeUnmount(() => {
  window.removeEventListener('sparkorbit:shop-updated', loadOwnedAudio as EventListener);
  disconnectWs();
  stopAudio();
  if (focusTimer) window.clearInterval(focusTimer);
  if (pomodoroTicker) window.clearInterval(pomodoroTicker);
});
</script>

<template>
  <div class="absolute inset-0">
    <!-- 3D 星空常驻：进房后作为暗化背景 -->
    <StudyGalaxy3D
      ref="galaxyRef"
      :active="step === 'galaxy'"
      :dimmed="step === 'room'"
      @select-constellation="(slug, name) => (activeConstellation = { slug, name })"
      @select-room="onSelectRoom"
      @depth-change="onGalaxyDepth"
    />

    <div
      v-if="step === 'room' && activeRoom"
      class="absolute inset-0 overflow-auto px-4 pb-24 pt-24 backdrop-blur-[3px]"
      :class="roomOverlayClass"
    >
      <div class="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[1fr_340px]">
        <!-- 星盘控制台 -->
        <div class="glass-gold relative overflow-hidden rounded-3xl p-8">
          <div class="absolute left-0 top-0 h-px w-full bg-gradient-to-r from-transparent via-astro-gold/40 to-transparent"></div>
          <div class="absolute left-8 top-0 h-8 w-px bg-astro-gold/30"></div>
          <div class="absolute bottom-0 right-8 h-8 w-px bg-astro-gold/30"></div>

          <StudyStreakCalendar class="mb-6" />

          <!-- 顶部：星座徽章 + 房间名 + 在线数 -->
          <div class="flex items-end justify-between border-b border-astro-gold/15 pb-5">
            <div class="flex items-center gap-4">
              <span
                v-if="activeZodiac"
                class="flex h-14 w-14 items-center justify-center rounded-full border border-astro-gold/40 bg-astro-gold/10 text-2xl text-astro-bright shadow-glow-gold"
              >
                {{ activeZodiac.symbol }}
              </span>
              <div>
                <p class="font-mono-tech text-[10px] uppercase tracking-[0.4em] text-astro-dusk">
                  所在星座 · {{ activeConstellation.name || '未知' }}
                </p>
                <h3 class="font-serif-astro mt-1.5 text-2xl tracking-wide text-astro-cream">{{ activeRoom.name }}</h3>
              </div>
            </div>
            <div class="text-right">
              <p class="text-gold-glow text-3xl font-light">
                {{ occupants.length }}<span class="text-lg text-astro-dusk">/{{ activeRoom.capacity }}</span>
              </p>
              <p class="mt-1 font-mono-tech text-[10px] uppercase tracking-widest text-astro-dusk">在线</p>
            </div>
          </div>

          <!-- 集体番茄钟横幅 -->
          <div
            v-if="roomPomodoro.active"
            class="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-astro-gold/35 bg-astro-gold/10 px-5 py-3"
          >
            <div class="flex items-center gap-3">
              <span class="text-xl">🍅</span>
              <div>
                <p class="text-sm text-astro-cream">
                  {{ roomPomodoro.started_by === auth.user?.id ? '你' : roomPomodoro.started_by_name }} 发起的集体专注 ·
                  {{ roomPomodoro.minutes }} 分钟
                </p>
                <p class="font-mono-tech text-lg text-gold-glow">{{ pomodoroRemainLabel }}</p>
              </div>
            </div>
            <div class="flex gap-2">
              <button
                v-if="!focusRunning"
                class="astro-btn is-active rounded-lg px-4 py-2 text-[11px]"
                @click="joinGroupPomodoro"
              >
                加入本轮
              </button>
              <button
                v-if="roomPomodoro.started_by === auth.user?.id"
                class="rounded-lg border border-rose-400/25 px-4 py-2 text-[11px] text-rose-300 transition-colors hover:bg-rose-400/10"
                @click="cancelGroupPomodoro"
              >
                提前结束
              </button>
            </div>
          </div>
          <div v-else class="mt-6 flex items-center justify-between gap-3 rounded-2xl border border-white/10 px-5 py-3">
            <p class="text-[11px] text-slate-400">发起集体番茄钟，房间里的同学会收到邀请并同步倒计时</p>
            <button class="astro-btn press-fx shrink-0 rounded-lg px-4 py-2 text-[11px]" @click="launchGroupPomodoro">
              🍅 发起集体专注
            </button>
          </div>

          <!-- 我的学习状态 -->
          <div class="glass-gold-card mt-6 rounded-2xl p-5">
            <p class="mb-3 font-mono-tech text-[10px] uppercase tracking-[0.3em] text-astro-dusk">我的学习状态</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="(meta, s) in statusMeta"
                :key="s"
                class="flex items-center gap-2 rounded-xl border px-4 py-2 text-xs transition"
                :class="myStatus === s ? meta.activeClass : 'border-white/10 text-slate-400 hover:bg-white/5'"
                @click="setMyStatus(s as 'focus' | 'break' | 'help')"
              >
                <svg
                  v-if="s === 'focus'"
                  class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                >
                  <circle cx="12" cy="12" r="9" />
                  <circle cx="12" cy="12" r="4" />
                  <circle cx="12" cy="12" r="0.5" fill="currentColor" />
                </svg>
                <svg
                  v-else-if="s === 'break'"
                  class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                >
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
                <svg
                  v-else
                  class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                >
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  <path d="M5 11h14l-1 9a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2l-1-9z" />
                </svg>
                {{ meta.label }}
              </button>
            </div>
          </div>

          <div class="mt-6 grid gap-6 sm:grid-cols-2">
            <!-- 圆环专注计时器 -->
            <div class="glass-gold-card group relative flex flex-col items-center justify-center rounded-2xl p-6">
              <p class="font-mono-tech text-[10px] uppercase tracking-[0.3em] text-astro-dusk">专注计时</p>
              <div class="relative mt-4 h-48 w-48">
                <svg class="h-full w-full -rotate-90" viewBox="0 0 200 200">
                  <defs>
                    <linearGradient id="focus-ring-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stop-color="#d4af37" />
                      <stop offset="100%" stop-color="#f5d76e" />
                    </linearGradient>
                  </defs>
                  <circle cx="100" cy="100" :r="RING_R" fill="none" stroke="rgba(212,175,55,0.12)" stroke-width="5" />
                  <circle
                    cx="100" cy="100" :r="RING_R" fill="none"
                    stroke="url(#focus-ring-gradient)"
                    stroke-width="5"
                    stroke-linecap="round"
                    :stroke-dasharray="RING_CIRC"
                    :stroke-dashoffset="ringOffset"
                    :class="focusRunning ? 'drop-shadow-[0_0_6px_rgba(245,215,110,0.7)]' : 'opacity-60'"
                    style="transition: stroke-dashoffset 1s linear"
                  />
                </svg>
                <div class="absolute inset-0 flex flex-col items-center justify-center">
                  <p class="font-mono-tech text-4xl font-light tracking-wider" :class="focusRunning ? 'text-gold-glow' : 'text-astro-cream'">
                    {{ focusDisplay }}
                  </p>
                  <p v-if="focusRunning" class="mt-1 font-mono-tech text-[10px] uppercase tracking-[0.3em] text-astro-dusk">Focusing</p>
                </div>
              </div>
              <button
                class="astro-btn press-fx mt-5 w-full rounded-xl px-4 py-3 text-xs tracking-widest"
                :class="{ 'is-active': focusRunning }"
                @click="focusRunning ? completeSharedFocus() : startSharedFocus()"
              >
                {{ focusRunning ? '结束专注' : '开启专注' }}
              </button>
            </div>

            <!-- 环境控制台 -->
            <div class="glass-gold-card rounded-2xl p-6">
              <p class="mb-4 font-mono-tech text-[10px] uppercase tracking-[0.3em] text-astro-dusk">环境控制</p>

              <div class="space-y-4">
                <div>
                  <p class="mb-2 text-[10px] text-slate-500">白噪音 · <span class="text-astro-cream/70">{{ audioHint }}</span></p>
                  <div class="flex flex-wrap gap-2">
                    <button
                      class="astro-btn flex items-center gap-1.5 rounded-lg px-4 py-2 text-[11px]"
                      :class="{ 'is-active': audioTrack === 'rain' }"
                      :disabled="!hasRain"
                      :title="hasRain ? '雨声白噪音' : '在休闲区商城兑换「雨声白噪音」后解锁'"
                      @click="playNoise('rain')"
                    >
                      <svg v-if="!hasRain" class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                        <rect x="5" y="11" width="14" height="10" rx="2" />
                        <path d="M8 11V7a4 4 0 0 1 8 0v4" />
                      </svg>
                      雨声
                    </button>
                    <button
                      class="astro-btn flex items-center gap-1.5 rounded-lg px-4 py-2 text-[11px]"
                      :class="{ 'is-active': audioTrack === 'nebula' }"
                      :disabled="!hasNebula"
                      :title="hasNebula ? '星云脉冲' : '在休闲区商城兑换「星云脉冲」后解锁'"
                      @click="playNoise('nebula')"
                    >
                      <svg v-if="!hasNebula" class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                        <rect x="5" y="11" width="14" height="10" rx="2" />
                        <path d="M8 11V7a4 4 0 0 1 8 0v4" />
                      </svg>
                      星云脉冲
                    </button>
                    <button
                      class="rounded-lg border border-rose-400/20 px-4 py-2 text-[11px] text-rose-300 transition-colors hover:bg-rose-400/10"
                      @click="stopAudio"
                    >
                      静音
                    </button>
                  </div>
                </div>

                <div>
                  <p class="mb-2 text-[10px] text-slate-500">智能小老师监督</p>
                  <div v-if="cameraActive" class="mb-3 overflow-hidden rounded-xl border border-astro-gold/25 bg-slate-950">
                    <video
                      ref="cameraPreviewRef"
                      class="aspect-video w-full scale-x-[-1] object-cover"
                      autoplay
                      muted
                      playsinline
                      aria-label="摄像头实时预览"
                    ></video>
                    <p class="border-t border-white/5 px-3 py-2 text-[10px] text-astro-cream/70">
                      监督开启时教师可查看巡查截图
                    </p>
                  </div>
                  <button
                    class="astro-btn rounded-lg px-4 py-2 text-[11px]"
                    :class="{ 'is-active': cameraActive }"
                    @click="cameraActive ? stopCamera() : startCamera()"
                  >
                    {{ cameraActive ? '● 监督中' : '开启摄像头监督' }}
                  </button>
                  <p v-if="warning" class="mt-2 text-[10px] text-amber-300">{{ warning }}</p>
                </div>

                <div>
                  <p class="mb-2 text-[10px] text-slate-500">视觉主题</p>
                  <div class="flex flex-wrap gap-2">
                    <button
                      class="astro-btn rounded-lg px-4 py-2 text-[11px]"
                      :class="{ 'is-active': studyTheme === 'theme-gold' || (!studyTheme && true) }"
                      @click="applyTheme('theme-gold')"
                    >
                      鎏金
                    </button>
                    <button
                      class="rounded-lg border px-4 py-2 text-[11px] transition-colors"
                      :class="studyTheme === 'theme-aurora' ? 'border-emerald-400/50 bg-emerald-400/10 text-emerald-200' : 'border-white/10 text-slate-300 hover:bg-white/5'"
                      @click="applyTheme('theme-aurora')"
                    >
                      极光
                    </button>
                    <button
                      class="rounded-lg border px-4 py-2 text-[11px] transition-colors"
                      :class="studyTheme === 'theme-violet' ? 'border-violet-400/50 bg-violet-400/10 text-violet-200' : 'border-white/10 text-slate-300 hover:bg-white/5'"
                      @click="applyTheme('theme-violet')"
                    >
                      紫星云
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="mt-6 flex items-center justify-between">
            <button
              class="astro-btn press-fx rounded-xl px-6 py-2.5 text-xs"
              @click="exitRoom"
            >
              ← 离开自习室
            </button>
            <p v-if="error" class="text-sm text-rose-400">{{ error }}</p>
          </div>
        </div>

        <!-- 侧边栏：成员与排行 -->
        <div class="space-y-6">
          <aside class="glass-gold rounded-3xl p-6">
            <div class="mb-4 flex items-center justify-between">
              <h4 class="font-mono-tech text-[10px] uppercase tracking-[0.3em] text-astro-dusk">在场同学</h4>
              <button class="astro-btn rounded-lg px-3 py-1.5 text-[10px]" @click="toggleInvitePicker">
                {{ invitePickerOpen ? '收起' : '＋邀请搭子' }}
              </button>
            </div>
            <div v-if="invitePickerOpen" class="mb-3 max-h-[160px] space-y-1.5 overflow-y-auto rounded-xl border border-astro-gold/15 bg-black/20 p-2">
              <div
                v-for="c in classmates"
                :key="c.id"
                class="flex items-center justify-between rounded-lg px-2 py-1.5 text-xs text-slate-300"
              >
                <span class="truncate">{{ c.display_name || c.username }}</span>
                <button
                  class="astro-btn shrink-0 rounded px-2.5 py-1 text-[10px]"
                  :disabled="invitedIds.has(c.id)"
                  @click="inviteBuddy(c.id, c.display_name || c.username)"
                >
                  {{ invitedIds.has(c.id) ? '已邀请' : '邀请' }}
                </button>
              </div>
              <p v-if="!classmates.length" class="py-2 text-center text-[10px] text-slate-500">同班同学都不在线或已在房间里</p>
            </div>
            <div class="max-h-[300px] space-y-3 overflow-y-auto pr-2">
              <div
                v-for="person in occupants"
                :key="person.user_id"
                class="group flex items-center gap-3 rounded-xl border border-astro-gold/10 bg-white/[0.02] p-2.5 transition-colors hover:border-astro-gold/30 hover:bg-astro-gold/5"
              >
                <div class="relative h-10 w-10 shrink-0">
                  <div class="absolute inset-0 rounded-full border border-astro-gold/40"></div>
                  <div class="h-full w-full overflow-hidden rounded-full bg-black/50 p-0.5">
                    <img v-if="person.avatar" :src="person.avatar" class="h-full w-full rounded-full object-cover" />
                    <div v-else class="flex h-full w-full items-center justify-center rounded-full bg-slate-800 text-xs text-astro-cream/70">
                      {{ person.display_name.slice(0, 1) }}
                    </div>
                  </div>
                  <span
                    class="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-black/80"
                    :style="{ background: occupantStatusColor(person) }"
                  ></span>
                </div>
                <div class="min-w-0 flex-1">
                  <p class="truncate text-sm text-slate-200 transition-colors group-hover:text-white">{{ person.display_name }}</p>
                  <p class="font-mono-tech text-[10px]" :style="{ color: occupantStatusColor(person) }">
                    {{ occupantStatusLabel(person) }}
                  </p>
                </div>
                <button
                  v-if="person.user_id !== auth.user?.id"
                  class="astro-btn shrink-0 rounded-lg px-3 py-1.5 text-[10px] opacity-0 transition-all group-hover:opacity-100"
                  @click="privateChat(person.user_id, person.display_name)"
                >
                  私聊
                </button>
              </div>
            </div>
          </aside>

          <aside class="glass-gold rounded-3xl p-6">
            <div class="mb-4 flex items-center justify-between">
              <h4 class="font-mono-tech text-[10px] uppercase tracking-[0.3em] text-astro-dusk">今日专注榜</h4>
              <div class="flex rounded-lg border border-astro-gold/20 p-0.5">
                <button
                  class="rounded-md px-2.5 py-1 text-[10px] transition-colors"
                  :class="boardTab === 'global' ? 'bg-astro-gold/20 text-astro-bright' : 'text-slate-400 hover:text-astro-cream'"
                  @click="boardTab = 'global'"
                >
                  全站
                </button>
                <button
                  class="rounded-md px-2.5 py-1 text-[10px] transition-colors"
                  :class="boardTab === 'room' ? 'bg-astro-gold/20 text-astro-bright' : 'text-slate-400 hover:text-astro-cream'"
                  @click="boardTab = 'room'"
                >
                  本室
                </button>
              </div>
            </div>
            <div class="space-y-2">
              <div
                v-for="(row, i) in shownLeaderboard.slice(0, 5)"
                :key="boardTab + '-' + row.user_id"
                class="flex items-center justify-between rounded-lg px-2 py-1.5 text-sm"
                :class="i === 0 ? 'border border-astro-gold/25 bg-astro-gold/8' : ''"
              >
                <div class="flex items-center gap-3 text-slate-300">
                  <span v-if="i === 0" class="flex w-4 justify-center">
                    <svg class="h-3.5 w-3.5 text-astro-bright" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M3 8l4 4 5-6 5 6 4-4v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8z" />
                    </svg>
                  </span>
                  <span v-else class="w-4 font-mono-tech text-xs text-slate-500">{{ i + 1 }}</span>
                  <span class="max-w-[120px] truncate" :class="i === 0 ? 'text-astro-cream' : ''">{{ row.display_name }}</span>
                </div>
                <span class="font-mono-tech" :class="i === 0 ? 'text-astro-bright' : 'text-astro-cream/80'">
                  {{ row.minutes }}<span class="ml-1 text-[10px] text-slate-500">分钟</span>
                </span>
              </div>
              <p v-if="!shownLeaderboard.length" class="py-4 text-center text-[11px] text-slate-500">暂无数据</p>
            </div>
          </aside>
        </div>
      </div>
    </div>
    <p v-if="loading" class="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-astro-cream">
      进入自习室中…
    </p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import {
  addFriend,
  fetchFriends,
  fetchLeaderboard,
  fetchSosList,
  respondSos,
  type FriendItem,
  type LeaderboardItem,
  type SosBeacon,
} from '../api/orbit';

const leaderboard = ref<LeaderboardItem[]>([]);
const friends = ref<FriendItem[]>([]);
const sosList = ref<SosBeacon[]>([]);
const friendInput = ref('');
const message = ref('');
const respondText = ref<Record<string, string>>({});

async function load() {
  [leaderboard.value, friends.value, sosList.value] = await Promise.all([
    fetchLeaderboard(),
    fetchFriends(),
    fetchSosList(),
  ]);
}

async function handleAddFriend() {
  if (!friendInput.value.trim()) return;
  message.value = '';
  try {
    await addFriend(friendInput.value.trim());
    friendInput.value = '';
    message.value = '已添加好友';
    await load();
  } catch {
    message.value = '添加失败：用户不存在或已是好友';
  }
}

async function handleRespond(beaconId: string) {
  const content = respondText.value[beaconId]?.trim();
  if (!content) return;
  try {
    const res = await respondSos(beaconId, content);
    message.value = res.message;
    respondText.value[beaconId] = '';
    await load();
  } catch {
    message.value = '跃迁应答失败';
  }
}

onMounted(load);
</script>

<template>
  <div class="grid gap-4 lg:grid-cols-2">
    <section class="glass glass-edge rounded-2xl p-4">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-semibold text-white">全息投影榜单</h3>
        <span class="text-[10px] text-slate-400">按点亮行星数排名</span>
      </div>
      <div class="mt-3 space-y-2">
        <div
          v-for="item in leaderboard"
          :key="item.user_id"
          class="flex items-center justify-between rounded-xl border px-3 py-2 text-sm"
          :class="item.is_me ? 'border-sky-400/50 glass-card' : 'border-white/10 glass-card'"
        >
          <div class="flex items-center gap-3">
            <span
              class="flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold"
              :class="item.rank <= 3 ? 'bg-amber-400/20 text-amber-300' : 'bg-white/10 text-slate-300'"
            >{{ item.rank }}</span>
            <span class="text-slate-100">{{ item.display_name }}<span v-if="item.is_me" class="ml-1 text-[10px] text-sky-300">(我)</span></span>
          </div>
          <div class="text-right">
            <p class="text-emerald-300">{{ item.lit_count }} 点亮</p>
            <p class="text-[10px] text-amber-300">{{ item.points }} 积分</p>
          </div>
        </div>
      </div>
    </section>

    <section class="glass glass-edge rounded-2xl p-4">
      <h3 class="text-sm font-semibold text-white">星云求救信号 S.O.S</h3>
      <p class="text-[10px] text-slate-400">已点亮该行星的高分学生可跃迁应答</p>
      <div class="mt-3 space-y-2">
        <div
          v-for="b in sosList"
          :key="b.id"
          class="rounded-xl border border-rose-400/20 glass-card px-3 py-2"
        >
          <p class="text-sm text-rose-100">🆘 {{ b.sender_name }} · {{ b.planet_name }}</p>
          <div v-if="b.can_respond" class="mt-2 flex gap-2">
            <input
              v-model="respondText[b.id]"
              class="flex-1 rounded-lg border border-white/10 glass-card px-2 py-1 text-xs text-white outline-none"
              placeholder="跃迁解答…"
            />
            <button class="rounded-lg glass-btn px-3 py-1 text-xs text-sky-100" @click="handleRespond(b.id)">跃迁</button>
          </div>
          <p v-if="b.is_mine" class="mt-1 text-[10px] text-amber-300">等待救援中…</p>
        </div>
        <p v-if="!sosList.length" class="text-[11px] text-slate-500">全宇宙平静，暂无求救信号。</p>
      </div>
    </section>

    <section class="glass glass-edge rounded-2xl p-4 lg:col-span-2">
      <h3 class="text-sm font-semibold text-white">虫洞好友</h3>
      <div class="mt-3 flex gap-2">
        <input v-model="friendInput" class="flex-1 rounded-xl border border-white/10 glass-card px-3 py-2 text-sm text-slate-100 outline-none" placeholder="输入好友用户名，如 student002" @keyup.enter="handleAddFriend" />
        <button class="rounded-xl glass-btn px-4 py-2 text-sm font-semibold text-white" @click="handleAddFriend">添加</button>
      </div>
      <p v-if="message" class="mt-2 text-[11px] text-sky-300">{{ message }}</p>
      <div class="mt-3 space-y-2">
        <div v-for="f in friends" :key="f.user_id" class="flex items-center justify-between rounded-xl border border-white/10 glass-card px-3 py-2 text-sm">
          <span class="text-slate-100">{{ f.display_name }} <span class="text-[10px] text-slate-500">@{{ f.username }}</span></span>
          <span class="text-emerald-300">{{ f.lit_count }} 点亮</span>
        </div>
        <p v-if="!friends.length" class="rounded-xl border border-dashed border-white/10 glass-card p-3 text-[11px] text-slate-500">还没有好友，添加一位一起探索星轨吧。</p>
      </div>
    </section>
  </div>
</template>

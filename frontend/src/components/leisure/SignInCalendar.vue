<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { fetchSignInStatus, postSignIn, type SignInStatus } from '../../api/zone';
import { useOrbitStore } from '../../stores/orbit';

const orbit = useOrbitStore();
const status = ref<SignInStatus | null>(null);
const loading = ref(false);

async function load() {
  status.value = await fetchSignInStatus().catch(() => null);
}

async function signIn() {
  loading.value = true;
  try {
    status.value = await postSignIn();
    if (status.value.points_awarded > 0) {
      orbit.pushNotification('每日签到', `连续 ${status.value.streak} 天 · +${status.value.points_awarded} 积分`, 'success');
    }
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="dock-panel space-y-3">
    <div class="flex items-center justify-between">
      <div>
        <p class="text-sm font-medium text-white">每日签到</p>
        <p class="text-[11px] text-slate-400">连续 {{ status?.streak ?? 0 }} 天</p>
      </div>
      <button
        class="rounded-full px-4 py-2 text-xs font-semibold"
        :class="status?.signed_today ? 'bg-white/10 text-slate-400' : 'bg-amber-500/20 text-amber-100'"
        :disabled="loading || status?.signed_today"
        @click="signIn"
      >
        {{ status?.signed_today ? '已签到' : '签到' }}
      </button>
    </div>
    <div class="grid grid-cols-7 gap-1">
      <div
        v-for="cell in status?.calendar ?? []"
        :key="cell.day"
        class="aspect-square rounded-md"
        :class="cell.signed ? 'bg-amber-400/30 ring-1 ring-amber-300/40' : 'bg-white/5'"
        :title="cell.day"
      />
    </div>
  </div>
</template>

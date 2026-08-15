<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { fetchShopOwned, equipTitle } from '../../api/zone';
import { TITLE_MAP, titleDisplayName } from '../../constants/titles';
import { useAuthStore } from '../../stores/auth';
import { useOrbitStore } from '../../stores/orbit';

const auth = useAuthStore();
const orbit = useOrbitStore();
const titles = ref<{ id: string; name: string }[]>([]);
const loading = ref(false);

const equippedLabel = computed(() => titleDisplayName(auth.user?.equippedTitle));

async function loadTitles() {
  loading.value = true;
  try {
    const owned = await fetchShopOwned();
    titles.value = owned
      .filter((i) => i.kind === 'title')
      .map((i) => ({ id: i.item_id, name: TITLE_MAP[i.item_id] || i.item_name }));
  } catch {
    titles.value = [];
  } finally {
    loading.value = false;
  }
}

async function equip(id: string) {
  await equipTitle(id);
  if (auth.user) auth.setAuth(auth.token, { ...auth.user, equippedTitle: id });
  orbit.pushNotification('称号', `已佩戴「${TITLE_MAP[id] || id}」`, 'success');
  window.dispatchEvent(new CustomEvent('sparkorbit:shop-updated'));
}

function onShopUpdated() {
  void loadTitles();
}

onMounted(() => {
  void loadTitles();
  window.addEventListener('sparkorbit:shop-updated', onShopUpdated as EventListener);
});

onBeforeUnmount(() => {
  window.removeEventListener('sparkorbit:shop-updated', onShopUpdated as EventListener);
});

watch(
  () => auth.user?.equippedTitle,
  () => {
    /* 佩戴状态来自 auth，列表异步刷新 */
  },
);
</script>

<template>
  <div class="space-y-3">
    <div
      v-if="auth.user?.equippedTitle"
      class="rounded-2xl border border-amber-300/30 bg-amber-500/10 px-4 py-3"
    >
      <p class="text-[10px] uppercase tracking-wider text-amber-200/70">当前佩戴</p>
      <p class="mt-0.5 text-sm font-semibold text-amber-100">🏅 {{ equippedLabel }}</p>
    </div>
    <p class="text-xs text-slate-400">在休闲区商城兑换称号后，在此佩戴展示</p>
    <button
      v-for="t in titles"
      :key="t.id"
      class="flex w-full items-center justify-between rounded-2xl border p-3 text-left"
      :class="auth.user?.equippedTitle === t.id ? 'border-amber-300/30 bg-amber-500/10' : 'border-white/10 bg-white/5'"
      @click="equip(t.id)"
    >
      <span class="text-sm text-white">{{ t.name }}</span>
      <span class="text-[10px] text-amber-200">{{ auth.user?.equippedTitle === t.id ? '已佩戴' : '佩戴' }}</span>
    </button>
    <p v-if="loading" class="py-6 text-center text-sm text-slate-500">加载中…</p>
    <p v-else-if="!titles.length" class="py-6 text-center text-sm text-slate-500">暂无称号，去商城兑换吧</p>
  </div>
</template>

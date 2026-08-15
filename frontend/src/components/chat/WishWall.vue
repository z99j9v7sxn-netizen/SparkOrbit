<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { createWish, fetchWishes, likeWish, type WishItem } from '../../api/zone';

const items = ref<WishItem[]>([]);
const draft = ref('');
const loading = ref(false);

async function load() {
  items.value = await fetchWishes().catch(() => []);
}

async function publish() {
  if (!draft.value.trim()) return;
  loading.value = true;
  try {
    await createWish(draft.value.trim());
    draft.value = '';
    await load();
  } finally {
    loading.value = false;
  }
}

async function like(id: string) {
  await likeWish(id);
  await load();
}

onMounted(load);
</script>

<template>
  <div class="space-y-3">
    <textarea v-model="draft" rows="3" class="cosmic-input w-full rounded-xl px-3 py-2 text-sm outline-none" placeholder="写下你的学习心愿或班级公告…" />
    <button class="w-full rounded-xl bg-fuchsia-500/20 px-3 py-2 text-sm text-fuchsia-100" :disabled="loading" @click="publish">发布星愿</button>
    <div class="max-h-80 space-y-2 overflow-auto">
      <article v-for="item in items" :key="item.id" class="rounded-xl border border-white/10 bg-white/5 p-3">
        <div class="flex items-center justify-between">
          <p class="text-xs font-medium text-white">{{ item.display_name }}</p>
          <button class="text-[11px] text-amber-200" @click="like(item.id)">★ {{ item.likes }}</button>
        </div>
        <p class="mt-2 text-sm leading-5 text-slate-300">{{ item.content }}</p>
      </article>
      <p v-if="!items.length" class="py-8 text-center text-sm text-slate-500">还没有星愿，做第一条吧</p>
    </div>
  </div>
</template>

<script setup lang="ts">

import { onMounted, ref } from 'vue';

import { fetchShopItems, fetchShopOwned, redeemShopItem, type OwnedShopItem, type ShopItem } from '../../api/zone';

import { selectPet } from '../../api/pet';

import { useAuthStore } from '../../stores/auth';

import { useOrbitStore } from '../../stores/orbit';



const auth = useAuthStore();

const orbit = useOrbitStore();

const items = ref<ShopItem[]>([]);

const owned = ref<OwnedShopItem[]>([]);

const loading = ref(false);

const message = ref('');



async function reload() {

  const [shop, mine] = await Promise.all([

    fetchShopItems().catch(() => []),

    fetchShopOwned().catch(() => []),

  ]);

  items.value = shop;

  owned.value = mine;

}



onMounted(reload);



function isOwned(id: string) {

  return owned.value.some((o) => o.item_id === id);

}



async function redeem(item: ShopItem) {

  if (isOwned(item.id)) {

    message.value = '已拥有该商品';

    return;

  }

  loading.value = true;

  message.value = '';

  try {

    const res = await redeemShopItem(item.id);

    message.value = `兑换成功：${item.name}`;

    orbit.pushNotification('积分商城', `兑换 ${item.name}`, 'success');

    if (item.kind === 'pet' && auth.user) {

      const slug = res.pet_slug || item.pet_slug || '';

      if (slug) {

        await selectPet(slug);

        auth.setAuth(auth.token, { ...auth.user, petSlug: slug });

      }

    }

    if (auth.user && typeof res.points === 'number') {

      auth.setAuth(auth.token, { ...auth.user });

    }

    await reload();

    window.dispatchEvent(new CustomEvent('sparkorbit:shop-updated'));

  } catch (e) {

    message.value = e instanceof Error ? e.message : '兑换失败';

  } finally {

    loading.value = false;

  }

}

</script>



<template>

  <div class="dock-panel space-y-3">

    <p v-if="message" class="text-xs text-amber-200">{{ message }}</p>

    <div class="space-y-2">

      <button

        v-for="item in items"

        :key="item.id"

        class="flex w-full items-center justify-between rounded-2xl border p-3 text-left transition"

        :class="isOwned(item.id) ? 'border-emerald-400/25 bg-emerald-500/5' : 'border-white/10 bg-white/5 hover:border-amber-300/30'"

        :disabled="loading || isOwned(item.id)"

        @click="redeem(item)"

      >

        <div>

          <p class="text-sm font-medium text-white">

            {{ item.name }}

            <span v-if="isOwned(item.id)" class="ml-1 text-[10px] text-emerald-300">已拥有</span>

          </p>

          <p class="mt-1 text-[11px] text-slate-400">{{ item.description }}</p>

        </div>

        <span class="rounded-full bg-amber-500/15 px-2 py-1 text-xs text-amber-200">{{ item.cost }} 积分</span>

      </button>

    </div>

  </div>

</template>


<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import {
  DEFAULT_PET_SLUG,
  FREE_PET_SLUGS,
  fetchOwnedPets,
  fetchPets,
  selectPet,
  type PetManifest,
} from '../../api/pet';
import { useAuthStore } from '../../stores/auth';

const emit = defineEmits<{ (e: 'selected', slug: string): void; (e: 'close'): void }>();
const auth = useAuthStore();
const pets = ref<PetManifest[]>([]);
const ownedSlugs = ref<Set<string>>(new Set(FREE_PET_SLUGS));
const loading = ref(false);
const error = ref('');

function previewStyle(pet: PetManifest) {
  const row = pet.format === 'codex' ? (pet.animation_row ?? 0) : 0;
  const col = 0;
  const cols = Math.max(pet.columns, 1);
  const rows = Math.max(pet.rows, 1);
  const xPct = cols > 1 ? (col / (cols - 1)) * 100 : 0;
  const yPct = rows > 1 ? (row / (rows - 1)) * 100 : 0;
  const aspect =
    pet.cell_width && pet.cell_height
      ? { aspectRatio: `${pet.cell_width} / ${pet.cell_height}` }
      : {};
  return {
    ...aspect,
    backgroundImage: `url(${pet.sprite_url || pet.preview_url})`,
    backgroundSize: `${cols * 100}% ${rows * 100}%`,
    backgroundPosition: `${xPct}% ${yPct}%`,
    backgroundRepeat: 'no-repeat',
  };
}

const ownedPets = computed(() => pets.value.filter((p) => ownedSlugs.value.has(p.slug)));
const lockedPets = computed(() => pets.value.filter((p) => !ownedSlugs.value.has(p.slug)));

onMounted(async () => {
  const [list, owned] = await Promise.all([
    fetchPets(),
    fetchOwnedPets().catch(() => ({ owned: [...FREE_PET_SLUGS] })),
  ]);
  pets.value = list;
  ownedSlugs.value = new Set(owned.owned?.length ? owned.owned : FREE_PET_SLUGS);
  if (auth.user?.petSlug) ownedSlugs.value.add(auth.user.petSlug);
});

async function choose(slug: string) {
  if (!ownedSlugs.value.has(slug)) {
    error.value = '尚未解锁，请先到积分商城兑换';
    return;
  }
  loading.value = true;
  error.value = '';
  try {
    await selectPet(slug);
    if (auth.user) {
      auth.setAuth(auth.token, { ...auth.user, petSlug: slug });
    }
    emit('selected', slug);
    emit('close');
  } catch (e) {
    error.value = e instanceof Error ? e.message : '切换失败';
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="cosmic-panel absolute bottom-36 right-5 z-30 w-80 rounded-2xl p-4">
    <div class="mb-3 flex items-center justify-between">
      <h3 class="text-sm font-semibold text-white">选择桌宠</h3>
      <button class="text-xs text-slate-400 hover:text-white" @click="emit('close')">关闭</button>
    </div>
    <p v-if="error" class="mb-2 text-[11px] text-rose-300">{{ error }}</p>
    <div class="max-h-80 space-y-3 overflow-auto">
      <div class="grid grid-cols-2 gap-3">
        <button
          v-for="pet in ownedPets"
          :key="pet.slug"
          class="rounded-2xl border border-white/10 bg-white/5 p-3 text-left transition hover:border-sky-400/30"
          :disabled="loading"
          @click="choose(pet.slug)"
        >
          <div class="mb-2 flex h-16 items-center justify-center overflow-hidden rounded-xl bg-black/30">
            <div class="w-14" :style="previewStyle(pet)" />
          </div>
          <p class="text-sm font-medium text-white">{{ pet.name }}</p>
          <p class="mt-1 line-clamp-2 text-[11px] text-slate-400">{{ pet.description }}</p>
        </button>
      </div>
      <div v-if="lockedPets.length" class="border-t border-white/10 pt-3">
        <p class="mb-2 text-[10px] uppercase tracking-wider text-slate-500">未解锁 · 积分商城兑换</p>
        <div class="grid grid-cols-2 gap-2">
          <div
            v-for="pet in lockedPets"
            :key="pet.slug"
            class="rounded-2xl border border-white/5 bg-white/[0.03] p-2 opacity-60"
          >
            <div class="mb-1 flex h-12 items-center justify-center overflow-hidden rounded-lg bg-black/30">
              <div class="w-10" :style="previewStyle(pet)" />
            </div>
            <p class="text-xs text-slate-400">{{ pet.name }}</p>
          </div>
        </div>
      </div>
    </div>
    <p v-if="!pets.length" class="py-6 text-center text-sm text-slate-500">暂无桌宠</p>
    <p v-else-if="!ownedPets.length" class="py-4 text-center text-xs text-slate-500">
      暂无已拥有桌宠，默认免费宠为 {{ DEFAULT_PET_SLUG }}
    </p>
  </div>
</template>

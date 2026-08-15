<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import {
  DEFAULT_PET_SLUG,
  FREE_PET_SLUGS,
  fetchOwnedPets,
  fetchPets,
  fetchPetAffinity,
  selectPet,
  type PetManifest,
} from '../../api/pet';
import { useAuthStore } from '../../stores/auth';
import PetStage from '../pet/PetStage.vue';

const auth = useAuthStore();
const pets = ref<PetManifest[]>([]);
const affinity = ref({ pet_affinity: 0, level: 0, level_name: '陌生' });
const previewSlug = ref('');
const ownedSlugs = ref<Set<string>>(new Set(FREE_PET_SLUGS));
const choosing = ref('');

const currentSlug = computed(() => auth.user?.petSlug || DEFAULT_PET_SLUG);

onMounted(async () => {
  const [list, owned] = await Promise.all([
    fetchPets(),
    fetchOwnedPets().catch(() => ({ owned: [...FREE_PET_SLUGS] })),
  ]);
  pets.value = list;
  ownedSlugs.value = new Set(owned.owned?.length ? owned.owned : FREE_PET_SLUGS);
  if (auth.user?.petSlug) ownedSlugs.value.add(auth.user.petSlug);
  affinity.value = await fetchPetAffinity().catch(() => affinity.value);
  const preferred = auth.user?.petSlug || '';
  previewSlug.value =
    preferred && pets.value.some((p) => p.slug === preferred)
      ? preferred
      : pets.value.find((p) => ownedSlugs.value.has(p.slug))?.slug || pets.value[0]?.slug || DEFAULT_PET_SLUG;
  if (auth.user && preferred && preferred !== previewSlug.value) {
    auth.setAuth(auth.token, { ...auth.user, petSlug: previewSlug.value });
  }
});

async function choose(slug: string) {
  if (!ownedSlugs.value.has(slug)) return;
  choosing.value = slug;
  try {
    await selectPet(slug);
    if (auth.user) auth.setAuth(auth.token, { ...auth.user, petSlug: slug });
    previewSlug.value = slug;
  } finally {
    choosing.value = '';
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="grid items-center gap-4 rounded-2xl border border-white/10 bg-black/20 p-4 sm:grid-cols-[minmax(0,280px)_1fr]">
      <div class="min-w-0 overflow-hidden">
        <PetStage :slug="previewSlug" :affinity-level="affinity.level" />
      </div>
      <div class="min-w-0">
        <p class="text-sm text-white">亲密度 Lv.{{ affinity.level }}</p>
        <p class="text-xs text-sky-200">{{ affinity.level_name }} · {{ affinity.pet_affinity }} 点</p>
        <p class="mt-2 text-[11px] text-slate-400">免费桌宠可直接使用；其余需在积分商城兑换。</p>
      </div>
    </div>
    <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      <article
        v-for="pet in pets"
        :key="pet.slug"
        class="rounded-2xl border p-3"
        :class="currentSlug === pet.slug ? 'border-sky-400/30 bg-sky-500/5' : 'border-white/10 bg-white/5'"
      >
        <div class="flex items-start justify-between gap-2">
          <p class="text-sm font-medium text-white">{{ pet.name }}</p>
          <span
            class="shrink-0 rounded-full px-2 py-0.5 text-[10px]"
            :class="ownedSlugs.has(pet.slug) ? 'bg-emerald-500/15 text-emerald-200' : 'bg-amber-500/15 text-amber-200'"
          >
            {{ FREE_PET_SLUGS.includes(pet.slug as (typeof FREE_PET_SLUGS)[number]) ? '免费' : ownedSlugs.has(pet.slug) ? '已解锁' : '需兑换' }}
          </span>
        </div>
        <p class="mt-1 text-[11px] text-slate-400">{{ pet.description }}</p>
        <p class="mt-2 text-[10px] text-slate-500">{{ pet.actions?.length ?? 0 }} 个动作</p>
        <button
          class="mt-3 rounded-xl border border-white/10 px-3 py-1.5 text-[11px] disabled:opacity-40"
          :class="ownedSlugs.has(pet.slug) ? 'text-sky-100' : 'text-slate-500'"
          :disabled="!ownedSlugs.has(pet.slug) || choosing === pet.slug"
          @click="choose(pet.slug)"
        >
          {{
            currentSlug === pet.slug
              ? '当前桌宠'
              : ownedSlugs.has(pet.slug)
                ? choosing === pet.slug
                  ? '切换中…'
                  : '设为桌宠'
                : '商城解锁'
          }}
        </button>
      </article>
    </div>
  </div>
</template>

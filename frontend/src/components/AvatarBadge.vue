<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import type { AvatarState } from '../api/orbit';
import { generateAvatar, updateUserProfile } from '../api/orbit';
import { fetchShopOwned, type OwnedShopItem } from '../api/zone';
import { titleDisplayName } from '../constants/titles';
import { useAuthStore } from '../stores/auth';

const props = defineProps<{
  avatar?: AvatarState | null;
}>();

const emit = defineEmits<{ (e: 'logout'): void; (e: 'updated'): void }>();

const auth = useAuthStore();
const open = ref(false);
const editing = ref(false);
const editName = ref('');
const uploading = ref(false);
const uploadError = ref('');
const fileInputRef = ref<HTMLInputElement | null>(null);
const ownedTitles = ref<OwnedShopItem[]>([]);

const activeTitle = computed(() => titleDisplayName(auth.user?.equippedTitle));

const avatarUrl = computed(
  () => props.avatar?.avatar_cartoon_url || auth.user?.avatar || '',
);
const displayName = computed(() => auth.user?.displayName || '星轨学习者');
const points = computed(() => props.avatar?.points ?? 0);
const mastery = computed(() => props.avatar?.mastery_rate ?? 0);
const streak = computed(() => props.avatar?.streak_days ?? 0);

function toggle() {
  open.value = !open.value;
}

function close() {
  open.value = false;
  editing.value = false;
}

function onLogout() {
  close();
  emit('logout');
}

function startEdit() {
  editName.value = displayName.value;
  editing.value = true;
}

async function saveName() {
  if (!editName.value.trim()) return;
  const user = await updateUserProfile(editName.value.trim());
    if (auth.user) {
      auth.setAuth(auth.token, { ...auth.user, displayName: user.display_name, avatar: user.avatar_cartoon_url || user.avatar });
    }
  editing.value = false;
  emit('updated');
}

function pickPhoto() {
  fileInputRef.value?.click();
}

async function onPhotoSelected(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0];
  if (!file) return;
  uploading.value = true;
  uploadError.value = '';
  try {
    const result = await generateAvatar(file);
    if (auth.user && result.cartoon_url) {
      auth.setAuth(auth.token, { ...auth.user, avatar: result.cartoon_url });
    }
    emit('updated');
  } catch (e) {
    uploadError.value = e instanceof Error ? e.message : '上传失败';
  } finally {
    uploading.value = false;
  }
}

function onDocClick(ev: MouseEvent) {
  const target = ev.target as HTMLElement;
  if (!target.closest('[data-avatar-badge]')) close();
}

onMounted(() => {
  void fetchShopOwned()
    .then((items) => {
      ownedTitles.value = items.filter((i) => i.kind === 'title');
    })
    .catch(() => {
      ownedTitles.value = [];
    });
  window.addEventListener('sparkorbit:shop-updated', reloadTitles as EventListener);
});

function reloadTitles() {
  void fetchShopOwned()
    .then((items) => {
      ownedTitles.value = items.filter((i) => i.kind === 'title');
    })
    .catch(() => {
      ownedTitles.value = [];
    });
}

if (typeof document !== 'undefined') {
  document.addEventListener('click', onDocClick);
}

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick);
  window.removeEventListener('sparkorbit:shop-updated', reloadTitles as EventListener);
});
</script>

<template>
  <div class="relative" data-avatar-badge>
    <button
      class="flex items-center gap-2 rounded-full border border-white/10 bg-slate-950/70 py-1 pl-1 pr-3 transition hover:border-sky-400/30 hover:bg-white/5"
      @click.stop="toggle"
    >
      <div class="h-9 w-9 overflow-hidden rounded-full ring-2 ring-sky-400/30">
        <img v-if="avatarUrl" :src="avatarUrl" :alt="displayName" class="h-full w-full object-cover" />
        <div v-else class="flex h-full w-full items-center justify-center bg-gradient-to-br from-sky-500/30 to-purple-500/30 text-sm">👤</div>
      </div>
      <span class="hidden max-w-[5rem] truncate text-xs font-medium text-white sm:inline">{{ displayName }}</span>
      <span v-if="activeTitle" class="hidden rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[9px] text-amber-200 sm:inline">{{ activeTitle }}</span>
    </button>

    <transition name="fade">
      <div
        v-if="open"
        class="absolute right-0 top-12 z-50 w-72 rounded-2xl border border-white/10 bg-slate-950/95 p-4 shadow-glow-lg backdrop-blur-xl"
        @click.stop
      >
        <div class="flex items-center gap-3 border-b border-white/10 pb-3">
          <button class="relative h-12 w-12 overflow-hidden rounded-full ring-2 ring-sky-400/40" @click="pickPhoto">
            <img v-if="avatarUrl" :src="avatarUrl" :alt="displayName" class="h-full w-full object-cover" />
            <div v-else class="flex h-full w-full items-center justify-center bg-white/5 text-lg">👤</div>
            <span class="absolute inset-0 flex items-end justify-center bg-black/40 pb-0.5 text-[8px] text-white">更换</span>
          </button>
          <div class="min-w-0 flex-1">
            <input
              v-if="editing"
              v-model="editName"
              class="w-full rounded-lg border border-white/10 bg-black/30 px-2 py-1 text-sm text-white outline-none"
              @keyup.enter="saveName"
            />
            <p v-else class="truncate font-semibold text-white">{{ displayName }}</p>
            <p v-if="activeTitle" class="mt-0.5 truncate text-[10px] text-amber-200">🏅 {{ activeTitle }}</p>
            <p class="text-[11px] text-slate-400">@{{ auth.user?.username }}</p>
          </div>
        </div>

        <div class="mt-2 flex gap-2">
          <button v-if="!editing" class="flex-1 rounded-lg bg-white/5 px-2 py-1.5 text-[11px] text-sky-200" @click="startEdit">编辑昵称</button>
          <button v-else class="flex-1 rounded-lg bg-sky-500/20 px-2 py-1.5 text-[11px] text-sky-100" @click="saveName">保存</button>
          <button class="flex-1 rounded-lg bg-white/5 px-2 py-1.5 text-[11px] text-slate-300" :disabled="uploading" @click="pickPhoto">
            {{ uploading ? '生成中…' : '上传转卡通' }}
          </button>
        </div>
        <p v-if="uploadError" class="mt-1 text-[10px] text-rose-300">{{ uploadError }}</p>
        <input ref="fileInputRef" type="file" accept="image/*" class="hidden" @change="onPhotoSelected" />

        <div class="mt-3 grid grid-cols-3 gap-2 text-center">
          <div class="rounded-xl bg-white/5 px-2 py-2">
            <p class="text-[10px] text-slate-400">积分</p>
            <p class="text-sm font-semibold text-amber-200">{{ points }}</p>
          </div>
          <div class="rounded-xl bg-white/5 px-2 py-2">
            <p class="text-[10px] text-slate-400">掌握率</p>
            <p class="text-sm font-semibold text-sky-200">{{ mastery }}%</p>
          </div>
          <div class="rounded-xl bg-white/5 px-2 py-2">
            <p class="text-[10px] text-slate-400">连续天</p>
            <p class="text-sm font-semibold text-fuchsia-200">{{ streak }}</p>
          </div>
        </div>

        <div v-if="auth.user?.classId" class="mt-3 rounded-xl bg-white/5 px-3 py-2 text-[11px] text-slate-300">
          班级 ID：{{ auth.user.classId.slice(0, 8) }}…
        </div>

        <button
          class="mt-4 w-full rounded-xl border border-rose-400/20 bg-rose-500/10 px-3 py-2 text-xs text-rose-100 transition hover:bg-rose-500/20"
          @click="onLogout"
        >
          退出登录
        </button>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
























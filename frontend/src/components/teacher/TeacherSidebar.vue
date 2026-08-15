<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useNavIndicator } from '../../composables/useNavIndicator';
import { useAuthStore } from '../../stores/auth';
import OrbAvatar from '../common/orb/OrbAvatar.vue';
import { teacherNavGroups } from './teacherNav';

const props = defineProps<{
  open?: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'navigate'): void;
}>();

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const navRef = ref<HTMLElement | null>(null);
const indicatorRef = ref<HTMLElement | null>(null);

useNavIndicator(navRef, indicatorRef);

const COLLAPSE_KEY = 'sparkorbit.teacher.sidebar-collapsed';
const collapsed = ref(localStorage.getItem(COLLAPSE_KEY) === '1');

function toggleCollapsed() {
  collapsed.value = !collapsed.value;
  try {
    localStorage.setItem(COLLAPSE_KEY, collapsed.value ? '1' : '0');
  } catch {
    /* ignore */
  }
}

const displayName = computed(() => auth.user?.displayName || auth.user?.username || '教师');

const activePath = computed(() => {
  const p = route.path;
  if (p.startsWith('/teacher/students/') && route.params.id) return '/teacher/students';
  return p;
});

function isActive(path: string) {
  return (
    activePath.value === path ||
    (path !== '/teacher/students' && route.path.startsWith(path + '/'))
  );
}

function go(path: string) {
  void router.push(path);
  emit('navigate');
  emit('close');
}

function logout() {
  auth.logout();
  void router.push('/');
}
</script>

<template>
  <aside
    class="glass-strong glass-edge flex h-full shrink-0 flex-col border-r border-t-line/10 transition-[width] duration-300"
    :class="[
      props.open === false ? 'hidden lg:flex' : 'flex',
      collapsed ? 'w-60 lg:w-[76px]' : 'w-60',
    ]"
  >
    <!-- 品牌区 + 折叠按钮 -->
    <div
      class="flex items-center gap-3 border-b border-t-line/10 px-4 py-4"
      :class="collapsed ? 'lg:flex-col lg:gap-2 lg:px-2' : ''"
    >
      <div
        class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-t-accent/80 to-t-accent2/70 text-sm font-bold text-white shadow-lg"
        aria-hidden="true"
      >
        S
      </div>
      <div class="min-w-0 flex-1" :class="collapsed ? 'lg:hidden' : ''">
        <h1 class="truncate text-[15px] font-semibold text-t-1">教师工作台</h1>
        <p class="t-kicker mt-0.5">SparkOrbit</p>
      </div>
      <button
        type="button"
        class="hidden h-7 w-7 shrink-0 items-center justify-center rounded-lg text-t-3 transition hover:bg-t-line/10 hover:text-t-1 lg:flex"
        :title="collapsed ? '展开侧栏' : '折叠侧栏'"
        @click="toggleCollapsed"
      >
        <svg viewBox="0 0 16 16" class="h-3.5 w-3.5 transition-transform duration-300" :class="collapsed ? 'rotate-180' : ''" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10 3 5 8l5 5" />
        </svg>
      </button>
    </div>

    <!-- 分组导航 -->
    <nav ref="navRef" class="relative flex-1 overflow-y-auto overflow-x-hidden px-3 py-3" aria-label="教师端导航">
      <span ref="indicatorRef" class="console-nav-indicator" aria-hidden="true" />
      <div v-for="group in teacherNavGroups" :key="group.label" class="mb-3">
        <p
          class="px-2 pb-1.5 pt-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-t-3"
          :class="collapsed ? 'lg:hidden' : ''"
        >
          {{ group.label }}
        </p>
        <div class="space-y-1">
          <button
            v-for="item in group.items"
            :key="item.path"
            type="button"
            class="console-nav-item"
            :class="[{ 'is-active': isActive(item.path) }, collapsed ? 'lg:justify-center lg:px-0' : '']"
            :title="collapsed ? item.label : undefined"
            @click="go(item.path)"
          >
            <img :src="item.icon" alt="" class="t-icon-img h-4 w-4 shrink-0 opacity-90" />
            <span :class="collapsed ? 'lg:hidden' : ''">{{ item.label }}</span>
          </button>
        </div>
      </div>
    </nav>

    <!-- 底部用户卡 -->
    <div class="border-t border-t-line/10 p-3">
      <div
        class="flex items-center gap-2.5 rounded-xl p-2 transition"
        :class="collapsed ? 'lg:flex-col lg:gap-2' : ''"
      >
        <OrbAvatar palette="cyan" :size="32" :label="displayName" />
        <div class="min-w-0 flex-1" :class="collapsed ? 'lg:hidden' : ''">
          <p class="truncate text-[13px] font-medium text-t-1">{{ displayName }}</p>
          <p class="truncate text-[11px] text-t-3">教师账号</p>
        </div>
        <button
          type="button"
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-t-3 transition hover:bg-t-danger/12 hover:text-t-danger"
          title="退出登录"
          @click="logout"
        >
          <svg viewBox="0 0 16 16" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M6 14H3.5A1.5 1.5 0 0 1 2 12.5v-9A1.5 1.5 0 0 1 3.5 2H6" />
            <path d="M10.5 11 14 8l-3.5-3M14 8H6" />
          </svg>
        </button>
      </div>
    </div>
  </aside>
</template>

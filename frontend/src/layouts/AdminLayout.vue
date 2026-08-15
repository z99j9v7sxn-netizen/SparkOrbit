<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { fetchSystemStatus } from '../api/admin';
import AdminCommandPalette from '../components/admin/AdminCommandPalette.vue';
import AdminSidebar from '../components/admin/AdminSidebar.vue';
import { adminNavItems } from '../components/admin/adminNav';
import { useAdminTheme } from '../composables/useAdminTheme';
import { useOrbParallax } from '../composables/useOrbParallax';

const route = useRoute();
const router = useRouter();
const sidebarOpen = ref(false);
const paletteOpen = ref(false);
const shellRef = ref<HTMLElement | null>(null);
const { theme, isLight, toggleTheme } = useAdminTheme();

useOrbParallax(shellRef);

const pageTitle = computed(() => {
  const match = adminNavItems.find(
    (i) => route.path === i.path || (i.path !== '/admin' && route.path.startsWith(i.path + '/')),
  );
  return match?.label ?? '平台运维中心';
});

/* 系统状态胶囊：轮询维护状态 */
type SystemState = 'ok' | 'maintenance' | 'unknown';
const systemState = ref<SystemState>('unknown');
let statusTimer: number | undefined;

async function pollStatus() {
  try {
    const status = await fetchSystemStatus();
    systemState.value = status.enabled ? 'maintenance' : 'ok';
  } catch {
    systemState.value = 'unknown';
  }
}

const statusPill = computed(() => {
  if (systemState.value === 'ok') return { cls: 'adm-pill--ok', label: '运行正常' };
  if (systemState.value === 'maintenance') return { cls: 'adm-pill--warn', label: '维护中' };
  return { cls: 'adm-pill--neutral', label: '状态未知' };
});

function onGlobalKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    paletteOpen.value = !paletteOpen.value;
  }
}

onMounted(() => {
  void pollStatus();
  statusTimer = window.setInterval(() => void pollStatus(), 30000);
  window.addEventListener('keydown', onGlobalKeydown);
});

onBeforeUnmount(() => {
  if (statusTimer) window.clearInterval(statusTimer);
  window.removeEventListener('keydown', onGlobalKeydown);
});
</script>

<template>
  <div ref="shellRef" class="console-shell flex h-dvh overflow-hidden" :data-theme="theme">
    <div class="console-orb console-orb--cyan" aria-hidden="true" />
    <div class="console-orb console-orb--violet" aria-hidden="true" />
    <div v-if="!isLight" class="console-orb console-orb--neon" aria-hidden="true" />

    <div
      v-if="sidebarOpen"
      class="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
      @click="sidebarOpen = false"
    />

    <div
      class="fixed inset-y-0 left-0 z-50 transition-transform duration-300 lg:static lg:translate-x-0"
      :class="sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'"
    >
      <AdminSidebar :open="true" @close="sidebarOpen = false" @navigate="sidebarOpen = false" />
    </div>

    <div class="flex min-w-0 flex-1 flex-col">
      <header
        class="glass glass-edge sticky top-0 z-30 flex flex-wrap items-center justify-between gap-3 border-b border-t-line/10 px-4 py-2.5 lg:px-6"
      >
        <div class="flex min-w-0 items-center gap-3">
          <button
            type="button"
            class="t-theme-toggle lg:hidden"
            aria-label="打开菜单"
            @click="sidebarOpen = true"
          >
            <svg viewBox="0 0 16 16" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
              <path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11" />
            </svg>
          </button>
          <div class="min-w-0">
            <p class="t-kicker">Ops Console</p>
            <h2 class="truncate text-[15px] font-semibold text-t-1">{{ pageTitle }}</h2>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <!-- Ctrl+K 快捷导航入口 -->
          <button
            type="button"
            class="hidden items-center gap-2 rounded-xl border border-t-line/15 bg-t-s1/40 px-3 py-2 text-xs text-t-3 transition hover:border-t-accent/40 hover:text-t-2 sm:flex"
            @click="paletteOpen = true"
          >
            <svg viewBox="0 0 16 16" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
              <circle cx="7" cy="7" r="4.5" />
              <path d="m13.5 13.5-3.2-3.2" />
            </svg>
            <span>搜索页面 / 操作</span>
            <span class="t-kbd">Ctrl K</span>
          </button>

          <!-- 系统状态胶囊 -->
          <button
            type="button"
            class="adm-pill"
            :class="statusPill.cls"
            title="查看维护模式"
            @click="router.push('/admin/maintenance')"
          >
            <span class="adm-pill__dot" aria-hidden="true" />
            {{ statusPill.label }}
          </button>

          <!-- 主题切换 -->
          <button
            type="button"
            class="t-theme-toggle"
            :title="isLight ? '切换到深色主题' : '切换到浅色主题'"
            @click="toggleTheme"
          >
            <svg v-if="isLight" viewBox="0 0 16 16" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
              <path d="M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7Z" />
            </svg>
            <svg v-else viewBox="0 0 16 16" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="8" cy="8" r="3.25" />
              <path d="M8 1.5v1.75M8 12.75v1.75M1.5 8h1.75M12.75 8h1.75M3.4 3.4l1.24 1.24M11.36 11.36l1.24 1.24M12.6 3.4l-1.24 1.24M4.64 11.36 3.4 12.6" />
            </svg>
          </button>

          <RouterLink
            to="/teacher"
            class="rounded-xl border border-t-accent2/30 bg-t-accent2/10 px-3.5 py-2 text-[13px] text-t-accent2 transition hover:bg-t-accent2/20"
          >
            教师工作台
          </RouterLink>
        </div>
      </header>

      <main class="flex-1 overflow-y-auto px-4 py-6 lg:px-6">
        <div class="mx-auto max-w-7xl">
          <RouterView v-slot="{ Component }">
            <Transition name="console-page">
              <component :is="Component" :key="route.path" />
            </Transition>
          </RouterView>
        </div>
      </main>
    </div>

    <AdminCommandPalette :open="paletteOpen" @close="paletteOpen = false" />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import TeacherCommandPalette from '../components/teacher/TeacherCommandPalette.vue';
import FeedbackWidget from '../components/common/FeedbackWidget.vue';
import TeacherSidebar from '../components/teacher/TeacherSidebar.vue';
import { teacherNavItems } from '../components/teacher/teacherNav';
import { useOrbParallax } from '../composables/useOrbParallax';
import { useTeacherTheme } from '../composables/useTeacherTheme';
import { useAuthStore } from '../stores/auth';
import { useTeacherClassStore } from '../stores/teacherClass';

const auth = useAuthStore();
const classStore = useTeacherClassStore();
const route = useRoute();
const sidebarOpen = ref(false);
const paletteOpen = ref(false);
const shellRef = ref<HTMLElement | null>(null);
const { theme, isLight, toggleTheme } = useTeacherTheme();

useOrbParallax(shellRef);

const pageTitle = computed(() => {
  if (route.path.startsWith('/teacher/students/') && route.params.id) return '学生详情';
  const match = teacherNavItems.find(
    (i) => route.path === i.path || route.path.startsWith(i.path + '/'),
  );
  return match?.label ?? '教师工作台';
});

function onClassChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value;
  classStore.setClassId(value);
}

function onGlobalKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    paletteOpen.value = !paletteOpen.value;
  }
}

onMounted(() => {
  void classStore.loadClasses();
  window.addEventListener('keydown', onGlobalKeydown);
});

onBeforeUnmount(() => {
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
      <TeacherSidebar :open="true" @close="sidebarOpen = false" @navigate="sidebarOpen = false" />
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
            <p class="t-kicker">Teacher Console</p>
            <h2 class="truncate text-[15px] font-semibold text-t-1">{{ pageTitle }}</h2>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <!-- Ctrl+K 搜索入口 -->
          <button
            type="button"
            class="hidden items-center gap-2 rounded-xl border border-t-line/15 bg-t-s1/40 px-3 py-2 text-xs text-t-3 transition hover:border-t-accent/40 hover:text-t-2 sm:flex"
            @click="paletteOpen = true"
          >
            <svg viewBox="0 0 16 16" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
              <circle cx="7" cy="7" r="4.5" />
              <path d="m13.5 13.5-3.2-3.2" />
            </svg>
            <span>搜索页面 / 学生</span>
            <span class="t-kbd">Ctrl K</span>
          </button>

          <!-- 班级切换 -->
          <div class="relative flex items-center">
            <span
              class="pointer-events-none absolute left-3 h-1.5 w-1.5 rounded-full"
              :class="classStore.hasClasses ? 'bg-t-ok' : 'bg-t-warn'"
              aria-hidden="true"
            />
            <select
              class="t-input w-auto min-w-32 cursor-pointer appearance-none py-2 pl-6.5 pr-8 text-[13px]"
              :value="classStore.classId"
              :disabled="!classStore.hasClasses"
              @change="onClassChange"
            >
              <option v-if="!classStore.hasClasses" value="">暂无班级</option>
              <option v-for="c in classStore.classes" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
            <svg
              viewBox="0 0 16 16"
              class="pointer-events-none absolute right-3 h-3 w-3 text-t-3"
              fill="none"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="m4 6 4 4 4-4" />
            </svg>
          </div>

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
            v-if="auth.user?.role === 'admin'"
            to="/admin"
            class="rounded-xl border border-t-accent2/30 bg-t-accent2/10 px-3.5 py-2 text-[13px] text-t-accent2 transition hover:bg-t-accent2/20"
          >
            返回管理台
          </RouterLink>
        </div>
      </header>

      <main class="flex-1 overflow-y-auto px-4 py-6 lg:px-6">
        <div class="mx-auto max-w-7xl">
          <div
            v-if="!classStore.loading && !classStore.hasClasses"
            class="mb-5 rounded-2xl border border-t-warn/30 bg-t-warn/10 px-4 py-3 text-sm text-t-warn"
          >
            当前账号尚未关联班级。请联系管理员分配班级，或在「学生名册」中查看邀请码相关说明。
          </div>
          <RouterView v-slot="{ Component }">
            <Transition name="console-page">
              <component :is="Component" :key="route.path" />
            </Transition>
          </RouterView>
        </div>
      </main>
    </div>

    <TeacherCommandPalette :open="paletteOpen" @close="paletteOpen = false" />
    <FeedbackWidget />
  </div>
</template>

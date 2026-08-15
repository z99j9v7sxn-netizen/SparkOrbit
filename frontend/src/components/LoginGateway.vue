<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref } from 'vue';
import { useRouter } from 'vue-router';
import { login, preflightAuth, toAuthUser } from '../api/auth';
import { useAuthStore, type UserRole } from '../stores/auth';
import TerminalAuthShell from './auth/TerminalAuthShell.vue';
import TerminalField from './auth/TerminalField.vue';
import TerminalGeometry from './auth/TerminalGeometry.vue';
import TerminalLogStream from './auth/TerminalLogStream.vue';

type Step = 'role' | 'username' | 'password' | 'granted';

const auth = useAuthStore();
const router = useRouter();

const step = ref<Step>('role');
const roleChoice = ref<UserRole>('student');
const username = ref('');
const password = ref('');
const errorMessage = ref('');
const loading = ref(false);
const doneRole = ref(false);
const doneUser = ref(false);
const donePass = ref(false);

const roleLabelMap: Record<UserRole, string> = {
  student: '学生',
  teacher: '教师',
  admin: '管理员',
};

const roles: { key: UserRole; label: string; hint: string }[] = [
  { key: 'student', label: '1  学生', hint: '星际领航台' },
  { key: 'teacher', label: '2  教师', hint: '教师工作台' },
  { key: 'admin', label: '3  管理员', hint: '系统控制台' },
];

const footerHint = computed(() => {
  if (step.value === 'role') return '按 1 / 2 / 3 选择 · 回车确认';
  if (step.value === 'username') return loading.value ? '正在校验用户名…' : '输入用户名 · 回车继续';
  if (step.value === 'password') return loading.value ? '正在验证…' : '输入密码 · 回车登录';
  return '正在跳转…';
});

function confirmRole(key?: UserRole) {
  if (key) roleChoice.value = key;
  doneRole.value = true;
  step.value = 'username';
  errorMessage.value = '';
}

async function submitUsername() {
  if (!username.value.trim()) {
    errorMessage.value = '请输入用户名';
    return;
  }
  loading.value = true;
  errorMessage.value = '';
  try {
    const result = await preflightAuth(username.value.trim(), roleChoice.value);
    if (!result.ok) {
      errorMessage.value = result.message || '用户名与角色不匹配';
      return;
    }
    doneUser.value = true;
    step.value = 'password';
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '用户名校验失败';
  } finally {
    loading.value = false;
  }
}

async function submitPassword() {
  if (!password.value) {
    errorMessage.value = '请输入密码';
    return;
  }
  loading.value = true;
  errorMessage.value = '';
  try {
    const result = await login(username.value.trim(), password.value, roleChoice.value);
    auth.setAuth(result.access_token, toAuthUser(result.user));
    donePass.value = true;
    step.value = 'granted';
    await nextTick();
    window.setTimeout(() => {
      void router.push(
        result.user.role === 'student' ? '/student' : result.user.role === 'teacher' ? '/teacher' : '/admin',
      );
    }, 600);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登录失败';
  } finally {
    loading.value = false;
  }
}

function onKeydown(ev: KeyboardEvent) {
  if (step.value !== 'role') return;
  if (ev.key === '1') confirmRole('student');
  else if (ev.key === '2') confirmRole('teacher');
  else if (ev.key === '3') confirmRole('admin');
  else if (ev.key === 'Enter') confirmRole();
}

onMounted(() => window.addEventListener('keydown', onKeydown));
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown));
</script>

<template>
  <TerminalAuthShell title="ACCESS_GATE" subtitle="会话启动">
    <div class="mx-auto w-full max-w-md space-y-6">
      <div>
        <p class="text-[11px] tracking-[0.25em] text-[var(--term-muted)]">系统接入验证</p>
        <h1 class="mt-3 text-xl tracking-wide text-[var(--term-fg)] sm:text-2xl">接入认知孪生系统</h1>
        <p class="mt-2 text-[12px] leading-6 text-[var(--term-muted)]">
          逐项确认凭证，按回车进入下一步。
        </p>
      </div>

      <!-- completed lines -->
      <div class="space-y-1 text-[12px]">
        <p v-if="doneRole" class="text-[var(--term-muted)]">
          <span class="text-[var(--term-accent)]">&gt;</span> 角色:
          <span class="ml-2 text-[var(--term-fg)]">{{ roleLabelMap[roleChoice] }}</span>
          <span class="ml-3 text-[var(--term-accent)]">[OK]</span>
        </p>
        <p v-if="doneUser" class="text-[var(--term-muted)]">
          <span class="text-[var(--term-accent)]">&gt;</span> 用户名:
          <span class="ml-2 text-[var(--term-fg)]">{{ username }}</span>
          <span class="ml-3 text-[var(--term-accent)]">[OK]</span>
        </p>
        <p v-if="donePass" class="text-[var(--term-muted)]">
          <span class="text-[var(--term-accent)]">&gt;</span> 密码:
          <span class="ml-2 text-[var(--term-fg)]">********</span>
          <span class="ml-3 text-[var(--term-accent)]">[OK]</span>
        </p>
      </div>

      <!-- role step -->
      <div v-if="step === 'role'" class="space-y-2">
        <p class="text-[11px] tracking-wider text-[var(--term-muted)]">&gt; 选择角色:</p>
        <button
          v-for="r in roles"
          :key="r.key"
          type="button"
          class="flex w-full items-center justify-between border-b border-[var(--term-line)] py-3 text-left text-sm transition hover:border-[var(--term-accent)] hover:text-[var(--term-accent)]"
          :class="roleChoice === r.key ? 'text-[var(--term-accent)]' : 'text-[var(--term-fg)]'"
          @click="confirmRole(r.key)"
        >
          <span>{{ r.label }}</span>
          <span class="text-[10px] tracking-wider text-[var(--term-muted)]">{{ r.hint }}</span>
        </button>
      </div>

      <TerminalField
        v-if="step === 'username' || doneUser"
        v-show="step === 'username'"
        v-model="username"
        label="> 用户名:"
        autocomplete="username"
        :active="step === 'username'"
        :disabled="loading"
        :error="step === 'username' ? errorMessage : ''"
        @submit="submitUsername"
      />

      <TerminalField
        v-if="step === 'password' || donePass"
        v-show="step === 'password'"
        v-model="password"
        label="> 密码:"
        type="password"
        autocomplete="current-password"
        :active="step === 'password'"
        :disabled="loading"
        :error="step === 'password' ? errorMessage : ''"
        @submit="submitPassword"
      />

      <p v-if="step === 'granted'" class="text-sm tracking-wider text-[var(--term-accent)]">
        &gt; 接入成功 · 正在跳转…
      </p>

      <p class="pt-4 text-[10px] tracking-[0.2em] text-[var(--term-muted)]">{{ footerHint }}</p>

      <button
        type="button"
        class="mt-2 text-left text-[11px] tracking-wider text-[var(--term-muted)] underline-offset-4 hover:text-[var(--term-accent)] hover:underline"
        @click="router.push('/register')"
      >
        &gt; 没有账号？去注册
      </button>
    </div>

    <template #geometry>
      <TerminalGeometry />
    </template>
    <template #logs>
      <TerminalLogStream />
    </template>
  </TerminalAuthShell>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { fetchClasses, fetchTeachers, register, checkUsername, toAuthUser } from '../api/auth';
import type { ClassBrief, TeacherBrief } from '../api/auth';
import { useAuthStore, type UserRole } from '../stores/auth';
import TerminalAuthShell from './auth/TerminalAuthShell.vue';
import TerminalField from './auth/TerminalField.vue';
import TerminalGeometry from './auth/TerminalGeometry.vue';
import TerminalLogStream from './auth/TerminalLogStream.vue';

type Step =
  | 'role'
  | 'username'
  | 'display'
  | 'password'
  | 'teacher'
  | 'class'
  | 'photo'
  | 'bio'
  | 'confirm'
  | 'granted';

const auth = useAuthStore();
const router = useRouter();

const step = ref<Step>('role');
const role = ref<UserRole>('student');
const username = ref('');
const password = ref('');
const displayName = ref('');
const teacherId = ref('');
const classId = ref('');
const description = ref('');
const photoFile = ref<File | null>(null);
const previewUrl = ref('');
const teachers = ref<TeacherBrief[]>([]);
const classes = ref<ClassBrief[]>([]);
const loading = ref(false);
const errorMessage = ref('');
const fileInputRef = ref<HTMLInputElement | null>(null);

const completed = ref<Partial<Record<Step, string>>>({});

const filteredClasses = computed(() =>
  teacherId.value ? classes.value.filter((c) => c.teacher_id === teacherId.value) : classes.value,
);

const selectedTeacherName = computed(
  () => teachers.value.find((t) => t.id === teacherId.value)?.display_name || teacherId.value,
);
const selectedClassName = computed(
  () => filteredClasses.value.find((c) => c.id === classId.value)?.name || classId.value,
);

const footerHint = computed(() => {
  if (loading.value) {
    if (step.value === 'username') return '正在校验用户名…';
    return '正在提交…';
  }
  const map: Record<string, string> = {
    role: '按 1 / 2 选择 · 回车确认',
    username: '输入用户名 · 回车继续',
    display: '输入显示名称 · 回车继续',
    password: '输入密码 · 回车继续',
    teacher: '选择负责老师 · 回车确认',
    class: '选择所属班级 · 回车确认',
    photo: '选择文件（可跳过）· 回车继续',
    bio: '输入自我描述，或输入 skip 跳过',
    confirm: '回车完成注册',
    granted: '正在跳转…',
  };
  return map[step.value] || '';
});

onMounted(async () => {
  window.addEventListener('keydown', onRoleKey);
  try {
    [teachers.value, classes.value] = await Promise.all([fetchTeachers(), fetchClasses()]);
    if (teachers.value.length) teacherId.value = teachers.value[0].id;
    if (filteredClasses.value.length) classId.value = filteredClasses.value[0].id;
  } catch {
    /* allow offline form */
  }
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onRoleKey);
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
});

watch(teacherId, () => {
  if (filteredClasses.value.length) classId.value = filteredClasses.value[0].id;
  else classId.value = '';
});

function onRoleKey(ev: KeyboardEvent) {
  if (ev.key === 'Enter') {
    if (step.value === 'role') {
      confirmRole();
      return;
    }
    if (step.value === 'teacher') {
      submitTeacher();
      return;
    }
    if (step.value === 'class') {
      submitClass();
      return;
    }
    if (step.value === 'photo') {
      submitPhoto();
      return;
    }
    if (step.value === 'confirm' && !loading.value) {
      void executeRegister();
      return;
    }
  }
  if (step.value !== 'role') return;
  if (ev.key === '1') confirmRole('student');
  else if (ev.key === '2') confirmRole('teacher');
}

function confirmRole(key?: UserRole) {
  if (key) role.value = key;
  completed.value.role = role.value === 'student' ? '学生' : '教师';
  errorMessage.value = '';
  step.value = 'username';
}

async function submitUsername() {
  const name = username.value.trim();
  if (!name) {
    errorMessage.value = '请输入用户名';
    return;
  }
  loading.value = true;
  errorMessage.value = '';
  try {
    const result = await checkUsername(name);
    if (!result.available) {
      errorMessage.value = result.message || '用户名已存在';
      return;
    }
    username.value = name;
    completed.value.username = name;
    step.value = 'display';
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '校验用户名失败';
  } finally {
    loading.value = false;
  }
}

function submitDisplay() {
  if (!displayName.value.trim()) {
    errorMessage.value = '请输入显示名称';
    return;
  }
  completed.value.display = displayName.value.trim();
  errorMessage.value = '';
  step.value = 'password';
}

function submitPassword() {
  if (!password.value || password.value.length < 6) {
    errorMessage.value = '密码至少 6 位';
    return;
  }
  completed.value.password = '********';
  errorMessage.value = '';
  step.value = role.value === 'student' ? 'teacher' : 'photo';
}

function submitTeacher() {
  if (!teacherId.value) {
    errorMessage.value = '请选择负责老师';
    return;
  }
  completed.value.teacher = selectedTeacherName.value;
  errorMessage.value = '';
  step.value = 'class';
}

function submitClass() {
  if (!classId.value) {
    errorMessage.value = '请选择所属班级';
    return;
  }
  completed.value.class = selectedClassName.value;
  errorMessage.value = '';
  step.value = 'photo';
}

function openFilePicker() {
  fileInputRef.value?.click();
}

function onPhotoChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  photoFile.value = file;
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  previewUrl.value = URL.createObjectURL(file);
  errorMessage.value = '';
}

function submitPhoto() {
  completed.value.photo = photoFile.value ? photoFile.value.name : '已跳过';
  errorMessage.value = '';
  step.value = 'bio';
}

function submitBio() {
  const raw = description.value.trim();
  if (raw.toLowerCase() === 'skip') description.value = '';
  completed.value.bio = description.value.trim() || '已跳过';
  errorMessage.value = '';
  step.value = 'confirm';
}

async function executeRegister() {
  loading.value = true;
  errorMessage.value = '';
  try {
    const form = new FormData();
    form.append('username', username.value.trim());
    form.append('password', password.value);
    form.append('display_name', displayName.value.trim());
    form.append('role', role.value);
    form.append('teacher_id', teacherId.value);
    form.append('class_id', classId.value);
    form.append('description', description.value);
    if (photoFile.value) form.append('photo', photoFile.value);

    const result = await register(form);
    auth.setAuth(result.access_token, toAuthUser(result.user));
    step.value = 'granted';
    await nextTick();
    window.setTimeout(() => {
      void router.push(
        result.user.role === 'student' ? '/student' : result.user.role === 'teacher' ? '/teacher' : '/admin',
      );
    }, 600);
  } catch (error) {
    const raw = error instanceof Error ? error.message : '注册失败';
    // FastAPI 可能返回 {"detail":"..."} 字符串
    let message = raw;
    try {
      const parsed = JSON.parse(raw) as { detail?: string };
      if (parsed?.detail) message = parsed.detail;
    } catch {
      /* keep raw */
    }
    errorMessage.value = message;
    if (message.includes('用户名已存在')) {
      delete completed.value.username;
      step.value = 'username';
    }
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <TerminalAuthShell title="REGISTER_NODE" subtitle="账户开通">
    <div class="mx-auto w-full max-w-md space-y-5">
      <div>
        <p class="text-[11px] tracking-[0.25em] text-[var(--term-muted)]">账户开通</p>
        <h1 class="mt-3 text-xl tracking-wide text-[var(--term-fg)] sm:text-2xl">创建星轨账户</h1>
        <p class="mt-2 text-[12px] leading-6 text-[var(--term-muted)]">
          命令行式注册，回车推进下一步；可选字段可输入 skip 跳过。
        </p>
      </div>

      <!-- history -->
      <div class="space-y-1 text-[12px]">
        <p v-if="completed.role" class="text-[var(--term-muted)]">
          <span class="text-[var(--term-accent)]">&gt;</span> 角色:
          <span class="ml-2 text-[var(--term-fg)]">{{ completed.role }}</span>
          <span class="ml-3 text-[var(--term-accent)]">[OK]</span>
        </p>
        <p v-if="completed.username" class="text-[var(--term-muted)]">
          <span class="text-[var(--term-accent)]">&gt;</span> 用户名:
          <span class="ml-2 text-[var(--term-fg)]">{{ completed.username }}</span>
          <span class="ml-3 text-[var(--term-accent)]">[OK]</span>
        </p>
        <p v-if="completed.display" class="text-[var(--term-muted)]">
          <span class="text-[var(--term-accent)]">&gt;</span> 显示名称:
          <span class="ml-2 text-[var(--term-fg)]">{{ completed.display }}</span>
          <span class="ml-3 text-[var(--term-accent)]">[OK]</span>
        </p>
        <p v-if="completed.password" class="text-[var(--term-muted)]">
          <span class="text-[var(--term-accent)]">&gt;</span> 密码:
          <span class="ml-2 text-[var(--term-fg)]">********</span>
          <span class="ml-3 text-[var(--term-accent)]">[OK]</span>
        </p>
        <p v-if="completed.teacher" class="text-[var(--term-muted)]">
          <span class="text-[var(--term-accent)]">&gt;</span> 负责老师:
          <span class="ml-2 text-[var(--term-fg)]">{{ completed.teacher }}</span>
          <span class="ml-3 text-[var(--term-accent)]">[OK]</span>
        </p>
        <p v-if="completed.class" class="text-[var(--term-muted)]">
          <span class="text-[var(--term-accent)]">&gt;</span> 所属班级:
          <span class="ml-2 text-[var(--term-fg)]">{{ completed.class }}</span>
          <span class="ml-3 text-[var(--term-accent)]">[OK]</span>
        </p>
        <p v-if="completed.photo" class="text-[var(--term-muted)]">
          <span class="text-[var(--term-accent)]">&gt;</span> 自拍上传:
          <span class="ml-2 text-[var(--term-fg)]">{{ completed.photo }}</span>
          <span class="ml-3 text-[var(--term-accent)]">[OK]</span>
        </p>
        <p v-if="completed.bio" class="text-[var(--term-muted)]">
          <span class="text-[var(--term-accent)]">&gt;</span> 自我描述:
          <span class="ml-2 text-[var(--term-fg)]">{{ completed.bio }}</span>
          <span class="ml-3 text-[var(--term-accent)]">[OK]</span>
        </p>
      </div>

      <!-- role -->
      <div v-if="step === 'role'" class="space-y-2">
        <p class="text-[11px] tracking-wider text-[var(--term-muted)]">&gt; 选择角色:</p>
        <button
          type="button"
          class="flex w-full items-center justify-between border-b border-[var(--term-line)] py-3 text-left text-sm transition hover:border-[var(--term-accent)]"
          :class="role === 'student' ? 'text-[var(--term-accent)]' : 'text-[var(--term-fg)]'"
          @click="confirmRole('student')"
        >
          <span>1  学生</span>
          <span class="text-[10px] text-[var(--term-muted)]">STUDENT</span>
        </button>
        <button
          type="button"
          class="flex w-full items-center justify-between border-b border-[var(--term-line)] py-3 text-left text-sm transition hover:border-[var(--term-accent)]"
          :class="role === 'teacher' ? 'text-[var(--term-accent)]' : 'text-[var(--term-fg)]'"
          @click="confirmRole('teacher')"
        >
          <span>2  教师</span>
          <span class="text-[10px] text-[var(--term-muted)]">TEACHER</span>
        </button>
      </div>

      <TerminalField
        v-if="step === 'username'"
        v-model="username"
        label="> 用户名:"
        autocomplete="username"
        :active="true"
        :disabled="loading"
        :error="errorMessage"
        @submit="submitUsername"
      />

      <TerminalField
        v-if="step === 'display'"
        v-model="displayName"
        label="> 显示名称:"
        :active="true"
        :error="errorMessage"
        @submit="submitDisplay"
      />

      <TerminalField
        v-if="step === 'password'"
        v-model="password"
        label="> 密码:"
        type="password"
        autocomplete="new-password"
        :active="true"
        :error="errorMessage"
        @submit="submitPassword"
      />

      <!-- teacher select -->
      <div v-if="step === 'teacher'" class="space-y-2">
        <p class="text-[11px] tracking-wider text-[var(--term-muted)]">&gt; 负责老师:</p>
        <select
          v-model="teacherId"
          class="terminal-select w-full bg-transparent py-2 text-sm text-[var(--term-accent)] outline-none"
          @keydown.enter.prevent="submitTeacher"
        >
          <option v-for="t in teachers" :key="t.id" :value="t.id">{{ t.display_name }}</option>
        </select>
        <div class="h-px w-full bg-[var(--term-line)]">
          <div class="h-px w-full bg-[var(--term-accent)]" />
        </div>
        <button type="button" class="text-[11px] tracking-wider text-[var(--term-accent)]" @click="submitTeacher">
          [回车] 确认
        </button>
        <p v-if="errorMessage" class="text-[11px] text-[var(--term-err)]">错误：{{ errorMessage }}</p>
      </div>

      <!-- class select -->
      <div v-if="step === 'class'" class="space-y-2">
        <p class="text-[11px] tracking-wider text-[var(--term-muted)]">&gt; 所属班级:</p>
        <select
          v-model="classId"
          class="terminal-select w-full bg-transparent py-2 text-sm text-[var(--term-accent)] outline-none"
          @keydown.enter.prevent="submitClass"
        >
          <option v-for="c in filteredClasses" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
        <div class="h-px w-full bg-[var(--term-line)]">
          <div class="h-px w-full bg-[var(--term-accent)]" />
        </div>
        <button type="button" class="text-[11px] tracking-wider text-[var(--term-accent)]" @click="submitClass">
          [回车] 确认
        </button>
        <p v-if="errorMessage" class="text-[11px] text-[var(--term-err)]">错误：{{ errorMessage }}</p>
      </div>

      <!-- photo -->
      <div v-if="step === 'photo'" class="space-y-3">
        <p class="text-[11px] tracking-wider text-[var(--term-muted)]">&gt; 上传自拍:</p>
        <input ref="fileInputRef" type="file" accept="image/*" class="sr-only" @change="onPhotoChange" />
        <button
          type="button"
          class="flex w-full items-center gap-3 border-b border-[var(--term-line)] py-3 text-left text-sm text-[var(--term-fg)] transition hover:border-[var(--term-accent)] hover:text-[var(--term-accent)]"
          @click="openFilePicker"
        >
          <span class="text-[var(--term-accent)]">[选择文件]</span>
          <span class="truncate">{{ photoFile ? photoFile.name : '未选择文件' }}</span>
        </button>
        <div v-if="previewUrl" class="flex items-center gap-3">
          <img :src="previewUrl" alt="预览" class="h-12 w-12 object-cover" style="border: 0.5px solid var(--term-line)" />
          <span class="text-[10px] text-[var(--term-muted)]">预览已就绪</span>
        </div>
        <p class="text-[10px] text-[var(--term-muted)]">支持 JPG / PNG · 可选 · 回车继续</p>
        <button type="button" class="text-[11px] tracking-wider text-[var(--term-accent)]" @click="submitPhoto">
          [回车] 继续
        </button>
      </div>

      <TerminalField
        v-if="step === 'bio'"
        v-model="description"
        label="> 自我描述（可选，输入 skip 跳过）:"
        placeholder="skip"
        :active="true"
        @submit="submitBio"
      />

      <!-- confirm -->
      <div v-if="step === 'confirm'" class="space-y-3">
        <p class="text-[11px] tracking-wider text-[var(--term-muted)]">&gt; 确认注册</p>
        <button
          type="button"
          class="border-b border-[var(--term-accent)] py-3 text-left text-sm tracking-wider text-[var(--term-accent)] disabled:opacity-50"
          :disabled="loading"
          @click="executeRegister"
        >
          {{ loading ? '正在提交…' : '[回车] 完成注册并进入' }}
        </button>
        <p v-if="errorMessage" class="text-[11px] text-[var(--term-err)]">错误：{{ errorMessage }}</p>
      </div>

      <p v-if="step === 'granted'" class="text-sm tracking-wider text-[var(--term-accent)]">
        &gt; 账户已创建 · 正在跳转…
      </p>

      <p class="pt-2 text-[10px] tracking-[0.2em] text-[var(--term-muted)]">{{ footerHint }}</p>

      <button
        type="button"
        class="text-left text-[11px] tracking-wider text-[var(--term-muted)] underline-offset-4 hover:text-[var(--term-accent)] hover:underline"
        @click="router.push('/')"
      >
        &gt; 已有账号？返回登录
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

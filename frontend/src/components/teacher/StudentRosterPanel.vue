<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRouter } from 'vue-router';
import { fetchGradebook, importRosterCsv, importStudents, type GradebookRow } from '../../api/teacher';
import { parseApiError } from '../../api/errors';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';
import TeacherStatCard from './TeacherStatCard.vue';
import { useTeacherClassStore } from '../../stores/teacherClass';

const classStore = useTeacherClassStore();
const { classId, inviteCode, currentClassName } = storeToRefs(classStore);
const router = useRouter();

const rows = ref<GradebookRow[]>([]);
const importText = ref('student010,王小明\nstudent011,李小红');
const msg = ref('');
const loading = ref(false);
const importing = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

async function load() {
  if (!classId.value) {
    rows.value = [];
    return;
  }
  loading.value = true;
  try {
    rows.value = await fetchGradebook(classId.value);
  } catch {
    rows.value = [];
  } finally {
    loading.value = false;
  }
}

async function handleImport() {
  if (!classId.value) {
    msg.value = '请先选择班级';
    return;
  }
  const students = importText.value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [username, display_name] = line.split(',').map((s) => s.trim());
      return { username, display_name: display_name || username, password: '123456' };
    })
    .filter((s) => s.username);
  if (!students.length) {
    msg.value = '请按「用户名,姓名」格式填写';
    return;
  }
  importing.value = true;
  msg.value = '';
  try {
    const res = await importStudents(classId.value, students);
    msg.value = `导入完成：新增 ${res.created}，跳过 ${res.skipped}`;
    await load();
  } catch (err) {
    msg.value = err instanceof Error ? err.message : '导入失败';
  } finally {
    importing.value = false;
  }
}

async function handleCsvFile(ev: Event) {
  const input = ev.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  if (!classId.value) {
    msg.value = '请先选择班级';
    input.value = '';
    return;
  }
  importing.value = true;
  msg.value = '';
  try {
    const res = await importRosterCsv(classId.value, file);
    msg.value = `CSV「${res.filename || file.name}」导入完成：解析 ${res.parsed} 行，新增 ${res.created}，跳过 ${res.skipped}`;
    await load();
  } catch (err) {
    msg.value = parseApiError(err, 'CSV 导入失败');
  } finally {
    importing.value = false;
    input.value = '';
  }
}

function copyInvite() {
  if (!inviteCode.value) return;
  void navigator.clipboard.writeText(inviteCode.value);
  msg.value = `邀请码 ${inviteCode.value} 已复制`;
}

function openStudent(id: string) {
  void router.push({ path: `/teacher/students/${id}`, query: { class_id: classId.value } });
}

watch(classId, () => void load());
onMounted(load);
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="学生名册" :subtitle="currentClassName ? `当前班级：${currentClassName}` : '管理班级学生与邀请码'">
      <template #actions>
        <button v-if="inviteCode" type="button" class="t-btn t-btn--soft t-btn--sm font-mono-tech" @click="copyInvite">
          邀请码 {{ inviteCode }} · 复制
        </button>
      </template>
    </TeacherPageHeader>

    <div class="grid grid-cols-2 gap-4 lg:grid-cols-3">
      <TeacherStatCard label="班级人数" :value="rows.length" />
      <TeacherStatCard label="邀请码" :value="inviteCode || '—'" accent="sky" />
      <TeacherStatCard
        label="平均掌握率"
        :value="rows.length ? `${Math.round(rows.reduce((s, r) => s + r.mastery_rate, 0) / rows.length)}%` : '—'"
        accent="emerald"
      />
    </div>

    <section class="t-card glass-edge p-5">
      <div class="flex items-baseline justify-between gap-2">
        <h3 class="text-[15px] font-semibold text-t-1">批量导入学生</h3>
        <span class="t-kicker">Import</span>
      </div>
      <p class="mt-1 text-xs text-t-3">每行格式：用户名,显示名（默认密码 123456）；也可上传 CSV（表头 username,display_name 或 学号,姓名）</p>
      <textarea v-model="importText" rows="4" class="t-input mt-3 font-mono-tech" />
      <div class="mt-3 flex flex-wrap items-center gap-3">
        <button type="button" class="t-btn t-btn--primary t-btn--md" :disabled="importing" @click="handleImport">
          {{ importing ? '导入中…' : '导入文本' }}
        </button>
        <button type="button" class="t-btn t-btn--ghost t-btn--md" :disabled="importing" @click="fileInput?.click()">
          上传 CSV 花名册
        </button>
        <input ref="fileInput" type="file" accept=".csv,text/csv" class="hidden" @change="handleCsvFile" />
      </div>
      <p v-if="msg" class="mt-2 text-xs text-t-accent">{{ msg }}</p>
    </section>

    <section>
      <TeacherLoading v-if="loading" variant="skeleton" :rows="6" />
      <div v-else class="t-table-wrap">
        <table class="t-table">
          <thead>
            <tr>
              <th>姓名</th>
              <th>用户名</th>
              <th>掌握率</th>
              <th>点亮</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.user_id" class="is-clickable" @click="openStudent(r.user_id)">
              <td class="font-medium text-t-1">{{ r.display_name }}</td>
              <td class="text-t-3">{{ r.username }}</td>
              <td class="font-mono-tech">{{ r.mastery_rate }}%</td>
              <td class="font-mono-tech">{{ r.lit_count }}/{{ r.total_planets }}</td>
            </tr>
          </tbody>
        </table>
        <TeacherEmptyState v-if="!rows.length" class="m-4" title="暂无学生" description="可通过上方导入或让学生使用邀请码注册" />
      </div>
    </section>
  </div>
</template>

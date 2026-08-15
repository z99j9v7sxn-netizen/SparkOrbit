<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { fetchGradebook, type GradebookRow } from '../../api/teacher';
import {
  createGroup,
  deleteGroup,
  dispatchToGroup,
  fetchGroups,
  updateGroup,
  type StudentGroupItem,
} from '../../api/teacherSuite';
import { parseApiError } from '../../api/errors';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';
import { useTeacherClassStore } from '../../stores/teacherClass';

const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);

const groups = ref<StudentGroupItem[]>([]);
const roster = ref<GradebookRow[]>([]);
const loading = ref(false);
const msg = ref('');

const newName = ref('');
const newMemberIds = ref<string[]>([]);
const creating = ref(false);

const editingId = ref('');
const editMemberIds = ref<string[]>([]);

const dispatchGroupId = ref('');
const dispatchMessage = ref('老师给小组安排了协作任务，请互相帮助共同完成！');
const dispatching = ref(false);

async function load() {
  if (!classId.value) {
    groups.value = [];
    roster.value = [];
    return;
  }
  loading.value = true;
  msg.value = '';
  try {
    const [gs, rows] = await Promise.all([fetchGroups(classId.value), fetchGradebook(classId.value)]);
    groups.value = gs;
    roster.value = rows;
  } catch (e) {
    msg.value = parseApiError(e, '加载分组失败');
  } finally {
    loading.value = false;
  }
}

async function handleCreate() {
  if (!newName.value.trim() || !classId.value) return;
  creating.value = true;
  msg.value = '';
  try {
    await createGroup({
      class_id: classId.value,
      name: newName.value,
      member_ids: newMemberIds.value,
    });
    newName.value = '';
    newMemberIds.value = [];
    msg.value = '分组已创建';
    await load();
  } catch (e) {
    msg.value = parseApiError(e, '创建失败');
  } finally {
    creating.value = false;
  }
}

function startEdit(g: StudentGroupItem) {
  editingId.value = g.id;
  editMemberIds.value = [...g.member_ids];
}

async function saveEdit() {
  if (!editingId.value) return;
  msg.value = '';
  try {
    await updateGroup(editingId.value, { member_ids: editMemberIds.value });
    editingId.value = '';
    await load();
  } catch (e) {
    msg.value = parseApiError(e, '保存失败');
  }
}

async function handleDelete(id: string) {
  msg.value = '';
  try {
    await deleteGroup(id);
    groups.value = groups.value.filter((g) => g.id !== id);
  } catch (e) {
    msg.value = parseApiError(e, '删除失败');
  }
}

async function handleDispatch(g: StudentGroupItem) {
  if (!dispatchMessage.value.trim()) return;
  dispatchGroupId.value = g.id;
  dispatching.value = true;
  msg.value = '';
  try {
    const res = await dispatchToGroup(g.id, dispatchMessage.value);
    msg.value = res.message;
  } catch (e) {
    msg.value = parseApiError(e, '派发失败');
  } finally {
    dispatching.value = false;
    dispatchGroupId.value = '';
  }
}

watch(classId, () => void load());
onMounted(() => void load());
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="学生分组" subtitle="组建班内学习小组 · 按组派发协作任务" />

    <p v-if="msg" class="text-xs" :class="msg.includes('失败') ? 'text-t-danger' : 'text-t-ok'">{{ msg }}</p>

    <div class="grid gap-4 xl:grid-cols-[1fr_1.4fr]">
      <!-- 新建分组 -->
      <section class="t-card glass-edge p-5">
        <div class="flex items-baseline justify-between gap-2">
          <h3 class="text-[15px] font-semibold text-t-1">新建分组</h3>
          <span class="t-kicker">New Group</span>
        </div>
        <input v-model="newName" placeholder="小组名称，如：算法攻坚组" class="t-input mt-3" />
        <p class="mt-3 text-xs font-medium text-t-2">勾选成员（{{ newMemberIds.length }}）</p>
        <div class="mt-2 max-h-72 space-y-1 overflow-y-auto">
          <label
            v-for="s in roster"
            :key="s.user_id"
            class="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 transition hover:bg-t-s1/50"
          >
            <input v-model="newMemberIds" type="checkbox" :value="s.user_id" class="t-check rounded" />
            <span class="text-sm text-t-1">{{ s.display_name }}</span>
            <span class="ml-auto font-mono-tech text-[10px] text-t-3">掌握 {{ s.mastery_rate }}%</span>
          </label>
          <TeacherEmptyState v-if="!roster.length" title="班级暂无学生" />
        </div>
        <button
          type="button"
          class="t-btn t-btn--primary t-btn--md mt-3"
          :disabled="creating || !newName.trim()"
          @click="handleCreate"
        >
          {{ creating ? '创建中…' : '创建分组' }}
        </button>
      </section>

      <!-- 分组列表 -->
      <section class="space-y-3">
        <div class="t-card glass-edge p-4">
          <p class="text-xs font-medium text-t-2">按组派发的任务内容</p>
          <textarea v-model="dispatchMessage" rows="2" class="t-input mt-2" placeholder="任务说明" />
        </div>

        <TeacherLoading v-if="loading" :rows="3" />
        <template v-else>
          <div v-for="g in groups" :key="g.id" class="t-card glass-edge p-5">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <h4 class="text-sm font-semibold text-t-1">{{ g.name }}</h4>
                <span class="t-badge t-badge--neutral">{{ g.members.length }} 人</span>
              </div>
              <div class="flex gap-2">
                <button
                  type="button"
                  class="t-btn t-btn--primary t-btn--sm"
                  :disabled="dispatching && dispatchGroupId === g.id"
                  @click="handleDispatch(g)"
                >
                  {{ dispatching && dispatchGroupId === g.id ? '派发中…' : '派发任务' }}
                </button>
                <button type="button" class="t-btn t-btn--ghost t-btn--sm" @click="editingId === g.id ? (editingId = '') : startEdit(g)">
                  {{ editingId === g.id ? '取消' : '编辑成员' }}
                </button>
                <button type="button" class="t-btn t-btn--sm border-t-danger/40 bg-t-danger/10 text-t-danger hover:bg-t-danger/18" @click="handleDelete(g.id)">
                  解散
                </button>
              </div>
            </div>

            <div v-if="editingId === g.id" class="mt-3 rounded-xl border border-t-line/10 bg-t-s1/30 p-3">
              <div class="max-h-56 space-y-1 overflow-y-auto">
                <label
                  v-for="s in roster"
                  :key="s.user_id"
                  class="flex cursor-pointer items-center gap-2 rounded px-2 py-1 transition hover:bg-t-s1/60"
                >
                  <input v-model="editMemberIds" type="checkbox" :value="s.user_id" class="t-check rounded" />
                  <span class="text-sm text-t-1">{{ s.display_name }}</span>
                </label>
              </div>
              <button type="button" class="t-btn t-btn--soft t-btn--sm mt-2" @click="saveEdit">保存成员（{{ editMemberIds.length }}）</button>
            </div>

            <div v-else class="mt-2 flex flex-wrap gap-1.5">
              <span v-for="m in g.members" :key="m.id" class="rounded-full bg-t-line/10 px-2.5 py-1 text-[11px] text-t-2">
                {{ m.name }}
              </span>
              <span v-if="!g.members.length" class="text-[11px] text-t-3">暂无成员</span>
            </div>
          </div>
          <TeacherEmptyState v-if="!groups.length" title="暂无分组" description="创建学习小组后可按组派发任务" />
        </template>
      </section>
    </div>
  </div>
</template>

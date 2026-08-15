<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { fetchGradebook, type GradebookRow } from '../../api/teacher';
import { createPraise, fetchPraiseOverview, type PraiseOverview } from '../../api/teacherSuite';
import { parseApiError } from '../../api/errors';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';
import { useTeacherClassStore } from '../../stores/teacherClass';

const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);

const overview = ref<PraiseOverview | null>(null);
const roster = ref<GradebookRow[]>([]);
const loading = ref(false);
const msg = ref('');
const sending = ref(false);

const studentId = ref('');
const badge = ref('进步之星');
const points = ref(5);
const message = ref('');

const badges = ['进步之星', '专注达人', '互助之星', '思考者', '全勤标兵', '创意先锋'];

async function load() {
  if (!classId.value) {
    overview.value = null;
    roster.value = [];
    return;
  }
  loading.value = true;
  msg.value = '';
  try {
    const [ov, rows] = await Promise.all([fetchPraiseOverview(classId.value), fetchGradebook(classId.value)]);
    overview.value = ov;
    roster.value = rows;
  } catch (e) {
    msg.value = parseApiError(e, '加载激励数据失败');
  } finally {
    loading.value = false;
  }
}

async function handlePraise() {
  if (!studentId.value || !badge.value) return;
  sending.value = true;
  msg.value = '';
  try {
    await createPraise({
      student_id: studentId.value,
      class_id: classId.value || '',
      badge: badge.value,
      points: points.value,
      message: message.value,
    });
    const name = roster.value.find((s) => s.user_id === studentId.value)?.display_name || '';
    msg.value = `已表扬 ${name}，学生将在通知中心收到`;
    message.value = '';
    await load();
  } catch (e) {
    msg.value = parseApiError(e, '发放失败');
  } finally {
    sending.value = false;
  }
}

function fmt(ts: string) {
  return ts?.slice(0, 16)?.replace('T', ' ') || '';
}

watch(classId, () => void load());
onMounted(() => void load());
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="星光激励" subtitle="发放表扬徽章与星光积分 · 推送到学生端通知中心" />

    <p v-if="msg" class="text-xs" :class="msg.includes('失败') ? 'text-t-danger' : 'text-t-ok'">{{ msg }}</p>

    <div class="grid gap-4 xl:grid-cols-[1fr_1.4fr]">
      <!-- 发放 -->
      <section class="t-card glass-edge p-5">
        <div class="flex items-baseline justify-between gap-2">
          <h3 class="text-[15px] font-semibold text-t-1">发放表扬</h3>
          <span class="t-kicker">Praise</span>
        </div>
        <select v-model="studentId" class="t-input mt-3 cursor-pointer">
          <option value="">选择学生</option>
          <option v-for="s in roster" :key="s.user_id" :value="s.user_id">{{ s.display_name }}</option>
        </select>
        <p class="mt-3 text-xs font-medium text-t-2">选择徽章</p>
        <div class="mt-2 flex flex-wrap gap-2">
          <button
            v-for="b in badges"
            :key="b"
            type="button"
            class="rounded-full border px-3 py-1.5 text-xs transition"
            :class="badge === b ? 'border-t-accent/50 bg-t-accent/12 text-t-accent' : 'border-t-line/15 bg-t-s1/30 text-t-2 hover:border-t-accent/30'"
            @click="badge = b"
          >
            {{ b }}
          </button>
        </div>
        <label class="mt-3 flex items-center gap-2 text-xs text-t-3">
          星光积分
          <input v-model.number="points" type="number" min="0" max="100" class="t-input w-24 py-1" />
        </label>
        <textarea v-model="message" rows="2" class="t-input mt-3" placeholder="表扬语（可选）" />
        <button
          type="button"
          class="t-btn t-btn--primary t-btn--md mt-3"
          :disabled="sending || !studentId"
          @click="handlePraise"
        >
          {{ sending ? '发放中…' : '发放表扬' }}
        </button>
      </section>

      <!-- 榜单与历史 -->
      <section class="space-y-4">
        <div class="t-card glass-edge p-5">
          <div class="flex items-baseline justify-between gap-2">
            <h3 class="text-[15px] font-semibold text-t-1">星光榜</h3>
            <span class="t-kicker">Leaderboard</span>
          </div>
          <TeacherLoading v-if="loading" class="mt-3" :rows="3" />
          <div v-else class="mt-3 space-y-1.5">
            <div
              v-for="(l, idx) in overview?.leaderboard || []"
              :key="l.student_id"
              class="flex items-center gap-3 rounded-xl border border-t-line/10 bg-t-s1/30 px-3 py-2"
            >
              <span class="font-mono-tech w-6 text-center text-sm font-bold" :class="idx < 3 ? 'text-t-warn' : 'text-t-3'">
                {{ idx + 1 }}
              </span>
              <p class="text-sm font-medium text-t-1">{{ l.student_name }}</p>
              <span v-if="l.top_badge" class="t-badge t-badge--info">{{ l.top_badge }}</span>
              <span class="ml-auto font-mono-tech text-sm text-t-warn">{{ l.total_points }} ✦</span>
              <span class="font-mono-tech text-[10px] text-t-3">{{ l.badge_count }} 枚</span>
            </div>
            <TeacherEmptyState v-if="!overview?.leaderboard?.length" title="暂无激励记录" />
          </div>
        </div>

        <div class="t-card glass-edge p-5">
          <div class="flex items-baseline justify-between gap-2">
            <h3 class="text-[15px] font-semibold text-t-1">发放历史</h3>
            <span class="t-kicker">History</span>
          </div>
          <div class="mt-3 max-h-72 space-y-1.5 overflow-y-auto">
            <div v-for="r in overview?.records || []" :key="r.id" class="rounded-xl border border-t-line/10 bg-t-s1/30 px-3 py-2">
              <div class="flex flex-wrap items-center gap-2">
                <p class="text-sm text-t-1">{{ r.student_name }}</p>
                <span class="t-badge t-badge--info">{{ r.badge }}</span>
                <span class="font-mono-tech text-[11px] text-t-warn">+{{ r.points }} ✦</span>
                <span class="ml-auto text-[10px] text-t-3">{{ fmt(r.created_at) }}</span>
              </div>
              <p v-if="r.message" class="mt-0.5 text-[11px] text-t-2">{{ r.message }}</p>
            </div>
            <TeacherEmptyState v-if="!overview?.records?.length" title="暂无发放记录" />
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

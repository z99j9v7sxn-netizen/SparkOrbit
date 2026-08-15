<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { fetchInsightOverview, type InsightOverview } from '../../api/teacher';
import { dispatchHotspotReview, fetchMistakeHotspots, type MistakeHotspots } from '../../api/teacherSuite';
import { useTeacherClassStore } from '../../stores/teacherClass';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';
import TeacherStatCard from './TeacherStatCard.vue';

const router = useRouter();
const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);

const loading = ref(false);
const error = ref('');
const data = ref<InsightOverview | null>(null);
const sortKey = ref<'evidence_7d' | 'mastery_rate' | 'quiz_accuracy' | 'focus_minutes'>('evidence_7d');
const mistakes = ref<MistakeHotspots | null>(null);
const dispatchMsg = ref('');
const dispatching = ref('');

const kindBars = computed(() => {
  const raw = data.value?.evidence_by_kind || {};
  const entries = Object.entries(raw)
    .map(([kind, count]) => ({ kind, count: Number(count) || 0 }))
    .filter((x) => x.count > 0)
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);
  const max = Math.max(1, ...entries.map((e) => e.count));
  return entries.map((e) => ({ ...e, pct: Math.round((e.count / max) * 100) }));
});

const sortedStudents = computed(() => {
  const list = [...(data.value?.students || [])];
  list.sort((a, b) => Number(b[sortKey.value]) - Number(a[sortKey.value]));
  return list;
});

async function load() {
  loading.value = true;
  error.value = '';
  try {
    const [overview, hotspots] = await Promise.all([
      fetchInsightOverview(classId.value || ''),
      fetchMistakeHotspots(classId.value || '').catch(() => null),
    ]);
    data.value = overview;
    mistakes.value = hotspots;
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载学情洞察失败';
    data.value = null;
  } finally {
    loading.value = false;
  }
}

async function handleDispatchHotspot(planetSlug: string, planetName: string) {
  if (!classId.value) {
    dispatchMsg.value = '请先选择班级';
    return;
  }
  dispatching.value = planetSlug;
  dispatchMsg.value = '';
  try {
    const res = await dispatchHotspotReview(classId.value, planetSlug);
    dispatchMsg.value = `「${planetName}」：${res.message}`;
  } catch (e) {
    dispatchMsg.value = e instanceof Error ? e.message : '派发失败';
  } finally {
    dispatching.value = '';
  }
}

function openStudent(id: string, tab: 'overview' | 'growth' | 'vault' = 'growth') {
  void router.push({
    path: `/teacher/students/${id}`,
    query: {
      ...(classId.value ? { class_id: classId.value } : {}),
      tab,
    },
  });
}

watch(classId, () => void load());
onMounted(() => void load());
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="学情洞察" subtitle="班级成长总览 · 点进学生查看知识库与成长评估">
      <template #actions>
        <button type="button" class="t-btn t-btn--ghost t-btn--sm" @click="load">刷新</button>
      </template>
    </TeacherPageHeader>

    <TeacherLoading v-if="loading" :rows="6" />
    <p v-else-if="error" class="rounded-xl border border-t-danger/30 bg-t-danger/10 px-4 py-3 text-sm text-t-danger">
      {{ error }}
    </p>

    <template v-else-if="data">
      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <TeacherStatCard label="班级人数" :value="data.total_students" accent="sky" />
        <TeacherStatCard label="平均掌握率" :value="`${data.avg_mastery_rate}%`" accent="emerald" />
        <TeacherStatCard label="平均正确率" :value="`${data.avg_quiz_accuracy}%`" accent="sky" />
        <TeacherStatCard label="近7日活跃" :value="data.active_students_7d" accent="amber" />
        <TeacherStatCard label="风险告警" :value="data.risk_count" accent="rose" />
      </div>

      <section class="t-card glass-edge p-5">
        <div class="flex items-baseline justify-between gap-2">
          <h3 class="text-[15px] font-semibold text-t-1">学闸证据分布</h3>
          <span class="t-kicker">Evidence</span>
        </div>
        <p class="mt-1 text-[11px] text-t-3">合计 {{ data.total_evidence }} 条证据 · 含星库阅读、划词提问等</p>
        <div v-if="kindBars.length" class="mt-4 space-y-2">
          <div v-for="k in kindBars" :key="k.kind" class="flex items-center gap-3">
            <span class="w-28 shrink-0 truncate text-[11px] text-t-3">{{ k.kind }}</span>
            <div class="h-2 flex-1 overflow-hidden rounded-full bg-t-line/10">
              <div
                class="h-full rounded-full bg-gradient-to-r from-t-accent/80 to-t-accent2/70 transition-[width] duration-500"
                :style="{ width: `${k.pct}%` }"
              />
            </div>
            <span class="w-10 text-right font-mono-tech text-[11px] text-t-2">{{ k.count }}</span>
          </div>
        </div>
        <TeacherEmptyState v-else class="mt-3" title="暂无学闸证据" description="学生在星库划词或演武后会出现在这里" />
      </section>

      <!-- 错题热点 -->
      <section class="t-card glass-edge p-5">
        <div class="flex items-baseline justify-between gap-2">
          <h3 class="text-[15px] font-semibold text-t-1">班级错题热点</h3>
          <span class="t-kicker">Mistake Hotspots</span>
        </div>
        <p class="mt-1 text-[11px] text-t-3">按演武答错聚合的共性薄弱知识点 · 可一键向答错学生派发复习任务</p>
        <p v-if="dispatchMsg" class="mt-2 text-xs" :class="dispatchMsg.includes('失败') ? 'text-t-danger' : 'text-t-ok'">
          {{ dispatchMsg }}
        </p>

        <div v-if="mistakes?.hotspots?.length" class="mt-3 space-y-2">
          <div
            v-for="h in mistakes.hotspots"
            :key="h.planet_slug"
            class="flex flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3"
            :class="h.wrong_rate >= 50 ? 'border-t-danger/30 bg-t-danger/6' : 'border-t-warn/25 bg-t-warn/6'"
          >
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <p class="text-sm font-medium text-t-1">{{ h.planet_name }}</p>
                <span class="text-[10px] text-t-3">{{ h.galaxy_name }}</span>
              </div>
              <p class="mt-0.5 font-mono-tech text-[11px]" :class="h.wrong_rate >= 50 ? 'text-t-danger' : 'text-t-warn'">
                错 {{ h.wrong_count }} / {{ h.attempts }} 次（{{ h.wrong_rate }}%）· 涉及 {{ h.affected_students }} 名学生
              </p>
              <div v-if="h.top_tags.length" class="mt-1 flex flex-wrap gap-1">
                <span v-for="t in h.top_tags" :key="t" class="rounded bg-t-line/10 px-1.5 py-0.5 text-[10px] text-t-3">{{ t }}</span>
              </div>
            </div>
            <button
              type="button"
              class="t-btn t-btn--soft t-btn--sm shrink-0"
              :disabled="dispatching === h.planet_slug"
              @click="handleDispatchHotspot(h.planet_slug, h.planet_name)"
            >
              {{ dispatching === h.planet_slug ? '派发中…' : '派发针对复习' }}
            </button>
          </div>
        </div>
        <TeacherEmptyState v-else class="mt-3" title="暂无错题热点" description="学生演武答错后会在这里聚合" />

        <div v-if="mistakes?.recent_mistakes?.length" class="mt-4">
          <p class="text-xs font-medium text-t-2">最近错题（错题本）</p>
          <div class="mt-2 max-h-48 space-y-1.5 overflow-y-auto">
            <div v-for="m in mistakes.recent_mistakes" :key="m.id" class="rounded-lg border border-t-line/10 bg-t-s1/30 px-3 py-2">
              <p class="text-[11px] text-t-2">{{ m.question || '（无题干）' }}</p>
              <p class="mt-0.5 text-[10px] text-t-3">{{ m.student_name }}<template v-if="m.subject"> · {{ m.subject }}</template></p>
            </div>
          </div>
        </div>
      </section>

      <section class="t-card glass-edge p-5">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <h3 class="text-[15px] font-semibold text-t-1">学生成长列表</h3>
          <select v-model="sortKey" class="t-input w-auto cursor-pointer py-1.5 text-sm">
            <option value="evidence_7d">按近7日证据</option>
            <option value="mastery_rate">按掌握率</option>
            <option value="quiz_accuracy">按正确率</option>
            <option value="focus_minutes">按专注时长</option>
          </select>
        </div>

        <div class="t-table-wrap mt-3">
          <table class="t-table min-w-[720px]">
            <thead>
              <tr>
                <th>学生</th>
                <th>掌握率</th>
                <th>正确率</th>
                <th>近7日证据</th>
                <th>专注分钟</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in sortedStudents" :key="s.user_id">
                <td>
                  <button type="button" class="text-left font-medium text-t-1 transition hover:text-t-accent" @click="openStudent(s.user_id)">
                    {{ s.display_name || s.username }}
                  </button>
                  <p class="text-[10px] text-t-3">@{{ s.username }}</p>
                </td>
                <td class="font-mono-tech">{{ s.mastery_rate }}%</td>
                <td class="font-mono-tech">{{ s.quiz_accuracy }}%</td>
                <td class="font-mono-tech">
                  {{ s.evidence_7d }}
                  <span class="text-[10px] text-t-3">/ 总 {{ s.evidence_total }}</span>
                </td>
                <td class="font-mono-tech">{{ s.focus_minutes }}</td>
                <td>
                  <div class="flex flex-wrap gap-2">
                    <button type="button" class="t-btn t-btn--soft t-btn--sm" @click="openStudent(s.user_id, 'growth')">成长</button>
                    <button type="button" class="t-btn t-btn--ghost t-btn--sm" @click="openStudent(s.user_id, 'vault')">知识库</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <TeacherEmptyState v-if="!sortedStudents.length" class="mt-4" title="班级暂无学生" />
      </section>
    </template>
  </div>
</template>

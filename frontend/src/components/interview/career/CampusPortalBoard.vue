<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import { LzButton, LzEmptyState, LzSkeleton } from '../../learning/ui';
import { parseApiError } from '../../../api/errors';
import {
  createInterviewApplication,
  fetchCareerPortals,
  type CareerPortal,
  type CareerWindow,
} from '../../../api/interview';

const emit = defineEmits<{
  (e: 'tracked'): void;
  (e: 'goto-tracker'): void;
}>();

const GROUP_ORDER = ['互联网', '硬件制造', '新能源车', '升学考公'];

const loading = ref(true);
const error = ref('');
const portals = ref<CareerPortal[]>([]);
const windows = ref<CareerWindow[]>([]);
const group = ref('');
const savingId = ref('');
const tracked = ref<Record<string, boolean>>({});
const hint = ref('');
const logoFailed = ref<Record<string, boolean>>({});

const groupCounts = computed(() => {
  const counts: Record<string, number> = { '': portals.value.length };
  for (const g of GROUP_ORDER) counts[g] = 0;
  for (const p of portals.value) counts[p.group] = (counts[p.group] || 0) + 1;
  return counts;
});

const grouped = computed(() => {
  const map = new Map<string, CareerPortal[]>();
  for (const p of portals.value) {
    if (group.value && p.group !== group.value) continue;
    const list = map.get(p.group) || [];
    list.push(p);
    map.set(p.group, list);
  }
  return GROUP_ORDER.filter((g) => map.has(g)).map((g) => ({ group: g, items: map.get(g) || [] }));
});

onMounted(async () => {
  try {
    const data = await fetchCareerPortals();
    portals.value = data.portals;
    windows.value = data.windows;
  } catch (err) {
    error.value = parseApiError(err, '校招门户加载失败');
  } finally {
    loading.value = false;
  }
});

function mark(g: string) {
  group.value = g;
}

function logoSrc(item: CareerPortal) {
  const host = item.logo_host?.trim();
  if (!host) return '';
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=64`;
}

function onLogoError(id: string) {
  logoFailed.value = { ...logoFailed.value, [id]: true };
}

async function jumpWindow(win: CareerWindow) {
  const items = portals.value.filter((p) => win.portal_ids.includes(p.id));
  const groups = new Set(items.map((p) => p.group));
  group.value = groups.size === 1 ? [...groups][0] : '';
  await nextTick();
  document.getElementById(`portal-${win.portal_ids[0]}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

async function track(item: CareerPortal) {
  savingId.value = item.id;
  hint.value = '';
  try {
    await createInterviewApplication({
      company: item.name,
      portal_url: item.url,
      status: 'wishlist',
      role: '',
    });
    tracked.value = { ...tracked.value, [item.id]: true };
    hint.value = `已记入「${item.name}」，可继续浏览或去看板`;
    emit('tracked');
  } catch (err) {
    error.value = parseApiError(err, '记入看板失败');
  } finally {
    savingId.value = '';
  }
}
</script>

<template>
  <div class="portal-layout">
    <aside class="portal-side">
      <p class="side-title">校招官网</p>
      <p class="side-hint">只做跳转，不代投</p>
      <nav class="side-nav">
        <button type="button" class="nav-row" :class="!group ? 'is-on' : ''" @click="mark('')">
          <span>全部</span>
          <span class="nav-count">{{ groupCounts[''] || 0 }}</span>
        </button>
        <button
          v-for="g in GROUP_ORDER"
          :key="g"
          type="button"
          class="nav-row"
          :class="group === g ? 'is-on' : ''"
          @click="mark(g)"
        >
          <span>{{ g }}</span>
          <span class="nav-count">{{ groupCounts[g] || 0 }}</span>
        </button>
      </nav>
      <p class="side-title side-title--sub">校招日历</p>
      <ol class="cal-list">
        <li v-for="win in windows" :key="win.id">
          <button type="button" class="cal-row" @click="jumpWindow(win)">
            <span class="cal-when">{{ win.when }}</span>
            <span class="cal-name">{{ win.title }}</span>
          </button>
        </li>
      </ol>
    </aside>

    <div class="portal-main">
      <p v-if="hint" class="text-xs text-emerald-300">
        {{ hint }}
        <button type="button" class="ml-2 text-amber-200 underline" @click="emit('goto-tracker')">去看板</button>
      </p>
      <p v-if="error" class="text-xs text-rose-300">{{ error }}</p>
      <div v-if="loading"><LzSkeleton preset="card" /></div>

      <section v-for="block in grouped" :key="block.group" class="dir-block">
        <h4 class="dir-head">{{ block.group }}</h4>
        <ul class="dir-list">
          <li
            v-for="item in block.items"
            :id="`portal-${item.id}`"
            :key="item.id"
            class="dir-row"
          >
            <span class="brand">
              <img
                v-if="logoSrc(item) && !logoFailed[item.id]"
                class="brand-img"
                :src="logoSrc(item)"
                :alt="item.name"
                width="28"
                height="28"
                @error="onLogoError(item.id)"
              />
              <span
                v-else
                class="brand-fallback"
                :style="{ background: item.accent || '#f59e0b' }"
              >{{ item.name.slice(0, 1) }}</span>
            </span>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm text-slate-100">{{ item.name }}</p>
              <p class="mt-0.5 truncate text-[11px] text-slate-500">{{ item.note }}</p>
            </div>
            <div class="dir-actions">
              <a
                class="portal-btn portal-btn--primary"
                :href="item.url"
                target="_blank"
                rel="noopener noreferrer"
              >
                打开官网
              </a>
              <a
                v-if="item.intern_url && item.intern_url !== item.url"
                class="portal-btn"
                :href="item.intern_url"
                target="_blank"
                rel="noopener noreferrer"
              >
                实习入口
              </a>
              <LzButton
                size="sm"
                :loading="savingId === item.id"
                :disabled="tracked[item.id]"
                @click="track(item)"
              >
                {{ tracked[item.id] ? '已记入' : '记入看板' }}
              </LzButton>
            </div>
          </li>
        </ul>
      </section>
      <LzEmptyState v-if="!loading && !grouped.length" title="没有匹配的门户" />
    </div>
  </div>
</template>

<style scoped>
.portal-layout {
  display: grid;
  grid-template-columns: 200px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.portal-side {
  position: sticky;
  top: 0;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  padding-right: 12px;
}
.side-title {
  margin: 0;
  font-size: 13px;
  color: #f8fafc;
}
.side-title--sub {
  margin-top: 18px;
  font-size: 12px;
  color: #94a3b8;
}
.side-hint {
  margin: 4px 0 10px;
  font-size: 11px;
  color: #64748b;
}
.side-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.nav-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  border-radius: 8px;
  padding: 6px 8px;
  font-size: 12px;
  color: #94a3b8;
  text-align: left;
}
.nav-row:hover {
  background: rgba(255, 255, 255, 0.04);
  color: #e2e8f0;
}
.nav-row.is-on {
  background: rgba(245, 158, 11, 0.12);
  color: #fde68a;
}
.nav-count {
  font-variant-numeric: tabular-nums;
  font-size: 11px;
  color: #64748b;
}
.cal-list {
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}
.cal-row {
  display: flex;
  flex-direction: column;
  width: 100%;
  gap: 2px;
  border-radius: 8px;
  padding: 6px 8px;
  text-align: left;
}
.cal-row:hover {
  background: rgba(255, 255, 255, 0.04);
}
.cal-when {
  font-size: 10px;
  color: #fbbf24;
}
.cal-name {
  font-size: 12px;
  color: #cbd5e1;
}
.portal-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.dir-head {
  margin: 0 0 6px;
  font-size: 11px;
  color: #64748b;
}
.dir-list {
  margin: 0;
  padding: 0;
  list-style: none;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}
.dir-row {
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding: 10px 4px;
}
.brand {
  display: flex;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 8px;
  background: #fff;
}
.brand-img {
  width: 22px;
  height: 22px;
  object-fit: contain;
}
.brand-fallback {
  display: flex;
  width: 100%;
  height: 100%;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
}
.dir-actions {
  display: flex;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}
.portal-btn {
  display: inline-flex;
  align-items: center;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  padding: 5px 10px;
  font-size: 11px;
  color: #cbd5e1;
}
.portal-btn--primary {
  background: #f59e0b;
  color: #1c1917;
  font-weight: 600;
  border-color: #f59e0b;
}
@media (max-width: 720px) {
  .portal-layout {
    grid-template-columns: 1fr;
  }
  .portal-side {
    position: static;
    border-right: 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-right: 0;
    padding-bottom: 12px;
  }
}
</style>

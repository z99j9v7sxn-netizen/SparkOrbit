<script setup lang="ts">
import { computed, nextTick, ref } from 'vue';
import CompanionChat from '../CompanionChat.vue';
import ZoneHeader from '../common/ZoneHeader.vue';
import {
  createMoodDiary,
  createTreeHoleComment,
  createTreeHolePost,
  deleteTreeHolePost,
  fetchMoodDiaries,
  fetchTreeHoleComments,
  fetchTreeHolePosts,
  reactTreeHolePost,
  uploadTreeHoleImage,
  type TreeHoleCommentItem,
  type TreeHolePostItem,
  type MoodDiaryItem,
} from '../../api/zone';

const tab = ref<'ai' | 'diary' | 'feed'>('ai');
const moods = [
  { key: 'happy', label: '开心', icon: '/icons/sparkle.svg' },
  { key: 'calm', label: '平静', icon: '/icons/moon.svg' },
  { key: 'tired', label: '疲惫', icon: '/icons/cloud.svg' },
  { key: 'sad', label: '低落', icon: '/icons/rain.svg' },
  { key: 'angry', label: '烦躁', icon: '/icons/bolt.svg' },
];
const reactionEmojis = ['❤️', '😢', '😂', '😡', '🥺', '✨'];
const selectedMood = ref('calm');
const diaryDraft = ref('');
const diaries = ref<MoodDiaryItem[]>([]);
const diaryImage = ref('');
const diaryInputRef = ref<HTMLInputElement | null>(null);
const bookOpen = ref(false);
const bookPage = ref(0);
const pageTurning = ref(false);
const posts = ref<TreeHolePostItem[]>([]);
const postDraft = ref('');
const postEmoji = ref('🥺');
const imagePreview = ref('');
const imageUploading = ref(false);
const imageInputRef = ref<HTMLInputElement | null>(null);
const uploadError = ref('');
const expandedPostId = ref<string | null>(null);
const commentsByPost = ref<Record<string, TreeHoleCommentItem[]>>({});
const commentDraft = ref('');
const commentEmoji = ref('');
const visibleDiary = computed(() => diaries.value[bookPage.value] ?? null);

/** 三个场景入口：切换时整区氛围随之变化 */
const scenes = [
  { key: 'ai' as const, icon: '/icons/campfire.svg', label: '心灵聊天', en: 'Campfire Talk', desc: '和星语伴聊聊此刻的心事' },
  { key: 'diary' as const, icon: '/icons/diary.svg', label: '星空日记', en: 'Star Journal', desc: '只写给自己的一页' },
  { key: 'feed' as const, icon: '/icons/jar.svg', label: '匿名星轨', en: 'Drift Wall', desc: '把心情贴上漂流星轨墙' },
];

/** 情绪 → 环境双色（径向渐变），选择心情时全区氛围缓慢过渡 */
const moodPalettes: Record<string, [string, string]> = {
  happy: ['rgba(251, 191, 36, 0.16)', 'rgba(236, 72, 153, 0.09)'],
  calm: ['rgba(167, 139, 250, 0.16)', 'rgba(56, 189, 248, 0.09)'],
  tired: ['rgba(148, 163, 184, 0.13)', 'rgba(56, 189, 248, 0.06)'],
  sad: ['rgba(96, 165, 250, 0.16)', 'rgba(99, 102, 241, 0.09)'],
  angry: ['rgba(251, 113, 133, 0.15)', 'rgba(245, 158, 11, 0.08)'],
};

const ambientKey = computed(() => (tab.value === 'diary' ? `diary-${selectedMood.value}` : tab.value));

const ambientStyle = computed(() => {
  const pair =
    tab.value === 'diary'
      ? moodPalettes[selectedMood.value] ?? moodPalettes.calm
      : tab.value === 'ai'
        ? moodPalettes.calm
        : (['rgba(129, 140, 248, 0.15)', 'rgba(236, 72, 153, 0.08)'] as [string, string]);
  return {
    background: `radial-gradient(ellipse 55% 42% at 22% 0%, ${pair[0]}, transparent 60%), radial-gradient(ellipse 45% 38% at 85% 12%, ${pair[1]}, transparent 58%)`,
  };
});

function stickerRotate(id: string) {
  const hash = id.split('').reduce((sum, ch) => sum + ch.charCodeAt(0), 0);
  return ((hash % 7) - 3) * 1.2;
}

/** 漂浮动画的错峰延迟，让贴纸墙有星群缓动感 */
function stickerDelay(id: string) {
  const hash = id.split('').reduce((sum, ch) => sum + ch.charCodeAt(0), 0);
  return `${(hash % 9) * -0.7}s`;
}

async function loadDiaries() {
  diaries.value = await fetchMoodDiaries().catch(() => []);
}

async function loadPosts() {
  posts.value = await fetchTreeHolePosts().catch(() => []);
}

async function saveDiary() {
  if (!diaryDraft.value.trim()) return;
  await createMoodDiary(selectedMood.value, diaryDraft.value.trim(), diaryImage.value);
  diaryDraft.value = '';
  diaryImage.value = '';
  if (diaryInputRef.value) diaryInputRef.value.value = '';
  await loadDiaries();
  bookPage.value = 0;
  bookOpen.value = true;
}

async function onImagePick(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0];
  if (!file) return;
  uploadError.value = '';
  imageUploading.value = true;
  try {
    const res = await uploadTreeHoleImage(file);
    if (!res.url) throw new Error('服务器未返回图片地址');
    imagePreview.value = res.url;
  } catch (error) {
    uploadError.value = error instanceof Error
      ? `图片上传失败：${error.message}`
      : '图片上传失败，请确认后端服务已启动';
  } finally {
    imageUploading.value = false;
  }
}

async function onDiaryImagePick(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0];
  if (!file) return;
  imageUploading.value = true;
  uploadError.value = '';
  try {
    const res = await uploadTreeHoleImage(file);
    if (!res.url) throw new Error('服务器未返回图片地址');
    diaryImage.value = res.url;
  } catch (error) {
    uploadError.value = error instanceof Error ? `照片上传失败：${error.message}` : '照片上传失败';
  } finally {
    imageUploading.value = false;
  }
}

function clearPostImage() {
  imagePreview.value = '';
  if (imageInputRef.value) imageInputRef.value.value = '';
}

function clearDiaryImage() {
  diaryImage.value = '';
  if (diaryInputRef.value) diaryInputRef.value.value = '';
}

async function publishPost() {
  if (!postDraft.value.trim()) return;
  const content = `${postEmoji.value} ${postDraft.value.trim()}`;
  await createTreeHolePost(content, imagePreview.value);
  postDraft.value = '';
  imagePreview.value = '';
  clearPostImage();
  await loadPosts();
}

async function withdrawPost(postId: string) {
  await deleteTreeHolePost(postId);
  posts.value = posts.value.filter((post) => post.id !== postId);
}

async function turnPage(direction: -1 | 1) {
  const next = bookPage.value + direction;
  if (next < 0 || next >= diaries.value.length || pageTurning.value) return;
  pageTurning.value = true;
  await new Promise((resolve) => window.setTimeout(resolve, 220));
  bookPage.value = next;
  await nextTick();
  window.setTimeout(() => { pageTurning.value = false; }, 220);
}

async function toggleReaction(postId: string, emoji: string) {
  const res = await reactTreeHolePost(postId, emoji);
  posts.value = posts.value.map((post) =>
    post.id === postId
      ? { ...post, reaction_summary: res.reaction_summary, my_reactions: res.my_reactions }
      : post,
  );
}

async function openComments(postId: string) {
  expandedPostId.value = expandedPostId.value === postId ? null : postId;
  if (expandedPostId.value === postId && !commentsByPost.value[postId]) {
    commentsByPost.value[postId] = await fetchTreeHoleComments(postId).catch(() => []);
  }
}

async function sendComment(postId: string) {
  if (!commentDraft.value.trim() && !commentEmoji.value) return;
  const row = await createTreeHoleComment(postId, commentDraft.value.trim(), commentEmoji.value);
  commentsByPost.value[postId] = [...(commentsByPost.value[postId] ?? []), row];
  posts.value = posts.value.map((post) =>
    post.id === postId ? { ...post, comment_count: post.comment_count + 1 } : post,
  );
  commentDraft.value = '';
  commentEmoji.value = '';
}

function switchTab(next: 'ai' | 'diary' | 'feed') {
  tab.value = next;
  if (next === 'diary') void loadDiaries();
  if (next === 'feed') void loadPosts();
}
</script>

<template>
  <div class="lz-accent-violet absolute inset-0 overflow-auto px-4 pb-24 pt-20">
    <!-- 情绪驱动的环境氛围层：随场景 / 心情缓慢过渡 -->
    <Transition name="th-ambient">
      <div :key="ambientKey" class="pointer-events-none fixed inset-0" :style="ambientStyle" aria-hidden="true"></div>
    </Transition>

    <div class="relative mx-auto max-w-6xl">
      <ZoneHeader
        eyebrow="Tree Hole // Midnight Sanctuary"
        title="星语树洞 · 心灵栖息地"
        desc="智能倾听、心情日记与匿名星轨贴纸墙"
      />

      <!-- 场景切换卡 -->
      <div class="mb-5 grid grid-cols-3 gap-3">
        <button
          v-for="scene in scenes"
          :key="scene.key"
          type="button"
          class="th-scene lz-hud-card p-3 text-left sm:p-4"
          :class="{ 'is-active': tab === scene.key }"
          @click="switchTab(scene.key)"
        >
          <img class="th-scene-icon h-6 w-6 sm:h-7 sm:w-7" :src="scene.icon" alt="" aria-hidden="true" />
          <p class="mt-1.5 truncate text-sm font-semibold text-white sm:mt-2">{{ scene.label }}</p>
          <p class="lz-hud-label mt-0.5 hidden truncate sm:block">{{ scene.en }}</p>
          <p class="mt-1 hidden text-[11px] text-slate-500 md:block">{{ scene.desc }}</p>
        </button>
      </div>

      <Transition name="zone-swap" mode="out-in">
        <div :key="tab" class="glass-strong rounded-3xl p-6">
          <div v-if="tab === 'ai'" class="h-[32rem]">
            <CompanionChat />
          </div>

          <div v-else-if="tab === 'diary'" class="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(280px,.65fr)]">
            <div class="diary-stage flex min-h-[430px] items-center justify-center [perspective:1400px]">
              <button
                v-if="!bookOpen"
                class="diary-cover relative h-[380px] w-[290px] overflow-hidden rounded-r-2xl border border-amber-200/25 bg-[#08162b] text-left shadow-[18px_24px_70px_rgba(0,0,0,.55)] transition hover:-translate-y-1"
                @click="bookOpen = true"
              >
                <span class="absolute inset-y-0 left-0 w-7 border-r border-amber-200/20 bg-[#06101f]"></span>
                <span class="diary-gold absolute left-12 top-16 text-[10px] tracking-[0.45em]">PRIVATE JOURNAL</span>
                <strong class="absolute left-12 top-28 max-w-[190px] text-3xl font-light leading-tight text-slate-100">我的<br />星空日记</strong>
                <span class="diary-gold-line absolute bottom-24 left-12 right-12" aria-hidden="true"></span>
                <span class="absolute bottom-12 left-12 text-xs text-slate-500">{{ diaries.length }} 篇记录</span>
              </button>

              <div
                v-else
                class="diary-book relative grid h-[430px] w-full max-w-[760px] grid-cols-2 overflow-hidden rounded-2xl border border-sky-200/15 bg-[#e9edf0] text-slate-800 shadow-[0_30px_90px_rgba(0,0,0,.5)]"
                :class="{ 'diary-turning': pageTurning }"
              >
                <section class="relative border-r border-slate-300/70 p-8">
                  <button class="absolute left-5 top-4 text-xs text-slate-500 hover:text-slate-900" @click="bookOpen = false">合上日记</button>
                  <div v-if="visibleDiary" class="mt-8">
                    <p class="text-xs tracking-[0.22em] text-slate-500">{{ visibleDiary.created_at.slice(0, 10) }}</p>
                    <img class="mt-5 h-9 w-9" :src="moods.find((m) => m.key === visibleDiary?.mood)?.icon" alt="" aria-hidden="true" />
                    <h3 class="mt-3 text-xl font-medium">今日心绪</h3>
                    <p class="mt-5 whitespace-pre-wrap text-sm leading-7 text-slate-700">{{ visibleDiary.content }}</p>
                  </div>
                  <p v-else class="mt-36 text-center text-sm text-slate-500">还没有日记，从右页写下第一篇。</p>
                </section>
                <section class="relative flex flex-col p-8">
                  <img
                    v-if="visibleDiary?.image_url"
                    :src="visibleDiary.image_url"
                    class="mt-6 min-h-0 flex-1 rounded-lg object-cover shadow-md"
                  />
                  <div v-else class="mt-12 flex flex-1 items-center justify-center border border-dashed border-slate-300 text-xs text-slate-400">
                    这一页没有照片
                  </div>
                  <div class="mt-5 flex items-center justify-between text-xs text-slate-500">
                    <button :disabled="bookPage === 0" class="disabled:opacity-25" @click="turnPage(-1)">上一页</button>
                    <span>{{ diaries.length ? bookPage + 1 : 0 }} / {{ diaries.length }}</span>
                    <button :disabled="bookPage >= diaries.length - 1" class="disabled:opacity-25" @click="turnPage(1)">下一页</button>
                  </div>
                </section>
              </div>
            </div>

            <aside class="lz-hud-card p-5">
              <p class="lz-hud-label">Journal // 今日心绪</p>
              <h3 class="mt-1.5 text-base text-white">写下今天</h3>
              <p class="mt-1 text-xs text-slate-500">内容仅自己可见</p>
              <div class="mt-4 flex flex-wrap gap-2">
                <button
                  v-for="m in moods"
                  :key="m.key"
                  class="th-mood rounded-lg border px-3 py-2 text-xs transition"
                  :class="selectedMood === m.key ? 'is-active' : 'border-white/10 text-slate-400'"
                  @click="selectedMood = m.key"
                ><img class="inline-block h-4 w-4 align-[-3px]" :src="m.icon" alt="" aria-hidden="true" /> {{ m.label }}</button>
              </div>
              <textarea v-model="diaryDraft" rows="7" placeholder="写下此刻的想法…" class="cosmic-input mt-4 w-full rounded-xl px-4 py-3 text-sm text-slate-200" />
              <div class="mt-3 flex items-center gap-2">
                <label class="lz-btn lz-btn--ghost lz-btn--sm cursor-pointer">
                  {{ imageUploading ? '上传中' : '添加照片' }}
                  <input ref="diaryInputRef" type="file" accept="image/*" class="hidden" @change="onDiaryImagePick" />
                </label>
                <button v-if="diaryImage" class="text-xs text-rose-300" @click="clearDiaryImage">移除照片</button>
              </div>
              <img v-if="diaryImage" :src="diaryImage" class="mt-3 h-24 w-full rounded-lg object-cover" />
              <button class="lz-btn lz-btn--primary lz-btn--md mt-4 w-full" @click="saveDiary">写入日记本</button>
            </aside>
          </div>

          <div v-else class="space-y-5">
            <div class="lz-edge-glow rounded-2xl bg-white/[0.03] p-4">
              <p class="lz-hud-label mb-2">Drift // 投递一颗星</p>
              <div class="mb-2 flex flex-wrap gap-2">
                <button
                  v-for="emoji in reactionEmojis"
                  :key="emoji"
                  class="rounded-full border px-3 py-1 text-sm transition"
                  :class="postEmoji === emoji ? 'border-violet-400/50 bg-violet-400/15 shadow-[0_0_14px_-4px_rgba(167,139,250,0.7)]' : 'border-white/10 text-slate-400 hover:border-white/20'"
                  @click="postEmoji = emoji"
                >
                  {{ emoji }}
                </button>
              </div>
              <textarea
                v-model="postDraft"
                rows="3"
                placeholder="匿名分享你的心情，贴上星轨便利贴…"
                class="cosmic-input w-full rounded-2xl px-4 py-3 text-sm text-slate-200"
              />
              <div class="mt-3 flex flex-wrap items-center gap-3">
                <label class="lz-btn lz-btn--ghost lz-btn--sm cursor-pointer">
                  {{ imageUploading ? '上传中…' : '上传图片' }}
                  <input ref="imageInputRef" type="file" accept="image/*" class="hidden" @change="onImagePick" />
                </label>
                <div v-if="imagePreview" class="relative">
                  <img :src="imagePreview" class="h-16 w-16 rounded-lg object-cover" />
                  <button class="absolute -right-2 -top-2 rounded-full border border-rose-300/30 bg-slate-950 px-2 py-0.5 text-xs text-rose-200" @click="clearPostImage">删除</button>
                </div>
                <button class="lz-btn lz-btn--primary lz-btn--md ml-auto" @click="publishPost">
                  贴到星轨墙
                </button>
              </div>
              <p v-if="uploadError" class="mt-2 text-xs text-rose-300">{{ uploadError }}</p>
            </div>

            <div class="columns-1 gap-4 sm:columns-2 xl:columns-3">
              <article
                v-for="(post, i) in posts"
                :key="post.id"
                class="th-sticker mb-4 inline-block w-full break-inside-avoid rounded-2xl border border-white/10 bg-white/[0.04] p-4 shadow-[0_12px_40px_rgba(0,0,0,0.25)] backdrop-blur-md"
                :style="{
                  '--rot': `${stickerRotate(post.id)}deg`,
                  '--drift-delay': stickerDelay(post.id),
                  animationDelay: `${Math.min(i * 50, 450)}ms`,
                }"
              >
                <p class="text-sm leading-6 text-slate-100">{{ post.content }}</p>
                <img v-if="post.image_url" :src="post.image_url" class="mt-3 max-h-56 w-full rounded-xl object-cover" />
                <div class="mt-2 flex items-center justify-between">
                  <p class="text-[10px] text-slate-500">{{ post.created_at.slice(0, 16) }}</p>
                  <button v-if="post.is_mine" class="text-[10px] text-rose-300/80 hover:text-rose-200" @click="withdrawPost(post.id)">撤销发布</button>
                </div>

                <div class="mt-3 flex flex-wrap gap-1.5">
                  <button
                    v-for="emoji in reactionEmojis"
                    :key="`${post.id}-${emoji}`"
                    class="rounded-full border px-2 py-0.5 text-xs transition"
                    :class="post.my_reactions?.includes(emoji) ? 'border-rose-400/40 bg-rose-400/10 text-rose-100' : 'border-white/10 text-slate-400 hover:border-white/25'"
                    @click="toggleReaction(post.id, emoji)"
                  >
                    {{ emoji }}
                    <span v-if="post.reaction_summary?.[emoji]">{{ post.reaction_summary[emoji] }}</span>
                  </button>
                </div>

                <button class="mt-3 text-xs text-violet-300 hover:text-violet-200" @click="openComments(post.id)">
                  {{ expandedPostId === post.id ? '收起评论' : `评论 ${post.comment_count}` }}
                </button>

                <div v-if="expandedPostId === post.id" class="mt-3 space-y-2 rounded-xl border border-white/10 bg-black/20 p-3">
                  <div v-for="c in commentsByPost[post.id] ?? []" :key="c.id" class="text-xs text-slate-300">
                    <span v-if="c.emoji" class="mr-1">{{ c.emoji }}</span>{{ c.content || '（表情回应）' }}
                    <span class="ml-2 text-slate-500">{{ c.created_at.slice(11, 16) }}</span>
                  </div>
                  <div class="flex flex-wrap gap-1">
                    <button
                      v-for="emoji in reactionEmojis"
                      :key="`c-${post.id}-${emoji}`"
                      class="rounded-full border px-2 py-0.5 text-xs"
                      :class="commentEmoji === emoji ? 'border-sky-400/40 text-sky-100' : 'border-white/10 text-slate-500'"
                      @click="commentEmoji = emoji"
                    >
                      {{ emoji }}
                    </button>
                  </div>
                  <div class="flex gap-2">
                    <input
                      v-model="commentDraft"
                      placeholder="写下暖心评论…"
                      class="cosmic-input flex-1 rounded-xl px-3 py-2 text-xs text-slate-200"
                    />
                    <button class="lz-btn lz-btn--soft lz-btn--sm" @click="sendComment(post.id)">
                      发送
                    </button>
                  </div>
                </div>
              </article>
            </div>
          </div>
        </div>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
/* 环境氛围层交叉淡入 */
.th-ambient-enter-active,
.th-ambient-leave-active {
  transition: opacity 1.4s ease;
}
.th-ambient-enter-from,
.th-ambient-leave-to {
  opacity: 0;
}

/* 场景卡 */
.th-scene {
  transition: border-color 0.22s ease, box-shadow 0.22s ease, transform 0.22s ease, background 0.22s ease;
}
.th-scene:hover {
  transform: translateY(-2px);
  border-color: rgb(var(--lz-accent) / 0.35);
}
.th-scene.is-active {
  border-color: rgb(var(--lz-accent) / 0.5);
  background:
    radial-gradient(120% 90% at 50% 0%, rgb(var(--lz-accent) / 0.16), transparent 60%),
    var(--surface-2);
  box-shadow: 0 0 32px -10px rgb(var(--lz-accent) / 0.55);
}
.th-scene.is-active::before {
  opacity: 1;
}
.th-scene-icon {
  display: inline-block;
  filter: drop-shadow(0 0 10px rgb(var(--lz-accent) / 0.45));
}

/* 心情选择 */
.th-mood.is-active {
  border-color: rgb(var(--lz-accent) / 0.5);
  background: rgb(var(--lz-accent) / 0.12);
  color: #fff;
  box-shadow: 0 0 16px -6px rgb(var(--lz-accent) / 0.6);
}

/* 漂流星轨贴纸：入场漂入 + 待机缓慢漂浮 + hover 发光 */
.th-sticker {
  --rot: 0deg;
  --drift-delay: 0s;
  transform: rotate(var(--rot));
  animation:
    th-pop 0.5s cubic-bezier(0.22, 1, 0.36, 1) both,
    th-drift 7s ease-in-out infinite var(--drift-delay);
  transition: box-shadow 0.25s ease, border-color 0.25s ease;
}
.th-sticker:hover {
  border-color: rgb(var(--lz-accent) / 0.4);
  box-shadow: 0 16px 50px rgba(0, 0, 0, 0.35), 0 0 32px -10px rgb(var(--lz-accent) / 0.5);
  animation-play-state: paused, running;
}

@keyframes th-pop {
  from { opacity: 0; transform: rotate(var(--rot)) translateY(22px) scale(0.96); }
  to { opacity: 1; transform: rotate(var(--rot)) translateY(0) scale(1); }
}

@keyframes th-drift {
  0%, 100% { transform: rotate(var(--rot)) translateY(0); }
  50% { transform: rotate(var(--rot)) translateY(-6px); }
}

/* 日记本 */
.diary-cover {
  transform-origin: left center;
  background-image:
    radial-gradient(circle at 70% 18%, rgba(245, 215, 110, 0.1), transparent 34%),
    linear-gradient(135deg, rgba(255, 255, 255, 0.04), transparent);
}
.diary-gold {
  color: var(--astro-gold-bright);
  text-shadow: 0 0 14px var(--astro-gold-glow);
}
.diary-gold-line {
  display: block;
  height: 1px;
  background: linear-gradient(90deg, var(--astro-gold-dim), transparent);
}
.diary-book {
  transform-style: preserve-3d;
  background-image: repeating-linear-gradient(
    to bottom,
    transparent 0,
    transparent 31px,
    rgba(71, 85, 105, 0.08) 32px
  );
}
.diary-book::after {
  content: '';
  pointer-events: none;
  position: absolute;
  inset: 0 49.7%;
  width: 5px;
  background: linear-gradient(90deg, rgba(15, 23, 42, 0.12), rgba(255, 255, 255, 0.55), rgba(15, 23, 42, 0.12));
}
.diary-turning {
  animation: diary-page-turn 0.44s ease-in-out;
}
@keyframes diary-page-turn {
  0% { transform: rotateY(0deg); }
  48% { transform: rotateY(-7deg) scale(0.985); }
  100% { transform: rotateY(0deg); }
}
@media (max-width: 767px) {
  .diary-book {
    grid-template-columns: 1fr;
    height: auto;
    min-height: 520px;
  }
  .diary-book > section:first-child {
    border-right: 0;
    border-bottom: 1px solid rgba(148, 163, 184, 0.35);
  }
  .diary-book::after { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  .diary-turning { animation: none; }
  .th-sticker { animation: none; }
  .th-ambient-enter-active,
  .th-ambient-leave-active,
  .th-scene {
    transition: none;
  }
}
</style>

import { apiDelete, apiGet, apiPatch, apiPost, apiPostForm } from './client';

export interface FocusSummary {
  today_minutes: number;
  week_minutes: number;
  sessions: number;
}

export interface FocusHeatmapCell {
  day: number;
  slot: string;
  minutes: number;
}

export interface FocusHeatmap {
  week_start: string;
  week_end: string;
  total_minutes: number;
  cells: FocusHeatmapCell[];
}

export interface FocusLeaderboardItem {
  user_id: string;
  display_name: string;
  minutes: number;
}

export interface MistakeItem {
  id: string;
  question: string;
  student_answer: string;
  correct_answer: string;
  subject: string;
  note: string;
  created_at: string;
}

export interface WishItem {
  id: string;
  user_id: string;
  display_name: string;
  content: string;
  likes: number;
  liked_by_me: boolean;
  created_at: string;
}

export interface ForumPostItem {
  id: string;
  author_id: string;
  author_name: string;
  class_id: string;
  title: string;
  body: string;
  kind: string;
  file_url: string;
  source_type?: string;
  source_id?: string;
  like_count: number;
  promoted_asset_id: string;
  created_at: string;
}

export interface ForumAttachableItem {
  id: string;
  source_type: 'vault' | 'workshop' | 'video' | string;
  title: string;
  subtitle: string;
  kind_label: string;
  file_url: string;
  content_preview: string;
  suggested_kind: string;
}

export interface ShopItem {
  id: string;
  name: string;
  description: string;
  cost: number;
  kind: string;
  pet_slug?: string;
}

export interface OwnedShopItem {
  item_id: string;
  item_name: string;
  kind?: string;
  pet_slug?: string;
  cost?: number;
  redeemed_at?: string;
}

export interface AchievementItem {
  id: string;
  name: string;
  description: string;
  icon: string;
  unlocked: boolean;
  progress: number;
  target: number;
}

export interface LeisureSessionResult {
  points_awarded: number;
  total_points: number;
  message: string;
  pet_affinity_delta?: number;
}

export interface DailyTask {
  id: string;
  title: string;
  task_type: string;
  done: boolean;
  points: number;
}

export interface SignInStatus {
  signed_today: boolean;
  streak: number;
  points_awarded: number;
  calendar: { day: string; signed: boolean }[];
}

export interface StudyStreak {
  streak_days: number;
  calendar: { day: string; studied: boolean }[];
}

export interface KnowledgeGraph {
  nodes: { id: string; name: string; slug: string; galaxy: string; status: string; mastery: number }[];
  edges: { source: string; target: string }[];
}

export interface BuddyMatch {
  user_id: string;
  display_name: string;
  reason: string;
  complement_score: number;
}

export interface ProgressBoardItem {
  user_id: string;
  display_name: string;
  lit_count: number;
  total_planets: number;
  mastery_rate: number;
  recent_activity: string;
  is_me: boolean;
}

export interface ProgressBoard {
  scope: string;
  scope_label: string;
  total_planets: number;
  students: ProgressBoardItem[];
}

export interface GameChallenge {
  id: string;
  challenger_name: string;
  target_name: string;
  game: string;
  challenger_score: number;
  target_score: number;
  status: string;
}

export interface Milestone {
  id: string;
  achievement_id: string;
  achievement_name: string;
  unlocked_at: string;
}

export interface ChatReaction {
  emoji: string;
  count: number;
  reacted_by_me: boolean;
}

export interface ArchivePolishIssue {
  original: string;
  suggestion: string;
  reason: string;
}

export interface ArchivePolishResult {
  original: string;
  revised: string;
  issues: ArchivePolishIssue[];
  originality_tips: string[];
}

export interface OralPracticeResult {
  reply: string;
  feedback: string;
  score: number | null;
  next_prompt: string;
  audio_url?: string;
  transcript?: string;
  pronunciation?: {
    total?: number | null;
    accuracy?: number | null;
    fluency?: number | null;
    integrity?: number | null;
    engine?: string;
    passed?: boolean;
    language?: string;
    expected_jyutping?: string;
    transcribed_jyutping?: string;
    expected_text?: string;
    transcribed_text?: string;
  } | null;
}

export const postFocusSession = (minutes: number, source = 'pomodoro', room_id = '') =>
  apiPost<FocusSummary>('/api/focus/session', { minutes, source, room_id });
export const fetchFocusSummary = () => apiGet<FocusSummary>('/api/focus/summary');
export const fetchFocusHeatmap = (week_offset = 0) =>
  apiGet<FocusHeatmap>(`/api/focus/heatmap?week_offset=${week_offset}`);
export const fetchFocusLeaderboard = (room_id = '') =>
  apiGet<FocusLeaderboardItem[]>(
    `/api/focus/leaderboard${room_id ? `?room_id=${encodeURIComponent(room_id)}` : ''}`,
  );

export const fetchMistakes = () => apiGet<MistakeItem[]>('/api/mistakes');
export const createMistake = (payload: Omit<MistakeItem, 'id' | 'created_at'>) =>
  apiPost<MistakeItem>('/api/mistakes', payload);
export const removeMistake = (id: string) => apiDelete<{ status: string }>(`/api/mistakes/${id}`);

export const fetchWishes = () => apiGet<WishItem[]>('/api/wishes');
export const createWish = (content: string) => apiPost<WishItem>('/api/wishes', { content });
export const likeWish = (id: string) => apiPost<WishItem>(`/api/wishes/${id}/like`, {});

export const fetchForumPosts = (class_id = '') =>
  apiGet<ForumPostItem[]>(`/api/forum/posts${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`);
export const createForumPost = (payload: {
  title: string;
  body: string;
  kind?: string;
  file_url?: string;
  source_type?: string;
  source_id?: string;
}) => apiPost<ForumPostItem>('/api/forum/posts', payload);
export const fetchForumAttachable = () =>
  apiGet<{ items: ForumAttachableItem[] }>('/api/forum/attachable');
export const likeForumPost = (id: string) => apiPost<ForumPostItem>(`/api/forum/posts/${id}/like`, {});
export const promoteForumPost = (id: string, galaxy_slug = '', planet_slug = '') =>
  apiPost<ForumPostItem & { star_asset?: { id: string; title: string } }>(
    `/api/forum/posts/${id}/promote`,
    { galaxy_slug, planet_slug },
  );

export const fetchShopItems = () => apiGet<ShopItem[]>('/api/shop/items');
export const fetchShopOwned = () => apiGet<OwnedShopItem[]>('/api/shop/owned');
export const redeemShopItem = (item_id: string) =>
  apiPost<{ ok: boolean; points: number; item?: ShopItem; pet_slug?: string }>('/api/shop/redeem', { item_id });
export const postLeisureSession = (game: string, score: number, won: boolean) =>
  apiPost<LeisureSessionResult>('/api/leisure/session', { game, score, won });
export const ocrMistakePhoto = (file: File) => {
  const form = new FormData();
  form.append('photo', file);
  return apiPostForm<{ question: string; subject_guess: string; correct_answer_guess: string; vision_unavailable: boolean }>(
    '/api/mistakes/ocr',
    form,
  );
};

export interface MistakeDraft {
  question: string;
  student_answer: string;
  correct_answer: string;
  subject: string;
  note: string;
}

/** 批量识别一张图中的多道错题（预览，不入库） */
export const importMistakePhoto = (file: File) => {
  const form = new FormData();
  form.append('photo', file);
  return apiPostForm<{ ok: boolean; items: MistakeDraft[] }>('/api/mistakes/import-photo', form, {
    timeoutMs: 150_000,
  });
};

/** 批量入库（导入确认后调用） */
export const createMistakesBatch = (items: MistakeDraft[]) =>
  apiPost<MistakeItem[]>('/api/mistakes/batch', items);
export const fetchAchievements = () => apiGet<AchievementItem[]>('/api/achievements');
export const fetchMilestones = () => apiGet<Milestone[]>('/api/achievements/milestones');
export const fetchDailyTasks = () => apiGet<DailyTask[]>('/api/learn/daily-tasks');
export const toggleDailyTask = (task_id: string) => apiPost<DailyTask>('/api/learn/daily-tasks/toggle', { task_id });
export const fetchKnowledgeGraph = () => apiGet<KnowledgeGraph>('/api/learn/knowledge-graph');
export const fetchProgressBoard = () => apiGet<ProgressBoard>('/api/learn/progress-board');
export const explainKnowledge = (slug: string) => apiGet<{ slug: string; name: string; galaxy: string; summary: string; tips: string[] }>(`/api/learn/knowledge/${slug}/explain`);
export const askKnowledge = (slug: string, question: string) => apiPost<{ answer: string }>('/api/learn/knowledge/ask', { slug, question });
export const fetchAiQuiz = (slug: string) => apiGet<{ slug: string; name: string; questions: { q: string; hint: string }[] }>(`/api/learn/ai-quiz/${slug}`);
export const submitAiQuiz = (body: { slug: string; question_index: number; answer: string; self_ok?: boolean | null }) =>
  apiPost<{ ok: boolean; correct: boolean; feedback: string; message: string }>('/api/learn/ai-quiz/submit', body);
export const fetchFocusYearly = () =>
  apiGet<{ cells: { date: string; minutes: number; sessions?: number }[]; total_minutes: number }>('/api/focus/yearly');
export interface NoteItem {
  id: string;
  planet_slug: string;
  galaxy_slug?: string;
  title: string;
  content: string;
  attachment_url: string;
  blocks_json?: unknown[];
  source?: string;
  session_id?: string;
  created_at: string;
  updated_at: string;
}

export interface LessonResourceItem {
  id: string;
  title: string;
  galaxy_slug: string;
  file_url: string;
  class_id: string;
  resource_kind?: string;
  promoted_asset_id?: string;
  created_at: string;
  star_asset?: {
    id: string;
    title: string;
    asset_type: string;
    galaxy_slug: string;
    planet_slug: string;
    class_id?: string;
  };
}

export interface TreeHolePostItem {
  id: string;
  content: string;
  image_url: string;
  like_count: number;
  liked_by_me: boolean;
  reaction_summary: Record<string, number>;
  my_reactions: string[];
  comment_count: number;
  is_mine: boolean;
  created_at: string;
}

export interface TreeHoleCommentItem {
  id: string;
  post_id: string;
  content: string;
  emoji: string;
  created_at: string;
}

export const fetchNotes = (opts: { planet_slug?: string; galaxy_slug?: string; q?: string } | string = '') => {
  const q = new URLSearchParams();
  if (typeof opts === 'string') {
    if (opts) q.set('planet_slug', opts);
  } else {
    if (opts.planet_slug) q.set('planet_slug', opts.planet_slug);
    if (opts.galaxy_slug) q.set('galaxy_slug', opts.galaxy_slug);
    if (opts.q) q.set('q', opts.q);
  }
  const qs = q.toString();
  return apiGet<NoteItem[]>(`/api/notes${qs ? `?${qs}` : ''}`);
};
export const createNote = (payload: {
  title: string;
  content: string;
  planet_slug?: string;
  galaxy_slug?: string;
  attachment_url?: string;
}) => apiPost<NoteItem>('/api/notes', payload);
export const updateNote = (
  noteId: string,
  payload: { title?: string; content?: string; blocks_json?: unknown[]; attachment_url?: string },
) => apiPatch<NoteItem>(`/api/notes/${encodeURIComponent(noteId)}`, payload);
export const deleteNote = (noteId: string) => apiDelete(`/api/notes/${noteId}`);
export const uploadNoteAttachment = (file: File) => {
  const form = new FormData();
  form.append('file', file);
  return apiPostForm<{ url: string }>('/api/notes/upload', form);
};
export const fetchLessonResources = (galaxy_slug = '', resource_kind = '') => {
  const q = new URLSearchParams();
  if (galaxy_slug) q.set('galaxy_slug', galaxy_slug);
  if (resource_kind) q.set('resource_kind', resource_kind);
  const qs = q.toString();
  return apiGet<LessonResourceItem[]>(`/api/resources${qs ? `?${qs}` : ''}`);
};
export const uploadTeacherResource = (
  file: File,
  title: string,
  galaxy_slug: string,
  class_id = '',
  resource_kind = 'other',
) => {
  const form = new FormData();
  form.append('file', file);
  form.append('title', title);
  form.append('galaxy_slug', galaxy_slug);
  form.append('class_id', class_id);
  form.append('resource_kind', resource_kind);
  return apiPostForm<LessonResourceItem>('/api/teacher/resources', form);
};
export const createTeacherResourceFromText = (payload: {
  title: string;
  content: string;
  galaxy_slug?: string;
  class_id?: string;
  resource_kind?: string;
}) => apiPost<LessonResourceItem>('/api/teacher/resources/from-text', payload);

export const promoteTeacherResource = (
  resourceId: string,
  payload: { class_id?: string; galaxy_slug?: string; planet_slug?: string; asset_type?: string } = {},
) => apiPost<LessonResourceItem>(`/api/teacher/resources/${encodeURIComponent(resourceId)}/promote-to-starlib`, payload);

export const promoteGeneratedResource = (
  resourceId: string,
  payload: { class_id?: string; galaxy_slug?: string; planet_slug?: string } = {},
) => apiPost<LessonResourceItem>(`/api/teacher/generated/${encodeURIComponent(resourceId)}/promote-to-starlib`, payload);

export const deleteTeacherResource = (resourceId: string) =>
  apiDelete<{ ok: boolean }>(`/api/teacher/resources/${encodeURIComponent(resourceId)}`);
export const fetchTreeHolePosts = () => apiGet<TreeHolePostItem[]>('/api/tree-hole/posts');
export const createTreeHolePost = (content: string, image_url = '') => apiPost('/api/tree-hole/posts', { content, image_url });
export const deleteTreeHolePost = (postId: string) => apiDelete<{ ok: boolean }>(`/api/tree-hole/posts/${postId}`);
export const likeTreeHolePost = (postId: string) => apiPost<{ like_count: number; liked_by_me: boolean }>(`/api/tree-hole/posts/${postId}/like`, {});
export const reactTreeHolePost = (postId: string, emoji: string) =>
  apiPost<{ reaction_summary: Record<string, number>; my_reactions: string[]; toggled_on: boolean }>(
    `/api/tree-hole/posts/${postId}/react`,
    { emoji },
  );
export const fetchTreeHoleComments = (postId: string) => apiGet<TreeHoleCommentItem[]>(`/api/tree-hole/posts/${postId}/comments`);
export const createTreeHoleComment = (postId: string, content: string, emoji = '') =>
  apiPost<TreeHoleCommentItem>(`/api/tree-hole/posts/${postId}/comments`, { content, emoji });
export const uploadTreeHoleImage = (file: File) => {
  const form = new FormData();
  form.append('image', file);
  return apiPostForm<{ url: string }>('/api/tree-hole/upload-image', form);
};
export interface MoodDiaryItem {
  id: string;
  mood: string;
  content: string;
  image_url: string;
  created_at: string;
}
export const fetchMoodDiaries = () => apiGet<MoodDiaryItem[]>('/api/tree-hole/diaries');
export const createMoodDiary = (mood: string, content: string, image_url = '') =>
  apiPost<MoodDiaryItem>('/api/tree-hole/diaries', { mood, content, image_url });
export const fetchBuddyMatches = () => apiGet<BuddyMatch[]>('/api/learn/buddy-matches');
export const fetchSignInStatus = () => apiGet<SignInStatus>('/api/leisure/sign-in');
export const postSignIn = () => apiPost<SignInStatus>('/api/leisure/sign-in', {});
export const fetchStudyStreak = () => apiGet<StudyStreak>('/api/study/streak-calendar');
export const createGameChallenge = (target_user_id: string, game: string, score: number) =>
  apiPost<GameChallenge>('/api/leisure/challenges', { target_user_id, game, score });
export const respondGameChallenge = (challenge_id: string, score: number) =>
  apiPost<GameChallenge>(`/api/leisure/challenges/${challenge_id}/respond`, { target_user_id: '', game: '', score });
export const fetchPendingChallenges = () => apiGet<GameChallenge[]>('/api/leisure/challenges/pending');
export const equipTitle = (title_id: string) => apiPost<{ equipped_title: string }>('/api/users/me/title', { title_id });
export const equipStudyTheme = (theme_id: string) => apiPost<{ study_theme: string }>('/api/users/me/study-theme', { theme_id });
export const polishArchive = (text: string, file?: File | null) => {
  const form = new FormData();
  form.append('text', text);
  if (file) form.append('file', file);
  return apiPostForm<ArchivePolishResult>('/api/archive/polish', form);
};
export const submitOralPractice = (cabin: string, message: string, mode: string) =>
  apiPost<OralPracticeResult>('/api/agents/oral', { cabin, message, mode });

export const submitOralAudio = (
  cabin: string,
  mode: string,
  file: Blob,
  durationSec: number,
  transcript = '',
  refText = '',
) => {
  const form = new FormData();
  form.append('cabin', cabin);
  form.append('mode', mode);
  form.append('duration_sec', String(durationSec));
  form.append('transcript', transcript);
  form.append('ref_text', refText);
  const ext = file.type.includes('mp4') ? 'm4a' : file.type.includes('ogg') ? 'ogg' : 'webm';
  form.append('file', file, `oral.${ext}`);
  return apiPostForm<OralPracticeResult>('/api/agents/oral-audio', form);
};

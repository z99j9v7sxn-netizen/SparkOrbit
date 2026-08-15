<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import OrbitExplorer from '../components/OrbitExplorer.vue';
import PlanetPanel from '../components/PlanetPanel.vue';
import AvatarBadge from '../components/AvatarBadge.vue';
import MirrorDashboard from '../components/MirrorDashboard.vue';
import BlackHoleAssessment from '../components/BlackHoleAssessment.vue';
import NotificationToast from '../components/NotificationToast.vue';
import FeedbackWidget from '../components/common/FeedbackWidget.vue';
import MiniChart from '../components/MiniChart.vue';
import ZoneHub from '../components/ZoneHub.vue';
import ChatZone from '../components/chat/ChatZone.vue';
import LeisureZone from '../components/leisure/LeisureZone.vue';
import StudyZone from '../components/study/StudyZone.vue';
import DomainZone from '../components/domain/DomainZone.vue';
import TreeHoleZone from '../components/treehole/TreeHoleZone.vue';
import MockInterviewZone from '../components/interview/MockInterviewZone.vue';
import AiToolsPanel from '../components/learning/AiToolsPanel.vue';
import AiQuizPanel from '../components/learning/AiQuizPanel.vue';
import DailyTaskList from '../components/learning/DailyTaskList.vue';
import StudentAssignmentsPanel from '../components/learning/StudentAssignmentsPanel.vue';
import KnowledgeGraph from '../components/learning/KnowledgeGraph.vue';
import BuddyMatcher from '../components/learning/BuddyMatcher.vue';
import MistakeBook from '../components/learning/MistakeBook.vue';
import VaultStudio from '../components/learning/vault/VaultStudio.vue';
import FocusTimer from '../components/learning/FocusTimer.vue';
import StellarArchive from '../components/archive/StellarArchive.vue';
import AsteroidChallenge from '../components/trial/AsteroidChallenge.vue';
import OrbitNavigator from '../components/learning/OrbitNavigator.vue';
import InterstellarComms from '../components/comms/InterstellarComms.vue';
import NotificationBell from '../components/NotificationBell.vue';
import PetStage from '../components/pet/PetStage.vue';
import PetPicker from '../components/pet/PetPicker.vue';
import PetActionMenu from '../components/pet/PetActionMenu.vue';
import CosmicBackground from '../components/CosmicBackground.vue';
import NebulaGalaxy from '../components/hub/NebulaGalaxy.vue';
import type { GalaxyZoneKey } from '../three/galaxy/cluster-layout';
import ZoneDock, { type DockItem } from '../components/common/ZoneDock.vue';
import SimulationConsole from '../components/SimulationConsole.vue';
import LearningPathPanel from '../components/learning/LearningPathPanel.vue';
import ResourceStudio from '../components/learning/ResourceStudio.vue';
import GrowthReport from '../components/learning/GrowthReport.vue';
import AlgoVizLab from '../components/learning/AlgoVizLab.vue';
import CodeLab from '../components/learning/CodeLab.vue';
import StarLibrary from '../components/learning/StarLibrary.vue';
import TutorLab from '../components/learning/TutorLab.vue';
import ReviewQueuePanel from '../components/learning/ReviewQueuePanel.vue';
import ExamCenter from '../components/learning/exam/ExamCenter.vue';
import StudyCalendar from '../components/learning/StudyCalendar.vue';

import { fetchPets, bumpPetAffinity, fetchPetAffinity, type PetAction, type PetManifest } from '../api/pet';
import { usePetController } from '../composables/usePetController';
import { fetchAvatarState, fetchWeeklyActivity, type AvatarState, type GalaxyDetail, type Planet } from '../api/orbit';
import { createMistake, fetchProgressBoard, type ProgressBoard } from '../api/zone';
import type { MistakeTutorPayload } from '../api/digitalTutor';
import { useAuthStore } from '../stores/auth';
import { useOrbitStore } from '../stores/orbit';
import { useOrbitSync } from '../composables/useOrbitSync';

type Zone = 'hub' | 'chat' | 'learn' | 'leisure' | 'study' | 'domain' | 'treehole' | 'interview';

const auth = useAuthStore();
const orbit = useOrbitStore();
const router = useRouter();
const route = useRoute();

const zone = ref<Zone>('hub');
const orbitActive = computed(() => zone.value === 'learn');
useOrbitSync(orbitActive);
const explorer = ref<InstanceType<typeof OrbitExplorer> | null>(null);
const quizPanelRef = ref<InstanceType<typeof AiQuizPanel> | null>(null);
const focusTimerRef = ref<InstanceType<typeof FocusTimer> | null>(null);
const mistakeBookRef = ref<InstanceType<typeof MistakeBook> | null>(null);
const avatarBadgeRef = ref<HTMLDivElement | null>(null);
const avatar = ref<AvatarState | null>(null);
const showPetPicker = ref(false);
const avatarSurge = ref(false);
const showAssessment = ref<{ slug: string; name: string } | null>(null);
/** 进入星系后的摸底邀请卡：不再强制弹出评估，由学生主动触发 */
const assessmentOffer = ref<{ slug: string; name: string } | null>(null);
const learnDock = ref<string | null>(null);
/** 右栏形态：full 详情 / mini 窄条；与 selectedPlanet 解耦，收起不退出星球 */
const planetPanelMode = ref<'full' | 'mini'>('full');
const pendingLearnDock = ref<string | null>(null);
const pendingFocusMinutes = ref(25);
const showProgressBoard = ref(false);
const progressBoard = ref<ProgressBoard | null>(null);
const progressBoardLoading = ref(false);
const studyZoneRef = ref<InstanceType<typeof StudyZone> | null>(null);
const deepViewLabel = ref<string | null>(null);
const showSimConsole = ref(false);
const simConsoleRef = ref<InstanceType<typeof SimulationConsole> | null>(null);

const DEMO_CORE_KEYS = new Set(['profile', 'resources', 'path', 'growth', 'starlib', 'viz', 'codelab', 'notes', 'mistakes', 'tutor']);
const demoSlimMode = ref(localStorage.getItem('sparkorbit_demo_slim') === '1');
const pendingMistakeTutor = ref<MistakeTutorPayload | null>(null);
const planetTutorTarget = ref<{ planetSlug: string; planetName: string } | null>(null);
const vaultStudioOpen = ref(false);
const PANEL_WIDE = 'w-[min(860px,calc(100vw-120px))]';
const PANEL_XWIDE = 'w-[min(1400px,calc(100vw-88px))]';
const allLearnDockItems: DockItem[] = [
  // 学识：输入型学习
  { key: 'starlib', label: '星库', iconSrc: '/icons/archive.svg', group: '学识', accent: 'sky', desc: '原书阅读 · 划词问答', panelClass: PANEL_XWIDE },
  { key: 'viz', label: '演武舱', iconSrc: '/icons/challenge.svg', group: '学识', accent: 'sky', desc: '算法步进可视演练', panelClass: PANEL_WIDE },
  { key: 'codelab', label: '代码舱', iconSrc: '/icons/ai.svg', group: '学识', accent: 'sky', desc: '在线编码实验', panelClass: PANEL_WIDE },
  { key: 'resources', label: '资源工坊', iconSrc: '/icons/resources.svg', group: '学识', accent: 'sky', desc: 'AI 学案 / 闪卡 / 试题生成', panelClass: PANEL_WIDE },
  { key: 'tutor', label: '伴学舱', iconSrc: '/icons/ai.svg', group: '学识', accent: 'violet', desc: '数字人伴学对话', panelClass: PANEL_WIDE },
  // 航向：规划与评估
  { key: 'profile', label: '画像', iconSrc: '/icons/profile.svg', group: '航向', accent: 'sky', desc: '学习画像与能力透视', panelClass: PANEL_WIDE },
  { key: 'path', label: '学习路径', iconSrc: '/icons/path.svg', group: '航向', accent: 'sky', desc: '个性化学习路径规划', panelClass: PANEL_WIDE },
  { key: 'growth', label: '成长评估', iconSrc: '/icons/growth.svg', group: '航向', accent: 'sky', desc: '阶段成长报告' },
  { key: 'graph', label: '星链', iconSrc: '/icons/graph.svg', group: '航向', accent: 'sky', desc: '知识点关联网络' },
  { key: 'navigator', label: '星轨导航仪', iconSrc: '/icons/navigator.svg', group: '航向', accent: 'sky', desc: '跨星系快速跃迁' },
  { key: 'examcenter', label: '考级中心', iconSrc: '/icons/medal.svg', group: '学识', accent: 'sky', desc: '四六级刷题 · 模考 · 词汇 · 精听', panelClass: PANEL_WIDE },
  // 实战：练习与检验
  { key: 'review', label: '今日复习', iconSrc: '/icons/sparkle.svg', group: '实战', accent: 'amber', desc: '遗忘曲线复习队列' },
  { key: 'tasks', label: '任务', iconSrc: '/icons/tasks.svg', group: '实战', accent: 'amber', desc: '今日任务与复习固化' },
  { key: 'homework', label: '作业', iconSrc: '/icons/homework.svg', group: '实战', accent: 'amber', desc: '教师布置的作业' },
  { key: 'quiz', label: '智能测验', iconSrc: '/icons/quiz.svg', group: '实战', accent: 'amber', desc: 'AI 出题即时自测' },
  { key: 'mistakes', label: '错题本', iconSrc: '/icons/mistakes.svg', group: '实战', accent: 'amber', desc: '错题回炉与讲解', panelClass: PANEL_WIDE },
  { key: 'challenge', label: '流星雨试炼', iconSrc: '/icons/challenge.svg', group: '实战', accent: 'amber', desc: '限时知识挑战' },
  // 装备：效率工具
  { key: 'ai', label: '智能工具', iconSrc: '/icons/ai.svg', group: '装备', accent: 'violet', desc: '拍照解题 · 智能文本' },
  { key: 'notes', label: '星轨知识库', iconSrc: '/icons/notes.svg', group: '装备', accent: 'emerald', desc: '双链笔记知识库' },
  { key: 'focus', label: '番茄钟', iconSrc: '/icons/focus.svg', group: '装备', accent: 'emerald', desc: '专注计时' },
  { key: 'calendar', label: '学习日历', iconSrc: '/icons/calendar.svg', group: '装备', accent: 'emerald', desc: '任务·作业·复习一览', panelClass: PANEL_WIDE },
  { key: 'archive', label: '恒星档案馆', iconSrc: '/icons/archive.svg', group: '装备', accent: 'emerald', desc: '学习履历档案', panelClass: PANEL_WIDE },
  // 星际：社交互动
  { key: 'buddy', label: '搭子', iconSrc: '/icons/buddy.svg', group: '星际', accent: 'rose', desc: '学习搭子匹配' },
  { key: 'comms', label: '星际通讯舱', iconSrc: '/icons/comms.svg', group: '星际', accent: 'rose', desc: '星际社区互动', panelClass: PANEL_WIDE },
];
const learnDockItems = computed(() =>
  demoSlimMode.value ? allLearnDockItems.filter((i) => DEMO_CORE_KEYS.has(i.key)) : allLearnDockItems,
);
function toggleDemoSlim() {
  demoSlimMode.value = !demoSlimMode.value;
  localStorage.setItem('sparkorbit_demo_slim', demoSlimMode.value ? '1' : '0');
}

const petStageRef = ref<InstanceType<typeof PetStage> | null>(null);
const petManifest = ref<PetManifest | null>(null);
const petAffinityLevel = ref(0);
const { menuOpen, bubbleText, forcedAction, showBubble, triggerAction } = usePetController();

const GREET_LINES = ['加油，星轨在等你！', '今天也要点亮一颗星～', '桌宠永远站你这边！', '专注一下，会更强哦'];

const petBonusFps = computed(() => {
  const streak = avatar.value?.streak_days ?? 0;
  const points = avatar.value?.points ?? 0;
  if (streak >= 7 || points >= 100) return 4;
  if (streak >= 3 || points >= 50) return 2;
  return 0;
});

watch(zone, async (next) => {
  const dockToOpen = pendingLearnDock.value;
  learnDock.value = dockToOpen;
  pendingLearnDock.value = null;
  deepViewLabel.value = null;
  if (next === 'learn') {
    await nextTick();
    explorer.value?.reactivate?.();
    if (dockToOpen === 'focus') {
      await nextTick();
      focusTimerRef.value?.startWithMinutes(pendingFocusMinutes.value);
      pendingFocusMinutes.value = 25;
    } else if (dockToOpen === 'quiz') {
      await nextTick();
      quizPanelRef.value?.load?.();
    }
  }
});

watch(learnDock, async (next) => {
  explorer.value?.setFocusMode(Boolean(next));
  if (next === 'quiz') {
    await nextTick();
    quizPanelRef.value?.load?.();
  }
});

const galaxyRef = ref<InstanceType<typeof NebulaGalaxy> | null>(null);
const galaxyFallback = ref(false);
const warpBusy = ref(false);
const galaxyAnchors = computed(() => (galaxyFallback.value ? null : galaxyRef.value?.anchors ?? null));

async function enterZone(next: Zone) {
  if (warpBusy.value) return;
  // 星云模式：先执行镜头飞入簇心，再切换分区
  if (next !== 'hub' && zone.value === 'hub' && !galaxyFallback.value && galaxyRef.value) {
    warpBusy.value = true;
    try {
      await galaxyRef.value.flyToZone(next as GalaxyZoneKey);
    } finally {
      warpBusy.value = false;
    }
  }
  zone.value = next;
}

function onZoneHover(key: GalaxyZoneKey | null) {
  galaxyRef.value?.notifyHover(key);
}

function backToHub() {
  zone.value = 'hub';
  orbit.clearSelection();
  learnDock.value = null;
  deepViewLabel.value = null;
}

function onDeepViewChange(label: string | null) {
  deepViewLabel.value = label;
}

function handleBack() {
  if (deepViewLabel.value && zone.value === 'study') {
    studyZoneRef.value?.backOneLevel();
    return;
  }
  backToHub();
}

const backLabel = computed(() => {
  if (deepViewLabel.value) return `← ${deepViewLabel.value}`;
  return '← 返回星区中枢';
});

const selectedPlanet = computed(() => orbit.selectedPlanet);
const selectedGalaxyName = computed(() => orbit.currentGalaxy?.name ?? '');

watch(learnDock, (next) => {
  if (next && selectedPlanet.value) {
    planetPanelMode.value = 'mini';
  }
});

const comet = reactive({ visible: false, x: 0, y: 0, tx: 0, ty: 0, moving: false });

async function loadAvatar() {
  try {
    avatar.value = await fetchAvatarState();
    if (avatar.value) {
      orbit.updateCycleProgress(avatar.value.mastery_rate);
    }
    const weekly = await fetchWeeklyActivity();
    orbit.setWeeklyActivity(weekly.labels, weekly.hours);
  } catch {
    avatar.value = null;
  }
}

async function toggleProgressBoard() {
  showProgressBoard.value = !showProgressBoard.value;
  if (!showProgressBoard.value) return;
  progressBoardLoading.value = true;
  try {
    progressBoard.value = await fetchProgressBoard();
  } catch {
    progressBoard.value = null;
  } finally {
    progressBoardLoading.value = false;
  }
}

function onSelectPlanet(planet: Planet, galaxy: GalaxyDetail) {
  orbit.selectPlanet(planet, galaxy);
  planetPanelMode.value = 'full';
}

function onGalaxyEnter(slug: string, name: string) {
  assessmentOffer.value = { slug, name };
}

function startAssessment() {
  showAssessment.value = assessmentOffer.value;
  assessmentOffer.value = null;
}

function onAssessmentDone() {
  showAssessment.value = null;
  explorer.value?.reloadCurrentGalaxy();
  void loadAvatar();
}

// 回宇宙或离开学习区时收起摸底邀请
watch(() => orbit.viewMode, (mode) => {
  if (mode === 'universe') assessmentOffer.value = null;
});
watch(zone, (next) => {
  if (next !== 'learn') assessmentOffer.value = null;
});

// ---- URL 深链：/student?galaxy=slug&planet=slug 与视图状态双向同步 ----

watch(
  [zone, () => orbit.viewMode, () => orbit.currentGalaxy?.slug, () => orbit.selectedPlanet?.slug],
  () => {
    const query = { ...route.query } as Record<string, string | undefined>;
    delete query.galaxy;
    delete query.planet;
    if (zone.value === 'learn' && orbit.viewMode === 'galaxy' && orbit.currentGalaxy?.slug) {
      query.galaxy = orbit.currentGalaxy.slug;
      if (orbit.selectedPlanet?.slug) query.planet = orbit.selectedPlanet.slug;
    }
    if ((route.query.galaxy ?? undefined) === query.galaxy && (route.query.planet ?? undefined) === query.planet) return;
    void router.replace({ query });
  },
);

function restoreFromDeepLink() {
  const qGalaxy = typeof route.query.galaxy === 'string' ? route.query.galaxy : '';
  const qPlanet = typeof route.query.planet === 'string' ? route.query.planet : '';
  if (!qGalaxy) return;
  zone.value = 'learn';
  // 等星图完成挂载/重激活后再跃迁；渲染令牌保证后发起的星系渲染覆盖宇宙渲染
  window.setTimeout(() => {
    if (qPlanet) void explorer.value?.focusPlanet(qGalaxy, qPlanet);
    else void explorer.value?.focusGalaxy(qGalaxy);
  }, 600);
}

async function onSupernovaReview(planet: Planet) {
  orbit.triggerMaterialChange(planet.slug, 'lit');
  orbit.pushNotification('超新星复习', `「${planet.name}」记忆已重新点亮`, 'success');
  explorer.value?.triggerSupernova(planet.slug);
  await loadAvatar();
  window.setTimeout(() => explorer.value?.reloadCurrentGalaxy(), 1400);
}

function collapsePlanetPanel() {
  planetPanelMode.value = 'mini';
}

function expandPlanetPanel() {
  planetPanelMode.value = 'full';
}

function exitPlanet() {
  orbit.clearSelection();
  planetPanelMode.value = 'full';
}

const pendingSimTopic = ref<string | null>(null);
const pendingSimDimension = ref<string | undefined>(undefined);
const lastSimSummary = ref<{ topic: string; pathSteps: string[]; rootCause: string } | null>(null);

type SimRequest = string | { topic: string; targetDimension?: string; planetSlug?: string };

const pendingSimPlanetSlug = ref<string | undefined>(undefined);

function onSimulate(payload: SimRequest) {
  const topic = typeof payload === 'string' ? payload : payload.topic;
  const dim = typeof payload === 'string' ? undefined : payload.targetDimension;
  const slug = typeof payload === 'string' ? undefined : payload.planetSlug;
  pendingSimTopic.value = topic;
  pendingSimDimension.value = dim;
  pendingSimPlanetSlug.value = slug;
  showSimConsole.value = true;
  void nextTick(() => {
    void nextTick(() => {
      if (simConsoleRef.value && pendingSimTopic.value) {
        const t = pendingSimTopic.value;
        const d = pendingSimDimension.value;
        const s = pendingSimPlanetSlug.value;
        pendingSimTopic.value = null;
        pendingSimDimension.value = undefined;
        pendingSimPlanetSlug.value = undefined;
        void simConsoleRef.value.run(t, {}, d, s ? { planetSlug: s } : undefined);
      }
    });
  });
}

watch(simConsoleRef, (console) => {
  if (console && pendingSimTopic.value) {
    const t = pendingSimTopic.value;
    const d = pendingSimDimension.value;
    const s = pendingSimPlanetSlug.value;
    pendingSimTopic.value = null;
    pendingSimDimension.value = undefined;
    pendingSimPlanetSlug.value = undefined;
    void console.run(t, {}, d, s ? { planetSlug: s } : undefined);
  }
});

function onSimComplete(payload: { topic: string; pathSteps: string[]; rootCause: string }) {
  lastSimSummary.value = payload;
}

function closeSimConsole() {
  showSimConsole.value = false;
}

async function onSimAddMistake(payload: { question: string; subject: string; note: string }) {
  try {
    await createMistake({
      question: payload.question,
      student_answer: '',
      correct_answer: '',
      subject: payload.subject,
      note: payload.note,
    });
    orbit.pushNotification('错题本', '已加入推演补救条目', 'success');
    learnDock.value = 'mistakes';
  } catch (e) {
    orbit.pushNotification('错题本', e instanceof Error ? e.message : '加入失败', 'warning');
  }
}

function onSimStartFocus(minutes: number) {
  pendingFocusMinutes.value = minutes;
  if (zone.value === 'learn') {
    learnDock.value = 'focus';
    void nextTick(() => focusTimerRef.value?.startWithMinutes(minutes));
  } else {
    pendingLearnDock.value = 'focus';
    zone.value = 'learn';
  }
}

async function onPlanetLit(planet: Planet) {
  orbit.triggerMaterialChange(planet.slug, 'lit');
  orbit.pushNotification('行星点亮', `「${planet.name}」已加入你的星轨！`, 'success');
  explorer.value?.triggerSupernova(planet.slug);
  await loadAvatar();
  window.setTimeout(() => explorer.value?.reloadCurrentGalaxy(), 1400);
}

function onArchiveScan() {
  orbit.pushNotification('恒星档案馆', '正在进行结构化重构扫描...', 'info');
}

function onFireLaser(isCorrect: boolean) {
  if (zone.value === 'learn') {
    explorer.value?.spawnMeteorFx(isCorrect);
  }
  if (isCorrect) {
    orbit.pushNotification('流星雨试炼', '精确命中！陨石击碎', 'success');
    if (avatar.value) avatar.value.points += 50;
  } else {
    orbit.pushNotification('流星雨试炼', '偏离目标，护盾受损', 'warning');
  }
}

async function onOrbitNavigate(target: { galaxySlug: string; galaxyName: string; planetSlug: string; planetName: string }) {
  learnDock.value = null;
  await nextTick();
  await explorer.value?.focusPlanet(target.galaxySlug, target.planetSlug);
  orbit.pushNotification('星轨导航仪', `已跃迁至「${target.planetName}」`, 'success');
}

async function onNoteJumpPlanet(slug: string) {
  if (!slug) return;
  const g = orbit.currentGalaxy;
  const planet = g?.planets?.find((p) => p.slug === slug);
  if (g && planet) {
    await onOrbitNavigate({
      galaxySlug: g.slug,
      galaxyName: g.name,
      planetSlug: planet.slug,
      planetName: planet.name,
    });
    return;
  }
  // 跨星系：尽力用 slug 聚焦当前宇宙
  learnDock.value = null;
  await nextTick();
  if (g) await explorer.value?.focusPlanet(g.slug, slug);
  orbit.pushNotification('笔记本', `尝试跳转到行星 ${slug}`, 'info');
}

function onCommsSpeak(text: string) {
  orbit.pushNotification('星际通讯舱', '接收到来自外星智慧的讯息', 'info');
}

function onSupernova(pos: { x: number; y: number }) {
  const rect = avatarBadgeRef.value?.getBoundingClientRect();
  const tx = rect ? rect.left + rect.width / 2 : window.innerWidth - 60;
  const ty = rect ? rect.top + rect.height / 2 : 40;
  comet.x = pos.x;
  comet.y = pos.y;
  comet.tx = 0;
  comet.ty = 0;
  comet.moving = false;
  comet.visible = true;
  void nextTick(() => {
    requestAnimationFrame(() => {
      comet.tx = tx - pos.x;
      comet.ty = ty - pos.y;
      comet.moving = true;
    });
  });
  window.setTimeout(() => {
    comet.visible = false;
    avatarSurge.value = true;
    window.setTimeout(() => (avatarSurge.value = false), 1200);
  }, 1050);
}

function onOpenChat(ev?: Event) {
  zone.value = 'chat';
  const roomId = (ev as CustomEvent | undefined)?.detail?.roomId as string | undefined;
  if (roomId) {
    window.dispatchEvent(new CustomEvent('sparkorbit:select-chat-room', { detail: { roomId } }));
  }
  orbit.pushNotification('消息', '已切换到聊天区', 'info');
}

function onNotificationOpenChat(roomId: string) {
  zone.value = 'chat';
  window.dispatchEvent(new CustomEvent('sparkorbit:select-chat-room', { detail: { roomId } }));
}

function onPoints(points: number) {
  if (avatar.value) avatar.value.points = points;
  playPetAction('laugh');
  showBubble('积分 UP！');
}

function onOpenMistakeTutor(payload: MistakeTutorPayload) {
  pendingMistakeTutor.value = payload;
  planetTutorTarget.value = null;
  learnDock.value = 'mistakes';
  zone.value = 'learn';
  nextTick(() => {
    mistakeBookRef.value?.openTutor?.(payload);
  });
}

function onOpenPlanetTutor(payload: { planetSlug: string; planetName: string }) {
  pendingMistakeTutor.value = null;
  planetTutorTarget.value = { ...payload };
  learnDock.value = 'tutor';
  zone.value = 'learn';
}

function onMistakeTutorClosed() {
  pendingMistakeTutor.value = null;
}

function onOpenLearnDock(id: string) {
  if (id !== 'mistakes') {
    pendingMistakeTutor.value = null;
  }
  if (id !== 'tutor') {
    planetTutorTarget.value = null;
  }
  if (id === 'notes') {
    vaultStudioOpen.value = true;
    learnDock.value = null;
    zone.value = 'learn';
    if (selectedPlanet.value) planetPanelMode.value = 'mini';
    return;
  }
  learnDock.value = id;
  if (selectedPlanet.value) planetPanelMode.value = 'mini';
}

function onGlobalOpenDock(ev: Event) {
  const detail = (ev as CustomEvent).detail as { dock?: string; resourceId?: string } | undefined;
  const dock = detail?.dock;
  if (!dock) return;
  zone.value = 'learn';
  onOpenLearnDock(dock);
  if (detail?.resourceId) {
    window.setTimeout(() => {
      window.dispatchEvent(
        new CustomEvent('sparkorbit:focus-resource', { detail: { resourceId: detail.resourceId } }),
      );
    }, 80);
  }
}

function onGlobalJumpPlanet(ev: Event) {
  const detail = (ev as CustomEvent).detail as { planetSlug?: string; planetName?: string } | undefined;
  if (!detail?.planetSlug) return;
  zone.value = 'learn';
  void onNoteJumpPlanet(detail.planetSlug);
}

watch(learnDock, (id) => {
  if (id === 'notes') {
    vaultStudioOpen.value = true;
    nextTick(() => {
      learnDock.value = null;
    });
  }
});

function logout() {
  auth.logout();
  router.push('/');
}

async function loadPetMeta() {
  const pets = await fetchPets().catch(() => []);
  const preferred = auth.user?.petSlug || '';
  const matched = pets.find((p) => p.slug === preferred) ?? pets.find((p) => p.slug === 'boxcat') ?? pets[0] ?? null;
  petManifest.value = matched;
  if (auth.user && matched && preferred !== matched.slug) {
    auth.setAuth(auth.token, { ...auth.user, petSlug: matched.slug });
  }
  const aff = await fetchPetAffinity().catch(() => null);
  if (aff) {
    petAffinityLevel.value = aff.level;
    if (auth.user) auth.setAuth(auth.token, { ...auth.user, petAffinity: aff.pet_affinity });
  }
}

function findAction(key: string): PetAction | undefined {
  return petManifest.value?.actions?.find((a) => a.key === key);
}

function playPetAction(key: string) {
  const action = findAction(key);
  if (action) {
    triggerAction(action);
    petStageRef.value?.playAction(action);
  }
}

async function onPetActionSelect(action: PetAction) {
  menuOpen.value = false;
  playPetAction(action.key);
  await bumpPetAffinity(1, action.key).catch(() => null);
  void loadPetMeta();

  const route = action.route;
  if (route === 'greet') {
    showBubble(GREET_LINES[Math.floor(Math.random() * GREET_LINES.length)]);
    return;
  }
  if (route === 'focus') {
    pendingLearnDock.value = 'focus';
    pendingFocusMinutes.value = 25;
    zone.value = 'learn';
    showBubble('开始 25 分钟专注吧！');
    return;
  }
  if (route === 'report') {
    pendingLearnDock.value = 'report';
    zone.value = 'learn';
    return;
  }
  if (route === 'mistakes') {
    pendingLearnDock.value = 'mistakes';
    zone.value = 'learn';
    return;
  }
  if (route === 'leisure') {
    enterZone('leisure');
    return;
  }
  if (route === 'bonus') {
    showBubble('✨ 星尘洒落！也许有惊喜～');
    if (Math.random() < 0.3) orbit.pushNotification('桌宠彩蛋', '额外获得鼓励能量 +1', 'success');
  }
}

function onPetOpenMenu() {
  menuOpen.value = !menuOpen.value;
}

function onCheckin(ev: Event) {
  const detail = (ev as CustomEvent).detail as { minutes?: number };
  playPetAction('wave');
  showBubble(`完成专注 ${detail?.minutes ?? 25} 分钟！`);
}

function onAchievementUnlock() {
  playPetAction('wink');
  showBubble('解锁新成就啦！');
}

function onNewChatMessage() {
  if (zone.value === 'chat') return;
  playPetAction('think');
  showBubble('有人在等你回复～');
}

function onStudyCompanion() {
  playPetAction('walk');
  showBubble('自习陪伴模式已开启');
}

function onGlobalEnterZone(ev: Event) {
  const next = (ev as CustomEvent).detail?.zone as Zone | undefined;
  if (!next) return;
  void enterZone(next);
}

onMounted(() => {
  void loadAvatar();
  void loadPetMeta();
  restoreFromDeepLink();
  window.addEventListener('sparkorbit:open-chat', onOpenChat as EventListener);
  window.addEventListener('sparkorbit:checkin', onCheckin as EventListener);
  window.addEventListener('sparkorbit:achievement-unlock', onAchievementUnlock as EventListener);
  window.addEventListener('sparkorbit:new-chat-message', onNewChatMessage as EventListener);
  window.addEventListener('sparkorbit:study-companion', onStudyCompanion as EventListener);
  window.addEventListener('sparkorbit:open-dock', onGlobalOpenDock as EventListener);
  window.addEventListener('sparkorbit:jump-planet', onGlobalJumpPlanet as EventListener);
  window.addEventListener('sparkorbit:enter-zone', onGlobalEnterZone as EventListener);
});

onBeforeUnmount(() => {
  window.removeEventListener('sparkorbit:open-chat', onOpenChat as EventListener);
  window.removeEventListener('sparkorbit:checkin', onCheckin as EventListener);
  window.removeEventListener('sparkorbit:achievement-unlock', onAchievementUnlock as EventListener);
  window.removeEventListener('sparkorbit:new-chat-message', onNewChatMessage as EventListener);
  window.removeEventListener('sparkorbit:study-companion', onStudyCompanion as EventListener);
  window.removeEventListener('sparkorbit:open-dock', onGlobalOpenDock as EventListener);
  window.removeEventListener('sparkorbit:jump-planet', onGlobalJumpPlanet as EventListener);
  window.removeEventListener('sparkorbit:enter-zone', onGlobalEnterZone as EventListener);
});
</script>

<template>
  <div class="relative h-screen w-screen overflow-hidden bg-black text-sky-50">
    <NotificationToast />
    <FeedbackWidget />

    <header class="pointer-events-none absolute left-0 right-0 top-0 z-20 flex items-start justify-between px-5 py-3">
      <div class="pointer-events-auto flex items-center gap-4">
        <div>
          <p class="text-[10px] uppercase tracking-[0.45em] text-sky-300/70">SparkOrbit 星轨学图</p>
          <h1 class="text-base font-semibold text-white text-glow">星际领航台</h1>
        </div>
      </div>
      <div class="pointer-events-auto flex items-center gap-3">
        <div v-show="zone === 'learn'" class="relative">
          <div class="cosmic-nav-btn flex items-center gap-2 rounded-full px-3 py-1.5">
            <div class="h-8 w-8">
              <MiniChart type="pie" :data="[orbit.cycleProgress]" height="32px" color="#7dd3fc" />
            </div>
            <div class="text-[10px] leading-tight text-slate-300">
              <p>周期进度</p>
              <p class="font-semibold text-sky-200">{{ orbit.cycleProgress }}%</p>
            </div>
            <button
              type="button"
              class="ml-1 rounded-full border border-sky-300/25 px-2 py-0.5 text-[10px] text-sky-100 transition hover:bg-sky-400/15"
              @click="toggleProgressBoard"
            >
              学习榜 {{ showProgressBoard ? '▴' : '▾' }}
            </button>
          </div>
          <div
            v-if="showProgressBoard"
            class="absolute right-0 top-full z-40 mt-2 w-[min(320px,calc(100vw-2rem))] rounded-2xl border border-white/10 bg-[#0a1228]/95 p-3 shadow-xl backdrop-blur"
          >
            <div class="mb-2 flex items-center justify-between">
              <p class="text-xs font-semibold text-white">{{ progressBoard?.scope_label || '学习榜' }}</p>
              <button type="button" class="text-[10px] text-slate-400 hover:text-slate-200" @click="showProgressBoard = false">关闭</button>
            </div>
            <p class="mb-2 text-[10px] text-slate-400">点亮 / 未点亮概览（与周期掌握率口径一致）</p>
            <p v-if="progressBoardLoading" class="py-4 text-center text-xs text-slate-400">加载中…</p>
            <p v-else-if="!progressBoard?.students?.length" class="py-4 text-center text-xs text-slate-500">暂无同窗数据</p>
            <ul v-else class="max-h-64 space-y-1.5 overflow-auto">
              <li
                v-for="(s, idx) in progressBoard.students"
                :key="s.user_id"
                class="rounded-xl border px-2.5 py-2 text-[11px]"
                :class="s.is_me ? 'border-sky-400/40 bg-sky-500/10' : 'border-white/5 bg-white/[0.03]'"
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="font-medium text-slate-100">
                    <span class="mr-1 text-slate-500">{{ idx + 1 }}.</span>{{ s.display_name }}
                    <span v-if="s.is_me" class="ml-1 text-[10px] text-sky-300">我</span>
                  </span>
                  <span class="shrink-0 text-sky-200">{{ s.mastery_rate }}%</span>
                </div>
                <div class="mt-1 flex items-center justify-between text-[10px] text-slate-400">
                  <span>
                    已点亮 {{ s.lit_count }}/{{ s.total_planets }}
                    · 未点亮 {{ Math.max(0, s.total_planets - s.lit_count) }}
                  </span>
                </div>
                <p class="mt-0.5 text-[10px] text-slate-500">{{ s.recent_activity }}</p>
              </li>
            </ul>
          </div>
        </div>
        <span class="cosmic-nav-btn rounded-full px-3 py-1 text-xs text-amber-200">积分 {{ avatar?.points ?? 0 }}</span>
        <NotificationBell @open-chat="onNotificationOpenChat" />
        <div ref="avatarBadgeRef" :class="avatarSurge ? 'animate-surge' : ''">
          <AvatarBadge :avatar="avatar" @logout="logout" @updated="loadAvatar" />
        </div>
      </div>
    </header>

    <section class="absolute inset-0">
      <template v-if="zone !== 'learn' && zone !== 'study' && zone !== 'domain' && zone !== 'interview'">
        <NebulaGalaxy
          v-if="!galaxyFallback"
          ref="galaxyRef"
          :dimmed="zone !== 'hub'"
          @fallback="galaxyFallback = true"
        />
        <CosmicBackground v-else :active="true" />
      </template>
      <div
        v-else-if="zone === 'domain' || zone === 'interview'"
        class="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,#0b1a33_0%,#050816_55%,#02040a_100%)]"
        aria-hidden="true"
      />
      <OrbitExplorer
        v-show="zone === 'learn'"
        ref="explorer"
        :active="orbitActive"
        :interactive="!learnDock"
        :slim="demoSlimMode"
        @select-planet="onSelectPlanet"
        @supernova="onSupernova"
        @enter-galaxy="onGalaxyEnter"
      />

      <ZoneHub v-if="zone === 'hub'" :anchors="galaxyAnchors" @enter="enterZone" @hover="onZoneHover" />
      <ChatZone v-else-if="zone === 'chat'" />
      <StudyZone v-else-if="zone === 'study'" ref="studyZoneRef" @depth-change="onDeepViewChange" />
      <LeisureZone v-else-if="zone === 'leisure'" @pet-affinity="loadPetMeta" />
      <DomainZone v-else-if="zone === 'domain'" />
      <TreeHoleZone v-else-if="zone === 'treehole'" />
      <MockInterviewZone v-else-if="zone === 'interview'" />

      <button
        v-if="zone !== 'hub'"
        class="cosmic-nav-btn pointer-events-auto absolute left-5 top-20 z-30 rounded-full px-4 py-2 text-xs text-sky-100"
        @click="handleBack"
      >
        {{ backLabel }}
      </button>
      <button
        v-if="zone === 'learn'"
        type="button"
        class="cosmic-nav-btn pointer-events-auto absolute left-5 top-32 z-30 rounded-full px-3 py-1.5 text-[10px]"
        :class="demoSlimMode ? 'text-emerald-200 ring-1 ring-emerald-400/40' : 'text-slate-300'"
        @click="toggleDemoSlim"
      >
        {{ demoSlimMode ? '答辩精简 · 开' : '答辩精简 · 关' }}
      </button>

      <!-- 学习区侧边坞：默认不遮挡星图 -->
      <ZoneDock v-if="zone === 'learn'" v-model="learnDock" :items="learnDockItems">
        <template #profile>
          <MirrorDashboard :sim-summary="lastSimSummary" @simulate="onSimulate" />
        </template>
        <template #starlib>
          <StarLibrary />
        </template>
        <template #viz>
          <AlgoVizLab />
        </template>
        <template #codelab>
          <CodeLab />
        </template>
        <template #resources>
          <ResourceStudio />
        </template>
        <template #tutor>
          <TutorLab
            :planet-slug="planetTutorTarget?.planetSlug || selectedPlanet?.slug"
            :planet-name="planetTutorTarget?.planetName || selectedPlanet?.name"
            :initial-tab="planetTutorTarget ? 'avatar' : 'chat'"
          />
        </template>
        <template #path>
          <LearningPathPanel @navigate="onOrbitNavigate" @open-dock="(id) => { learnDock = id }" />
        </template>
        <template #growth>
          <GrowthReport />
        </template>
        <template #review>
          <ReviewQueuePanel />
        </template>
        <template #examcenter>
          <ExamCenter />
        </template>
        <template #calendar>
          <StudyCalendar @open-dock="onOpenLearnDock" />
        </template>
        <template #tasks>
          <DailyTaskList />
        </template>
        <template #homework>
          <StudentAssignmentsPanel />
        </template>
        <template #graph>
          <KnowledgeGraph />
        </template>
        <template #buddy>
          <BuddyMatcher />
        </template>
        <template #ai>
          <AiToolsPanel />
        </template>
        <template #quiz>
          <AiQuizPanel ref="quizPanelRef" />
        </template>
        <template #mistakes>
          <MistakeBook
            ref="mistakeBookRef"
            :pending-tutor="pendingMistakeTutor"
            @simulate="onSimulate"
            @tutor-closed="onMistakeTutorClosed"
          />
        </template>
        <template #notes>
          <p class="text-xs text-slate-400">正在打开星轨知识库…</p>
        </template>
        <template #focus>
          <FocusTimer ref="focusTimerRef" @close="learnDock = null" />
        </template>
        <template #archive>
          <StellarArchive embedded @scan="onArchiveScan" />
        </template>
        <template #challenge>
          <AsteroidChallenge embedded @fire-laser="onFireLaser" />
        </template>
        <template #navigator>
          <OrbitNavigator embedded @navigate="onOrbitNavigate" />
        </template>
        <template #comms>
          <InterstellarComms embedded @speak="onCommsSpeak" />
        </template>
      </ZoneDock>

      <div v-if="zone !== 'hub'" class="pointer-events-auto absolute bottom-8 right-5 z-10">
        <div class="relative">
          <div
            v-if="bubbleText"
            class="pointer-events-none absolute -top-12 left-1/2 z-20 max-w-[10rem] -translate-x-1/2 rounded-2xl border border-sky-400/20 bg-slate-950/95 px-3 py-1.5 text-center text-[10px] text-sky-100 shadow-glow"
          >
            {{ bubbleText }}
          </div>
          <PetActionMenu
            :open="menuOpen"
            :actions="petManifest?.actions ?? []"
            @select="onPetActionSelect"
            @close="menuOpen = false"
          />
          <PetStage
            ref="petStageRef"
            :slug="auth.user?.petSlug || petManifest?.slug || 'boxcat'"
            :bonus-fps="petBonusFps"
            :forced-action="forcedAction"
            :affinity-level="petAffinityLevel"
            @open-menu="onPetOpenMenu"
          />
        </div>
        <button class="mt-2 w-full rounded-xl border border-white/10 px-3 py-2 text-xs text-slate-300 hover:bg-white/5" @click="showPetPicker = !showPetPicker">
          更换桌宠
        </button>
      </div>
      <PetPicker v-if="showPetPicker" @close="showPetPicker = false" @selected="(slug) => { if (auth.user) auth.user.petSlug = slug; void loadPetMeta(); }" />

      <transition name="fade">
        <div
          v-if="selectedPlanet && zone === 'learn' && planetPanelMode === 'full'"
          class="absolute inset-0 z-30 bg-black/45 backdrop-blur-[2px]"
          @click.self="collapsePlanetPanel"
        />
      </transition>
      <transition name="slide">
        <div
          v-if="selectedPlanet && zone === 'learn' && planetPanelMode === 'full'"
          class="absolute right-0 top-0 z-40 h-full w-full max-w-[min(760px,96vw)] shadow-[-24px_0_60px_rgba(0,0,0,0.45)]"
        >
          <PlanetPanel
            :planet="selectedPlanet"
            :galaxy-name="selectedGalaxyName"
            @collapse="collapsePlanetPanel"
            @exit="exitPlanet"
            @lit="onPlanetLit"
            @points="onPoints"
            @simulate="onSimulate"
            @supernova-review="onSupernovaReview"
            @open-dock="onOpenLearnDock"
            @open-mistake-tutor="onOpenMistakeTutor"
            @open-planet-tutor="onOpenPlanetTutor"
          />
        </div>
      </transition>
      <!-- 迷你条：保持星球上下文，不挡左坞 -->
      <div
        v-if="selectedPlanet && zone === 'learn' && planetPanelMode === 'mini'"
        class="pointer-events-auto absolute right-0 top-1/2 z-40 flex w-14 -translate-y-1/2 flex-col items-center gap-2 rounded-l-2xl border border-r-0 border-cyan-400/30 bg-slate-950/95 px-1.5 py-3 shadow-[-8px_0_24px_rgba(0,0,0,0.4)]"
      >
        <span class="h-2 w-2 rounded-full bg-sky-400 shadow-[0_0_10px_#38bdf8]"></span>
        <p
          class="max-h-40 overflow-hidden text-[10px] font-semibold leading-tight tracking-wide text-sky-100"
          style="writing-mode: vertical-rl; text-orientation: mixed"
          :title="selectedPlanet.name"
        >{{ selectedPlanet.name }}</p>
        <button
          type="button"
          class="w-full rounded-lg border border-sky-400/40 bg-sky-500/20 px-1 py-1.5 text-[10px] text-sky-50 hover:bg-sky-500/35"
          @click="expandPlanetPanel"
        >展开</button>
        <button
          type="button"
          class="w-full rounded-lg border border-white/10 px-1 py-1 text-[9px] text-slate-400 hover:border-rose-300/40 hover:text-rose-100"
          @click="exitPlanet"
        >退出</button>
      </div>

      <!-- 摸底邀请卡：进星系不打断心流，学生主动选择是否评估 -->
      <transition name="fade">
        <div
          v-if="assessmentOffer && zone === 'learn' && !showAssessment"
          class="pointer-events-auto absolute bottom-16 left-1/2 z-20 -translate-x-1/2"
        >
          <div class="flex items-center gap-3 rounded-2xl border border-sky-400/25 bg-[#0a1228]/92 px-4 py-2.5 shadow-xl backdrop-blur">
            <p class="text-xs text-slate-200">已进入「{{ assessmentOffer.name }}」— 要先做一次黑洞摸底评估吗？</p>
            <button
              type="button"
              class="shrink-0 rounded-full border border-sky-400/45 bg-sky-500/20 px-3 py-1 text-[11px] text-sky-50 transition hover:bg-sky-500/35"
              @click="startAssessment"
            >开始摸底</button>
            <button
              type="button"
              class="shrink-0 rounded-full border border-white/10 px-3 py-1 text-[11px] text-slate-400 transition hover:text-slate-200"
              @click="assessmentOffer = null"
            >稍后再说</button>
          </div>
        </div>
      </transition>

      <BlackHoleAssessment
        v-if="showAssessment"
        :galaxy-slug="showAssessment.slug"
        :galaxy-name="showAssessment.name"
        @done="onAssessmentDone"
        @close="showAssessment = null"
      />

      <teleport to="body">
        <transition name="fade-scale">
          <div
            v-if="showSimConsole"
            class="fixed inset-0 z-[120] flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm"
            @click.self="closeSimConsole"
          >
            <div class="h-[min(640px,90vh)] w-[min(900px,96vw)]">
              <SimulationConsole
                ref="simConsoleRef"
                @close="closeSimConsole"
                @add-mistake="onSimAddMistake"
                @start-focus="onSimStartFocus"
                @complete="onSimComplete"
              />
            </div>
          </div>
        </transition>
      </teleport>

      <VaultStudio
        :open="vaultStudioOpen"
        :planet-slug="selectedPlanet?.slug || ''"
        :galaxy-slug="orbit.currentGalaxy?.slug || ''"
        @close="vaultStudioOpen = false"
      />
    </section>

    <div
      v-if="comet.visible"
      class="pointer-events-none fixed z-40 h-3 w-3 rounded-full"
      :style="{
        left: `${comet.x}px`,
        top: `${comet.y}px`,
        transform: `translate(${comet.tx}px, ${comet.ty}px)`,
        transition: comet.moving ? 'transform 1s cubic-bezier(0.5,0,0.2,1)' : 'none',
        background: 'radial-gradient(circle, #fff7d6 0%, #7dd3fc 55%, rgba(125,211,252,0) 75%)',
        boxShadow: '0 0 18px 6px rgba(125,211,252,0.85), 0 0 40px 12px rgba(168,85,247,0.4)',
      }"
    ></div>
  </div>
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>

import { defineStore } from 'pinia';
import { ref, shallowRef } from 'vue';
import type { GalaxyDetail, Planet, PlanetStatus } from '../api/orbit';

export interface OrbitNotification {
  id: string;
  title: string;
  message: string;
  type: 'info' | 'warning' | 'success';
  createdAt: number;
  planetSlug?: string;
  actionLabel?: string;
}

export interface MaterialChangeEvent {
  slug: string;
  status: PlanetStatus;
}

export const useOrbitStore = defineStore('orbit', () => {
  const selectedPlanet = ref<Planet | null>(null);
  const currentGalaxy = shallowRef<GalaxyDetail | null>(null);
  const viewMode = ref<'universe' | 'galaxy'>('universe');
  const hoveredPlanet = ref<Planet | null>(null);
  const notifications = ref<OrbitNotification[]>([]);
  const materialChangeQueue = ref<MaterialChangeEvent | null>(null);

  const learningWeeklyHours = ref<number[]>([0, 0, 0, 0, 0, 0, 0]);
  const learningWeekLabels = ref<string[]>(['一', '二', '三', '四', '五', '六', '日']);
  const cycleProgress = ref(0);
  const planetSnapshots = ref<Record<string, { status: PlanetStatus; score: number; attempts: number }>>({});
  /** 最近一次费曼讲闸评分（0~1），供 PlanetPanel 过讲闸 */
  const lastExplainScore = ref<number | null>(null);
  const lastExplainPlanetSlug = ref('');

  function setExplainScore(slug: string, score: number | null) {
    lastExplainPlanetSlug.value = slug || '';
    lastExplainScore.value = score;
  }

  function selectPlanet(planet: Planet, galaxy: GalaxyDetail) {
    selectedPlanet.value = planet;
    currentGalaxy.value = galaxy;
  }

  function clearSelection() {
    selectedPlanet.value = null;
  }

  function setHoveredPlanet(planet: Planet | null) {
    hoveredPlanet.value = planet;
  }

  function enterGalaxyView(galaxy: GalaxyDetail) {
    currentGalaxy.value = galaxy;
    viewMode.value = 'galaxy';
  }

  function enterUniverseView() {
    viewMode.value = 'universe';
    currentGalaxy.value = null;
    selectedPlanet.value = null;
    hoveredPlanet.value = null;
  }

  function pushNotification(
    title: string,
    message: string,
    type: OrbitNotification['type'] = 'info',
    extra?: { planetSlug?: string; actionLabel?: string },
  ) {
    const note: OrbitNotification = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      title,
      message,
      type,
      createdAt: Date.now(),
      planetSlug: extra?.planetSlug,
      actionLabel: extra?.actionLabel,
    };
    notifications.value.unshift(note);
    if (notifications.value.length > 5) notifications.value.pop();
    return note.id;
  }

  function dismissNotification(id: string) {
    notifications.value = notifications.value.filter((n) => n.id !== id);
  }

  function triggerMaterialChange(slug: string, status: PlanetStatus) {
    materialChangeQueue.value = { slug, status };
  }

  function ackMaterialChange() {
    materialChangeQueue.value = null;
  }

  function updateCycleProgress(rate: number) {
    cycleProgress.value = Math.min(100, Math.max(0, rate));
  }

  function setWeeklyActivity(labels: string[], hours: number[]) {
    learningWeekLabels.value = labels;
    learningWeeklyHours.value = hours;
  }

  function applySnapshot(
    planets: { slug: string; status: PlanetStatus; score: number; attempts: number }[],
  ) {
    const next: Record<string, { status: PlanetStatus; score: number; attempts: number }> = {};
    for (const p of planets) next[p.slug] = { status: p.status, score: p.score, attempts: p.attempts };
    planetSnapshots.value = next;
  }

  return {
    selectedPlanet,
    currentGalaxy,
    viewMode,
    hoveredPlanet,
    notifications,
    materialChangeQueue,
    learningWeeklyHours,
    learningWeekLabels,
    cycleProgress,
    planetSnapshots,
    lastExplainScore,
    lastExplainPlanetSlug,
    setExplainScore,
    selectPlanet,
    clearSelection,
    setHoveredPlanet,
    enterGalaxyView,
    enterUniverseView,
    pushNotification,
    dismissNotification,
    triggerMaterialChange,
    ackMaterialChange,
    updateCycleProgress,
    setWeeklyActivity,
    applySnapshot,
  };
});

import { onBeforeUnmount, watch, type Ref } from 'vue';
import { fetchOrbitSnapshot, fetchStudentAlerts, fetchWeeklyActivity, type PlanetStatus } from '../api/orbit';
import { useOrbitStore } from '../stores/orbit';

const STATUS_LABELS: Record<PlanetStatus, string> = {
  lit: '已点亮',
  dim: '待挑战',
  locked: '锁定',
  fading: '记忆衰减',
  meteor: '陨石危机',
};

const ALERT_LEVEL_MAP: Record<string, 'info' | 'warning' | 'success'> = {
  info: 'info',
  warning: 'warning',
  medium: 'warning',
  high: 'warning',
  success: 'success',
};

export function useOrbitSync(active: Ref<boolean>) {
  const orbit = useOrbitStore();
  let timer: ReturnType<typeof setInterval> | null = null;
  let syncing = false;
  const seenAlerts = new Set<string>();
  const seenStatuses = new Map<string, PlanetStatus>();

  async function syncOnce() {
    if (syncing || !active.value || document.hidden) return;
    syncing = true;
    try {
      const [snapshot, weekly, alerts] = await Promise.all([
        fetchOrbitSnapshot(),
        fetchWeeklyActivity(),
        fetchStudentAlerts(),
      ]);

      orbit.setWeeklyActivity(weekly.labels, weekly.hours);
      orbit.applySnapshot(snapshot.planets);

      for (const planet of snapshot.planets) {
        const prev = seenStatuses.get(planet.slug);
        if (prev && prev !== planet.status) {
          orbit.triggerMaterialChange(planet.slug, planet.status);
          if (planet.status === 'meteor' || planet.status === 'fading') {
            orbit.pushNotification(
              '掌握度变化',
              `检测到行星状态变为 ${STATUS_LABELS[planet.status]}`,
              'warning',
            );
          }
        }
        seenStatuses.set(planet.slug, planet.status);
      }

      for (const alert of alerts) {
        if (seenAlerts.has(alert.id)) continue;
        seenAlerts.add(alert.id);
        orbit.pushNotification(
          alert.title,
          alert.message,
          ALERT_LEVEL_MAP[alert.level] ?? 'info',
          alert.planet_slug
            ? { planetSlug: alert.planet_slug, actionLabel: '去学习' }
            : undefined,
        );
      }
    } catch {
      /* 静默失败，下一轮重试 */
    } finally {
      syncing = false;
    }
  }

  function start() {
    stop();
    void syncOnce();
    timer = setInterval(() => void syncOnce(), 60_000);
    document.addEventListener('visibilitychange', onVisibility);
  }

  function stop() {
    if (timer) clearInterval(timer);
    timer = null;
    document.removeEventListener('visibilitychange', onVisibility);
  }

  function onVisibility() {
    if (!document.hidden && active.value) void syncOnce();
  }

  watch(active, (on) => {
    if (on) start();
    else stop();
  }, { immediate: true });

  onBeforeUnmount(stop);

  return { syncOnce };
}

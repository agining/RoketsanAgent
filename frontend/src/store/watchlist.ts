import { create } from 'zustand';
import type { AnalysisEntity, RiskLevel } from '../types/analysis';

export type WatchlistEventType = 'risk' | 'scenario' | 'approach' | 'behavior' | 'threshold' | 'report' | 'verdict' | 'track' | 'zone';
export type WatchlistSeverity = 'info' | 'warning' | 'critical';

export interface WatchlistSnapshot {
  trackId: string;
  riskLevel: RiskLevel;
  scenario: string | null;
  zone: string | null;
  distanceToBase: number | null;
  etaMin: number | null;
  reportIds: string[];
  reportVerdicts: Record<string, string>;
  lastSeen: string;
  visible: boolean;
}

export interface WatchlistNotification {
  id: string;
  trackId: string;
  type: WatchlistEventType;
  severity: WatchlistSeverity;
  message: string;
  at: string;
  read: boolean;
}

interface WatchlistState {
  trackIds: string[];
  snapshots: Record<string, WatchlistSnapshot>;
  notifications: WatchlistNotification[];
  add: (trackId: string) => void;
  remove: (trackId: string) => void;
  toggle: (trackId: string) => void;
  isWatching: (trackId: string) => boolean;
  applyAnalysis: (entities: AnalysisEntity[], generatedAt: string) => void;
  markAllRead: () => void;
  markRead: (id: string) => void;
}

const watchlistKey = 'atlas-watchlist-track-ids';
const snapshotsKey = 'atlas-watchlist-snapshots';
const notificationsKey = 'atlas-watchlist-notifications';

const readJson = <T,>(key: string, fallback: T): T => {
  if (typeof window === 'undefined') return fallback;
  try {
    const value = window.localStorage.getItem(key);
    return value ? JSON.parse(value) as T : fallback;
  } catch {
    return fallback;
  }
};

const writeJson = (key: string, value: unknown) => {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(key, JSON.stringify(value));
};

const reportIds = (entity: AnalysisEntity) => [...new Set(entity.reports.map(report => report.report_id))].sort();
const reportVerdicts = (entity: AnalysisEntity) => Object.fromEntries(entity.reports.map(report => [report.report_id, report.verdict]));
const behaviorScenario = (scenario: string | null) => Boolean(scenario && /loiter|circl|bekle|dolan/i.test(scenario));

export function watchlistSnapshot(entity: AnalysisEntity): WatchlistSnapshot {
  return {
    trackId: entity.track_id,
    riskLevel: entity.risk_level,
    scenario: entity.scenario,
    zone: entity.zone,
    distanceToBase: entity.distance_to_base_m,
    etaMin: entity.features?.eta_min ?? entity.offframe?.features.eta_min ?? null,
    reportIds: reportIds(entity),
    reportVerdicts: reportVerdicts(entity),
    lastSeen: entity.last_seen,
    visible: entity.source !== null,
  };
}

function event(id: number, trackId: string, type: WatchlistEventType, severity: WatchlistSeverity, message: string, at: string): WatchlistNotification {
  return { id: `${at}-${trackId}-${type}-${id}`, trackId, type, severity, message, at, read: false };
}

function compareSnapshots(previous: WatchlistSnapshot, next: WatchlistSnapshot, at: string) {
  const events: WatchlistNotification[] = [];
  const push = (type: WatchlistEventType, severity: WatchlistSeverity, message: string) => events.push(event(events.length, next.trackId, type, severity, message, at));
  if (previous.riskLevel !== next.riskLevel) push('risk', next.riskLevel === 'CRITICAL' || next.riskLevel === 'HIGH' ? 'critical' : 'warning', `${next.trackId}: Risk ${previous.riskLevel} -> ${next.riskLevel}`);
  if (previous.scenario !== next.scenario) {
    push('scenario', behaviorScenario(next.scenario) ? 'warning' : 'info', `${next.trackId}: Yeni durum: ${next.scenario ?? 'Belirsiz'}`);
    if (!behaviorScenario(previous.scenario) && behaviorScenario(next.scenario)) push('behavior', 'warning', `${next.trackId}: Loitering/circling benzeri davranış başladı`);
  }
  if (previous.zone !== next.zone && next.zone) push('zone', 'info', `${next.trackId}: ${next.zone} bölgesine girdi`);
  if (previous.visible !== next.visible) push('track', next.visible ? 'info' : 'warning', next.visible ? `${next.trackId}: Track tekrar bulundu` : `${next.trackId}: Track bağlantısı kayboldu`);
  if (previous.distanceToBase !== null && next.distanceToBase !== null) {
    if (next.distanceToBase < previous.distanceToBase - 25) push('approach', 'warning', `${next.trackId}: Üsse yaklaşmaya başladı`);
    const crossedDistance = previous.distanceToBase >= 1000 && next.distanceToBase < 1000;
    if (crossedDistance) push('threshold', 'critical', `${next.trackId}: Kritik mesafe eşiği aşıldı (${Math.round(next.distanceToBase)} m)`);
  }
  if ((previous.etaMin ?? Infinity) >= 10 && next.etaMin !== null && next.etaMin < 10) push('threshold', 'critical', `${next.trackId}: ETA kritik eşiğin altında (${next.etaMin.toFixed(1)} dk)`);
  const newReports = next.reportIds.filter(id => !previous.reportIds.includes(id));
  newReports.forEach(reportId => push('report', 'info', `${next.trackId}: Yeni saha raporu eşleşti: ${reportId}`));
  next.reportIds.forEach(reportId => {
    if (previous.reportVerdicts[reportId] && previous.reportVerdicts[reportId] !== next.reportVerdicts[reportId]) push('verdict', 'warning', `${next.trackId}: Rapor hükmü değişti: ${reportId}`);
    if (next.reportVerdicts[reportId] === 'celisir' && previous.reportVerdicts[reportId] !== 'celisir') push('verdict', 'warning', `${next.trackId}: Çelişkili rapor oluştu: ${reportId}`);
  });
  return events;
}

export const useWatchlistStore = create<WatchlistState>((set, get) => ({
  trackIds: readJson<string[]>(watchlistKey, []),
  snapshots: readJson<Record<string, WatchlistSnapshot>>(snapshotsKey, {}),
  notifications: readJson<WatchlistNotification[]>(notificationsKey, []),
  add: trackId => set(state => {
    if (state.trackIds.includes(trackId)) return state;
    const trackIds = [...state.trackIds, trackId];
    writeJson(watchlistKey, trackIds);
    return { trackIds };
  }),
  remove: trackId => set(state => {
    const trackIds = state.trackIds.filter(id => id !== trackId);
    const { [trackId]: _removed, ...snapshots } = state.snapshots;
    writeJson(watchlistKey, trackIds);
    writeJson(snapshotsKey, snapshots);
    return { trackIds, snapshots };
  }),
  toggle: trackId => get().isWatching(trackId) ? get().remove(trackId) : get().add(trackId),
  isWatching: trackId => get().trackIds.includes(trackId),
  applyAnalysis: (entities, generatedAt) => set(state => {
    const byTrack = new Map(entities.map(entity => [entity.track_id, entity]));
    const snapshots = { ...state.snapshots };
    const notifications: WatchlistNotification[] = [];
    state.trackIds.forEach(trackId => {
      const entity = byTrack.get(trackId);
      if (!entity) return;
      const next = watchlistSnapshot(entity);
      const previous = snapshots[trackId];
      if (previous) notifications.push(...compareSnapshots(previous, next, generatedAt));
      snapshots[trackId] = next;
    });
    if (!notifications.length) {
      writeJson(snapshotsKey, snapshots);
      return { snapshots };
    }
    const merged = [...notifications, ...state.notifications].slice(0, 80);
    writeJson(snapshotsKey, snapshots);
    writeJson(notificationsKey, merged);
    return { snapshots, notifications: merged };
  }),
  markAllRead: () => set(state => {
    const notifications = state.notifications.map(item => ({ ...item, read: true }));
    writeJson(notificationsKey, notifications);
    return { notifications };
  }),
  markRead: id => set(state => {
    const notifications = state.notifications.map(item => item.id === id ? { ...item, read: true } : item);
    writeJson(notificationsKey, notifications);
    return { notifications };
  }),
}));

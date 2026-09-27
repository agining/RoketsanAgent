import type { Dispatch, SetStateAction } from 'react';
import { initialMapFilters, type MapFilterState } from '../components/map/MapSidebar';
import type { MapOverlayPanel } from '../components/map/MapOverlays';
import { api } from './api';
import { clockSeconds, formatClock } from './analysis-playback';
import { formatRiskLevel, formatScenario, formatVehicleClass } from './formatters';
import { activeTrackEntities } from './trackFilters';
import { useAgentChatStore } from '../store/agentChat';
import { useOverlayPanelStore } from '../store/overlayPanel';
import { playbackSpeeds, usePlaybackStore, type PlaybackSpeed, type TrailMode } from '../store/playback';
import { useSettingsStore, type FontScale, type ThemeMode } from '../store/settings';
import { useTimelineStore } from '../store/timeline';
import { useTrackingStore, type MapLayer } from '../store/tracking';
import { useVoiceAlertsStore } from '../store/voiceAlerts';
import { useWatchlistStore } from '../store/watchlist';
import { useWorkspaceStore } from '../store/workspace';
import type { AnalysisData, AnalysisEntity, RiskLevel } from '../types/analysis';
import { API_RISK_LEVELS, type ApiRiskLevel, type ApiUiAction } from '../types/api';

/**
 * Voice commands: the API (POST /api/ui-command) turns a spoken command into actions from the catalog in
 * app/ui_actions.md; this module builds the UI context sent with the command and carries the actions out with
 * the app's existing state setters and stores. Every parameter is validated here — the LLM output is untrusted.
 */

/** App-level state and callbacks that live in App.tsx (everything else is reached through the stores). */
export interface UiController {
  analysis: AnalysisData;
  filters: MapFilterState;
  setFilters: Dispatch<SetStateAction<MapFilterState>>;
  selectTrack: (trackId: string) => void;
  sidebarOpen: boolean; setSidebarOpen: (open: boolean) => void;
  bottomOpen: boolean; setBottomOpen: (open: boolean) => void;
  notificationsOpen: boolean; setNotificationsOpen: (open: boolean) => void;
  settingsOpen: boolean; setSettingsOpen: (open: boolean) => void;
  helpOpen: boolean; setHelpOpen: (open: boolean) => void;
  selectedFrameId: string | null;
  startTutorial: () => void;
  openPdfReport: () => void;
  reload: () => void;
  setHumanReview: (enabled: boolean) => Promise<void>;
}

export interface UiActionResult { action: string; ok: boolean; note?: string }

class ActionError extends Error {}
const fail = (message: string): never => { throw new ActionError(message); };

const RISKS: RiskLevel[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'UNKNOWN'];
const API_TO_RISK: Record<ApiRiskLevel, RiskLevel> = { DUSUK: 'LOW', ORTA: 'MEDIUM', YUKSEK: 'HIGH', KRITIK: 'CRITICAL' };
const LAYERS: MapLayer[] = ['vehicles', 'untracked', 'zones', 'base'];
const OVERLAY_PANELS = ['summary', 'priority', 'reviews', 'chat'] as const;
const APP_PANELS = ['sidebar', 'track_list', 'notifications', 'settings', 'help'] as const;
const THEMES: ThemeMode[] = ['light', 'dark', 'system'];
const FONT_SCALES: FontScale[] = [0.85, 1, 1.15, 1.3];
const TRAILS: TrailMode[] = ['elapsed', 'full', 'off'];
const riskRank: Record<RiskLevel, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, UNKNOWN: 0 };

const fold = (value: unknown) => String(value ?? '').trim().toLocaleLowerCase('tr-TR');
const isAll = (value: unknown) => ['all', 'tümü', 'tumu', 'hepsi', '*', ''].includes(fold(value));

function bool(params: Record<string, unknown>, key: string): boolean {
  const value = params[key];
  if (typeof value === 'boolean') return value;
  if (['true', 'on', 'açık', 'evet', '1'].includes(fold(value))) return true;
  if (['false', 'off', 'kapalı', 'hayır', '0'].includes(fold(value))) return false;
  return fail(`"${key}" true/false olmalı.`);
}

function text(params: Record<string, unknown>, key: string): string {
  const value = params[key];
  if (typeof value !== 'string' && typeof value !== 'number') return fail(`"${key}" eksik.`);
  return String(value).trim();
}

function oneOf<T extends string | number>(value: unknown, options: readonly T[], label: string, name: (option: T) => string = String): T {
  const match = options.find(option => fold(option) === fold(value) || fold(name(option)) === fold(value));
  return match ?? fail(`${label} geçersiz: ${String(value)}.`);
}

function risk(value: unknown): RiskLevel {
  const apiLevel = API_RISK_LEVELS.find(level => fold(level) === fold(value));
  return apiLevel ? API_TO_RISK[apiLevel] : oneOf(value, RISKS, 'Risk', formatRiskLevel);
}

/** Track IDs survive speech-to-text badly ("t 106"): exact match first, then the same digits. */
export function resolveTrackId(value: unknown, entities: AnalysisEntity[]): string {
  const wanted = String(value ?? '').replace(/\s+/g, '').toUpperCase();
  const exact = entities.find(entity => entity.track_id.toUpperCase() === wanted);
  if (exact) return exact.track_id;
  const digits = wanted.replace(/\D/g, '').replace(/^0+/, '');
  const byDigits = digits ? entities.filter(entity => entity.track_id.replace(/\D/g, '').replace(/^0+/, '') === digits) : [];
  return byDigits.length === 1 ? byDigits[0].track_id : fail(`İz bulunamadı: ${String(value)}.`);
}

function panelName(value: unknown) {
  return oneOf(value, [...OVERLAY_PANELS, ...APP_PANELS, 'all'] as const, 'Panel');
}

function setPanel(ctrl: UiController, panel: ReturnType<typeof panelName>, open: boolean) {
  const overlay = useOverlayPanelStore.getState();
  if (panel === 'all') {
    if (open) fail('Tüm paneller birlikte açılamaz.');
    overlay.open(null); ctrl.setSettingsOpen(false); ctrl.setHelpOpen(false); ctrl.setNotificationsOpen(false);
    return;
  }
  if ((OVERLAY_PANELS as readonly string[]).includes(panel)) {
    if (open) overlay.open(panel as MapOverlayPanel);
    else if (overlay.current === panel) overlay.open(null);
    return;
  }
  const setters = { sidebar: ctrl.setSidebarOpen, track_list: ctrl.setBottomOpen, notifications: ctrl.setNotificationsOpen, settings: ctrl.setSettingsOpen, help: ctrl.setHelpOpen };
  setters[panel as typeof APP_PANELS[number]](open);
}

type Handler = (params: Record<string, unknown>, ctrl: UiController) => void | string | Promise<void | string>;

const handlers: Record<string, Handler> = {
  set_filters: (params, ctrl) => {
    const entities = activeTrackEntities(ctrl.analysis.entities);
    const next: Partial<MapFilterState> = {};
    if ('risk' in params) next.risk = isAll(params.risk) ? 'ALL' : risk(params.risk);
    if ('vehicle_class' in params) next.vehicleClass = isAll(params.vehicle_class) ? 'ALL'
      : oneOf(params.vehicle_class, [...new Set(entities.map(entity => entity.vehicle_class))], 'Araç tipi', formatVehicleClass);
    if ('scenario' in params) next.scenario = isAll(params.scenario) ? 'ALL'
      : oneOf(params.scenario, [...new Set(entities.map(entity => entity.scenario).filter((value): value is string => Boolean(value)))], 'Senaryo', formatScenario);
    if ('zone' in params) next.zone = isAll(params.zone) ? 'ALL' : oneOf(params.zone, ctrl.analysis.zones.map(zone => zone.name), 'Bölge');
    if ('query' in params) next.query = String(params.query ?? '');
    if (!Object.keys(next).length) fail('Değiştirilecek filtre verilmedi.');
    ctrl.setFilters(current => ({ ...current, ...next }));
  },
  clear_filters: (_params, ctrl) => ctrl.setFilters(initialMapFilters),

  set_layer: params => {
    const layer = oneOf(params.layer, LAYERS, 'Katman');
    const tracking = useTrackingStore.getState();
    if (tracking.layers[layer] !== bool(params, 'visible')) tracking.toggleLayer(layer);
  },
  map_view: params => useTrackingStore.getState().requestView(oneOf(params.view, ['all', 'reset'] as const, 'Görünüm')),
  focus_zone: (params, ctrl) => useTrackingStore.getState().requestView('zone', oneOf(params.zone, ctrl.analysis.zones.map(zone => zone.name), 'Bölge')),
  focus_detection: (params, ctrl) => {
    const id = fold(params.vehicle_id);
    const item = ctrl.analysis.untracked.find(vehicle => fold(vehicle.vehicle_id) === id) ?? fail(`Tespit bulunamadı: ${String(params.vehicle_id)}.`);
    usePlaybackStore.getState().seek(clockSeconds(item.capture_time));
    useTrackingStore.getState().requestView('coordinate', undefined, [item.lon, item.lat]);
  },

  select_track: (params, ctrl) => ctrl.selectTrack(resolveTrackId(params.track_id, activeTrackEntities(ctrl.analysis.entities))),
  clear_selection: () => useTrackingStore.getState().selectTrack(null),
  follow_vehicle: (params, ctrl) => {
    const enabled = bool(params, 'enabled');
    if (params.track_id) ctrl.selectTrack(resolveTrackId(params.track_id, activeTrackEntities(ctrl.analysis.entities)));
    const tracking = useTrackingStore.getState();
    if (!enabled) return tracking.setFollowVehicle(false);
    if (!tracking.selectedTrackId) fail('Takip için önce bir araç seçilmeli.');
    tracking.requestView('vehicle');
  },
  watch_track: (params, ctrl) => {
    const trackId = resolveTrackId(params.track_id, activeTrackEntities(ctrl.analysis.entities));
    const watchlist = useWatchlistStore.getState();
    if (bool(params, 'watch')) watchlist.add(trackId); else watchlist.remove(trackId);
  },
  mark_notifications_read: () => useWatchlistStore.getState().markAllRead(),

  open_panel: (params, ctrl) => setPanel(ctrl, panelName(params.panel), true),
  close_panel: (params, ctrl) => setPanel(ctrl, panelName(params.panel), false),
  start_tutorial: (_params, ctrl) => ctrl.startTutorial(),

  playback: params => {
    const playback = usePlaybackStore.getState();
    const command = oneOf(params.command, ['play', 'pause', 'restart', 'step_forward', 'step_back'] as const, 'Oynatma komutu');
    if (command === 'play') { if (!playback.isPlaying) playback.togglePlaying(); }
    else if (command === 'pause') { if (playback.isPlaying) playback.togglePlaying(); }
    else if (command === 'restart') playback.restart();
    else if (command === 'step_forward') playback.stepNext();
    else playback.stepPrevious();
  },
  seek: params => {
    const time = text(params, 'time');
    if (!/^\d{1,2}[:.]\d{2}([:.]\d{2})?$/.test(time)) fail(`Saat anlaşılamadı: ${time}.`);
    const playback = usePlaybackStore.getState();
    const seconds = clockSeconds(time.replace(/\./g, ':'));
    playback.seek(seconds);
    if (seconds < playback.minTime || seconds > playback.maxTime) return `Zaman aralık dışında; ${formatClock(usePlaybackStore.getState().currentTime)} kullanıldı.`;
  },
  set_speed: params => usePlaybackStore.getState().setSpeed(oneOf(Number(params.speed), playbackSpeeds, 'Hız') as PlaybackSpeed),
  set_trail: params => usePlaybackStore.getState().setTrailMode(oneOf(params.mode, TRAILS, 'Rota izi')),
  set_timeline_compact: params => useTimelineStore.getState().setCompact(bool(params, 'compact')),

  set_voice_alerts: params => useVoiceAlertsStore.getState().setEnabled(bool(params, 'enabled')),
  stop_voice_alert: () => useVoiceAlertsStore.getState().requestStop(),
  set_voice_auto_lock: params => useVoiceAlertsStore.getState().setAutoLock(bool(params, 'enabled')),

  set_theme: params => useSettingsStore.getState().setThemeMode(oneOf(params.mode, THEMES, 'Tema')),
  set_font_scale: params => useSettingsStore.getState().setFontScale(oneOf(Number(params.scale), FONT_SCALES, 'Yazı boyutu')),
  set_human_review: async (params, ctrl) => {
    const enabled = bool(params, 'enabled');
    if (useSettingsStore.getState().humanReview !== enabled) await ctrl.setHumanReview(enabled);
  },

  refresh_data: (_params, ctrl) => ctrl.reload(),
  open_pdf_report: (_params, ctrl) => ctrl.openPdfReport(),
  assess_risky_frames: async (_params, ctrl) => {
    const result = await api.assessAll('ORTA');
    ctrl.reload();
    return `${result.assessed.length} kare değerlendirildi.`;
  },
  ask_agent: (params, ctrl) => {
    const message = text(params, 'message') || fail('Ajana gönderilecek mesaj boş.');
    if (useAgentChatStore.getState().pending) fail('Ajan önceki mesajı yanıtlıyor.');
    useOverlayPanelStore.getState().open('chat');
    void useAgentChatStore.getState().send(message, ctrl.selectedFrameId);
  },
  set_analyst: params => useWorkspaceStore.getState().setAnalyst(text(params, 'name')),
  decide_review: async (params, ctrl) => {
    if (!useSettingsStore.getState().humanReview) fail('"Son söz insanda" kapalı; önce açılmalı.');
    const id = fold(params.vehicle_id);
    const item = ctrl.analysis.reviews.items.find(entry => fold(entry.vehicle_id) === id) ?? fail(`Onay kaydı bulunamadı: ${String(params.vehicle_id)}.`);
    const level = oneOf(params.level, item.options.length ? item.options : API_RISK_LEVELS, 'Seviye', value => formatRiskLevel(API_TO_RISK[value]));
    const analyst = useWorkspaceStore.getState().analyst.trim();
    await api.decideReview(item.vehicle_id, { level, analyst: analyst || null, note: typeof params.note === 'string' ? params.note : null });
    ctrl.reload();
  },
};

export const supportedUiActions = Object.keys(handlers);

/** Runs the actions in order. A failing action is reported and skipped; the rest still run. */
export async function runUiActions(actions: ApiUiAction[], ctrl: UiController): Promise<UiActionResult[]> {
  const results: UiActionResult[] = [];
  for (const item of actions) {
    const handler = typeof item?.action === 'string' ? handlers[item.action] : undefined;
    if (!handler) { results.push({ action: String(item?.action), ok: false, note: 'Desteklenmeyen eylem.' }); continue; }
    const params = item.params && typeof item.params === 'object' ? item.params : {};
    try {
      const note = await handler(params, ctrl);
      results.push({ action: item.action, ok: true, ...(note ? { note } : {}) });
    } catch (cause) {
      results.push({ action: item.action, ok: false, note: cause instanceof Error ? cause.message : 'Eylem uygulanamadı.' });
    }
  }
  return results;
}

const MAX_CONTEXT_TRACKS = 150;
const MAX_CONTEXT_DETECTIONS = 40;

/** What the LLM needs to pick valid parameters: the current option values, IDs and UI state. */
export function buildUiContext(ctrl: UiController) {
  const { analysis } = ctrl;
  const entities = activeTrackEntities(analysis.entities)
    .sort((a, b) => riskRank[b.risk_level] - riskRank[a.risk_level] || a.track_id.localeCompare(b.track_id));
  const unique = (values: (string | null)[]) => [...new Set(values.filter((value): value is string => Boolean(value)))].sort();
  const tracking = useTrackingStore.getState();
  const playback = usePlaybackStore.getState();
  const settings = useSettingsStore.getState();
  const voice = useVoiceAlertsStore.getState();
  return {
    options: {
      risk: RISKS.map(value => ({ value, label: formatRiskLevel(value) })),
      vehicle_class: unique(entities.map(entity => entity.vehicle_class)).map(value => ({ value, label: formatVehicleClass(value) })),
      scenario: unique(entities.map(entity => entity.scenario)).map(value => ({ value, label: formatScenario(value) })),
      zone: analysis.zones.map(zone => zone.name),
    },
    state: {
      filters: ctrl.filters,
      layers: tracking.layers,
      selected_track: tracking.selectedTrackId,
      following: tracking.followVehicle,
      open_panels: {
        overlay: useOverlayPanelStore.getState().current, sidebar: ctrl.sidebarOpen, track_list: ctrl.bottomOpen,
        notifications: ctrl.notificationsOpen, settings: ctrl.settingsOpen, help: ctrl.helpOpen,
      },
      playback: {
        time: formatClock(playback.currentTime), start: formatClock(playback.minTime), end: formatClock(playback.maxTime),
        playing: playback.isPlaying, speed: playback.playbackSpeed, trail: playback.trailMode,
      },
      timeline_compact: useTimelineStore.getState().compact,
      theme: settings.themeMode, font_scale: settings.fontScale, human_review: settings.humanReview,
      voice_alerts: voice.enabled, voice_auto_lock: voice.autoLock,
      analyst: useWorkspaceStore.getState().analyst,
      watchlist: useWatchlistStore.getState().trackIds,
    },
    // "id | tip | risk | bölge | senaryo", riskliden başlayarak
    tracks: entities.slice(0, MAX_CONTEXT_TRACKS).map(entity =>
      [entity.track_id, entity.vehicle_class, entity.risk_level, entity.zone ?? '-', entity.scenario ?? '-'].join(' | ')),
    tracks_total: entities.length,
    untracked_detections: analysis.untracked.slice(0, MAX_CONTEXT_DETECTIONS).map(item =>
      [item.vehicle_id, item.label, item.risk_level, item.zone, item.capture_time].join(' | ')),
    pending_reviews: analysis.reviews.items.filter(item => !item.review)
      .map(item => ({ vehicle_id: item.vehicle_id, track_id: item.track_id, current_level: item.current_level, options: item.options })),
  };
}

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent, type SetStateAction } from 'react';
import {
  AlertTriangle,
  Bell,
  BrainCircuit,
  CheckCheck,
  CircleAlert,
  Clock3,
  Crosshair,
  FileDown,
  HelpCircle,
  LoaderCircle,
  Settings,
  RefreshCw,
  Search,
  UserCheck,
  X,
} from 'lucide-react';

import { OperationsMap } from './components/map/OperationsMap';
import { MapOverlays } from './components/map/MapOverlays';
import {
  MapSidebar,
  entityMatchesMapFilters,
  initialMapFilters,
  type MapFilterState,
} from './components/map/MapSidebar';
import type { MapOverlayPanel } from './components/map/MapOverlays';
import { BottomTrackPanel } from './components/tracks/BottomTrackPanel';
import { TrackDetail } from './components/tracks/TrackDetail';
import { Timeline } from './components/Timeline';
import { AppTutorial } from './components/tutorial/AppTutorial';
import { Button } from './components/ui/button';
import { VoiceAlertCard } from './components/voice/VoiceAlertCard';
import { VoiceCommandButton } from './components/voice/VoiceCommandButton';

import { useAnalysis } from './hooks/useAnalysis';
import { useGraphAnalysis } from './hooks/useGraphAnalysis';
import { GraphAnalysisPanel } from './components/graph/GraphAnalysisPanel';
import type { GraphWindow } from './types/graph';
import { useVoiceAlerts } from './hooks/useVoiceAlerts';

import { api, API_BASE_URL, apiUrl } from './services/api';
import { clockSeconds, positionAtTime } from './services/analysis-playback';
import { formatScenario, formatVehicleClass } from './services/formatters';
import { startPlaybackClock } from './services/playback-clock';
import { activeTrackEntities, isActiveTrackEntity } from './services/trackFilters';
import type { UiController } from './services/uiActions';

import type { AnalysisData } from './types/analysis';

import { usePlaybackStore } from './store/playback';
import { usePanelLayoutStore } from './store/panelLayout';
import {
  useSettingsStore,
  type FontScale,
  type ThemeMode,
} from './store/settings';
import { useTimelineStore } from './store/timeline';
import { useTrackingStore } from './store/tracking';
import { useWatchlistStore } from './store/watchlist';
import { useWorkspaceStore } from './store/workspace';

import hisarLogo from '@/assets/hisar-logo.png';
import { HelpPanel } from './components/help/HelpPanel';

const bottomControlGroupStorageKey = 'hisar-bottom-control-group-position-v1';
type UtilityPanel = 'settings' | 'help' | null;

function demoReportEnabled() {
  const envValue = String(import.meta.env.VITE_DEMO_REPORT ?? '').toLowerCase();
  if (envValue === '1' || envValue === 'true' || envValue === 'yes') return true;
  try {
    return window.localStorage.getItem('hisar-demo-report') === 'true';
  } catch {
    return false;
  }
}

function loadStoredPosition(key: string) {
  if (typeof window === 'undefined') return null;
  try {
    const stored = window.localStorage.getItem(key);
    if (!stored) return null;
    const parsed = JSON.parse(stored) as { x?: unknown; y?: unknown };
    return typeof parsed.x === 'number' && typeof parsed.y === 'number' ? { x: parsed.x, y: parsed.y } : null;
  } catch {
    return null;
  }
}

function formatTimestamp(value: string) {
  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat('tr-TR', {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(date);
}

function InitialState({
  error,
  retry,
}: {
  error: string | null;
  retry: () => void;
}) {
  return (
    <div
      className={`map-first-initial ${error ? 'error' : ''}`}
      role={error ? 'alert' : 'status'}
    >
      {error ? <CircleAlert size={30} /> : <Crosshair size={30} />}

      <h1>
        {error
          ? 'Analiz verisi alınamadı'
          : 'Operasyon haritası yükleniyor'}
      </h1>

      <p>
        {error ??
          `Analiz API'den alınıyor (${
            API_BASE_URL || 'proxy → localhost:8000'
          }).`}
      </p>

      {error ? (
        <Button variant="outline" onClick={retry}>
          <RefreshCw size={15} />
          Tekrar Dene
        </Button>
      ) : (
        <div className="map-loading-line">
          <i />
        </div>
      )}
    </div>
  );
}

const themeOptions: { value: ThemeMode; label: string }[] = [
  { value: 'light', label: 'Açık' },
  { value: 'dark', label: 'Koyu' },
  { value: 'system', label: 'Sistem' },
];

const fontScaleOptions: { value: FontScale; label: string }[] = [
  { value: 0.85, label: 'Küçük' },
  { value: 1, label: 'Normal' },
  { value: 1.15, label: 'Büyük' },
  { value: 1.3, label: 'Çok büyük' },
];

function SettingsPanel({
  open,
  onClose,
  togglingReview,
  humanReviewDisabled,
  onToggleHumanReview,
  summary,
}: {
  open: boolean;
  onClose: () => void;
  togglingReview: boolean;
  humanReviewDisabled: boolean;
  onToggleHumanReview: () => void;
  summary?: AnalysisData['summary'] | null;
}) {
  const themeMode = useSettingsStore(state => state.themeMode);
  const setThemeMode = useSettingsStore(state => state.setThemeMode);
  const fontScale = useSettingsStore(state => state.fontScale);
  const setFontScale = useSettingsStore(state => state.setFontScale);
  const humanReview = useSettingsStore(state => state.humanReview);

  if (!open) return null;

  return (
    <section className="settings-panel" aria-label="Ayarlar paneli">
      <header>
        <span>
          <Settings size={14} />
          Ayarlar
        </span>

        <button type="button" aria-label="Ayarlar panelini kapat" onClick={onClose}>
          <X size={14} />
        </button>
      </header>

      <div className="settings-panel-body">
        <section>
          <h2>Görünüm</h2>

          <div className="settings-field">
            <span>Tema</span>

            <div className="settings-segmented" role="radiogroup" aria-label="Tema seçimi">
              {themeOptions.map(option => (
                <button
                  key={option.value}
                  type="button"
                  role="radio"
                  aria-checked={themeMode === option.value}
                  onClick={() => setThemeMode(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className="settings-field">
            <span>Yazı boyutu</span>

            <div className="settings-segmented" role="radiogroup" aria-label="Yazı boyutu">
              {fontScaleOptions.map(option => (
                <button
                  key={option.value}
                  type="button"
                  role="radio"
                  aria-checked={fontScale === option.value}
                  onClick={() => setFontScale(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        </section>

        <section>
          <h2>Sistem</h2>

          <div className="settings-status-card" aria-label="Model durumu">
            <span>
              <BrainCircuit size={15} />
              <b>Model durumu</b>
            </span>

            <dl>
              <div>
                <dt>LLM durumu</dt>
                <dd>
                  <i className={summary?.llm_enabled ? 'on' : ''} />
                  {summary ? (summary.llm_enabled ? 'Açık' : 'Kapalı') : 'Bilinmiyor'}
                </dd>
              </div>

              <div>
                <dt>Aktif model</dt>
                <dd>{summary?.model ?? 'Model yok'}</dd>
              </div>
            </dl>
          </div>
        </section>

        <section>
          <h2>Operasyon</h2>

          <button
            className={`settings-switch ${humanReview ? 'on' : ''}`}
            type="button"
            role="switch"
            aria-checked={humanReview}
            disabled={humanReviewDisabled || togglingReview}
            onClick={onToggleHumanReview}
          >
            <span>
              <b>Son söz insanda</b>
              <small>Motor ile LLM ayrışırsa karar analist onayına düşer.</small>
            </span>

            {togglingReview ? <LoaderCircle size={14} className="spinning" /> : <i />}
          </button>
        </section>
      </div>
    </section>
  );
}

export default function App() {
  const analysis = useAnalysis();
  const [graphOpen, setGraphOpen] = useState(false);
  const [graphWindow, setGraphWindow] = useState<GraphWindow>({});
  const [showNormalRegions, setShowNormalRegions] = useState(false);
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);
  const graph = useGraphAnalysis(graphOpen, analysis.data, graphWindow);
  const graphRegions = useMemo(() => graphOpen ? (graph.data?.regions ?? []).filter(region =>
    region.interest_score >= (graph.data?.region_interest_threshold ?? 1)) : [], [graphOpen, graph.data]);
  const selectedRegion = graph.data?.regions.find(region => region.region_id === selectedRegionId) ?? null;
  const selectRegion = useCallback((regionId: string) => {
    setSelectedRegionId(regionId);
    useTrackingStore.getState().selectTrack(null);
  }, []);

  const themeMode = useSettingsStore(state => state.themeMode);
  const setThemeMode = useSettingsStore(state => state.setThemeMode);
  const fontScale = useSettingsStore(state => state.fontScale);
  const humanReview = useSettingsStore(state => state.humanReview);
  const setHumanReview = useSettingsStore(state => state.setHumanReview);
  useLayoutEffect(() => {
    const resolve = () => themeMode === 'system'
      ? window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
      : themeMode;
    const apply = () => {
      const next = resolve();
      document.documentElement.dataset.theme = next;
      document.documentElement.dataset.themeMode = themeMode;
      document.documentElement.style.setProperty('--ui-font-scale', String(fontScale));
      try { localStorage.setItem('hisar-theme', next); } catch { /* Private storage may be unavailable. */ }
    };
    apply();
    if (themeMode !== 'system') return undefined;
    const media = window.matchMedia('(prefers-color-scheme: light)');
    media.addEventListener('change', apply);
    return () => media.removeEventListener('change', apply);
  }, [fontScale, themeMode]);
  const [activeUtilityPanel, setActiveUtilityPanel] =
    useState<UtilityPanel>(null);
  const settingsOpen = activeUtilityPanel === 'settings';
  const helpOpen = activeUtilityPanel === 'help';
  const setSettingsOpen = useCallback((value: SetStateAction<boolean>) => {
    setActiveUtilityPanel(current => {
      const nextOpen = typeof value === 'function'
        ? value(current === 'settings')
        : value;
      return nextOpen ? 'settings' : current === 'settings' ? null : current;
    });
  }, []);
  const setHelpOpen = useCallback((value: SetStateAction<boolean>) => {
    setActiveUtilityPanel(current => {
      const nextOpen = typeof value === 'function'
        ? value(current === 'help')
        : value;
      return nextOpen ? 'help' : current === 'help' ? null : current;
    });
  }, []);
  const [tutorialRunId, setTutorialRunId] = useState(0);
  const [tutorialActive, setTutorialActive] = useState(false);
  const [tutorialOverlayPanel, setTutorialOverlayPanel] =
    useState<MapOverlayPanel | undefined>(undefined);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [bottomOpen, setBottomOpen] = useState(false);
  const [filters, setFilters] =
    useState<MapFilterState>(initialMapFilters);

  const [togglingReview, setTogglingReview] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const notificationsRef = useRef<HTMLDivElement>(null);
  const [trackSearch, setTrackSearch] = useState('');
  const [trackSearchOpen, setTrackSearchOpen] = useState(false);
  const detailWidth = usePanelLayoutStore(state => state.detailWidth);
  const setDetailWidth = usePanelLayoutStore(state => state.setDetailWidth);
  const timelineCompact = useTimelineStore(state => state.compact);
  const bottomControlsRef = useRef<HTMLDivElement>(null);
  const [bottomControlsPosition, setBottomControlsPosition] = useState<{ x: number; y: number } | null>(() => loadStoredPosition(bottomControlGroupStorageKey));
  const bottomControlsPositionRef = useRef(bottomControlsPosition);

  useEffect(() => {
    bottomControlsPositionRef.current = bottomControlsPosition;
  }, [bottomControlsPosition]);

  const selectedTrackId = useTrackingStore(
    state => state.selectedTrackId,
  );

  const inspectorOpen = useWorkspaceStore(
    state => state.inspectorOpen,
  );

  const watchTrackIds = useWatchlistStore(
    state => state.trackIds,
  );

  const notifications = useWatchlistStore(
    state => state.notifications,
  );

  const unreadNotifications = notifications.filter(
    item => !item.read,
  ).length;

  const startDetailResize = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const startWidth = detailWidth;
    const move = (moveEvent: PointerEvent) => setDetailWidth(startWidth + startX - moveEvent.clientX);
    const stop = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', stop);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', stop, { once: true });
  };

  const startBottomControlsDrag = (event: ReactPointerEvent<HTMLButtonElement>) => {
    const element = bottomControlsRef.current;
    const parent = element?.parentElement;
    if (!element || !parent) return;
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    const parentRect = parent.getBoundingClientRect();
    const rect = element.getBoundingClientRect();
    const startX = event.clientX;
    const startY = event.clientY;
    const initial = bottomControlsPosition ?? { x: rect.left - parentRect.left, y: rect.top - parentRect.top };
    const clamp = (x: number, y: number) => ({
      x: Math.min(Math.max(8, x), Math.max(8, parentRect.width - rect.width - 8)),
      y: Math.min(Math.max(8, y), Math.max(8, parentRect.height - rect.height - 8)),
    });
    const move = (moveEvent: PointerEvent) => {
      const next = clamp(initial.x + moveEvent.clientX - startX, initial.y + moveEvent.clientY - startY);
      bottomControlsPositionRef.current = next;
      setBottomControlsPosition(next);
    };
    const stop = () => {
      const finalPosition = bottomControlsPositionRef.current;
      if (finalPosition) {
        try { localStorage.setItem(bottomControlGroupStorageKey, JSON.stringify(finalPosition)); } catch { /* localStorage may be unavailable. */ }
      }
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', stop);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', stop, { once: true });
  };

  const playbackTime = usePlaybackStore(state =>
    Math.floor(state.currentTime),
  );

  const rawData = analysis.data;
  const data = useMemo(() => rawData ? {
    ...rawData,
    human_review: humanReview,
    summary: { ...rawData.summary, human_review: humanReview },
    reviews: { ...rawData.reviews, human_review: humanReview },
  } : null, [humanReview, rawData]);
  useVoiceAlerts(data);

  useEffect(() => {
    if (!data) return undefined;
    const keepReachableIfFullyOutside = () => {
      const position = bottomControlsPositionRef.current;
      const element = bottomControlsRef.current;
      const parent = element?.parentElement;
      if (!position || !element || !parent) return;
      const parentRect = parent.getBoundingClientRect();
      const rect = element.getBoundingClientRect();
      const visibleEdge = 24;
      let x = position.x;
      let y = position.y;

      if (rect.right < parentRect.left + visibleEdge) x = 8;
      else if (rect.left > parentRect.right - visibleEdge) x = Math.max(8, parentRect.width - rect.width - 8);

      if (rect.bottom < parentRect.top + visibleEdge) y = 8;
      else if (rect.top > parentRect.bottom - visibleEdge) y = Math.max(8, parentRect.height - rect.height - 8);

      if (x === position.x && y === position.y) return;
      const next = { x, y };
      bottomControlsPositionRef.current = next;
      setBottomControlsPosition(next);
    };

    window.addEventListener('resize', keepReachableIfFullyOutside);
    const observer = typeof ResizeObserver === 'undefined'
      ? null
      : new ResizeObserver(keepReachableIfFullyOutside);
    if (bottomControlsRef.current) observer?.observe(bottomControlsRef.current);
    return () => {
      window.removeEventListener('resize', keepReachableIfFullyOutside);
      observer?.disconnect();
    };
  }, [data]);

  const activeEntities = useMemo(
    () => activeTrackEntities(data?.entities ?? []),
    [data],
  );

  const visibleTrackIds = useMemo(
    () =>
      new Set(
        activeEntities
          .filter(entity =>
            entityMatchesMapFilters(entity, filters),
          )
          .map(entity => entity.track_id),
      ),
    [activeEntities, filters],
  );

  const trackSearchResults = useMemo(() => {
    const query = trackSearch.trim().toLocaleLowerCase('tr-TR');
    if (!data || !query) return [];
    return activeEntities
      .filter(entity => [
        entity.track_id,
        entity.vehicle?.vehicle_id ?? '',
        entity.vehicle_class,
        entity.zone ?? '',
        entity.scenario ? formatScenario(entity.scenario) : '',
      ].some(value => value.toLocaleLowerCase('tr-TR').includes(query)))
      .slice(0, 8);
  }, [activeEntities, data, trackSearch]);

  const selectedEntity =
    activeEntities.find(
      entity => entity.track_id === selectedTrackId,
    ) ?? null;

  const highCritical = data
    ? data.alerts.filter(
        alert =>
          alert.risk_level === 'HIGH' ||
          alert.risk_level === 'CRITICAL',
      ).length
    : 0;

  const dataRef = useRef<AnalysisData | null>(null);

  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  /**
   * Haritadaki aracı seçer.
   * Araç mevcut playback anında görünmüyorsa gözlem anına gider.
   */
  const selectTrack = useCallback((trackId: string) => {
    setBottomOpen(false);

    const entity = dataRef.current?.entities.find(
      item => item.track_id === trackId,
    );

    if (!entity || !isActiveTrackEntity(entity)) return;

    const target =
      entity?.observed_at ?? entity?.first_seen;

    if (
      entity &&
      target &&
      !positionAtTime(
        entity,
        usePlaybackStore.getState().currentTime,
      )
    ) {
      usePlaybackStore
        .getState()
        .seek(clockSeconds(target));
    }

    useTrackingStore.getState().selectTrack(trackId);
    useTrackingStore.getState().requestView('vehicle');
  }, []);

  const chooseSearchResult = useCallback((trackId: string) => {
    selectTrack(trackId);
    setTrackSearchOpen(false);
    setTrackSearch('');
  }, [selectTrack]);

  const toggleHumanReview = async () => {
    if (!rawData) return;

    setTogglingReview(true);
    setActionError(null);
    const next = !humanReview;
    setHumanReview(next);

    try {
      await api.setHumanReview(next);
      analysis.reload();
    } catch (cause) {
      setHumanReview(rawData.human_review);
      setActionError(
        cause instanceof Error
          ? cause.message
          : 'Ayar değiştirilemedi.',
      );
    } finally {
      setTogglingReview(false);
    }
  };

  const openPdfReport = () => {
    const path = demoReportEnabled()
      ? '/api/threat-report/demo-download'
      : '/api/threat-report/download?min_risk=YUKSEK';
    window.open(
      apiUrl(path),
      '_blank',
      'noopener,noreferrer',
    );
  };

  useEffect(() => {
    if (rawData) setHumanReview(rawData.human_review);
  }, [rawData, setHumanReview]);

  useEffect(() => {
    if (
      selectedTrackId &&
      data &&
      !data.entities.some(
        entity =>
          entity.track_id === selectedTrackId &&
          isActiveTrackEntity(entity),
      )
    ) {
      useTrackingStore.getState().selectTrack(null);
    }
  }, [data, selectedTrackId]);

  useEffect(() => {
    if (!data) return;

    useWatchlistStore
      .getState()
      .applyAnalysis(activeEntities, data.generated_at);
  }, [activeEntities, data, watchTrackIds]);

  useEffect(() => {
    const clearSelection = (event: KeyboardEvent) => {
      if (
        event.key === 'Escape' &&
        !notificationsOpen &&
        !event.defaultPrevented
      ) {
        useTrackingStore.getState().selectTrack(null);
      }
    };

    window.addEventListener('keydown', clearSelection);

    return () =>
      window.removeEventListener(
        'keydown',
        clearSelection,
      );
  }, []);

  useEffect(() => {
    if (!notificationsOpen) return undefined;

    const closeOnOutside = (event: PointerEvent) => {
      const target = event.target;
      if (target instanceof Node && notificationsRef.current?.contains(target)) return;
      setNotificationsOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !event.defaultPrevented) setNotificationsOpen(false);
    };

    document.addEventListener('pointerdown', closeOnOutside);
    document.addEventListener('keydown', closeOnEscape);

    return () => {
      document.removeEventListener('pointerdown', closeOnOutside);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [notificationsOpen]);

  useEffect(() => startPlaybackClock(), []);

  const startTutorial = useCallback(() => {
    setSettingsOpen(false);
    setHelpOpen(false);
    setNotificationsOpen(false);
    setTutorialRunId(current => current + 1);
  }, []);

  // Voice commands read the latest render's state and callbacks through this ref (see services/uiActions.ts).
  const voiceControllerRef = useRef<UiController | null>(null);
  const voiceController = useCallback(() => voiceControllerRef.current!, []);

  if (!data) {
    return (
      <div className="map-first-shell">
        <header className="map-first-topbar">
          <div className="map-first-brand hisar-brand">
            <img src={hisarLogo} alt="HİSAR" />
            <span>
              HİSAR
              <small>OPERATIONS CENTER</small>
            </span>
          </div>
          <button
            className="settings-trigger"
            type="button"
            data-tour="settings"
            aria-label="Ayarları aç"
            aria-expanded={settingsOpen}
            onClick={() => setSettingsOpen(open => !open)}
          >
            <Settings size={16} />
          </button>
          <button
            className="help-trigger"
            type="button"
            data-tour="help"
            aria-label="Yardım"
            title="Yardım"
            aria-expanded={helpOpen}
            onClick={() => setHelpOpen(open => !open)}
          >
            <HelpCircle size={16} />
          </button>
        </header>
        <SettingsPanel
          open={settingsOpen}
          onClose={() => setSettingsOpen(false)}
          togglingReview={togglingReview}
          humanReviewDisabled
          onToggleHumanReview={() => void toggleHumanReview()}
          summary={null}
        />
        <HelpPanel open={helpOpen} onClose={() => setHelpOpen(false)} onStartTutorial={startTutorial} />

        <InitialState
          error={
            analysis.status === 'error'
              ? analysis.error
              : null
          }
          retry={analysis.reload}
        />
      </div>
    );
  }

  voiceControllerRef.current = {
    analysis: data,
    filters,
    setFilters,
    selectTrack,
    sidebarOpen, setSidebarOpen,
    bottomOpen, setBottomOpen,
    notificationsOpen, setNotificationsOpen,
    settingsOpen, setSettingsOpen,
    helpOpen, setHelpOpen,
    graphOpen, setGraphOpen,
    showNormalRegions, setShowNormalRegions,
    selectedFrameId: selectedEntity?.frame_id ?? null,
    startTutorial,
    openPdfReport,
    reload: analysis.reload,
    setHumanReview: async enabled => { if (enabled !== humanReview) await toggleHumanReview(); },
  };

  const error =
    analysis.status === 'error'
      ? `Yenileme başarısız: ${analysis.error}`
      : actionError;

  return (
    <div className="map-first-shell">
      <header className="map-first-topbar">
        <div className="map-first-brand hisar-brand">
          <img src={hisarLogo} alt="HİSAR" />

          <span>
            HİSAR
            <small>OPERATIONS CENTER</small>
          </span>
        </div>

        <div className="map-top-stat timestamp">
          <Clock3 size={13} />

          <span>
            <small>SON ANALİZ</small>
            <strong>
              {formatTimestamp(data.generated_at)}
            </strong>
          </span>
        </div>

        <div className="map-top-stat">
          <span>
            <small>İZ</small>
            <strong>{data.summary.tracks}</strong>
          </span>
        </div>

        <div
          className={`map-top-stat risk-total ${
            highCritical ? 'active' : ''
          }`}
        >
          <AlertTriangle size={13} />

          <span>
            <small>YÜKSEK / KRİTİK</small>
            <strong>{highCritical}</strong>
          </span>
        </div>

        <div
          className={`map-top-stat pending-total ${
            data.summary.pending_reviews
              ? 'active'
              : ''
          }`}
        >
          <UserCheck size={13} />

          <span>
            <small>ONAY BEKLEYEN</small>
            <strong>
              {data.summary.pending_reviews}
            </strong>
          </span>
        </div>

        <div className="map-top-search" role="search">
          <Search size={13} />
          <input
            aria-label="İz ara"
            placeholder="İz ara"
            value={trackSearch}
            onChange={event => {
              setTrackSearch(event.target.value);
              setTrackSearchOpen(true);
            }}
            onFocus={() => setTrackSearchOpen(true)}
            onBlur={() => window.setTimeout(() => setTrackSearchOpen(false), 120)}
            onKeyDown={event => {
              if (event.key === 'Enter' && trackSearchResults[0]) {
                event.preventDefault();
                chooseSearchResult(trackSearchResults[0].track_id);
              }
              if (event.key === 'Escape') {
                setTrackSearchOpen(false);
                event.currentTarget.blur();
              }
            }}
          />
          <div className="watch-notification-anchor" ref={notificationsRef}>
            <button
              className={`watch-notification-trigger ${
                unreadNotifications ? 'active' : ''
              }`}
              data-tour="notifications"
              aria-expanded={notificationsOpen}
              aria-label={`İzleme listesi bildirimleri${
                unreadNotifications
                  ? `, ${unreadNotifications} okunmamış`
                  : ''
              }`}
              onClick={() =>
                setNotificationsOpen(open => !open)
              }
              type="button"
            >
              <Bell size={14} />

              {unreadNotifications > 0 && (
                <b>{unreadNotifications}</b>
              )}
            </button>

            {notificationsOpen && (
              <div className="watch-notification-panel">
                <header>
                  <span>
                    <Bell size={13} />
                    Bildirimler
                  </span>

                  <button
                    disabled={!unreadNotifications}
                    onClick={() =>
                      useWatchlistStore
                        .getState()
                        .markAllRead()
                    }
                  >
                    <CheckCheck size={12} />
                    Tümünü okundu işaretle
                  </button>
                </header>

                <div>
                  {notifications.length ? (
                    notifications
                      .slice(0, 20)
                      .map(item => (
                        <button
                          key={item.id}
                          className={`${
                            item.read ? 'read' : ''
                          } severity-${item.severity}`}
                          onClick={() => {
                            useWatchlistStore
                              .getState()
                              .markRead(item.id);

                            selectTrack(item.trackId);
                            setNotificationsOpen(false);
                          }}
                        >
                          <span>
                            <strong>
                              {item.trackId}
                            </strong>

                            <small>
                              {item.type} ·{' '}
                              {formatTimestamp(
                                item.at,
                              )}
                            </small>
                          </span>

                          <p>{item.message}</p>
                        </button>
                      ))
                  ) : (
                    <p>
                      Henüz watchlist bildirimi yok.
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
          {trackSearchOpen && trackSearch.trim() && (
            <div className="map-top-search-results" role="listbox">
              {trackSearchResults.length ? trackSearchResults.map(entity => (
                <button
                  key={entity.track_id}
                  type="button"
                  role="option"
                  onMouseDown={event => event.preventDefault()}
                  onClick={() => chooseSearchResult(entity.track_id)}
                >
                  <strong>{entity.track_id}</strong>
                  <span>{formatVehicleClass(entity.vehicle_class)} · {entity.zone ?? 'Bölge yok'}</span>
                  <small>{entity.scenario ? formatScenario(entity.scenario) : 'Senaryo yok'}</small>
                </button>
              )) : <p>Sonuç yok.</p>}
            </div>
          )}
        </div>

        <VoiceCommandButton controller={voiceController} />

        <button
          className="pdf-report-download"
          onClick={openPdfReport}
          aria-label="PDF tehdit raporunu yeni sekmede aç"
        >
          <FileDown size={14} />
          <span>PDF Raporu Al</span>
        </button>

        <button
          className="settings-trigger"
          type="button"
          data-tour="settings"
          aria-label="Ayarları aç"
          aria-expanded={settingsOpen}
          onClick={() => setSettingsOpen(open => !open)}
        >
          <Settings size={15} />
        </button>

        <button
          className="help-trigger"
          type="button"
          data-tour="help"
          aria-label="Yardım"
          title="Yardım"
          aria-expanded={helpOpen}
          onClick={() => setHelpOpen(open => !open)}
        >
          <HelpCircle size={15} />
        </button>

        <button
          className="map-refresh"
          onClick={analysis.reload}
          disabled={analysis.status === 'loading'}
          aria-label="Analiz verisini yenile"
        >
          <RefreshCw
            size={14}
            className={
              analysis.status === 'loading'
                ? 'spinning'
                : ''
            }
          />

          <span>
            {analysis.status === 'loading'
              ? 'Yenileniyor…'
              : 'Yenile'}
          </span>
        </button>
      </header>

      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        togglingReview={togglingReview}
        humanReviewDisabled={!rawData}
        onToggleHumanReview={() => void toggleHumanReview()}
        summary={data.summary}
      />
      <HelpPanel open={helpOpen} onClose={() => setHelpOpen(false)} onStartTutorial={startTutorial} />

      <AppTutorial
        ready={Boolean(data)}
        runId={tutorialRunId}
        bottomOpen={bottomOpen}
        helpOpen={helpOpen}
        notificationsOpen={notificationsOpen}
        settingsOpen={settingsOpen}
        sidebarOpen={sidebarOpen}
        timelineCompact={timelineCompact}
        setBottomOpen={setBottomOpen}
        setHelpOpen={setHelpOpen}
        setNotificationsOpen={setNotificationsOpen}
        setSettingsOpen={setSettingsOpen}
        setSidebarOpen={setSidebarOpen}
        setTimelineCompact={useTimelineStore.getState().setCompact}
        setTourActive={setTutorialActive}
        setTourOverlayPanel={setTutorialOverlayPanel}
      />

      <main
        className={`map-first-workspace ${
          sidebarOpen ? 'sidebar-open' : ''
        } ${
          selectedEntity && inspectorOpen
            ? 'detail-open'
            : ''
        } ${timelineCompact ? 'timeline-compact' : 'timeline-full'}`}
        style={{ '--map-detail-width': `${detailWidth}px` } as CSSProperties}
      >
        <OperationsMap
          analysis={data}
          onSelectTrack={selectTrack}
          visibleTrackIds={visibleTrackIds}
          graphRegions={graphRegions}
          selectedRegionId={selectedRegionId}
          onSelectRegion={selectRegion}
        />

        <MapSidebar
          graphPanel={<GraphAnalysisPanel showNormal={showNormalRegions} requestWindow={graphWindow} enabled={graphOpen} onToggle={() => setGraphOpen(value => !value)}
            data={graph.data} loading={graph.loading} error={graph.error} reload={graph.reload}
            onWindow={window => { setSelectedRegionId(null); setGraphWindow(window); }}
            selected={selectedRegion} onSelect={regionId => {
              selectRegion(regionId);
              const region = graph.data?.regions.find(item => item.region_id === regionId);
              if (region) useTrackingStore.getState().requestView('coordinate', undefined, [region.location.lon, region.location.lat]);
            }} reports={data.reports} />}
          analysis={data}
          filters={filters}
          setFilters={setFilters}
          open={sidebarOpen}
          setOpen={setSidebarOpen}
          onSelectTrack={selectTrack}
        />

        <MapOverlays
          analysis={data}
          filters={filters}
          setFilters={setFilters}
          onSelectTrack={selectTrack}
          onChanged={analysis.reload}
          selectedFrameId={
            selectedEntity?.frame_id ?? null
          }
          tourActive={tutorialActive}
          tourPanel={tutorialOverlayPanel}
        />

        <div
          ref={bottomControlsRef}
          data-tour="track-list"
          className={`bottom-control-group ${bottomControlsPosition ? 'dragged' : ''}`}
          style={bottomControlsPosition ? { left: bottomControlsPosition.x, top: bottomControlsPosition.y, right: 'auto', bottom: 'auto' } : undefined}
        >
          <BottomTrackPanel
            analysis={data}
            selectedTrackId={selectedTrackId}
            onSelectTrack={selectTrack}
            open={bottomOpen}
            setOpen={setBottomOpen}
          />

          <Timeline analysis={data} onDragHandlePointerDown={startBottomControlsDrag} />
        </div>

        <VoiceAlertCard onSelectTrack={selectTrack} />

        {selectedEntity && inspectorOpen && (
          <div
            className="map-detail-backdrop"
            onClick={() =>
              useTrackingStore
                .getState()
                .selectTrack(null)
            }
            aria-hidden="true"
          />
        )}

        {selectedEntity && inspectorOpen && (
          <aside
            className="map-detail-drawer"
            aria-label={`${selectedEntity.track_id} araç detay paneli`}
            style={{ width: `min(${detailWidth}px, 100vw)` }}
          >
            <div className="panel-resize-handle left-edge" role="separator" aria-orientation="vertical" aria-label="Detay paneli genişliği" onPointerDown={startDetailResize} />
            <TrackDetail
              analysis={data}
              entity={selectedEntity}
              playbackTime={playbackTime}
              onChanged={analysis.reload}
            />
          </aside>
        )}

        {analysis.status === 'empty' && (
          <div
            className="map-empty-notice"
            role="status"
          >
            <CircleAlert size={14} />

            <span>
              API araç gözlemi döndürmedi. Üs ve
              bölge bilgileri gösterilmeye devam
              ediyor.
            </span>
          </div>
        )}

        {error && (
          <div
            className="map-refresh-error"
            role="alert"
          >
            <CircleAlert size={14} />

            <span>{error}</span>

            <button
              onClick={() => {
                setActionError(null);
                analysis.reload();
              }}
            >
              Tekrar dene
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

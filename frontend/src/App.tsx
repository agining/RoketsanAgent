import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Bell,
  BrainCircuit,
  CheckCheck,
  CircleAlert,
  Clock3,
  Crosshair,
  FileDown,
  LoaderCircle,
  RefreshCw,
  Search,
  UserCheck,
  Volume2,
  VolumeX,
} from 'lucide-react';

import { OperationsMap } from './components/map/OperationsMap';
import { MapOverlays } from './components/map/MapOverlays';
import {
  MapSidebar,
  entityMatchesMapFilters,
  initialMapFilters,
  type MapFilterState,
} from './components/map/MapSidebar';
import { BottomTrackPanel } from './components/tracks/BottomTrackPanel';
import { TrackDetail } from './components/tracks/TrackDetail';
import { Timeline } from './components/Timeline';
import { Button } from './components/ui/button';
import { VoiceAlertCard } from './components/voice/VoiceAlertCard';

import { useAnalysis } from './hooks/useAnalysis';
import { useVoiceAlerts } from './hooks/useVoiceAlerts';

import { api, API_BASE_URL, apiUrl } from './services/api';
import { clockSeconds, positionAtTime } from './services/analysis-playback';
import { startPlaybackClock } from './services/playback-clock';

import type { AnalysisData } from './types/analysis';

import { usePlaybackStore } from './store/playback';
import { useTrackingStore } from './store/tracking';
import { useVoiceAlertsStore } from './store/voiceAlerts';
import { useWatchlistStore } from './store/watchlist';
import { useWorkspaceStore } from './store/workspace';

import hisarLogo from '@/assets/hisar-logo.png';

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

export default function App() {
  const analysis = useAnalysis();

  const [sidebarOpen, setSidebarOpen] = useState(
    () => typeof window !== 'undefined' && window.innerWidth >= 900,
  );
  const [bottomOpen, setBottomOpen] = useState(false);
  const [filters, setFilters] =
    useState<MapFilterState>(initialMapFilters);

  const [togglingReview, setTogglingReview] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notificationsOpen, setNotificationsOpen] = useState(false);

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

  const playbackTime = usePlaybackStore(state =>
    Math.floor(state.currentTime),
  );

  const data = analysis.data;
  useVoiceAlerts(data);

  const voiceAlertsEnabled = useVoiceAlertsStore(
    state => state.enabled,
  );

  const voiceAlertsSpeaking = useVoiceAlertsStore(
    state => state.isSpeaking,
  );

  const toggleVoiceAlerts = useVoiceAlertsStore(
    state => state.toggleEnabled,
  );

  const visibleTrackIds = useMemo(
    () =>
      new Set(
        data?.entities
          .filter(entity =>
            entityMatchesMapFilters(entity, filters),
          )
          .map(entity => entity.track_id) ?? [],
      ),
    [data, filters],
  );

  const selectedEntity =
    data?.entities.find(
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

  const toggleHumanReview = async () => {
    if (!data) return;

    setTogglingReview(true);
    setActionError(null);

    try {
      await api.setHumanReview(!data.human_review);
      analysis.reload();
    } catch (cause) {
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
    window.open(
      apiUrl(
        '/api/threat-report/download?min_risk=YUKSEK',
      ),
      '_blank',
      'noopener,noreferrer',
    );
  };

  useEffect(() => {
    if (
      selectedTrackId &&
      data &&
      !data.entities.some(
        entity => entity.track_id === selectedTrackId,
      )
    ) {
      useTrackingStore.getState().selectTrack(null);
    }
  }, [data, selectedTrackId]);

  useEffect(() => {
    if (!data) return;

    useWatchlistStore
      .getState()
      .applyAnalysis(data.entities, data.generated_at);
  }, [data, watchTrackIds]);

  useEffect(() => {
    const clearSelection = (event: KeyboardEvent) => {
      if (
        event.key === 'Escape' &&
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

  useEffect(() => startPlaybackClock(), []);

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
        </header>

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

        <button
          className={`human-review-toggle ${
            data.human_review ? 'on' : ''
          }`}
          role="switch"
          aria-checked={data.human_review}
          disabled={togglingReview}
          onClick={() => void toggleHumanReview()}
          title="Açıkken motor ile LLM'in ayrıştığı kararlar analist onayına düşer"
        >
          {togglingReview ? (
            <LoaderCircle
              size={13}
              className="spinning"
            />
          ) : (
            <UserCheck size={13} />
          )}

          <span>Son söz insanda</span>
          <i />
        </button>

        <span
          className={`llm-badge ${
            data.summary.llm_enabled ? 'on' : ''
          }`}
          title={
            data.summary.llm_enabled
              ? `Model: ${data.summary.model ?? '—'}`
              : "API'de OPENAI_API_KEY tanımlı değil"
          }
        >
          <BrainCircuit size={13} />
          <span>
            {data.summary.llm_enabled
              ? 'LLM açık'
              : 'LLM kapalı'}
          </span>
        </span>

        <button
          className={`voice-alert-toggle ${
            voiceAlertsEnabled ? 'on' : ''
          } ${voiceAlertsSpeaking ? 'speaking' : ''}`}
          role="switch"
          aria-checked={voiceAlertsEnabled}
          onClick={toggleVoiceAlerts}
          title={
            voiceAlertsEnabled
              ? 'Sesli tehdit bildirimlerini kapat'
              : 'Sesli tehdit bildirimlerini aç'
          }
        >
          {voiceAlertsEnabled ? (
            <Volume2 size={13} />
          ) : (
            <VolumeX size={13} />
          )}

          <span>
            {voiceAlertsEnabled ? 'Ses açık' : 'Ses kapalı'}
          </span>
        </button>

        <div className="watch-notification-anchor">
          <button
            className={`watch-notification-trigger ${
              unreadNotifications ? 'active' : ''
            }`}
            aria-expanded={notificationsOpen}
            aria-label={`İzleme listesi bildirimleri${
              unreadNotifications
                ? `, ${unreadNotifications} okunmamış`
                : ''
            }`}
            onClick={() =>
              setNotificationsOpen(open => !open)
            }
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

        <button
          className="map-top-search"
          onClick={() => {
            setSidebarOpen(true);

            requestAnimationFrame(() =>
              document
                .querySelector<HTMLInputElement>(
                  '[aria-label="Harita araç kayıtlarında ara"]',
                )
                ?.focus(),
            );
          }}
        >
          <Search size={13} />
          <span>İz ara</span>
        </button>

        <button
          className="pdf-report-download"
          onClick={openPdfReport}
          aria-label="PDF tehdit raporunu yeni sekmede aç"
        >
          <FileDown size={14} />
          <span>PDF Raporu Al</span>
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

      <main
        className={`map-first-workspace ${
          sidebarOpen ? 'sidebar-open' : ''
        } ${
          selectedEntity && inspectorOpen
            ? 'detail-open'
            : ''
        }`}
      >
        <OperationsMap
          analysis={data}
          onSelectTrack={selectTrack}
          visibleTrackIds={visibleTrackIds}
        />

        <MapSidebar
          analysis={data}
          filters={filters}
          setFilters={setFilters}
          open={sidebarOpen}
          setOpen={setSidebarOpen}
          onSelectTrack={selectTrack}
        />

        <MapOverlays
          analysis={data}
          onSelectTrack={selectTrack}
          onChanged={analysis.reload}
          selectedFrameId={
            selectedEntity?.frame_id ?? null
          }
        />

        <BottomTrackPanel
          analysis={data}
          selectedTrackId={selectedTrackId}
          onSelectTrack={selectTrack}
          open={bottomOpen}
          setOpen={setBottomOpen}
        />

        <Timeline analysis={data} />

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
          >
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

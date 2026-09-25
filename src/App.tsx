import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CircleAlert, Clock3, Crosshair, RefreshCw, Search } from 'lucide-react';
import { OperationsMap } from './components/map/OperationsMap';
import { MapOverlays } from './components/map/MapOverlays';
import { MapSidebar, entityMatchesMapFilters, initialMapFilters, type MapFilterState } from './components/map/MapSidebar';
import { BottomTrackPanel } from './components/tracks/BottomTrackPanel';
import { TrackDetail } from './components/tracks/TrackDetail';
import { Timeline } from './components/Timeline';
import { Button } from './components/ui/button';
import { useAnalysis } from './hooks/useAnalysis';
import { startPlaybackClock } from './services/playback-clock';
import { usePlaybackStore } from './store/playback';
import { useTrackingStore } from './store/tracking';
import { useWorkspaceStore } from './store/workspace';

function formatTimestamp(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

function InitialState({ error, retry }: { error: string | null; retry: () => void }) {
  return <div className={`map-first-initial ${error ? 'error' : ''}`} role={error ? 'alert' : 'status'}>{error ? <CircleAlert size={30} /> : <Crosshair size={30} />}<h1>{error ? 'Analiz verisi alınamadı' : 'Operasyon haritası yükleniyor'}</h1><p>{error ?? 'Son backend analizi alınıp doğrulanıyor.'}</p>{error ? <Button variant="outline" onClick={retry}><RefreshCw size={15} />Tekrar Dene</Button> : <div className="map-loading-line"><i /></div>}</div>;
}

export default function App() {
  const analysis = useAnalysis();
  const [sidebarOpen, setSidebarOpen] = useState(() => typeof window !== 'undefined' && window.innerWidth >= 900);
  const [bottomOpen, setBottomOpen] = useState(false);
  const [filters, setFilters] = useState<MapFilterState>(initialMapFilters);
  const selectedTrackId = useTrackingStore(state => state.selectedTrackId);
  const inspectorOpen = useWorkspaceStore(state => state.inspectorOpen);
  const playbackTime = usePlaybackStore(state => Math.floor(state.currentTime));
  const visibleTrackIds = useMemo(() => new Set(analysis.data?.entities.filter(entity => entityMatchesMapFilters(entity, filters)).map(entity => entity.track_id) ?? []), [analysis.data, filters]);
  const selectedEntity = analysis.data?.entities.find(entity => entity.track_id === selectedTrackId) ?? null;
  const highCritical = analysis.data ? analysis.data.operation_summary.risk_counts.HIGH + analysis.data.operation_summary.risk_counts.CRITICAL : 0;
  const selectTrack = useCallback((trackId: string) => {
    setBottomOpen(false); useTrackingStore.getState().selectTrack(trackId); useTrackingStore.getState().requestView('vehicle');
  }, []);

  useEffect(() => {
    if (selectedTrackId && analysis.data && !analysis.data.entities.some(entity => entity.track_id === selectedTrackId)) useTrackingStore.getState().selectTrack(null);
  }, [analysis.data, selectedTrackId]);
  useEffect(() => {
    const clearSelection = (event: KeyboardEvent) => { if (event.key === 'Escape' && !event.defaultPrevented) useTrackingStore.getState().selectTrack(null); };
    window.addEventListener('keydown', clearSelection); return () => window.removeEventListener('keydown', clearSelection);
  }, []);
  useEffect(() => startPlaybackClock(), []);

  if (!analysis.data) return <div className="map-first-shell"><header className="map-first-topbar"><div className="map-first-brand"><Crosshair size={18} /><span>ATLAS<small>OPERATIONS CENTER</small></span></div></header><InitialState error={analysis.status === 'error' ? analysis.error : null} retry={analysis.reload} /></div>;

  return <div className="map-first-shell">
    <header className="map-first-topbar">
      <div className="map-first-brand"><Crosshair size={18} /><span>ATLAS<small>OPERATIONS CENTER</small></span></div>
      <div className="map-top-stat timestamp"><Clock3 size={13} /><span><small>SON ANALİZ</small><strong>{formatTimestamp(analysis.data.generated_at)}</strong></span></div>
      <div className="map-top-stat"><span><small>TAKİPTE</small><strong>{analysis.data.operation_summary.tracked_entity_count}</strong></span></div>
      <div className={`map-top-stat risk-total ${highCritical ? 'active' : ''}`}><AlertTriangle size={13} /><span><small>YÜKSEK / KRİTİK</small><strong>{highCritical}</strong></span></div>
      <button className="map-top-search" onClick={() => { setSidebarOpen(true); requestAnimationFrame(() => document.querySelector<HTMLInputElement>('[aria-label="Harita araç kayıtlarında ara"]')?.focus()); }}><Search size={13} /><span>Araç ara</span></button>
      <button className="map-refresh" onClick={analysis.reload} disabled={analysis.status === 'loading'} aria-label="Analiz verisini yenile"><RefreshCw size={14} className={analysis.status === 'loading' ? 'spinning' : ''} /><span>{analysis.status === 'loading' ? 'Yenileniyor…' : 'Yenile'}</span></button>
    </header>
    <main className={`map-first-workspace ${sidebarOpen ? 'sidebar-open' : ''} ${selectedEntity && inspectorOpen ? 'detail-open' : ''}`}>
      <OperationsMap analysis={analysis.data} onSelectTrack={selectTrack} visibleTrackIds={visibleTrackIds} />
      <MapSidebar analysis={analysis.data} filters={filters} setFilters={setFilters} open={sidebarOpen} setOpen={setSidebarOpen} onSelectTrack={selectTrack} />
      <MapOverlays analysis={analysis.data} onSelectTrack={selectTrack} />
      <BottomTrackPanel analysis={analysis.data} selectedTrackId={selectedTrackId} onSelectTrack={selectTrack} open={bottomOpen} setOpen={setBottomOpen} />
      <Timeline analysis={analysis.data} />
      {selectedEntity && inspectorOpen && <div className="map-detail-backdrop" onClick={() => useTrackingStore.getState().selectTrack(null)} aria-hidden="true" />}
      {selectedEntity && inspectorOpen && <aside className="map-detail-drawer" aria-label={`${selectedEntity.track_id} araç detay paneli`}><TrackDetail entity={selectedEntity} playbackTime={playbackTime} /></aside>}
      {analysis.status === 'empty' && <div className="map-empty-notice" role="status"><CircleAlert size={14} /><span>Araç gözlemi yok. Üs ve bölge bilgileri gösterilmeye devam ediyor.</span></div>}
      {analysis.status === 'error' && <div className="map-refresh-error" role="alert"><CircleAlert size={14} /><span>Yenileme başarısız: {analysis.error}</span><button onClick={analysis.reload}>Tekrar dene</button></div>}
    </main>
  </div>;
}

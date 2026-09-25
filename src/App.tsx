import { useEffect, useState } from 'react';
import { Crosshair, RefreshCw, TerminalSquare, CircleAlert } from 'lucide-react';
import { OperationsMap } from './components/map/OperationsMap';
import { Button } from './components/ui/button';
import { loadTrackingData } from './services/tracking';
import { OperationsSidebar } from './components/sidebar/OperationsSidebar';
import { Timeline } from './components/Timeline';
import { VehicleDetails } from './components/VehicleDetails';
import { usePlaybackStore } from './store/playback';
import { playbackBounds } from './services/playback';
import { startPlaybackClock } from './services/playback-clock';
import { ResizablePanel } from './components/layout/ResizablePanel';
import { CommandPalette } from './components/CommandPalette';
import { WorkspaceStatus } from './components/WorkspaceStatus';
import { useWorkspaceStore } from './store/workspace';
import { useTrackingStore } from './store/tracking';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import type { TrackingData } from './types/tracking';
export default function App() {
  const [data, setData] = useState<TrackingData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const sidebarOpen = useTrackingStore(state => state.sidebarOpen);
  const inspectorOpen = useWorkspaceStore(state => state.inspectorOpen);
  useKeyboardShortcuts();
  useEffect(() => startPlaybackClock(), []);
  useEffect(() => {
    const controller = new AbortController(); setError(null);
    loadTrackingData(controller.signal).then(loaded => {
      if (controller.signal.aborted) return;
      const { minTime, maxTime } = playbackBounds(loaded.tracks);
      usePlaybackStore.getState().initialize(minTime, maxTime); setData(loaded);
    }).catch(error => { if (!controller.signal.aborted) setError(error instanceof Error ? error.message : 'Unable to load tracking data.'); });
    return () => controller.abort();
  }, [attempt]);
  const pointCount = data?.tracks.reduce((count, track) => count + track.points.length, 0) ?? 0;
  return <div className="app-shell">
    <header className="topbar"><div className="brand"><div className="brand-icon"><Crosshair size={22} /></div><span>ATLAS<span className="brand-sub">OPERATIONS CENTER</span></span></div><div className="topbar-label">Regional monitoring <span>/</span> Track overview</div><Button className="command-trigger" variant="outline" onClick={() => useWorkspaceStore.getState().setCommandOpen(true)}><TerminalSquare size={14} /> Commands <kbd>Ctrl K</kbd></Button><span className="dataset-badge"><span className="status-dot" /> MOCK DATA</span></header>
    <div className="workspace">
      <ResizablePanel side="left" open={sidebarOpen}><OperationsSidebar data={data} /></ResizablePanel>
      <main>
        <div className="page-heading"><div><div className="section-eyebrow">SITUATIONAL OVERVIEW</div><h1>Operations map</h1><p>Vehicle routes and reference locations</p></div><div className="summary"><div><strong>{data?.tracks.length ?? '—'}</strong><span>VEHICLES</span></div><div><strong>{data?.zones.length ?? '—'}</strong><span>ZONES</span></div><div><strong>{pointCount || '—'}</strong><span>GPS POINTS</span></div></div></div>
        <div className="analysis-layout"><div className="map-column"><section className="map-region" aria-label="Operations overview">
          {data ? <OperationsMap data={data} /> : <div className="loading-state" role="status">{error ? <><CircleAlert size={28} /><h2>Unable to prepare the workspace</h2><p>{error}</p><small>Check the source files, then retry loading.</small><Button variant="outline" onClick={() => setAttempt(value => value + 1)}><RefreshCw size={16} /> Retry loading</Button></> : <><div className="loading-symbol"><Crosshair size={28} /></div><h2>Preparing operations map</h2><p>Loading and validating vehicle tracks and reference locations…</p><div className="loading-bars"><i /><i /><i /></div></>}</div>}
        </section>
        {data && <><WorkspaceStatus data={data} /><Timeline /></>}</div><ResizablePanel side="right" open={inspectorOpen}><VehicleDetails tracks={data?.tracks ?? []} base={data?.base} /></ResizablePanel></div>
        <footer className="main-footer"><span>COORDINATES · WGS 84</span><span>5-minute source intervals <span>•</span> Interpolated positions</span></footer>
      </main>
    </div>
    <CommandPalette tracks={data?.tracks ?? []} />
  </div>;
}

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
import { OperationKpis } from './components/OperationKpis';
import { OperationSummary } from './components/OperationSummary';
import { ReportDetailDrawer } from './components/reports/ReportDetailDrawer';
import { useReportStore } from './store/reports';
import { AgentConsole } from './components/agent/AgentConsole';
import { useAgentStore } from './store/agent';
export default function App() {
  const [data, setData] = useState<TrackingData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const sidebarOpen = useTrackingStore(state => state.sidebarOpen);
  const selectedTrackId = useTrackingStore(state => state.selectedTrackId);
  const selectedReportId = useReportStore(state => state.selectedReportId);
  const demoMode = useAgentStore(state => state.demoMode);
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
  return <div className={`app-shell ${demoMode ? 'demo-mode' : ''}`}>
    <header className="topbar"><div className="brand"><div className="brand-icon"><Crosshair size={22} /></div><span>ATLAS<span className="brand-sub">OPERATIONS CENTER</span></span></div><div className="topbar-label">Regional monitoring <span>/</span> Track overview</div><Button className="command-trigger" variant="outline" onClick={() => useWorkspaceStore.getState().setCommandOpen(true)}><TerminalSquare size={14} /> Commands <kbd>Ctrl K</kbd></Button><span className="dataset-badge"><span className="status-dot" /> MOCK DATA</span></header>
    <div className="workspace">
      <ResizablePanel side="left" open={sidebarOpen}><OperationsSidebar data={data} /></ResizablePanel>
      <main>
        <div className="page-heading"><div><div className="section-eyebrow">SITUATIONAL OVERVIEW</div><h1>Operations map</h1><p>Vehicle, risk and zone posture at the current playback time</p></div></div>
        {data && <OperationKpis analysis={data.analysis} />}
        <div className="analysis-layout"><div className="map-column"><section className="map-region" aria-label="Operations overview">
          {data ? <OperationsMap data={data} /> : <div className="loading-state" role="status">{error ? <><CircleAlert size={28} /><h2>Unable to prepare the workspace</h2><p>{error}</p><small>Check the source files, then retry loading.</small><Button variant="outline" onClick={() => setAttempt(value => value + 1)}><RefreshCw size={16} /> Retry loading</Button></> : <><div className="loading-symbol"><Crosshair size={28} /></div><h2>Preparing operations map</h2><p>Loading and validating vehicle tracks and reference locations…</p><div className="loading-bars"><i /><i /><i /></div></>}</div>}
        </section>
        {data && <><WorkspaceStatus data={data} /><Timeline /></>}</div><ResizablePanel side="right" open={inspectorOpen}>{data && selectedReportId ? <ReportDetailDrawer data={data} /> : data && !selectedTrackId ? <OperationSummary data={data} /> : <VehicleDetails tracks={data?.tracks ?? []} base={data?.base} analysis={data?.analysis} />}</ResizablePanel></div>
        <footer className="main-footer"><span>COORDINATES · WGS 84</span><span>5-minute source intervals <span>•</span> Interpolated positions</span></footer>
      </main>
    </div>
    <CommandPalette tracks={data?.tracks ?? []} />
    {data && <AgentConsole data={data} />}
  </div>;
}

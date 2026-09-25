import { useEffect, useState, type RefObject } from 'react';
import { Focus, LocateFixed, Maximize, Minimize, PanelLeft, PanelRight, RotateCcw, TerminalSquare } from 'lucide-react';
import { useWorkspaceStore } from '../../store/workspace';
import { Button } from '../ui/button';
import { useTrackingStore } from '../../store/tracking';
export function MapToolbar({ target }: { target: RefObject<HTMLDivElement | null> }) {
  const inspectorOpen = useWorkspaceStore(state => state.inspectorOpen);
  const state = useTrackingStore(), [fullscreen, setFullscreen] = useState(false), [error, setError] = useState('');
  useEffect(() => { const update = () => setFullscreen(document.fullscreenElement === target.current?.closest('.map-column')); document.addEventListener('fullscreenchange', update); return () => document.removeEventListener('fullscreenchange', update); }, [target]);
  const toggleFullscreen = async () => { try { setError(''); if (document.fullscreenElement) await document.exitFullscreen(); else await target.current?.closest('.map-column')?.requestFullscreen(); } catch { setError('Fullscreen is unavailable in this browser.'); } };
  return <><div className="map-toolbar" role="toolbar" aria-label="Map tools">
    <Button variant="ghost" size="icon" title="Toggle sidebar" aria-label="Toggle sidebar" aria-pressed={state.sidebarOpen} onClick={state.toggleSidebar}><PanelLeft size={16} /></Button>
    <Button variant="ghost" title="Fit all tracks" aria-label="Fit all tracks" onClick={() => state.requestView('all')}><LocateFixed size={15} /><span>Fit all</span></Button>
    <Button variant="ghost" size="icon" title="Fit selected vehicle" aria-label="Fit selected vehicle" disabled={!state.selectedTrackId} onClick={() => state.requestView('route')}><Focus size={16} /></Button>
    <Button variant="ghost" size="icon" title="Reset view" aria-label="Reset map view" onClick={() => state.requestView('reset')}><RotateCcw size={15} /></Button>
    <Button variant="ghost" size="icon" title="Toggle inspector" aria-label="Toggle inspector" aria-pressed={inspectorOpen} onClick={() => useWorkspaceStore.getState().toggleInspector()}><PanelRight size={16} /></Button>
    <Button variant="ghost" size="icon" title="Commands (Ctrl K)" aria-label="Open commands" onClick={() => useWorkspaceStore.getState().setCommandOpen(true)}><TerminalSquare size={15} /></Button>
    <Button variant="ghost" size="icon" title={fullscreen ? 'Exit fullscreen map' : 'Fullscreen map'} aria-label={fullscreen ? 'Exit fullscreen map' : 'Fullscreen map'} disabled={!document.fullscreenEnabled} onClick={toggleFullscreen}>{fullscreen ? <Minimize size={15} /> : <Maximize size={15} />}</Button>
  </div>{error && <div className="toolbar-error" role="status">{error}</div>}</>;
}

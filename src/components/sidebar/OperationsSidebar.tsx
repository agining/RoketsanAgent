import { useEffect, useRef, useState } from 'react';
import { Search, PanelLeftClose } from 'lucide-react';
import { useWorkspaceStore } from '../../store/workspace';
import { activeFilterCount } from '../WorkspaceStatus';
import { useTrackingStore } from '../../store/tracking';
import { usePlaybackStore } from '../../store/playback';
import { filterVehicles } from '../../services/vehicle-filters';
import type { TrackingData } from '../../types/tracking';
import { LayerControls } from './LayerControls';
import { VehicleFilterPanel } from './VehicleFilterPanel';
import { VehicleList } from './VehicleList';
import { ZoneList } from './ZoneList';
import { ReportsPanel } from '../reports/ReportsPanel';
const tabs = ['Vehicles', 'Reports', 'Layers', 'Zones', 'Filters'] as const;
const tabLabels: Record<typeof tabs[number], string> = { Vehicles: 'Araçlar', Reports: 'Raporlar', Layers: 'Katmanlar', Zones: 'Bölgeler', Filters: 'Filtreler' };
export function OperationsSidebar({ data }: { data: TrackingData | null }) {
  const state = useTrackingStore(), time = usePlaybackStore(state => Math.floor(state.currentTime * 10) / 10);
  const [tab, setTab] = useState<typeof tabs[number]>('Vehicles');
  const vehicles = data ? filterVehicles(data, state, time) : [];
  const input = useRef<HTMLInputElement>(null);
  const searchRequest = useWorkspaceStore(state => state.searchRequest);
  useEffect(() => { if (searchRequest) { setTab('Vehicles'); const frame = requestAnimationFrame(() => input.current?.focus()); return () => cancelAnimationFrame(frame); } }, [searchRequest]);
  if (!state.sidebarOpen) return null;
  const active = !!(state.searchQuery.trim() || state.selectedZone || state.activeMovementStates.length || state.minSpeed !== null || state.maxSpeed !== null);
  return <aside className="operations-sidebar" aria-label="Operasyon kontrolleri"><div className="sidebar-title"><span className="section-eyebrow">HARİTA KEŞFİ</span><span>{vehicles.length} / {data?.tracks.length ?? 0}</span><button className="panel-collapse" title="Paneli daralt" aria-label="Paneli daralt" onClick={state.toggleSidebar}><PanelLeftClose size={14} /></button></div>
    <label className="search-box"><Search size={14} /><input ref={input} aria-label="Araç kayıtlarında ara" placeholder="Track kimliği ara…" value={state.searchQuery} onChange={event => { state.setFilters({ searchQuery: event.target.value }); setTab('Vehicles'); }} /></label>
    <div className="sidebar-tabs" role="tablist" aria-label="Harita kontrolleri">{tabs.map(name => <button role="tab" id={`tab-${name}`} aria-selected={tab === name} aria-controls="sidebar-content" key={name} tabIndex={tab === name ? 0 : -1} onKeyDown={event => {
      const index = tabs.indexOf(tab);
      const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : -1;
      if (next < 0) return;
      event.preventDefault(); setTab(tabs[next]); document.getElementById(`tab-${tabs[next]}`)?.focus();
    }} onClick={() => setTab(name)}>{tabLabels[name]}</button>)}</div>
    {active && <div className="active-filter-summary"><span>{activeFilterCount(state)} aktif filtre{state.selectedZone ? ` · ${state.selectedZone}` : ''}</span><button onClick={state.clearFilters}>Temizle</button></div>}
    <div id="sidebar-content" className="sidebar-content" role="tabpanel" aria-labelledby={`tab-${tab}`}>
      {tab === 'Vehicles' && (data ? <VehicleList vehicles={vehicles} /> : <p className="control-note">Takip verisi bekleniyor…</p>)}{tab === 'Reports' && (data ? <ReportsPanel data={data} /> : <p className="control-note">Rapor verisi bekleniyor…</p>)}{tab === 'Layers' && <LayerControls />}{tab === 'Zones' && <ZoneList zones={data?.zones ?? []} />}{tab === 'Filters' && <VehicleFilterPanel zones={data?.zones ?? []} />}
    </div><div className="explorer-footer">Simülasyon zamanında canlı · WGS 84</div></aside>;
}

import { ChevronLeft, ChevronRight, Filter, Layers3, MapPin, Radar, Search } from 'lucide-react';
import type { Dispatch, SetStateAction } from 'react';
import { useMemo } from 'react';
import type { AnalysisData, AnalysisEntity, MovementState, RiskLevel } from '../../types/analysis';
import { useTrackingStore, type MapLayer } from '../../store/tracking';
import { formatAllOption, formatMovementState, formatRiskLevel, formatVehicleClass } from '../../services/formatters';

export interface MapFilterState {
  query: string;
  risk: RiskLevel | 'ALL';
  movement: MovementState | 'ALL';
  zone: string;
  vehicleClass: string;
}

export const initialMapFilters: MapFilterState = { query: '', risk: 'ALL', movement: 'ALL', zone: 'ALL', vehicleClass: 'ALL' };

export function entityMatchesMapFilters(entity: AnalysisEntity, filters: MapFilterState) {
  const query = filters.query.trim().toLocaleLowerCase();
  if (query && ![entity.track_id, entity.vehicle_class.canonical, entity.latest_position.zone].some(value => value.toLocaleLowerCase().includes(query))) return false;
  if (filters.risk !== 'ALL' && (entity.risk.assessment?.risk_level ?? 'UNKNOWN') !== filters.risk) return false;
  if (filters.movement !== 'ALL' && entity.latest_movement.movement_state !== filters.movement) return false;
  if (filters.zone !== 'ALL' && entity.latest_position.zone !== filters.zone) return false;
  if (filters.vehicleClass !== 'ALL' && entity.vehicle_class.canonical !== filters.vehicleClass) return false;
  return true;
}

const layerLabels: Array<[MapLayer, string]> = [['vehicles', 'Araç kayıtları'], ['untracked', 'Takipsiz tespitler'], ['zones', 'Bölgeler'], ['base', 'Üs']];
const risks: Array<RiskLevel | 'ALL'> = ['ALL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'UNKNOWN'];
const movements: Array<MovementState | 'ALL'> = ['ALL', 'APPROACHING_BASE', 'LEAVING_BASE', 'TRANSIT', 'STATIONARY'];
const riskOption = (value: RiskLevel | 'ALL') => value === 'ALL' ? formatAllOption() : formatRiskLevel(value);
const movementOption = (value: MovementState | 'ALL') => value === 'ALL' ? formatAllOption() : formatMovementState(value);

export function MapSidebar({ analysis, filters, setFilters, open, setOpen, onSelectTrack }: {
  analysis: AnalysisData;
  filters: MapFilterState;
  setFilters: Dispatch<SetStateAction<MapFilterState>>;
  open: boolean;
  setOpen: (open: boolean) => void;
  onSelectTrack: (trackId: string) => void;
}) {
  const layers = useTrackingStore(state => state.layers);
  const selectedTrackId = useTrackingStore(state => state.selectedTrackId);
  const vehicles = useMemo(() => [...new Set(analysis.entities.map(entity => entity.vehicle_class.canonical))].sort(), [analysis.entities]);
  const matches = useMemo(() => analysis.entities.filter(entity => entityMatchesMapFilters(entity, filters)), [analysis.entities, filters]);
  const update = <K extends keyof MapFilterState>(key: K, value: MapFilterState[K]) => setFilters(current => ({ ...current, [key]: value }));
  if (!open) return <button className="map-sidebar-rail" aria-label="Harita panelini aç" title="Harita panelini aç" onClick={() => setOpen(true)}><Layers3 size={17} /><ChevronRight size={14} /></button>;

  return <aside className="map-sidebar" aria-label="Harita paneli">
    <header><span><Layers3 size={15} /><strong>Harita Paneli</strong></span><button aria-label="Harita panelini daralt" title="Harita panelini daralt" onClick={() => setOpen(false)}><ChevronLeft size={16} /></button></header>
    <div className="map-sidebar-scroll">
      <section><h2><Layers3 size={12} />Katmanlar</h2><div className="compact-layer-grid">{layerLabels.map(([layer, label]) => <label key={layer}><input type="checkbox" checked={layers[layer]} onChange={() => useTrackingStore.getState().toggleLayer(layer)} />{label}</label>)}</div></section>
      <section><h2><Filter size={12} />Araç kayıt filtreleri</h2>
        <label className="map-filter-search"><Search size={13} /><input aria-label="Harita araç kayıtlarında ara" placeholder="Track kimliği, araç sınıfı veya bölge" value={filters.query} onChange={event => update('query', event.target.value)} /></label>
        <div className="map-filter-grid">
          <label><span>Risk</span><select aria-label="Harita risk filtresi" value={filters.risk} onChange={event => update('risk', event.target.value as MapFilterState['risk'])}>{risks.map(value => <option key={value} value={value}>{riskOption(value)}</option>)}</select></label>
          <label><span>Araç</span><select aria-label="Harita araç filtresi" value={filters.vehicleClass} onChange={event => update('vehicleClass', event.target.value)}>{['ALL', ...vehicles].map(value => <option key={value} value={value}>{value === 'ALL' ? formatAllOption() : formatVehicleClass(value)}</option>)}</select></label>
          <label className="wide"><span>Hareket</span><select aria-label="Harita hareket filtresi" value={filters.movement} onChange={event => update('movement', event.target.value as MapFilterState['movement'])}>{movements.map(value => <option key={value} value={value}>{movementOption(value)}</option>)}</select></label>
          <label className="wide"><span>Bölge</span><select aria-label="Harita bölge filtresi" value={filters.zone} onChange={event => update('zone', event.target.value)}><option value="ALL">{formatAllOption()}</option>{analysis.zones.map(zone => <option key={zone.name}>{zone.name}</option>)}</select></label>
        </div>
        <div className="map-filter-result"><span>{matches.length} / {analysis.entities.length} araç kaydı görünür</span><button onClick={() => setFilters(initialMapFilters)}>Temizle</button></div>
        <div className="map-track-shortlist">{matches.slice(0, 8).map(entity => { const risk = entity.risk.assessment?.risk_level ?? 'UNKNOWN'; return <button className={selectedTrackId === entity.track_id ? 'active' : ''} key={entity.track_id} onClick={() => onSelectTrack(entity.track_id)}><span><strong>{entity.track_id}</strong><small>{formatVehicleClass(entity.vehicle_class.canonical)} · {entity.latest_position.zone}</small></span><em className={`entity-risk risk-${risk.toLowerCase()}`}>{formatRiskLevel(risk)}</em></button>; })}{!matches.length && <p>Bu filtrelerle eşleşen araç kaydı yok.</p>}</div>
      </section>
      <section><h2><MapPin size={12} />Bölgeler</h2><div className="map-zone-list">{analysis.zones.map(zone => <button key={zone.name} onClick={() => useTrackingStore.getState().requestView('zone', zone.name)}><span>{zone.name}</span><ChevronRight size={12} /></button>)}</div></section>
      <section><h2><Radar size={12} />Takipsiz tespitler <b>{analysis.untracked_observations.length}</b></h2><div className="map-untracked-list">{analysis.untracked_observations.map(item => <article key={item.vehicle_id}><strong>{formatVehicleClass(item.detection.class)}</strong><time>{item.capture_time}</time><span>{item.position.zone}</span><small>%{Math.round(item.detection.confidence * 100)} tespit güveni · üsse {Math.round(item.position.distance_to_base_m)} m</small></article>)}{!analysis.untracked_observations.length && <p>Takipsiz tespit yok.</p>}</div></section>
    </div>
  </aside>;
}

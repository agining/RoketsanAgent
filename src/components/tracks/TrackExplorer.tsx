import { ArrowDown, ArrowUp, Filter, Search, ShieldAlert } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { AnalysisData, AnalysisEntity, AttentionLevel, BehaviorType, MovementState, RiskLevel } from '../../types/analysis';
import { formatAllOption, formatAttention, formatBehavior, formatMovementState, formatRiskLevel, formatUnavailable, formatVehicleClass } from '../../services/formatters';

type FilterValue<T extends string> = T | 'ALL';
type SortKey = 'risk' | 'distance' | 'last_seen' | 'confidence';
const riskLevels: Array<FilterValue<RiskLevel>> = ['ALL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
const attentionLevels: Array<FilterValue<AttentionLevel>> = ['ALL', 'ROUTINE', 'MONITOR', 'PRIORITY', 'IMMEDIATE'];
const movementStates: Array<FilterValue<MovementState>> = ['ALL', 'APPROACHING_BASE', 'LEAVING_BASE', 'TRANSIT', 'STATIONARY'];
const behaviorTypes: Array<FilterValue<BehaviorType>> = ['ALL', 'NORMAL_PATH', 'LOITERING', 'CIRCLING'];
const riskRank: Record<RiskLevel, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, UNKNOWN: 0 };

const assessment = (entity: AnalysisEntity) => entity.risk.assessment;
const risk = (entity: AnalysisEntity): RiskLevel => assessment(entity)?.risk_level ?? 'UNKNOWN';
const attention = (entity: AnalysisEntity): AttentionLevel => assessment(entity)?.recommended_attention ?? 'UNKNOWN';
const clockMinutes = (value: string) => { const [hours, minutes] = value.split(':').map(Number); return hours * 60 + minutes; };

function formatOption(option: string) {
  if (option === 'ALL') return formatAllOption();
  if (riskLevels.includes(option as FilterValue<RiskLevel>)) return formatRiskLevel(option);
  if (attentionLevels.includes(option as FilterValue<AttentionLevel>)) return formatAttention(option);
  if (movementStates.includes(option as FilterValue<MovementState>)) return formatMovementState(option);
  if (behaviorTypes.includes(option as FilterValue<BehaviorType>)) return formatBehavior(option);
  return formatVehicleClass(option);
}

function SelectFilter({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return <label className="track-filter"><span>{label}</span><select aria-label={`${label} filter`} value={value} onChange={event => onChange(event.target.value)}>{options.map(option => <option key={option} value={option}>{formatOption(option)}</option>)}</select></label>;
}

export function TrackExplorer({ analysis, selectedTrackId, onSelectTrack }: { analysis: AnalysisData; selectedTrackId: string | null; onSelectTrack: (trackId: string) => void }) {
  const [query, setQuery] = useState('');
  const [riskFilter, setRiskFilter] = useState<FilterValue<RiskLevel>>('ALL');
  const [attentionFilter, setAttentionFilter] = useState<FilterValue<AttentionLevel>>('ALL');
  const [movementFilter, setMovementFilter] = useState<FilterValue<MovementState>>('ALL');
  const [behaviorFilter, setBehaviorFilter] = useState<FilterValue<BehaviorType>>('ALL');
  const [vehicleFilter, setVehicleFilter] = useState('ALL');
  const [zoneFilter, setZoneFilter] = useState('ALL');
  const [contradictionsOnly, setContradictionsOnly] = useState(false);
  const [inconsistenciesOnly, setInconsistenciesOnly] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>('risk');
  const [descending, setDescending] = useState(true);
  const vehicleClasses = useMemo(() => [...new Set(analysis.entities.map(entity => entity.vehicle_class.canonical))].sort(), [analysis.entities]);
  const zones = useMemo(() => [...new Set(analysis.entities.map(entity => entity.latest_position.zone))].sort(), [analysis.entities]);

  const entities = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    const filtered = analysis.entities.filter(entity => {
      if (normalized && ![entity.track_id, entity.vehicle_class.canonical, entity.latest_position.zone].some(value => value.toLocaleLowerCase().includes(normalized))) return false;
      if (riskFilter !== 'ALL' && risk(entity) !== riskFilter) return false;
      if (attentionFilter !== 'ALL' && attention(entity) !== attentionFilter) return false;
      if (movementFilter !== 'ALL' && entity.latest_movement.movement_state !== movementFilter) return false;
      if (behaviorFilter !== 'ALL' && entity.latest_behavior?.behavior !== behaviorFilter) return false;
      if (vehicleFilter !== 'ALL' && entity.vehicle_class.canonical !== vehicleFilter) return false;
      if (zoneFilter !== 'ALL' && entity.latest_position.zone !== zoneFilter) return false;
      if (contradictionsOnly && !entity.current_evidence_flags.includes('REPORT_CONTRADICTION')) return false;
      if (inconsistenciesOnly && entity.vehicle_class.consistent) return false;
      return true;
    });
    return filtered.sort((a, b) => {
      let delta = 0;
      if (sortKey === 'risk') delta = riskRank[risk(a)] - riskRank[risk(b)];
      if (sortKey === 'distance') delta = a.latest_position.distance_to_base_m - b.latest_position.distance_to_base_m;
      if (sortKey === 'last_seen') delta = clockMinutes(a.last_seen) - clockMinutes(b.last_seen);
      if (sortKey === 'confidence') delta = (assessment(a)?.confidence ?? -1) - (assessment(b)?.confidence ?? -1);
      return (descending ? -delta : delta) || a.track_id.localeCompare(b.track_id);
    });
  }, [analysis.entities, attentionFilter, behaviorFilter, contradictionsOnly, descending, inconsistenciesOnly, movementFilter, query, riskFilter, sortKey, vehicleFilter, zoneFilter]);

  const clearFilters = () => { setQuery(''); setRiskFilter('ALL'); setAttentionFilter('ALL'); setMovementFilter('ALL'); setBehaviorFilter('ALL'); setVehicleFilter('ALL'); setZoneFilter('ALL'); setContradictionsOnly(false); setInconsistenciesOnly(false); };
  return <article className="dashboard-panel track-explorer" aria-label="Tüm araç kayıtları listesi">
    <header><div><span className="panel-kicker">TÜM ARAÇ KAYITLARI</span><h2>Analiz edilen araç kayıtları</h2></div><span className="panel-total">{entities.length} / {analysis.entities.length} kayıt</span></header>
    <div className="track-explorer-toolbar">
      <label className="track-search"><Search size={14} /><input aria-label="Analiz edilen araç kayıtlarında ara" value={query} onChange={event => setQuery(event.target.value)} placeholder="Track kimliği, araç sınıfı veya bölge" /></label>
      <SelectFilter label="Risk" value={riskFilter} options={riskLevels} onChange={value => setRiskFilter(value as FilterValue<RiskLevel>)} />
      <SelectFilter label="Takip" value={attentionFilter} options={attentionLevels} onChange={value => setAttentionFilter(value as FilterValue<AttentionLevel>)} />
      <SelectFilter label="Hareket" value={movementFilter} options={movementStates} onChange={value => setMovementFilter(value as FilterValue<MovementState>)} />
      <SelectFilter label="Davranış" value={behaviorFilter} options={behaviorTypes} onChange={value => setBehaviorFilter(value as FilterValue<BehaviorType>)} />
      <SelectFilter label="Araç" value={vehicleFilter} options={['ALL', ...vehicleClasses]} onChange={setVehicleFilter} />
      <SelectFilter label="Bölge" value={zoneFilter} options={['ALL', ...zones]} onChange={setZoneFilter} />
      <label className="track-flag-filter"><input type="checkbox" checked={contradictionsOnly} onChange={event => setContradictionsOnly(event.target.checked)} />Saha raporu ile sensör verisi çelişkili</label>
      <label className="track-flag-filter"><input type="checkbox" checked={inconsistenciesOnly} onChange={event => setInconsistenciesOnly(event.target.checked)} />Araç sınıflandırması tutarsız</label>
      <div className="track-sort"><Filter size={13} /><select aria-label="Araç kaydı listesini sırala" value={sortKey} onChange={event => setSortKey(event.target.value as SortKey)}><option value="risk">Risk seviyesi</option><option value="distance">Üsse mesafe</option><option value="last_seen">Son görülme</option><option value="confidence">Değerlendirme güveni</option></select><button aria-label={descending ? 'Azalan sırala' : 'Artan sırala'} onClick={() => setDescending(value => !value)}>{descending ? <ArrowDown size={13} /> : <ArrowUp size={13} />}</button></div>
      <button className="track-clear-filters" onClick={clearFilters}>Temizle</button>
    </div>
    <div className="track-table-scroll"><table className="track-table"><thead><tr><th>Track kimliği</th><th>Araç</th><th>Risk</th><th>Güven</th><th>Takip</th><th>Bölge</th><th>Üsse mesafe</th><th>Hareket</th><th>Davranış</th><th>Son görülme</th><th>Rapor</th><th>Kanıt</th></tr></thead><tbody>{entities.map(entity => {
      const entityRisk = risk(entity), entityAttention = attention(entity), entityAssessment = assessment(entity);
      return <tr key={entity.track_id} role="button" tabIndex={0} aria-label={`${entity.track_id} araç detayını aç`} aria-selected={selectedTrackId === entity.track_id} onClick={() => onSelectTrack(entity.track_id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelectTrack(entity.track_id); } }}>
        <td><strong>{entity.track_id}</strong></td><td>{formatVehicleClass(entity.vehicle_class.canonical)}</td><td><span className={`entity-risk risk-${entityRisk.toLowerCase()}`}>{formatRiskLevel(entityRisk)}</span></td><td>{entityAssessment ? `%${Math.round(entityAssessment.confidence * 100)}` : formatUnavailable()}</td><td><span className={`entity-attention attention-${entityAttention.toLowerCase()}`}>{formatAttention(entityAttention)}</span></td><td>{entity.latest_position.zone}</td><td>{(entity.latest_position.distance_to_base_m / 1000).toFixed(2)} km</td><td>{formatMovementState(entity.latest_movement.movement_state)}</td><td>{entity.latest_behavior ? formatBehavior(entity.latest_behavior.behavior) : formatUnavailable()}</td><td>{entity.last_seen}</td><td>{entity.reports.length}</td><td><span className="evidence-count"><b>{entity.current_evidence_flags.length}</b> güncel</span><span className="evidence-count historical"><b>{entity.historical_evidence_flags.length}</b> geçmiş</span></td>
      </tr>;
    })}</tbody></table>{!entities.length && <div className="track-table-empty"><ShieldAlert size={18} /><span><strong>Eşleşen araç kaydı yok</strong><small>Analiz edilen kayıtları görmek için filtreleri değiştir veya temizle.</small></span></div>}</div>
  </article>;
}

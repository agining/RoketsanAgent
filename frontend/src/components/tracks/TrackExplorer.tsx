import { ArrowDown, ArrowUp, Filter, Search, ShieldAlert } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { AnalysisData, AnalysisEntity, ObservationSource, RiskLevel } from '../../types/analysis';
import { clockMinutes } from '../../services/analysisService';
import { formatAllOption, formatDecisionStatus, formatKm, formatMinutes, formatRiskLevel, formatScenario, formatSource, formatSpeed, formatUnavailable, formatVehicleClass } from '../../services/formatters';

type SortKey = 'risk' | 'distance' | 'observed' | 'eta';
const riskLevels: Array<RiskLevel | 'ALL'> = ['ALL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'UNKNOWN'];
const sources: Array<ObservationSource | 'ALL'> = ['ALL', 'detection', 'track_only', 'offframe'];
const riskRank: Record<RiskLevel, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, UNKNOWN: 0 };
const contradicted = (entity: AnalysisEntity) => entity.reports.some(report => report.verdict === 'celisir' || report.verdict === 'manipulasyon');

function SelectFilter({ guide, label, value, options, format, onChange }: { guide?: string; label: string; value: string; options: string[]; format: (value: string) => string; onChange: (value: string) => void }) {
  return <label className="track-filter" data-guide={guide}><span>{label}</span><select aria-label={`${label} filtresi`} value={value} onChange={event => onChange(event.target.value)}>{options.map(option => <option key={option} value={option}>{option === 'ALL' ? formatAllOption() : format(option)}</option>)}</select></label>;
}

export function TrackExplorer({ analysis, selectedTrackId, onSelectTrack }: { analysis: AnalysisData; selectedTrackId: string | null; onSelectTrack: (trackId: string) => void }) {
  const [query, setQuery] = useState('');
  const [riskFilter, setRiskFilter] = useState('ALL');
  const [scenarioFilter, setScenarioFilter] = useState('ALL');
  const [decisionFilter, setDecisionFilter] = useState('ALL');
  const [vehicleFilter, setVehicleFilter] = useState('ALL');
  const [zoneFilter, setZoneFilter] = useState('ALL');
  const [sourceFilter, setSourceFilter] = useState('ALL');
  const [contradictionsOnly, setContradictionsOnly] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>('risk');
  const [descending, setDescending] = useState(true);
  const unique = (values: Array<string | null>) => [...new Set(values.filter((value): value is string => Boolean(value)))].sort();
  const vehicleClasses = useMemo(() => unique(analysis.entities.map(entity => entity.vehicle_class)), [analysis.entities]);
  const zones = useMemo(() => unique(analysis.entities.map(entity => entity.zone)), [analysis.entities]);
  const scenarios = useMemo(() => unique(analysis.entities.map(entity => entity.scenario)), [analysis.entities]);
  const decisions = useMemo(() => unique(analysis.entities.map(entity => entity.decision_status)), [analysis.entities]);

  const entities = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('tr-TR');
    const filtered = analysis.entities.filter(entity => {
      if (normalized && ![entity.track_id, entity.vehicle_class, entity.zone ?? '', entity.frame_id ?? '', entity.vehicle?.vehicle_id ?? ''].some(value => value.toLocaleLowerCase('tr-TR').includes(normalized))) return false;
      if (riskFilter !== 'ALL' && entity.risk_level !== riskFilter) return false;
      if (scenarioFilter !== 'ALL' && entity.scenario !== scenarioFilter) return false;
      if (decisionFilter !== 'ALL' && entity.decision_status !== decisionFilter) return false;
      if (vehicleFilter !== 'ALL' && entity.vehicle_class !== vehicleFilter) return false;
      if (zoneFilter !== 'ALL' && entity.zone !== zoneFilter) return false;
      if (sourceFilter !== 'ALL' && entity.source !== sourceFilter) return false;
      if (contradictionsOnly && !contradicted(entity)) return false;
      return true;
    });
    const eta = (entity: AnalysisEntity) => entity.features?.eta_min ?? Number.POSITIVE_INFINITY;
    return filtered.sort((a, b) => {
      let delta = 0;
      if (sortKey === 'risk') delta = riskRank[a.risk_level] - riskRank[b.risk_level];
      if (sortKey === 'distance') delta = (a.distance_to_base_m ?? Infinity) - (b.distance_to_base_m ?? Infinity);
      if (sortKey === 'observed') delta = clockMinutes(a.observed_at ?? '99:99') - clockMinutes(b.observed_at ?? '99:99');
      if (sortKey === 'eta') delta = eta(a) === eta(b) ? 0 : eta(a) < eta(b) ? -1 : 1;
      return (descending ? -delta : delta) || a.track_id.localeCompare(b.track_id);
    });
  }, [analysis.entities, contradictionsOnly, decisionFilter, descending, query, riskFilter, scenarioFilter, sortKey, sourceFilter, vehicleFilter, zoneFilter]);

  const clearFilters = () => { setQuery(''); setRiskFilter('ALL'); setScenarioFilter('ALL'); setDecisionFilter('ALL'); setVehicleFilter('ALL'); setZoneFilter('ALL'); setSourceFilter('ALL'); setContradictionsOnly(false); };
  return <article className="dashboard-panel track-explorer" data-guide="track-explorer" aria-label="Tüm iz kayıtları listesi">
    <header><div><span className="panel-kicker">TÜM İZ KAYITLARI</span><h2>API'nin analiz ettiği izler</h2></div><span className="panel-total">{entities.length} / {analysis.entities.length} kayıt</span></header>
    <div className="track-explorer-toolbar">
      <label className="track-search" data-guide="explorer-search"><Search size={14} /><input aria-label="Analiz edilen iz kayıtlarında ara" value={query} onChange={event => setQuery(event.target.value)} placeholder="İz, araç, kare veya bölge" /></label>
      <SelectFilter guide="explorer-filters" label="Risk" value={riskFilter} options={riskLevels} format={formatRiskLevel} onChange={setRiskFilter} />
      <SelectFilter label="Senaryo" value={scenarioFilter} options={['ALL', ...scenarios]} format={formatScenario} onChange={setScenarioFilter} />
      <SelectFilter label="Karar" value={decisionFilter} options={['ALL', ...decisions]} format={formatDecisionStatus} onChange={setDecisionFilter} />
      <SelectFilter label="Araç" value={vehicleFilter} options={['ALL', ...vehicleClasses]} format={formatVehicleClass} onChange={setVehicleFilter} />
      <SelectFilter label="Bölge" value={zoneFilter} options={['ALL', ...zones]} format={value => value} onChange={setZoneFilter} />
      <SelectFilter label="Kaynak" value={sourceFilter} options={sources} format={value => formatSource(value as ObservationSource)} onChange={setSourceFilter} />
      <label className="track-flag-filter" data-guide="explorer-contradictions"><input type="checkbox" checked={contradictionsOnly} onChange={event => setContradictionsOnly(event.target.checked)} />Çelişen / manipülatif rapor var</label>
      <div className="track-sort" data-guide="explorer-sort"><Filter size={13} /><select aria-label="İz listesini sırala" value={sortKey} onChange={event => setSortKey(event.target.value as SortKey)}><option value="risk">Risk seviyesi</option><option value="distance">Üsse mesafe</option><option value="observed">Gözlem zamanı</option><option value="eta">Tahmini varış</option></select><button aria-label={descending ? 'Azalan sırala' : 'Artan sırala'} onClick={() => setDescending(value => !value)}>{descending ? <ArrowDown size={13} /> : <ArrowUp size={13} />}</button></div>
      <button className="track-clear-filters" data-guide="explorer-clear" onClick={clearFilters}>Temizle</button>
    </div>
    <div className="track-table-scroll" data-guide="explorer-table"><table className="track-table"><thead><tr><th>İz</th><th>Araç</th><th>Risk</th><th>Motor</th><th>Karar</th><th>Senaryo</th><th>Bölge</th><th>Üsse mesafe</th><th>Hız</th><th>ETA</th><th>Gözlem</th><th>Kaynak</th><th>Rapor</th></tr></thead><tbody>{entities.map(entity => {
      const conflicts = entity.reports.filter(report => report.verdict === 'celisir' || report.verdict === 'manipulasyon').length;
      return <tr key={entity.track_id} role="button" tabIndex={0} aria-label={`${entity.track_id} iz detayını aç`} aria-selected={selectedTrackId === entity.track_id} onClick={() => onSelectTrack(entity.track_id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelectTrack(entity.track_id); } }}>
        <td><strong>{entity.track_id}</strong></td><td>{formatVehicleClass(entity.vehicle_class)}</td>
        <td><span className={`entity-risk risk-${entity.risk_level.toLowerCase()}`}>{formatRiskLevel(entity.risk_level)}</span></td>
        <td><span className={`entity-risk risk-${entity.engine_risk_level.toLowerCase()}`}>{formatRiskLevel(entity.engine_risk_level)}</span></td>
        <td>{formatDecisionStatus(entity.decision_status)}</td><td>{entity.scenario ? formatScenario(entity.scenario) : formatUnavailable()}</td>
        <td>{entity.zone ?? formatUnavailable()}</td><td>{formatKm(entity.distance_to_base_m)}</td>
        <td>{formatSpeed(entity.features?.speed_now_mps)}</td><td>{formatMinutes(entity.features?.eta_min)}</td>
        <td>{entity.observed_at ?? formatUnavailable()}</td><td>{formatSource(entity.source)}</td>
        <td>{entity.reports.length}{conflicts > 0 && <span className="evidence-count"><b>{conflicts}</b> çelişen</span>}</td>
      </tr>;
    })}</tbody></table>{!entities.length && <div className="track-table-empty"><ShieldAlert size={18} /><span><strong>Eşleşen iz yok</strong><small>Filtreleri değiştir veya temizle.</small></span></div>}</div>
  </article>;
}

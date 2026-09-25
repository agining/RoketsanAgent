import { Crosshair, MapPin, PanelRightClose } from 'lucide-react';
import { usePlaybackStore } from '../store/playback';
import { useTrackingStore } from '../store/tracking';
import { useWorkspaceStore } from '../store/workspace';
import type { TrackingData } from '../types/tracking';
import type { RiskLevel } from '../types/analysis';
import { currentFrameAtTime, criticalVehiclesAtTime, zoneSummariesAtTime } from '../services/operation-summary';
import { Button } from './ui/button';
import { ReasoningTrace } from './agent/ReasoningTrace';
import { reportsAtTime } from '../services/reports';

const levels: { key: RiskLevel; label: string }[] = [{ key: 'DUSUK', label: 'LOW' }, { key: 'ORTA', label: 'MED' }, { key: 'YUKSEK', label: 'HIGH' }, { key: 'KRITIK', label: 'CRIT' }];

export function OperationSummary({ data }: { data: TrackingData }) {
  const time = usePlaybackStore(state => Math.floor(state.currentTime));
  const select = useTrackingStore(state => state.selectTrack), request = useTrackingStore(state => state.requestView);
  const frame = currentFrameAtTime(data.analysis, time), critical = criticalVehiclesAtTime(data, time), zones = zoneSummariesAtTime(data, time);
  const top = frame?.vehicles.find(vehicle => vehicle.vehicle_id === frame.top_vehicle_id) ?? null;
  const frameReports = frame ? reportsAtTime(data.analysis, time).filter(report => report.related_frames.includes(frame.frame_id)) : [];
  const globalRisk = data.analysis.summary.frame_risk_counts, globalTotal = Math.max(1, Object.values(globalRisk).reduce((sum, count) => sum + count, 0));
  const maxZoneScore = Math.max(1, ...zones.map(zone => zone.riskScore));
  const focusTrack = (trackId: string) => { select(trackId); request('vehicle'); };
  return <aside className="vehicle-details operation-summary" aria-label="Operation summary">
    <div className="details-heading"><span className="section-eyebrow">OPERATION SUMMARY</span><Button variant="ghost" size="icon" aria-label="Collapse inspector" title="Collapse inspector" onClick={() => useWorkspaceStore.getState().toggleInspector()}><PanelRightClose size={15} /></Button></div>
    <div className="operation-inspect-hint"><Crosshair size={13} /><span><b>Inspect a vehicle</b><small>Select a marker or a critical vehicle for full movement details.</small></span></div>
    <section className="summary-section current-frame"><div className="summary-section-heading"><h2>Current frame</h2><span>{frame?.capture_time ?? 'NO FRAME'}</span></div>
      {frame ? <><div className="frame-identity"><strong>{frame.frame_id}</strong><span><MapPin size={11} />{frame.zone}</span></div><div className="frame-metrics"><span><b>{frame.vehicles.length}</b> vehicles</span><span><b>{frame.reports.length}</b> related reports</span></div>
        <div className="frame-risk-grid">{levels.map(level => <div key={level.key} className={`risk-${level.key.toLowerCase()}`}><b>{frame.counts[level.key] ?? 0}</b><span>{level.label}</span></div>)}</div>
        <div className="frame-top-risk"><span>TOP RISK</span><b>{top?.track_id ?? top?.vehicle_id ?? '—'}</b><small>{top ? `${top.risk_level} · ${top.scenario}` : 'No vehicle'}</small></div></> : <p className="summary-empty">No image frame within ±2.5 minutes of the playback cursor.</p>}
    </section>
    <ReasoningTrace vehicle={top} reports={frameReports} />
    <section className="summary-section"><div className="summary-section-heading"><h2>Frame risk distribution</h2><span>{data.analysis.summary.frames} total</span></div>
      <div className="risk-distribution" aria-label="Frame risk distribution">{levels.map(level => <i key={level.key} className={`risk-${level.key.toLowerCase()}`} style={{ width: `${globalRisk[level.key] / globalTotal * 100}%` }} title={`${level.label}: ${globalRisk[level.key]}`} />)}</div>
      <div className="risk-distribution-labels">{levels.map(level => <span key={level.key}><i className={`risk-dot risk-${level.key.toLowerCase()}`} />{level.label} <b>{globalRisk[level.key]}</b></span>)}</div>
    </section>
    <section className="summary-section"><div className="summary-section-heading"><h2>Critical vehicles</h2><span>Known at cursor</span></div>
      <div className="critical-list">{critical.map(vehicle => <button key={vehicle.trackId} onClick={() => focusTrack(vehicle.trackId)}><span className={`critical-rank risk-${vehicle.risk.toLowerCase()}`}><Crosshair size={13} /></span><span className="critical-main"><strong>{vehicle.trackId}<em>{vehicle.type.toUpperCase()}</em></strong><small>{vehicle.zone} · {(vehicle.distanceM / 1000).toFixed(2)} km</small><small>{vehicle.scenario}</small><p>{vehicle.reason}</p></span></button>)}{!critical.length && <p className="summary-empty">No HIGH or CRITICAL mapped vehicles known at this time.</p>}</div>
    </section>
    <section className="summary-section"><div className="summary-section-heading"><h2>Zone summary</h2><span>At cursor</span></div>
      <div className="zone-summary-head"><span>Zone</span><span>Veh</span><span>H/C</span><span>Untr</span><span>Conf</span></div>
      <div className="zone-summary-list">{zones.map(zone => <button key={zone.zone} onClick={() => request('zone', zone.zone)} aria-label={`Focus zone ${zone.zone}`}><span className="zone-summary-name"><b>{zone.zone}</b><i><em style={{ width: `${zone.riskScore / maxZoneScore * 100}%` }} /></i></span><span>{zone.vehicles}</span><span className={zone.elevated ? 'elevated' : ''}>{zone.elevated}</span><span>{zone.untracked}</span><span className={zone.conflicts ? 'conflict' : ''}>{zone.conflicts}</span></button>)}</div>
    </section>
  </aside>;
}

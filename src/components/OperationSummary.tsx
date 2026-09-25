import { Crosshair, PanelRightClose, ShieldCheck } from 'lucide-react';
import { useTrackingStore } from '../store/tracking';
import { useWorkspaceStore } from '../store/workspace';
import type { TrackingData } from '../types/tracking';
import { buildAnalysisIndex } from '../services/analysis';
import { allReports } from '../services/reports';
import { formatAttention, formatRiskLevel, formatVehicleClass, humanizeAssessmentText } from '../services/formatters';
import { Button } from './ui/button';
import { ReasoningTrace } from './agent/ReasoningTrace';

export function OperationSummary({ data }: { data: TrackingData }) {
  const summary = data.analysis.operation_summary;
  const select = useTrackingStore(state => state.selectTrack), request = useTrackingStore(state => state.requestView);
  const lead = summary.priority_entities[0] ?? null;
  const leadVehicle = lead ? buildAnalysisIndex(data.analysis).byTrackId.get(lead.track_id)?.[0] ?? null : null;
  const leadReports = lead ? allReports(data.analysis).filter(report => report.matched_track_id === lead.track_id) : [];
  const focusTrack = (trackId: string) => { select(trackId); request('vehicle'); };
  return <aside className="vehicle-details operation-summary" aria-label="Operasyon özeti">
    <div className="details-heading"><span className="section-eyebrow">ANALİZ ÖZETİ</span><Button variant="ghost" size="icon" aria-label="İnceleme panelini daralt" title="İnceleme panelini daralt" onClick={() => useWorkspaceStore.getState().toggleInspector()}><PanelRightClose size={15} /></Button></div>
    <div className="operation-inspect-hint"><Crosshair size={13} /><span><b>Bir aracı incele</b><small>Araç kaydı düzeyindeki kanıtlar için harita markerı veya öncelikli kart seç.</small></span></div>
    <section className="summary-section"><div className="summary-section-heading"><h2>Operasyon toplamları</h2><span>Son analiz</span></div>
      <div className="frame-metrics"><span><b>{summary.tracked_entity_count}</b> takipte</span><span><b>{summary.untracked_observation_count}</b> takipsiz</span></div>
      <div className="frame-risk-grid"><div className="risk-low"><b>{summary.risk_counts.LOW}</b><span>{formatRiskLevel('LOW')}</span></div><div className="risk-medium"><b>{summary.risk_counts.MEDIUM}</b><span>{formatRiskLevel('MEDIUM')}</span></div><div className="risk-high"><b>{summary.risk_counts.HIGH}</b><span>{formatRiskLevel('HIGH')}</span></div><div className="risk-critical"><b>{summary.risk_counts.CRITICAL}</b><span>{formatRiskLevel('CRITICAL')}</span></div></div>
    </section>
    <section className="summary-section"><div className="summary-section-heading"><h2>En öncelikli araç kaydı</h2><span>{formatAttention(lead?.recommended_attention ?? 'ROUTINE')}</span></div>
      {lead ? <button className="inspector-priority" onClick={() => focusTrack(lead.track_id)}><span><ShieldCheck size={14} /><strong>{lead.track_id}</strong></span><small>{formatVehicleClass(lead.vehicle_class)} · {lead.zone}</small><p>{humanizeAssessmentText(lead.summary)}</p></button> : <p className="summary-empty">Son analizde öncelikli araç kaydı yok.</p>}
    </section>
    <ReasoningTrace vehicle={leadVehicle} reports={leadReports} />
  </aside>;
}

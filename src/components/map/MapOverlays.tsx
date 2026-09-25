import { Activity, ChevronRight, ListFilter, ShieldAlert, X } from 'lucide-react';
import { useState } from 'react';
import type { AnalysisData, RiskLevel } from '../../types/analysis';
import { formatAttention, formatRiskLevel, formatVehicleClass, humanizeAssessmentText } from '../../services/formatters';

const riskRank: Record<RiskLevel, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, UNKNOWN: 0 };

export function MapOverlays({ analysis, onSelectTrack }: { analysis: AnalysisData; onSelectTrack: (trackId: string) => void }) {
  const [panel, setPanel] = useState<'summary' | 'priority' | null>(null);
  const summary = analysis.operation_summary;
  const priorities = [...summary.priority_entities].sort((a, b) => riskRank[b.risk_level] - riskRank[a.risk_level] || a.distance_to_base_m - b.distance_to_base_m);
  return <div className="map-floating-overlays">
    <div className="map-overlay-actions">
      <button aria-expanded={panel === 'summary'} onClick={() => setPanel(value => value === 'summary' ? null : 'summary')}><Activity size={14} />Operasyon Özeti</button>
      <button aria-expanded={panel === 'priority'} onClick={() => setPanel(value => value === 'priority' ? null : 'priority')}><ShieldAlert size={14} />Öncelikli Araçlar <b>{priorities.length}</b></button>
    </div>
    {panel === 'summary' && <section className="map-summary-popover" aria-label="Operasyon özeti"><header><span><Activity size={14} />Operasyon Özeti</span><button aria-label="Operasyon özetini kapat" onClick={() => setPanel(null)}><X size={14} /></button></header>
      <div className="compact-distributions"><div><h3>Risk</h3>{(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'UNKNOWN'] as const).map(level => <span key={level}><i className={`risk-${level.toLowerCase()}`} />{formatRiskLevel(level)}<b>{summary.risk_counts[level]}</b></span>)}</div><div><h3>Takip seviyesi</h3>{(['ROUTINE', 'MONITOR', 'PRIORITY', 'IMMEDIATE', 'UNKNOWN'] as const).map(level => <span key={level}>{formatAttention(level)}<b>{summary.attention_counts[level]}</b></span>)}</div></div>
      <div className="compact-state-grid"><span>Üsse yaklaşıyor<b>{summary.current_state_counts.approaching_base}</b></span><span>Üsten uzaklaşıyor<b>{summary.current_state_counts.leaving_base}</b></span><span>Bölgede dolaşma<b>{summary.current_state_counts.loitering}</b></span><span>Dairesel hareket<b>{summary.current_state_counts.circling}</b></span></div>
      <div className="compact-quality"><ListFilter size={12} /><span>Saha raporu ile sensör verisi çelişkili <b>{summary.current_state_counts.report_contradiction}</b></span><span>Araç sınıflandırması tutarsız <b>{summary.current_state_counts.class_inconsistency}</b></span></div>
    </section>}
    {panel === 'priority' && <section className="map-priority-popover" aria-label="Öncelikli araç kayıtları"><header><span><ShieldAlert size={14} />Öncelikli Araçlar</span><button aria-label="Öncelikli araç listesini kapat" onClick={() => setPanel(null)}><X size={14} /></button></header>{priorities.length ? <div>{priorities.map(entity => <button key={entity.track_id} onClick={() => { onSelectTrack(entity.track_id); setPanel(null); }}><span><strong>{entity.track_id}</strong><small>{formatVehicleClass(entity.vehicle_class)} · {entity.zone}</small><em>{humanizeAssessmentText(entity.summary)}</em></span><span><b className={`risk-${entity.risk_level.toLowerCase()}`}>{formatRiskLevel(entity.risk_level)}</b><small>{Math.round(entity.distance_to_base_m)} m</small><ChevronRight size={13} /></span></button>)}</div> : <p>Bu analizde yüksek veya kritik öncelikli araç kaydı yok.</p>}</section>}
  </div>;
}

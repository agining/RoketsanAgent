import { Activity, Bot, BrainCircuit, ChevronRight, LoaderCircle, ShieldAlert, UserCheck, X } from 'lucide-react';
import { useState } from 'react';
import type { AnalysisAlert, AnalysisData, RiskLevel } from '../../types/analysis';
import { api } from '../../services/api';
import { clockSeconds } from '../../services/analysis-playback';
import { formatDecisionStatus, formatMeters, formatMinutes, formatReportVerdict, formatRiskLevel, formatScenario, formatVehicleClass } from '../../services/formatters';
import { usePlaybackStore } from '../../store/playback';
import { useTrackingStore } from '../../store/tracking';
import { useWorkspaceStore } from '../../store/workspace';
import { ReviewCard } from '../review/ReviewCard';
import { AgentChat } from '../agent/AgentChat';

type Panel = 'summary' | 'priority' | 'reviews' | 'chat' | null;
const levels = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const satisfies readonly RiskLevel[];

export function MapOverlays({ analysis, onSelectTrack, onChanged, selectedFrameId }: {
  analysis: AnalysisData; onSelectTrack: (trackId: string) => void; onChanged: () => void; selectedFrameId: string | null;
}) {
  const [panel, setPanel] = useState<Panel>(null);
  const [assessing, setAssessing] = useState(false);
  const [assessMessage, setAssessMessage] = useState('');
  const analyst = useWorkspaceStore(state => state.analyst);
  const setAnalyst = useWorkspaceStore(state => state.setAnalyst);
  const summary = analysis.summary;
  const pending = analysis.reviews.items.filter(item => !item.review);
  const toggle = (value: Panel) => setPanel(current => current === value ? null : value);

  const openAlert = (alert: AnalysisAlert) => {
    usePlaybackStore.getState().seek(clockSeconds(alert.time));
    if (alert.track_id && analysis.entities.some(entity => entity.track_id === alert.track_id)) onSelectTrack(alert.track_id);
    else useTrackingStore.getState().requestView('coordinate', undefined, [alert.lon, alert.lat]);
    setPanel(null);
  };
  const assessAll = async () => {
    setAssessing(true); setAssessMessage('');
    try { const result = await api.assessAll('ORTA'); setAssessMessage(`${result.assessed.length} kare değerlendirildi.`); onChanged(); }
    catch (cause) { setAssessMessage(cause instanceof Error ? cause.message : 'Değerlendirme başarısız.'); }
    finally { setAssessing(false); }
  };

  return <div className="map-floating-overlays">
    <div className="map-overlay-actions">
      <button data-guide="overlay-summary" aria-expanded={panel === 'summary'} onClick={() => toggle('summary')}><Activity size={14} />Operasyon Özeti</button>
      <button data-guide="overlay-priority" aria-expanded={panel === 'priority'} onClick={() => toggle('priority')}><ShieldAlert size={14} />Öncelikli Araçlar <b>{analysis.alerts.length}</b></button>
      <button data-guide="overlay-reviews" aria-expanded={panel === 'reviews'} onClick={() => toggle('reviews')}><UserCheck size={14} />Analist Onayı {pending.length > 0 && <b>{pending.length}</b>}</button>
      <button data-guide="overlay-chat" aria-expanded={panel === 'chat'} onClick={() => toggle('chat')}><Bot size={14} />Ajan</button>
    </div>

    {panel === 'summary' && <section className="map-summary-popover" data-guide="summary-panel" aria-label="Operasyon özeti"><header><span><Activity size={14} />Operasyon Özeti</span><button aria-label="Operasyon özetini kapat" onClick={() => setPanel(null)}><X size={14} /></button></header>
      <div className="compact-distributions">
        <div><h3>Kare riski (nihai)</h3>{levels.map(level => <span key={level}><i className={`risk-${level.toLowerCase()}`} />{formatRiskLevel(level)}<b>{summary.frame_risk_counts[level]}</b></span>)}</div>
        <div><h3>Kare riski (motor)</h3>{levels.map(level => <span key={level}><i className={`risk-${level.toLowerCase()}`} />{formatRiskLevel(level)}<b>{summary.engine_frame_risk_counts[level]}</b></span>)}</div>
      </div>
      <div className="compact-state-grid">
        <span>Kare<b>{summary.frames}</b></span><span>Araç (karelerde)<b>{summary.vehicles}</b></span>
        <span>İz<b>{summary.tracks}</b></span><span>Kare dışı iz<b>{summary.offframe_tracks}</b></span>
        <span>İzden kurtarılan tespit<b>{summary.missed_detections_recovered}</b></span><span>Elenen tespit<b>{summary.filtered_detections}</b></span>
        <span>Değerlendirilen kare<b>{summary.assessed_frames}</b></span><span>Onay bekleyen<b>{summary.pending_reviews}</b></span>
      </div>
      <div className="compact-distributions single"><div><h3>Saha raporu hükümleri</h3>{Object.entries(summary.report_verdicts).map(([verdict, count]) => <span key={verdict}><i className={`verdict-dot verdict-${verdict}`} />{formatReportVerdict(verdict)}<b>{count}</b></span>)}</div></div>
      {Object.keys(summary.decisions).length > 0 && <div className="compact-distributions single"><div><h3>Karar durumları</h3>{Object.entries(summary.decisions).map(([status, count]) => <span key={status}>{formatDecisionStatus(status)}<b>{count}</b></span>)}</div></div>}
      <div className="summary-llm">
        <span><BrainCircuit size={13} />{summary.llm_enabled ? `LLM açık · ${summary.model ?? 'model bilinmiyor'}` : 'LLM kapalı — API motor şablonunu kullanır'} · dedektör: {summary.detector || '—'}</span>
        <button data-guide="summary-assess-all" disabled={assessing} onClick={() => void assessAll()}>{assessing ? <LoaderCircle size={12} className="spinning" /> : <BrainCircuit size={12} />}Riskli kareleri ajanla değerlendir</button>
        {assessMessage && <small role="status">{assessMessage}</small>}
      </div>
    </section>}

    {panel === 'priority' && <section className="map-priority-popover" data-guide="priority-panel" aria-label="Öncelikli araç kayıtları"><header><span><ShieldAlert size={14} />Öncelikli Araçlar · ORTA ve üzeri</span><button aria-label="Öncelikli araç listesini kapat" onClick={() => setPanel(null)}><X size={14} /></button></header>
      {analysis.alerts.length ? <div>{analysis.alerts.map((alert, index) => <button key={`${alert.kind}-${alert.vehicle_id ?? alert.track_id}-${index}`} onClick={() => openAlert(alert)}>
        <span><strong>{alert.track_id ?? alert.vehicle_id}</strong><small>{alert.label ? `${formatVehicleClass(alert.label)} · ` : ''}{alert.zone} · {alert.time}{alert.kind === 'offframe_track' ? ' · kare dışı' : ''} · {formatScenario(alert.scenario)}</small><em>{alert.reason}</em>{alert.decision_status !== 'motor' && <small className="alert-decision">{formatDecisionStatus(alert.decision_status)}</small>}</span>
        <span><b className={`risk-${alert.risk_level.toLowerCase()}`}>{formatRiskLevel(alert.risk_level)}</b><small>{formatMeters(alert.distance_to_base_m)}{alert.eta_min != null ? ` · ETA ${formatMinutes(alert.eta_min)}` : ''}</small><ChevronRight size={13} /></span>
      </button>)}</div> : <p>Bu analizde ORTA veya üzeri riskli araç yok.</p>}
    </section>}

    {panel === 'reviews' && <section className="map-priority-popover map-review-popover" data-guide="reviews-panel" aria-label="Analist onayı"><header><span><UserCheck size={14} />Son söz insanda · {analysis.human_review ? 'AÇIK' : 'KAPALI'}</span><button aria-label="Analist onayı panelini kapat" onClick={() => setPanel(null)}><X size={14} /></button></header>
      <div className="review-panel-body">
        <label className="review-analyst" data-guide="review-analyst"><span>Analist</span><input aria-label="Analist adı" placeholder="Adınız" value={analyst} onChange={event => setAnalyst(event.target.value)} /></label>
        {analysis.reviews.items.length ? analysis.reviews.items.map(item => <ReviewCard key={`${item.vehicle_id}-${item.review?.at ?? 'pending'}-${item.current_level}`} item={item} humanReview={analysis.human_review} analyst={analyst} onChanged={onChanged} />)
          : <p className="review-empty">Analist onayı gerektiren karar yok. Kararlar, ajan bir kareyi değerlendirdiğinde motor ile LLM ayrışırsa burada görünür.</p>}
      </div>
    </section>}

    {panel === 'chat' && <AgentChat analysis={analysis} frameId={selectedFrameId} onSelectTrack={onSelectTrack} onClose={() => setPanel(null)} />}
  </div>;
}

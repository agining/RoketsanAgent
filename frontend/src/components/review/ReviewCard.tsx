import { useState } from 'react';
import { Check, LoaderCircle, Undo2, UserCheck } from 'lucide-react';
import type { ApiReviewItem, ApiRiskLevel } from '../../types/api';
import { toRiskLevel } from '../../types/analysis';
import { api } from '../../services/api';
import { formatDecisionStatus, formatEpoch, formatReportVerdict, formatRiskLevel, formatScenario, formatVehicleClass } from '../../services/formatters';

function Level({ level }: { level: ApiRiskLevel | null | undefined }) {
  const risk = toRiskLevel(level);
  return <span className={`entity-risk risk-${risk.toLowerCase()}`}>{level ? formatRiskLevel(risk) : '—'}</span>;
}

/** One "son söz insanda" decision: engine vs LLM rationale side by side, analyst sets the final level. */
export function ReviewCard({ item, humanReview, analyst, onChanged, compact = false }: {
  item: ApiReviewItem; humanReview: boolean; analyst: string; onChanged: () => void; compact?: boolean;
}) {
  const [level, setLevel] = useState<ApiRiskLevel>(item.review?.level ?? item.current_level);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const run = async (work: () => Promise<unknown>) => {
    setBusy(true); setError('');
    try { await work(); onChanged(); } catch (cause) { setError(cause instanceof Error ? cause.message : 'İşlem başarısız.'); } finally { setBusy(false); }
  };
  const options = item.options?.length ? item.options : (['DUSUK', 'ORTA', 'YUKSEK', 'KRITIK'] as ApiRiskLevel[]);
  return <article className={`review-card ${item.review ? 'decided' : 'pending'}`} aria-label={`${item.vehicle_id} analist kararı`}>
    <header>
      <span><strong>{item.track_id ?? item.vehicle_id}</strong><small>{item.vehicle_id} · {item.capture_time} · {item.zone}{item.label ? ` · ${formatVehicleClass(item.label)}` : ''}</small></span>
      <Level level={item.current_level} />
    </header>
    <div className="review-status">{formatDecisionStatus(item.status)}{item.rule_label ? ` · ${item.rule_label}` : ''}</div>
    {!compact && <div className="review-compare">
      <div><h4>Motor <Level level={item.engine_level} /></h4><p>{formatScenario(item.motor.scenario)}</p>{item.motor.reasons.slice(0, 3).map(reason => <small key={reason}>{reason}</small>)}</div>
      <div><h4>LLM <Level level={item.llm_level} /></h4><p>{item.llm.reason ?? 'Gerekçe yok.'}</p>{item.llm.evidence.map(evidence => <small key={evidence.report_id}>{evidence.report_id} · {formatReportVerdict(evidence.verdict)} — {evidence.summary}</small>)}</div>
    </div>}
    {item.note && <p className="review-note">{item.note}</p>}
    {item.review && <div className="review-decided"><UserCheck size={13} /><span>Analist kararı: <b>{formatRiskLevel(toRiskLevel(item.review.level))}</b> · {item.review.analyst} · {formatEpoch(item.review.at)}{item.review.note ? ` — ${item.review.note}` : ''}</span><button disabled={busy} onClick={() => void run(() => api.undoReview(item.vehicle_id))}><Undo2 size={12} />Geri al</button></div>}
    {humanReview ? <div className="review-form">
      <div className="review-options" data-guide="review-levels" role="radiogroup" aria-label={`${item.vehicle_id} için seviye`}>{options.map(option => <button key={option} role="radio" aria-checked={level === option} className={`risk-${toRiskLevel(option).toLowerCase()}`} onClick={() => setLevel(option)}>{formatRiskLevel(toRiskLevel(option))}</button>)}</div>
      <input data-guide="review-note" aria-label="Analist notu" placeholder="Not (isteğe bağlı)" value={note} onChange={event => setNote(event.target.value)} />
      <button className="review-submit" data-guide="review-submit" disabled={busy} onClick={() => void run(() => api.decideReview(item.vehicle_id, { level, analyst: analyst.trim() || null, note: note.trim() || null }))}>{busy ? <LoaderCircle size={12} className="spinning" /> : <Check size={12} />}{item.review ? 'Kararı güncelle' : 'Kararı kaydet'}</button>
    </div> : <p className="review-disabled">"Son söz insanda" kapalı: karar tablosunun otomatik sonucu uygulanıyor.</p>}
    {error && <p className="review-error" role="alert">{error}</p>}
  </article>;
}

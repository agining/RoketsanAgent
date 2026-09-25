import { useEffect } from 'react';
import { AlertTriangle, Crosshair, MapPin, ShieldAlert, X } from 'lucide-react';
import type { TrackingData } from '../../types/tracking';
import { usePlaybackStore } from '../../store/playback';
import { useReportStore } from '../../store/reports';
import { useTrackingStore } from '../../store/tracking';
import { clockMinutes } from '../../services/operation-summary';
import { checkText } from '../../services/reports';
import { Button } from '../ui/button';
import { ReportVerdictBadge } from './ReportVerdictBadge';

const claimLabel = (key: string) => key.replaceAll('_', ' ').replace(/^claims /, '').toUpperCase();

export function ReportDetailDrawer({ data }: { data: TrackingData }) {
  const selected = useReportStore(state => state.selectedReportId), close = useReportStore(state => state.selectReport);
  const time = usePlaybackStore(state => Math.floor(state.currentTime));
  const report = (data.analysis.reports ?? []).find(report => report.report_id === selected) ?? null;
  useEffect(() => { if (report && clockMinutes(report.time) > time / 60) close(null); }, [close, report, time]);
  if (!report || clockMinutes(report.time) > time / 60) return null;
  const contradiction = report.verdict === 'celisir' || report.verdict === 'manipulasyon';
  const locationMatch = report.checks.konum ?? report.checks.konum_rapor_saatinde ?? report.checks.konum_cekim_aninda;
  const movementMatch = report.checks.davranis ?? report.checks.olagan_iddiasi ?? report.checks.dost_iddiasi;
  const claims = Object.entries(report.parsed).filter(([, value]) => value === true || (value !== false && value !== null && value !== '' && (!Array.isArray(value) || value.length)));
  const canFocusTrack = !!report.matched_track_id && data.tracks.some(track => track.id === report.matched_track_id);
  const focusTrack = () => { if (!report.matched_track_id) return; close(null); useTrackingStore.getState().selectTrack(report.matched_track_id); useTrackingStore.getState().requestView('vehicle'); };
  return <aside className="vehicle-details report-drawer" aria-label="Report investigation">
    <div className="details-heading"><span className="section-eyebrow">FIELD REPORT EVIDENCE</span><Button variant="ghost" size="icon" aria-label="Close report details" onClick={() => close(null)}><X size={16} /></Button></div>
    <div className="report-drawer-title"><div><strong>{report.report_id}</strong><span>{report.time} · {report.source.replace('_', ' ')}</span></div><ReportVerdictBadge verdict={report.verdict} /></div>
    {contradiction && <div className="contradiction-warning"><AlertTriangle size={17} /><span><b>Evidence contradiction</b><small>This report conflicts with detection or tracked behavior. Do not use it to lower risk.</small></span></div>}
    {report.injection_detected && <div className="injection-warning"><ShieldAlert size={17} /><span><b>Instruction injection detected</b><small>Embedded instructions were isolated and not applied.</small></span></div>}
    <section className="report-detail-section"><h2>Original report</h2><blockquote>{report.text}</blockquote><div className="report-context"><span><MapPin size={11} />{report.zone ?? 'No zone'}</span><span>{report.report_type}</span></div></section>
    <section className="report-detail-section"><h2>Evidence match</h2><dl className="evidence-checks">
      <div><dt>Matched track</dt><dd>{report.matched_track_id ?? '—'}</dd></div><div><dt>Matched vehicle</dt><dd>{report.matched_vehicle_id ?? '—'}</dd></div>
      <div><dt>Location</dt><dd>{checkText(locationMatch)}</dd></div><div><dt>Distance</dt><dd>{typeof report.checks.mesafe_m === 'number' ? `${report.checks.mesafe_m.toFixed(1)} m` : '—'}</dd></div>
      <div><dt>Vehicle type</dt><dd>{checkText(report.checks.tip)}</dd></div><div><dt>Movement / behavior</dt><dd>{checkText(movementMatch)}</dd></div>
    </dl>{canFocusTrack && <Button variant="outline" onClick={focusTrack}><Crosshair size={13} />Focus matched track</Button>}</section>
    <section className="report-detail-section"><h2>Parsed claims</h2><dl className="parsed-claims">{claims.map(([key, value]) => <div key={key}><dt>{claimLabel(key)}</dt><dd>{checkText(value)}</dd></div>)}{!claims.length && <p className="summary-empty">No structured claims extracted.</p>}</dl></section>
    <section className="report-detail-section"><h2>Verification summary</h2><p className="verification-summary">{report.summary}</p></section>
    <div className="injection-status"><span>Injection detected</span><b>{report.injection_detected ? 'YES' : 'NO'}</b></div>
  </aside>;
}

import { useEffect } from 'react';
import { AlertTriangle, Crosshair, MapPin, ShieldAlert, X } from 'lucide-react';
import type { TrackingData } from '../../types/tracking';
import { usePlaybackStore } from '../../store/playback';
import { useReportStore } from '../../store/reports';
import { useTrackingStore } from '../../store/tracking';
import { clockMinutes } from '../../services/operation-summary';
import { allReports, checkText } from '../../services/reports';
import { formatEvidenceFlag, formatReportSource, formatReportType, formatVehicleClass, humanizeAssessmentText } from '../../services/formatters';
import { Button } from '../ui/button';
import { ReportVerdictBadge } from './ReportVerdictBadge';

const claimLabel = (key: string) => humanizeAssessmentText(key.replace(/^claims_?/, ''));

export function ReportDetailDrawer({ data }: { data: TrackingData }) {
  const selected = useReportStore(state => state.selectedReportId), close = useReportStore(state => state.selectReport);
  const time = usePlaybackStore(state => Math.floor(state.currentTime));
  const report = allReports(data.analysis).find(report => report.report_id === selected) ?? null;
  useEffect(() => { if (report && clockMinutes(report.time) > time / 60) close(null); }, [close, report, time]);
  if (!report || clockMinutes(report.time) > time / 60) return null;
  const contradiction = report.verdict === 'CONTRADICTED' || report.contradicted_checks > 0;
  const canFocusTrack = !!report.matched_track_id && data.tracks.some(track => track.id === report.matched_track_id);
  const focusTrack = () => { if (!report.matched_track_id) return; close(null); useTrackingStore.getState().selectTrack(report.matched_track_id); useTrackingStore.getState().requestView('vehicle'); };
  return <aside className="vehicle-details report-drawer" aria-label="Saha raporu incelemesi">
    <div className="details-heading"><span className="section-eyebrow">SAHA RAPORU KANITI</span><Button variant="ghost" size="icon" aria-label="Rapor detayını kapat" onClick={() => close(null)}><X size={16} /></Button></div>
    <div className="report-drawer-title"><div><strong>{report.report_id}</strong><span>{report.time} · {formatReportSource(report.source)}</span></div><ReportVerdictBadge verdict={report.verdict} /></div>
    {contradiction && <div className="contradiction-warning"><AlertTriangle size={17} /><span><b>Saha raporu ile sensör verisi çelişkili</b><small>Bu rapor tespit veya track davranışıyla çelişiyor. Riski düşürmek için tek başına kullanılmamalıdır.</small></span></div>}
    {report.injection_detected && <div className="injection-warning"><ShieldAlert size={17} /><span><b>Talimat enjeksiyonu tespit edildi</b><small>Gömülü talimatlar ayrıştırıldı ve uygulanmadı.</small></span></div>}
    <section className="report-detail-section"><h2>Orijinal rapor</h2><blockquote>{humanizeAssessmentText(report.text)}</blockquote><div className="report-context"><span><MapPin size={11} />{report.zone ?? 'Bölge yok'}</span><span>{formatReportType(report.report_type)}</span></div></section>
    <section className="report-detail-section"><h2>Kanıt eşleşmesi</h2><dl className="evidence-checks">
      <div><dt>Eşleşen track</dt><dd>{report.matched_track_id ?? '—'}</dd></div><div><dt>Eşleşen araç</dt><dd>{report.matched_vehicle_id ?? '—'}</dd></div>
      <div><dt>Mesafe</dt><dd>{report.match_distance_m.toFixed(1)} m</dd></div><div><dt>Araç tipi</dt><dd>{formatVehicleClass(report.vehicle_type)}</dd></div>
      <div><dt>Desteklenen kontrol</dt><dd>{report.supported_checks}</dd></div><div><dt>Çelişen kontrol</dt><dd>{report.contradicted_checks}</dd></div>
    </dl>{canFocusTrack && <Button variant="outline" onClick={focusTrack}><Crosshair size={13} />Eşleşen track'e odaklan</Button>}</section>
    <section className="report-detail-section"><h2>Kanıt kontrolleri</h2><dl className="parsed-claims">{report.checks.map((check, index) => <div key={`${check.claim}-${index}`}><dt>{claimLabel(check.claim)}</dt><dd>{formatEvidenceFlag(check.result)} · {humanizeAssessmentText(checkText(check.value))}</dd></div>)}{!report.checks.length && <p className="summary-empty">Yapılandırılmış kontrol yok.</p>}</dl></section>
    <section className="report-detail-section"><h2>Doğrulama özeti</h2><p className="verification-summary">{humanizeAssessmentText(report.summary)}</p></section>
    <div className="injection-status"><span>Talimat enjeksiyonu</span><b>{report.injection_detected ? 'Evet' : 'Hayır'}</b></div>
  </aside>;
}

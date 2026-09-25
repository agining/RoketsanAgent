import { AlertTriangle, FileText, ShieldAlert } from 'lucide-react';
import type { TrackingData } from '../../types/tracking';
import { usePlaybackStore } from '../../store/playback';
import { useReportStore, type ReportMode, type ReportSourceFilter } from '../../store/reports';
import { reportsAtTime } from '../../services/reports';
import { currentFrameAtTime } from '../../services/operation-summary';
import { formatReportSource, formatReportType, humanizeAssessmentText } from '../../services/formatters';
import { ReportVerdictBadge } from './ReportVerdictBadge';

const modes: { value: ReportMode; label: string }[] = [{ value: 'all', label: 'Tümü' }, { value: 'contradictions', label: 'Çelişkiler' }, { value: 'supporting', label: 'Destekleyenler' }, { value: 'manipulation', label: 'Enjeksiyon' }];
const sources: { value: ReportSourceFilter; label: string }[] = [{ value: 'all', label: 'Tüm kaynaklar' }, { value: 'official', label: 'Resmi kaynak' }, { value: 'third_party', label: 'Üçüncü taraf' }];

export function ReportsPanel({ data }: { data: TrackingData }) {
  const time = usePlaybackStore(state => Math.floor(state.currentTime));
  const state = useReportStore(), reports = reportsAtTime(data.analysis, time, state);
  const frame = currentFrameAtTime(data.analysis, time);
  return <div className="reports-panel">
    <div className="report-filter-group" role="group" aria-label="Rapor doğrulama filtresi">{modes.map(mode => <button key={mode.value} aria-pressed={state.mode === mode.value} onClick={() => state.setMode(mode.value)}>{mode.label}</button>)}</div>
    <div className="report-source-filter" role="group" aria-label="Rapor kaynak filtresi">{sources.map(source => <button key={source.value} aria-pressed={state.source === source.value} onClick={() => state.setSource(source.value)}>{source.label}</button>)}</div>
    <div className="report-list-heading"><span>{reports.length} rapor biliniyor</span><small>Gelecek zamanlı raporlar gizli</small></div>
    <div className="report-list">{reports.slice().reverse().map(report => {
      const current = !!frame && report.time === frame.capture_time, warning = report.verdict === 'CONTRADICTED';
      return <button className={`report-row ${state.selectedReportId === report.report_id ? 'active' : ''} ${warning ? 'warning' : ''}`} key={report.report_id} aria-pressed={state.selectedReportId === report.report_id} onClick={() => state.selectReport(report.report_id)}>
        <span className="report-row-icon">{report.injection_detected ? <ShieldAlert size={14} /> : warning ? <AlertTriangle size={14} /> : <FileText size={14} />}</span>
        <span className="report-row-main"><strong>{report.report_id}<time>{report.time}</time></strong><span className="report-row-meta">{formatReportSource(report.source)} · {formatReportType(report.report_type)}</span><p>{humanizeAssessmentText(report.text)}</p><span className="report-row-footer"><ReportVerdictBadge verdict={report.verdict} />{current && <em>GEÇERLİ KARE</em>}</span></span>
      </button>;
    })}{!reports.length && <p className="summary-empty">Bu zaman ve filtrelerle eşleşen rapor yok.</p>}</div>
  </div>;
}

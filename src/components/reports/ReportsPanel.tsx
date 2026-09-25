import { AlertTriangle, FileText, ShieldAlert } from 'lucide-react';
import type { TrackingData } from '../../types/tracking';
import { usePlaybackStore } from '../../store/playback';
import { useReportStore, type ReportMode, type ReportSourceFilter } from '../../store/reports';
import { reportsAtTime } from '../../services/reports';
import { currentFrameAtTime } from '../../services/operation-summary';
import { ReportVerdictBadge } from './ReportVerdictBadge';

const modes: { value: ReportMode; label: string }[] = [{ value: 'all', label: 'All' }, { value: 'contradictions', label: 'Conflicts' }, { value: 'supporting', label: 'Supports' }, { value: 'manipulation', label: 'Injection' }];
const sources: { value: ReportSourceFilter; label: string }[] = [{ value: 'all', label: 'All sources' }, { value: 'official', label: 'Official' }, { value: 'third_party', label: 'Third party' }];

export function ReportsPanel({ data }: { data: TrackingData }) {
  const time = usePlaybackStore(state => Math.floor(state.currentTime));
  const state = useReportStore(), reports = reportsAtTime(data.analysis, time, state);
  const frame = currentFrameAtTime(data.analysis, time);
  return <div className="reports-panel">
    <div className="report-filter-group" role="group" aria-label="Report verdict filter">{modes.map(mode => <button key={mode.value} aria-pressed={state.mode === mode.value} onClick={() => state.setMode(mode.value)}>{mode.label}</button>)}</div>
    <div className="report-source-filter" role="group" aria-label="Report source filter">{sources.map(source => <button key={source.value} aria-pressed={state.source === source.value} onClick={() => state.setSource(source.value)}>{source.label}</button>)}</div>
    <div className="report-list-heading"><span>{reports.length} reports known</span><small>Future reports hidden</small></div>
    <div className="report-list">{reports.slice().reverse().map(report => {
      const current = !!frame && report.related_frames.includes(frame.frame_id), warning = report.verdict === 'celisir' || report.verdict === 'manipulasyon';
      return <button className={`report-row ${state.selectedReportId === report.report_id ? 'active' : ''} ${warning ? 'warning' : ''}`} key={report.report_id} aria-pressed={state.selectedReportId === report.report_id} onClick={() => state.selectReport(report.report_id)}>
        <span className="report-row-icon">{report.injection_detected ? <ShieldAlert size={14} /> : warning ? <AlertTriangle size={14} /> : <FileText size={14} />}</span>
        <span className="report-row-main"><strong>{report.report_id}<time>{report.time}</time></strong><span className="report-row-meta">{report.source.replace('_', ' ')} · {report.report_type}</span><p>{report.text}</p><span className="report-row-footer"><ReportVerdictBadge verdict={report.verdict} />{current && <em>CURRENT FRAME</em>}</span></span>
      </button>;
    })}{!reports.length && <p className="summary-empty">No reports match the current time and filters.</p>}</div>
  </div>;
}

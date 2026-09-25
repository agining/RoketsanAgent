import type { AnalysisData, AnalysisReportView } from '../types/analysis';
import type { ReportMode, ReportSourceFilter } from '../store/reports';
import { clockMinutes, reportId } from './analysis';
export interface ReportFilters { mode: ReportMode; source: ReportSourceFilter }
export function reportMatchesFilters(report: AnalysisReportView, filters: ReportFilters) {
  if (filters.source !== 'all' && report.source !== filters.source) return false;
  if (filters.mode === 'contradictions' && report.verdict !== 'CONTRADICTED' && report.contradicted_checks === 0) return false;
  if (filters.mode === 'supporting' && report.verdict !== 'SUPPORTED') return false;
  if (filters.mode === 'manipulation') return false;
  return true;
}
export function allReports(analysis: AnalysisData): AnalysisReportView[] {
  return analysis.entities.flatMap(entity => entity.reports.map((report, index) => ({
    ...report, report_id: reportId(entity.track_id, report.time, index), zone: entity.latest_position.zone,
    summary: report.reasons.join(' '), related_frames: [], matched_vehicle_id: entity.entity_id, injection_detected: false as const,
  })));
}
export function reportsAtTime(analysis: AnalysisData, playbackSeconds: number, filters: ReportFilters = { mode: 'all', source: 'all' }) {
  const minute = playbackSeconds / 60;
  return allReports(analysis).filter(report => clockMinutes(report.time) <= minute && reportMatchesFilters(report, filters));
}
export function checkText(value: unknown): string {
  if (value === null || value === undefined) return 'Mevcut değil';
  if (Array.isArray(value)) return value.join(', ') || 'Yok';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

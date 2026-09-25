import type { AnalysisData, AnalysisReport } from '../types/analysis';
import type { ReportMode, ReportSourceFilter } from '../store/reports';
import { clockMinutes } from './operation-summary';

export interface ReportFilters { mode: ReportMode; source: ReportSourceFilter }

export function reportMatchesFilters(report: AnalysisReport, filters: ReportFilters) {
  if (filters.source !== 'all' && report.source !== filters.source) return false;
  if (filters.mode === 'contradictions' && report.verdict !== 'celisir') return false;
  if (filters.mode === 'supporting' && report.verdict !== 'destekler') return false;
  if (filters.mode === 'manipulation' && report.verdict !== 'manipulasyon' && !report.injection_detected) return false;
  return true;
}

export function reportsAtTime(analysis: AnalysisData, playbackSeconds: number, filters: ReportFilters = { mode: 'all', source: 'all' }) {
  const minute = playbackSeconds / 60;
  return (analysis.reports ?? []).filter(report => clockMinutes(report.time) <= minute && reportMatchesFilters(report, filters));
}

export function checkText(value: unknown): string {
  if (value === null || value === undefined) return 'Not available';
  if (Array.isArray(value)) return value.join(', ') || 'None';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

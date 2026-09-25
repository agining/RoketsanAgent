import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { parseAnalysis } from './analysisService';
import { allReports, reportMatchesFilters, reportsAtTime } from './reports';

const analysis = parseAnalysis(JSON.parse(readFileSync(new URL('../../backend/analysis.json', import.meta.url), 'utf8')));

describe('report projections', () => {
  it('flattens entity reports and never exposes future reports', () => {
    expect(allReports(analysis)).toHaveLength(24);
    expect(reportsAtTime(analysis, 12 * 3600)).toHaveLength(0);
    expect(reportsAtTime(analysis, 15 * 3600)).toHaveLength(24);
  });
  it('filters report sources and evidence outcomes', () => {
    const reports = allReports(analysis);
    expect(reports.some(report => reportMatchesFilters(report, { mode: 'contradictions', source: 'all' }))).toBe(true);
    expect(reports.filter(report => reportMatchesFilters(report, { mode: 'supporting', source: 'official' })).every(report => report.verdict === 'SUPPORTED' && report.source === 'official')).toBe(true);
  });
});

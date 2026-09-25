import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { analysisForTrack, buildAnalysisIndex, untrackedAtTime, vehicleType } from './analysis';
import { parseAnalysis } from './analysisService';

const analysis = parseAnalysis(JSON.parse(readFileSync(new URL('../../backend/analysis.json', import.meta.url), 'utf8')));

describe('current analysis model', () => {
  it('parses and indexes the real pipeline output', () => {
    const index = buildAnalysisIndex(analysis);
    expect(index.byTrackId.size).toBe(analysis.operation_summary.tracked_entity_count);
    expect(index.untracked).toHaveLength(analysis.operation_summary.untracked_observation_count);
  });
  it('does not expose tracked or untracked observations before their observation time', () => {
    const index = buildAnalysisIndex(analysis);
    expect(analysisForTrack(index, 'T0001', 12 * 3600)).toBeNull();
    expect(analysisForTrack(index, 'T0001', 12 * 3600 + 5 * 60)?.track_id).toBe('T0001');
    expect(untrackedAtTime(index, 13 * 3600)).toHaveLength(1);
    expect(untrackedAtTime(index, 13 * 3600 + 5 * 60)).toHaveLength(0);
  });
  it('derives display vehicle types without changing the backend payload', () => {
    const index = buildAnalysisIndex(analysis);
    expect(vehicleType(index.byTrackId.get('T0001')![0])).toBe('van');
    expect(vehicleType(index.untracked[0])).toBe('van');
  });
  it('rejects the retired frames/summary schema', () => {
    expect(() => parseAnalysis({ frames: {}, summary: {} })).toThrow('generated_at');
  });
});

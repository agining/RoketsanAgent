import { describe, expect, it } from 'vitest';
import { toApiRiskLevel, toRiskLevel } from '../types/analysis';
import { formatCheckValue, formatDecisionStatus, formatReportVerdict, formatRiskLevel, formatScenario } from './formatters';

describe('formatters', () => {
  it('maps API risk levels both ways', () => {
    expect(['DUSUK', 'ORTA', 'YUKSEK', 'KRITIK', 'X'].map(toRiskLevel)).toEqual(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'UNKNOWN']);
    expect(toApiRiskLevel('HIGH')).toBe('YUKSEK');
    expect(toApiRiskLevel('UNKNOWN')).toBeNull();
    expect(formatRiskLevel('KRITIK')).toBe('Kritik');
    expect(formatRiskLevel('MEDIUM')).toBe('Orta');
  });

  it('labels API enums in Turkish and humanizes unknown values', () => {
    expect(formatScenario('APPROACH_WITH_STOPS')).toBe('Duraklamalı yaklaşma');
    expect(formatDecisionStatus('onay_bekliyor')).toBe('Analist onayı bekliyor');
    expect(formatReportVerdict('celisir')).toBe('Çelişiyor');
    expect(formatScenario('NEW_SCENARIO')).toBe('New scenario');
  });

  it('renders report check values', () => {
    expect(formatCheckValue(true)).toBe('Evet');
    expect(formatCheckValue(null)).toBe('Mevcut değil');
    expect(formatCheckValue([1, 'a'])).toBe('1, a');
  });
});

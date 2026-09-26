import { describe, expect, it } from 'vitest';
import { formatAlertForSpeech, sanitizeSpeechText } from './speechFormatter';
import type { AnalysisAlert } from '../../types/analysis';

describe('speechFormatter', () => {
  it('sanitizes technical terms into natural Turkish speech', () => {
    const raw = '11.1 m/s hızla 900 m yaklaştı. ETA 1.5 dk.';
    const sanitized = sanitizeSpeechText(raw);
    expect(sanitized).toContain('metre bölü saniye');
    expect(sanitized).toContain('metre yaklaştı');
    expect(sanitized).toContain('tahmini varış süresi');
    expect(sanitized).toContain('dakika');
  });

  it('formats critical tactical alert with vehicle, zone and ETA', () => {
    const mockAlert: AnalysisAlert = {
      kind: 'frame_vehicle',
      vehicle_id: 'img_006140_v0',
      frame_id: 'img_006140',
      track_id: 'T0106',
      time: '12:05',
      zone: 'Güney Kapısı Yaklaşımı',
      label: 'van',
      risk_level: 'CRITICAL',
      scenario: 'DIRECT_FAST_APPROACH',
      distance_to_base_m: 684.5,
      eta_min: 1.5,
      lat: 39.915704,
      lon: 32.853702,
      reason: '110 dk bekledikten sonra üsse doğru 11.1 m/s ile ilerliyor.',
      engine_risk_level: 'CRITICAL',
      decision_status: 'CONFIRMED',
    };

    const text = formatAlertForSpeech(mockAlert);
    expect(text).toContain('Kritik!');
    expect(text).toContain('T 106');
    expect(text).toContain('minibüs');
    expect(text).toContain('hızlı yaklaşma');
  });
});

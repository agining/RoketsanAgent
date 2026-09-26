import type { AnalysisAlert, RiskLevel, VehicleType } from '../../types/analysis';
import type { ApiAssessment } from '../../types/api';

/**
 * Normalizes text for clear natural Turkish speech.
 * Converts technical abbreviations into speech-friendly words.
 */
export function sanitizeSpeechText(text: string): string {
  if (!text) return '';
  return text
    .replace(/\bm\/s\b/gi, ' metre bölü saniye')
    .replace(/\bkm\/s\b/gi, ' kilometre bölü saat')
    .replace(/\bkm\b/gi, ' kilometre')
    .replace(/\bm\b/gi, ' metre')
    .replace(/\bdk\b/gi, ' dakika')
    .replace(/\bsn\b/gi, ' saniye')
    .replace(/\bETA\b/gi, 'tahmini varış süresi')
    .replace(/\bT(\d{2,4})\b/g, 'T $1') // E.g., T0106 -> "T 0106" for natural pronunciation
    .replace(/\bimg_0*(\d+)/gi, 'kare $1')
    .replace(/[_]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

const VEHICLE_NAMES: Record<VehicleType, string> = {
  car: 'otomobil',
  van: 'minibüs',
  truck: 'kamyon',
  bus: 'otobüs',
  unknown: 'araç',
};

export const SCENARIO_SPEECH_NAMES: Record<string, string> = {
  DIRECT_FAST_APPROACH: 'hızlı yaklaşma',
  APPROACH_WITH_STOPS: 'kademeli yaklaşma',
  LOITER_NEAR_BASE: 'üs çevresinde tur',
  FRIENDLY_PATROL: 'devriye',
  APPROACHING: 'yaklaşıyor',
  TRANSIT: 'transit geçiş',
  MOVING_AWAY: 'uzaklaşıyor',
  PARKED: 'durdu',
  UNTRACKED: 'izsiz hedef',
  FILTERED_LOW_CONF: 'şüpheli tespit',
};

/**
 * Formats a tactical analysis alert into a punchy, ultra-concise Turkish spoken alert.
 * Spoken in ~0.6 - 1.0 second so playback never lags behind the real-time simulation clock.
 */
export function formatAlertForSpeech(alert: AnalysisAlert, extraCount = 0): string {
  const riskIntro = alert.risk_level === 'CRITICAL' ? 'Kritik!' :
                    alert.risk_level === 'HIGH' ? 'Yüksek Risk!' : 'Dikkat!';
  const targetId = alert.track_id ? `T ${alert.track_id.replace(/^T0*/, '')}` : (alert.vehicle_id ? 'hedef' : 'araç');
  const vehicleType = alert.label ? VEHICLE_NAMES[alert.label] ?? '' : '';

  let action = '';
  if (alert.scenario && SCENARIO_SPEECH_NAMES[alert.scenario]) {
    action = SCENARIO_SPEECH_NAMES[alert.scenario];
  } else if (alert.reason) {
    action = sanitizeSpeechText(alert.reason).split('.')[0].slice(0, 30);
  }

  const vehicleStr = vehicleType ? ` ${vehicleType}` : '';
  const extraNotice = extraCount > 0 ? ` artı ${extraCount} hedef` : '';

  return `${riskIntro} ${targetId}${vehicleStr}, ${action}.${extraNotice}`.replace(/\s+/g, ' ').trim();
}

/**
 * Formats an LLM assessment headline and vehicle highlight for speech.
 */
export function formatAssessmentForSpeech(assessment: ApiAssessment): string {
  const riskIntro = assessment.risk_level === 'KRITIK' ? 'Kritik durum tespiti!' : 'Bölge durum değerlendirmesi.';
  const headline = assessment.headline ? sanitizeSpeechText(assessment.headline).split('.')[0].slice(0, 50) : '';
  return `${riskIntro} ${headline}`.trim();
}

import type { AnalysisAlert, RiskLevel, VehicleType } from '../../types/analysis';
import type { ApiAssessment } from '../../types/api';

/**
 * Normalizes text for clear natural Turkish speech.
 * Converts technical abbreviations into speech-friendly words.
 */
export function sanitizeSpeechText(text: string): string {
  if (!text) return '';
  return text
    .replace(/(\d+(?:[.,]\d+)?)\s*m\/s\b/gi, '$1 metre bölü saniye')
    .replace(/(\d+(?:[.,]\d+)?)\s*km\/s\b/gi, '$1 kilometre bölü saat')
    .replace(/(\d+(?:[.,]\d+)?)\s*km\b/gi, '$1 kilometre')
    .replace(/(\d+(?:[.,]\d+)?)\s*m\b/gi, '$1 metre')
    .replace(/(\d+(?:[.,]\d+)?)\s*dk\b/gi, '$1 dakika')
    .replace(/(\d+(?:[.,]\d+)?)\s*sn\b/gi, '$1 saniye')
    .replace(/\bETA\b/gi, 'tahmini varış süresi')
    .replace(/\bT0*(\d{2,4})\b/g, 'takip numarası $1')
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
 * Formats a tactical analysis alert into a short but intelligible Turkish spoken alert.
 */
export function formatAlertForSpeech(alert: AnalysisAlert, extraCount = 0): string {
  const riskIntro = alert.risk_level === 'CRITICAL' ? 'Kritik uyarı.' :
                    alert.risk_level === 'HIGH' ? 'Yüksek risk uyarısı.' : 'Dikkat.';
  const targetId = alert.track_id
    ? `Takip numarası ${alert.track_id.replace(/^T0*/, '')}`
    : (alert.vehicle_id ? 'Hedef araç' : 'Araç');
  const vehicleType = alert.label ? VEHICLE_NAMES[alert.label] ?? '' : '';

  let action = '';
  if (alert.scenario && SCENARIO_SPEECH_NAMES[alert.scenario]) {
    action = SCENARIO_SPEECH_NAMES[alert.scenario];
  } else if (alert.reason) {
    action = sanitizeSpeechText(alert.reason).split('.')[0].slice(0, 30);
  }

  const vehicleStr = vehicleType ? `, ${vehicleType}` : '';
  const zoneText = alert.zone ? ` Bölge: ${sanitizeSpeechText(alert.zone)}.` : '';
  const extraNotice = extraCount > 0 ? ` Ayrıca ${extraCount} hedef daha var.` : '';

  const actionText = action ? ` Durum: ${action}.` : '';
  return `${riskIntro} ${targetId}${vehicleStr}.${zoneText}${actionText}${extraNotice}`.replace(/\s+/g, ' ').trim();
}

/**
 * Formats an LLM assessment headline and vehicle highlight for speech.
 */
export function formatAssessmentForSpeech(assessment: ApiAssessment): string {
  const riskIntro = assessment.risk_level === 'KRITIK' ? 'Kritik durum tespiti!' : 'Bölge durum değerlendirmesi.';
  const headline = assessment.headline ? sanitizeSpeechText(assessment.headline).split('.')[0].slice(0, 50) : '';
  return `${riskIntro} ${headline}`.trim();
}

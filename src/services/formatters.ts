import type { AttentionLevel, BehaviorType, MovementState, ReportSource, ReportVerdict, RiskLevel, VehicleType } from '../types/analysis';

const unknown = 'Bilinmiyor';

const vehicleLabels: Record<VehicleType, string> = {
  car: 'Otomobil',
  van: 'Van',
  truck: 'Kamyon',
  bus: 'Otobüs',
  unknown,
};

const riskLabels: Record<RiskLevel, string> = {
  LOW: 'Düşük',
  MEDIUM: 'Orta',
  HIGH: 'Yüksek',
  CRITICAL: 'Kritik',
  UNKNOWN: unknown,
};

const attentionLabels: Record<AttentionLevel, string> = {
  ROUTINE: 'Rutin takip',
  MONITOR: 'İzlemede tut',
  PRIORITY: 'Öncelikli takip',
  IMMEDIATE: 'Acil müdahale',
  UNKNOWN: unknown,
};

const movementLabels: Record<MovementState, string> = {
  APPROACHING_BASE: 'Üsse yaklaşıyor',
  LEAVING_BASE: 'Üsten uzaklaşıyor',
  TRANSIT: 'Geçiş halinde',
  STATIONARY: 'Hareketsiz',
};

const behaviorLabels: Record<BehaviorType, string> = {
  NORMAL_PATH: 'Normal rota',
  LOITERING: 'Bölgede dolaşma paterni',
  CIRCLING: 'Dairesel hareket paterni',
};

const reportVerdictLabels: Record<ReportVerdict, string> = {
  SUPPORTED: 'Destekleniyor',
  PARTIAL: 'Kısmen destekleniyor',
  CONTRADICTED: 'Çelişkili',
  UNVERIFIED: 'Doğrulanamadı',
  IRRELEVANT: 'İlgisiz',
};

const reportSourceLabels: Record<ReportSource, string> = {
  official: 'Resmi kaynak',
  third_party: 'Üçüncü taraf kaynak',
};

const evidenceLabels: Record<string, string> = {
  SUPPORTED: 'Destekleniyor',
  CONTRADICTED: 'Çelişkili',
  MOVING: 'Hareket halinde',
  'APPROACHING BASE': 'Üsse yaklaşıyor',
  'LEAVING BASE': 'Üsten uzaklaşıyor',
  APPROACHING_BASE: 'Üsse yaklaşma göstergesi',
  LEAVING_BASE: 'Üsten uzaklaşma göstergesi',
  TRANSIT: 'Geçiş hareketi',
  STATIONARY: 'Hareketsizlik',
  NORMAL_PATH: 'Normal rota paterni',
  LOITERING: 'Bölgede dolaşma paterni',
  CIRCLING: 'Dairesel hareket paterni',
  REPORT_CONTRADICTION: 'Saha raporu ile sensör verisi çelişkili',
  CLASS_INCONSISTENCY: 'Araç sınıflandırması tutarsız',
  ETA_AVAILABLE: 'Tahmini varış süresi mevcut',
  HIGH_HEADING_CHANGE: 'Yüksek yön değişimi',
  LOW_PATH_EFFICIENCY: 'Düşük rota verimliliği',
  CLOSE_TO_BASE: 'Üsse yakın konum',
  MIN_DISTANCE_LOW: 'Üsse düşük minimum mesafe',
  SLOW_MOVEMENT: 'Yavaş hareket',
  STOP_DETECTED: 'Duraklama tespit edildi',
  REPORT_SUPPORTED: 'Saha raporu sensör verisiyle destekleniyor',
};

const technicalTerms: Record<string, string> = {
  latest_movement: 'güncel hareket durumu',
  latest_behavior: 'güncel davranış analizi',
  current_evidence_flags: 'güncel kanıt göstergeleri',
  historical_evidence_flags: 'geçmiş kanıt göstergeleri',
  movement_state: 'hareket durumu',
  risk_level: 'risk seviyesi',
  recommended_attention: 'önerilen takip seviyesi',
  confidence: 'değerlendirme güveni',
  key_evidence: 'temel bulgular',
  uncertainties: 'belirsizlikler',
  reasoning: 'değerlendirme gerekçeleri',
  vehicle_class: 'araç sınıfı',
  track_id: 'track kimliği',
  eta_min: 'tahmini varış süresi',
  distance_to_base_m: 'üsse mesafe',
  minimum_distance_to_base_m: 'üsse en düşük mesafe',
  path_efficiency: 'rota verimliliği',
  heading_change_total_deg: 'toplam yön değişimi',
  closing_speed_mps: 'üsse yaklaşma hızı',
  speed_mps: 'hız',
};

export const formatUnavailable = () => 'Mevcut değil';
export const formatAllOption = () => 'Tümü';
export const formatVehicleClass = (value: VehicleType | string | null | undefined) => vehicleLabels[value as VehicleType] ?? humanizeToken(value);
export const formatRiskLevel = (value: RiskLevel | string | null | undefined) => riskLabels[value as RiskLevel] ?? humanizeToken(value);
export const formatAttention = (value: AttentionLevel | string | null | undefined) => attentionLabels[value as AttentionLevel] ?? humanizeToken(value);
export const formatMovementState = (value: MovementState | string | null | undefined) => movementLabels[value as MovementState] ?? humanizeToken(value);
export const formatBehavior = (value: BehaviorType | string | null | undefined) => behaviorLabels[value as BehaviorType] ?? humanizeToken(value);
export const formatReportVerdict = (value: ReportVerdict | string | null | undefined) => reportVerdictLabels[value as ReportVerdict] ?? humanizeToken(value);
export const formatReportSource = (value: ReportSource | string | null | undefined) => reportSourceLabels[value as ReportSource] ?? humanizeToken(value);
export const formatEvidenceFlag = (value: string | null | undefined) => evidenceLabels[value ?? ''] ?? humanizeToken(value);
export const formatReportType = (value: string | null | undefined) => humanizeToken(value);

export function humanizeToken(value: string | null | undefined): string {
  if (!value) return unknown;
  const mapped = evidenceLabels[value] ?? technicalTerms[value];
  if (mapped) return mapped;
  return value
    .replace(/\./g, ' ')
    .replace(/_/g, ' ')
    .toLocaleLowerCase('tr-TR')
    .replace(/\b\p{L}/gu, letter => letter.toLocaleUpperCase('tr-TR'));
}

export function humanizeAssessmentText(value: string): string {
  let text = value;
  const replacements = {
    ...technicalTerms,
    ...Object.fromEntries(Object.entries(evidenceLabels).map(([key, label]) => [key, label.toLocaleLowerCase('tr-TR')])),
    ...Object.fromEntries(Object.entries(riskLabels).map(([key, label]) => [key, label.toLocaleLowerCase('tr-TR')])),
    ...Object.fromEntries(Object.entries(attentionLabels).map(([key, label]) => [key, label.toLocaleLowerCase('tr-TR')])),
    ...Object.fromEntries(Object.entries(movementLabels).map(([key, label]) => [key, label.toLocaleLowerCase('tr-TR')])),
    ...Object.fromEntries(Object.entries(behaviorLabels).map(([key, label]) => [key, label.toLocaleLowerCase('tr-TR')])),
  };
  Object.entries(replacements).sort((a, b) => b[0].length - a[0].length).forEach(([token, label]) => {
    text = text.replace(new RegExp(`\\b${token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'g'), label);
  });
  return text
    .replace(/\blatest movement\b/gi, 'güncel hareket durumu')
    .replace(/\blatest behavior\b/gi, 'güncel davranış analizi')
    .replace(/\bcurrent evidence flags\b/gi, 'güncel kanıt göstergeleri')
    .replace(/\bhistorical evidence flags\b/gi, 'geçmiş kanıt göstergeleri')
    .replace(/\bmovement history\b/gi, 'hareket geçmişi')
    .replace(/\bbehavior history\b/gi, 'davranış geçmişi')
    .replace(/\breport contradiction\b/gi, 'saha raporu ile sensör verisi çelişkisi')
    .replace(/\bclass inconsistency\b/gi, 'araç sınıflandırması tutarsızlığı')
    .replace(/\boutside track\b/gi, 'kayıt aralığı dışında')
    .replace(/\bbase\b/gi, 'üs')
    .replace(/([A-Za-z]+)_([A-Za-z_]+)/g, match => humanizeToken(match).toLocaleLowerCase('tr-TR'))
    .replace(/\s+/g, ' ')
    .trim();
}

export function evidenceSentence(flags: string[]): string {
  if (!flags.length) return 'Bu bölüm için kanıt göstergesi yok.';
  const labels = flags.map(formatEvidenceFlag);
  if (labels.length === 1) return `${labels[0]} görülüyor.`;
  return `${labels.slice(0, -1).join(', ')} ve ${labels.at(-1)} görülüyor.`;
}

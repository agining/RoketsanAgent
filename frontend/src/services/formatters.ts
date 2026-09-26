import type { ObservationSource, RiskLevel, VehicleType } from '../types/analysis';
import { toRiskLevel } from '../types/analysis';

const unknown = 'Bilinmiyor';

const vehicleLabels: Record<VehicleType, string> = { car: 'Otomobil', van: 'Van', truck: 'Kamyon', bus: 'Otobüs', unknown };

const riskLabels: Record<RiskLevel, string> = { LOW: 'Düşük', MEDIUM: 'Orta', HIGH: 'Yüksek', CRITICAL: 'Kritik', UNKNOWN: unknown };

/** Engine scenarios (app/risk.py). */
const scenarioLabels: Record<string, string> = {
  DIRECT_FAST_APPROACH: 'Doğrudan hızlı yaklaşma',
  APPROACH_WITH_STOPS: 'Duraklamalı yaklaşma',
  LOITER_NEAR_BASE: 'Üs yakınında tur atma',
  FRIENDLY_PATROL: 'Sabit yarıçaplı devriye',
  APPROACHING: 'Üsse yönelmiş hareket',
  TRANSIT: 'Geçiş',
  MOVING_AWAY: 'Üsten uzaklaşıyor',
  PARKED: 'Park halinde',
  UNTRACKED: 'İzi olmayan araç',
  FILTERED_LOW_CONF: 'Düşük güvenli tespit (elendi)',
};

/** decision_status values documented in app/api.py. */
const decisionLabels: Record<string, string> = {
  motor: 'Motor kararı',
  uzlasi: 'Uzlaşı (motor + LLM)',
  llm_yukseltti: 'LLM yükseltti',
  fazla_yukseltme: 'Aşırı yükseltme — kısmen uygulandı',
  motor_kesin: 'Motor kesin',
  llm_dusurdu: 'LLM düşürdü',
  belirsiz: 'Belirsiz — motor sınırda',
  reddedildi: 'LLM önerisi reddedildi',
  llm_belirtmedi: 'LLM belirtmedi',
  onay_bekliyor: 'Analist onayı bekliyor',
  analist_karari: 'Analist kararı',
  bilinmiyor: 'Değerlendirme yok',
};

const verdictLabels: Record<string, string> = {
  destekler: 'Destekliyor',
  celisir: 'Çelişiyor',
  kismen_uyumlu: 'Kısmen uyumlu',
  dogrulanamaz: 'Doğrulanamaz',
  ilgisiz: 'İlgisiz',
  manipulasyon: 'Manipülasyon',
};

const reportSourceLabels: Record<string, string> = { official: 'Resmi kaynak', third_party: 'Üçüncü taraf kaynak' };

const reportTypeLabels: Record<string, string> = {
  DOGRU_GOZLEM: 'Doğru gözlem', YANLIS_TIP: 'Yanlış araç tipi', YANLIS_DAVRANIS: 'Yanlış davranış',
  YANILTICI_OLAGAN: 'Yanıltıcı "olağan" bildirimi', DOST_TEYITLI: 'Teyitli dost bildirimi', DOST_ALDATICI: 'Teyitsiz dost iddiası',
  HAYALET_KARE_ICI: 'Karede olmayan araç', HAYALET_KARE_DISI: 'Kare dışı bildirim', BOLGE_NORMAL: '"Trafik normal" bildirimi',
  ESKI_IHBAR: 'Eski ihbar', BOLGE_GOZLEM: 'Bölge gözlemi', GENEL_TATBIKAT: 'Genel tatbikat bildirimi', MANIPULASYON: 'Talimat enjeksiyonu',
  ZAMAN_KAYMASI: 'Zaman kayması', ORNEK_ZAMAN_UYUMSUZ: 'Zaman uyumsuzluğu', BILINMIYOR: unknown,
};

const distTrendLabels: Record<string, string> = {
  azaliyor: 'Azalıyor', artiyor: 'Artıyor', once_azalip_sonra_artiyor: 'Önce azalıp sonra artıyor', sabit: 'Sabit',
};

const sourceLabels: Record<ObservationSource, string> = {
  detection: 'Karede tespit edildi', track_only: 'İzden kurtarıldı (model kaçırmış)', offframe: 'Kare dışı iz',
};

const stageLabels: Record<string, string> = { tespit: 'Tespit', konumlandirma: 'Konumlandırma', hareket: 'Hareket analizi', risk: 'Risk analizi' };

const checkLabels: Record<string, string> = {
  kare_icinde: 'Kare içinde', konum: 'Konum', konum_cekim_aninda: 'Konum (çekim anında)', konum_rapor_saatinde: 'Konum (rapor saatinde)',
  mesafe_m: 'Mesafe (m)', tip: 'Araç tipi', tip_uyan: 'Tipi uyan araç', zaman: 'Zaman', davranis: 'Davranış',
  hiz_rapor_saatinde_mps: 'Hız (rapor saatinde, m/s)', rapor_saatinde_eslesen_iz_sayisi: 'Rapor saatinde eşleşen iz',
  bolgede_uyan_arac_sayisi: 'Bölgede uyan araç sayısı',
};

export const formatUnavailable = () => 'Mevcut değil';
export const formatAllOption = () => 'Tümü';
export const formatVehicleClass = (value: VehicleType | string | null | undefined) => vehicleLabels[value as VehicleType] ?? humanizeToken(value);
export const formatRiskLevel = (value: RiskLevel | string | null | undefined) => riskLabels[value as RiskLevel] ?? riskLabels[toRiskLevel(value)];
export const formatScenario = (value: string | null | undefined) => (value && scenarioLabels[value]) ?? humanizeToken(value);
export const formatDecisionStatus = (value: string | null | undefined) => (value && decisionLabels[value]) ?? humanizeToken(value);
export const formatReportVerdict = (value: string | null | undefined) => (value && verdictLabels[value]) ?? humanizeToken(value);
export const formatReportSource = (value: string | null | undefined) => (value && reportSourceLabels[value]) ?? humanizeToken(value);
export const formatReportType = (value: string | null | undefined) => (value && reportTypeLabels[value]) ?? humanizeToken(value);
export const formatDistTrend = (value: string | null | undefined) => (value && distTrendLabels[value]) ?? humanizeToken(value);
export const formatSource = (value: ObservationSource | null | undefined) => (value && sourceLabels[value]) ?? unknown;
export const formatStage = (value: string | null | undefined) => (value && stageLabels[value]) ?? humanizeToken(value);
export const formatCheckKey = (value: string) => checkLabels[value] ?? humanizeToken(value);
export const formatMotorConfidence = (value: string | null | undefined) => value === 'net' ? 'Net' : value === 'sinirda' ? 'Sınırda' : humanizeToken(value);

export function humanizeToken(value: string | null | undefined): string {
  if (!value) return unknown;
  // API tokens are ASCII (no Turkish letters), so a locale-free lowercase is the safer guess for "I".
  const text = value.replace(/[._]/g, ' ').toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const finite = (value: number | null | undefined): value is number => typeof value === 'number' && Number.isFinite(value);
export const formatNumber = (value: number | null | undefined, digits = 1) => finite(value) ? value.toFixed(digits) : formatUnavailable();
export const formatMeters = (value: number | null | undefined) => finite(value) ? `${Math.round(value)} m` : formatUnavailable();
export const formatKm = (value: number | null | undefined) => finite(value) ? `${(value / 1000).toFixed(2)} km` : formatUnavailable();
export const formatSpeed = (value: number | null | undefined) => finite(value) ? `${value.toFixed(1)} m/s` : formatUnavailable();
export const formatDegrees = (value: number | null | undefined) => finite(value) ? `${Math.round(value)}°` : formatUnavailable();
export const formatMinutes = (value: number | null | undefined) => finite(value) ? `${value.toFixed(1)} dk` : formatUnavailable();
export const formatPercent = (value: number | null | undefined) => finite(value) ? `%${Math.round(value * 100)}` : formatUnavailable();
export const formatEpoch = (seconds: number | null | undefined) => finite(seconds)
  ? new Intl.DateTimeFormat('tr-TR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(seconds * 1000)) : formatUnavailable();

export function formatCheckValue(value: unknown): string {
  if (value === null || value === undefined) return formatUnavailable();
  if (typeof value === 'boolean') return value ? 'Evet' : 'Hayır';
  if (Array.isArray(value)) return value.map(formatCheckValue).join(', ') || 'Yok';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

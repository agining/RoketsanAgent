import { Camera, CheckCircle2, MapPin, Route, ScanSearch, ShieldCheck } from 'lucide-react';
import type { AnalysisReportView, AnalysisVehicle } from '../../types/analysis';
import { formatRiskLevel, formatUnavailable, formatVehicleClass, humanizeAssessmentText } from '../../services/formatters';

export function ReasoningTrace({ vehicle, reports }: { vehicle: AnalysisVehicle | null; reports: AnalysisReportView[] }) {
  if (!vehicle) return <section className="reasoning-trace"><div className="chart-heading"><h3>Değerlendirme izi</h3><span>Kanıt bekleniyor</span></div><p className="summary-empty">Bu playback anında araç analizi bilinmiyor.</p></section>;
  const f = vehicle.features, conflicts = reports.filter(report => report.verdict === 'CONTRADICTED').length;
  const steps = [
    { icon: Camera, name: 'Tespit', value: vehicle.source === 'track_only' ? 'Dedektör tarafından yakalanmayan track noktası' : `${formatVehicleClass(vehicle.label)} · ${vehicle.confidence == null ? 'güven değeri yok' : `%${Math.round(vehicle.confidence * 100)}`}` },
    { icon: MapPin, name: 'GPS', value: `${vehicle.lat.toFixed(5)}, ${vehicle.lon.toFixed(5)} · ${vehicle.dist_to_base_m.toFixed(0)} m` },
    { icon: Route, name: 'Track eşleşmesi', value: vehicle.track_id ? `${vehicle.track_id} · ${vehicle.track_match_m?.toFixed(1) ?? '—'} m` : 'Takipsiz tespit' },
    { icon: ScanSearch, name: 'Hareket analizi', value: f ? `${f.speed_now_mps == null ? formatUnavailable() : `${(Number(f.speed_now_mps) * 3.6).toFixed(1)} km/sa`} · ${humanizeAssessmentText(String(f.dist_trend ?? vehicle.scenario))}` : humanizeAssessmentText(vehicle.scenario) },
    { icon: ShieldCheck, name: 'Rapor doğrulama', value: `${reports.length} ilişkili rapor · ${conflicts} çelişki` },
    { icon: CheckCircle2, name: 'Risk sonucu', value: `${formatRiskLevel(vehicle.risk_level)} · ${humanizeAssessmentText(vehicle.scenario)}` },
  ];
  return <section className="reasoning-trace"><div className="chart-heading"><h3>Değerlendirme izi</h3><span>Deterministik pipeline</span></div><div className="reasoning-steps">{steps.map(({ icon: Icon, name, value }, index) => <div key={name}><span className="reasoning-index"><Icon size={12} /></span><span><b>{name}</b><small>{value}</small></span>{index < steps.length - 1 && <i>→</i>}</div>)}</div></section>;
}

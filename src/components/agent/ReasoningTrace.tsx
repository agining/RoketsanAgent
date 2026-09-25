import { Camera, CheckCircle2, MapPin, Route, ScanSearch, ShieldCheck } from 'lucide-react';
import type { AnalysisReport, AnalysisVehicle } from '../../types/analysis';

export function ReasoningTrace({ vehicle, reports }: { vehicle: AnalysisVehicle | null; reports: AnalysisReport[] }) {
  if (!vehicle) return <section className="reasoning-trace"><div className="chart-heading"><h3>Reasoning trace</h3><span>Awaiting evidence</span></div><p className="summary-empty">No vehicle analysis is known at this playback time.</p></section>;
  const f = vehicle.features, conflicts = reports.filter(report => report.verdict === 'celisir' || report.verdict === 'manipulasyon').length;
  const steps = [
    { icon: Camera, name: 'Detection', value: vehicle.source === 'track_only' ? 'Missed by detector' : `${vehicle.label ?? 'unknown'} · ${vehicle.confidence == null ? 'no confidence' : `${Math.round(vehicle.confidence * 100)}%`}` },
    { icon: MapPin, name: 'GPS', value: `${vehicle.lat.toFixed(5)}, ${vehicle.lon.toFixed(5)} · ${vehicle.dist_to_base_m.toFixed(0)} m` },
    { icon: Route, name: 'Track Match', value: vehicle.track_id ? `${vehicle.track_id} · ${vehicle.track_match_m?.toFixed(1) ?? '—'} m` : 'UNTRACKED' },
    { icon: ScanSearch, name: 'Movement Analysis', value: f ? `${f.speed_now_mps == null ? '—' : `${(Number(f.speed_now_mps) * 3.6).toFixed(1)} km/h`} · ${String(f.dist_trend ?? vehicle.scenario)}` : vehicle.scenario },
    { icon: ShieldCheck, name: 'Report Validation', value: `${reports.length} related · ${conflicts} conflicts` },
    { icon: CheckCircle2, name: 'Risk Result', value: `${vehicle.risk_level} · ${vehicle.scenario}` },
  ];
  return <section className="reasoning-trace"><div className="chart-heading"><h3>Reasoning trace</h3><span>Deterministic pipeline</span></div><div className="reasoning-steps">{steps.map(({ icon: Icon, name, value }, index) => <div key={name}><span className="reasoning-index"><Icon size={12} /></span><span><b>{name}</b><small>{value}</small></span>{index < steps.length - 1 && <i>→</i>}</div>)}</div></section>;
}

import { MapPin, Radar } from 'lucide-react';
import type { UntrackedObservation } from '../../types/analysis';
import { formatVehicleClass } from '../../services/formatters';

const distance = (meters: number) => meters < 1000 ? `${Math.round(meters)} m` : `${(meters / 1000).toFixed(2)} km`;

function DetectionCard({ item }: { item: UntrackedObservation }) {
  return <article className="untracked-card">
    <header><span className="untracked-icon"><Radar size={15} /></span><span><small>TAKİPSİZ TESPİT</small><strong>{formatVehicleClass(item.detection.class)}</strong></span><time>{item.capture_time}</time></header>
    <dl>
      <div><dt>Tespit güveni</dt><dd>%{Math.round(item.detection.confidence * 100)}</dd></div>
      <div><dt>Bölge</dt><dd>{item.position.zone}</dd></div>
      <div><dt>Üsse mesafe</dt><dd>{distance(item.position.distance_to_base_m)}</dd></div>
      <div><dt>Konum</dt><dd>{item.position.lat.toFixed(5)}, {item.position.lon.toFixed(5)}</dd></div>
    </dl>
    <p><MapPin size={12} />Kalıcı bir track ile eşleşmedi. Bu tespit için risk değerlendirmesi atanmadı.</p>
  </article>;
}

export function UntrackedDetections({ observations }: { observations: UntrackedObservation[] }) {
  return <article className="dashboard-panel untracked-section" aria-label="Takipsiz tespitler">
    <header><div><span className="panel-kicker">TAKİPSİZ TESPİTLER</span><h2>Track ile eşleşmeyen gözlemler</h2></div><span className="panel-total">{observations.length} tespit</span></header>
    {observations.length ? <div className="untracked-grid">{observations.map(item => <DetectionCard key={item.vehicle_id} item={item} />)}</div> : <div className="untracked-empty"><Radar size={20} /><span><strong>Takipsiz tespit yok</strong><small>Bu analizdeki tüm gözlemler bir track ile eşleşmiş.</small></span></div>}
  </article>;
}

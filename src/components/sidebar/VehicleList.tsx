import { useTrackingStore } from '../../store/tracking';
import type { filterVehicles } from '../../services/vehicle-filters';
import { humanizeAssessmentText } from '../../services/formatters';
export function VehicleList({ vehicles }: { vehicles: ReturnType<typeof filterVehicles> }) {
  const selected = useTrackingStore(state => state.selectedTrackId);
  const select = useTrackingStore(state => state.selectTrack), request = useTrackingStore(state => state.requestView);
  return <div className="vehicle-directory">{vehicles.map(vehicle => <button className={`track-row ${selected === vehicle.track.id ? 'active' : ''}`} key={vehicle.track.id} aria-pressed={selected === vehicle.track.id} onClick={() => { select(vehicle.track.id); request('vehicle'); }}>
    <span className="vehicle-row-main"><strong>{vehicle.track.id}</strong><small>{humanizeAssessmentText(vehicle.baseTrend ?? vehicle.motion)}</small></span><span className="vehicle-row-metrics"><strong>{vehicle.position ? `${vehicle.position.speedKmh.toFixed(1)} km/sa` : '—'}</strong><small>{vehicle.distanceKm != null ? `Üsse ${vehicle.distanceKm.toFixed(2)} km` : 'Kayıt aralığı dışında'}</small></span>
  </button>)}{!vehicles.length && <div className="empty-message">Bu anda eşleşen araç yok.<button className="text-action" onClick={() => useTrackingStore.getState().clearFilters()}>Filtreleri temizle</button></div>}</div>;
}

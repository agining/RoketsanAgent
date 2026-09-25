import { useTrackingStore } from '../../store/tracking';
import type { Zone } from '../../types/tracking';
import { ZONE_PROXIMITY_KM, type MovementFilter } from '../../services/vehicle-filters';
export function VehicleFilterPanel({ zones }: { zones: Zone[] }) {
  const state = useTrackingStore();
  const options: [MovementFilter, string][] = [['moving', 'Hareket halinde'], ['stationary', 'Hareketsiz'], ['approaching', 'Üsse yaklaşıyor'], ['leaving', 'Üsten uzaklaşıyor']];
  return <div className="filter-controls"><span className="section-eyebrow">HAREKET · HERHANGİ BİRİ EŞLEŞSİN</span><div className="movement-options">{options.map(([key, label]) => <label key={key}><input type="checkbox" checked={state.activeMovementStates.includes(key)} onChange={() => state.setFilters({ activeMovementStates: state.activeMovementStates.includes(key) ? state.activeMovementStates.filter(value => value !== key) : [...state.activeMovementStates, key] })} />{label}</label>)}</div>
    <label className="field-label">Bölgeye yakın<select aria-label="Seçili bölge" value={state.selectedZone ?? ''} onChange={event => state.setFilters({ selectedZone: event.target.value || null })}><option value="">Tüm bölgeler</option>{zones.map(zone => <option key={zone.name}>{zone.name}</option>)}</select></label>
    <p className="control-note">Merkezden {ZONE_PROXIMITY_KM * 1000} m mesafe içinde. Bölge sınırları sağlanmıyor.</p>
    <div className="speed-fields">{(['minSpeed', 'maxSpeed'] as const).map((key, index) => <label className="field-label" key={key}>{index ? 'En yüksek' : 'En düşük'} km/sa<input type="number" min="0" step="0.1" aria-label={index ? 'En yüksek hız' : 'En düşük hız'} value={state[key] ?? ''} placeholder="Fark etmez" onChange={event => state.setFilters({ [key]: event.target.value === '' ? null : Math.max(0, Number(event.target.value)) })} /></label>)}</div>
    {state.minSpeed !== null && state.maxSpeed !== null && state.minSpeed > state.maxSpeed && <p role="status" className="control-note">En düşük hız, en yüksek hızdan büyük; hiçbir araç eşleşmez.</p>}
    <button className="text-action" onClick={state.clearFilters}>Tüm filtreleri temizle</button></div>;
}

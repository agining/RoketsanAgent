import type { Zone } from '../../types/tracking';
import { useTrackingStore } from '../../store/tracking';
import { ZONE_PROXIMITY_KM } from '../../services/vehicle-filters';
export function ZoneList({ zones }: { zones: Zone[] }) {
  const selected = useTrackingStore(state => state.selectedZone), setFilters = useTrackingStore(state => state.setFilters), request = useTrackingStore(state => state.requestView);
  return <div className="zone-directory"><p className="control-note">Focus a zone center, or filter vehicles within {ZONE_PROXIMITY_KM * 1000} m.</p>{zones.map(zone => <div className="zone-row" key={zone.name}><button className="zone-focus" onClick={() => request('zone', zone.name)} aria-label={`Focus zone ${zone.name}`}><strong>{zone.name}</strong><small>{zone.center[0].toFixed(4)}, {zone.center[1].toFixed(4)}</small></button><button className="zone-filter" aria-label={`Filter near ${zone.name}`} aria-pressed={selected === zone.name} onClick={() => setFilters({ selectedZone: selected === zone.name ? null : zone.name })}>Near</button></div>)}</div>;
}

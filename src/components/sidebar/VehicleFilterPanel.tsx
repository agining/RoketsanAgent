import { useTrackingStore } from '../../store/tracking';
import type { Zone } from '../../types/tracking';
import { ZONE_PROXIMITY_KM, type MovementFilter } from '../../services/vehicle-filters';
export function VehicleFilterPanel({ zones }: { zones: Zone[] }) {
  const state = useTrackingStore();
  const options: [MovementFilter, string][] = [['moving', 'Moving'], ['stationary', 'Stationary'], ['approaching', 'Approaching base'], ['leaving', 'Leaving base']];
  return <div className="filter-controls"><span className="section-eyebrow">MOVEMENT · MATCH ANY</span><div className="movement-options">{options.map(([key, label]) => <label key={key}><input type="checkbox" checked={state.activeMovementStates.includes(key)} onChange={() => state.setFilters({ activeMovementStates: state.activeMovementStates.includes(key) ? state.activeMovementStates.filter(value => value !== key) : [...state.activeMovementStates, key] })} />{label}</label>)}</div>
    <label className="field-label">Near zone<select aria-label="Selected zone" value={state.selectedZone ?? ''} onChange={event => state.setFilters({ selectedZone: event.target.value || null })}><option value="">All zones</option>{zones.map(zone => <option key={zone.name}>{zone.name}</option>)}</select></label>
    <p className="control-note">Within {ZONE_PROXIMITY_KM * 1000} m of the center. Zone boundaries are not provided.</p>
    <div className="speed-fields">{(['minSpeed', 'maxSpeed'] as const).map((key, index) => <label className="field-label" key={key}>{index ? 'Maximum' : 'Minimum'} km/h<input type="number" min="0" step="0.1" aria-label={index ? 'Maximum speed' : 'Minimum speed'} value={state[key] ?? ''} placeholder="Any" onChange={event => state.setFilters({ [key]: event.target.value === '' ? null : Math.max(0, Number(event.target.value)) })} /></label>)}</div>
    {state.minSpeed !== null && state.maxSpeed !== null && state.minSpeed > state.maxSpeed && <p role="status" className="control-note">Minimum exceeds maximum; no vehicles match.</p>}
    <button className="text-action" onClick={state.clearFilters}>Clear all filters</button></div>;
}

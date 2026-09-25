import { useTrackingStore, type MapLayer, type MapMode } from '../../store/tracking';
const labels: Record<MapLayer, string> = { vehicles: 'Vehicle markers', reports: 'Report locations', routes: 'Vehicle routes', zones: 'Zones', base: 'Base', traveled: 'Traveled route', future: 'Future route' };
const modes: { value: MapMode; label: string }[] = [{ value: 'vehicle', label: 'Vehicle' }, { value: 'risk', label: 'Risk' }, { value: 'density', label: 'Density' }];
export function LayerControls() {
  const state = useTrackingStore();
  return <div className="layer-controls"><div className="layer-mode-control"><span>Map mode</span><div>{modes.map(mode => <button key={mode.value} aria-pressed={state.mapMode === mode.value} onClick={() => state.setMapMode(mode.value)}>{mode.label}</button>)}</div></div>{(Object.keys(labels) as MapLayer[]).map(layer => <label key={layer}><input type="checkbox" checked={state.layers[layer]} onChange={() => state.toggleLayer(layer)} />{labels[layer]}</label>)}<p className="control-note">Vehicle routes is the master switch for traveled and future segments.</p></div>;
}

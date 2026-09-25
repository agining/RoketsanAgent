import { useTrackingStore, type MapLayer } from '../../store/tracking';
const labels: Record<MapLayer, string> = { vehicles: 'Vehicle markers', routes: 'Vehicle routes', zones: 'Zones', base: 'Base', traveled: 'Traveled route', future: 'Future route' };
export function LayerControls() {
  const layers = useTrackingStore(state => state.layers), toggle = useTrackingStore(state => state.toggleLayer);
  return <div className="layer-controls">{(Object.keys(labels) as MapLayer[]).map(layer => <label key={layer}><input type="checkbox" checked={layers[layer]} onChange={() => toggle(layer)} />{labels[layer]}</label>)}<p className="control-note">Vehicle routes is the master switch for traveled and future segments.</p></div>;
}

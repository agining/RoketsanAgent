import { useTrackingStore, type MapLayer, type MapMode } from '../../store/tracking';
const labels: Record<MapLayer, string> = { vehicles: 'Araç markerları', untracked: 'Takipsiz tespitler', reports: 'Rapor konumları', routes: 'Araç rotaları', zones: 'Bölgeler', base: 'Üs', traveled: 'Gidilen rota', future: 'Kalan rota' };
const modes: { value: MapMode; label: string }[] = [{ value: 'vehicle', label: 'Araç' }, { value: 'risk', label: 'Risk' }, { value: 'density', label: 'Yoğunluk' }];
export function LayerControls() {
  const state = useTrackingStore();
  return <div className="layer-controls"><div className="layer-mode-control"><span>Harita modu</span><div>{modes.map(mode => <button key={mode.value} aria-pressed={state.mapMode === mode.value} onClick={() => state.setMapMode(mode.value)}>{mode.label}</button>)}</div></div>{(Object.keys(labels) as MapLayer[]).map(layer => <label key={layer}><input type="checkbox" checked={state.layers[layer]} onChange={() => state.toggleLayer(layer)} />{labels[layer]}</label>)}<p className="control-note">Araç rotaları, gidilen ve kalan rota segmentleri için ana kontroldür.</p></div>;
}

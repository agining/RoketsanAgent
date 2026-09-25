import { Crosshair, Focus, LocateFixed, Truck, X, PanelRightClose } from 'lucide-react';
import { useWorkspaceStore } from '../store/workspace';
import { Button } from './ui/button';
import { VehicleCharts } from './VehicleCharts';
import { useTrackingStore } from '../store/tracking';
import { usePlaybackStore } from '../store/playback';
import { formatTime } from '../services/playback';
import { formatDuration, selectedVehicleMetrics } from '../services/vehicle-metrics';
import type { BaseLocation, VehicleTrack } from '../types/tracking';
export function VehicleDetails({ tracks, base }: { tracks: VehicleTrack[]; base?: BaseLocation }) {
  const selectedId = useTrackingStore(state => state.selectedTrackId);
  const select = useTrackingStore(state => state.selectTrack);
  const follow = useTrackingStore(state => state.followVehicle);
  const setFollow = useTrackingStore(state => state.setFollowVehicle);
  const requestView = useTrackingStore(state => state.requestView);
  // Inspector refreshes at 10 Hz; map motion retains the full animation frame rate.
  const currentTime = usePlaybackStore(state => Math.floor(state.currentTime * 10) / 10);
  const track = tracks.find(track => track.id === selectedId);
  const metrics = track && base ? selectedVehicleMetrics(track, currentTime, base) : null;
  const position = metrics?.position;
  return <aside className="vehicle-details" aria-label="Vehicle details">
    <div className="details-heading"><span className="section-eyebrow">VEHICLE INSPECTOR</span><Button variant="ghost" size="icon" aria-label="Collapse inspector" title="Collapse inspector" onClick={() => useWorkspaceStore.getState().toggleInspector()}><PanelRightClose size={15} /></Button>{track && <Button variant="ghost" size="icon" aria-label="Clear vehicle selection" onClick={() => select(null)}><X size={16} /></Button>}</div>
    {track && metrics && base ? <><div className="detail-title"><span className="track-icon"><Truck size={18} /></span><div><span className="section-eyebrow">SELECTED VEHICLE</span><strong>{track.id}</strong></div><span className="record-count">{track.points.length} points</span></div>
      <div className="vehicle-status" aria-label="Vehicle status"><span className={`status-badge ${metrics.motion === 'MOVING' ? 'moving' : ''}`}>{metrics.motion}</span>{metrics.baseTrend && <span className="status-badge">{metrics.baseTrend}</span>}</div>
      <div className="vehicle-actions"><Button variant={follow ? 'default' : 'outline'} aria-pressed={follow} onClick={() => setFollow(!follow)}><Crosshair size={13} />Follow</Button><Button variant="outline" onClick={() => requestView('route')}><Focus size={13} />Focus on route</Button><Button variant="ghost" onClick={() => requestView('reset')}><LocateFixed size={13} />Reset view</Button></div>
      {follow && <p className="follow-note">Following {track.id} · Drag the map or toggle Follow to stop.</p>}
      <dl className="live-values">
        <div><dt>SIMULATED TIME</dt><dd>{formatTime(currentTime)}</dd></div><div><dt>ELAPSED TRACKED TIME</dt><dd>{formatDuration(metrics.elapsedSeconds)}</dd></div>
        <div><dt>LATITUDE</dt><dd>{position ? `${position.lat.toFixed(6)}°` : '—'}</dd></div><div><dt>LONGITUDE</dt><dd>{position ? `${position.lon.toFixed(6)}°` : '—'}</dd></div>
        <div><dt>APPROX. SPEED</dt><dd>{position ? `${position.speedKmh.toFixed(1)} km/h` : '—'}</dd></div><div><dt>HEADING / DIRECTION</dt><dd>{position?.heading != null ? `${position.heading.toFixed(1)}° ${metrics.direction}` : '—'}</dd></div>
        <div><dt>DISTANCE TO BASE</dt><dd>{metrics.distanceToBase != null ? `${metrics.distanceToBase.toFixed(2)} km` : '—'}</dd></div><div><dt>DISTANCE TRAVELED</dt><dd>{metrics.totalDistance.toFixed(2)} km</dd></div>
      </dl>
      {!position && <p className="outside-track">Outside this vehicle’s recorded interval. Position and follow are suspended; selection is retained.</p>}
      {position && <div className="sample-bracket"><div><span className="section-eyebrow">PREVIOUS KNOWN POINT</span><strong>{formatTime(position.previous.timestamp)}</strong><small>{position.previous.lat.toFixed(6)}°, {position.previous.lon.toFixed(6)}°</small></div><div><span className="section-eyebrow">NEXT KNOWN POINT</span><strong>{formatTime(position.next.timestamp)}</strong><small>{position.next.lat.toFixed(6)}°, {position.next.lon.toFixed(6)}°</small></div></div>}
      <VehicleCharts track={track} base={base} time={Math.floor(currentTime)} />
      <section className="movement-history"><div className="chart-heading"><h3>Movement history</h3><span>Latest 5 GPS samples</span></div><div className="history-scroll"><table><thead><tr><th>Time</th><th>Lat / Lon</th><th>km/h</th><th>Base km</th></tr></thead><tbody>{metrics.history.map((point, index) => <tr key={`${point.timestamp}-${index}`}><td>{formatTime(point.timestamp)}</td><td>{point.lat.toFixed(6)}<br />{point.lon.toFixed(6)}</td><td>{point.speedKmh.toFixed(1)}</td><td>{point.distanceKm.toFixed(2)}</td></tr>)}</tbody></table>{!metrics.history.length && <p className="details-note">No recorded points yet at this time.</p>}</div></section>
      <p className="details-note">Base: {base.name}. Estimates use GPS segments. Stationary: under 0.5 km/h. Base trend follows local distance change; history speed describes the outgoing segment (last point uses the final segment).</p>
    </> : <div className="inspector-empty"><Crosshair size={29} /><h2>Inspect a vehicle</h2><p>Select a marker, route, or directory entry to explore its movement.</p><ul><li>Live position, heading, and speed</li><li>Distance and movement relative to base</li><li>Track charts and recent GPS samples</li></ul><p>Use the timeline to inspect any moment. Follow keeps the selected vehicle centered.</p></div>}
  </aside>;
}

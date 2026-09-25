import { useTrackingStore } from '../store/tracking';
import { usePlaybackStore } from '../store/playback';
import { filterVehicles } from '../services/vehicle-filters';
import { formatTime } from '../services/playback';
import type { TrackingData } from '../types/tracking';
export function activeFilterCount(state: ReturnType<typeof useTrackingStore.getState>) { return Number(!!state.searchQuery.trim()) + Number(!!state.selectedZone) + state.activeMovementStates.length + Number(state.minSpeed !== null) + Number(state.maxSpeed !== null); }
export function WorkspaceStatus({ data }: { data: TrackingData }) {
  const state = useTrackingStore(), time = usePlaybackStore(state => Math.floor(state.currentTime)), speed = usePlaybackStore(state => state.playbackSpeed);
  const vehicles = filterVehicles(data, state, time);
  const visible = state.layers.vehicles ? vehicles.filter(vehicle => vehicle.position).length : 0;
  const following = state.followVehicle && state.layers.vehicles && vehicles.some(vehicle => vehicle.track.id === state.selectedTrackId && vehicle.position);
  return <div className="workspace-status" aria-label="Workspace status"><span><b>{visible}</b> visible / {data.tracks.length}</span><span>{activeFilterCount(state)} filters</span><span className="status-time">{formatTime(time)} · {speed}x</span><span className="status-selection">{state.selectedTrackId ? `Selected ${state.selectedTrackId}` : 'No selection'}</span>{state.followVehicle && <span className="follow-status">{following ? 'Following' : 'Follow suspended'}</span>}</div>;
}

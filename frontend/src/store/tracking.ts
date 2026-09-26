import { create } from 'zustand';
import { useWorkspaceStore } from './workspace';

export type MapLayer = 'vehicles' | 'untracked' | 'zones' | 'base';
export type ViewAction = 'route' | 'reset' | 'all' | 'vehicle' | 'zone' | 'coordinate';

export interface TrackingState {
  selectedTrackId: string | null;
  selectTrack: (id: string | null) => void;
  followVehicle: boolean;
  setFollowVehicle: (enabled: boolean) => void;
  lockOntoTrack: (trackId: string, coordinate?: [number, number]) => void;
  viewRequest: { action: ViewAction; sequence: number; zoneName?: string; coordinate?: [number, number] };
  requestView: (action: ViewAction, zoneName?: string, coordinate?: [number, number]) => void;
  layers: Record<MapLayer, boolean>;
  toggleLayer: (layer: MapLayer) => void;
}

export const useTrackingStore = create<TrackingState>((set) => ({
  selectedTrackId: null,
  selectTrack: (selectedTrackId) => {
    if (selectedTrackId) useWorkspaceStore.setState({ inspectorOpen: true });
    set((state) => ({
      selectedTrackId,
      followVehicle: selectedTrackId ? state.followVehicle : false,
    }));
  },
  followVehicle: false,
  setFollowVehicle: (enabled) => set((state) => ({
    followVehicle: enabled && !!state.selectedTrackId,
  })),
  lockOntoTrack: (trackId: string, coordinate?: [number, number]) => {
    useWorkspaceStore.setState({ inspectorOpen: true });
    set((state) => ({
      selectedTrackId: trackId,
      followVehicle: true,
      viewRequest: {
        action: coordinate ? 'coordinate' : 'vehicle',
        coordinate,
        sequence: state.viewRequest.sequence + 1,
      },
    }));
  },
  viewRequest: { action: 'reset', sequence: 0 },
  requestView: (action, zoneName, coordinate) => set((state) => ({
    followVehicle: action === 'vehicle' ? true : false,
    viewRequest: { action, zoneName, coordinate, sequence: state.viewRequest.sequence + 1 },
  })),
  layers: { vehicles: true, untracked: true, zones: true, base: true },
  toggleLayer: (layer) => set((state) => ({
    layers: { ...state.layers, [layer]: !state.layers[layer] },
  })),
}));

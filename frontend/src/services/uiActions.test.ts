import { beforeEach, describe, expect, it } from 'vitest';
import { initialMapFilters, type MapFilterState } from '../components/map/MapSidebar';
import { useOverlayPanelStore } from '../store/overlayPanel';
import { usePlaybackStore } from '../store/playback';
import { useSettingsStore } from '../store/settings';
import { useTrackingStore } from '../store/tracking';
import type { AnalysisData, AnalysisEntity } from '../types/analysis';
import { buildUiContext, resolveTrackId, runUiActions, type UiController } from './uiActions';

const entity = (track_id: string, vehicle_class: string, risk_level: string, zone: string, scenario: string) =>
  ({ track_id, vehicle_class, risk_level, zone, scenario, source: 'detection', vehicle: null, first_seen: '10:00:00', observed_at: '10:00:00' }) as unknown as AnalysisEntity;

const analysis = {
  entities: [entity('T0106', 'bus', 'HIGH', 'Kuzey Kapı', 'APPROACHING'), entity('T0200', 'truck', 'LOW', 'Güney', 'TRANSIT'), entity('T0301', 'car', 'CRITICAL', 'Güney', 'LOITER_NEAR_BASE')],
  zones: [{ name: 'Kuzey Kapı' }, { name: 'Güney' }],
  untracked: [],
  reviews: { human_review: false, items: [], pending_count: 0 },
} as unknown as AnalysisData;

function controller() {
  let filters: MapFilterState = initialMapFilters;
  const opened: Record<string, boolean> = {};
  const selected: string[] = [];
  const ctrl: UiController = {
    analysis,
    get filters() { return filters; },
    setFilters: value => { filters = typeof value === 'function' ? value(filters) : value; },
    selectTrack: id => { selected.push(id); useTrackingStore.getState().selectTrack(id); },
    sidebarOpen: false, setSidebarOpen: open => { opened.sidebar = open; },
    bottomOpen: false, setBottomOpen: open => { opened.track_list = open; },
    notificationsOpen: false, setNotificationsOpen: open => { opened.notifications = open; },
    settingsOpen: false, setSettingsOpen: open => { opened.settings = open; },
    helpOpen: false, setHelpOpen: open => { opened.help = open; },
    selectedFrameId: null, startTutorial: () => {}, openPdfReport: () => {}, reload: () => {},
    setHumanReview: async () => {},
  };
  return { ctrl, opened, selected, filters: () => filters };
}

describe('voice UI actions', () => {
  beforeEach(() => {
    useTrackingStore.setState({ selectedTrackId: null, followVehicle: false, layers: { vehicles: true, untracked: true, zones: true, base: true } });
    usePlaybackStore.setState({ minTime: 36000, maxTime: 43200, currentTime: 36000, isPlaying: false });
  });

  it('"Sadece otobüsleri göster" clears the filters and shows only buses', async () => {
    const { ctrl, filters } = controller();
    ctrl.setFilters(current => ({ ...current, risk: 'HIGH' }));
    const results = await runUiActions([{ action: 'clear_filters', params: {} }, { action: 'set_filters', params: { vehicle_class: 'bus' } }], ctrl);
    expect(results.every(result => result.ok)).toBe(true);
    expect(filters()).toEqual({ ...initialMapFilters, vehicleClass: 'bus' });
  });

  it('accepts Turkish labels and API risk names for filter values', async () => {
    const { ctrl, filters } = controller();
    await runUiActions([{ action: 'set_filters', params: { vehicle_class: 'Kamyon', risk: 'KRITIK', zone: 'güney', scenario: 'Geçiş' } }], ctrl);
    expect(filters()).toMatchObject({ vehicleClass: 'truck', risk: 'CRITICAL', zone: 'Güney', scenario: 'TRANSIT' });
  });

  it('reports invalid parameters and unknown actions but keeps running the rest', async () => {
    const { ctrl } = controller();
    const results = await runUiActions([
      { action: 'set_filters', params: { vehicle_class: 'tank' } },
      { action: 'drop_database', params: {} },
      { action: 'set_layer', params: { layer: 'zones', visible: false } },
    ], ctrl);
    expect(results.map(result => result.ok)).toEqual([false, false, true]);
    expect(useTrackingStore.getState().layers.zones).toBe(false);
  });

  it('selects and follows a track from a speech-mangled ID', async () => {
    const { ctrl, selected } = controller();
    await runUiActions([{ action: 'select_track', params: { track_id: 't 106' } }, { action: 'follow_vehicle', params: { enabled: true } }], ctrl);
    expect(selected).toEqual(['T0106']);
    expect(useTrackingStore.getState().followVehicle).toBe(true);
    expect(() => resolveTrackId('T9999', analysis.entities)).toThrow();
  });

  it('opens panels, changes settings and drives playback', async () => {
    const { ctrl, opened } = controller();
    await runUiActions([
      { action: 'open_panel', params: { panel: 'priority' } }, { action: 'open_panel', params: { panel: 'sidebar' } },
      { action: 'set_theme', params: { mode: 'light' } }, { action: 'set_speed', params: { speed: 4 } },
      { action: 'seek', params: { time: '11:30' } }, { action: 'playback', params: { command: 'play' } },
    ], ctrl);
    expect(useOverlayPanelStore.getState().request.panel).toBe('priority');
    expect(opened.sidebar).toBe(true);
    expect(useSettingsStore.getState().themeMode).toBe('light');
    expect(usePlaybackStore.getState()).toMatchObject({ playbackSpeed: 4, currentTime: 41400, isPlaying: true });
  });

  it('builds a context with option values and risk-sorted tracks', () => {
    const context = buildUiContext(controller().ctrl);
    expect(context.options.vehicle_class).toContainEqual({ value: 'bus', label: 'Otobüs' });
    expect(context.tracks[0]).toMatch(/^T0301 \| car \| CRITICAL/);
    expect(context.state.filters).toEqual(initialMapFilters);
  });
});

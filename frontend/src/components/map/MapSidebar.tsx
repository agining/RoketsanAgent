import {
  ChevronLeft,
  ChevronRight,
  Eye,
  Filter,
  Layers3,
  MapPin,
  Radar,
  Search,
  Trash2,
} from 'lucide-react';
import type { Dispatch, ReactNode, PointerEvent as ReactPointerEvent, SetStateAction } from 'react';
import { useMemo, useRef } from 'react';

import type {
  AnalysisData,
  AnalysisEntity,
  AnalysisVehicle,
  RiskLevel,
} from '../../types/analysis';

import {
  useTrackingStore,
  type MapLayer,
} from '../../store/tracking';
import { usePanelLayoutStore } from '../../store/panelLayout';
import { usePlaybackStore } from '../../store/playback';
import { useWatchlistStore } from '../../store/watchlist';

import { clockSeconds } from '../../services/analysis-playback';
import { activeTrackEntities } from '../../services/trackFilters';

import {
  formatAllOption,
  formatMeters,
  formatPercent,
  formatRiskLevel,
  formatScenario,
  formatVehicleClass,
} from '../../services/formatters';

export interface MapFilterState {
  query: string;
  risk: RiskLevel | 'ALL';
  scenario: string;
  zone: string;
  vehicleClass: string;
}

export const initialMapFilters: MapFilterState = {
  query: '',
  risk: 'ALL',
  scenario: 'ALL',
  zone: 'ALL',
  vehicleClass: 'ALL',
};

export function entityMatchesMapFilters(
  entity: AnalysisEntity,
  filters: MapFilterState,
) {
  const query = filters.query
    .trim()
    .toLocaleLowerCase('tr-TR');

  if (
    query &&
    ![
      entity.track_id,
      entity.vehicle_class,
      entity.zone ?? '',
      entity.vehicle?.vehicle_id ?? '',
      entity.frame_id ?? '',
    ].some(value =>
      value
        .toLocaleLowerCase('tr-TR')
        .includes(query),
    )
  ) {
    return false;
  }

  if (
    filters.risk !== 'ALL' &&
    entity.risk_level !== filters.risk
  ) {
    return false;
  }

  if (
    filters.scenario !== 'ALL' &&
    entity.scenario !== filters.scenario
  ) {
    return false;
  }

  if (
    filters.zone !== 'ALL' &&
    entity.zone !== filters.zone
  ) {
    return false;
  }

  if (
    filters.vehicleClass !== 'ALL' &&
    entity.vehicle_class !== filters.vehicleClass
  ) {
    return false;
  }

  return true;
}

const layerLabels: Array<[MapLayer, string]> = [
  ['vehicles', 'İz kayıtları'],
  ['untracked', 'İzsiz tespitler'],
  ['zones', 'Bölgeler'],
  ['base', 'Üs'],
];

const risks: Array<RiskLevel | 'ALL'> = [
  'ALL',
  'LOW',
  'MEDIUM',
  'HIGH',
  'CRITICAL',
  'UNKNOWN',
];

const riskOption = (value: RiskLevel | 'ALL') =>
  value === 'ALL'
    ? formatAllOption()
    : formatRiskLevel(value);

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

const riskRank: Record<RiskLevel, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
  UNKNOWN: 0,
};

function focusDetection(item: AnalysisVehicle) {
  usePlaybackStore
    .getState()
    .seek(clockSeconds(item.capture_time));

  useTrackingStore
    .getState()
    .requestView(
      'coordinate',
      undefined,
      [item.lon, item.lat],
    );
}

export function MapSidebar({
  analysis,
  filters,
  setFilters,
  open,
  setOpen,
  onSelectTrack,
  graphPanel,
}: {
  analysis: AnalysisData;
  filters: MapFilterState;
  setFilters: Dispatch<SetStateAction<MapFilterState>>;
  open: boolean;
  setOpen: (open: boolean) => void;
  onSelectTrack: (trackId: string) => void;
  graphPanel?: ReactNode;
}) {
  const panelRef = useRef<HTMLElement | null>(null);
  const sidebarLayout = usePanelLayoutStore(state => state.sidebar);
  const setSidebarPosition = usePanelLayoutStore(state => state.setSidebarPosition);
  const setSidebarWidth = usePanelLayoutStore(state => state.setSidebarWidth);
  const layers = useTrackingStore(
    state => state.layers,
  );

  const selectedTrackId = useTrackingStore(
    state => state.selectedTrackId,
  );

  const watchIds = useWatchlistStore(
    state => state.trackIds,
  );

  const removeWatch = useWatchlistStore(
    state => state.remove,
  );
  const activeEntities = useMemo(
    () => activeTrackEntities(analysis.entities),
    [analysis.entities],
  );

  const vehicles = useMemo(
    () =>
      [
        ...new Set(
          activeEntities.map(
            entity => entity.vehicle_class,
          ),
        ),
      ].sort(),
    [activeEntities],
  );

  const scenarios = useMemo(
    () =>
      [
        ...new Set(
          activeEntities
            .map(entity => entity.scenario)
            .filter(
              (value): value is string =>
                Boolean(value),
            ),
        ),
      ].sort(),
    [activeEntities],
  );

  const matches = useMemo(
    () =>
      activeEntities
        .filter(entity =>
          entityMatchesMapFilters(
            entity,
            filters,
          ),
        )
        .sort(
          (a, b) =>
            riskRank[b.risk_level] -
              riskRank[a.risk_level] ||
            a.track_id.localeCompare(
              b.track_id,
            ),
        ),
    [activeEntities, filters],
  );

  const watched = useMemo(
    () =>
      watchIds
        .map(trackId =>
          activeEntities.find(
            entity =>
              entity.track_id === trackId,
          ),
        )
        .filter(
          (
            entity,
          ): entity is AnalysisEntity =>
            Boolean(entity),
        )
        .sort(
          (a, b) =>
            riskRank[b.risk_level] -
              riskRank[a.risk_level] ||
            a.track_id.localeCompare(
              b.track_id,
            ),
        ),
    [activeEntities, watchIds],
  );

  const untracked = useMemo(
    () =>
      [...analysis.untracked].sort(
        (a, b) =>
          riskRank[b.risk_level] -
            riskRank[a.risk_level] ||
          a.capture_time.localeCompare(
            b.capture_time,
          ),
      ),
    [analysis.untracked],
  );

  const update = <
    K extends keyof MapFilterState,
  >(
    key: K,
    value: MapFilterState[K],
  ) => {
    setFilters(current => ({
      ...current,
      [key]: value,
    }));
  };

  const startDrag = (event: ReactPointerEvent<HTMLElement>) => {
    const target = event.target as HTMLElement;
    if (target.closest('button,input,select,textarea,a,label')) return;
    const panel = panelRef.current;
    const parent = panel?.parentElement;
    if (!panel || !parent) return;
    event.preventDefault();
    const parentRect = parent.getBoundingClientRect();
    const startX = event.clientX;
    const startY = event.clientY;
    const startLeft = sidebarLayout.x;
    const startTop = sidebarLayout.y;
    const width = panel.offsetWidth;
    const height = panel.offsetHeight;
    const move = (moveEvent: PointerEvent) => {
      const maxX = Math.max(8, parentRect.width - width - 8);
      const maxY = Math.max(8, parentRect.height - Math.min(height, 120));
      setSidebarPosition(
        clamp(startLeft + moveEvent.clientX - startX, 8, maxX),
        clamp(startTop + moveEvent.clientY - startY, 8, maxY),
      );
    };
    const stop = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', stop);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', stop, { once: true });
  };

  const startResize = (event: ReactPointerEvent<HTMLDivElement>) => {
    const panel = panelRef.current;
    const parent = panel?.parentElement;
    if (!panel || !parent) return;
    event.preventDefault();
    event.stopPropagation();
    const parentRect = parent.getBoundingClientRect();
    const startX = event.clientX;
    const startWidth = sidebarLayout.width;
    const move = (moveEvent: PointerEvent) => {
      const maxWidth = Math.max(230, parentRect.width - sidebarLayout.x - 16);
      setSidebarWidth(clamp(startWidth + moveEvent.clientX - startX, 230, Math.min(420, maxWidth)));
    };
    const stop = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', stop);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', stop, { once: true });
  };

  if (!open) {
    return (
      <button
        className="map-sidebar-rail"
        aria-label="Harita panelini aç"
        title="Harita panelini aç"
        onClick={() => setOpen(true)}
      >
        <Layers3 size={17} />
        <ChevronRight size={14} />
      </button>
    );
  }

  return (
    <aside
      ref={panelRef}
      className="map-sidebar"
      aria-label="Harita paneli"
      style={{ left: sidebarLayout.x, top: sidebarLayout.y, width: sidebarLayout.width }}
    >
      <header onPointerDown={startDrag}>
        <span>
          <Layers3 size={15} />
          <strong>Harita Paneli</strong>
        </span>

        <button
          aria-label="Harita panelini daralt"
          title="Harita panelini daralt"
          onClick={() => setOpen(false)}
        >
          <ChevronLeft size={16} />
        </button>
      </header>
      <div className="panel-resize-handle right-edge" role="separator" aria-orientation="vertical" aria-label="Harita paneli genişliği" onPointerDown={startResize} />

      <div className="map-sidebar-scroll">
        {graphPanel}
        <section>
          <h2>
            <Layers3 size={12} />
            Katmanlar
          </h2>

          <div className="compact-layer-grid">
            {layerLabels.map(
              ([layer, label]) => (
                <label key={layer}>
                  <input
                    type="checkbox"
                    checked={layers[layer]}
                    onChange={() =>
                      useTrackingStore
                        .getState()
                        .toggleLayer(layer)
                    }
                  />
                  {label}
                </label>
              ),
            )}
          </div>
        </section>

        <section>
          <h2>
            <Filter size={12} />
            İz filtreleri
          </h2>

          <label className="map-filter-search">
            <Search size={13} />
            <input
              aria-label="Harita araç kayıtlarında ara"
              placeholder="İz, araç, kare veya bölge"
              value={filters.query}
              onChange={event =>
                update(
                  'query',
                  event.target.value,
                )
              }
            />
          </label>

          <div className="map-filter-grid">
            <label>
              <span>Risk</span>

              <select
                aria-label="Harita risk filtresi"
                value={filters.risk}
                onChange={event =>
                  update(
                    'risk',
                    event.target
                      .value as MapFilterState['risk'],
                  )
                }
              >
                {risks.map(value => (
                  <option
                    key={value}
                    value={value}
                  >
                    {riskOption(value)}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span>Araç</span>

              <select
                aria-label="Harita araç filtresi"
                value={filters.vehicleClass}
                onChange={event =>
                  update(
                    'vehicleClass',
                    event.target.value,
                  )
                }
              >
                {[
                  'ALL',
                  ...vehicles,
                ].map(value => (
                  <option
                    key={value}
                    value={value}
                  >
                    {value === 'ALL'
                      ? formatAllOption()
                      : formatVehicleClass(
                          value,
                        )}
                  </option>
                ))}
              </select>
            </label>

            <label className="wide">
              <span>Senaryo</span>

              <select
                aria-label="Harita senaryo filtresi"
                value={filters.scenario}
                onChange={event =>
                  update(
                    'scenario',
                    event.target.value,
                  )
                }
              >
                <option value="ALL">
                  {formatAllOption()}
                </option>

                {scenarios.map(value => (
                  <option
                    key={value}
                    value={value}
                  >
                    {formatScenario(value)}
                  </option>
                ))}
              </select>
            </label>

            <label className="wide">
              <span>Bölge</span>

              <select
                aria-label="Harita bölge filtresi"
                value={filters.zone}
                onChange={event =>
                  update(
                    'zone',
                    event.target.value,
                  )
                }
              >
                <option value="ALL">
                  {formatAllOption()}
                </option>

                {analysis.zones.map(zone => (
                  <option
                    key={zone.name}
                    value={zone.name}
                  >
                    {zone.name}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="map-filter-result">
            <span>
              {matches.length} /{' '}
              {activeEntities.length} iz
              görünür
            </span>

            <button
              onClick={() =>
                setFilters(initialMapFilters)
              }
            >
              Temizle
            </button>
          </div>

          <div className="map-track-shortlist">
            {matches
              .slice(0, 8)
              .map(entity => (
                <button
                  className={
                    selectedTrackId ===
                    entity.track_id
                      ? 'active'
                      : ''
                  }
                  key={entity.track_id}
                  onClick={() =>
                    onSelectTrack(
                      entity.track_id,
                    )
                  }
                >
                  <span>
                    <strong>
                      {entity.track_id}
                    </strong>

                    <small>
                      {formatVehicleClass(
                        entity.vehicle_class,
                      )}{' '}
                      ·{' '}
                      {entity.zone ??
                        'Bölge yok'}
                      {entity.scenario
                        ? ` · ${formatScenario(
                            entity.scenario,
                          )}`
                        : ''}
                    </small>
                  </span>

                  <em
                    className={`entity-risk risk-${entity.risk_level.toLowerCase()}`}
                  >
                    {formatRiskLevel(
                      entity.risk_level,
                    )}
                  </em>
                </button>
              ))}

            {!matches.length && (
              <p>
                Bu filtrelerle eşleşen iz yok.
              </p>
            )}
          </div>
        </section>

        <section>
          <h2>
            <Eye size={12} />
            İzleme Listesi{' '}
            <b>{watched.length}</b>
          </h2>

          <div className="watchlist-panel">
            {watched.map(entity => (
              <article
                key={entity.track_id}
                className={
                  selectedTrackId ===
                  entity.track_id
                    ? 'active'
                    : ''
                }
              >
                <button
                  className="watchlist-row-main"
                  onClick={() =>
                    onSelectTrack(
                      entity.track_id,
                    )
                  }
                >
                  <span>
                    <strong>
                      {entity.track_id}
                    </strong>

                    <small>
                      {formatVehicleClass(
                        entity.vehicle_class,
                      )}{' '}
                      ·{' '}
                      {entity.scenario
                        ? formatScenario(
                            entity.scenario,
                          )
                        : 'Durum yok'}
                    </small>

                    <small>
                      {entity.zone ??
                        'Bölge yok'}{' '}
                      · üsse{' '}
                      {formatMeters(
                        entity.distance_to_base_m,
                      )}{' '}
                      · {entity.last_seen}
                    </small>
                  </span>

                  <em
                    className={`entity-risk risk-${entity.risk_level.toLowerCase()}`}
                  >
                    {formatRiskLevel(
                      entity.risk_level,
                    )}
                  </em>
                </button>

                <button
                  className="watchlist-remove"
                  aria-label={`${entity.track_id} izleme listesinden çıkar`}
                  title="İzlemeden çıkar"
                  onClick={() =>
                    removeWatch(
                      entity.track_id,
                    )
                  }
                >
                  <Trash2 size={12} />
                </button>
              </article>
            ))}

            {!watched.length && (
              <p>
                İzleme listesi boş. Sağ
                panelden bir aracı izlemeye
                al.
              </p>
            )}
          </div>
        </section>

        <section>
          <h2>
            <MapPin size={12} />
            Bölgeler
          </h2>

          <div className="map-zone-list">
            {analysis.zones.map(zone => (
              <button
                key={zone.name}
                onClick={() =>
                  useTrackingStore
                    .getState()
                    .requestView(
                      'zone',
                      zone.name,
                    )
                }
              >
                <span>{zone.name}</span>
                <ChevronRight size={12} />
              </button>
            ))}
          </div>
        </section>

        <section>
          <h2>
            <Radar size={12} />
            İzsiz tespitler{' '}
            <b>
              {analysis.untracked.length}
            </b>
          </h2>

          <div className="map-untracked-list">
            {untracked.map(item => (
              <article
                key={item.vehicle_id}
                role="button"
                tabIndex={0}
                aria-label={`${item.vehicle_id} tespitine git`}
                onClick={() =>
                  focusDetection(item)
                }
                onKeyDown={event => {
                  if (
                    event.key === 'Enter' ||
                    event.key === ' '
                  ) {
                    event.preventDefault();
                    focusDetection(item);
                  }
                }}
              >
                <strong>
                  {formatVehicleClass(
                    item.label,
                  )}{' '}
                  <em
                    className={`entity-risk risk-${item.risk_level.toLowerCase()}`}
                  >
                    {formatRiskLevel(
                      item.risk_level,
                    )}
                  </em>
                </strong>

                <time>
                  {item.capture_time}
                </time>

                <span>
                  {item.zone} · {item.frame_id}
                </span>

                <small>
                  {item.filtered
                    ? 'Düşük güven — risk hesabına katılmadı · '
                    : ''}
                  {formatPercent(
                    item.confidence,
                  )}{' '}
                  tespit güveni · üsse{' '}
                  {formatMeters(
                    item.distance_to_base_m,
                  )}
                </small>
              </article>
            ))}

            {!untracked.length && (
              <p>İzsiz tespit yok.</p>
            )}
          </div>
        </section>
      </div>
    </aside>
  );
}

// Track geometry remains a temporary playback source. Analysis/base/zones come from the backend output.
import tracksUrl from '../../mock_data/tracks.csv?url';
import type { BaseLocation, TrackingData, VehicleTrack, Zone } from '../types/tracking';
import type { AnalysisData } from '../types/analysis';
import { buildAnalysisIndex } from './analysis';

function coordinates(lat: number, lon: number) {
  return Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180;
}
/** Parses the unquoted four-column track export; preserves source point order. */
export function parseTracksCsv(csv: string): VehicleTrack[] {
  const lines = csv.replace(/^\uFEFF/, '').trim().split(/\r?\n/);
  if (lines.shift()?.trim() !== 'track_id,time,lat,lon') throw new Error('tracks.csv başlığı beklenen formatta değil.');
  const tracks = new Map<string, VehicleTrack>();
  lines.forEach((line, index) => {
    if (!line.trim()) return;
    const columns = line.split(',').map(value => value.trim());
    const [id, time, rawLat, rawLon] = columns;
    const lat = Number(rawLat), lon = Number(rawLon);
    if (columns.length !== 4 || !id || !/^([01]\d|2[0-3]):[0-5]\d$/.test(time) || !rawLat || !rawLon || !coordinates(lat, lon)) {
      throw new Error(`tracks.csv içinde ${index + 2}. satır geçersiz.`);
    }
    if (!tracks.has(id)) tracks.set(id, { id, points: [] });
    tracks.get(id)!.points.push({ time, lat, lon });
  });
  if (!tracks.size) throw new Error('Araç track kaydı bulunamadı.');
  return [...tracks.values()];
}
export function parseZones(value: unknown): { base: BaseLocation; zones: Zone[] } {
  if (!value || typeof value !== 'object') throw new Error('Bölge verisi geçersiz.');
  const { base, zones } = value as { base?: BaseLocation; zones?: Zone[] };
  if (!base || typeof base.name !== 'string' || !coordinates(base.lat, base.lon) || !Array.isArray(zones) || zones.some(zone =>
    !zone || typeof zone.name !== 'string' || !Array.isArray(zone.center) || zone.center.length !== 2 || !coordinates(zone.center[0], zone.center[1])
  )) throw new Error('Üs veya bölge koordinatları geçersiz.');
  return { base, zones };
}

/** Refuses to join stale analysis with a different track export. */
export function validateDatasetConsistency(tracks: VehicleTrack[], analysis: AnalysisData): void {
  const trackIds = new Set(tracks.map(track => track.id));
  const analysisIds = new Set(buildAnalysisIndex(analysis).byTrackId.keys());
  const missing = [...trackIds].filter(id => !analysisIds.has(id));
  const extra = [...analysisIds].filter(id => !trackIds.has(id));
  if (missing.length || extra.length) {
    const details = [
      missing.length ? `${missing.length} track analize dahil değil (${missing.slice(0, 3).join(', ')})` : '',
      extra.length ? `${extra.length} analiz track kaydı CSV’de yok (${extra.slice(0, 3).join(', ')})` : '',
    ].filter(Boolean).join('; ');
    throw new Error(`Mock veri seti analiz çıktısıyla uyumlu değil: ${details}. Analiz pipeline’ını yeniden çalıştırın.`);
  }
}

export async function loadTrackingData(analysis: AnalysisData, signal?: AbortSignal): Promise<TrackingData> {
  const fetchFile = async (url: string, label: string) => {
    try { const response = await fetch(url, { signal }); if (!response.ok) throw new Error(`HTTP ${response.status}`); return response; }
    catch (error) { if (signal?.aborted) throw error; throw new Error(`${label} unavailable. Check the file and connection, then retry.`); }
  };
  const tracksResponse = await fetchFile(tracksUrl, 'tracks.csv');
  let tracks: VehicleTrack[];
  try { tracks = parseTracksCsv(await tracksResponse.text()); } catch (error) { throw new Error(`Malformed tracks.csv: ${error instanceof Error ? error.message : 'Cannot read track rows.'}`); }
  validateDatasetConsistency(tracks, analysis);
  return { tracks, base: analysis.base, zones: analysis.zones, analysis };
}

import type {
  BaseLocation,
  TrackingData,
  VehicleTrack,
  Zone,
} from '../types/tracking';


const API_URL =
  import.meta.env.VITE_API_URL ?? 'http://localhost:8000';


function coordinates(lat: number, lon: number): boolean {
  return (
    Number.isFinite(lat) &&
    Number.isFinite(lon) &&
    Math.abs(lat) <= 90 &&
    Math.abs(lon) <= 180
  );
}


function validateBase(value: unknown): BaseLocation {
  if (!value || typeof value !== 'object') {
    throw new Error('Invalid base data.');
  }

  const base = value as Partial<BaseLocation>;

  if (
    typeof base.name !== 'string' ||
    typeof base.lat !== 'number' ||
    typeof base.lon !== 'number' ||
    !coordinates(base.lat, base.lon)
  ) {
    throw new Error('Invalid base coordinates.');
  }

  return {
    name: base.name,
    lat: base.lat,
    lon: base.lon,
  };
}


function validateZones(value: unknown): Zone[] {
  if (!Array.isArray(value)) {
    throw new Error('Invalid zones data.');
  }

  return value.map((item, index) => {
    if (!item || typeof item !== 'object') {
      throw new Error(`Invalid zone at index ${index}.`);
    }

    const zone = item as {
      name?: unknown;
      center?: unknown;
    };

    if (
      typeof zone.name !== 'string' ||
      !Array.isArray(zone.center) ||
      zone.center.length !== 2
    ) {
      throw new Error(`Invalid zone at index ${index}.`);
    }

    const [lat, lon] = zone.center;

    if (
      typeof lat !== 'number' ||
      typeof lon !== 'number' ||
      !coordinates(lat, lon)
    ) {
      throw new Error(`Invalid zone coordinates at index ${index}.`);
    }

    return {
      name: zone.name,
      center: [lat, lon] as [number, number],
    };
  });
}


function validateTracks(value: unknown): VehicleTrack[] {
  if (!Array.isArray(value)) {
    throw new Error('Invalid tracks data.');
  }

  return value.map((item, trackIndex) => {
    if (!item || typeof item !== 'object') {
      throw new Error(`Invalid track at index ${trackIndex}.`);
    }

    const track = item as {
      id?: unknown;
      points?: unknown;
    };

    if (
      typeof track.id !== 'string' ||
      !track.id.trim() ||
      !Array.isArray(track.points)
    ) {
      throw new Error(`Invalid track at index ${trackIndex}.`);
    }

    const points = track.points.map((point, pointIndex) => {
      if (!point || typeof point !== 'object') {
        throw new Error(
          `Invalid point ${pointIndex} in track ${track.id}.`
        );
      }

      const value = point as {
        time?: unknown;
        lat?: unknown;
        lon?: unknown;
      };

      if (
        typeof value.time !== 'string' ||
        !/^([01]\d|2[0-3]):[0-5]\d$/.test(value.time) ||
        typeof value.lat !== 'number' ||
        typeof value.lon !== 'number' ||
        !coordinates(value.lat, value.lon)
      ) {
        throw new Error(
          `Invalid point ${pointIndex} in track ${track.id}.`
        );
      }

      return {
        time: value.time,
        lat: value.lat,
        lon: value.lon,
      };
    });

    return {
      id: track.id,
      points,
    };
  });
}


export function validateTrackingData(value: unknown): TrackingData {
  if (!value || typeof value !== 'object') {
    throw new Error('Invalid tracking data.');
  }

  const data = value as {
    base?: unknown;
    zones?: unknown;
    tracks?: unknown;
  };

  const base = validateBase(data.base);
  const zones = validateZones(data.zones);
  const tracks = validateTracks(data.tracks);

  return {
    base,
    zones,
    tracks,
  };
}


export async function loadTrackingData(
  signal?: AbortSignal
): Promise<TrackingData> {
  let response: Response;

  try {
    response = await fetch(
      `${API_URL}/api/tracking-data`,
      {
        method: 'GET',
        headers: {
          Accept: 'application/json',
        },
        signal,
      }
    );
  } catch (error) {
    if (signal?.aborted) {
      throw error;
    }

    throw new Error(
      'Tracking API unavailable. Backend bağlantısını kontrol edin.'
    );
  }

  if (!response.ok) {
    throw new Error(
      `Tracking API request failed: HTTP ${response.status}`
    );
  }

  let json: unknown;

  try {
    json = await response.json();
  } catch {
    throw new Error(
      'Tracking API geçerli JSON döndürmedi.'
    );
  }

  try {
    return validateTrackingData(json);
  } catch (error) {
    throw new Error(
      `Invalid tracking API response: ${
        error instanceof Error
          ? error.message
          : 'Unknown response format.'
      }`
    );
  }
}

import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import {
  loadTrackingData,
  validateTrackingData,
} from './tracking';

import {
  routeFeatures,
  trackingBounds,
} from './map-data';


const mockTrackingData = {
  base: {
    name: 'Merkez Us',
    lat: 39.92184,
    lon: 32.85306,
  },

  zones: [
    {
      name: 'Kuzey Yolu',
      center: [39.950586, 32.85306],
    },

    {
      name: 'Dogu Yolu',
      center: [39.92184, 32.890542],
    },
  ],

  tracks: [
    {
      id: 'T0001',
      points: [
        {
          time: '12:00',
          lat: 39.95,
          lon: 32.85,
        },
        {
          time: '12:05',
          lat: 39.94,
          lon: 32.85,
        },
      ],
    },

    {
      id: 'T0002',
      points: [
        {
          time: '12:00',
          lat: 39.91,
          lon: 32.87,
        },
        {
          time: '12:05',
          lat: 39.915,
          lon: 32.86,
        },
      ],
    },
  ],
};


describe('tracking data', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });


  it('loads tracking data from API', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify(mockTrackingData),
        {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
    );

    const data = await loadTrackingData();

    expect(fetch).toHaveBeenCalledTimes(1);

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/tracking-data'),
      expect.objectContaining({
        method: 'GET',
      })
    );

    expect(data.base).toEqual({
      name: 'Merkez Us',
      lat: 39.92184,
      lon: 32.85306,
    });

    expect(data.zones).toHaveLength(2);

    expect(data.tracks).toHaveLength(2);

    expect(data.tracks[0].id).toBe('T0001');

    expect(data.tracks[0].points).toHaveLength(2);
  });


  it('preserves track point order returned by API', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify(mockTrackingData),
        {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
    );

    const data = await loadTrackingData();

    expect(data.tracks[0].points).toEqual([
      {
        time: '12:00',
        lat: 39.95,
        lon: 32.85,
      },
      {
        time: '12:05',
        lat: 39.94,
        lon: 32.85,
      },
    ]);
  });


  it('creates route features from API tracks', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify(mockTrackingData),
        {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
    );

    const data = await loadTrackingData();

    const features = routeFeatures(data.tracks);

    expect(features.features).toHaveLength(2);

    expect(
      features.features[0].geometry.coordinates
    ).toEqual([
      [32.85, 39.95],
      [32.85, 39.94],
    ]);
  });


  it('includes tracks, zones and base in map bounds', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify(mockTrackingData),
        {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
    );

    const data = await loadTrackingData();

    const bounds = trackingBounds(data);

    for (const track of data.tracks) {
      for (const point of track.points) {
        expect(point.lon)
          .toBeGreaterThanOrEqual(bounds[0][0]);

        expect(point.lon)
          .toBeLessThanOrEqual(bounds[1][0]);

        expect(point.lat)
          .toBeGreaterThanOrEqual(bounds[0][1]);

        expect(point.lat)
          .toBeLessThanOrEqual(bounds[1][1]);
      }
    }

    expect(data.base.lon)
      .toBeGreaterThanOrEqual(bounds[0][0]);

    expect(data.base.lon)
      .toBeLessThanOrEqual(bounds[1][0]);

    expect(data.base.lat)
      .toBeGreaterThanOrEqual(bounds[0][1]);

    expect(data.base.lat)
      .toBeLessThanOrEqual(bounds[1][1]);
  });


  it('rejects invalid coordinates', () => {
    expect(() =>
      validateTrackingData({
        ...mockTrackingData,

        tracks: [
          {
            id: 'T1',
            points: [
              {
                time: '12:00',
                lat: 91,
                lon: 32,
              },
            ],
          },
        ],
      })
    ).toThrow('Invalid point');
  });


  it('rejects invalid time', () => {
    expect(() =>
      validateTrackingData({
        ...mockTrackingData,

        tracks: [
          {
            id: 'T1',
            points: [
              {
                time: '25:00',
                lat: 39,
                lon: 32,
              },
            ],
          },
        ],
      })
    ).toThrow('Invalid point');
  });


  it('rejects invalid zones', () => {
    expect(() =>
      validateTrackingData({
        ...mockTrackingData,

        zones: [
          {
            name: 'Broken Zone',
            center: [32, 190],
          },
        ],
      })
    ).toThrow('Invalid zone coordinates');
  });


  it('throws when API responds with an error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        null,
        {
          status: 500,
        }
      )
    );

    await expect(
      loadTrackingData()
    ).rejects.toThrow(
      'Tracking API request failed: HTTP 500'
    );
  });


  it('throws when API returns malformed JSON', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        'this-is-not-json',
        {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
    );

    await expect(
      loadTrackingData()
    ).rejects.toThrow(
      'Tracking API geçerli JSON döndürmedi'
    );
  });


  it('throws when API response structure is invalid', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          base: null,
          zones: [],
          tracks: [],
        }),
        {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
    );

    await expect(
      loadTrackingData()
    ).rejects.toThrow(
      'Invalid tracking API response'
    );
  });


  it('throws a connection error when API cannot be reached', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(
      new Error('Connection refused')
    );

    await expect(
      loadTrackingData()
    ).rejects.toThrow(
      'Tracking API unavailable'
    );
  });
});

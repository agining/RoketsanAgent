export interface TrackPoint { time: string; lat: number; lon: number }
export interface VehicleTrack { id: string; points: TrackPoint[] }
/** Source centers are [latitude, longitude], unlike GeoJSON. */
export interface Zone { name: string; center: [number, number] }
export interface BaseLocation { name: string; lat: number; lon: number }
export interface TrackingData { tracks: VehicleTrack[]; zones: Zone[]; base: BaseLocation }

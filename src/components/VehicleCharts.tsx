import { memo, useMemo } from 'react';
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { BaseLocation, VehicleTrack } from '../types/tracking';
import { calculateDistanceSeries, calculateTrackSpeedSeries, type MetricSample } from '../services/vehicle-metrics';
import { formatTime } from '../services/playback';
function MetricChart({ title, unit, data, time, stepped = false }: { title: string; unit: string; data: MetricSample[]; time: number; stepped?: boolean }) {
  return <section className="metric-chart" aria-label={title}><div className="chart-heading"><h3>{title}</h3><span>{unit}</span></div>
    <div className="chart-canvas"><ResponsiveContainer width="100%" height="100%" minWidth={0}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -19 }} accessibilityLayer>
        <CartesianGrid vertical={false} stroke="#29373f" strokeDasharray="2 4" />
        <XAxis dataKey="time" type="number" domain={['dataMin', 'dataMax']} tickFormatter={time => formatTime(time).slice(-8, -3)} tick={{ fill: '#8c9fa9', fontSize: 9 }} tickLine={false} axisLine={false} minTickGap={35} />
        <YAxis tick={{ fill: '#8c9fa9', fontSize: 9 }} tickLine={false} axisLine={false} tickCount={3} tickFormatter={value => Number(value).toFixed(1)} domain={[0, 'auto']} />
        <Tooltip contentStyle={{ background: '#1b2932', border: '1px solid #43545e', borderRadius: 5, fontSize: 10 }} labelFormatter={label => formatTime(Number(label))} formatter={value => [`${Number(value).toFixed(2)} ${unit}`, title]} />
        <Line type={stepped ? 'stepAfter' : 'linear'} dataKey="value" stroke={stepped ? '#9eb9d0' : '#9dc9b7'} strokeWidth={1.7} dot={data.length === 1} isAnimationActive={false} />
        <ReferenceLine x={time} stroke="#d1dfdf" strokeDasharray="3 3" ifOverflow="discard" />
      </LineChart>
    </ResponsiveContainer></div>
  </section>;
}
export const VehicleCharts = memo(function VehicleCharts({ track, base, time }: { track: VehicleTrack; base: BaseLocation; time: number }) {
  const distance = useMemo(() => calculateDistanceSeries(track, base), [track, base]);
  const speed = useMemo(() => calculateTrackSpeedSeries(track), [track]);
  return <div className="vehicle-charts"><div className="section-eyebrow">FULL TRACK · CURSOR = CURRENT TIME</div><MetricChart title="Distance to base" unit="km" data={distance} time={time} /><MetricChart title="Speed over time" unit="km/h" data={speed} time={time} stepped /></div>;
});

import { Pause, Play, RotateCcw, SkipBack, SkipForward } from 'lucide-react';
import { useEffect, useMemo } from 'react';
import { Button } from './ui/button';
import { playbackSpeeds, usePlaybackStore, type PlaybackSpeed, type TrailMode } from '../store/playback';
import type { AnalysisData } from '../types/analysis';
import { analysisPlaybackBounds, formatClock, timelineEvents } from '../services/analysis-playback';

export function Timeline({ analysis }: { analysis: AnalysisData }) {
  const state = usePlaybackStore();
  const bounds = useMemo(() => analysisPlaybackBounds(analysis), [analysis]);
  const events = useMemo(() => timelineEvents(analysis), [analysis]);
  const range = Math.max(1, state.maxTime - state.minTime);

  useEffect(() => { usePlaybackStore.getState().initialize(bounds.minTime, bounds.maxTime); }, [bounds.minTime, bounds.maxTime]);

  return <section className="timeline playback-timeline" aria-label="Zaman çizelgesi oynatma kontrolleri">
    <div className="timeline-actions">
      <Button data-guide="timeline-restart" variant="ghost" size="icon" aria-label="Oynatımı başa al" title="Başa al" onClick={state.restart}><RotateCcw size={15} /></Button>
      <Button data-guide="timeline-step-back" variant="ghost" size="icon" aria-label="Önceki zaman adımı" title="Önceki 5 dakika" onClick={state.stepPrevious}><SkipBack size={16} /></Button>
      <Button data-guide="timeline-play" variant="outline" size="icon" disabled={state.minTime === state.maxTime} aria-label={state.isPlaying ? 'Oynatımı duraklat' : 'Oynatımı başlat'} title={state.isPlaying ? 'Duraklat' : 'Oynat'} onClick={state.togglePlaying}>{state.isPlaying ? <Pause size={16} /> : <Play size={16} />}</Button>
      <Button data-guide="timeline-step-forward" variant="ghost" size="icon" aria-label="Sonraki zaman adımı" title="Sonraki 5 dakika" onClick={state.stepNext}><SkipForward size={16} /></Button>
      <time className="simulated-time">{formatClock(state.currentTime)}</time>
      <span className="timeline-label">DURUM ZAMANI</span>
      <label className="speed-select" data-guide="timeline-speed">Hız<select aria-label="Oynatma hızı" value={state.playbackSpeed} onChange={event => state.setSpeed(Number(event.target.value) as PlaybackSpeed)}>{playbackSpeeds.map(speed => <option value={speed} key={speed}>{speed}x</option>)}</select></label>
      <label className="speed-select trail-select" data-guide="timeline-trail">İz<select aria-label="Rota izi modu" value={state.trailMode} onChange={event => state.setTrailMode(event.target.value as TrailMode)}><option value="elapsed">Gidilen rota</option><option value="full">Tüm rota</option><option value="off">Kapalı</option></select></label>
    </div>
    <div className="timeline-scrubber">
      <input className="time-slider" data-guide="timeline-slider" type="range" aria-label="Oynatma zamanı" min={state.minTime} max={state.maxTime} step="1" value={state.currentTime} disabled={state.minTime === state.maxTime} onChange={event => state.seek(Number(event.target.value))} />
      <div className="timeline-events" data-guide="timeline-events" aria-label="Zaman çizelgesi olayları">
        {events.map(event => {
          const left = `${Math.max(0, Math.min(100, (event.timestamp - state.minTime) / range * 100))}%`;
          return <button key={event.id} type="button" className={`timeline-event event-${event.type.toLowerCase()}${event.risk ? ` risk-${event.risk.toLowerCase()}` : ''}`} style={{ left }} title={`${event.label} · ${event.time}`} aria-label={`${event.time} olayına git: ${event.label}`} onClick={() => state.seek(event.timestamp)} />;
        })}
      </div>
    </div>
    <div className="timeline-bounds"><span>{formatClock(state.minTime)}</span><span>{events.length} olay</span><span>{formatClock(state.maxTime)}</span></div>
  </section>;
}

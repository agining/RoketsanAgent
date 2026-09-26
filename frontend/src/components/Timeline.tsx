import { GripVertical, Maximize2, Minimize2, Pause, Play, RotateCcw, SkipBack, SkipForward, Volume2, VolumeX } from 'lucide-react';
import { useEffect, useMemo, type PointerEvent as ReactPointerEvent } from 'react';
import { Button } from './ui/button';
import { playbackSpeeds, usePlaybackStore, type PlaybackSpeed, type TrailMode } from '../store/playback';
import { useTimelineStore } from '../store/timeline';
import { useVoiceAlertsStore } from '../store/voiceAlerts';
import type { AnalysisData } from '../types/analysis';
import { analysisPlaybackBounds, formatClock, timelineEvents } from '../services/analysis-playback';

export function Timeline({ analysis, onDragHandlePointerDown }: { analysis: AnalysisData; onDragHandlePointerDown?: (event: ReactPointerEvent<HTMLButtonElement>) => void }) {
  const state = usePlaybackStore();
  const compact = useTimelineStore(state => state.compact);
  const toggleCompact = useTimelineStore(state => state.toggleCompact);
  const voiceAlertsEnabled = useVoiceAlertsStore(state => state.enabled);
  const voiceAlertsSpeaking = useVoiceAlertsStore(state => state.isSpeaking);
  const toggleVoiceAlerts = useVoiceAlertsStore(state => state.toggleEnabled);
  const bounds = useMemo(() => analysisPlaybackBounds(analysis), [analysis]);
  const events = useMemo(() => timelineEvents(analysis), [analysis]);
  const range = Math.max(1, state.maxTime - state.minTime);

  useEffect(() => { usePlaybackStore.getState().initialize(bounds.minTime, bounds.maxTime); }, [bounds.minTime, bounds.maxTime]);

  return <section
    className={`timeline playback-timeline ${compact ? 'compact' : ''}`}
    data-tour="timeline"
    aria-label="Zaman çizelgesi oynatma kontrolleri"
  >
    <div className="timeline-actions">
      <button className="timeline-drag-handle" type="button" aria-label="Alt kontrol grubunu taşı" title="Alt kontrol grubunu taşı" onPointerDown={onDragHandlePointerDown}><GripVertical size={14} /></button>
      {!compact && <Button variant="ghost" size="icon" aria-label="Oynatımı başa al" title="Başa al" onClick={state.restart}><RotateCcw size={15} /></Button>}
      {!compact && <Button variant="ghost" size="icon" aria-label="Önceki zaman adımı" title="Önceki 5 dakika" onClick={state.stepPrevious}><SkipBack size={16} /></Button>}
      <Button variant="outline" size="icon" disabled={state.minTime === state.maxTime} aria-label={state.isPlaying ? 'Oynatımı duraklat' : 'Oynatımı başlat'} title={state.isPlaying ? 'Duraklat' : 'Oynat'} onClick={state.togglePlaying}>{state.isPlaying ? <Pause size={16} /> : <Play size={16} />}</Button>
      {!compact && <Button variant="ghost" size="icon" aria-label="Sonraki zaman adımı" title="Sonraki 5 dakika" onClick={state.stepNext}><SkipForward size={16} /></Button>}
      <time className="simulated-time">{formatClock(state.currentTime)}</time>
      {!compact && <span className="timeline-label">DURUM ZAMANI</span>}
      {!compact && <label className="speed-select">Hız<select aria-label="Oynatma hızı" value={state.playbackSpeed} onChange={event => state.setSpeed(Number(event.target.value) as PlaybackSpeed)}>{playbackSpeeds.map(speed => <option value={speed} key={speed}>{speed}x</option>)}</select></label>}
      {!compact && <label className="speed-select trail-select">İz<select aria-label="Rota izi modu" value={state.trailMode} onChange={event => state.setTrailMode(event.target.value as TrailMode)}><option value="elapsed">Gidilen rota</option><option value="full">Tüm rota</option><option value="off">Kapalı</option></select></label>}
      <Button variant="ghost" size="icon" className={`timeline-voice-toggle ${voiceAlertsEnabled ? 'on' : ''} ${voiceAlertsSpeaking ? 'speaking' : ''}`} role="switch" aria-checked={voiceAlertsEnabled} aria-label={voiceAlertsEnabled ? 'Ses açık' : 'Ses kapalı'} title={voiceAlertsEnabled ? 'Ses açık' : 'Ses kapalı'} onClick={toggleVoiceAlerts}>{voiceAlertsEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />}</Button>
      <Button variant="ghost" size="icon" className="timeline-compact-toggle" aria-label={compact ? 'Timeline genişlet' : 'Timeline küçült'} title={compact ? 'Timeline genişlet' : 'Timeline küçült'} onClick={toggleCompact}>{compact ? <Maximize2 size={14} /> : <Minimize2 size={14} />}</Button>
    </div>
    <div className="timeline-scrubber">
      <input className="time-slider" type="range" aria-label="Oynatma zamanı" min={state.minTime} max={state.maxTime} step="1" value={state.currentTime} disabled={state.minTime === state.maxTime} onChange={event => state.seek(Number(event.target.value))} />
      <div className="timeline-events" aria-label="Zaman çizelgesi olayları">
        {events.map(event => {
          const left = `${Math.max(0, Math.min(100, (event.timestamp - state.minTime) / range * 100))}%`;
          return <button key={event.id} type="button" className={`timeline-event event-${event.type.toLowerCase()}${event.risk ? ` risk-${event.risk.toLowerCase()}` : ''}`} style={{ left }} title={`${event.label} · ${event.time}`} aria-label={`${event.time} olayına git: ${event.label}`} onClick={() => state.seek(event.timestamp)} />;
        })}
      </div>
    </div>
    {!compact && <div className="timeline-bounds"><span>{formatClock(state.minTime)}</span><span>{events.length} olay</span><span>{formatClock(state.maxTime)}</span></div>}
  </section>;
}

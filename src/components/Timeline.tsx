import { Pause, Play, SkipBack } from 'lucide-react';
import { Button } from './ui/button';
import { playbackSpeeds, usePlaybackStore, type PlaybackSpeed } from '../store/playback';
import { formatTime } from '../services/playback';
export function Timeline() {
  const state = usePlaybackStore();
  return <div className="timeline" aria-label="Playback controls">
    <div className="timeline-actions">
      <Button variant="ghost" size="icon" aria-label="Jump to beginning" onClick={state.restart}><SkipBack size={16} /></Button>
      <Button variant="outline" size="icon" disabled={state.minTime === state.maxTime} aria-label={state.isPlaying ? 'Pause' : 'Play'} onClick={state.togglePlaying}>{state.isPlaying ? <Pause size={16} /> : <Play size={16} />}</Button>
      <time className="simulated-time">{formatTime(state.currentTime)}</time><span className="timeline-label">SIMULATED TIME</span>
      <label className="speed-select">Speed<select aria-label="Playback speed" value={state.playbackSpeed} onChange={event => state.setSpeed(Number(event.target.value) as PlaybackSpeed)}>{playbackSpeeds.map(speed => <option value={speed} key={speed}>{speed}x</option>)}</select></label>
    </div>
    <input className="time-slider" type="range" aria-label="Simulated time" min={state.minTime} max={state.maxTime} step="0.01" value={state.currentTime} disabled={state.minTime === state.maxTime} onChange={event => state.seek(Number(event.target.value))} />
    <div className="timeline-bounds"><span>{formatTime(state.minTime)}</span><span>{formatTime(state.maxTime)}</span></div>
  </div>;
}

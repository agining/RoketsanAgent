import { useMemo, useState, type FormEvent, type ReactNode } from 'react';
import { AlertTriangle, Bot, LoaderCircle, MessageSquare, MonitorPlay, Radio, Send, Siren, Volume2, X } from 'lucide-react';
import type { TrackingData } from '../../types/tracking';
import type { AgentAlert } from '../../services/agent-demo';
import { alertsAtTime, buildSitrep, sendAgentChat, speakText } from '../../services/agent-demo';
import { currentFrameAtTime, clockMinutes } from '../../services/operation-summary';
import { usePlaybackStore } from '../../store/playback';
import { useTrackingStore } from '../../store/tracking';
import { useReportStore } from '../../store/reports';
import { useAgentStore } from '../../store/agent';

const quickActions = [
  ['critical', 'Show critical vehicles'], ['contradictions', 'Show contradictions'], ['missed', 'Show missed detections'], ['untracked', 'Show untracked vehicles'],
] as const;
const prompts = ['En kritik araç hangisi?', 'Üsse yaklaşan araçları göster', 'Hangi raporlar çelişiyor?', 'Son 30 dakikada ne değişti?'];
type Message = { role: 'user' | 'agent'; text: string };

export function AgentConsole({ data }: { data: TrackingData }) {
  const ui = useAgentStore(), time = usePlaybackStore(state => Math.floor(state.currentTime));
  const allAlerts = useMemo(() => alertsAtTime(data, time), [data, time]);
  const alerts = ui.alertFilter === 'all' ? allAlerts : allAlerts.filter(alert => alert.kind === ui.alertFilter);
  const [sitrep, setSitrep] = useState(''), [messages, setMessages] = useState<Message[]>([]), [input, setInput] = useState('');
  const [threadId, setThreadId] = useState<string>(), [loading, setLoading] = useState(false), [error, setError] = useState('');
  const currentFrame = currentFrameAtTime(data.analysis, time);
  const focusAlert = (alert: AgentAlert) => {
    usePlaybackStore.getState().seek(clockMinutes(alert.time) * 60);
    if (alert.reportId) { useReportStore.getState().selectReport(alert.reportId); return; }
    if (alert.trackId && data.tracks.some(track => track.id === alert.trackId)) { useTrackingStore.getState().selectTrack(alert.trackId); useTrackingStore.getState().requestView('vehicle'); return; }
    if (alert.lon != null && alert.lat != null) useTrackingStore.getState().requestView('coordinate', undefined, [alert.lon, alert.lat]);
  };
  const focusIdentifier = (id: string) => {
    if (/^R\d+$/.test(id)) { useReportStore.getState().selectReport(id); return; }
    if (/^T\d+$/.test(id)) {
      if (data.tracks.some(track => track.id === id)) { useTrackingStore.getState().selectTrack(id); useTrackingStore.getState().requestView('vehicle'); return; }
      const matched = Object.values(data.analysis.frames).flatMap(frame => frame.vehicles).find(vehicle => vehicle.track_id === id);
      const offFrame = data.analysis.offframe_tracks?.[id];
      if (matched) { usePlaybackStore.getState().seek(matched.capture_min * 60); useTrackingStore.getState().requestView('coordinate', undefined, [matched.lon, matched.lat]); }
      else if (offFrame) { usePlaybackStore.getState().seek(clockMinutes(offFrame.last_time) * 60); useTrackingStore.getState().requestView('coordinate', undefined, [offFrame.lon, offFrame.lat]); }
      return;
    }
    const frame = data.analysis.frames[id] ?? Object.values(data.analysis.frames).find(frame => frame.vehicles.some(vehicle => vehicle.vehicle_id === id));
    const vehicle = frame?.vehicles.find(vehicle => vehicle.vehicle_id === id) ?? frame?.vehicles[0];
    if (frame) usePlaybackStore.getState().seek(clockMinutes(frame.capture_time) * 60);
    if (vehicle) useTrackingStore.getState().requestView('coordinate', undefined, [vehicle.lon, vehicle.lat]);
  };
  const linkedText = (text: string): ReactNode[] => text.split(/(T\d{4}|R\d{3}|img_\d{6}(?:_v\d+)?)/g).map((part, index) => /^(T\d{4}|R\d{3}|img_\d{6}(?:_v\d+)?)$/.test(part) ? <button className="agent-id-link" key={`${part}-${index}`} onClick={() => focusIdentifier(part)}>{part}</button> : part);
  const submit = async (event?: FormEvent, suggestion?: string) => {
    event?.preventDefault(); const message = (suggestion ?? input).trim(); if (!message || loading) return;
    setMessages(items => [...items, { role: 'user', text: message }]); setInput(''); setLoading(true); setError('');
    try { const reply = await sendAgentChat(message, threadId, currentFrame?.frame_id); setThreadId(reply.thread_id); setMessages(items => [...items, { role: 'agent', text: reply.answer }]); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Agent is unavailable.'); }
    finally { setLoading(false); }
  };
  const focusHighest = () => { const highest = allAlerts.find(alert => alert.kind === 'critical'); if (highest) focusAlert(highest); else { ui.setAlertFilter('critical'); setError('No high-risk vehicle is known at this time.'); } };
  const toggleDemo = () => {
    const activating = !ui.demoMode; ui.toggleDemoMode();
    if (!activating) return;
    const firstCritical = Object.values(data.analysis.frames).flatMap(frame => frame.vehicles).filter(vehicle => vehicle.risk_level === 'KRITIK').sort((a, b) => a.capture_min - b.capture_min)[0];
    if (firstCritical) { usePlaybackStore.getState().seek(firstCritical.capture_min * 60); useTrackingStore.getState().requestView('coordinate', undefined, [firstCritical.lon, firstCritical.lat]); }
  };
  return <>
    <div className="agent-launcher" role="toolbar" aria-label="Agent and demo tools"><button onClick={() => ui.setPanel(ui.panel === 'alerts' ? null : 'alerts')} aria-pressed={ui.panel === 'alerts'}><Siren size={14} /><span>Alerts</span><b>{allAlerts.length}</b></button><button onClick={() => ui.setPanel(ui.panel === 'sitrep' ? null : 'sitrep')} aria-pressed={ui.panel === 'sitrep'}><Radio size={14} /><span>SITREP</span></button><button onClick={() => ui.setPanel(ui.panel === 'chat' ? null : 'chat')} aria-pressed={ui.panel === 'chat'}><MessageSquare size={14} /><span>Agent</span></button><button onClick={toggleDemo} aria-pressed={ui.demoMode}><MonitorPlay size={14} /><span>Demo</span></button></div>
    {ui.panel && <section className={`agent-console agent-${ui.panel}`} aria-label={`${ui.panel} panel`}><header><span>{ui.panel === 'alerts' ? <Siren size={15} /> : ui.panel === 'sitrep' ? <Radio size={15} /> : <Bot size={15} />}<b>{ui.panel === 'alerts' ? 'ALERT CENTER' : ui.panel === 'sitrep' ? 'SITREP' : 'AGENT CHAT'}</b></span><button aria-label="Close agent panel" onClick={() => ui.setPanel(null)}><X size={15} /></button></header>
      {ui.panel === 'alerts' && <><div className="agent-quick-actions">{quickActions.map(([filter, label]) => <button key={filter} aria-pressed={ui.alertFilter === filter} onClick={() => ui.setAlertFilter(filter)}>{label}</button>)}<button onClick={focusHighest}>Focus highest-risk vehicle</button></div><div className="alert-center-list">{alerts.map(alert => <button key={alert.id} className={`agent-alert alert-${alert.kind}`} onClick={() => focusAlert(alert)}><span><AlertTriangle size={13} /><b>{alert.title}</b><time>{alert.time}</time></span><p>{alert.detail}</p><small>{alert.kind.replaceAll('_', ' ')}{alert.frameId ? ` · ${alert.frameId}` : ''}</small></button>)}{!alerts.length && <div className="agent-empty">No alerts match this filter at the current playback time.</div>}</div></>}
      {ui.panel === 'sitrep' && <div className="sitrep-panel"><p className="agent-note">Generated locally from structured risk, frame, vehicle and report data. No LLM call is required.</p><button className="generate-sitrep" onClick={() => setSitrep(buildSitrep(data, time))}>Generate current SITREP</button>{sitrep ? <div className="sitrep-output"><p>{linkedText(sitrep)}</p><button onClick={() => speakText(sitrep)}><Volume2 size={13} />Read aloud</button></div> : <div className="agent-empty">Generate a concise operational summary for the current timeline position.</div>}</div>}
      {ui.panel === 'chat' && <div className="chat-panel"><div className="suggested-prompts">{prompts.map(prompt => <button key={prompt} onClick={() => void submit(undefined, prompt)}>{prompt}</button>)}</div><div className="chat-messages">{messages.map((message, index) => <div key={index} className={`chat-message ${message.role}`}><span>{message.role === 'agent' ? 'AGENT' : 'YOU'}</span><p>{message.role === 'agent' ? linkedText(message.text) : message.text}</p>{message.role === 'agent' && <button aria-label="Read response aloud" onClick={() => speakText(message.text)}><Volume2 size={12} /></button>}</div>)}{!messages.length && <div className="agent-empty">Backend-ready chat. Start the Python API to enable `/api/chat`.</div>}{loading && <div className="agent-loading"><LoaderCircle size={15} />Analyzing current context…</div>}{error && <div className="agent-error">{error}</div>}</div><form onSubmit={event => void submit(event)}><textarea value={input} onChange={event => setInput(event.target.value)} placeholder="Ask about vehicles, frames or reports…" aria-label="Agent message" rows={2} /><button aria-label="Send agent message" disabled={loading || !input.trim()}><Send size={14} /></button></form></div>}
    </section>}
  </>;
}

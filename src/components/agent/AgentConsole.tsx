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
  ['critical', 'Kritik araçları göster'], ['contradictions', 'Çelişkileri göster'], ['missed', 'Kaçırılan tespitleri göster'], ['untracked', 'Takipsiz tespitleri göster'],
] as const;
const alertKindLabels: Record<AgentAlert['kind'], string> = { critical: 'Kritik risk', contradictions: 'Rapor çelişkisi', missed: 'Kaçırılan tespit', untracked: 'Takipsiz tespit', manipulation: 'Şüpheli rapor içeriği' };
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
      const matched = data.analysis.entities.find(entity => entity.track_id === id);
      if (matched) { usePlaybackStore.getState().seek(clockMinutes(matched.first_seen) * 60); useTrackingStore.getState().requestView('coordinate', undefined, [matched.latest_position.lon, matched.latest_position.lat]); }
      return;
    }
    const observation = data.analysis.untracked_observations.find(item => item.vehicle_id === id || item.image_id === id);
    if (observation) { usePlaybackStore.getState().seek(clockMinutes(observation.capture_time) * 60); useTrackingStore.getState().requestView('coordinate', undefined, [observation.position.lon, observation.position.lat]); }
  };
  const linkedText = (text: string): ReactNode[] => text.split(/(T\d{4}|R\d{3}|img_\d{6}(?:_v\d+)?)/g).map((part, index) => /^(T\d{4}|R\d{3}|img_\d{6}(?:_v\d+)?)$/.test(part) ? <button className="agent-id-link" key={`${part}-${index}`} onClick={() => focusIdentifier(part)}>{part}</button> : part);
  const submit = async (event?: FormEvent, suggestion?: string) => {
    event?.preventDefault(); const message = (suggestion ?? input).trim(); if (!message || loading) return;
    setMessages(items => [...items, { role: 'user', text: message }]); setInput(''); setLoading(true); setError('');
    try { const reply = await sendAgentChat(message, threadId, currentFrame?.frame_id); setThreadId(reply.thread_id); setMessages(items => [...items, { role: 'agent', text: reply.answer }]); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Ajan kullanılamıyor.'); }
    finally { setLoading(false); }
  };
  const focusHighest = () => { const highest = allAlerts.find(alert => alert.kind === 'critical'); if (highest) focusAlert(highest); else { ui.setAlertFilter('critical'); setError('Bu anda bilinen yüksek riskli araç yok.'); } };
  const toggleDemo = () => {
    const activating = !ui.demoMode; ui.toggleDemoMode();
    if (!activating) return;
    const firstCritical = data.analysis.entities.filter(entity => entity.risk.assessment?.risk_level === 'CRITICAL').sort((a, b) => clockMinutes(a.first_seen) - clockMinutes(b.first_seen))[0];
    if (firstCritical) { usePlaybackStore.getState().seek(clockMinutes(firstCritical.first_seen) * 60); useTrackingStore.getState().requestView('coordinate', undefined, [firstCritical.latest_position.lon, firstCritical.latest_position.lat]); }
  };
  return <>
    <div className="agent-launcher" role="toolbar" aria-label="Ajan ve demo araçları"><button onClick={() => ui.setPanel(ui.panel === 'alerts' ? null : 'alerts')} aria-pressed={ui.panel === 'alerts'}><Siren size={14} /><span>Uyarılar</span><b>{allAlerts.length}</b></button><button onClick={() => ui.setPanel(ui.panel === 'sitrep' ? null : 'sitrep')} aria-pressed={ui.panel === 'sitrep'}><Radio size={14} /><span>Durum özeti</span></button><button onClick={() => ui.setPanel(ui.panel === 'chat' ? null : 'chat')} aria-pressed={ui.panel === 'chat'}><MessageSquare size={14} /><span>Ajan</span></button><button onClick={toggleDemo} aria-pressed={ui.demoMode}><MonitorPlay size={14} /><span>Demo</span></button></div>
    {ui.panel && <section className={`agent-console agent-${ui.panel}`} aria-label={`${ui.panel} paneli`}><header><span>{ui.panel === 'alerts' ? <Siren size={15} /> : ui.panel === 'sitrep' ? <Radio size={15} /> : <Bot size={15} />}<b>{ui.panel === 'alerts' ? 'UYARI MERKEZİ' : ui.panel === 'sitrep' ? 'DURUM ÖZETİ' : 'AJAN SOHBETİ'}</b></span><button aria-label="Ajan panelini kapat" onClick={() => ui.setPanel(null)}><X size={15} /></button></header>
      {ui.panel === 'alerts' && <><div className="agent-quick-actions">{quickActions.map(([filter, label]) => <button key={filter} aria-pressed={ui.alertFilter === filter} onClick={() => ui.setAlertFilter(filter)}>{label}</button>)}<button onClick={focusHighest}>En yüksek riskli araca odaklan</button></div><div className="alert-center-list">{alerts.map(alert => <button key={alert.id} className={`agent-alert alert-${alert.kind}`} onClick={() => focusAlert(alert)}><span><AlertTriangle size={13} /><b>{alert.title}</b><time>{alert.time}</time></span><p>{alert.detail}</p><small>{alertKindLabels[alert.kind]}{alert.frameId ? ` · ${alert.frameId}` : ''}</small></button>)}{!alerts.length && <div className="agent-empty">Geçerli playback zamanında bu filtreyle eşleşen uyarı yok.</div>}</div></>}
      {ui.panel === 'sitrep' && <div className="sitrep-panel"><p className="agent-note">Yapılandırılmış risk, görüntü, araç ve rapor verilerinden yerel olarak oluşturulur. LLM çağrısı gerekmez.</p><button className="generate-sitrep" onClick={() => setSitrep(buildSitrep(data, time))}>Güncel durum özetini üret</button>{sitrep ? <div className="sitrep-output"><p>{linkedText(sitrep)}</p><button onClick={() => speakText(sitrep)}><Volume2 size={13} />Sesli oku</button></div> : <div className="agent-empty">Geçerli timeline konumu için kısa operasyon özeti üretin.</div>}</div>}
      {ui.panel === 'chat' && <div className="chat-panel"><div className="suggested-prompts">{prompts.map(prompt => <button key={prompt} onClick={() => void submit(undefined, prompt)}>{prompt}</button>)}</div><div className="chat-messages">{messages.map((message, index) => <div key={index} className={`chat-message ${message.role}`}><span>{message.role === 'agent' ? 'AJAN' : 'SİZ'}</span><p>{message.role === 'agent' ? linkedText(message.text) : message.text}</p>{message.role === 'agent' && <button aria-label="Yanıtı sesli oku" onClick={() => speakText(message.text)}><Volume2 size={12} /></button>}</div>)}{!messages.length && <div className="agent-empty">Backend’e hazır sohbet. `/api/chat` için Python API’yi başlatın.</div>}{loading && <div className="agent-loading"><LoaderCircle size={15} />Güncel bağlam analiz ediliyor…</div>}{error && <div className="agent-error">{error}</div>}</div><form onSubmit={event => void submit(event)}><textarea value={input} onChange={event => setInput(event.target.value)} placeholder="Araçlar, görüntüler veya raporlar hakkında sorun…" aria-label="Ajan mesajı" rows={2} /><button aria-label="Ajan mesajını gönder" disabled={loading || !input.trim()}><Send size={14} /></button></form></div>}
    </section>}
  </>;
}

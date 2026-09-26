import { useState, type FormEvent, type ReactNode } from 'react';
import { Bot, LoaderCircle, Mic, Send, Square, X } from 'lucide-react';
import type { AnalysisData } from '../../types/analysis';
import { api } from '../../services/api';
import { useSpeechToText } from '../../hooks/useSpeechToText';
import { clockSeconds } from '../../services/analysis-playback';
import { usePlaybackStore } from '../../store/playback';
import { useTrackingStore } from '../../store/tracking';

type Message = { role: 'user' | 'agent'; text: string };
const prompts = ['En kritik araç hangisi?', 'Üsse yaklaşan araçları özetle', 'Hangi raporlar çelişiyor?', 'Seçili kareyi değerlendir'];
const ID_PATTERN = /(T\d{4}|img_\d{6}(?:_v\d+|_trk_T\d{4})?)/g;
const IS_ID = /^(T\d{4}|img_\d{6}(?:_v\d+|_trk_T\d{4})?)$/;

/** Chat with the API's LangChain agent (POST /api/chat). The selected track's frame is sent as context. */
export function AgentChat({ analysis, frameId, onSelectTrack, onClose }: { analysis: AnalysisData; frameId: string | null; onSelectTrack: (trackId: string) => void; onClose: () => void }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [threadId, setThreadId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const llmEnabled = analysis.summary.llm_enabled;
  const speech = useSpeechToText(text => setInput(current => current.trim() ? `${current.trimEnd()} ${text}` : text));
  const speechLabel = speech.state === 'recording' ? 'Ses kaydını durdur' : 'Sesle yaz';

  const focus = (id: string) => {
    const entity = analysis.entities.find(item => item.track_id === id);
    if (entity) { if (entity.observed_at) usePlaybackStore.getState().seek(clockSeconds(entity.observed_at)); onSelectTrack(id); return; }
    const vehicle = analysis.untracked.find(item => item.vehicle_id === id) ?? analysis.untracked.find(item => item.frame_id === id);
    const frame = analysis.frames.find(item => item.frame_id === id || id.startsWith(`${item.frame_id}_`));
    const target = vehicle ?? (frame ? { capture_time: frame.capture_time, lat: frame.center[0], lon: frame.center[1] } : null);
    if (target) { usePlaybackStore.getState().seek(clockSeconds(target.capture_time)); useTrackingStore.getState().requestView('coordinate', undefined, [target.lon, target.lat]); }
  };
  const linked = (text: string): ReactNode[] => text.split(ID_PATTERN).map((part, index) => IS_ID.test(part)
    ? <button className="agent-id-link" key={`${part}-${index}`} onClick={() => focus(part)}>{part}</button>
    : part);

  const submit = async (event?: FormEvent, suggestion?: string) => {
    event?.preventDefault();
    const message = (suggestion ?? input).trim();
    if (!message || loading) return;
    setMessages(items => [...items, { role: 'user', text: message }]); setInput(''); setLoading(true); setError('');
    try {
      const reply = await api.chat(message, threadId, frameId);
      setThreadId(reply.thread_id); setMessages(items => [...items, { role: 'agent', text: reply.answer }]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Ajan kullanılamıyor.');
    } finally { setLoading(false); }
  };

  return <section className="agent-console agent-chat map-agent-chat" data-guide="agent-chat" aria-label="Ajan sohbeti">
    <header><span><Bot size={15} /><b>AJAN SOHBETİ</b>{frameId && <small>bağlam: {frameId}</small>}</span><button aria-label="Ajan panelini kapat" onClick={onClose}><X size={15} /></button></header>
    <div className="chat-panel">
      {!llmEnabled && <p className="agent-note">API'de LLM kapalı (OPENAI_API_KEY tanımlı değil); sohbet 503 döner.</p>}
      <div className="suggested-prompts">{prompts.map(prompt => <button key={prompt} disabled={loading} onClick={() => void submit(undefined, prompt)}>{prompt}</button>)}</div>
      <div className="chat-messages">
        {messages.map((message, index) => <div key={index} className={`chat-message ${message.role}`}><span>{message.role === 'agent' ? 'AJAN' : 'SİZ'}</span><p>{message.role === 'agent' ? linked(message.text) : message.text}</p></div>)}
        {!messages.length && <div className="agent-empty">Araçlar, kareler veya raporlar hakkında sorun. Yanıtlar API'deki ajandan gelir.</div>}
        {loading && <div className="agent-loading"><LoaderCircle size={15} className="spinning" />Ajan yanıtlıyor…</div>}
        {error && <div className="agent-error" role="alert">{error}</div>}
        {speech.state === 'loading-model' && <div className="agent-loading"><LoaderCircle size={15} className="spinning" />Konuşma modeli yükleniyor (ilk seferde uzun sürebilir)…</div>}
        {speech.state === 'recording' && <div className="agent-loading voice-recording"><span className="voice-dot" />Dinleniyor… bitirmek için ■ düğmesine basın</div>}
        {speech.state === 'transcribing' && <div className="agent-loading"><LoaderCircle size={15} className="spinning" />Ses metne çevriliyor…</div>}
        {speech.error && <div className="agent-error" role="alert">{speech.error}</div>}
      </div>
      <form onSubmit={event => void submit(event)}><textarea data-guide="chat-input" value={input} onChange={event => setInput(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void submit(); } }} placeholder="Ajana sorun…" aria-label="Ajan mesajı" rows={2} /><button type="button" data-guide="chat-mic" className={`voice-input${speech.state === 'recording' ? ' recording' : ''}`} aria-label={speechLabel} title={speechLabel} aria-pressed={speech.state === 'recording'} disabled={speech.busy} onClick={speech.toggle}>{speech.busy ? <LoaderCircle size={14} className="spinning" /> : speech.state === 'recording' ? <Square size={12} /> : <Mic size={14} />}</button><button data-guide="chat-send" aria-label="Ajan mesajını gönder" disabled={loading || !input.trim()}><Send size={14} /></button></form>
    </div>
  </section>;
}

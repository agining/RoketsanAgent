import { useState, type FormEvent, type PointerEvent as ReactPointerEvent } from 'react';
import { Bot, LoaderCircle, Send, X } from 'lucide-react';
import type { AnalysisData } from '../../types/analysis';
import { clockSeconds } from '../../services/analysis-playback';
import { useAgentChatStore } from '../../store/agentChat';
import { usePanelLayoutStore } from '../../store/panelLayout';
import { usePlaybackStore } from '../../store/playback';
import { useTrackingStore } from '../../store/tracking';
import { AgentMarkdown } from './AgentMarkdown';

const prompts = ['En kritik araç hangisi?', 'Üsse yaklaşan araçları özetle', 'Hangi raporlar çelişiyor?', 'Seçili kareyi değerlendir'];

/** Chat with the API's LangChain agent (POST /api/chat). The selected track's frame is sent as context. */
export function AgentChat({ analysis, frameId, onSelectTrack, onClose }: { analysis: AnalysisData; frameId: string | null; onSelectTrack: (trackId: string) => void; onClose: () => void }) {
  const [input, setInput] = useState('');
  const messages = useAgentChatStore(state => state.messages);
  const pending = useAgentChatStore(state => state.pending);
  const send = useAgentChatStore(state => state.send);
  const agentWidth = usePanelLayoutStore(state => state.agentWidth);
  const setAgentWidth = usePanelLayoutStore(state => state.setAgentWidth);
  const llmEnabled = analysis.summary.llm_enabled;

  const focus = (id: string) => {
    const entity = analysis.entities.find(item => item.track_id === id);
    if (entity) { if (entity.observed_at) usePlaybackStore.getState().seek(clockSeconds(entity.observed_at)); onSelectTrack(id); return; }
    const vehicle = analysis.untracked.find(item => item.vehicle_id === id) ?? analysis.untracked.find(item => item.frame_id === id);
    const frame = analysis.frames.find(item => item.frame_id === id || id.startsWith(`${item.frame_id}_`));
    const target = vehicle ?? (frame ? { capture_time: frame.capture_time, lat: frame.center[0], lon: frame.center[1] } : null);
    if (target) { usePlaybackStore.getState().seek(clockSeconds(target.capture_time)); useTrackingStore.getState().requestView('coordinate', undefined, [target.lon, target.lat]); }
  };

  const submit = async (event?: FormEvent, suggestion?: string) => {
    event?.preventDefault();
    const message = (suggestion ?? input).trim();
    if (!message || pending) return;
    setInput('');
    void send(message, frameId);
  };

  const startResize = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const startWidth = agentWidth;
    const move = (moveEvent: PointerEvent) => setAgentWidth(startWidth + startX - moveEvent.clientX);
    const stop = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', stop);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', stop, { once: true });
  };

  return <section className="agent-console agent-chat map-agent-chat" data-tour="agent-panel" aria-label="Ajan sohbeti" style={{ width: `min(${agentWidth}px, calc(100vw - 28px))` }}>
    <div className="panel-resize-handle left-edge" role="separator" aria-orientation="vertical" aria-label="Ajan paneli genişliği" onPointerDown={startResize} />
    <header><span><Bot size={15} /><b>AJAN SOHBETİ</b>{frameId && <small>bağlam: {frameId}</small>}</span><button aria-label="Ajan panelini kapat" onClick={onClose}><X size={15} /></button></header>
    <div className="chat-panel">
      {!llmEnabled && <p className="agent-note">API'de LLM kapalı (OPENAI_API_KEY tanımlı değil); sohbet 503 döner.</p>}
      <div className="suggested-prompts">{prompts.map(prompt => <button key={prompt} disabled={pending} onClick={() => void submit(undefined, prompt)}>{prompt}</button>)}</div>
      <div className="chat-messages">
        {messages.map(message => <div key={message.id} className={`chat-message ${message.role === 'assistant' ? 'agent' : 'user'} ${message.status}`}>
          <span>{message.role === 'assistant' ? 'AJAN' : 'SİZ'}</span>
          {message.status === 'loading'
            ? <p className="message-loading"><LoaderCircle size={13} className="spinning" />Ajan yanıtlıyor…</p>
            : message.role === 'assistant'
              ? <AgentMarkdown text={message.text} onSelectId={focus} />
              : <p>{message.text}</p>}
        </div>)}
        {!messages.length && <div className="agent-empty">Araçlar, kareler veya raporlar hakkında sorun. Yanıtlar API'deki ajandan gelir.</div>}
      </div>
      <form onSubmit={event => void submit(event)}><textarea value={input} onChange={event => setInput(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void submit(); } }} placeholder="Ajana sorun…" aria-label="Ajan mesajı" rows={2} /><button aria-label="Ajan mesajını gönder" disabled={pending || !input.trim()}><Send size={14} /></button></form>
    </div>
  </section>;
}

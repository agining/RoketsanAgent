import { useState } from 'react';
import { CircleHelp, LoaderCircle, Square, X } from 'lucide-react';
import { api } from '../../services/api';
import { useSpeechToText } from '../../hooks/useSpeechToText';
import { useGuideStore } from '../../store/guide';

type Notice = { tone: 'info' | 'error'; text: string };

/**
 * Top-bar voice help: record a question ("Filtre nasıl yapılır?") → Whisper STT → POST /api/ui-guide →
 * the returned element sequence is highlighted by GuideOverlay.
 */
export function VoiceGuideButton() {
  const [asking, setAsking] = useState(false);
  const [question, setQuestion] = useState('');
  const [notice, setNotice] = useState<Notice | null>(null);

  const ask = async (text: string) => {
    setQuestion(text); setAsking(true);
    try {
      const plan = await api.uiGuide(text);
      if (useGuideStore.getState().start(plan)) setNotice(null);
      else setNotice({ tone: 'info', text: plan.message || 'Bu soru için vurgulanacak bir öğe bulunamadı.' });
    } catch (cause) {
      setNotice({ tone: 'error', text: cause instanceof Error ? cause.message : 'Yardım alınamadı.' });
    } finally { setAsking(false); }
  };
  const speech = useSpeechToText(text => void ask(text));

  const onClick = () => {
    if (speech.state === 'idle') { useGuideStore.getState().stop(); setNotice(null); setQuestion(''); }
    speech.toggle();
  };

  const busy = speech.busy || asking;
  const recording = speech.state === 'recording';
  const status = speech.state === 'loading-model' ? 'Konuşma modeli yükleniyor…'
    : recording ? 'Dinleniyor… sorunuzu söyleyin, bitince ■ düğmesine basın.'
      : speech.state === 'transcribing' ? 'Ses metne çevriliyor…'
        : asking ? 'Yardım adımları hazırlanıyor…' : '';
  const error = speech.error ? { tone: 'error' as const, text: speech.error } : notice;
  const label = recording ? 'Sesli soruyu bitir' : 'Nasıl yapılır? Sesli yardım iste';

  return <div className="voice-guide-anchor">
    <button className={`voice-guide-button${recording ? ' recording' : ''}`} data-guide="topbar-voice-guide" aria-label={label} title={label} aria-pressed={recording} disabled={busy} onClick={onClick}>
      {busy ? <LoaderCircle size={14} className="spinning" /> : recording ? <Square size={12} /> : <CircleHelp size={14} />}
      <span>{recording ? 'Bitir' : 'Nasıl yapılır?'}</span>
    </button>
    {(status || error) && <div className={`voice-guide-status ${error && !status ? error.tone : ''}`} role="status">
      {question && !recording && <q>{question}</q>}
      <span>{status || error?.text}</span>
      {!status && <button aria-label="Kapat" onClick={() => { setNotice(null); speech.clearError(); }}><X size={12} /></button>}
    </div>}
  </div>;
}

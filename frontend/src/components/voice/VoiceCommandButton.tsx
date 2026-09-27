import { useState } from 'react';
import { LoaderCircle, Mic, Square, X } from 'lucide-react';
import { api } from '../../services/api';
import { buildUiContext, runUiActions, type UiController } from '../../services/uiActions';
import { useSpeechToText } from '../../hooks/useSpeechToText';

type Notice = { tone: 'info' | 'error'; text: string; details?: string[] };

/**
 * Top-bar voice commands: record ("Sadece otobüsleri göster") → Whisper STT → POST /api/ui-command with the current
 * UI context → the returned actions are carried out with the app's existing functions (services/uiActions.ts).
 */
export function VoiceCommandButton({ controller }: { controller: () => UiController }) {
  const [running, setRunning] = useState(false);
  const [command, setCommand] = useState('');
  const [notice, setNotice] = useState<Notice | null>(null);

  const run = async (text: string) => {
    setCommand(text); setRunning(true);
    try {
      const plan = await api.uiCommand(text, buildUiContext(controller()));
      if (!plan.actions.length) { setNotice({ tone: 'info', text: plan.message || 'Bu komut için uygulanacak bir eylem bulunamadı.' }); return; }
      const results = await runUiActions(plan.actions, controller());
      const failed = results.filter(result => !result.ok);
      const notes = results.filter(result => result.ok && result.note).map(result => result.note as string);
      setNotice({
        tone: failed.length === results.length ? 'error' : 'info',
        text: plan.message || (failed.length ? 'Komut kısmen uygulandı.' : 'Komut uygulandı.'),
        details: [...notes, ...failed.map(result => `${result.action}: ${result.note}`)],
      });
    } catch (cause) {
      setNotice({ tone: 'error', text: cause instanceof Error ? cause.message : 'Komut uygulanamadı.' });
    } finally { setRunning(false); }
  };
  const speech = useSpeechToText(text => void run(text));

  const onClick = () => {
    if (speech.state === 'idle') { setNotice(null); setCommand(''); speech.clearError(); }
    speech.toggle();
  };

  const busy = speech.busy || running;
  const recording = speech.state === 'recording';
  const status = speech.state === 'loading-model' ? 'Konuşma modeli yükleniyor (ilk seferde uzun sürebilir)…'
    : recording ? 'Dinleniyor… komutunuzu söyleyin, bitince ■ düğmesine basın.'
      : speech.state === 'transcribing' ? 'Ses metne çevriliyor…'
        : running ? 'Komut uygulanıyor…' : '';
  const shown = speech.error ? { tone: 'error' as const, text: speech.error } : notice;
  const label = recording ? 'Sesli komutu bitir' : 'Sesli komut ver';

  return <div className="voice-command-anchor">
    <button type="button" className={`voice-command-button${recording ? ' recording' : ''}`} aria-label={label} title={label} aria-pressed={recording} disabled={busy} onClick={onClick}>
      {busy ? <LoaderCircle size={14} className="spinning" /> : recording ? <Square size={12} /> : <Mic size={14} />}
      <span>{recording ? 'Bitir' : 'Sesli Komut'}</span>
    </button>
    {(status || shown) && <div className={`voice-command-status ${shown && !status ? shown.tone : ''}`} role="status">
      {command && !recording && <q>{command}</q>}
      <span>{status || shown?.text}</span>
      {!status && <button type="button" aria-label="Kapat" onClick={() => { setNotice(null); speech.clearError(); }}><X size={12} /></button>}
      {!status && shown && 'details' in shown && shown.details?.length ? <ul>{shown.details.map(detail => <li key={detail}>{detail}</li>)}</ul> : null}
    </div>}
  </div>;
}

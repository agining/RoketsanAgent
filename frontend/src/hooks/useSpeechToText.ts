import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import { decodeToMono16k, encodeWav } from '../services/audio/wav';

/** idle → (loading-model) → recording → transcribing → idle */
export type SpeechState = 'idle' | 'loading-model' | 'recording' | 'transcribing';

/**
 * Microphone capture + Whisper transcription through the API.
 * `start()` loads the model on the API if needed (POST /api/asr/start) and begins recording;
 * `stop()` ends recording, converts it to 16 kHz WAV and calls `onText` with the transcript.
 */
export function useSpeechToText(onText: (text: string) => void) {
  const [state, setState] = useState<SpeechState>('idle');
  const [error, setError] = useState('');
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const onTextRef = useRef(onText);
  onTextRef.current = onText;

  const releaseMic = (recorder: MediaRecorder | null) => recorder?.stream.getTracks().forEach(track => track.stop());

  useEffect(() => () => {
    const recorder = recorderRef.current;
    recorderRef.current = null;
    if (recorder && recorder.state !== 'inactive') { recorder.onstop = null; recorder.stop(); }
    releaseMic(recorder);
  }, []);

  const start = useCallback(async () => {
    if (state !== 'idle') return;
    setError('');
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError('Tarayıcı mikrofon kaydını desteklemiyor (HTTPS veya localhost gerekir).');
      return;
    }
    try {
      setState('loading-model');
      const status = await api.asrStatus();
      if (!status.loaded) await api.asrStart();

      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = event => { if (event.data.size) chunksRef.current.push(event.data); };
      recorder.onstop = async () => {
        releaseMic(recorder);
        recorderRef.current = null;
        const recording = new Blob(chunksRef.current, { type: recorder.mimeType });
        chunksRef.current = [];
        try {
          const wav = encodeWav(await decodeToMono16k(recording));
          const { text } = await api.asrTranscribe(wav);
          if (text) onTextRef.current(text);
          else setError('Konuşma algılanamadı.');
        } catch (cause) {
          setError(cause instanceof Error ? cause.message : 'Ses metne çevrilemedi.');
        } finally { setState('idle'); }
      };
      recorderRef.current = recorder;
      recorder.start();
      setState('recording');
    } catch (cause) {
      const denied = cause instanceof DOMException && (cause.name === 'NotAllowedError' || cause.name === 'SecurityError');
      setError(denied ? 'Mikrofon izni verilmedi.' : cause instanceof Error ? cause.message : 'Kayıt başlatılamadı.');
      setState('idle');
    }
  }, [state]);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === 'inactive') return;
    setState('transcribing');
    recorder.stop();
  }, []);

  const toggle = useCallback(() => { if (state === 'recording') stop(); else void start(); }, [state, start, stop]);

  const clearError = useCallback(() => setError(''), []);

  return { state, error, clearError, start, stop, toggle, busy: state === 'loading-model' || state === 'transcribing' };
}

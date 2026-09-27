import { apiUrl } from '../api';
/**
 * Pluggable TTS Provider Interface.
 * Allows seamless switching between Browser SpeechSynthesis and ElevenLabs (or other external providers).
 */

export interface TTSOptions {
  rate?: number;       // Speech rate (0.5 to 2.5)
  pitch?: number;      // Pitch (0.5 to 1.5)
  volume?: number;     // Volume (0 to 1)
  lang?: string;       // Language tag, default 'tr-TR'
  voiceName?: string;  // Specific voice name if available
}

export interface TTSProvider {
  name: string;
  speak(text: string, options?: TTSOptions): Promise<void>;
  stop(): void;
  isSpeaking(): boolean;
  getVoices?(): Promise<SpeechSynthesisVoice[]>;
}

/**
 * Zero-latency Web Audio API tactical alert chime.
 * Triggers in <1ms without any network or speech engine startup delay.
 */
let sharedAudioCtx: AudioContext | null = null;

export function playTacticalAlertChime(risk: string, volume = 1.0) {
  if (typeof window === 'undefined') return;
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    if (!sharedAudioCtx || sharedAudioCtx.state === 'closed') {
      sharedAudioCtx = new AudioCtx();
    }
    if (sharedAudioCtx.state === 'suspended') {
      void sharedAudioCtx.resume();
    }

    const ctx = sharedAudioCtx;
    const now = ctx.currentTime;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(Math.max(0.01, Math.min(1, volume * 0.24)), now);
    gain.connect(ctx.destination);

    if (risk === 'CRITICAL') {
      // High-priority dual tactical chirp: 980Hz -> 1320Hz
      const osc1 = ctx.createOscillator();
      osc1.type = 'sine';
      osc1.frequency.setValueAtTime(980, now);
      osc1.connect(gain);
      osc1.start(now);
      osc1.stop(now + 0.05);

      const osc2 = ctx.createOscillator();
      osc2.type = 'sine';
      osc2.frequency.setValueAtTime(1320, now + 0.06);
      osc2.connect(gain);
      osc2.start(now + 0.06);
      osc2.stop(now + 0.12);

      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
    } else if (risk === 'HIGH') {
      // Warning chirp: 750Hz -> 980Hz
      const osc = ctx.createOscillator();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(750, now);
      osc.frequency.exponentialRampToValueAtTime(980, now + 0.07);
      osc.connect(gain);
      osc.start(now);
      osc.stop(now + 0.08);

      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.1);
    } else {
      // Subtle discrete notify pip: 620Hz
      const osc = ctx.createOscillator();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(620, now);
      osc.connect(gain);
      osc.start(now);
      osc.stop(now + 0.04);

      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.06);
    }
  } catch {
    // AudioContext autoplay restriction or error
  }
}

/**
 * Default Browser TTS Provider using window.speechSynthesis.
 * Prioritizes on-device local voices to eliminate cloud roundtrip delays.
 */
export class BrowserSpeechTTSProvider implements TTSProvider {
  public readonly name = 'browser-speech';
  private currentUtterance: SpeechSynthesisUtterance | null = null;
  private voices: SpeechSynthesisVoice[] = [];
  private activeReject: ((reason?: unknown) => void) | null = null;
  private loggedVoiceName: string | null = null;
  private warnedMissingTurkishVoice = false;

  constructor() {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      this.loadVoices();
      if (window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = () => this.loadVoices();
      }
    }
  }

  private loadVoices() {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    this.voices = window.speechSynthesis.getVoices();
  }

  public async getVoices(): Promise<SpeechSynthesisVoice[]> {
    if (this.voices.length === 0) {
      this.loadVoices();
    }
    return this.voices;
  }

  private async waitForVoices(): Promise<void> {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;

    for (let attempt = 0; attempt < 12; attempt += 1) {
      this.loadVoices();
      if (this.voices.some((voice) => voice.lang.toLowerCase().startsWith('tr'))) {
        return;
      }

      await new Promise<void>((resolve) => {
        window.setTimeout(resolve, 150);
      });
    }

    this.loadVoices();
  }

  public prewarm(): void {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    try {
      this.loadVoices();
      if (window.speechSynthesis.paused) {
        window.speechSynthesis.resume();
      }
    } catch {
      // ignore
    }
  }

  private getBestTurkishVoice(): SpeechSynthesisVoice | null {
    if (!this.voices.length) this.loadVoices();

    const scoreVoice = (voice: SpeechSynthesisVoice) => {
      const lang = voice.lang.toLowerCase();
      const name = voice.name.toLowerCase();
      let score = 0;
      if (lang === 'tr-tr') score += 100;
      else if (lang.startsWith('tr')) score += 85;
      if (voice.localService) score += 20;
      if (voice.default) score += 8;
      if (name.includes('tolga') || name.includes('emel')) score += 18;
      if (name.includes('turkish') || name.includes('türkçe') || name.includes('turkce')) score += 12;
      return score;
    };

    const turkishVoices = this.voices.filter((voice) =>
      voice.lang.toLowerCase().startsWith('tr')
    );

    return turkishVoices.sort((a, b) => scoreVoice(b) - scoreVoice(a))[0] ?? null;
  }

  public isSpeaking(): boolean {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return false;
    return window.speechSynthesis.speaking;
  }

  public stop(): void {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;

    if (this.activeReject) {
      this.activeReject(new Error('TTS_STOPPED'));
      this.activeReject = null;
    }

    try {
      window.speechSynthesis.cancel();
    } catch {
      // Ignore cancellation errors
    }

    this.currentUtterance = null;
  }

  public async speak(text: string, options: TTSOptions = {}): Promise<void> {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      return Promise.resolve();
    }

    if (!text || !text.trim()) {
      return Promise.resolve();
    }

    await this.waitForVoices();

    return new Promise<void>((resolve, reject) => {
      this.activeReject = reject;

      try {
        const utterance = new SpeechSynthesisUtterance(text);
        this.currentUtterance = utterance;

        // Language & Voice
        utterance.lang = options.lang || 'tr-TR';
        const preferredVoice = this.getBestTurkishVoice();
        if (preferredVoice) {
          utterance.voice = preferredVoice;
          if (this.loggedVoiceName !== preferredVoice.name) {
            this.loggedVoiceName = preferredVoice.name;
            this.warnedMissingTurkishVoice = false;
            console.debug(
              `Voice alerts using TTS voice: ${preferredVoice.name} (${preferredVoice.lang})`
            );
          }
        } else if (!this.warnedMissingTurkishVoice) {
          this.warnedMissingTurkishVoice = true;
          console.warn(
            'Türkçe TTS sesi bulunamadı. Tarayıcıda veya işletim sisteminde Türkçe ses paketi etkin değilse konuşma varsayılan aksanla okunabilir.'
          );
        }

        // Turkish browser voices become hard to parse above normal speed.
        const targetRate = options.rate ?? 0.88;
        utterance.rate = Math.max(0.72, Math.min(1.08, targetRate));

        // Pitch & Volume
        utterance.pitch = options.pitch ?? 0.96;
        utterance.volume = options.volume ?? 1.0;

        utterance.onend = () => {
          this.activeReject = null;
          this.currentUtterance = null;
          resolve();
        };

        utterance.onerror = (event) => {
          this.activeReject = null;
          this.currentUtterance = null;
          // 'canceled' or 'interrupted' is normal when user clicks stop or new alert preempts
          if (event.error === 'canceled' || event.error === 'interrupted') {
            resolve();
          } else {
            reject(new Error(`Speech error: ${event.error}`));
          }
        };

        // Resume if synth got paused by browser power-saving
        if (window.speechSynthesis.paused) {
          window.speechSynthesis.resume();
        }

        window.speechSynthesis.speak(utterance);
      } catch (err) {
        this.activeReject = null;
        this.currentUtterance = null;
        reject(err);
      }
    });
  }
}

const DEFAULT_ELEVENLABS_VOICE_ID =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_ELEVENLABS_VOICE_ID) ||
  'EXAVITQu4vr4xnSDxMaL'; // Sarah - Net, doğal Türkçe diksiyon ve kararlı premade ses

const DEFAULT_ELEVENLABS_MODEL_ID =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_ELEVENLABS_MODEL_ID) ||
  'eleven_multilingual_v2';

/**
 * ElevenLabs Cloud TTS Provider.
 * Provides ultra-realistic voice synthesis with in-memory audio caching,
 * active request cancellation, and graceful fallback to browser speech.
 */
export class ElevenLabsTTSProvider implements TTSProvider {
  public readonly name = 'elevenlabs';
  private voiceId: string;
  private modelId: string;
  private currentAudio: HTMLAudioElement | null = null;
  private currentUrl: string | null = null;
  private abortController: AbortController | null = null;
  private activeReject: ((reason?: unknown) => void) | null = null;
  private fallbackProvider: BrowserSpeechTTSProvider | null = null;
  private audioCache = new Map<string, Blob>();
  private readonly maxCacheSize = 40;

  constructor(
    voiceId = DEFAULT_ELEVENLABS_VOICE_ID,
    modelId = DEFAULT_ELEVENLABS_MODEL_ID
  ) {
    this.voiceId = voiceId;
    this.modelId = modelId;
  }

  public configure(voiceId?: string, modelId?: string) {
    if (voiceId) this.voiceId = voiceId;
    if (modelId) this.modelId = modelId;
  }

  public isSpeaking(): boolean {
    return (this.currentAudio !== null && !this.currentAudio.paused) || Boolean(this.fallbackProvider?.isSpeaking());
  }

  public stop(): void {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }

    if (this.activeReject) {
      this.activeReject(new Error('TTS_STOPPED'));
      this.activeReject = null;
    }

    if (this.currentAudio) {
      this.currentAudio.onended = null;
      this.currentAudio.onerror = null;
      try {
        this.currentAudio.pause();
        this.currentAudio.currentTime = 0;
        this.currentAudio.src = '';
      } catch {
        // ignore
      }
      this.currentAudio = null;
    }

    if (this.currentUrl) {
      try {
        URL.revokeObjectURL(this.currentUrl);
      } catch {
        // ignore
      }
      this.currentUrl = null;
    }

    if (this.fallbackProvider) {
      this.fallbackProvider.stop();
    }
  }

  private cacheKey(text: string): string {
    return `${this.voiceId}:${this.modelId}:${text.trim()}`;
  }

  public async speak(text: string, options: TTSOptions = {}): Promise<void> {
    if (!text || !text.trim()) {
      return Promise.resolve();
    }

    this.stop();

    const controller = new AbortController();
    this.abortController = controller;

    try {
      const key = this.cacheKey(text);
      let blob = this.audioCache.get(key);

      if (!blob) {
        const response = await fetch(
          apiUrl('/api/voice/synthesize'),
          {
            method: 'POST',
            signal: controller.signal,
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              text,
              voice_id: this.voiceId,
              model_id: this.modelId,
              voice_settings: {
                stability: 0.5,
                similarity_boost: 0.75,
              },
            }),
          }
        );

        if (!response.ok) {
          const errorText = await response.text().catch(() => '');
          throw new Error(`ElevenLabs API hatası: ${response.status} ${response.statusText} ${errorText}`);
        }

        blob = await response.blob();

        if (this.audioCache.size >= this.maxCacheSize) {
          const oldestKey = this.audioCache.keys().next().value;
          if (oldestKey) this.audioCache.delete(oldestKey);
        }
        this.audioCache.set(key, blob);
      }

      if (controller.signal.aborted) {
        throw new Error('TTS_STOPPED');
      }

      const url = URL.createObjectURL(blob);
      this.currentUrl = url;
      const audio = new Audio(url);
      this.currentAudio = audio;

      if (options.rate) audio.playbackRate = options.rate;
      if (options.volume !== undefined) audio.volume = options.volume;

      return await new Promise<void>((resolve, reject) => {
        this.activeReject = reject;

        audio.onended = () => {
          this.cleanupAudio();
          resolve();
        };

        audio.onerror = () => {
          this.cleanupAudio();
          reject(new Error('ElevenLabs ses oynatma hatası'));
        };

        audio.play().catch((err) => {
          this.cleanupAudio();
          reject(err);
        });
      });
    } catch (err: unknown) {
      if (err instanceof Error && (err.name === 'AbortError' || err.message === 'TTS_STOPPED')) {
        return;
      }

      this.cleanupAudio();

      console.warn('ElevenLabs TTS uyarısı (tarayıcı sesine geçiliyor):', err);
      return this.getFallback().speak(text, options);
    }
  }

  private cleanupAudio() {
    this.activeReject = null;
    this.abortController = null;
    if (this.currentAudio) {
      this.currentAudio = null;
    }
    if (this.currentUrl) {
      try {
        URL.revokeObjectURL(this.currentUrl);
      } catch {
        // ignore
      }
      this.currentUrl = null;
    }
  }

  private getFallback(): BrowserSpeechTTSProvider {
    if (!this.fallbackProvider) {
      this.fallbackProvider = new BrowserSpeechTTSProvider();
    }
    return this.fallbackProvider;
  }
}

// Default singleton instance using ElevenLabs with browser speech fallback
export const defaultTTSProvider: TTSProvider = new ElevenLabsTTSProvider();

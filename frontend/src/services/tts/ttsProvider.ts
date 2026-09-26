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

/**
 * Placeholder for future ElevenLabs integration.
 * Once ready, add apiKey & voiceId configuration.
 */
export class ElevenLabsTTSProvider implements TTSProvider {
  public readonly name = 'elevenlabs';
  private apiKey: string;
  private voiceId: string;
  private currentAudio: HTMLAudioElement | null = null;

  constructor(apiKey = '', voiceId = '21m00Tcm4TlvDq8ikWAM') {
    this.apiKey = apiKey;
    this.voiceId = voiceId;
  }

  public setCredentials(apiKey: string, voiceId?: string) {
    this.apiKey = apiKey;
    if (voiceId) this.voiceId = voiceId;
  }

  public isSpeaking(): boolean {
    return this.currentAudio !== null && !this.currentAudio.paused;
  }

  public stop(): void {
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio.currentTime = 0;
      this.currentAudio = null;
    }
  }

  public async speak(text: string, options: TTSOptions = {}): Promise<void> {
    if (!this.apiKey) {
      console.warn('ElevenLabs API key is not configured. Falling back to browser speech.');
      return;
    }

    this.stop();

    try {
      const response = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${this.voiceId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'xi-api-key': this.apiKey,
        },
        body: JSON.stringify({
          text,
          model_id: 'eleven_multilingual_v2',
          voice_settings: {
            stability: 0.5,
            similarity_boost: 0.75,
          },
        }),
      });

      if (!response.ok) {
        throw new Error(`ElevenLabs API error: ${response.statusText}`);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      this.currentAudio = audio;
      if (options.rate) audio.playbackRate = options.rate;
      if (options.volume !== undefined) audio.volume = options.volume;

      return new Promise<void>((resolve, reject) => {
        audio.onended = () => {
          this.currentAudio = null;
          URL.revokeObjectURL(url);
          resolve();
        };
        audio.onerror = () => {
          this.currentAudio = null;
          URL.revokeObjectURL(url);
          reject(new Error('Audio playback failed'));
        };
        audio.play().catch(reject);
      });
    } catch (err) {
      this.stop();
      throw err;
    }
  }
}

// Default singleton instance using browser speech
export const defaultTTSProvider: TTSProvider = new BrowserSpeechTTSProvider();

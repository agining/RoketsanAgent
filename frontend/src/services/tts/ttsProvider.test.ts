import { afterEach, describe, expect, it, vi } from 'vitest';
import { BrowserSpeechTTSProvider, defaultTTSProvider, ElevenLabsTTSProvider } from './ttsProvider';

describe('ttsProvider', () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
  it('uses the backend gateway without sending provider credentials and reuses audio', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(new Blob(['audio']), { status: 200 }));
    vi.stubGlobal('fetch', fetch);
    vi.stubGlobal('Audio', class {
      paused = false; onended: (() => void) | null = null; onerror: (() => void) | null = null;
      src = ''; currentTime = 0;
      play() { queueMicrotask(() => this.onended?.()); return Promise.resolve(); }
      pause() { this.paused = true; }
    });
    const provider = new ElevenLabsTTSProvider();
    await provider.speak('Merhaba');
    await provider.speak('Merhaba');
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toContain('/api/voice/synthesize');
    expect(fetch.mock.calls[0][1].headers).not.toHaveProperty('xi-api-key');
  });
  it('falls back when audio playback fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(new Blob(['audio']))));
    const fallback = vi.spyOn(BrowserSpeechTTSProvider.prototype, 'speak').mockResolvedValue();
    vi.stubGlobal('Audio', class {
      paused = false; onended = null; onerror = null;
      play() { return Promise.reject(new Error('playback denied')); }
      pause() {}
    });
    await new ElevenLabsTTSProvider().speak('Merhaba');
    expect(fallback).toHaveBeenCalledWith('Merhaba', {});
  });
  it('uses ElevenLabsTTSProvider as default provider', () => {
    expect(defaultTTSProvider.name).toBe('elevenlabs');
    expect(defaultTTSProvider).toBeInstanceOf(ElevenLabsTTSProvider);
  });

  it('initializes ElevenLabsTTSProvider with API key and allows stopping safely', () => {
    const provider = new ElevenLabsTTSProvider();
    expect(provider.name).toBe('elevenlabs');
    expect(provider.isSpeaking()).toBe(false);

    // stop() can be called safely even when not speaking
    expect(() => provider.stop()).not.toThrow();
  });
});

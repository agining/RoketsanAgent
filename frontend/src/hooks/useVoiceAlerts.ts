import { useEffect, useRef } from 'react';
import { usePlaybackStore, type PlaybackSpeed } from '../store/playback';
import { useVoiceAlertsStore, type ActiveVoiceAlert } from '../store/voiceAlerts';
import { useTrackingStore } from '../store/tracking';
import { defaultTTSProvider, playTacticalAlertChime, type TTSProvider } from '../services/tts/ttsProvider';
import { formatAlertForSpeech } from '../services/tts/speechFormatter';
import { clockSeconds, RISK_WEIGHT } from '../services/analysis-playback';
import type { AnalysisAlert, AnalysisData } from '../types/analysis';

/**
 * Snappy tactical speech rates for real-time synchronization with playback.
 */
function getSpeechRate(speed: PlaybackSpeed): number {
  switch (speed) {
    case 0.5:
      return 1.2;
    case 1:
      return 1.45; // Snappy tactical military tempo (~0.6 - 0.9s per alert)
    case 2:
      return 1.85;
    case 4:
      return 2.2;
    default:
      return 1.45;
  }
}

export function useVoiceAlerts(
  analysis: AnalysisData | null,
  provider: TTSProvider = defaultTTSProvider
) {
  const isPlaying = usePlaybackStore((state) => state.isPlaying);
  const currentTime = usePlaybackStore((state) => state.currentTime);
  const playbackSpeed = usePlaybackStore((state) => state.playbackSpeed);

  const enabled = useVoiceAlertsStore((state) => state.enabled);
  const minRisk = useVoiceAlertsStore((state) => state.minRisk);
  const volume = useVoiceAlertsStore((state) => state.volume);
  const stopRequested = useVoiceAlertsStore((state) => state.stopRequested);
  const autoLock = useVoiceAlertsStore((state) => state.autoLock);
  const setActiveAlert = useVoiceAlertsStore((state) => state.setActiveAlert);
  const setSpeaking = useVoiceAlertsStore((state) => state.setSpeaking);
  const setQueueCount = useVoiceAlertsStore((state) => state.setQueueCount);

  // References to avoid stale closures in fast animation frames
  const spokenEventIdsRef = useRef<Set<string>>(new Set());
  const lastProcessedTimeRef = useRef<number | null>(null);
  const speedRef = useRef<PlaybackSpeed>(playbackSpeed);
  const volumeRef = useRef<number>(volume);
  const enabledRef = useRef<boolean>(enabled);
  const autoLockRef = useRef<boolean>(autoLock);
  const lingerTimeoutRef = useRef<number | null>(null);

  useEffect(() => { speedRef.current = playbackSpeed; }, [playbackSpeed]);
  useEffect(() => { volumeRef.current = volume; }, [volume]);
  useEffect(() => { enabledRef.current = enabled; }, [enabled]);
  useEffect(() => { autoLockRef.current = autoLock; }, [autoLock]);

  // Clean stop helper
  const flushAndStop = () => {
    if (lingerTimeoutRef.current !== null) {
      window.clearTimeout(lingerTimeoutRef.current);
      lingerTimeoutRef.current = null;
    }
    provider.stop();
    setQueueCount(0);
    setActiveAlert(null);
    setSpeaking(false);
  };

  // 1. Handle explicit stopRequested from store (e.g. user clicked Sesi Kes / Durdur)
  useEffect(() => {
    if (stopRequested > 0) {
      flushAndStop();
    }
  }, [stopRequested]);

  // 2. Handle PLAY/STOP transitions & pre-warm engine
  useEffect(() => {
    if (!isPlaying) {
      flushAndStop();
    } else {
      if ('prewarm' in provider && typeof (provider as { prewarm?: () => void }).prewarm === 'function') {
        (provider as { prewarm: () => void }).prewarm();
      }
      lastProcessedTimeRef.current = currentTime;
    }
  }, [isPlaying]);

  // 3. Handle voice alert toggle OFF
  useEffect(() => {
    if (!enabled) {
      flushAndStop();
    }
  }, [enabled]);

  // 4. Time progression tracking: listen to currentTime updates
  useEffect(() => {
    if (!isPlaying || !enabled || !analysis?.alerts?.length) {
      return;
    }

    const prevTime = lastProcessedTimeRef.current;
    if (prevTime === null) {
      lastProcessedTimeRef.current = currentTime;
      return;
    }

    // Detect manual user seek / timeline jumps
    const timeDelta = currentTime - prevTime;
    if (timeDelta < 0 || timeDelta > 300) {
      flushAndStop();
      if (timeDelta < 0) {
        // Rewound: remove future alerts from spoken set so they re-trigger
        const currentSpoken = spokenEventIdsRef.current;
        analysis.alerts.forEach((alert) => {
          const t = clockSeconds(alert.time);
          if (t >= currentTime) {
            const id = `${alert.time}_${alert.track_id ?? alert.vehicle_id ?? alert.zone}`;
            currentSpoken.delete(id);
          }
        });
      }
      lastProcessedTimeRef.current = currentTime;
      return;
    }

    lastProcessedTimeRef.current = currentTime;

    // Find any alerts in the window: (prevTime, currentTime]
    const minWeight = RISK_WEIGHT[minRisk] ?? 2;
    const newAlerts: AnalysisAlert[] = [];

    for (const alert of analysis.alerts) {
      const alertTime = clockSeconds(alert.time);
      if (alertTime > prevTime && alertTime <= currentTime) {
        const weight = RISK_WEIGHT[alert.risk_level] ?? 0;
        if (weight >= minWeight) {
          const id = `${alert.time}_${alert.track_id ?? alert.vehicle_id ?? alert.zone}`;
          if (!spokenEventIdsRef.current.has(id)) {
            spokenEventIdsRef.current.add(id);
            newAlerts.push(alert);
          }
        }
      }
    }

    if (newAlerts.length === 0) return;

    // Pick highest-risk alert as primary
    newAlerts.sort((a, b) => (RISK_WEIGHT[b.risk_level] ?? 0) - (RISK_WEIGHT[a.risk_level] ?? 0));
    const primaryAlert = newAlerts[0];
    const extraCount = newAlerts.length - 1;

    // 1. Play zero-latency tactical earcon chime immediately (<1ms)
    playTacticalAlertChime(primaryAlert.risk_level, volumeRef.current);

    // 2. Build active alert payload
    const id = `${primaryAlert.time}_${primaryAlert.track_id ?? primaryAlert.vehicle_id ?? primaryAlert.zone}`;
    const text = formatAlertForSpeech(primaryAlert, extraCount);

    const activeAlertObj: ActiveVoiceAlert = {
      id,
      text,
      risk: primaryAlert.risk_level,
      trackId: primaryAlert.track_id,
      vehicleId: primaryAlert.vehicle_id,
      frameId: primaryAlert.frame_id,
      zone: primaryAlert.zone,
      vehicleType: primaryAlert.label,
      scenario: primaryAlert.scenario,
      reason: primaryAlert.reason,
      distanceToBaseM: primaryAlert.distance_to_base_m,
      etaMin: primaryAlert.eta_min,
      lat: primaryAlert.lat,
      lon: primaryAlert.lon,
      time: primaryAlert.time,
    };

    // 3. Auto-lock camera onto vehicle immediately if setting is active
    if (autoLockRef.current) {
      const coord: [number, number] | undefined =
        primaryAlert.lon !== null && primaryAlert.lat !== null ? [primaryAlert.lon, primaryAlert.lat] : undefined;
      if (primaryAlert.track_id) {
        useTrackingStore.getState().lockOntoTrack(primaryAlert.track_id, coord);
      } else if (coord) {
        useTrackingStore.getState().requestView('coordinate', undefined, coord);
      }
    }

    // 4. Update UI card immediately
    if (lingerTimeoutRef.current !== null) {
      window.clearTimeout(lingerTimeoutRef.current);
      lingerTimeoutRef.current = null;
    }
    setActiveAlert(activeAlertObj);
    setSpeaking(true);
    setQueueCount(0);

    // 5. Preemptively speak current alert immediately (ZERO QUEUE DELAY!)
    // In fast simulation, previous alerts are cut immediately so operator is ALWAYS in sync with timeline
    provider.stop();
    const rate = getSpeechRate(speedRef.current);
    provider.speak(text, {
      rate,
      volume: volumeRef.current,
      lang: 'tr-TR',
    }).catch((err: unknown) => {
      const isStopped = err instanceof Error && (err.message === 'TTS_STOPPED' || err.message.includes('canceled'));
      if (!isStopped) {
        console.debug('Voice alert speech notice:', err);
      }
    }).finally(() => {
      setSpeaking(false);
      // Keep active card visible for 3.5 seconds after speaking so user can read/click lock
      if (lingerTimeoutRef.current !== null) {
        window.clearTimeout(lingerTimeoutRef.current);
      }
      lingerTimeoutRef.current = window.setTimeout(() => {
        setActiveAlert(null);
        lingerTimeoutRef.current = null;
      }, 3500);
    });
  }, [currentTime, isPlaying, enabled, minRisk, analysis]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      flushAndStop();
    };
  }, []);
}

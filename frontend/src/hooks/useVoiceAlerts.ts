import { useEffect, useRef } from 'react';
import { usePlaybackStore, type PlaybackSpeed } from '../store/playback';
import { useVoiceAlertsStore, type ActiveVoiceAlert } from '../store/voiceAlerts';
import { useTrackingStore } from '../store/tracking';
import { defaultTTSProvider, playTacticalAlertChime, type TTSProvider } from '../services/tts/ttsProvider';
import { formatAlertForSpeech } from '../services/tts/speechFormatter';
import { clockSeconds, RISK_WEIGHT } from '../services/analysis-playback';
import type { AnalysisAlert, AnalysisData } from '../types/analysis';

const CHIME_TO_SPEECH_DELAY_MS = 420;
const BETWEEN_ALERTS_DELAY_MS = 650;
const CARD_LINGER_MS = 4500;
const MAX_QUEUED_ALERTS = 3;

/**
 * Keep Turkish browser TTS intelligible even when playback is accelerated.
 * Some voices sound much faster than their nominal rate, so stay conservative.
 */
function getSpeechRate(speed: PlaybackSpeed): number {
  switch (speed) {
    case 0.5:
      return 0.82;
    case 1:
      return 0.88;
    case 2:
      return 0.95;
    case 4:
      return 1.02;
    default:
      return 0.88;
  }
}

function wait(ms: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

interface QueuedVoiceAlert {
  alert: ActiveVoiceAlert;
  text: string;
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
  const isPlayingRef = useRef<boolean>(isPlaying);
  const autoLockRef = useRef<boolean>(autoLock);
  const lingerTimeoutRef = useRef<number | null>(null);
  const queueRef = useRef<QueuedVoiceAlert[]>([]);
  const processingQueueRef = useRef(false);
  const queueRunRef = useRef(0);

  useEffect(() => { speedRef.current = playbackSpeed; }, [playbackSpeed]);
  useEffect(() => { volumeRef.current = volume; }, [volume]);
  useEffect(() => { enabledRef.current = enabled; }, [enabled]);
  useEffect(() => { isPlayingRef.current = isPlaying; }, [isPlaying]);
  useEffect(() => { autoLockRef.current = autoLock; }, [autoLock]);

  // Clean stop helper
  const flushAndStop = () => {
    queueRunRef.current += 1;
    queueRef.current = [];
    if (lingerTimeoutRef.current !== null) {
      window.clearTimeout(lingerTimeoutRef.current);
      lingerTimeoutRef.current = null;
    }
    provider.stop();
    setQueueCount(0);
    setActiveAlert(null);
    setSpeaking(false);
  };

  const processQueue = async () => {
    if (processingQueueRef.current) return;

    processingQueueRef.current = true;
    const runId = queueRunRef.current;

    try {
      while (
        queueRef.current.length > 0 &&
        enabledRef.current &&
        isPlayingRef.current &&
        runId === queueRunRef.current
      ) {
        const next = queueRef.current.shift();
        if (!next) break;

        setQueueCount(queueRef.current.length);

        if (lingerTimeoutRef.current !== null) {
          window.clearTimeout(lingerTimeoutRef.current);
          lingerTimeoutRef.current = null;
        }

        setActiveAlert(next.alert);
        setSpeaking(true);

        playTacticalAlertChime(next.alert.risk, volumeRef.current);
        await wait(CHIME_TO_SPEECH_DELAY_MS);

        if (
          !enabledRef.current ||
          !isPlayingRef.current ||
          runId !== queueRunRef.current
        ) {
          break;
        }

        await provider.speak(next.text, {
          rate: getSpeechRate(speedRef.current),
          volume: volumeRef.current,
          lang: 'tr-TR',
        }).catch((err: unknown) => {
          const isStopped = err instanceof Error && (err.message === 'TTS_STOPPED' || err.message.includes('canceled'));
          if (!isStopped) {
            console.debug('Voice alert speech notice:', err);
          }
        });

        if (runId !== queueRunRef.current) {
          break;
        }

        setSpeaking(false);
        lingerTimeoutRef.current = window.setTimeout(() => {
          if (runId === queueRunRef.current) {
            setActiveAlert(null);
          }
          lingerTimeoutRef.current = null;
        }, CARD_LINGER_MS);

        if (queueRef.current.length > 0) {
          await wait(BETWEEN_ALERTS_DELAY_MS);
        }
      }
    } finally {
      processingQueueRef.current = false;
      setQueueCount(queueRef.current.length);
    }
  };

  const enqueueAlert = (item: QueuedVoiceAlert) => {
    if (queueRef.current.length >= MAX_QUEUED_ALERTS) {
      const weakestIndex = queueRef.current.reduce((weakest, current, index, items) => {
        const currentWeight = RISK_WEIGHT[current.alert.risk] ?? 0;
        const weakestWeight = RISK_WEIGHT[items[weakest].alert.risk] ?? 0;
        return currentWeight < weakestWeight ? index : weakest;
      }, 0);

      const incomingWeight = RISK_WEIGHT[item.alert.risk] ?? 0;
      const weakestWeight = RISK_WEIGHT[queueRef.current[weakestIndex].alert.risk] ?? 0;

      if (incomingWeight > weakestWeight) {
        queueRef.current.splice(weakestIndex, 1, item);
      }
    } else {
      queueRef.current.push(item);
    }

    setQueueCount(queueRef.current.length);
    void processQueue();
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

    // Build active alert payload
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

    enqueueAlert({ alert: activeAlertObj, text });
  }, [currentTime, isPlaying, enabled, minRisk, analysis]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      flushAndStop();
    };
  }, []);
}

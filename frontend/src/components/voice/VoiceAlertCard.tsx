import { useState, useEffect } from 'react';
import { Crosshair, Radio, ShieldAlert, VolumeX, Check } from 'lucide-react';
import { useVoiceAlertsStore } from '../../store/voiceAlerts';
import { useTrackingStore } from '../../store/tracking';
import { formatRiskLevel } from '../../services/formatters';

export function VoiceAlertCard({ onSelectTrack }: { onSelectTrack: (trackId: string) => void }) {
  const { activeAlert, isSpeaking, queueCount, requestStop, autoLock, toggleAutoLock } = useVoiceAlertsStore();
  const [locked, setLocked] = useState(false);

  useEffect(() => {
    setLocked(false);
  }, [activeAlert?.id]);

  if (!activeAlert) return null;

  const handleLockOnVehicle = () => {
    const coord: [number, number] | undefined =
      activeAlert.lon !== null && activeAlert.lat !== null ? [activeAlert.lon, activeAlert.lat] : undefined;
    if (activeAlert.trackId) {
      useTrackingStore.getState().lockOntoTrack(activeAlert.trackId, coord);
      setLocked(true);
    } else if (coord) {
      useTrackingStore.getState().requestView('coordinate', undefined, coord);
      setLocked(true);
    }
  };

  const riskClass = activeAlert.risk.toLowerCase();
  const targetLabel = activeAlert.trackId ?? activeAlert.vehicleId ?? 'Hedef Araç';

  return (
    <aside
      className={`voice-alert-panel risk-${riskClass}`}
      role="alert"
      aria-live="assertive"
      aria-label={`${targetLabel} sesli tehdit uyarısı`}
    >
      <header className="voice-alert-header">
        <div className="voice-alert-badge">
          <Radio size={13} className={isSpeaking ? 'speaking-pulse' : ''} />
          <span>{formatRiskLevel(activeAlert.risk)} TEHDİT</span>
          <time>{activeAlert.time}</time>
        </div>
        <button
          className="voice-alert-stop-btn"
          onClick={requestStop}
          title="Sesli anonsu sustur ve kapat"
          aria-label="Sesi kes"
        >
          <VolumeX size={13} />
          <span>Sesi Kes</span>
        </button>
      </header>

      <div className="voice-alert-body">
        <div className="voice-alert-target">
          <ShieldAlert size={15} />
          <strong>{targetLabel}</strong>
          {activeAlert.vehicleType && <span className="target-type">{activeAlert.vehicleType}</span>}
          {activeAlert.zone && <span className="target-zone">· {activeAlert.zone}</span>}
        </div>

        <p className="voice-alert-reason">
          {activeAlert.reason || activeAlert.scenario || activeAlert.text}
        </p>

        {(activeAlert.distanceToBaseM !== null || activeAlert.etaMin !== null) && (
          <div className="voice-alert-telemetry">
            {activeAlert.distanceToBaseM !== null && (
              <span>Üsse: <b>{Math.round(activeAlert.distanceToBaseM)} m</b></span>
            )}
            {activeAlert.etaMin !== null && (
              <span>ETA: <b>{activeAlert.etaMin.toFixed(1)} dk</b></span>
            )}
          </div>
        )}
      </div>

      <footer className="voice-alert-footer">
        <button
          className={`voice-lock-btn ${locked ? 'locked' : ''}`}
          onClick={handleLockOnVehicle}
          title="Haritada bu araca kilitlen ve takip et"
          aria-label={`${targetLabel} aracına kilitlen`}
        >
          {locked ? <Check size={14} /> : <Crosshair size={14} />}
          <span>{locked ? 'Kilitlendi' : 'Araca Kilitlen'}</span>
        </button>

        <label className="voice-autolock-toggle" title="Yeni uyarı geldiğinde kamerayı otomatik hedefe kilitler">
          <input
            type="checkbox"
            checked={autoLock}
            onChange={toggleAutoLock}
          />
          <span>Oto-Kilit</span>
        </label>

        {queueCount > 0 && (
          <span className="voice-queue-pill">+{queueCount} anons sırada</span>
        )}
      </footer>
    </aside>
  );
}

import { useMemo } from 'react';
import { AlertTriangle, Crosshair, Focus, LocateFixed, Truck, X, PanelRightClose } from 'lucide-react';
import { useWorkspaceStore } from '../store/workspace';
import { Button } from './ui/button';
import { VehicleCharts } from './VehicleCharts';
import { useTrackingStore } from '../store/tracking';
import { usePlaybackStore } from '../store/playback';
import { formatTime } from '../services/playback';
import { formatDuration, selectedVehicleMetrics } from '../services/vehicle-metrics';
import type { BaseLocation, VehicleTrack } from '../types/tracking';
import type { AnalysisData } from '../types/analysis';
import { analysisForTrack, buildAnalysisIndex } from '../services/analysis';
import { reportsAtTime } from '../services/reports';
import { formatRiskLevel, formatUnavailable, humanizeAssessmentText } from '../services/formatters';
import { useReportStore } from '../store/reports';
import { ReportVerdictBadge } from './reports/ReportVerdictBadge';
import { ReasoningTrace } from './agent/ReasoningTrace';
export function VehicleDetails({ tracks, base, analysis }: { tracks: VehicleTrack[]; base?: BaseLocation; analysis?: AnalysisData }) {
  const selectedId = useTrackingStore(state => state.selectedTrackId);
  const select = useTrackingStore(state => state.selectTrack);
  const follow = useTrackingStore(state => state.followVehicle);
  const setFollow = useTrackingStore(state => state.setFollowVehicle);
  const requestView = useTrackingStore(state => state.requestView);
  // Inspector refreshes at 10 Hz; map motion retains the full animation frame rate.
  const currentTime = usePlaybackStore(state => Math.floor(state.currentTime * 10) / 10);
  const analysisIndex = useMemo(() => analysis ? buildAnalysisIndex(analysis) : null, [analysis]);
  const track = tracks.find(track => track.id === selectedId);
  const metrics = track && base ? selectedVehicleMetrics(track, currentTime, base) : null;
  const position = metrics?.position;
  const evidence = selectedId && analysisIndex ? analysisForTrack(analysisIndex, selectedId, currentTime) : null;
  const relatedReports = analysis && selectedId ? reportsAtTime(analysis, currentTime).filter(report => report.matched_track_id === selectedId || evidence?.report_ids?.includes(report.report_id)) : [];
  const contradictoryReports = relatedReports.filter(report => report.verdict === 'CONTRADICTED');
  const featureRows = evidence?.features ? [
    ['Yön', evidence.features.heading_deg == null ? '—' : `${Number(evidence.features.heading_deg).toFixed(1)}°`],
    ['Analiz edilen hız', evidence.features.speed_now_mps == null ? '—' : `${(Number(evidence.features.speed_now_mps) * 3.6).toFixed(1)} km/sa`],
    ['Son 60 dakikada yaklaşma', evidence.features.approach_last60_m == null ? '—' : `${Number(evidence.features.approach_last60_m).toFixed(0)} m`],
    ['Duraklama / 60 dk', evidence.features.stops_last60 == null ? '—' : String(evidence.features.stops_last60)],
    ['Tahmini varış', evidence.features.eta_min == null ? '—' : `${Number(evidence.features.eta_min).toFixed(1)} dk`],
    ['Mesafe eğilimi', evidence.features.dist_trend == null ? '—' : humanizeAssessmentText(String(evidence.features.dist_trend))],
  ] : [];
  return <aside className="vehicle-details" aria-label="Araç detayları">
    <div className="details-heading"><span className="section-eyebrow">ARAÇ İNCELEME</span><Button variant="ghost" size="icon" aria-label="İnceleme panelini daralt" title="İnceleme panelini daralt" onClick={() => useWorkspaceStore.getState().toggleInspector()}><PanelRightClose size={15} /></Button>{track && <Button variant="ghost" size="icon" aria-label="Araç seçimini temizle" onClick={() => select(null)}><X size={16} /></Button>}</div>
    {track && metrics && base ? <><div className="detail-title"><span className="track-icon"><Truck size={18} /></span><div><span className="section-eyebrow">SEÇİLİ ARAÇ</span><strong>{track.id}</strong></div><span className="record-count">{track.points.length} nokta</span></div>
      <div className="vehicle-status" aria-label="Araç durumu"><span className={`status-badge ${metrics.motion === 'MOVING' ? 'moving' : ''}`}>{humanizeAssessmentText(metrics.motion)}</span>{metrics.baseTrend && <span className="status-badge">{humanizeAssessmentText(metrics.baseTrend)}</span>}</div>
      <div className="vehicle-actions"><Button variant={follow ? 'default' : 'outline'} aria-pressed={follow} onClick={() => setFollow(!follow)}><Crosshair size={13} />Takip et</Button><Button variant="outline" onClick={() => requestView('route')}><Focus size={13} />Rotaya odaklan</Button><Button variant="ghost" onClick={() => requestView('reset')}><LocateFixed size={13} />Görünümü sıfırla</Button></div>
      {follow && <p className="follow-note">{track.id} takip ediliyor · Durdurmak için haritayı sürükle veya Takip et seçimini kapat.</p>}
      <dl className="live-values">
        <div><dt>PLAYBACK ZAMANI</dt><dd>{formatTime(currentTime)}</dd></div><div><dt>GEÇEN TRACK SÜRESİ</dt><dd>{formatDuration(metrics.elapsedSeconds)}</dd></div>
        <div><dt>ENLEM</dt><dd>{position ? `${position.lat.toFixed(6)}°` : '—'}</dd></div><div><dt>BOYLAM</dt><dd>{position ? `${position.lon.toFixed(6)}°` : '—'}</dd></div>
        <div><dt>YAKLAŞIK HIZ</dt><dd>{position ? `${position.speedKmh.toFixed(1)} km/sa` : '—'}</dd></div><div><dt>YÖN</dt><dd>{position?.heading != null ? `${position.heading.toFixed(1)}° ${humanizeAssessmentText(metrics.direction ?? '')}` : '—'}</dd></div>
        <div><dt>ÜSSE MESAFE</dt><dd>{metrics.distanceToBase != null ? `${metrics.distanceToBase.toFixed(2)} km` : '—'}</dd></div><div><dt>KAT EDİLEN MESAFE</dt><dd>{metrics.totalDistance.toFixed(2)} km</dd></div>
      </dl>
      {!position && <p className="outside-track">Bu an, aracın kayıtlı gözlem aralığının dışında. Konum ve takip geçici olarak durduruldu; seçim korunuyor.</p>}
      {position && <div className="sample-bracket"><div><span className="section-eyebrow">ÖNCEKİ BİLİNEN NOKTA</span><strong>{formatTime(position.previous.timestamp)}</strong><small>{position.previous.lat.toFixed(6)}°, {position.previous.lon.toFixed(6)}°</small></div><div><span className="section-eyebrow">SONRAKİ BİLİNEN NOKTA</span><strong>{formatTime(position.next.timestamp)}</strong><small>{position.next.lat.toFixed(6)}°, {position.next.lon.toFixed(6)}°</small></div></div>}
      <section className="vehicle-evidence"><div className="chart-heading"><h3>Kanıt</h3><span>{evidence ? `${formatRiskLevel(evidence.risk_level)} · ${humanizeAssessmentText(evidence.scenario)}` : 'Henüz analiz edilmedi'}</span></div>
        {contradictoryReports.length > 0 && <div className="contradiction-warning compact"><AlertTriangle size={15} /><span><b>{contradictoryReports.length} çelişkili rapor</b><small>Rapor iddiaları tespit veya track davranışıyla çelişiyor.</small></span></div>}
        {evidence ? <><dl className="evidence-overview"><div><dt>TESPİT GÜVENİ</dt><dd>{evidence.confidence == null ? '—' : `%${Math.round(evidence.confidence * 100)}`}</dd></div><div><dt>TRACK EŞLEŞMESİ</dt><dd>{evidence.track_match_m == null ? '—' : `${evidence.track_match_m.toFixed(1)} m`}</dd></div></dl>
          <dl className="movement-evidence">{featureRows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
          <div className="risk-reasons"><span>RİSK GEREKÇELERİ</span>{(evidence.risk_reasons ?? []).map(reason => <p key={reason}>{humanizeAssessmentText(reason)}</p>)}{!evidence.risk_reasons?.length && <p>Risk gerekçesi sağlanmamış.</p>}</div>
          <div className="related-evidence"><span>İLİŞKİLİ RAPORLAR</span>{relatedReports.map(report => <button key={report.report_id} onClick={() => useReportStore.getState().selectReport(report.report_id)}><b>{report.report_id}</b><ReportVerdictBadge verdict={report.verdict} /><small>{report.time}</small></button>)}{!relatedReports.length && <p>Bu anda ilişkili rapor yok.</p>}</div></> : <p className="summary-empty">Analiz kanıtı, ilgili görüntü veya rapor zamanına ulaşıldığında görünür.</p>}
      </section>
      <ReasoningTrace vehicle={evidence} reports={relatedReports} />
      <VehicleCharts track={track} base={base} time={Math.floor(currentTime)} />
      <section className="movement-history"><div className="chart-heading"><h3>Hareket geçmişi</h3><span>Son 5 GPS örneği</span></div><div className="history-scroll"><table><thead><tr><th>Zaman</th><th>Enlem / Boylam</th><th>km/sa</th><th>Üs mesafesi</th></tr></thead><tbody>{metrics.history.map((point, index) => <tr key={`${point.timestamp}-${index}`}><td>{formatTime(point.timestamp)}</td><td>{point.lat.toFixed(6)}<br />{point.lon.toFixed(6)}</td><td>{point.speedKmh.toFixed(1)}</td><td>{point.distanceKm.toFixed(2)} km</td></tr>)}</tbody></table>{!metrics.history.length && <p className="details-note">Bu ana kadar kayıtlı nokta yok.</p>}</div></section>
      <p className="details-note">Üs: {base.name}. Tahminler GPS segmentlerinden hesaplanır. Hareketsiz kabulü: 0,5 km/sa altı. Üs eğilimi yerel mesafe değişimini izler; geçmiş hız değeri sonraki segmente aittir.</p>
    </> : <div className="inspector-empty"><Crosshair size={29} /><h2>Bir araç seçin</h2><p>Hareketini incelemek için haritadaki markerı, rotayı veya listedeki kaydı seçin.</p><ul><li>Anlık konum, yön ve hız</li><li>Üsse göre mesafe ve hareket</li><li>Rota grafikleri ve son GPS örnekleri</li></ul><p>Herhangi bir anı incelemek için timeline’ı kullanın. Takip modu seçili aracı merkezde tutar.</p></div>}
  </aside>;
}

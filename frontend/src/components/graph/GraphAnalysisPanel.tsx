import { useEffect, useRef, useState, type FormEvent } from 'react';
import { RefreshCw } from 'lucide-react';
import type { AnalysisReport } from '../../types/analysis';
import type { GraphAnalysis, GraphRegion, GraphWindow } from '../../types/graph';
import './graph.css';
import { api } from '../../services/api';
import type { VehicleSummary } from '../../types/graph';

const componentLabels: Record<string, string> = {
  lift: 'Düzeltilmiş lift', ratio: 'Düzeltilmiş oran', centrality_gap: 'Merkezilik farkı',
  trajectory_importance: 'Gözlenen rota kullanımı', graph_centrality: 'Rota merkeziliği', intelligence: 'Rapor desteği',
  group_concentration: 'Araç grubu yoğunluğu',
};
const percent = (value: number) => `%${(value * 100).toFixed(1)}`;
const levelLabels = { DUSUK: 'Düşük', ORTA: 'Orta', YUKSEK: 'Yüksek', KRITIK: 'Çok yüksek' };
const regionName = (region: GraphRegion) => `Bölge ${region.region_id.replace(/^REG_N_0*/, '')}`;

export function GraphAnalysisPanel({ enabled, onToggle, data, loading, error, reload, onWindow,
  selected, onSelect, reports, requestWindow }: {
    enabled: boolean; onToggle: () => void; data: GraphAnalysis | null; loading: boolean; error: string | null;
    reload: () => void; onWindow: (window: GraphWindow) => void; selected: GraphRegion | null;
    onSelect: (regionId: string) => void; reports: AnalysisReport[]; requestWindow: GraphWindow;
  }) {
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const detail = useRef<HTMLElement>(null);
  const [vehicleSummary, setVehicleSummary] = useState<VehicleSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const summaryRequest = useRef<AbortController | null>(null);
  useEffect(() => {
    summaryRequest.current?.abort();
    setVehicleSummary(null); setSummaryLoading(false); setSummaryError(null);
    return () => summaryRequest.current?.abort();
  }, [selected?.region_id, data?.data_revision]);
  const summarizeVehicles = async () => {
    if (!selected || !data) return;
    summaryRequest.current?.abort();
    const controller = new AbortController(); summaryRequest.current = controller;
    setSummaryLoading(true); setSummaryError(null);
    const timer = window.setTimeout(() => {
      if (summaryRequest.current !== controller) return;
      controller.abort();
      setSummaryError('Özet beklenenden uzun sürdü. Lütfen yeniden dene.');
      setSummaryLoading(false);
    }, 45000);
    try {
      const result = await api.graphVehicleSummary(selected.region_id, requestWindow, controller.signal);
      if (!controller.signal.aborted) setVehicleSummary(result);
    } catch (error) {
      if (!controller.signal.aborted) setSummaryError(error instanceof Error ? error.message : 'Özet alınamadı.');
    } finally { window.clearTimeout(timer); if (summaryRequest.current === controller) setSummaryLoading(false); }
  };
  useEffect(() => { detail.current?.scrollIntoView({ block: 'start' }); }, [selected?.region_id]);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (start && end && start > end) { setFormError('Başlangıç bitişten sonra olamaz.'); return; }
    setFormError(null);
    onWindow({ start_time: start || undefined, end_time: end || undefined });
  };
  const regions = data?.regions.filter(region => region.interest_score >= data.region_interest_threshold) ?? [];
  return <section className="game-graph-panel" aria-label="Bölgesel Anomali Analizini Başlat">
    <button className="graph-toggle" aria-pressed={enabled} onClick={onToggle}>
      {enabled ? 'Anomali tespitini kapat' : 'Bölgesel Anomali Analizini Başlat'}
    </button>
    {enabled && <>
      <p className="graph-description">Araçların ortak geçtiği bölgeleri ve dikkat çeken hareketleri incele.</p>
      <form onSubmit={submit} className="graph-window-form">
        <label>Başlangıç<input type="time" aria-label="Analiz başlangıç zamanı" value={start} onChange={event => setStart(event.target.value)} /></label>
        <label>Bitiş<input type="time" aria-label="Analiz bitiş zamanı" value={end} onChange={event => setEnd(event.target.value)} /></label>
        <button type="submit" disabled={loading}>Aralığı analiz et</button>
        <button type="button" onClick={reload} disabled={loading} aria-label="Anomali analizini yeniden hesapla"><RefreshCw size={12} /></button>
      </form>
      {(formError || error) && <p role="alert" className="graph-error">{formError || error}</p>}
      {error && <button onClick={reload} className="graph-toggle">Anomali analizini tekrar dene</button>}
      {loading && <p role="status">Anomaliler hesaplanıyor…</p>}
      {data && <>
        <dl className="graph-metrics graph-summary">
          <dt>Analiz aralığı</dt><dd>{data.analysis_start ?? '—'} – {data.analysis_end ?? '—'}</dd>
          <dt>İncelenen araç</dt><dd>{data.total_trajectories}</dd>
        </dl>
        {data.unclassified_trajectory_count > 0 && <p>{data.unclassified_trajectory_count} sınıflandırılmamış rota oran hesabına katılmadı.</p>}
        <div className="graph-region-list" aria-label="Anomali bölgeleri">
          {regions.slice(0, 50).map(region => <button key={region.region_id} aria-pressed={selected?.region_id === region.region_id}
            onClick={() => onSelect(region.region_id)} className={`graph-region-row graph-${region.severity.toLowerCase()}`}>
            <span>{regionName(region)}<small>{region.total_vehicle_count} araç · {region.threat_vehicle_count} tehdit etiketli</small></span>
            <strong>{levelLabels[region.severity]}</strong>
          </button>)}
          {!regions.length && <p>Bu aralıkta gösterilecek bölge yok.</p>}
          {regions.length > 50 && <p>En yüksek skorlu 50 bölge listeleniyor; tüm bölgeler haritada gösteriliyor.</p>}
        </div>
      </>}
      {selected && data && <article ref={detail} className="graph-region-detail" aria-label="Seçili anomali bölgesi">
        <h3>{regionName(selected)}</h3>
        <p className="graph-level">Anomali seviyesi: <strong>{levelLabels[selected.severity]}</strong></p>
        <p>{selected.total_vehicle_count} araç bu bölgeden geçti: {selected.threat_vehicle_count} tehdit etiketli, {selected.normal_vehicle_count} normal.</p>
        {selected.score_breakdown.group_rule?.matched && <p>Birden fazla tehdit etiketli araç aynı bölgede yoğunlaşıyor. Birlikte hareket edip etmediklerini anlamak için araç açıklamalarını ve geçiş zamanlarını incele.</p>}
        <p>{selected.local_threat_rate > selected.global_threat_rate
          ? 'Tehdit etiketli araçların oranı burada genel ortalamanın üzerinde.'
          : 'Tehdit etiketli araçların oranı genel ortalamanın üzerinde değil.'}
          {' '}{selected.confidence < 0.5 ? 'Az sayıda araç gözlendi; yeni hareketler değerlendirmeyi değiştirebilir.' : ''}</p>
        <p>{selected.severity === 'DUSUK' ? 'Hareketleri ve araç değerlendirmelerini birlikte inceleyebilirsin.' : 'Bu bölgenin araç değerlendirmelerini incelemen önerilir.'}</p>
        <details className="graph-technical"><summary>Teknik ayrıntılar</summary>
          <dl className="graph-metrics">
            <dt>Skor (olasılık değildir)</dt><dd>{(selected.interest_score * 100).toFixed(1)} / 100</dd>
            <dt>Konum</dt><dd>{selected.location.lat.toFixed(5)}, {selected.location.lon.toFixed(5)}</dd>
            <dt>Normal / threat araç</dt><dd>{selected.normal_vehicle_count} / {selected.threat_vehicle_count}</dd>
            <dt>Yerel / genel oran</dt><dd>{percent(selected.local_threat_rate)} / {percent(selected.global_threat_rate)}</dd>
            <dt>Threat lift</dt><dd>{selected.threat_lift.toFixed(2)}x</dd>
            <dt>Merkezilik farkı</dt><dd>{selected.threat_normal_centrality_gap.toFixed(4)}</dd>
            <dt>Gözlem hacmi güveni</dt><dd>{percent(selected.confidence)}</dd>
            <dt>Sanal gözlem sayısı</dt><dd>{selected.score_breakdown.effective_pseudo_count?.toFixed(2) ?? '—'}</dd>
            <dt>Hareket / rapor katkısı</dt><dd>{selected.graph_interest_score.toFixed(3)} / {selected.intelligence_contribution.toFixed(3)}</dd>
          </dl>
          <h4>Skor dökümü</h4>
          <p>Hareket skoru {selected.representative_node_id} düğümünden gelir. Grup yoğunluğu bölgedeki farklı araçlar üzerinden hesaplanır.</p>
          <table aria-label="Anomali skor bileşenleri"><thead><tr><th>Bileşen</th><th>Normalize</th><th>Katkı</th></tr></thead>
            <tbody>{Object.entries(selected.score_breakdown.components).map(([name, item]) => <tr key={name}>
              <th scope="row">{componentLabels[name] ?? name}</th><td>{item.normalized.toFixed(3)}</td><td>{item.contribution.toFixed(3)}</td>
            </tr>)}</tbody>
          </table>
          <ul>{selected.explanation.map((reason, index) => <li key={index}>{reason}</li>)}</ul>
        </details>
        <h4>Araç değerlendirmeleri</h4>
        <p>{selected.vehicle_assessments?.length ? `${selected.vehicle_assessments.length} aracın değerlendirmesi hazır.` : 'Bu bölgedeki araçları açıp değerlendirdikten sonra analizi yenileyebilirsin.'}</p>
        {!!selected.vehicle_assessments?.length && <>
          <button className="graph-toggle" onClick={summarizeVehicles} disabled={summaryLoading}>{summaryLoading ? 'Özet hazırlanıyor…' : 'Özet çıkar'}</button>
          {summaryError && <p role="alert">{summaryError}</p>}
          {vehicleSummary && <div>
            <p>{vehicleSummary.method === 'llm' ? 'Kısa değerlendirme' : 'İnceleme notu'} · {vehicleSummary.track_count} tekil rota</p>
            {vehicleSummary.findings.map((finding, index) => <p key={index}>{finding.text}</p>)}
          </div>}
          <details><summary>Kaynak araç değerlendirmeleri</summary>{selected.vehicle_assessments.map(record => <p key={record.vehicle_id}>
            <strong>{record.vehicle_id} · {record.track_id} · {record.level}</strong> · {record.reason}
            {record.evidence_report_ids.length > 0 && <small> · Raporlar: {record.evidence_report_ids.join(', ')}</small>}
          </p>)}</details>
        </>}
        {selected.related_intelligence_ids.length > 0 && <details><summary>İlgili raporlar ({selected.related_intelligence_count})</summary>
          {selected.related_intelligence_ids.map(id => <p key={id}><strong>{id}</strong> · {reports.find(report => report.report_id === id)?.text ?? 'Kaynak metin bu görünümde bulunamadı.'}</p>)}
        </details>}
      </article>}
    </>}
  </section>;
}

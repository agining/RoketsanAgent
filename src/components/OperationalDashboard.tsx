import {
  AlertTriangle, ArrowDownToLine, ArrowUpFromLine, CarFront, ChevronRight,
  CircleDotDashed, Clock3, DatabaseZap, Eye, FileWarning, Radar, RefreshCw, RotateCw, ShieldAlert,
} from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { AnalysisData, AttentionLevel, PriorityEntity, RiskLevel } from '../types/analysis';
import { formatAttention, formatRiskLevel, formatVehicleClass, humanizeAssessmentText } from '../services/formatters';
import { TrackExplorer } from './tracks/TrackExplorer';
import { UntrackedDetections } from './tracks/UntrackedDetections';

const riskOrder: RiskLevel[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
const attentionOrder: AttentionLevel[] = ['ROUTINE', 'MONITOR', 'PRIORITY', 'IMMEDIATE'];
const riskColors: Record<RiskLevel, string> = { LOW: '#64b88c', MEDIUM: '#d7b84a', HIGH: '#e47a3f', CRITICAL: '#e4545c', UNKNOWN: '#667985' };
const attentionColors: Record<AttentionLevel, string> = { ROUTINE: '#71828c', MONITOR: '#62a6a0', PRIORITY: '#d8a34a', IMMEDIATE: '#dc5961', UNKNOWN: '#667985' };
const riskRank: Record<RiskLevel, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, UNKNOWN: 0 };

function formatAnalysisTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

function formatDistance(meters: number) {
  return meters < 1000 ? `${Math.round(meters)} m` : `${(meters / 1000).toFixed(2)} km`;
}

function DistributionTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: { name: string; value: number } }> }) {
  if (!active || !payload?.length) return null;
  const item = payload[0].payload;
  return <div className="distribution-tooltip"><span>{item.name}</span><strong>{item.value}</strong></div>;
}

function PriorityCard({ entity, onSelect }: { entity: PriorityEntity; onSelect: (trackId: string) => void }) {
  return <button className={`priority-track-card risk-${entity.risk_level.toLowerCase()}`} onClick={() => onSelect(entity.track_id)} aria-label={`${entity.track_id} öncelikli araç detayını aç`}>
    <span className="priority-track-accent" />
    <span className="priority-track-content">
      <span className="priority-track-heading"><span><strong>{entity.track_id}</strong><small>{formatVehicleClass(entity.vehicle_class)}</small></span><ChevronRight size={17} /></span>
      <span className="priority-track-badges"><em className={`risk-badge risk-${entity.risk_level.toLowerCase()}`}>{formatRiskLevel(entity.risk_level)}</em><em className={`attention-badge attention-${entity.recommended_attention.toLowerCase()}`}>{formatAttention(entity.recommended_attention)}</em></span>
      <span className="priority-track-location"><span>{entity.zone}</span><b>Üsse {formatDistance(entity.distance_to_base_m)}</b></span>
      <span className="priority-track-summary">{humanizeAssessmentText(entity.summary)}</span>
    </span>
  </button>;
}

export function OperationalDashboard({ analysis, selectedTrackId, onSelectTrack, onRefresh, refreshing = false }: { analysis: AnalysisData; selectedTrackId: string | null; onSelectTrack: (trackId: string) => void; onRefresh: () => void; refreshing?: boolean }) {
  const summary = analysis.operation_summary;
  const riskData = riskOrder.map(level => ({ name: formatRiskLevel(level), value: summary.risk_counts[level], fill: riskColors[level] }));
  const attentionData = attentionOrder.map(level => ({ name: formatAttention(level), value: summary.attention_counts[level], fill: attentionColors[level] }));
  const highCritical = summary.risk_counts.HIGH + summary.risk_counts.CRITICAL;
  const complexBehavior = summary.current_state_counts.loitering + summary.current_state_counts.circling;
  const priorities = [...summary.priority_entities].sort((a, b) => riskRank[b.risk_level] - riskRank[a.risk_level] || a.distance_to_base_m - b.distance_to_base_m);
  const overview = [
    { label: 'Takip edilen araçlar', value: summary.tracked_entity_count, detail: 'Kalıcı track kayıtları', icon: CarFront, tone: 'neutral' },
    { label: 'Takipsiz tespitler', value: summary.untracked_observation_count, detail: 'Track ile eşleşmeyen gözlemler', icon: Radar, tone: 'watch' },
    { label: 'Yüksek / kritik risk', value: highCritical, detail: `${summary.risk_counts.HIGH} yüksek · ${summary.risk_counts.CRITICAL} kritik`, icon: ShieldAlert, tone: 'risk' },
    { label: 'Üsse yaklaşanlar', value: summary.current_state_counts.approaching_base, detail: 'Güncel hareket durumu', icon: ArrowDownToLine, tone: 'watch' },
    { label: 'Dolaşma / dairesel hareket', value: complexBehavior, detail: `${summary.current_state_counts.loitering} dolaşma · ${summary.current_state_counts.circling} dairesel`, icon: CircleDotDashed, tone: 'risk' },
    { label: 'Rapor güvenilirliği', value: summary.current_state_counts.report_contradiction, detail: 'Saha raporu ile sensör verisi çelişkileri', icon: FileWarning, tone: 'quality' },
  ] as const;
  const operationalStates = [
    { label: 'Üsse yaklaşıyor', value: summary.current_state_counts.approaching_base, icon: ArrowDownToLine },
    { label: 'Üsten uzaklaşıyor', value: summary.current_state_counts.leaving_base, icon: ArrowUpFromLine },
    { label: 'Bölgede dolaşma paterni', value: summary.current_state_counts.loitering, icon: Eye },
    { label: 'Dairesel hareket paterni', value: summary.current_state_counts.circling, icon: RotateCw },
  ];
  const qualityStates = [
    { label: 'Saha raporu ile sensör verisi çelişkili', value: summary.current_state_counts.report_contradiction, icon: FileWarning },
    { label: 'Araç sınıflandırması tutarsız', value: summary.current_state_counts.class_inconsistency, icon: DatabaseZap },
  ];

  return <section className="operational-dashboard" aria-label="Operasyonel araç risk paneli">
    <div className="dashboard-title-row">
      <div><span className="section-eyebrow">OPERASYON ÖZETİ</span><h1>Araç Risk Paneli</h1><p>Son tamamlanan analize göre güncel operasyonel tablo.</p></div>
      <div className="dashboard-title-actions"><div className="last-analysis"><Clock3 size={15} /><span><small>SON ANALİZ</small><strong>{formatAnalysisTime(analysis.generated_at)}</strong></span></div><button className="refresh-analysis" onClick={onRefresh} disabled={refreshing} aria-label="Analiz verisini yenile"><RefreshCw size={14} className={refreshing ? 'spinning' : ''} />{refreshing ? 'Yenileniyor…' : 'Analizi Yenile'}</button></div>
    </div>

    <div className="overview-grid">{overview.map(({ label, value, detail, icon: Icon, tone }) => <article className={`overview-card tone-${tone}`} key={label}>
      <span className="overview-card-icon"><Icon size={18} /></span><span className="overview-card-copy"><small>{label}</small><strong>{value}</strong><em>{detail}</em></span>
    </article>)}</div>

    <div className="dashboard-analysis-grid">
      <article className="dashboard-panel distribution-panel"><header><div><span className="panel-kicker">RİSK DAĞILIMI</span><h2>Değerlendirilen risk seviyeleri</h2></div><span className="panel-total">{summary.tracked_entity_count} track</span></header>
        <div className="risk-chart-wrap"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={riskData} dataKey="value" nameKey="name" innerRadius="62%" outerRadius="88%" paddingAngle={2} stroke="none">{riskData.map(item => <Cell key={item.name} fill={item.fill} />)}</Pie><Tooltip content={<DistributionTooltip />} /></PieChart></ResponsiveContainer><span className="chart-center"><strong>{highCritical}</strong><small>YÜKSEK / KRİTİK</small></span></div>
        <div className="distribution-legend">{riskData.map(item => <span key={item.name}><i style={{ background: item.fill }} /><small>{item.name}</small><strong>{item.value}</strong></span>)}</div>
      </article>

      <article className="dashboard-panel distribution-panel"><header><div><span className="panel-kicker">TAKİP SEVİYESİ DAĞILIMI</span><h2>Önerilen takip seviyesi</h2></div><span className="panel-total">Operasyonel yanıt</span></header>
        <div className="attention-chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={attentionData} margin={{ top: 8, right: 2, bottom: 0, left: -28 }}><CartesianGrid vertical={false} stroke="#2b3941" strokeDasharray="2 4" /><XAxis dataKey="name" tick={{ fill: '#8fa0a9', fontSize: 8 }} axisLine={false} tickLine={false} /><YAxis allowDecimals={false} tick={{ fill: '#6f828c', fontSize: 8 }} axisLine={false} tickLine={false} /><Tooltip cursor={{ fill: '#ffffff08' }} content={<DistributionTooltip />} /><Bar dataKey="value" radius={[3, 3, 0, 0]} maxBarSize={34}>{attentionData.map(item => <Cell key={item.name} fill={item.fill} />)}</Bar></BarChart></ResponsiveContainer></div>
      </article>

      <article className="dashboard-panel state-panel"><header><div><span className="panel-kicker">GÜNCEL DURUM</span><h2>Hareket ve davranış</h2></div><span className="panel-total">Backend sınıflandırması</span></header>
        <div className="state-counter-grid">{operationalStates.map(({ label, value, icon: Icon }) => <div key={label}><span><Icon size={14} />{label}</span><strong>{value}</strong></div>)}</div>
        <div className="quality-divider"><span>GÜVENİLİRLİK VE VERİ KALİTESİ</span><i /></div>
        <div className="quality-counter-grid">{qualityStates.map(({ label, value, icon: Icon }) => <div key={label}><Icon size={14} /><span><small>{label}</small><strong>{value}</strong></span></div>)}</div>
        <p className="quality-note"><AlertTriangle size={12} />Kalite göstergeleri değerlendirme güvenini etkiler; tehdit sınıflandırması değildir.</p>
      </article>
    </div>

    <article className="dashboard-panel priority-panel"><header><div><span className="panel-kicker">ÖNCELİKLİ TRACKLER</span><h2>Takip gerektiren kayıtlar</h2></div><span className="panel-total">{priorities.length} track</span></header>
      {priorities.length ? <div className="priority-track-grid">{priorities.map(entity => <PriorityCard key={entity.track_id} entity={entity} onSelect={onSelectTrack} />)}</div> : <div className="priority-empty"><ShieldAlert size={20} /><span><strong>Öncelikli araç kaydı yok</strong><small>Bu analizde yüksek veya kritik öncelikli kayıt bulunmuyor.</small></span></div>}
    </article>
    <TrackExplorer analysis={analysis} selectedTrackId={selectedTrackId} onSelectTrack={onSelectTrack} />
    <UntrackedDetections observations={analysis.untracked_observations} />
  </section>;
}

import {
  useEffect,
  useId,
  useMemo,
  useState,
} from 'react';

import {
  AlertTriangle,
  BrainCircuit,
  ChevronDown,
  Clock3,
  Crosshair,
  Eye,
  Focus,
  LoaderCircle,
  PanelRightClose,
  Route,
  Search,
  ShieldAlert,
  ShieldCheck,
  X,
} from 'lucide-react';

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type {
  AnalysisData,
  AnalysisEntity,
  AnalysisVehicle,
} from '../../types/analysis';
import { toRiskLevel } from '../../types/analysis';

import type { ApiTrack } from '../../types/api';

import { api } from '../../services/api';

import { useTrackingStore } from '../../store/tracking';
import { useWorkspaceStore } from '../../store/workspace';
import { usePlaybackStore } from '../../store/playback';
import { useWatchlistStore } from '../../store/watchlist';

import {
  clockSeconds,
  distanceAtTime,
  formatClock,
  positionAtTime,
  reportsUntil,
} from '../../services/analysis-playback';

import {
  formatCheckKey,
  formatCheckValue,
  formatDecisionStatus,
  formatDegrees,
  formatDistTrend,
  formatEpoch,
  formatMeters,
  formatMinutes,
  formatMotorConfidence,
  formatNumber,
  formatPercent,
  formatReportSource,
  formatReportType,
  formatRiskLevel,
  formatScenario,
  formatSource,
  formatSpeed,
  formatStage,
  formatUnavailable,
  formatVehicleClass,
} from '../../services/formatters';

import { Button } from '../ui/button';
import { ReportVerdictBadge } from '../reports/ReportVerdictBadge';
import { ReviewCard } from '../review/ReviewCard';


const detailFontOptions = [
  { key: 'normal', label: 'Varsayılan' },
  { key: 'large', label: 'Büyük' },
  { key: 'xlarge', label: 'Çok büyük' },
] as const;

type DetailFontSize =
  (typeof detailFontOptions)[number]['key'];


function nextDetailFontSize(
  current: DetailFontSize,
): DetailFontSize {
  const index = detailFontOptions.findIndex(
    option => option.key === current,
  );

  return detailFontOptions[
    (index + 1) % detailFontOptions.length
  ].key;
}


function DetailSection({
  title,
  meta,
  children,
  defaultOpen = true,
}: {
  title: string;
  meta?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = useId();

  return (
    <section
      className={`entity-detail-section ${
        open ? 'open' : 'collapsed'
      }`}
    >
      <button
        className="entity-detail-section-toggle"
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() =>
          setOpen(current => !current)
        }
      >
        <ChevronDown
          size={14}
          aria-hidden="true"
        />

        <span>
          <h2>{title}</h2>
          {meta && <small>{meta}</small>}
        </span>
      </button>

      {open && (
        <div
          id={panelId}
          className="entity-detail-section-body"
        >
          {children}
        </div>
      )}
    </section>
  );
}


function Grid({
  rows,
}: {
  rows: Array<[string, string]>;
}) {
  return (
    <dl className="entity-detail-grid">
      {rows.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}


/**
 * GET /api/tracks/{id}
 *
 * API'nin track başına mesafe geçmişini,
 * panel açıldığında yükler.
 */
function useApiTrack(
  trackId: string,
  refreshKey: string,
) {
  const [state, setState] = useState<{
    data: ApiTrack | null;
    error: string | null;
    loading: boolean;
  }>({
    data: null,
    error: null,
    loading: true,
  });

  useEffect(() => {
    const controller = new AbortController();

    setState(current => ({
      data:
        current.data?.track_id === trackId
          ? current.data
          : null,
      error: null,
      loading: true,
    }));

    api
      .track(trackId, controller.signal)
      .then(data => {
        if (!controller.signal.aborted) {
          setState({
            data,
            error: null,
            loading: false,
          });
        }
      })
      .catch(cause => {
        if (!controller.signal.aborted) {
          setState({
            data: null,
            error:
              cause instanceof Error
                ? cause.message
                : 'İz alınamadı.',
            loading: false,
          });
        }
      });

    return () => controller.abort();
  }, [trackId, refreshKey]);

  return state;
}


function FrameImage({
  analysis,
  vehicle,
}: {
  analysis: AnalysisData;
  vehicle: AnalysisVehicle;
}) {
  const [failed, setFailed] =
    useState(false);

  const frame = analysis.frames.find(
    item =>
      item.frame_id === vehicle.frame_id,
  );

  const boxes = useMemo(
    () =>
      [
        ...analysis.entities.map(
          entity => entity.vehicle,
        ),
        ...analysis.untracked,
      ].filter(
        (
          item,
        ): item is AnalysisVehicle =>
          Boolean(
            item &&
              item.frame_id ===
                vehicle.frame_id &&
              item.bbox,
          ),
      ),
    [analysis, vehicle.frame_id],
  );

  useEffect(
    () => setFailed(false),
    [vehicle.frame_id],
  );

  if (failed || !frame) {
    return null;
  }

  return (
    <figure className="frame-image">
      <div
        style={{
          aspectRatio: `${frame.width_px} / ${frame.height_px}`,
        }}
      >
        <img
          src={api.imageUrl(
            vehicle.frame_id,
          )}
          alt={`${vehicle.frame_id} drone karesi`}
          onError={() =>
            setFailed(true)
          }
        />

        {boxes.map(item => {
          const [x, y, w, h] =
            item.bbox!;

          return (
            <i
              key={item.vehicle_id}
              className={`frame-bbox risk-${item.risk_level.toLowerCase()} ${
                item.vehicle_id ===
                vehicle.vehicle_id
                  ? 'selected'
                  : ''
              }`}
              title={`${item.vehicle_id} · ${formatVehicleClass(
                item.label,
              )}`}
              style={{
                left: `${
                  (x /
                    frame.width_px) *
                  100
                }%`,
                top: `${
                  (y /
                    frame.height_px) *
                  100
                }%`,
                width: `${
                  (w /
                    frame.width_px) *
                  100
                }%`,
                height: `${
                  (h /
                    frame.height_px) *
                  100
                }%`,
              }}
            />
          );
        })}
      </div>

      <figcaption>
        {vehicle.frame_id} ·{' '}
        {vehicle.capture_time} ·{' '}
        {frame.zone}
      </figcaption>
    </figure>
  );
}


function AssessmentSection({
  analysis,
  entity,
  onChanged,
}: {
  analysis: AnalysisData;
  entity: AnalysisEntity;
  onChanged: () => void;
}) {
  const [busy, setBusy] =
    useState(false);
  const [error, setError] =
    useState('');

  const frameId = entity.frame_id;

  if (!frameId) {
    return (
      <DetailSection title="Ajan Değerlendirmesi">
        <p className="entity-empty-note">
          Bu iz hiçbir karede
          görünmüyor; API onu motorla
          iz sonuna göre
          değerlendiriyor. Ajan
          değerlendirmesi kare
          bazlıdır.
        </p>
      </DetailSection>
    );
  }

  const assessment =
    analysis.assessments[frameId];

  const note =
    assessment?.vehicles.find(
      item =>
        item.vehicle_id ===
        entity.vehicle?.vehicle_id,
    );

  const run = async (
    force: boolean,
  ) => {
    setBusy(true);
    setError('');

    try {
      await api.assessFrame(
        frameId,
        force,
      );

      onChanged();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Değerlendirme başarısız.',
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <DetailSection
      title="Ajan Değerlendirmesi"
      meta={
        assessment
          ? `${frameId} · ${
              assessment.model ??
              'motor şablonu'
            }`
          : frameId
      }
    >
      {!analysis.summary.llm_enabled && (
        <p className="field-report-disclaimer">
          <AlertTriangle size={12} />
          API'de LLM kapalı;
          değerlendirme motor
          şablonuyla üretilir.
        </p>
      )}

      <div className="assessment-actions">
        <button
          disabled={busy}
          onClick={() =>
            void run(
              Boolean(assessment),
            )
          }
        >
          {busy ? (
            <LoaderCircle
              size={12}
              className="spinning"
            />
          ) : (
            <BrainCircuit size={12} />
          )}

          {assessment
            ? 'Yeniden değerlendir'
            : 'Kareyi ajanla değerlendir'}
        </button>

        {assessment?.assessed_at && (
          <small>
            {formatEpoch(
              assessment.assessed_at,
            )}
          </small>
        )}
      </div>

      {error && (
        <div
          className="entity-analysis-error"
          role="alert"
        >
          <ShieldAlert size={16} />

          <span>
            <strong>
              Değerlendirme hatası
            </strong>
            <small>{error}</small>
          </span>
        </div>
      )}

      {assessment ? (
        <>
          <div className="risk-assessment-head">
            <span
              className={`entity-risk risk-${toRiskLevel(
                assessment.risk_level,
              ).toLowerCase()}`}
            >
              Kare:{' '}
              {formatRiskLevel(
                assessment.risk_level,
              )}
            </span>

            {assessment.llm_risk_level && (
              <span
                className={`entity-risk risk-${toRiskLevel(
                  assessment.llm_risk_level,
                ).toLowerCase()}`}
              >
                LLM:{' '}
                {formatRiskLevel(
                  assessment.llm_risk_level,
                )}
              </span>
            )}

            <b>
              {formatPercent(
                assessment.confidence,
              )}{' '}
              güven
            </b>
          </div>

          <p className="risk-assessment-summary">
            <strong>
              {assessment.headline}
            </strong>
          </p>

          <p className="risk-assessment-summary">
            {assessment.summary}
          </p>

          {note && (
            <div className="assessment-list evidence">
              <h3>Bu araç için</h3>
              <p>{note.explanation}</p>

              {note.change_reason && (
                <p>
                  Seviye değişikliği
                  gerekçesi:{' '}
                  {note.change_reason}
                </p>
              )}
            </div>
          )}

          {assessment.reasoning_steps
            .length > 0 && (
            <div className="assessment-list">
              <h3>
                Gerekçe adımları
              </h3>

              {assessment.reasoning_steps.map(
                (step, index) => (
                  <p
                    key={`${step.stage}-${index}`}
                  >
                    <b>
                      {formatStage(
                        step.stage,
                      )}
                      :
                    </b>{' '}
                    {step.finding}
                    {step.evidence.length
                      ? ` (${step.evidence.join(
                          ', ',
                        )})`
                      : ''}
                  </p>
                ),
              )}
            </div>
          )}

          {assessment
            .recommended_actions
            .length > 0 && (
            <div className="assessment-list evidence">
              <h3>
                Önerilen eylemler
              </h3>

              {assessment.recommended_actions.map(
                action => (
                  <p key={action}>
                    {action}
                  </p>
                ),
              )}
            </div>
          )}

          {assessment.disagreement && (
            <div className="assessment-list uncertainty">
              <h3>
                Görüş ayrılığı
              </h3>
              <p>
                {assessment.disagreement}
              </p>
            </div>
          )}

          {assessment
            .injection_report_ids
            .length > 0 && (
            <div className="entity-analysis-error">
              <ShieldAlert size={16} />

              <span>
                <strong>
                  Talimat enjeksiyonu
                  tespit edildi
                </strong>

                <small>
                  {assessment.injection_report_ids.join(
                    ', ',
                  )}
                </small>
              </span>
            </div>
          )}

          {assessment.guardrail_notes &&
            assessment.guardrail_notes
              .length > 0 && (
              <div className="assessment-list uncertainty">
                <h3>
                  Güvenlik notları
                </h3>

                {assessment.guardrail_notes.map(
                  item => (
                    <p key={item}>
                      {item}
                    </p>
                  ),
                )}
              </div>
            )}
        </>
      ) : (
        <div className="unknown-assessment">
          <BrainCircuit size={17} />

          <span>
            <strong>
              Henüz
              değerlendirilmedi
            </strong>

            <small>
              Ajan bu kare için
              çalıştırılmadı.
              Değerlendirme motor ile
              LLM'in ortak kararını
              üretir.
            </small>
          </span>
        </div>
      )}
    </DetailSection>
  );
}


export function TrackDetail({
  analysis,
  entity,
  playbackTime,
  onChanged,
}: {
  analysis: AnalysisData;
  entity: AnalysisEntity;
  playbackTime?: number;
  onChanged: () => void;
}) {
  const [detailFontSize, setDetailFontSize] =
    useState<DetailFontSize>(() => {
      if (
        typeof window ===
        'undefined'
      ) {
        return 'normal';
      }

      const stored =
        window.localStorage.getItem(
          'track-detail-font-size',
        );

      return detailFontOptions.some(
        option =>
          option.key === stored,
      )
        ? (stored as DetailFontSize)
        : 'normal';
    });

  const select =
    useTrackingStore(
      state => state.selectTrack,
    );

  const follow =
    useTrackingStore(
      state => state.followVehicle,
    );

  const setFollow =
    useTrackingStore(
      state => state.setFollowVehicle,
    );

  const requestView =
    useTrackingStore(
      state => state.requestView,
    );

  const watching =
    useWatchlistStore(state =>
      state.trackIds.includes(
        entity.track_id,
      ),
    );

  const toggleWatch =
    useWatchlistStore(
      state => state.toggle,
    );

  const analyst =
    useWorkspaceStore(
      state => state.analyst,
    );

  const apiTrack = useApiTrack(
    entity.track_id,
    analysis.generated_at,
  );

  const time =
    playbackTime ??
    clockSeconds(entity.last_seen);

  const position =
    positionAtTime(entity, time);

  const vehicle = entity.vehicle;
  const features = entity.features;

  const margin =
    vehicle?.margin ??
    entity.offframe?.margin ??
    null;

  const decision =
    vehicle?.decision ?? null;

  const review = vehicle
    ? analysis.reviews.items.find(
        item =>
          item.vehicle_id ===
          vehicle.vehicle_id,
      )
    : undefined;

  const visibleReports =
    reportsUntil(entity, time);

  const distancePoints =
    apiTrack.data?.points ?? [];

  const visibleDistance =
    distancePoints.filter(
      point =>
        clockSeconds(point.time) <=
        time,
    );

  const currentDistance =
    distanceAtTime(
      distancePoints,
      time,
    );

  const minimumDistance =
    distancePoints.length
      ? Math.min(
          ...distancePoints.map(
            point =>
              point.dist_to_base_m,
          ),
        )
      : null;

  const riskClass =
    entity.risk_level.toLowerCase();

  const detailFontLabel =
    detailFontOptions.find(
      option =>
        option.key === detailFontSize,
    )?.label ?? 'Varsayılan';

  useEffect(() => {
    window.localStorage.setItem(
      'track-detail-font-size',
      detailFontSize,
    );
  }, [detailFontSize]);

  return (
    <aside
      className={`vehicle-details entity-track-detail detail-font-${detailFontSize}`}
      aria-label="Araç detayları"
    >
      <div className="details-heading">
        <span className="section-eyebrow">
          İZ DETAYI
        </span>

        <span className="entity-detail-heading-actions">
          <Button
            variant="ghost"
            size="icon"
            className="detail-font-cycle"
            aria-label={`Yazı boyutu: ${detailFontLabel}. Değiştirmek için tıkla`}
            title={`Yazı boyutu: ${detailFontLabel}`}
            onClick={() =>
              setDetailFontSize(
                current =>
                  nextDetailFontSize(
                    current,
                  ),
              )
            }
          >
            <Search size={15} />
          </Button>

          <Button
            variant="ghost"
            size="icon"
            aria-label="Detay panelini daralt"
            onClick={() =>
              useWorkspaceStore
                .getState()
                .toggleInspector()
            }
          >
            <PanelRightClose
              size={15}
            />
          </Button>

          <Button
            variant="ghost"
            size="icon"
            aria-label="İz seçimini temizle"
            onClick={() =>
              select(null)
            }
          >
            <X size={16} />
          </Button>
        </span>
      </div>

      <div className="entity-detail-title">
        <span>
          <Route size={18} />
        </span>

        <div>
          <small>
            {formatClock(time)} ·{' '}
            {formatSource(
              entity.source,
            )}
          </small>

          <strong>
            {entity.track_id}
          </strong>

          <em>
            {formatVehicleClass(
              entity.vehicle_class,
            )}

            {position?.stale
              ? ' · son bilinen konum'
              : ''}
          </em>
        </div>

        <span
          className={`entity-risk risk-${riskClass}`}
        >
          {formatRiskLevel(
            entity.risk_level,
          )}
        </span>
      </div>

      <div className="vehicle-actions">
        <Button
          className="watchlist-toggle-button"
          variant={
            watching
              ? 'default'
              : 'outline'
          }
          aria-pressed={watching}
          title={
            watching
              ? 'İzlemeden çıkar'
              : 'İzlemeye al'
          }
          onClick={() =>
            toggleWatch(
              entity.track_id,
            )
          }
        >
          <Eye size={13} />

          {watching
            ? 'İzleniyor'
            : 'İzlemeye al'}
        </Button>

        <Button
          variant={
            follow
              ? 'default'
              : 'outline'
          }
          aria-pressed={follow}
          onClick={() =>
            setFollow(!follow)
          }
        >
          <Crosshair size={13} />
          Takip et
        </Button>

        <Button
          variant="outline"
          onClick={() =>
            requestView('vehicle')
          }
        >
          <Focus size={13} />
          Haritada odaklan
        </Button>

        {entity.observed_at && (
          <Button
            variant="outline"
            onClick={() => {
              usePlaybackStore
                .getState()
                .seek(
                  clockSeconds(
                    entity.observed_at!,
                  ),
                );

              requestView(
                'vehicle',
              );
            }}
          >
            <Clock3 size={13} />
            Gözlem anına git (
            {entity.observed_at})
          </Button>
        )}
      </div>

      {entity.risk_level ===
        'UNKNOWN' && (
        <div
          className="entity-analysis-error"
          role="alert"
        >
          <ShieldAlert size={16} />

          <span>
            <strong>
              Değerlendirme yok
            </strong>

            <small>
              API bu iz için risk
              seviyesi döndürmedi.
            </small>
          </span>
        </div>
      )}

      {entity.source ===
        'track_only' && (
        <div className="entity-quality-warning">
          <AlertTriangle size={16} />

          <span>
            <strong>
              Tespit edilmemiş araç
            </strong>

            <small>
              Karede izi var ama
              dedektör bu aracı
              kaçırmış; API aracı
              izden kurtardı.
            </small>
          </span>
        </div>
      )}

      {vehicle &&
        vehicle.friendly_confirmed_by
          .length > 0 && (
          <div className="entity-quality-warning friendly">
            <ShieldCheck size={16} />

            <span>
              <strong>
                Resmi dost teyidi
              </strong>

              <small>
                {vehicle.friendly_confirmed_by.join(
                  ', ',
                )}{' '}
                raporu ile risk
                DÜŞÜK'e indirildi.
              </small>
            </span>
          </div>
        )}

      <DetailSection
        title="Risk Kararı"
        meta={formatDecisionStatus(
          entity.decision_status,
        )}
      >
        <div className="risk-assessment-head">
          <span
            className={`entity-risk risk-${riskClass}`}
          >
            Nihai:{' '}
            {formatRiskLevel(
              entity.risk_level,
            )}
          </span>

          <span
            className={`entity-risk risk-${entity.engine_risk_level.toLowerCase()}`}
          >
            Motor:{' '}
            {formatRiskLevel(
              entity.engine_risk_level,
            )}
          </span>

          {decision?.llm_level && (
            <span
              className={`entity-risk risk-${toRiskLevel(
                decision.llm_level,
              ).toLowerCase()}`}
            >
              LLM:{' '}
              {formatRiskLevel(
                decision.llm_level,
              )}
            </span>
          )}
        </div>

        {decision && (
          <div className="assessment-list">
            <h3>
              {decision.rule_label}
            </h3>

            {decision.note && (
              <p>{decision.note}</p>
            )}

            {decision.llm_reason && (
              <p>
                LLM gerekçesi:{' '}
                {decision.llm_reason}
              </p>
            )}
          </div>
        )}

        {margin && (
          <div className="assessment-list uncertainty">
            <h3>
              Motor güveni:{' '}
              {formatMotorConfidence(
                margin.confidence,
              )}
            </h3>

            {margin.notes.map(
              item => (
                <p key={item}>
                  {item}
                </p>
              ),
            )}
          </div>
        )}

        {review && (
          <ReviewCard
            key={`${review.vehicle_id}-${review.review?.at ?? 'pending'}-${review.current_level}`}
            item={review}
            humanReview={
              analysis.human_review
            }
            analyst={analyst}
            onChanged={onChanged}
            compact
          />
        )}
      </DetailSection>

      <DetailSection
        title="Senaryo ve Gerekçeler"
        meta={
          entity.scenario
            ? formatScenario(
                entity.scenario,
              )
            : formatUnavailable()
        }
      >
        {entity.risk_reasons
          .length ? (
          <div className="assessment-list">
            {entity.risk_reasons.map(
              reason => (
                <p key={reason}>
                  {reason}
                </p>
              ),
            )}
          </div>
        ) : (
          <p className="entity-empty-note">
            API gerekçe
            döndürmedi.
          </p>
        )}
      </DetailSection>

      <DetailSection
        title="Gözlem"
        meta={
          entity.observed_at
            ? `${entity.observed_at} · ${
                entity.zone ?? ''
              }`
            : formatUnavailable()
        }
      >
        {vehicle ? (
          <>
            <Grid
              rows={[
                [
                  'Kare',
                  vehicle.frame_id,
                ],
                [
                  'Çekim zamanı',
                  vehicle.capture_time,
                ],
                [
                  'Araç kimliği',
                  vehicle.vehicle_id,
                ],
                [
                  'Tespit güveni',
                  formatPercent(
                    vehicle.confidence,
                  ),
                ],
                [
                  'Bölge',
                  vehicle.zone,
                ],
                [
                  'Üsse mesafe',
                  formatMeters(
                    vehicle.distance_to_base_m,
                  ),
                ],
                [
                  'Üsten kerteriz',
                  formatDegrees(
                    vehicle.bearing_from_base_deg,
                  ),
                ],
                [
                  'İz eşleşme sapması',
                  vehicle.track_match_m ==
                  null
                    ? formatUnavailable()
                    : `${formatNumber(
                        vehicle.track_match_m,
                        1,
                      )} m`,
                ],
              ]}
            />

            <FrameImage
              analysis={analysis}
              vehicle={vehicle}
            />
          </>
        ) : entity.offframe ? (
          <Grid
            rows={[
              [
                'Son nokta',
                entity.offframe
                  .last_time,
              ],
              [
                'Bölge',
                entity.offframe.zone,
              ],
              [
                'Üsse mesafe',
                formatMeters(
                  entity.offframe
                    .features
                    .dist_now_m,
                ),
              ],
              [
                'Konum',
                `${formatNumber(
                  entity.offframe.lat,
                  5,
                )}, ${formatNumber(
                  entity.offframe.lon,
                  5,
                )}`,
              ],
            ]}
          />
        ) : (
          <p className="entity-empty-note">
            Bu iz için API gözlemi
            yok.
          </p>
        )}
      </DetailSection>

      <DetailSection
        title="Hareket Öznitelikleri"
        meta={
          features
            ? `${features.t_start}–${features.t_end} penceresi`
            : formatUnavailable()
        }
      >
        {features ? (
          <>
            <Grid
              rows={[
                [
                  'Anlık hız',
                  formatSpeed(
                    features.speed_now_mps,
                  ),
                ],
                [
                  'En yüksek hız',
                  formatSpeed(
                    features.max_speed_mps,
                  ),
                ],
                [
                  'Üsse yaklaşma hızı',
                  formatSpeed(
                    features.closing_speed_mps,
                  ),
                ],
                [
                  'Tahmini varış (ETA)',
                  formatMinutes(
                    features.eta_min,
                  ),
                ],
                [
                  'Yönelim sapması',
                  formatDegrees(
                    features.heading_offset_deg,
                  ),
                ],
                [
                  'Mesafe trendi',
                  formatDistTrend(
                    features.dist_trend,
                  ),
                ],
                [
                  'Son 60 dk yaklaşma',
                  formatMeters(
                    features.approach_last60_m,
                  ),
                ],
                [
                  'Toplam yaklaşma',
                  formatMeters(
                    features.approach_total_m,
                  ),
                ],
                [
                  'En yakın mesafe',
                  formatMeters(
                    features.dist_min_m,
                  ),
                ],
                [
                  'Hareket ediyor mu?',
                  features.moving_now
                    ? 'Evet'
                    : 'Hayır',
                ],
                [
                  'Yol uzunluğu',
                  formatMeters(
                    features.path_length_m,
                  ),
                ],
                [
                  'Net yer değiştirme',
                  formatMeters(
                    features.net_displacement_m,
                  ),
                ],
                [
                  'Kapladığı alan',
                  formatMeters(
                    features.extent_m,
                  ),
                ],
                [
                  'Taranan açı',
                  formatDegrees(
                    features.angular_sweep_deg,
                  ),
                ],
                [
                  'Duraklama',
                  `${features.stops.length} (${features.stopped_minutes_total} dk)`,
                ],
                [
                  'Başlangıç bekleme',
                  `${features.initial_wait_min} dk`,
                ],
              ]}
            />

            {features.stops.length >
              0 && (
              <div className="entity-history-table">
                <table>
                  <thead>
                    <tr>
                      <th>
                        Duraklama
                      </th>
                      <th>Süre</th>
                      <th>
                        Üsse mesafe
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {features.stops.map(
                      stop => (
                        <tr
                          key={`${stop.start}-${stop.end}`}
                        >
                          <td>
                            {stop.start}–
                            {stop.end}
                          </td>
                          <td>
                            {
                              stop.minutes
                            }{' '}
                            dk
                          </td>
                          <td>
                            {formatMeters(
                              stop.dist_to_base_m,
                            )}
                          </td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : (
          <p className="entity-empty-note">
            Bu araç için hareket
            özniteliği yok.
          </p>
        )}
      </DetailSection>

      <AssessmentSection
        analysis={analysis}
        entity={entity}
        onChanged={onChanged}
      />

      <DetailSection
        title="Anlık Konum"
        meta={
          position
            ? formatClock(time)
            : 'İz henüz başlamadı'
        }
      >
        {position ? (
          <Grid
            rows={[
              [
                'Enlem',
                formatNumber(
                  position.lat,
                  6,
                ),
              ],
              [
                'Boylam',
                formatNumber(
                  position.lon,
                  6,
                ),
              ],
              [
                'Üsse mesafe',
                apiTrack.loading &&
                !apiTrack.data
                  ? 'Yükleniyor…'
                  : formatMeters(
                      currentDistance,
                    ),
              ],
              [
                'İz boyunca en yakın',
                formatMeters(
                  minimumDistance,
                ),
              ],
            ]}
          />
        ) : (
          <p className="entity-empty-note">
            Bu iz {formatClock(time)}
            {' '}anında henüz
            başlamamış (
            {entity.first_seen}).
          </p>
        )}
      </DetailSection>

      <DetailSection
        title="Saha Raporları"
        meta={`${visibleReports.length}/${entity.reports.length} rapor · ${formatClock(time)} anına kadar`}
      >
        <p className="field-report-disclaimer">
          <AlertTriangle size={12} />
          Rapor hükümleri API'nin
          doğrulamasıdır; saha raporu
          metni güvenilmez veri
          olarak ele alınır.
        </p>

        {visibleReports.length ? (
          <div className="entity-report-list">
            {visibleReports.map(
              report => (
                <article
                  key={
                    report.report_id
                  }
                >
                  <header>
                    <span>
                      <strong>
                        {
                          report.report_id
                        }{' '}
                        · {report.time}
                      </strong>

                      <small>
                        {formatReportSource(
                          report.source,
                        )}{' '}
                        ·{' '}
                        {formatReportType(
                          report.report_type,
                        )}
                      </small>
                    </span>

                    <ReportVerdictBadge
                      verdict={
                        report.verdict
                      }
                    />
                  </header>

                  <p>{report.text}</p>

                  <div className="report-reasons">
                    <span>
                      {report.summary}
                    </span>

                    {report.injection_detected && (
                      <span className="injection">
                        Talimat
                        enjeksiyonu:{' '}
                        {report.injection_span ??
                          'tespit edildi'}
                      </span>
                    )}

                    {report.affects_risk && (
                      <span>
                        Riski etkiliyor
                      </span>
                    )}
                  </div>

                  {Object.keys(
                    report.checks,
                  ).length > 0 && (
                    <details>
                      <summary>
                        Doğrulama
                        kontrolleri (
                        {
                          Object.keys(
                            report.checks,
                          ).length
                        }
                        )
                      </summary>

                      {Object.entries(
                        report.checks,
                      ).map(
                        ([
                          key,
                          value,
                        ]) => (
                          <div
                            className="entity-report-check"
                            key={key}
                          >
                            <span>
                              {formatCheckKey(
                                key,
                              )}
                            </span>

                            <small>
                              {formatCheckValue(
                                value,
                              )}
                            </small>
                          </div>
                        ),
                      )}
                    </details>
                  )}
                </article>
              ),
            )}
          </div>
        ) : (
          <p className="entity-empty-note">
            {formatClock(time)} anına
            kadar bu izle eşleşen saha
            raporu yok.
          </p>
        )}
      </DetailSection>

      <DetailSection
        title="Mesafe Geçmişi"
        meta={
          apiTrack.data
            ? `${visibleDistance.length}/${distancePoints.length} nokta`
            : apiTrack.loading
              ? 'Yükleniyor…'
              : formatUnavailable()
        }
      >
        {apiTrack.error && (
          <div
            className="entity-analysis-error"
            role="alert"
          >
            <ShieldAlert size={16} />

            <span>
              <strong>
                İz verisi alınamadı
              </strong>

              <small>
                {apiTrack.error}
              </small>
            </span>
          </div>
        )}

        {visibleDistance.length >
          0 && (
          <>
            <div
              className="entity-history-chart"
              aria-label="Zamana göre üs mesafesi"
            >
              <div className="chart-heading">
                <h3>
                  Zamana göre üs
                  mesafesi
                </h3>
                <span>metre</span>
              </div>

              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <LineChart
                  data={
                    visibleDistance
                  }
                  margin={{
                    top: 8,
                    right: 8,
                    bottom: 0,
                    left: -18,
                  }}
                >
                  <CartesianGrid
                    vertical={false}
                    stroke="#293940"
                    strokeDasharray="2 4"
                  />

                  <XAxis
                    dataKey="time"
                    tick={{
                      fill: '#81949d',
                      fontSize: 7,
                    }}
                    axisLine={false}
                    tickLine={false}
                  />

                  <YAxis
                    dataKey="dist_to_base_m"
                    tick={{
                      fill: '#81949d',
                      fontSize: 7,
                    }}
                    axisLine={false}
                    tickLine={false}
                  />

                  <Tooltip
                    contentStyle={{
                      background:
                        '#142027',
                      border:
                        '1px solid #3c4f58',
                      borderRadius: 4,
                      fontSize: 8,
                    }}
                    formatter={value => [
                      `${Number(
                        value,
                      ).toFixed(1)} m`,
                      'Üs mesafesi',
                    ]}
                  />

                  <Line
                    type="monotone"
                    dataKey="dist_to_base_m"
                    stroke="#85baa6"
                    strokeWidth={2}
                    dot={{
                      r: 2,
                      fill: '#a5d8c3',
                    }}
                    isAnimationActive={
                      false
                    }
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="entity-history-table">
              <table>
                <thead>
                  <tr>
                    <th>Zaman</th>
                    <th>Enlem</th>
                    <th>Boylam</th>
                    <th>
                      Üsse mesafe
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {visibleDistance.map(
                    point => (
                      <tr
                        key={
                          point.time
                        }
                      >
                        <td>
                          {
                            point.time
                          }
                        </td>

                        <td>
                          {formatNumber(
                            point.lat,
                            5,
                          )}
                        </td>

                        <td>
                          {formatNumber(
                            point.lon,
                            5,
                          )}
                        </td>

                        <td>
                          {formatMeters(
                            point.dist_to_base_m,
                          )}
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}

        {apiTrack.data &&
          !visibleDistance.length && (
            <p className="entity-empty-note">
              {formatClock(time)} anına
              kadar iz noktası yok.
            </p>
          )}
      </DetailSection>

      {vehicle &&
        (() => {
          const frame =
            analysis.frames.find(
              item =>
                item.frame_id ===
                vehicle.frame_id,
            );

          return frame?.pipeline_steps
            .length ? (
            <DetailSection
              title="Motor Adımları"
              meta={frame.frame_id}
            >
              <div className="assessment-list">
                {frame.pipeline_steps.map(
                  step => (
                    <p key={step.key}>
                      <b>
                        {step.step}.{' '}
                        {step.title}:
                      </b>{' '}
                      {step.summary}
                    </p>
                  ),
                )}
              </div>
            </DetailSection>
          ) : null;
        })()}
    </aside>
  );
}
"""Graph analizi veri modelleri.
Tüm veri yapıları tip güvenli, serializable ve temiz katman ayrımına uygundur.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Structured Intelligence (LLM extraction schema)
# ---------------------------------------------------------------------------
class StructuredIntelligence(BaseModel):
    """Saha raporu veya yazılı istihbarat kaydından LLM aracılığıyla çıkarılan yapılandırılmış bilgi."""
    report_id: str = Field(description="İstihbarat raporunun özgün kimliği")
    location_name: str | None = Field(default=None, description="Metinde açıkça geçen yer veya bölge adı (yoksa null)")
    lat: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False, description="Metindeki enlem (yoksa null)")
    lon: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False, description="Metindeki boylam (yoksa null)")
    time_info: str | None = Field(default=None, description="Olay veya gözlem zamanı")
    event_type: str = Field(description="Olay türü (ör: intikal, bekleme, devriye, temas, trafik_akisi)")
    description: str = Field(description="1-2 cümlelik nesnel özet")
    confidence: Literal["high", "medium", "low"] | None = Field(
        default=None, description="Metinde belirtilen kesinlik; belirtilmemişse null"
    )
    mentioned_vehicles: list[str] = Field(default_factory=list, description="Bahsedilen araç tipleri veya plakaları")
    keywords: list[str] = Field(default_factory=list, description="Öne çıkan anahtar kelimeler")
    source: str = Field(default="field_report", description="İstihbarat kaynağı veya referansı")
    has_explicit_coordinates: bool = Field(default=False, description="Koordinat metinde kesin olarak var mıydı")
    extraction_method: str = "deterministic"
    unmatched_reason: str | None = None

    @model_validator(mode="after")
    def paired_coordinates(self):
        if (self.lat is None) != (self.lon is None):
            raise ValueError("Coordinates must be supplied as a pair")
        return self


# ---------------------------------------------------------------------------
# Spatial Graph Core Entities
# ---------------------------------------------------------------------------
@dataclass
class SpatialNode:
    """Trajectory graph içerisindeki coğrafi olarak kümelenmiş kavşak / koridor düğümü."""
    node_id: str
    lat: float
    lon: float
    # Gözlem ve araç sayımları
    total_vehicle_count: int = 0
    normal_vehicle_count: int = 0
    threat_vehicle_count: int = 0
    unique_vehicle_count: int = 0
    unique_threat_trajectories: int = 0
    unique_normal_trajectories: int = 0
    # Graph yapısal bağlantı metrikleri
    incoming_edge_count: int = 0
    outgoing_edge_count: int = 0
    degree_centrality: float = 0.0
    in_degree_centrality: float = 0.0
    out_degree_centrality: float = 0.0
    betweenness_centrality: float = 0.0
    weighted_degree: float = 0.0
    # Alt graph metrikleri
    threat_graph_centrality: float = 0.0
    normal_graph_centrality: float = 0.0
    # Özel oran ve lift metrikleri
    raw_threat_ratio: float = 0.0
    smoothed_threat_rate: float = 0.0
    global_threat_rate: float = 0.0
    threat_lift: float = 0.0
    threat_normal_centrality_gap: float = 0.0
    threat_trajectory_importance: float = 0.0  # Toplam threat izlerinin yüzde kaçı burayı kullandı
    # Örneklem güveni ve istatistiksel düzeltme
    sample_confidence: float = 0.0
    effective_pseudo_count: float = 0.0
    # İstihbarat ilişkilendirmesi (corroboration)
    related_intelligence_count: int = 0
    related_intelligence_ids: list[str] = field(default_factory=list)
    intelligence_confidence: float = 0.0
    intelligence_summaries: list[str] = field(default_factory=list)
    # Nihai açıklanabilir ilgi skoru ve gerekçeler
    interest_score: float = 0.0
    severity: str = "DUSUK"  # DUSUK, ORTA, YUKSEK, KRITIK
    explanations: list[str] = field(default_factory=list)
    recommendation: str = "Rutin izleme yeterli."
    # Düğüme atanan ham GPS nokta sayısı
    point_count: int = 0
    passage_count: int = 0
    score_breakdown: dict[str, Any] = field(default_factory=dict)
    graph_interest_score: float = 0.0
    intelligence_contribution: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["lat"] = round(self.lat, 6)
        d["lon"] = round(self.lon, 6)
        d["degree_centrality"] = round(self.degree_centrality, 4)
        d["betweenness_centrality"] = round(self.betweenness_centrality, 4)
        d["threat_graph_centrality"] = round(self.threat_graph_centrality, 4)
        d["normal_graph_centrality"] = round(self.normal_graph_centrality, 4)
        d["raw_threat_ratio"] = round(self.raw_threat_ratio, 4)
        d["smoothed_threat_rate"] = round(self.smoothed_threat_rate, 4)
        d["global_threat_rate"] = round(self.global_threat_rate, 4)
        d["threat_lift"] = round(self.threat_lift, 3)
        d["threat_normal_centrality_gap"] = round(self.threat_normal_centrality_gap, 4)
        d["threat_trajectory_importance"] = round(self.threat_trajectory_importance, 4)
        d["sample_confidence"] = round(self.sample_confidence, 3)
        d["interest_score"] = round(self.interest_score, 3)
        return d


@dataclass
class SpatialEdge:
    """İki spatial node arasındaki araç geçiş bağlantısı."""
    source_id: str
    target_id: str
    total_weight: int = 0
    threat_weight: int = 0
    normal_weight: int = 0
    unique_tracks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "total_weight": self.total_weight,
            "threat_weight": self.threat_weight,
            "normal_weight": self.normal_weight,
            "unique_track_count": len(set(self.unique_tracks)),
        }


# ---------------------------------------------------------------------------
# High-Interest Merged Region (Operatöre Karar Desteği Çıktısı)
# ---------------------------------------------------------------------------
@dataclass
class HighInterestRegion:
    """Birbirine yakın yüksek skorlu düğümlerin spatial deduplication ile birleştirilmiş bölgesi."""
    region_id: str
    lat: float
    lon: float
    radius_m: float
    interest_score: float
    severity: str
    total_vehicle_count: int
    threat_vehicle_count: int
    normal_vehicle_count: int
    global_threat_rate: float
    local_threat_rate: float
    threat_lift: float
    threat_normal_centrality_gap: float
    unique_threat_trajectories: int
    related_intelligence_count: int
    confidence: float
    recommendation: str
    explanation: list[str]
    related_intelligence_ids: list[str]
    member_node_ids: list[str] = field(default_factory=list)
    score_breakdown: dict[str, Any] = field(default_factory=dict)
    graph_interest_score: float = 0.0
    intelligence_contribution: float = 0.0
    representative_node_id: str = ""
    vehicle_assessments: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "location": {"lat": round(self.lat, 6), "lon": round(self.lon, 6)},
            "radius_m": round(self.radius_m, 1),
            "interest_score": round(self.interest_score, 2),
            "severity": self.severity,
            "total_vehicle_count": self.total_vehicle_count,
            "threat_vehicle_count": self.threat_vehicle_count,
            "normal_vehicle_count": self.normal_vehicle_count,
            "global_threat_rate": round(self.global_threat_rate, 4),
            "local_threat_rate": round(self.local_threat_rate, 4),
            "threat_lift": round(self.threat_lift, 2),
            "threat_normal_centrality_gap": round(self.threat_normal_centrality_gap, 4),
            "unique_threat_trajectories": self.unique_threat_trajectories,
            "related_intelligence_count": self.related_intelligence_count,
            "confidence": round(self.confidence, 2),
            "recommendation": self.recommendation,
            "explanation": self.explanation,
            "related_intelligence_ids": self.related_intelligence_ids,
            "member_node_ids": self.member_node_ids,
            "score_breakdown": self.score_breakdown,
            "graph_interest_score": round(self.graph_interest_score, 4),
            "intelligence_contribution": round(self.intelligence_contribution, 4),
            "representative_node_id": self.representative_node_id,
            "vehicle_assessments": self.vehicle_assessments,
        }


# ---------------------------------------------------------------------------
# Full Graph Analysis Summary
# ---------------------------------------------------------------------------
@dataclass
class GraphAnalysisResult:
    """Tüm analiz zaman aralığı için graph analizi çıktısı."""
    generated_at: float
    total_nodes: int
    total_edges: int
    total_trajectories: int
    total_threat_trajectories: int
    total_normal_trajectories: int
    global_threat_rate: float
    regions: list[HighInterestRegion]
    nodes: list[SpatialNode]
    edges: list[SpatialEdge]
    unmatched_intelligence: list[StructuredIntelligence]
    matched_intelligence_count: int
    analysis_start: str | None = None
    analysis_end: str | None = None
    data_revision: str = ""
    unclassified_trajectory_count: int = 0
    region_interest_threshold: float = 0.35

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "total_trajectories": self.total_trajectories,
            "total_threat_trajectories": self.total_threat_trajectories,
            "total_normal_trajectories": self.total_normal_trajectories,
            "global_threat_rate": round(self.global_threat_rate, 4),
            "region_count": len(self.regions),
            "regions": [r.to_dict() for r in self.regions],
            "high_interest_regions": [r.to_dict() for r in self.regions if r.interest_score >= self.region_interest_threshold],
            "high_interest_region_count": sum(r.interest_score >= self.region_interest_threshold for r in self.regions),
            "region_interest_threshold": self.region_interest_threshold,
            "unmatched_intelligence_count": len(self.unmatched_intelligence),
            "matched_intelligence_count": self.matched_intelligence_count,
            "analysis_start": self.analysis_start,
            "analysis_end": self.analysis_end,
            "data_revision": self.data_revision,
            "unclassified_trajectory_count": self.unclassified_trajectory_count,
            "context": "game_simulation",
        }

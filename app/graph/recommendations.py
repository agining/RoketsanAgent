"""Explanations and observation suggestions for the game's replay screen."""
from .config import RegionClusteringConfig
from .models import SpatialNode


def describe_node(node: SpatialNode, config: RegionClusteringConfig) -> None:
    if node.interest_score >= config.critical_interest_threshold:
        node.severity = "KRITIK"
    elif node.interest_score >= config.high_interest_threshold:
        node.severity = "YUKSEK"
    elif node.interest_score >= config.medium_interest_threshold:
        node.severity = "ORTA"
    else:
        node.severity = "DUSUK"
    node.explanations = [
        f"Bu aralıkta {node.total_vehicle_count} tekil araç; {node.threat_vehicle_count} threat etiketli araç gözlendi.",
        f"Yerel etiket oranı %{node.raw_threat_ratio * 100:.1f}; genel oran %{node.global_threat_rate * 100:.1f}; lift {node.threat_lift:.2f}x.",
        f"Threat–normal merkezilik farkı {node.threat_normal_centrality_gap:+.4f}.",
        f"{node.unique_threat_trajectories} tekil threat rotası; tüm threat rotalarının %{node.threat_trajectory_importance * 100:.1f}'i.",
    ]
    if node.global_threat_rate in (0, 1):
        node.explanations.append("Analiz aralığında iki sınıf da bulunmadığından karşılaştırmalı anomali skoru üretilmedi.")
    if node.related_intelligence_count:
        node.explanations.append(
            f"{node.related_intelligence_count} Rapor konumla eşleşti; rapor içeriği bağımsız olarak doğrulanmış sayılmaz."
        )
    node.explanations.append(f"Düzeltmede {node.effective_pseudo_count:.2f} sanal gözlem kullanıldı; gözlem hacmi güveni %{node.sample_confidence * 100:.1f}. Bu güven bir olasılık değildir.")
    if node.sample_confidence < 0.5:
        node.explanations.append("Örneklem sınırlı; anomali seviyesi gözlem güveninden ayrı gösterilir.")
    if node.interest_score >= config.high_interest_threshold:
        node.recommendation = "Yüksek ilgi bölgesi: Bilirkişi incelemesi ve gözlem sıklığının artırılması değerlendirilebilir."
    elif node.interest_score >= config.medium_interest_threshold:
        node.recommendation = "Gözlem sıklığının artırılması değerlendirilebilir."
    else:
        node.recommendation = "Rutin gözlem; belirgin bir etiket yoğunlaşması saptanmadı."

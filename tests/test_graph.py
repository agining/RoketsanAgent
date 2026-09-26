"""Synthetic game-map regression tests; no external LLM calls or production writes."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.data import Track, TrackPoint
from app.graph.builder import SpatialGraphBuilder
from app.graph.clustering import RegionMerger
from app.graph.config import GraphAnalysisConfig, SpatialGraphConfig, ScoreWeightsConfig
from app.graph.geometry import LocalProjection
from app.graph.intelligence import IntelligenceProcessor
from app.graph.metrics import compute_all_metrics
from app.graph.models import SpatialNode, StructuredIntelligence
from app.graph.routes import router, get_graph_service
from app.graph.scorer import ExplainableScorer
from app.graph.service import GraphAnalysisService
from app.graph.smoothing import compute_sample_confidence, compute_smoothed_threat_rate, compute_threat_lift
from app.graph.window import clip_tracks

PROJECTION = LocalProjection(0, 0)


def test_filtered_duplicate_detections_do_not_promote_tracks():
    svc = GameService({'a': track('a', [(0, 0)])})
    svc.state.offframe_risk = {}
    svc.state.vehicles = {'v': {'vehicle_id': 'v', 'track_id': 'a', 'risk_level': 'YUKSEK', 'filtered': True}}
    graph = GraphAnalysisService(svc, enable_llm=False)
    assert graph._determine_track_classifications(GraphAnalysisConfig()) == {}


def test_fusion_feedback_preserves_final_level_and_all_evidence():
    from app.graph.assessments import stored_vehicle_feedback
    svc = SimpleNamespace(state=SimpleNamespace(frames={'f': {}}, vehicles={'v': {'track_id': 'a'}}),
        assessments={'f': {'vehicles': [{'vehicle_id': 'v', 'explanation': 'İlk değerlendirme'}]}},
        decision_map=lambda: {'v': {'llm_reason': 'İlk gerekçe', 'fusion_explanation': 'Nihai gerekçe',
                                  'evidence_report_ids': ['r1'], 'fusion_evidence_report_ids': ['r2']}},
        vehicle_final=lambda *args: {'level': 'DUSUK'})
    record = stored_vehicle_feedback(svc, {'a'})[0]
    assert record['level'] == 'DUSUK'
    assert 'Nihai gerekçe' in record['reason']
    assert record['evidence_report_ids'] == ['r1', 'r2']


@pytest.mark.parametrize('threats,normals,severity', [
    (4, 3, 'YUKSEK'), (4, 0, 'YUKSEK'), (3, 3, 'ORTA'),
    (1, 1, 'DUSUK'), (1, 0, 'DUSUK'), (2, 0, 'DUSUK'), (4, 20, 'DUSUK'),
])
def test_region_group_priority_uses_distinct_vehicles(threats, normals, severity):
    tracks = {str(i): track(str(i), [(0, 0), (0, 0), (0, 0)]) for i in range(threats + normals)}
    classes = {str(i): i < threats for i in range(threats + normals)}
    bundle = build(tracks, classes)
    baseline = compute_all_metrics(bundle)
    ExplainableScorer().score_all(list(bundle.nodes.values()))
    before = [n.to_dict() for n in bundle.nodes.values()]
    regions = RegionMerger().merge_high_interest_nodes(list(bundle.nodes.values()), baseline, bundle)
    assert len(regions) == 1
    region = regions[0]
    assert region.severity == severity
    assert region.threat_vehicle_count == threats
    assert region.interest_score == pytest.approx(sum(c['contribution'] for c in region.score_breakdown['components'].values()))
    assert region.interest_score == pytest.approx(region.graph_interest_score + region.intelligence_contribution)
    assert before == [n.to_dict() for n in bundle.nodes.values()]


def test_single_threat_cannot_be_high_even_with_high_structural_score():
    bundle = build({'a': track('a', [(0, 0)])}, {'a': True})
    node = next(iter(bundle.nodes.values()))
    node.interest_score = 0.9
    node.graph_interest_score = 0.8
    node.intelligence_contribution = 0.1
    node.score_breakdown = {'components': {
        'lift': {'raw': 10, 'normalized': 1, 'weight': 0.8, 'contribution': 0.8},
        'intelligence': {'raw': 1, 'normalized': 1, 'weight': 0.1, 'contribution': 0.1}}}
    region = RegionMerger().merge_high_interest_nodes([node], 0.1, bundle)[0]
    assert region.severity == 'DUSUK'
    assert region.interest_score == pytest.approx(sum(c['contribution'] for c in region.score_breakdown['components'].values()))


def test_adaptive_prior_uses_all_nodes_and_no_repeat_passages():
    bundle = build({'a': track('a', [(0, 0), (100, 0)]),
                    'b': track('b', [(0, 0), (200, 0)])}, {'a': True, 'b': False})
    compute_all_metrics(bundle)
    mean = sum(n.unique_vehicle_count for n in bundle.nodes.values()) / len(bundle.nodes)
    for node in bundle.nodes.values():
        assert node.effective_pseudo_count == pytest.approx(mean)
        assert node.sample_confidence == pytest.approx(node.unique_vehicle_count / (node.unique_vehicle_count + mean))
        assert node.smoothed_threat_rate == pytest.approx((node.threat_vehicle_count + mean * 0.5) / (node.total_vehicle_count + mean))


def test_stored_feedback_filters_stale_and_out_of_window():
    from app.graph.assessments import stored_vehicle_feedback
    vehicles = {'v': {'track_id': 'a', 'capture_time': '10:00', 'filtered': False},
                'stale': {'track_id': 'a', 'capture_time': '10:00'}}
    service = SimpleNamespace(state=SimpleNamespace(frames={'f': {}}, vehicles=vehicles),
        assessments={'f': {'vehicles': [{'vehicle_id': 'v', 'explanation': 'Kaynak açıklama'},
                                        {'vehicle_id': 'stale', 'explanation': 'Eski kayıt'}]}},
        decision_map=lambda: {'v': {'llm_reason': 'Karar gerekçesi', 'evidence_report_ids': ['r', 'r']}},
        vehicle_final=lambda vid, decisions: {'level': 'DUSUK', 'status': 'analist_karari', 'review': {'level': 'DUSUK'}})
    records = stored_vehicle_feedback(service, {'a'}, 590, 610)
    assert len(records) == 1
    assert records[0]['reason'] == 'Kaynak açıklama\nKarar gerekçesi'
    assert records[0]['evidence_report_ids'] == ['r']
    assert records[0]['level'] == 'DUSUK'
    assert stored_vehicle_feedback(service, {'a'}, 610, 620) == []


def test_summary_reuses_llm_cache_and_rejects_unknown_references(tmp_path):
    from app.graph.assessments import summarize_feedback
    calls = []
    class LLM:
        model_name = 'test'
        def with_structured_output(self, schema, **kwargs):
            return self
        def invoke(self, messages, **kwargs):
            calls.append(messages)
            return {'findings': [{'text': 'Kaynak gerekçesi', 'vehicle_ids': ['v']},
                                 {'text': 'Uydurma', 'vehicle_ids': ['unknown']}]}
    records = [{'vehicle_id': 'v', 'track_id': 'a', 'level': 'DUSUK', 'reason': 'Kaynak'}]
    path = tmp_path / 'summaries.json'
    result = summarize_feedback(records, LLM(), path, 1)
    assert result['method'] == 'llm'
    assert len(result['findings']) == 1
    assert summarize_feedback(records, LLM(), path, 1) == result
    assert len(calls) == 1
    changed = [{**records[0], 'reason': 'Yeni kaynak'}]
    summarize_feedback(changed, LLM(), path, 1)
    assert len(calls) == 2


def test_summary_failure_preserves_sources(tmp_path):
    from app.graph.assessments import summarize_feedback
    class Broken:
        def with_structured_output(self, *args, **kwargs):
            raise RuntimeError('offline')
    result = summarize_feedback([{'vehicle_id': 'v', 'track_id': 'a', 'level': 'DUSUK', 'reason': 'Normal'}],
                                Broken(), tmp_path / 'summaries.json', 1)
    assert result['method'] == 'stored_feedback_fallback'
    assert result['findings'][0]['vehicle_ids'] == ['v']


def test_legacy_feedback_requires_matching_engine():
    from app.graph.assessments import stored_vehicle_feedback
    svc = SimpleNamespace(state=SimpleNamespace(frames={'f': {}}, vehicles={
        'v': {'track_id': 'a', 'risk_level': 'ORTA'}}),
        assessments={'f': {'vehicles': [{'vehicle_id': 'v', 'engine_risk_level': 'ORTA', 'explanation': 'Eski format'}]}},
        decision_map=lambda: {}, vehicle_final=lambda *args: {'level': 'ORTA'})
    assert stored_vehicle_feedback(svc, {'a'})[0]['reason'] == 'Eski format'
    svc.state.vehicles['v']['risk_level'] = 'DUSUK'
    assert stored_vehicle_feedback(svc, {'a'}) == []


def track(tid, coordinates):
    return Track(tid, [TrackPoint(index * 10, *PROJECTION.unproject(x, y))
                       for index, (x, y) in enumerate(coordinates)])


def build(tracks, classes=None, radius=10):
    return SpatialGraphBuilder(SpatialGraphConfig(cluster_radius_m=radius)).build(
        tracks, classes if classes is not None else {tid: False for tid in tracks})


class GameService:
    def __init__(self, tracks, levels=None, reports=None):
        self.ds = SimpleNamespace(tracks=tracks, reports=reports or [])
        self.state = SimpleNamespace(vehicles={}, offframe_risk={
            tid: {"risk_level": (levels or {}).get(tid, "DUSUK")} for tid in tracks})
        self.agent = None

    def decision_map(self):
        return {}

    def vehicle_final(self, vid, decisions):
        return {"level": self.state.vehicles[vid]["risk_level"]}


def test_radius_snapping_and_input_order_are_stable():
    tracks = {"b": track("b", [(0, 0), (5, 0)]), "a": track("a", [(100, 0)])}
    one = build(tracks)
    two = build(dict(reversed(list(tracks.items()))))
    assert len(one.nodes) == 2
    assert [node.to_dict() for node in one.nodes.values()] == [node.to_dict() for node in two.nodes.values()]


def test_radius_index_handles_large_radius_and_high_latitude():
    projection = LocalProjection(70, 20)
    coordinates = [projection.unproject(0, 0), projection.unproject(90, 0)]
    tracks = {"a": Track("a", [TrackPoint(0, *coordinates[0])]),
              "b": Track("b", [TrackPoint(0, *coordinates[1])])}
    assert len(build(tracks, radius=100).nodes) == 1


def test_single_entity_interior_samples_are_not_junction_nodes():
    bundle = build({"a": track("a", [(0, 0), (100, 100), (200, 0), (300, 100)])})
    assert len(bundle.nodes) == 2
    assert len(bundle.edges) == 1


def test_intersection_between_samples_is_a_shared_node():
    tracks = {"a": track("a", [(-100, 0), (100, 0)]), "b": track("b", [(0, -100), (0, 100)])}
    bundle = build(tracks, {"a": True, "b": False})
    shared = [node for node in bundle.nodes.values() if node.unique_vehicle_count == 2]
    assert len(shared) == 1
    assert shared[0].threat_vehicle_count == shared[0].normal_vehicle_count == 1
    assert shared[0].incoming_edge_count == shared[0].outgoing_edge_count == 2


def test_repeated_visits_do_not_inflate_unique_vehicle_ratio():
    tracks = {"a": track("a", [(0, 0), (100, 0), (0, 0)]), "b": track("b", [(0, 0)])}
    bundle = build(tracks, {"a": True, "b": False})
    compute_all_metrics(bundle)
    node = next(node for node in bundle.nodes.values() if node.unique_vehicle_count == 2)
    assert node.passage_count == 3
    assert node.total_vehicle_count == 2
    assert node.raw_threat_ratio == 0.5
    assert node.threat_lift == 1


def test_global_baseline_ignores_empty_or_unclassified_tracks():
    tracks = {"a": track("a", [(0, 0)]), "b": track("b", [(100, 0)]), "empty": Track("empty", [])}
    bundle = build(tracks, {"a": True, "b": False, "empty": True, "missing": True})
    assert compute_all_metrics(bundle) == 0.5


def test_raw_lift_matches_expected_ratio_and_zero_baseline_is_safe():
    assert compute_threat_lift(0.15, 0.03) == pytest.approx(5)
    assert compute_threat_lift(0, 0) == 0


def test_identical_subgraphs_have_no_centrality_gap():
    tracks = {"a": track("a", [(0, 0), (100, 0), (200, 0)]),
              "b": track("b", [(0, 0), (100, 0), (200, 0)])}
    bundle = build(tracks, {"a": True, "b": False})
    compute_all_metrics(bundle)
    assert all(node.threat_normal_centrality_gap == 0 for node in bundle.nodes.values())
    assert all(0 <= node.degree_centrality <= 1 for node in bundle.nodes.values())


def test_threat_only_middle_node_has_positive_gap():
    tracks = {"a": track("a", [(0, 0), (100, 0), (200, 0)]),
              "b": track("b", [(500, 0), (600, 0)]),
              "c": track("c", [(100, -100), (100, 100)])}
    bundle = build(tracks, {"a": True, "b": False, "c": True})
    compute_all_metrics(bundle)
    middle = next(node for node in bundle.nodes.values() if node.incoming_edge_count and node.outgoing_edge_count)
    assert middle.threat_normal_centrality_gap > 0


def test_small_sample_is_smoothed_and_confidence_is_not_probability():
    assert compute_smoothed_threat_rate(1, 2, 0.03) == pytest.approx(1.6 / 22)
    assert compute_sample_confidence(2) == pytest.approx(2 / 12)
    assert compute_sample_confidence(0) == 0


def test_score_breakdown_sums_and_observation_confidence_is_separate():
    node = SpatialNode("a", 0, 0, total_vehicle_count=2, threat_vehicle_count=1,
                       unique_vehicle_count=2, global_threat_rate=0.03, raw_threat_ratio=0.5,
                       smoothed_threat_rate=1.6 / 22, threat_lift=0.5 / 0.03,
                       threat_normal_centrality_gap=0.4, threat_graph_centrality=1,
                       threat_trajectory_importance=1, sample_confidence=2 / 12)
    ExplainableScorer().score_node(node)
    original_score = node.interest_score
    assert node.score_breakdown['observation_confidence'] == pytest.approx(2 / 12)
    node.sample_confidence = 1
    ExplainableScorer().score_node(node)
    assert node.interest_score == original_score
    assert node.interest_score == pytest.approx(sum(item["contribution"] for item in node.score_breakdown["components"].values()))
    assert node.recommendation.strip()


def test_uniform_class_rate_and_reports_alone_do_not_create_anomaly():
    node = SpatialNode("a", 0, 0, threat_vehicle_count=20, global_threat_rate=0.5,
                       smoothed_threat_rate=0.5, threat_lift=1, sample_confidence=1,
                       threat_graph_centrality=0.5, related_intelligence_count=100, intelligence_confidence=1)
    ExplainableScorer().score_node(node)
    assert node.interest_score == 0


def test_all_threat_interval_does_not_infer_anomaly_without_normal_comparator():
    node = SpatialNode("a", 0, 0, threat_vehicle_count=20, global_threat_rate=1,
                       smoothed_threat_rate=1, threat_lift=1, sample_confidence=1,
                       threat_graph_centrality=1, threat_normal_centrality_gap=1)
    ExplainableScorer().score_node(node)
    assert node.interest_score == 0


def test_score_is_independent_of_unrelated_nodes():
    node = SpatialNode("a", 0, 0, threat_vehicle_count=5, global_threat_rate=0.1,
                       smoothed_threat_rate=0.5, threat_graph_centrality=0.4,
                       threat_normal_centrality_gap=0.2, sample_confidence=1)
    scorer = ExplainableScorer()
    scorer.score_node(node)
    expected = node.interest_score
    scorer.score_all([node, SpatialNode("b", 1, 1, threat_lift=1000)])
    assert node.interest_score == expected


def test_region_merging_uses_union_not_sum_or_max():
    tracks = {"a": track("a", [(0, 0), (100, 0)]), "b": track("b", [(100, 0)]),
              "c": track("c", [(0, 0)])}
    bundle = build(tracks, {"a": True, "b": True, "c": False})
    compute_all_metrics(bundle)
    ExplainableScorer().score_all(list(bundle.nodes.values()))
    regions = RegionMerger().merge_high_interest_nodes(list(bundle.nodes.values()), 2 / 3, bundle)
    assert len(regions) == 1
    assert regions[0].total_vehicle_count == 3
    assert regions[0].unique_threat_trajectories == 2
    assert regions[0].local_threat_rate == pytest.approx(2 / 3)
    assert RegionMerger().merge_high_interest_nodes([], 0, bundle) == []


def test_time_window_clips_segments_without_extrapolating():
    tracks = {"a": track("a", [(0, 0), (100, 0)])}
    clipped = clip_tracks(tracks, 2, 8)
    assert [point.t for point in clipped["a"].points] == [2, 8]
    assert PROJECTION.project(clipped["a"].points[0].lat, clipped["a"].points[0].lon)[0] == pytest.approx(20)
    assert clip_tracks(tracks, 11, 20) == {}
    with pytest.raises(ValueError):
        clip_tracks(tracks, 20, 10)


def test_intelligence_matching_keeps_unknown_confidence_and_unmatched(tmp_path):
    bundle = build({"a": track("a", [(0, 0)])})
    processor = IntelligenceProcessor(cache_path=tmp_path / "intel.json")
    matched, unmatched = processor.process_and_corroborate([
        {"id": "r1", "text": "0.0N 0.0E arac goruldu", "source": "official"},
        {"id": "r2", "text": "Konumu bilinmiyor"},
        {"id": "r3", "text": "20.0N 20.0E"},
    ], bundle)
    assert [item.report_id for item in matched] == ["r1"]
    assert matched[0].confidence is None
    assert [item.unmatched_reason for item in unmatched] == ["no_explicit_coordinates", "outside_node_radius"]


def test_unknown_report_time_is_preserved_without_matching_in_selected_window(tmp_path):
    main = GameService({"a": track("a", [(0, 0), (100, 0)])}, reports=[
        {"id": "r1", "text": "0.0N 0.0E", "time": "invalid"},
        {"id": "r2", "text": "0.0N 0.0E"},
    ])
    result = GraphAnalysisService(main, output_dir=tmp_path, enable_llm=False).run_analysis(start_min=0, end_min=10)
    assert result.matched_intelligence_count == 0
    assert [item.unmatched_reason for item in result.unmatched_intelligence] == ["unknown_time", "unknown_time"]


def test_optional_self_loops_do_not_break_centrality_normalization():
    tracks = {"a": track("a", [(0, 0), (0, 0), (100, 0)])}
    bundle = SpatialGraphBuilder(SpatialGraphConfig(cluster_radius_m=10, filter_self_loops=False)).build(tracks, {"a": True})
    compute_all_metrics(bundle)
    assert all(0 <= node.degree_centrality <= 1 for node in bundle.nodes.values())


def test_llm_hallucinated_coordinates_location_and_ids_are_removed(tmp_path):
    class FakeLLM:
        def with_structured_output(self, schema, **kwargs):
            return self

        def invoke(self, messages, **kwargs):
            assert kwargs["timeout"] == 30
            return StructuredIntelligence(report_id="invented", location_name="Invented zone", lat=42, lon=22,
                                          description="Summary", event_type="observation", confidence="high")

    processor = IntelligenceProcessor(llm=FakeLLM(), cache_path=tmp_path / "intel.json")
    result = processor.extract_structured({"id": "r1", "text": "Vehicle observed", "source": "third_party"})
    assert result.report_id == "r1"
    assert result.lat is result.lon is result.location_name is result.confidence is None
    assert result.extraction_method == "llm"


def test_llm_failure_does_not_retry_every_report_or_cache_fallback(tmp_path):
    class FailingLLM:
        calls = 0

        def with_structured_output(self, schema, **kwargs):
            return self

        def invoke(self, messages, **kwargs):
            self.calls += 1
            raise RuntimeError("Unavailable")

    llm = FailingLLM()
    processor = IntelligenceProcessor(llm=llm, cache_path=tmp_path / "intel.json")
    for rid in ("a", "b"):
        item = processor.extract_structured({"id": rid, "text": "Location unknown"})
        assert item.extraction_method == "deterministic_fallback"
    assert llm.calls == 1
    assert processor.cache == {}


def test_changed_report_text_does_not_reuse_old_extraction(tmp_path):
    processor = IntelligenceProcessor(cache_path=tmp_path / "intel.json")
    first = processor.extract_structured({"id": "r1", "text": "0.0N 0.0E"})
    second = processor.extract_structured({"id": "r1", "text": "Location unknown"})
    assert first.lat == 0
    assert second.lat is None


@pytest.mark.parametrize("kwargs", [{"lat": 200, "lon": 0}, {"lat": 10}, {"lat": float('nan'), "lon": 0}])
def test_invalid_coordinates_are_rejected(kwargs):
    with pytest.raises(ValidationError):
        StructuredIntelligence(report_id="r", description="x", event_type="observation", **kwargs)


def test_cache_updates_on_label_data_config_and_window_changes(tmp_path):
    main = GameService({"a": track("a", [(0, 0), (100, 0)])})
    svc = GraphAnalysisService(main, output_dir=tmp_path, enable_llm=False)
    first = svc.run_analysis()
    assert svc.run_analysis() is first
    main.state.offframe_risk["a"]["risk_level"] = "YUKSEK"
    second = svc.run_analysis()
    assert second.global_threat_rate == 1
    assert second.data_revision != first.data_revision
    assert svc.run_analysis(start_min=2, end_min=8).data_revision != second.data_revision
    config = replace(svc.config, spatial=replace(svc.config.spatial, cluster_radius_m=200))
    assert svc.run_analysis(custom_config=config).total_nodes == 1
    main.ds.tracks["a"].points[-1].lon += 0.01
    assert svc.run_analysis().data_revision != second.data_revision


def test_unknown_labels_are_reported_not_assumed_normal(tmp_path):
    main = GameService({"a": track("a", [(0, 0)])})
    main.state.offframe_risk.clear()
    result = GraphAnalysisService(main, output_dir=tmp_path, enable_llm=False).run_analysis()
    assert result.total_trajectories == 0
    assert result.unclassified_trajectory_count == 1


def test_recompute_options_are_applied_and_invalid_requests_fail(tmp_path):
    main = GameService({"a": track("a", [(0, 0), (100, 0)])})
    svc = GraphAnalysisService(main, output_dir=tmp_path, enable_llm=False)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_graph_service] = lambda: svc
    client = TestClient(app)
    base = "/api/graph-analysis"
    assert client.get(base).json()["total_nodes"] == 2
    response = client.post(base + "/recompute", json={"cluster_radius_m": 200, "min_observation_threshold": 2})
    assert response.status_code == 200
    assert response.json()["total_nodes"] == 1
    assert response.json()["regions"][0]["confidence"] == 0.5
    assert client.get(base + "?start_time=00:08&end_time=00:02").status_code == 422
    assert client.get(base + "?start_time=99:00").status_code == 422
    assert client.post(base + "/recompute", json={"cluster_radius_m": -1}).status_code == 422
    assert client.post(base + "/recompute", json={"config": {"weights": {"lift_weight": 5}}}).status_code == 422
    assert client.get(base + "/regions/missing").status_code == 404


def test_configuration_rejects_invalid_weights_and_zero_radius():
    with pytest.raises(ValueError):
        ScoreWeightsConfig(lift_weight=-1)
    with pytest.raises(ValueError):
        SpatialGraphConfig(cluster_radius_m=0)

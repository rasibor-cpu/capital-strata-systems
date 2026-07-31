"""DIP-006 enterprise readiness and certification validation tests."""

from __future__ import annotations

import ast
import json
import time
import tracemalloc
from pathlib import Path

import pytest

from backend.intelligence.decision_analytics import DecisionAnalyticsEngine
from backend.intelligence.edge_intelligence import (
    EdgeDiscoveryEngine,
    EdgeEvaluator,
    EdgeRegistry,
    EvidenceThresholdPolicy,
)
from backend.intelligence.enterprise_intelligence import (
    CapitalIntelligenceEngine,
    EnterpriseReportBuilder,
    ExecutiveIntelligenceEngine,
)
from backend.intelligence.trade_dna import (
    CanonicalCloseEventError,
    DurableCaptureStore,
    TradeDNACaptureService,
    TradeDNAValidationError,
    build_canonical_close_event,
    compute_content_hash,
    deserialize_trade_dna,
)


GENERATED_AT = "2026-07-31T00:00:00+00:00"


def _event(
    trade_id: str,
    *,
    pnl: float,
    strategy: str = "alpha",
    symbol: str = "EUR_USD",
    opened_at: str = "2026-07-01T10:00:00+00:00",
    regime: str = "trend",
) -> object:
    return build_canonical_close_event(
        trade_id=trade_id,
        symbol=symbol,
        side="buy",
        broker_name="css_paper",
        broker_mode="paper",
        entry_price=1.10,
        exit_price=1.12,
        quantity=1000.0,
        filled_quantity=1000.0,
        opened_at=opened_at,
        closed_at=opened_at.replace("10:00:00", "12:00:00"),
        realized_pnl=pnl,
        session_id="S-DIP6",
        order_type="market",
        strategy_id=strategy,
        market_regime=regime,
        exit_reason="take_profit" if pnl >= 0 else "stop",
        scaled_notional=1000.0,
        requested_notional=1000.0,
        fill_kind="paper_synthetic_full_request_qty",
        gate_final="ALLOW",
        gate_reason="historical_close_evidence",
        source_event_ids=(f"warehouse:{trade_id}",),
    )


def _events() -> list[object]:
    return [
        _event("DIP6-T1", pnl=30.0, strategy="alpha", opened_at="2026-07-01T10:00:00+00:00"),
        _event("DIP6-T2", pnl=-10.0, strategy="alpha", opened_at="2026-07-02T10:00:00+00:00", regime="range"),
        _event("DIP6-T3", pnl=20.0, strategy="beta", symbol="GBP_USD", opened_at="2026-07-03T10:00:00+00:00"),
        _event("DIP6-T4", pnl=15.0, strategy="beta", symbol="GBP_USD", opened_at="2026-07-04T10:00:00+00:00"),
        _event("DIP6-T5", pnl=5.0, strategy="alpha", opened_at="2026-07-05T10:00:00+00:00"),
    ]


def _capture(events: list[object], root: Path) -> tuple[list[object], list[object], DurableCaptureStore]:
    store = DurableCaptureStore(root)
    service = TradeDNACaptureService(store)
    for event in events:
        service.capture_close_event(event)
    records = sorted(store.list_dna(), key=lambda record: record.identity.trade_id)
    metrics = sorted(store.list_derived(), key=lambda metric: metric.trade_id)
    return records, metrics, store


def _edge_policy() -> EvidenceThresholdPolicy:
    return EvidenceThresholdPolicy(
        observational_min_trades=1,
        supported_min_trades=2,
        observational_min_independent=1,
        supported_min_independent=2,
        min_data_completeness=0.50,
        supported_data_completeness=0.50,
        observational_min_confidence=0.10,
        supported_min_confidence=0.20,
        max_supported_outlier_impact=0.90,
    )


def _enterprise_report(records: list[object], metrics: list[object], edges: tuple[object, ...]):
    capital = CapitalIntelligenceEngine(
        dna_records=records,
        derived_metrics=metrics,
        generated_at=GENERATED_AT,
    ).build_report()
    executive = ExecutiveIntelligenceEngine(
        dna_records=records,
        derived_metrics=metrics,
        edge_records=edges,
        capital_report=capital,
        generated_at=GENERATED_AT,
    ).build_summary()
    return EnterpriseReportBuilder(
        dna_records=records,
        derived_metrics=metrics,
        edge_records=edges,
        capital_report=capital,
        executive_summary=executive,
        generated_at=GENERATED_AT,
    ).build_report()


def test_dip_packages_do_not_import_or_invoke_execution_authority():
    roots = [
        Path("backend/intelligence/trade_dna"),
        Path("backend/intelligence/decision_analytics"),
        Path("backend/intelligence/edge_intelligence"),
        Path("backend/intelligence/enterprise_intelligence"),
    ]
    forbidden_import_tokens = (
        "execution_gate",
        "risk_governor",
        "anti_bleed",
        "antibleed",
        "broker_adapter",
        "order_router",
        "position_sizer",
        "volatility_position_sizer",
        "runtime_control",
        "mission_control",
    )
    forbidden_call_names = {
        "ExecutionGate",
        "RiskGovernor",
        "AntiBleed",
        "AntiBleedGuard",
        "BrokerAdapter",
        "PositionSizer",
        "VolatilityPositionSizer",
        "place_order",
        "route_order",
        "submit_order",
        "authorize_trade",
        "start_runtime",
        "stop_runtime",
    }
    violations: list[str] = []
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports = [node.module]
                else:
                    imports = []
                for imported in imports:
                    if any(token in imported.lower() for token in forbidden_import_tokens):
                        violations.append(f"{path}:{imported}")
                if isinstance(node, ast.Call):
                    func = node.func
                    name = ""
                    if isinstance(func, ast.Name):
                        name = func.id
                    elif isinstance(func, ast.Attribute):
                        name = func.attr
                    if name in forbidden_call_names:
                        violations.append(f"{path}:call:{name}")
    assert violations == []


def test_end_to_end_lineage_and_replay_determinism(tmp_path: Path):
    records_a, metrics_a, store_a = _capture(_events(), tmp_path / "a")
    records_b, metrics_b, store_b = _capture(list(reversed(_events())), tmp_path / "b")
    assert [record.content_hash for record in records_a] == [record.content_hash for record in records_b]
    assert [metric.to_dict() for metric in metrics_a] == [metric.to_dict() for metric in metrics_b]
    assert [store_a.get_outbox(event.trade_id)["status"] for event in _events()] == ["COMPLETE"] * 5
    assert [store_b.get_outbox(event.trade_id)["status"] for event in _events()] == ["COMPLETE"] * 5

    analytics_a = DecisionAnalyticsEngine(
        dna_records=records_a,
        derived_metrics=metrics_a,
        generated_at=GENERATED_AT,
    ).full_report()
    analytics_b = DecisionAnalyticsEngine(
        dna_records=list(reversed(records_b)),
        derived_metrics=list(reversed(metrics_b)),
        generated_at=GENERATED_AT,
    ).full_report()
    assert analytics_a == analytics_b
    assert analytics_a["execution_allowed"] is False

    candidates_a = EdgeDiscoveryEngine(dna_records=records_a, derived_metrics=metrics_a).discover()
    candidates_b = EdgeDiscoveryEngine(dna_records=list(reversed(records_b)), derived_metrics=list(reversed(metrics_b))).discover()
    evaluator_a = EdgeEvaluator(dna_records=records_a, derived_metrics=metrics_a, threshold_policy=_edge_policy())
    evaluator_b = EdgeEvaluator(dna_records=records_b, derived_metrics=metrics_b, threshold_policy=_edge_policy())
    registry_a = EdgeRegistry(tmp_path / "edges-a.json")
    registry_b = EdgeRegistry(tmp_path / "edges-b.json")
    registry_a.upsert_candidates(candidates=candidates_a, evaluator=evaluator_a, recalculated_at=GENERATED_AT)
    registry_b.upsert_candidates(candidates=list(reversed(candidates_b)), evaluator=evaluator_b, recalculated_at=GENERATED_AT)
    assert registry_a.registry_hash() == registry_b.registry_hash()

    report_a = _enterprise_report(records_a, metrics_a, registry_a.list_edges())
    report_b = _enterprise_report(list(reversed(records_b)), list(reversed(metrics_b)), tuple(reversed(registry_b.list_edges())))
    assert report_a.to_dict() == report_b.to_dict()
    assert report_a.report_hash == report_b.report_hash
    assert report_a.evidence.trade_ids == tuple(event.trade_id for event in _events())
    assert report_a.evidence.dna_ids == tuple(sorted(record.identity.dna_id for record in records_a))
    assert report_a.sections["decision_intelligence_summary"]["capital_report_hash"]


def test_report_hash_excludes_caller_timestamp_under_full_lineage(tmp_path: Path):
    records, metrics, _store = _capture(_events(), tmp_path / "capture")
    candidates = EdgeDiscoveryEngine(dna_records=records, derived_metrics=metrics).discover()
    evaluator = EdgeEvaluator(dna_records=records, derived_metrics=metrics, threshold_policy=_edge_policy())
    registry = EdgeRegistry()
    registry.upsert_candidates(candidates=candidates, evaluator=evaluator, recalculated_at=GENERATED_AT)
    report_a = _enterprise_report(records, metrics, registry.list_edges())

    capital_b = CapitalIntelligenceEngine(
        dna_records=records,
        derived_metrics=metrics,
        generated_at="2030-01-01T00:00:00+00:00",
    ).build_report()
    executive_b = ExecutiveIntelligenceEngine(
        dna_records=records,
        derived_metrics=metrics,
        edge_records=registry.list_edges(),
        capital_report=capital_b,
        generated_at="2030-01-01T00:00:00+00:00",
    ).build_summary()
    report_b = EnterpriseReportBuilder(
        dna_records=records,
        derived_metrics=metrics,
        edge_records=registry.list_edges(),
        capital_report=capital_b,
        executive_summary=executive_b,
        generated_at="2030-01-01T00:00:00+00:00",
    ).build_report()
    assert report_a.report_hash == report_b.report_hash
    assert report_a.to_dict(include_caller_metadata=False) == report_b.to_dict(include_caller_metadata=False)
    assert report_a.generated_at != report_b.generated_at


def test_material_failure_modes_are_fail_closed_or_advisory_safe(tmp_path: Path):
    event = _events()[0]
    store = DurableCaptureStore(tmp_path / "capture")
    service = TradeDNACaptureService(store)
    service.capture_close_event(event)
    with pytest.raises(CanonicalCloseEventError):
        service.capture_close_event(
            _event(
                event.trade_id,
                pnl=999.0,
                strategy="alpha",
                opened_at="2026-07-01T10:00:00+00:00",
            )
        )
    assert len(store.list_dna()) == 1
    assert store.get_outbox(event.trade_id)["status"] == "CONFLICT"
    assert store.list_conflicts()

    corrupted = tmp_path / "corrupted_registry.json"
    corrupted.write_text("{not-json", encoding="utf-8")
    registry = EdgeRegistry(corrupted)
    assert registry.list_edges() == ()
    assert registry.registry_hash()

    with pytest.raises(Exception):
        deserialize_trade_dna({"schema_version": "css.trade_dna.v999", "identity": {}})

    records, metrics, _store = _capture(_events(), tmp_path / "healthy")
    candidates = EdgeDiscoveryEngine(dna_records=records, derived_metrics=metrics).discover()
    evaluator = EdgeEvaluator(dna_records=records, derived_metrics=metrics, threshold_policy=_edge_policy())
    registry = EdgeRegistry()
    registry.upsert_candidates(candidates=candidates, evaluator=evaluator, recalculated_at=GENERATED_AT)
    first = registry.list_edges()[0]
    with pytest.raises(ValueError):
        registry.link_edges(edge_id=first.edge_id, supporting_edges=("EDGE-999999",))

    empty = CapitalIntelligenceEngine(dna_records=[], derived_metrics=[], generated_at=GENERATED_AT).build_report()
    assert empty.metrics["trade_count"] == 0
    assert empty.metrics["capital_deployment"] == 0.0
    assert empty.advisory_flags["execution_allowed"] is False


def test_offline_benchmark_signature_is_deterministic(tmp_path: Path):
    tracemalloc.start()
    start = time.perf_counter()
    records, metrics, _store = _capture(_events() * 2, tmp_path / "bench")
    analytics = DecisionAnalyticsEngine(
        dna_records=records,
        derived_metrics=metrics,
        generated_at=GENERATED_AT,
    ).full_report()
    candidates = EdgeDiscoveryEngine(dna_records=records, derived_metrics=metrics).discover()
    evaluator = EdgeEvaluator(dna_records=records, derived_metrics=metrics, threshold_policy=_edge_policy())
    registry = EdgeRegistry(tmp_path / "bench_edges.json")
    registry.upsert_candidates(candidates=candidates, evaluator=evaluator, recalculated_at=GENERATED_AT)
    report = _enterprise_report(records, metrics, registry.list_edges())
    elapsed = time.perf_counter() - start
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    signature = compute_content_hash(
        {
            "dataset_size": len(records),
            "trade_dna_hashes": [record.content_hash for record in records],
            "analytics_sections": analytics["sections"],
            "edge_registry_hash": registry.registry_hash(),
            "enterprise_report_hash": report.report_hash,
        }
    )
    assert len(records) == 5
    assert elapsed >= 0.0
    assert signature == compute_content_hash(
        {
            "dataset_size": len(records),
            "trade_dna_hashes": [record.content_hash for record in records],
            "analytics_sections": analytics["sections"],
            "edge_registry_hash": registry.registry_hash(),
            "enterprise_report_hash": report.report_hash,
        }
    )
    assert len(signature) == 64
    assert json.dumps(report.to_dict(include_caller_metadata=False), sort_keys=True)
    print(
        "DIP006_BENCHMARK "
        f"dataset_size={len(records)} "
        f"elapsed_seconds={elapsed:.6f} "
        f"peak_bytes={peak} "
        f"deterministic_hash={signature}"
    )


def test_certification_manifest_integrity():
    path = Path("docs/governance/DIP_006_CERTIFICATION_MANIFEST.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest_hash = manifest["manifest_hash"]
    canonical = dict(manifest)
    canonical.pop("manifest_hash", None)
    recomputed = compute_content_hash(canonical)

    assert manifest["schema_version"] == "css.dip006.certification_manifest.v1"
    assert manifest["branch"] == "css-v1.0.1-maintenance"
    assert manifest["assessed_head"] == "6cfa8862c42ef118a249c7a47a63386c60bd9f77"
    assert manifest_hash == recomputed
    assert "generated_at" not in manifest
    assert "created_at" not in manifest
    assert manifest["readiness_classifications"]["decision_intelligence_library"] == "READY_WITH_LIMITATIONS"
    assert manifest["readiness_classifications"]["mission_control_integration"] == "NOT_READY"
    assert manifest["readiness_classifications"]["live_trading_integration"] == "NOT_READY"
    assert manifest["readiness_classifications"]["external_commercial_deployment"] == "NOT_READY"
    assert sum(item["test_function_count"] for item in manifest["blocked_tests"]) == 78
    assert any("ReportLab is not installed" in item for item in manifest["known_limitations"])
    assert any("formal third-party ISO certification" in item for item in manifest["known_limitations"])
    assert any("live trading" in item for item in manifest["known_limitations"])
    assert any("commercial deployment" in item for item in manifest["known_limitations"])

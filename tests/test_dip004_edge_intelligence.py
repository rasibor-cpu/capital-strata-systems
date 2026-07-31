"""DIP-004 Enterprise Edge Intelligence deterministic tests."""

from __future__ import annotations

from pathlib import Path

from backend.intelligence.decision_analytics import DecisionAnalyticsEngine
from backend.intelligence.edge_intelligence import (
    EdgeDefinition,
    EdgeDiscoveryEngine,
    EdgeEvaluator,
    EdgeRegistry,
    EdgeReportBuilder,
    EvidenceThresholdPolicy,
)
from backend.intelligence.trade_dna import (
    DerivedTradeMetrics,
    ExecutionFacts,
    MarketFacts,
    OutcomeFacts,
    StrategyFacts,
    TimingFacts,
    TradeDNARecord,
    TradeIdentityFacts,
    VolatilityFacts,
)


GENERATED_AT = "2026-07-30T15:00:00+00:00"


def _dna(
    trade_id: str,
    *,
    profit: float,
    strategy: str = "alpha",
    regime: str = "trend",
    signal: str = "breakout+volume",
    opened_at: str = "2026-07-30T10:00:00+00:00",
    confluence: float = 0.8,
    vol_regime: str = "medium",
    exit_reason: str = "take_profit",
    symbol: str = "EUR_USD",
) -> tuple[TradeDNARecord, DerivedTradeMetrics]:
    record = TradeDNARecord(
        identity=TradeIdentityFacts(
            trade_id=trade_id,
            dna_id=f"dna-{trade_id}",
            instrument=symbol,
            asset_class="FX",
            side="BUY",
        ),
        execution=ExecutionFacts(
            entry_price=1.10,
            exit_price=1.12,
            requested_notional=1000.0,
            scaled_notional=1000.0,
        ),
        market=MarketFacts(
            symbol=symbol,
            session="NY",
            market_regime=regime,
        ),
        strategy=StrategyFacts(
            strategy_id=strategy,
            signal_id=signal,
            confluence_score=confluence,
        ),
        volatility=VolatilityFacts(vol_regime=vol_regime),
        timing=TimingFacts(
            opened_at=opened_at,
            closed_at=opened_at.replace("10:00:00", "12:00:00"),
        ),
        outcome=OutcomeFacts(
            status="closed",
            exit_reason=exit_reason,
            win_loss="win" if profit > 0 else "loss" if profit < 0 else "flat",
        ),
    ).with_content_hash()
    metrics = DerivedTradeMetrics(
        dna_id=record.identity.dna_id,
        trade_id=trade_id,
        profit=profit,
        return_pct=profit / 1000.0,
        holding_period_seconds=7200.0,
        expectancy_contribution=profit,
        edge_contribution=profit,
    )
    return record, metrics


def _sample_population() -> tuple[list[TradeDNARecord], list[DerivedTradeMetrics]]:
    rows = [
        _dna("T1", profit=5.0, opened_at="2026-07-01T10:00:00+00:00", regime="trend"),
        _dna("T2", profit=5.0, opened_at="2026-07-02T10:00:00+00:00", regime="range"),
        _dna("T3", profit=5.0, opened_at="2026-07-03T11:00:00+00:00", regime="trend", symbol="GBP_USD"),
        _dna("T4", profit=5.0, opened_at="2026-07-04T11:00:00+00:00", regime="range", symbol="GBP_USD"),
        _dna("T5", profit=5.0, opened_at="2026-07-05T12:00:00+00:00", regime="trend"),
        _dna("T6", profit=5.0, opened_at="2026-07-06T12:00:00+00:00", regime="range"),
        _dna("T7", profit=-2.0, strategy="beta", opened_at="2026-07-07T10:00:00+00:00", regime="trend"),
        _dna("T8", profit=-3.0, strategy="beta", opened_at="2026-07-08T10:00:00+00:00", regime="range"),
        _dna("T9", profit=1.0, strategy="beta", opened_at="2026-07-09T10:00:00+00:00", regime="trend"),
    ]
    return [row[0] for row in rows], [row[1] for row in rows]


def _expanded_population() -> tuple[list[TradeDNARecord], list[DerivedTradeMetrics]]:
    records, metrics = _sample_population()
    rows = [
        _dna("T10", profit=4.0, strategy="gamma", signal="pullback", opened_at="2026-07-10T13:00:00+00:00"),
        _dna("T11", profit=4.0, strategy="gamma", signal="pullback", opened_at="2026-07-11T13:00:00+00:00"),
    ]
    return records + [row[0] for row in rows], metrics + [row[1] for row in rows]


def _policy() -> EvidenceThresholdPolicy:
    return EvidenceThresholdPolicy(
        observational_min_trades=2,
        supported_min_trades=5,
        observational_min_independent=2,
        supported_min_independent=5,
        min_data_completeness=0.70,
        supported_data_completeness=0.80,
        observational_min_confidence=0.20,
        supported_min_confidence=0.50,
        max_supported_outlier_impact=0.40,
    )


def _build_registry(path: Path | None = None) -> EdgeRegistry:
    records, metrics = _sample_population()
    candidates = EdgeDiscoveryEngine(dna_records=records, derived_metrics=metrics).discover()
    evaluator = EdgeEvaluator(dna_records=records, derived_metrics=metrics, threshold_policy=_policy())
    registry = EdgeRegistry(path)
    registry.upsert_candidates(candidates=candidates, evaluator=evaluator, recalculated_at=GENERATED_AT)
    return registry


def test_identical_edge_definition_produces_identical_definition_hash():
    first = EdgeDefinition(
        category="strategy",
        name="Strategy: alpha",
        description="Alpha strategy edge.",
        cohort_key="alpha",
        cohort_definition={"value": "alpha", "category": "strategy"},
        normalized_predicates={"operator": "equals", "value": "alpha", "field_family": "strategy"},
    )
    second = EdgeDefinition(
        category="STRATEGY",
        name="Different display name does not own identity",
        description="Different description does not own identity.",
        cohort_key="ALPHA",
        cohort_definition={"category": "strategy", "value": "alpha"},
        normalized_predicates={"field_family": "strategy", "value": "alpha", "operator": "equals"},
    )
    assert first.definition_hash == second.definition_hash
    assert first.definition_hash.startswith("edge-definition:")


def test_edge_discovery_is_deterministic():
    records, metrics = _sample_population()
    first = EdgeDiscoveryEngine(dna_records=records, derived_metrics=metrics).discover()
    second = EdgeDiscoveryEngine(dna_records=list(reversed(records)), derived_metrics=list(reversed(metrics))).discover()
    assert [c.definition_hash for c in first] == [c.definition_hash for c in second]
    assert any(c.category == "strategy" and c.cohort_key == "ALPHA" for c in first)
    assert any(c.category == "holding_period" for c in first)
    assert all(c.trade_ids for c in first)


def test_edge_registry_assigns_permanent_ids_and_persists(tmp_path: Path):
    path = tmp_path / "edge_registry.json"
    registry = _build_registry(path)
    edges = registry.list_edges()
    assert edges[0].edge_id == "EDGE-000001"
    assert all(edge.permanent_edge_id == edge.edge_id for edge in edges)
    reloaded = EdgeRegistry(path)
    assert [edge.edge_id for edge in reloaded.list_edges()] == [edge.edge_id for edge in edges]
    assert reloaded.registry_hash() == registry.registry_hash()


def test_shuffled_candidate_order_produces_identical_id_assignment(tmp_path: Path):
    records, metrics = _sample_population()
    candidates = list(EdgeDiscoveryEngine(dna_records=records, derived_metrics=metrics).discover())
    evaluator = EdgeEvaluator(dna_records=records, derived_metrics=metrics, threshold_policy=_policy())
    a = EdgeRegistry(tmp_path / "a.json")
    b = EdgeRegistry(tmp_path / "b.json")
    a.upsert_candidates(candidates=candidates, evaluator=evaluator, recalculated_at=GENERATED_AT)
    b.upsert_candidates(candidates=list(reversed(candidates)), evaluator=evaluator, recalculated_at=GENERATED_AT)
    assert [(e.definition_hash, e.edge_id) for e in a.list_edges()] == [
        (e.definition_hash, e.edge_id) for e in b.list_edges()
    ]


def test_existing_edge_ids_remain_stable_when_new_edges_are_added(tmp_path: Path):
    records, metrics = _sample_population()
    candidates = [
        c
        for c in EdgeDiscoveryEngine(dna_records=records, derived_metrics=metrics).discover()
        if c.category == "strategy" and c.cohort_key == "ALPHA"
    ]
    evaluator = EdgeEvaluator(dna_records=records, derived_metrics=metrics, threshold_policy=_policy())
    registry = EdgeRegistry(tmp_path / "registry.json")
    registry.upsert_candidates(candidates=candidates, evaluator=evaluator, recalculated_at=GENERATED_AT)
    alpha_id = registry.list_edges()[0].edge_id

    expanded_records, expanded_metrics = _expanded_population()
    expanded_candidates = EdgeDiscoveryEngine(
        dna_records=expanded_records,
        derived_metrics=expanded_metrics,
    ).discover()
    expanded_evaluator = EdgeEvaluator(
        dna_records=expanded_records,
        derived_metrics=expanded_metrics,
        threshold_policy=_policy(),
    )
    registry.upsert_candidates(
        candidates=expanded_candidates,
        evaluator=expanded_evaluator,
        recalculated_at="2026-07-31T00:00:00+00:00",
    )
    alpha = next(edge for edge in registry.list_edges() if edge.category == "strategy" and edge.name.endswith("ALPHA"))
    assert alpha.edge_id == alpha_id


def test_lifecycle_version_history_and_relationships(tmp_path: Path):
    path = tmp_path / "edge_registry.json"
    registry = _build_registry(path)
    first = registry.list_edges()[0]
    linked = registry.link_edges(
        edge_id=first.edge_id,
        supporting_edges=("EDGE-000002",),
        conflicting_edges=("EDGE-000003",),
        independent_edges=("EDGE-000004",),
    )
    assert linked.supporting_edges == ("EDGE-000002",)
    assert linked.conflicting_edges == ("EDGE-000003",)
    assert linked.independent_edges == ("EDGE-000004",)

    records, metrics = _sample_population()
    evaluator = EdgeEvaluator(dna_records=records, derived_metrics=metrics, threshold_policy=_policy())
    candidates = EdgeDiscoveryEngine(dna_records=records, derived_metrics=metrics).discover()
    registry.upsert_candidates(
        candidates=candidates,
        evaluator=evaluator,
        recalculated_at="2026-07-31T15:00:00+00:00",
    )
    updated = registry.get(first.edge_id)
    assert updated is not None
    assert updated.edge_id == first.edge_id
    assert updated.historical_versions == ()


def test_edge_evaluation_confidence_threshold_stability_persistence_and_drift():
    records, metrics = _sample_population()
    candidates = EdgeDiscoveryEngine(dna_records=records, derived_metrics=metrics).discover()
    alpha = next(c for c in candidates if c.category == "strategy" and c.cohort_key == "ALPHA")
    evaluation = EdgeEvaluator(dna_records=records, derived_metrics=metrics, threshold_policy=_policy()).evaluate(alpha)
    assert evaluation.sample_size == 6
    assert evaluation.win_rate == 1.0
    assert evaluation.loss_rate == 0.0
    assert evaluation.profit_factor > 0
    assert evaluation.expectancy == 5.0
    assert evaluation.evidence_threshold == "SUPPORTED"
    assert evaluation.confidence_label in {"HIGH", "VERY_HIGH"}
    assert evaluation.stability_label == "STABLE"
    assert evaluation.persistence_score > 0
    assert evaluation.drift_state == "NO_DRIFT"
    assert evaluation.edge_fingerprint == evaluation.metrics_hash


def test_explainability_contains_evidence_and_counter_evidence():
    records, metrics = _sample_population()
    candidates = EdgeDiscoveryEngine(dna_records=records, derived_metrics=metrics).discover()
    beta = next(c for c in candidates if c.category == "strategy" and c.cohort_key == "BETA")
    evaluation = EdgeEvaluator(dna_records=records, derived_metrics=metrics, threshold_policy=_policy()).evaluate(beta)
    explanation = evaluation.explanation.to_dict()
    assert explanation["why_detected"]
    assert explanation["supporting_trade_ids"] == ["T7", "T8", "T9"]
    assert explanation["counter_evidence"]
    assert explanation["confidence_breakdown"]
    assert explanation["stability_breakdown"]
    assert explanation["drift_breakdown"]


def test_edge_reporting_is_read_only_and_deterministic():
    registry = _build_registry()
    report_a = EdgeReportBuilder(edges=registry.list_edges(), generated_at=GENERATED_AT).full_report()
    report_b = EdgeReportBuilder(edges=registry.list_edges(), generated_at=GENERATED_AT).full_report()
    assert report_a == report_b
    assert report_a["report_hash"] == report_b["report_hash"]
    assert report_a["advisory_flags"]["execution_allowed"] is False
    assert report_a["advisory_flags"]["recommendations"] is False
    assert "top_edges" in report_a["sections"]
    top = report_a["sections"]["top_edges"][0]
    assert top["trade_references"]
    assert top["evidence_references"]
    assert "counter_evidence" in top


def test_replay_determinism_for_registry_and_reports(tmp_path: Path):
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    registry_a = _build_registry(path_a)
    records, metrics = _sample_population()
    candidates = EdgeDiscoveryEngine(dna_records=list(reversed(records)), derived_metrics=list(reversed(metrics))).discover()
    evaluator = EdgeEvaluator(
        dna_records=list(reversed(records)),
        derived_metrics=list(reversed(metrics)),
        threshold_policy=_policy(),
    )
    registry_b = EdgeRegistry(path_b)
    registry_b.upsert_candidates(candidates=candidates, evaluator=evaluator, recalculated_at=GENERATED_AT)
    assert registry_a.registry_hash() == registry_b.registry_hash()
    report_a = EdgeReportBuilder(edges=registry_a.list_edges(), generated_at=GENERATED_AT).full_report()
    report_b = EdgeReportBuilder(edges=registry_b.list_edges(), generated_at=GENERATED_AT).full_report()
    assert report_a["report_hash"] == report_b["report_hash"]


def test_changing_metrics_versions_and_evidence_do_not_change_permanent_edge_id(tmp_path: Path):
    records, metrics = _sample_population()
    candidates = EdgeDiscoveryEngine(dna_records=records, derived_metrics=metrics).discover()
    evaluator = EdgeEvaluator(dna_records=records, derived_metrics=metrics, threshold_policy=_policy())
    registry = EdgeRegistry(tmp_path / "registry.json")
    registry.upsert_candidates(candidates=candidates, evaluator=evaluator, recalculated_at=GENERATED_AT)
    alpha = next(edge for edge in registry.list_edges() if edge.category == "strategy" and edge.name.endswith("ALPHA"))
    original_id = alpha.edge_id
    original_fingerprint = alpha.edge_fingerprint

    changed_metrics = [
        DerivedTradeMetrics(
            **{
                **metric.to_dict(),
                "profit": 7.0 if metric.trade_id == "T1" else metric.profit,
                "return_pct": 0.007 if metric.trade_id == "T1" else metric.return_pct,
            }
        )
        for metric in metrics
    ]
    changed_evaluator = EdgeEvaluator(
        dna_records=records,
        derived_metrics=changed_metrics,
        threshold_policy=_policy(),
        evidence_version="css.trade_dna.evidence.v2",
        analysis_version="css.trade_dna.analysis.v2",
    )
    registry.upsert_candidates(
        candidates=candidates,
        evaluator=changed_evaluator,
        recalculated_at="2026-08-01T00:00:00+00:00",
    )
    updated = registry.get(original_id)
    assert updated is not None
    assert updated.edge_id == original_id
    assert updated.definition_hash == alpha.definition_hash
    assert updated.edge_fingerprint != original_fingerprint
    assert updated.historical_versions


def test_identical_evidence_does_not_append_duplicate_history(tmp_path: Path):
    registry = _build_registry(tmp_path / "registry.json")
    first = registry.list_edges()[0]
    records, metrics = _sample_population()
    candidates = EdgeDiscoveryEngine(dna_records=records, derived_metrics=metrics).discover()
    evaluator = EdgeEvaluator(dna_records=records, derived_metrics=metrics, threshold_policy=_policy())
    registry.upsert_candidates(
        candidates=candidates,
        evaluator=evaluator,
        recalculated_at="2026-09-01T00:00:00+00:00",
    )
    updated = registry.get(first.edge_id)
    assert updated is not None
    assert updated.edge_id == first.edge_id
    assert updated.edge_fingerprint == first.edge_fingerprint
    assert updated.historical_versions == first.historical_versions == ()


def test_definition_hash_and_edge_fingerprint_are_distinct():
    registry = _build_registry()
    edge = registry.list_edges()[0]
    assert edge.definition_hash != edge.edge_fingerprint
    assert edge.definition_hash.startswith("edge-definition:")
    assert len(edge.edge_fingerprint) == 64


def test_wall_clock_and_report_order_do_not_affect_identity():
    records, metrics = _sample_population()
    candidates = EdgeDiscoveryEngine(dna_records=records, derived_metrics=metrics).discover()
    evaluator = EdgeEvaluator(dna_records=records, derived_metrics=metrics, threshold_policy=_policy())
    a = EdgeRegistry()
    b = EdgeRegistry()
    a.upsert_candidates(candidates=candidates, evaluator=evaluator, recalculated_at="2026-01-01T00:00:00+00:00")
    b.upsert_candidates(candidates=candidates, evaluator=evaluator, recalculated_at="2026-12-31T00:00:00+00:00")
    assert [(e.definition_hash, e.edge_id) for e in a.list_edges()] == [
        (e.definition_hash, e.edge_id) for e in b.list_edges()
    ]
    report = EdgeReportBuilder(edges=list(reversed(a.list_edges())), generated_at=GENERATED_AT).full_report()
    assert report["sections"]["top_edges"]
    assert [(e.definition_hash, e.edge_id) for e in a.list_edges()] == [
        (e.definition_hash, e.edge_id) for e in b.list_edges()
    ]


def test_relationships_validate_permanent_ids_and_collapse_duplicates(tmp_path: Path):
    registry = _build_registry(tmp_path / "registry.json")
    first, second = registry.list_edges()[:2]
    linked = registry.link_edges(
        edge_id=first.edge_id,
        supporting_edges=(second.edge_id, second.edge_id),
    )
    assert linked.supporting_edges == (second.edge_id,)
    try:
        registry.link_edges(edge_id=first.edge_id, parent_edge_ids=(first.edge_id,))
    except ValueError as exc:
        assert "edge_relationship_self_reference" in str(exc)
    else:
        raise AssertionError("self relationship should fail")
    try:
        registry.link_edges(edge_id=first.edge_id, conflicting_edges=("EDGE-999999",))
    except ValueError as exc:
        assert "edge_relationship_unknown_reference" in str(exc)
    else:
        raise AssertionError("unknown relationship should fail")


def test_edge_intelligence_does_not_import_execution_facing_modules():
    import ast
    from pathlib import Path

    root = Path("backend/intelligence/edge_intelligence")
    forbidden = (
        "execution_gate",
        "risk_governor",
        "antibleed",
        "broker",
        "sizing",
        "runtime",
        "mission_control",
    )
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(any(token in name.lower() for token in forbidden) for name in imports)


def test_dip003_decision_analytics_regression():
    records, metrics = _sample_population()
    report = DecisionAnalyticsEngine(
        dna_records=records,
        derived_metrics=metrics,
        generated_at=GENERATED_AT,
    ).full_report()
    assert report["execution_allowed"] is False
    assert report["recommendations"] is False
    assert report["capital_allocation"] is False
    assert report["sections"]

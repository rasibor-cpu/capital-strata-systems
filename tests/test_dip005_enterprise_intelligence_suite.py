"""DIP-005 Enterprise Intelligence Suite deterministic tests."""

from __future__ import annotations

import ast
from pathlib import Path

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


GENERATED_AT = "2026-07-30T20:00:00+00:00"


def _dna(
    trade_id: str,
    *,
    profit: float,
    notional: float,
    strategy: str,
    symbol: str,
    opened_at: str,
    regime: str = "trend",
    execution_quality: float = 0.8,
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
            requested_notional=notional,
            scaled_notional=notional,
        ),
        market=MarketFacts(
            symbol=symbol,
            session="NY",
            market_regime=regime,
        ),
        strategy=StrategyFacts(
            strategy_id=strategy,
            signal_id="breakout",
            confluence_score=0.8,
        ),
        volatility=VolatilityFacts(vol_regime="medium"),
        timing=TimingFacts(
            opened_at=opened_at,
            closed_at=opened_at.replace("10:00:00", "12:00:00"),
        ),
        outcome=OutcomeFacts(
            status="closed",
            exit_reason="take_profit" if profit > 0 else "stop",
            win_loss="win" if profit > 0 else "loss" if profit < 0 else "flat",
        ),
    ).with_content_hash()
    metric = DerivedTradeMetrics(
        dna_id=record.identity.dna_id,
        trade_id=trade_id,
        profit=profit,
        return_pct=profit / notional,
        holding_period_seconds=7200.0,
        expectancy_contribution=profit,
        edge_contribution=profit,
        capital_efficiency=profit / notional,
        execution_quality=execution_quality,
        drawdown_contribution=min(0.0, profit),
    )
    return record, metric


def _population() -> tuple[list[TradeDNARecord], list[DerivedTradeMetrics]]:
    rows = [
        _dna("T1", profit=100.0, notional=1000.0, strategy="alpha", symbol="EUR_USD", opened_at="2026-07-01T10:00:00+00:00"),
        _dna("T2", profit=-40.0, notional=1000.0, strategy="alpha", symbol="EUR_USD", opened_at="2026-07-02T10:00:00+00:00", regime="range", execution_quality=0.6),
        _dna("T3", profit=60.0, notional=2000.0, strategy="beta", symbol="GBP_USD", opened_at="2026-07-03T10:00:00+00:00"),
        _dna("T4", profit=20.0, notional=1000.0, strategy="beta", symbol="USD_JPY", opened_at="2026-07-04T10:00:00+00:00"),
        _dna("T5", profit=10.0, notional=500.0, strategy="alpha", symbol="GBP_USD", opened_at="2026-07-05T10:00:00+00:00"),
    ]
    return [row[0] for row in rows], [row[1] for row in rows]


def _edges(records, metrics):
    candidates = EdgeDiscoveryEngine(dna_records=records, derived_metrics=metrics).discover()
    evaluator = EdgeEvaluator(
        dna_records=records,
        derived_metrics=metrics,
        threshold_policy=EvidenceThresholdPolicy(
            observational_min_trades=1,
            supported_min_trades=2,
            observational_min_independent=1,
            supported_min_independent=2,
            min_data_completeness=0.50,
            supported_data_completeness=0.50,
            observational_min_confidence=0.10,
            supported_min_confidence=0.20,
            max_supported_outlier_impact=0.90,
        ),
    )
    registry = EdgeRegistry()
    registry.upsert_candidates(candidates=candidates, evaluator=evaluator, recalculated_at=GENERATED_AT)
    return registry.list_edges()


def _suite():
    records, metrics = _population()
    edges = _edges(records, metrics)
    capital = CapitalIntelligenceEngine(
        dna_records=records,
        derived_metrics=metrics,
        generated_at=GENERATED_AT,
        period_days=30,
    ).build_report()
    executive = ExecutiveIntelligenceEngine(
        dna_records=records,
        derived_metrics=metrics,
        edge_records=edges,
        capital_report=capital,
        generated_at=GENERATED_AT,
    ).build_summary()
    enterprise = EnterpriseReportBuilder(
        dna_records=records,
        derived_metrics=metrics,
        edge_records=edges,
        capital_report=capital,
        executive_summary=executive,
        generated_at=GENERATED_AT,
    ).build_report()
    return records, metrics, edges, capital, executive, enterprise


def test_capital_calculations_are_deterministic_and_explainable():
    _records, _metrics, _edges, capital, _executive, _enterprise = _suite()
    assert capital.metrics["capital_deployment"] == 5500.0
    assert capital.metrics["realized_profitability"] == 150.0
    assert capital.metrics["capital_efficiency"] == round(150.0 / 5500.0, 10)
    assert capital.metrics["cumulative_banked_profits"] == 190.0
    assert capital.metrics["profit_retention"] == round(150.0 / 190.0, 10)
    assert capital.metrics["drawdown_utilization"] == round(40.0 / 5500.0, 10)
    assert capital.metrics["drawdown_recovery"] == 1.0
    assert capital.metrics["exposure_concentration"] == round(2500.0 / 5500.0, 10)
    assert "capital_efficiency" in capital.evidence.calculations
    assert capital.evidence.trade_ids == ("T1", "T2", "T3", "T4", "T5")
    assert capital.advisory_flags["execution_allowed"] is False


def test_profitability_drawdown_exposure_and_run_rate_sections():
    _records, _metrics, _edges, capital, _executive, enterprise = _suite()
    assert capital.trends
    assert capital.exposure_history[0]["symbol"] == "GBP_USD"
    assert enterprise.sections["drawdown_analysis"]["drawdown_recovery"] == 1.0
    assert enterprise.sections["profitability_run_rate"]["per_day"] > 0
    assert enterprise.sections["exposure_analysis"][0]["trade_ids"]


def test_executive_summary_is_traceable_and_advisory_only():
    _records, _metrics, edges, _capital, executive, _enterprise = _suite()
    summary = executive.summary
    assert summary["portfolio_health"]["status"] == "HEALTHY"
    assert summary["strategy_health"]["ranked_strategies"]
    assert summary["edge_health"]["supported_edges"]
    assert set(summary) >= {
        "portfolio_health",
        "strategy_health",
        "edge_health",
        "capital_health",
        "execution_quality",
        "evidence_quality",
        "profitability_trends",
        "drawdown_trends",
    }
    assert executive.evidence.edge_ids == tuple(sorted(edge.edge_id for edge in edges))
    assert executive.advisory_flags["capital_movement_allowed"] is False
    assert all(alert["severity"] == "ADVISORY" for alert in executive.operational_alerts)


def test_enterprise_reporting_contains_required_sections_and_hashes():
    _records, _metrics, _edges, capital, executive, enterprise = _suite()
    required = {
        "executive_summary",
        "strategy_performance",
        "edge_performance",
        "capital_performance",
        "drawdown_analysis",
        "exposure_analysis",
        "profitability_run_rate",
        "historical_trend_analysis",
        "decision_intelligence_summary",
    }
    assert set(enterprise.sections) == required
    assert enterprise.sections["decision_intelligence_summary"]["capital_report_hash"] == capital.report_hash
    assert enterprise.sections["decision_intelligence_summary"]["executive_summary_hash"] == executive.summary_hash
    assert enterprise.report_schema_version == "css.enterprise_intelligence.report.schema.v1"
    assert enterprise.analysis_version == "css.trade_dna.analysis.v1"
    assert enterprise.evidence_version == "css.trade_dna.evidence.v1"
    assert enterprise.generation_parameters == {"period_days": 30}
    assert enterprise.canonical_report_id
    assert enterprise.report_type == "ENTERPRISE_INTELLIGENCE"
    assert enterprise.report_hash
    assert enterprise.advisory_flags["trade_authorization_allowed"] is False


def test_metric_provenance_exists_for_every_executive_metric():
    records, _metrics, edges, _capital, executive, _enterprise = _suite()
    repeated = _suite()[4]
    dna_ids = sorted(record.identity.dna_id for record in records)
    for metric_name, metric in executive.summary.items():
        provenance = metric["provenance"]
        assert provenance == repeated.summary[metric_name]["provenance"]
        assert provenance["contributing_trade_dna_ids"] == dna_ids
        assert provenance["calculation_version"] == "css.enterprise_intelligence.v1"
        assert provenance["evidence_version"] == "css.trade_dna.evidence.v1"
        assert provenance["analysis_version"] == "css.trade_dna.analysis.v1"
        assert provenance["metric_definition"]
        assert provenance["metric_hash"]
        if metric_name in {"edge_health", "evidence_quality"}:
            assert provenance["contributing_edge_ids"] == sorted(edge.edge_id for edge in edges)


def test_replay_determinism_with_shuffled_inputs():
    records, metrics = _population()
    edges = _edges(records, metrics)
    capital_a = CapitalIntelligenceEngine(
        dna_records=records,
        derived_metrics=metrics,
        generated_at=GENERATED_AT,
    ).build_report()
    capital_b = CapitalIntelligenceEngine(
        dna_records=list(reversed(records)),
        derived_metrics=list(reversed(metrics)),
        generated_at=GENERATED_AT,
    ).build_report()
    assert capital_a.to_dict() == capital_b.to_dict()

    executive_a = ExecutiveIntelligenceEngine(
        dna_records=records,
        derived_metrics=metrics,
        edge_records=edges,
        capital_report=capital_a,
        generated_at=GENERATED_AT,
    ).build_summary()
    executive_b = ExecutiveIntelligenceEngine(
        dna_records=list(reversed(records)),
        derived_metrics=list(reversed(metrics)),
        edge_records=list(reversed(edges)),
        capital_report=capital_b,
        generated_at=GENERATED_AT,
    ).build_summary()
    assert executive_a.to_dict() == executive_b.to_dict()

    report_a = EnterpriseReportBuilder(
        dna_records=records,
        derived_metrics=metrics,
        edge_records=edges,
        capital_report=capital_a,
        executive_summary=executive_a,
        generated_at=GENERATED_AT,
    ).build_report()
    report_b = EnterpriseReportBuilder(
        dna_records=list(reversed(records)),
        derived_metrics=list(reversed(metrics)),
        edge_records=list(reversed(edges)),
        capital_report=capital_b,
        executive_summary=executive_b,
        generated_at=GENERATED_AT,
    ).build_report()
    assert report_a.to_dict() == report_b.to_dict()
    assert report_a.report_hash == report_b.report_hash


def test_report_hash_excludes_optional_caller_timestamp():
    records, metrics = _population()
    edges = _edges(records, metrics)
    capital_a = CapitalIntelligenceEngine(
        dna_records=records,
        derived_metrics=metrics,
        generated_at="2026-07-30T20:00:00+00:00",
    ).build_report()
    capital_b = CapitalIntelligenceEngine(
        dna_records=records,
        derived_metrics=metrics,
        generated_at="2026-08-01T20:00:00+00:00",
    ).build_report()
    assert capital_a.report_hash == capital_b.report_hash

    executive_a = ExecutiveIntelligenceEngine(
        dna_records=records,
        derived_metrics=metrics,
        edge_records=edges,
        capital_report=capital_a,
        generated_at="2026-07-30T20:00:00+00:00",
    ).build_summary()
    executive_b = ExecutiveIntelligenceEngine(
        dna_records=records,
        derived_metrics=metrics,
        edge_records=edges,
        capital_report=capital_b,
        generated_at="2026-08-01T20:00:00+00:00",
    ).build_summary()
    assert executive_a.summary_hash == executive_b.summary_hash

    report_a = EnterpriseReportBuilder(
        dna_records=records,
        derived_metrics=metrics,
        edge_records=edges,
        capital_report=capital_a,
        executive_summary=executive_a,
        generated_at="2026-07-30T20:00:00+00:00",
    ).build_report()
    report_b = EnterpriseReportBuilder(
        dna_records=records,
        derived_metrics=metrics,
        edge_records=edges,
        capital_report=capital_b,
        executive_summary=executive_b,
        generated_at="2026-08-01T20:00:00+00:00",
    ).build_report()
    assert report_a.report_hash == report_b.report_hash
    assert report_a.to_dict(include_caller_metadata=False) == report_b.to_dict(include_caller_metadata=False)
    assert report_a.to_dict() != report_b.to_dict()


def test_historical_snapshot_reproducibility_contract():
    first = _suite()[-1]
    second = _suite()[-1]
    assert first.to_dict() == second.to_dict()
    assert first.report_hash == second.report_hash
    assert first.canonical_report_id == second.canonical_report_id


def test_regression_against_dip002_dip003_and_dip004_contracts():
    records, metrics, edges, capital, executive, enterprise = _suite()
    assert all(record.content_hash for record in records)
    assert all(metric.layer == "derived" for metric in metrics)
    assert all(edge.edge_id.startswith("EDGE-") for edge in edges)
    assert capital.evidence.dna_ids
    assert executive.evidence.edge_ids
    assert enterprise.evidence.calculations


def test_enterprise_intelligence_does_not_import_execution_facing_modules():
    root = Path("backend/intelligence/enterprise_intelligence")
    forbidden = (
        "execution_gate",
        "risk_governor",
        "anti_bleed",
        "broker",
        "sizing",
        "order",
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

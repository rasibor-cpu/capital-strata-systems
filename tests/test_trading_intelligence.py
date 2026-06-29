"""
Tests for CSS Trading Intelligence Foundation (EWP-4/5A PART C & D)
"""

import pytest
import os
import tempfile
from backend.events.event_models import Event
from backend.events.visibility_layer import EventVisibilityLayer
from backend.metrics.metrics_service import MetricsService
from backend.metrics.metrics_registry import MetricsRegistry
from backend.metrics.telemetry import TelemetryCollector
from backend.metrics.metrics_history import MetricsHistory
from backend.intelligence.intelligence_service import IntelligenceService
from backend.dashboard.dashboard_read_model import DashboardReadModel
from backend.dashboard.dashboard_service import DashboardService


@pytest.fixture
def intelligence_fixture():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Setup metrics
        m_reg = MetricsRegistry()
        m_tel = TelemetryCollector()
        m_hist = MetricsHistory(file_path=os.path.join(temp_dir, "metrics.json"))
        metrics_service = MetricsService(registry=m_reg, telemetry=m_tel, history=m_hist)
        
        # Setup visibility
        v_layer = EventVisibilityLayer(
            event_store_file=os.path.join(temp_dir, "events.jsonl"),
            notification_queue_file=os.path.join(temp_dir, "notif_q.json"),
            notification_history_file=os.path.join(temp_dir, "notif_h.json"),
            operational_state_file=os.path.join(temp_dir, "ops_state.json"),
            operational_timeline_file=os.path.join(temp_dir, "ops_t.json")
        )
        
        # Seed visibility events to simulate trades
        e1 = Event(
            event_type="TRADE_APPROVED",
            severity="INFO",
            category="TRADING",
            source="trade_gate",
            payload={"trade_id": "T1", "symbol": "AAPL", "asset_class": "EQUITIES", "quantity": 10.0, "entry_price": 150.0, "realized_pnl": 50.0}
        )
        e2 = Event(
            event_type="TRADE_APPROVED",
            severity="INFO",
            category="TRADING",
            source="trade_gate",
            payload={"trade_id": "T2", "symbol": "BTC_USD", "asset_class": "CRYPTO", "quantity": 1.0, "entry_price": 30000.0, "realized_pnl": -100.0}
        )
        import json
        with open(v_layer.event_store_file, "a") as f:
            f.write(json.dumps(e1.to_dict()) + "\n")
            f.write(json.dumps(e2.to_dict()) + "\n")
        
        service = IntelligenceService(visibility_layer=v_layer, metrics_service=metrics_service)
        yield service


def test_trading_intelligence_analytics(intelligence_fixture):
    report = intelligence_fixture.get_trading_intelligence_report()
    
    # 1. Regime Detection
    assert report["market_regime"] in ("BULLISH", "BEARISH", "RANGE_BOUND", "HIGH_VOLATILITY")
    
    # 2. Win/Loss calculations
    win_loss = report["win_loss_statistics"]
    assert win_loss["total_trades"] == 2
    assert win_loss["wins_count"] == 1
    assert win_loss["losses_count"] == 1
    assert win_loss["win_rate"] == 0.5
    
    # 3. Asset Class Performance
    asset_perf = report["asset_class_performance"]
    assert asset_perf["EQUITIES"]["total_pnl"] == 50.0
    assert asset_perf["CRYPTO"]["total_pnl"] == -100.0
    
    # 4. Portfolio concentration
    portfolio = report["portfolio_concentration"]
    assert portfolio["highest_exposure_asset"] == "CRYPTO"
    assert portfolio["risk_concentration_score"] > 0.0


def test_explainability_and_confidence(intelligence_fixture):
    # Trade explanation check
    trade = {"symbol": "AAPL", "realized_pnl": 120.0, "side": "BUY", "asset_class": "EQUITIES"}
    msg = intelligence_fixture.explainability.explain_trade_outcome(trade)
    assert "gain of 120.00" in msg

    # Gate decision explanation check
    app_event = Event(
        event_type="TRADE_APPROVED",
        severity="INFO",
        category="TRADING",
        source="gate",
        payload={"trade_id": "T77"}
    )
    explanation = intelligence_fixture.explainability.explain_gate_decision(app_event)
    assert "Trade T77 was approved" in explanation
    
    # Confidence Score Check
    score = intelligence_fixture.confidence_engine.calculate_confidence({"probability": 0.8}, "HIGH_VOLATILITY")
    assert score == 0.8 * 0.8  # 0.64


def test_dashboard_intelligence_integration(intelligence_fixture):
    # Construct a dashboard read model
    from backend.notifications.notification_service import NotificationService, NotificationConfig
    from backend.notifications.notification_queue import NotificationQueue
    from backend.notifications.notification_history import NotificationHistory
    from backend.notifications.notification_delivery import NotificationDeliveryRouter
    from backend.notifications.notification_templates import NotificationTemplates
    from backend.notifications.notification_scheduler import NotificationScheduler
    
    from backend.reporting.reporting_service import ReportingService, ReportingConfig
    from backend.reporting.report_generator import ReportGenerator
    from backend.reporting.report_archive import ReportArchive
    from backend.reporting.report_history import ReportHistory
    from backend.reporting.report_scheduler import ReportScheduler
    from backend.reporting.report_templates import ReportTemplates
    
    from backend.operations.operations_service import OperationsService, OperationsConfig
    from backend.operations.health_monitor import HealthMonitor
    from backend.operations.operational_state_manager import OperationalStateManager
    from backend.operations.operational_timeline import OperationalTimeline
    from backend.operations.runtime_statistics import RuntimeStatistics
    
    with tempfile.TemporaryDirectory() as td:
        n_q = NotificationQueue(file_path=os.path.join(td, "notif_q.json"))
        n_h = NotificationHistory(file_path=os.path.join(td, "notif_h.json"))
        notif_service = NotificationService(
            config=NotificationConfig(),
            queue=n_q,
            history=n_h,
            router=NotificationDeliveryRouter(),
            templates=NotificationTemplates(),
            scheduler=NotificationScheduler()
        )
        
        rep_arch = os.path.join(td, "reports")
        os.makedirs(rep_arch, exist_ok=True)
        r_hist = ReportHistory(history_file=os.path.join(td, "report_history.json"))
        reporting_service = ReportingService(
            config=ReportingConfig(archive_dir=rep_arch, history_file=os.path.join(td, "report_history.json")),
            generator=ReportGenerator(templates=ReportTemplates()),
            archive=ReportArchive(archive_dir=rep_arch),
            history=r_hist,
            scheduler=ReportScheduler()
        )
        
        o_state = os.path.join(td, "ops_state.json")
        o_timeline = os.path.join(td, "ops_timeline.json")
        operations_service = OperationsService(
            config=OperationsConfig(state_file=o_state, timeline_file=o_timeline),
            monitor=HealthMonitor(),
            state_manager=OperationalStateManager(file_path=o_state),
            timeline=OperationalTimeline(file_path=o_timeline),
            statistics=RuntimeStatistics()
        )
        
        read_model = DashboardReadModel(
            metrics_service=intelligence_fixture.metrics_service,
            operations_service=operations_service,
            notification_service=notif_service,
            reporting_service=reporting_service,
            visibility_layer=intelligence_fixture.visibility_layer
        )
        
        dashboard = DashboardService(read_model=read_model, intelligence_service=intelligence_fixture)
        
        view = dashboard.get_trading_intelligence_view()
        assert "market_regime" in view
        assert "trading_confidence" in view
        assert "strategy_performance" in view
        assert "portfolio_health" in view
        assert "top_recommendations" in view
        assert "delivery_status" in view
        assert "communication_health" in view
        
        # Verify read-only constraints
        assert not hasattr(dashboard, "update_exposure")

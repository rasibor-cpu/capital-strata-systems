"""Mission Control mobile responsive presentation — no semantic/data changes."""

from __future__ import annotations

import re

from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS
from dashboard.mission_control.pages.executive_overview import render as render_executive_overview
from dashboard.mission_control.pages.alerts_incidents import render as render_alerts_incidents
from dashboard.mission_control.pages.risk_command import render as render_risk_command
from dashboard.mission_control.pages.trade_operations import render as render_trade_operations
from dashboard.mission_control.pages.runtime_operations import render as render_runtime_operations
from dashboard.mission_control.pages.portfolio import render as render_portfolio
from dashboard.mission_control.pages.market_intelligence import render as render_market_intelligence
from dashboard.mission_control.pages.certification_readiness import render as render_certification_readiness
from dashboard.mission_control.pages.audit_explainability import render as render_audit_explainability
from dashboard.mission_control.theme import MISSION_CONTROL_CSS


STATUS_KEYS = (
    "runtime",
    "execution",
    "broker",
    "broker-health",
    "platform",
    "safety",
    "posture",
)

PRIORITY_LABELS = (
    "Execution Status",
    "Cash",
    "Portfolio Value",
    "Session P&L",
    "Open Positions",
    "Next Maturity",
)


def _shell(**kwargs) -> str:
    return render_mission_control_shell(
        {
            "schema_version": "test",
            "generated_at": "2026-09-05T00:00:00Z",
            "platform": {
                "product": "CSS Mission Control",
                "runtime_mode": "DISABLED",
                "broker_health": "DISABLED",
                "platform_status": "RED",
                "selected_broker": "UNAVAILABLE",
                "broker_mode": "UNAVAILABLE",
            },
            "platform_status": {
                "runtime_mode": "DISABLED",
                "execution_state": "BLOCKED",
                "broker_mode": "UNAVAILABLE",
            },
            "safety": {
                "advisory_only": True,
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "safety_status": "PASS",
            },
            "runtime": {"heartbeat_status": "UNAVAILABLE"},
            "portfolio": {
                "cash": "UNAVAILABLE",
                "portfolio_value": "UNAVAILABLE",
                "session_pnl": "UNAVAILABLE",
                "open_positions": "UNAVAILABLE",
                "next_maturity": "UNAVAILABLE",
                "execution_status": "BLOCKED",
                "operating_context": {
                    "advisory_only": True,
                    "execution_allowed": False,
                    "live_trading_blocked": True,
                    "broker_execution_armed": False,
                },
            },
        },
        active_section="executive_overview",
        **kwargs,
    )


def test_single_native_nav_and_mobile_toggle() -> None:
    html = _shell()
    assert html.count('class="mc-nav"') == 1
    assert html.count('id="mc-nav-toggle"') == 1
    assert 'class="mc-mobile-chrome"' in html
    assert 'class="mc-nav-toggle-btn"' in html
    assert 'class="mc-nav-close"' in html
    assert 'for="mc-nav-toggle"' in html
    assert "CSS Mission Control" in html
    assert "Executive Overview" in html
    nav_block = re.search(r'<nav class="mc-nav"[^>]*>(.*?)</nav>', html, re.S)
    assert nav_block is not None
    hrefs = re.findall(r'href="(/mission-control/[^"]+)"', nav_block.group(1))
    assert len(hrefs) == len(MISSION_CONTROL_SECTIONS)
    assert "location.assign" not in html


def test_status_items_are_individually_rendered() -> None:
    html = _shell()
    strip = re.search(
        r'<div class="mc-status-strip"[^>]*>(.*?)</div>',
        html,
        re.S,
    )
    assert strip is not None
    for key in STATUS_KEYS:
        assert f'data-mc-status="{key}"' in strip.group(1)
    assert "Runtime" in strip.group(1)
    assert "DISABLED" in strip.group(1)
    assert "Execution" in strip.group(1)
    assert "BLOCKED" in strip.group(1)
    assert "Broker" in strip.group(1)
    assert "UNAVAILABLE" in strip.group(1)
    assert "Broker Health" in strip.group(1)
    assert "Platform" in strip.group(1)
    assert "RED" in strip.group(1)
    assert "Safety" in strip.group(1)
    assert "PASS" in strip.group(1)
    assert "Posture" in strip.group(1)
    assert "ADVISORY / READ-ONLY" in strip.group(1)
    # Concatenation defect: values must not immediately adjoin the next label.
    assert "DISABLEDExecution" not in html
    assert "BLOCKEDBroker" not in html


def test_css_collapses_nav_and_wraps_status_on_phone() -> None:
    assert ".mc-nav-toggle:checked ~ .mc-sidebar" in MISSION_CONTROL_CSS
    assert ".mc-mobile-chrome" in MISSION_CONTROL_CSS
    assert "min-width: 44px" in MISSION_CONTROL_CSS
    assert "min-height: 44px" in MISSION_CONTROL_CSS
    assert "grid-template-columns: repeat(auto-fit, minmax(148px, 1fr))" in MISSION_CONTROL_CSS
    assert ".mc-table-wrap" in MISSION_CONTROL_CSS
    assert "@media (max-width: 430px)" in MISSION_CONTROL_CSS
    assert "@media (max-width: 768px)" in MISSION_CONTROL_CSS
    assert "max-height: min(46vh, 420px)" not in MISSION_CONTROL_CSS
    desktop = MISSION_CONTROL_CSS[: MISSION_CONTROL_CSS.index("@media (max-width: 1100px)")]
    assert "grid-template-columns: 288px 1fr" in desktop
    assert ".mc-shell {\n  min-height: 100vh;\n  display: grid;" in desktop


def test_executive_overview_priority_and_sections() -> None:
    body = render_executive_overview(
        {
            "platform": {"runtime_mode": "DISABLED", "platform_status": "RED"},
            "safety": {
                "advisory_only": True,
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "safety_status": "PASS",
            },
            "portfolio": {
                "cash": "UNAVAILABLE",
                "portfolio_value": "UNAVAILABLE",
                "session_pnl": "UNAVAILABLE",
                "open_positions": "UNAVAILABLE",
                "next_maturity": "UNAVAILABLE",
                "execution_status": "BLOCKED",
                "operating_context": {
                    "advisory_only": True,
                    "read_only": True,
                    "execution_allowed": False,
                    "live_trading_blocked": True,
                    "broker_execution_armed": False,
                },
            },
            "mock_data_label": "RUNTIME DATA",
        }
    )
    assert 'aria-label="Executive cockpit priority"' in body
    assert "Session P&amp;L by Instrument" in body or "Session P&L by Instrument" in body
    assert "Current Holdings / Exposure" in body
    assert "Operating Context" in body
    first = body.find('aria-label="Executive cockpit priority"')
    second = body.find("Session P&amp;L by Instrument")
    if second < 0:
        second = body.find("Session P&L by Instrument")
    assert 0 <= first < second
    positions = []
    for label in PRIORITY_LABELS:
        token = f"<span>{label}</span>"
        pos = body.find(token)
        if pos < 0:
            pos = body.find(f"<span>{label.replace('&', '&amp;')}</span>")
        positions.append(pos)
    assert all(pos >= 0 for pos in positions)
    assert positions == sorted(positions)
    assert "execution_allowed" in body
    assert "False" in body
    assert "live_trading_blocked" in body
    assert "True" in body
    assert "broker_execution_armed" in body
    assert "advisory_only" in body


def test_safety_semantics_unchanged_in_shell() -> None:
    html = _shell()
    assert "ADVISORY / READ-ONLY" in html
    assert "BLOCKED" in html
    assert "DISABLED" in html
    assert "execution_allowed" in html or "Execution" in html
    assert "No execution authority is granted from Mission Control." in html


def test_status_class_does_not_treat_unavailable_as_available() -> None:
    from dashboard.mission_control.pages._components import status_class

    assert status_class("UNAVAILABLE") == "bad"
    assert status_class("unavailable") == "bad"
    assert status_class("Unavailable") == "bad"
    assert status_class("AVAILABLE") == "good"
    assert status_class("available") == "good"
    assert status_class("Available") == "good"
    assert status_class("UNAVAILABLE") != status_class("AVAILABLE")
    assert status_class("UNAVAILABLE") != "good"
    assert status_class("AVAILABLE") != "bad"


def test_status_class_keeps_blocked_disabled_pass_and_advisory_neutral() -> None:
    from dashboard.mission_control.pages._components import status_class

    assert status_class("DISABLED") == "bad"
    assert status_class("disabled") == "bad"
    assert status_class("BLOCKED") == "bad"
    assert status_class("blocked") == "bad"
    assert status_class("PASS") == "good"
    assert status_class("pass") == "good"
    assert status_class("RED") == "bad"
    assert status_class("ADVISORY / READ-ONLY") == "neutral"
    assert status_class("advisory / read-only") == "neutral"
    assert status_class("READ-ONLY") == "neutral"
    assert status_class("NOT_READY") == "bad"


def test_metric_grid_unavailable_tag_is_not_green() -> None:
    from dashboard.mission_control.pages._components import metric_grid

    html = metric_grid((("Cash", "UNAVAILABLE", "UNAVAILABLE"), ("Cash Available", "12", "AVAILABLE")))
    assert "UNAVAILABLE" in html
    assert 'mc-status bad">UNAVAILABLE' in html
    assert 'mc-status good">UNAVAILABLE' not in html
    assert 'mc-status good">AVAILABLE' in html


def test_alerts_mobile_triage_navigation_is_read_only_and_touch_friendly() -> None:
    body = render_alerts_incidents(
        {
            "alerts": {
                "count": 2,
                "severity": "WARNING",
                "heartbeat_status": "ACTIVE",
                "external_notifications": "DISABLED",
                "active_alerts": [{"severity": "WARNING", "source": "runtime"}],
                "incident_timeline": [{"event": "sample"}],
            },
            "alert_center": {
                "grouped_by_severity": {"WARNING": 2},
                "grouped_by_category": {"runtime": 2},
                "acknowledgement_actions": ["read-only"],
                "source": "canonical",
                "state_hash": "abc123",
            },
        }
    )
    assert 'aria-label="Alerts and incidents sections"' in body
    assert 'aria-label="Alert triage priority"' in body
    assert 'href="#mc-active-alerts"' in body
    assert 'href="#mc-alert-center"' in body
    assert 'href="#mc-incident-timeline"' in body
    assert 'id="mc-active-alerts"' in body
    assert 'id="mc-alert-center"' in body
    assert 'id="mc-incident-timeline"' in body
    assert "<form" not in body
    assert "method=" not in body


def test_alerts_mobile_css_uses_touch_targets_without_runtime_semantics() -> None:
    assert ".mc-page-jump" in MISSION_CONTROL_CSS
    assert ".mc-alert-priority" in MISSION_CONTROL_CSS
    assert "min-height: 44px" in MISSION_CONTROL_CSS
    assert ".mc-section-anchor" in MISSION_CONTROL_CSS


def test_risk_command_mobile_priority_is_read_only() -> None:
    body = render_risk_command({
        "risk": {
            "overall_risk_state": "AMBER",
            "risk_score": 42,
            "drawdown": "1.2%",
            "exposure": "LOW",
            "unified_trade_gate": "BLOCKED",
            "kill_switch": "SAFE",
        },
        "risk_command_center": {},
        "risk_committee": {},
        "profit_protection_governance": {"execution_allowed": False, "read_only": True},
    })
    assert 'aria-label="Risk Command priority"' in body
    assert 'aria-label="Risk Command sections"' in body
    assert 'href="#mc-risk-limits"' in body
    assert 'href="#mc-risk-command"' in body
    assert 'href="#mc-risk-profit-protection"' in body
    assert 'href="#mc-risk-committee"' in body
    assert body.find("<span>Unified Gate</span>") < body.find("<span>Risk Score</span>")
    assert "<form" not in body
    assert "method=" not in body


def test_trade_operations_mobile_priority_is_read_only() -> None:
    body = render_trade_operations({
        "trading": {
            "execution_status": "BLOCKED",
            "accepted_decisions": 1,
            "rejected_decisions": 2,
            "open_positions": [],
            "orders": [],
            "fills": [],
            "rejections": [],
        },
        "decision_panel": {"status": "REVIEW", "read_only": True},
        "decision_trace": {"stages": []},
        "trade_lifecycle": {"stages": [], "events": []},
        "execution_committee": {},
        "broker_balance_summary": {
            "account_summary": {
                "available_to_trade": {"availability_state": "AVAILABLE", "value": 1000, "currency": "CAD"},
            }
        },
    })
    assert 'aria-label="Trade Operations priority"' in body
    assert 'aria-label="Trade Operations sections"' in body
    assert 'href="#mc-trade-account"' in body
    assert 'href="#mc-trade-decisions"' in body
    assert 'href="#mc-trade-execution"' in body
    assert 'href="#mc-trade-lifecycle"' in body
    assert body.find("<span>Execution Status</span>") < body.find("<span>Account Value</span>")
    assert "1000 CAD" in body
    assert "<form" not in body
    assert "method=" not in body


def test_operator_mobile_stack_css_preserves_touch_layout() -> None:
    assert ".mc-operator-stack" in MISSION_CONTROL_CSS
    assert ".mc-risk-priority" in MISSION_CONTROL_CSS
    assert ".mc-trade-priority" in MISSION_CONTROL_CSS


def test_unavailable_risk_metrics_are_not_neutral() -> None:
    body = render_risk_command({
        "risk": {
            "overall_risk_state": "RED",
            "risk_score": None,
            "drawdown": None,
            "exposure": None,
            "unified_trade_gate": "DATA UNAVAILABLE",
            "kill_switch": "UNAVAILABLE",
        }
    })
    assert '<span>Risk Score</span><strong>UNAVAILABLE</strong><em class="mc-status bad">UNAVAILABLE</em>' in body
    assert '<span>Drawdown</span><strong>UNAVAILABLE</strong><em class="mc-status bad">UNAVAILABLE</em>' in body
    assert '<span>Exposure</span><strong>UNAVAILABLE</strong><em class="mc-status bad">UNAVAILABLE</em>' in body


def test_unavailable_trade_balance_metrics_are_not_neutral() -> None:
    body = render_trade_operations({
        "trading": {"execution_status": "BLOCKED"},
        "decision_panel": {"status": "UNAVAILABLE"},
        "broker_balance_summary": {"account_summary": {}},
    })
    assert '<span>Available to Trade</span><strong>UNAVAILABLE</strong><em class="mc-status bad">UNAVAILABLE</em>' in body
    assert '<span>Account Value</span><strong>UNAVAILABLE</strong><em class="mc-status bad">UNAVAILABLE</em>' in body
    assert '<span>Buying Power</span><strong>UNAVAILABLE</strong><em class="mc-status bad">UNAVAILABLE</em>' in body
    assert '<span>Margin Available</span><strong>UNAVAILABLE</strong><em class="mc-status bad">UNAVAILABLE</em>' in body


def test_trade_balance_value_does_not_append_unavailable_currency() -> None:
    body = render_trade_operations({
        "trading": {"execution_status": "BLOCKED"},
        "decision_panel": {"status": "BLOCKED"},
        "broker_balance_summary": {
            "account_summary": {
                "available_to_trade": {
                    "availability_state": "AVAILABLE",
                    "value": 601.0005,
                    "currency": "UNAVAILABLE",
                    "freshness": "UNAVAILABLE",
                },
                "total_account_value": {
                    "availability_state": "AVAILABLE",
                    "value": 601.0005,
                    "currency": "UNAVAILABLE",
                    "freshness": "UNAVAILABLE",
                },
                "buying_power": {
                    "availability_state": "AVAILABLE",
                    "value": 596.7317,
                    "currency": "UNAVAILABLE",
                    "freshness": "UNAVAILABLE",
                },
                "margin_available": {
                    "availability_state": "AVAILABLE",
                    "value": 601.0005,
                    "currency": "UNAVAILABLE",
                    "freshness": "UNAVAILABLE",
                },
            }
        },
    })
    assert "<strong>601.0005</strong>" in body
    assert "<strong>596.7317</strong>" in body
    assert "<strong>601.0005 UNAVAILABLE</strong>" not in body
    assert '<em class="mc-status warn">WARNING</em>' in body


def test_trade_operations_adds_compact_decision_snapshot_and_trace_summary() -> None:
    body = render_trade_operations({
        "trading": {"execution_status": "BLOCKED"},
        "decision_panel": {
            "status": "BLOCKED",
            "reason": "BLOCKED",
            "read_only": True,
            "decisions": [{
                "symbol": "DATA UNAVAILABLE",
                "asset_class": "DATA UNAVAILABLE",
                "decision": "BLOCKED",
                "quality_score": "UNKNOWN",
                "confidence": "DATA UNAVAILABLE",
                "generated_at": "2026-09-24T22:29:22Z",
                "freshness": "DATA UNAVAILABLE",
                "state_hash": "hash",
                "provenance": {"large": "payload"},
            }],
        },
        "decision_trace": {
            "stages": [{
                "stage": "Market Regime",
                "status": "DISABLED",
                "reason": "Market regime evidence",
                "freshness": "DATA UNAVAILABLE",
                "evidence": {"large": "payload"},
                "state_hash": "hash",
            }]
        },
    })
    assert "Decision Snapshot" in body
    assert "Decision Trace Summary" in body
    assert "Decision Evidence (Full)" in body
    assert "Decision Trace Evidence (Full)" in body
    summary_start = body.find("Decision Trace Summary")
    full_start = body.find("Decision Trace Evidence (Full)")
    decision_full_start = body.find("Decision Evidence (Full)")
    assert 0 <= summary_start < full_start < decision_full_start
    compact = body[summary_start:full_start]
    assert "Market Regime" in compact
    assert "DISABLED" in compact
    assert "Market regime evidence" in compact
    assert "state_hash" not in compact
    assert "provenance" not in compact


def test_trade_operations_adds_compact_account_and_margin_snapshots() -> None:
    body = render_trade_operations({
        "trading": {"execution_status": "BLOCKED"},
        "decision_panel": {"status": "BLOCKED"},
        "broker_balance_summary": {
            "account_summary": {
                "total_account_value": {"availability_state": "AVAILABLE", "value": 601.0005, "currency": "UNAVAILABLE"},
                "cash": {"availability_state": "AVAILABLE", "value": 596.7317, "currency": "UNAVAILABLE"},
                "available_to_trade": {"availability_state": "AVAILABLE", "value": 601.0005, "currency": "UNAVAILABLE"},
                "buying_power": {"availability_state": "AVAILABLE", "value": 596.7317, "currency": "UNAVAILABLE"},
                "margin_available": {"availability_state": "AVAILABLE", "value": 601.0005, "currency": "UNAVAILABLE"},
                "total_pnl": {"availability_state": "AVAILABLE", "value": 393.3379, "currency": "UNAVAILABLE"},
            },
            "collateral_margin": {
                "margin_state": "SIMULATED",
                "available_collateral": {"availability_state": "AVAILABLE", "value": 601.0005, "currency": "UNAVAILABLE"},
                "free_margin": {"availability_state": "AVAILABLE", "value": 601.0005, "currency": "UNAVAILABLE"},
                "required_collateral": {"availability_state": "UNAVAILABLE"},
                "used_margin": {"availability_state": "UNAVAILABLE"},
            },
        },
    })
    assert "Account Snapshot" in body
    assert "Margin Snapshot" in body
    assert "Account Evidence (Full)" in body
    assert "Collateral / Margin Evidence (Full)" in body
    account_start = body.find("Account Snapshot")
    account_full = body.find("Account Evidence (Full)")
    margin_start = body.find("Margin Snapshot")
    margin_full = body.find("Collateral / Margin Evidence (Full)")
    assert 0 <= account_start < account_full
    assert 0 <= margin_start < margin_full
    compact = body[account_start:account_full]
    assert "601.0005" in compact
    assert "596.7317" in compact
    assert "393.3379" in compact
    assert "provenance" not in compact
    assert "state_hash" not in compact


def test_trade_operations_adds_compact_position_snapshot() -> None:
    body = render_trade_operations({
        "trading": {"execution_status": "BLOCKED"},
        "decision_panel": {"status": "BLOCKED"},
        "broker_balance_summary": {
            "position_value": {
                "EQUITIES": {"availability_state": "UNAVAILABLE"},
                "CRYPTO": {"availability_state": "UNAVAILABLE"},
                "FX": {"availability_state": "UNAVAILABLE"},
                "OPTIONS": {"availability_state": "UNAVAILABLE"},
                "FUTURES": {"availability_state": "UNAVAILABLE"},
                "TOTAL_INVESTED_VALUE": {"availability_state": "UNAVAILABLE"},
            }
        },
    })
    assert "Position Snapshot" in body
    assert "Position Value Evidence (Full)" in body
    snapshot_start = body.find("Position Snapshot")
    evidence_start = body.find("Position Value Evidence (Full)")
    assert 0 <= snapshot_start < evidence_start
    compact = body[snapshot_start:evidence_start]
    for key in ("equities", "crypto", "fx", "options", "futures", "total_invested_value"):
        assert key in compact
    assert "provenance" not in compact
    assert "state_hash" not in compact


def test_trade_full_evidence_is_collapsed_by_default() -> None:
    body = render_trade_operations({
        "trading": {"execution_status": "BLOCKED"},
        "decision_panel": {"status": "BLOCKED", "read_only": True, "decisions": []},
        "decision_trace": {"stages": []},
        "broker_balance_summary": {},
    })
    assert 'class="mc-section-anchor mc-evidence-disclosure"' in body
    assert "<details>" in body
    assert "<summary>Show full account evidence</summary>" in body
    assert "<summary>Show full position-value evidence</summary>" in body
    assert "<summary>Show full collateral / margin evidence</summary>" in body
    assert "<summary>Show full decision trace evidence</summary>" in body
    assert "<summary>Show full decision evidence</summary>" in body
    assert "<details open" not in body
    assert "<form" not in body
    assert "method=" not in body


def test_trade_evidence_disclosure_has_touch_target_css() -> None:
    assert ".mc-evidence-disclosure summary" in MISSION_CONTROL_CSS
    assert "min-height: 44px" in MISSION_CONTROL_CSS


def test_trade_operations_compacts_execution_and_lifecycle() -> None:
    body = render_trade_operations({
        "trading": {
            "execution_status": "BLOCKED",
            "execution_quality": "UNKNOWN",
            "slippage": "DATA UNAVAILABLE",
            "fees": 0.0,
            "fills": [],
            "rejections": [],
        },
        "decision_panel": {"status": "BLOCKED", "read_only": True},
        "execution_committee": {
            "execution_quality": "UNKNOWN",
            "latency": 0.0,
            "slippage": "DATA UNAVAILABLE",
            "routing_quality": {"quality": "UNKNOWN", "slippage": "DATA UNAVAILABLE"},
            "controls": "READ_ONLY_DISABLED",
        },
        "trade_lifecycle": {
            "stages": [
                {"stage": "candidate", "count": 0, "freshness": "DATA UNAVAILABLE", "state_hash": "hash"},
                {"stage": "approved", "count": 5353, "freshness": "DATA UNAVAILABLE", "state_hash": "hash"},
            ],
            "events": [],
        },
    })
    assert "Execution Snapshot" in body
    assert "Lifecycle Summary" in body
    assert "<summary>Show full execution committee evidence</summary>" in body
    assert "<summary>Show full execution-quality evidence</summary>" in body
    assert "<summary>Show full lifecycle evidence</summary>" in body
    lifecycle_start = body.find("Lifecycle Summary")
    execution_full = body.find("<summary>Show full execution committee evidence</summary>")
    lifecycle_full = body.find("Trade Lifecycle Evidence (Full)")
    assert 0 <= lifecycle_start < execution_full < lifecycle_full
    compact = body[lifecycle_start:execution_full]
    assert "candidate" in compact
    assert "approved" in compact
    assert "5353" in compact
    assert "state_hash" not in compact
    assert "provenance" not in compact


def test_runtime_operations_mobile_priority_and_disclosures_are_read_only() -> None:
    body = render_runtime_operations({
        "runtime": {
            "runtime_status": "DISABLED",
            "runtime_mode": "ADVISORY",
            "engine_mode": "PAPER",
            "cycle": 12,
            "heartbeat": "STALE",
            "heartbeat_status": "FAIL_CLOSED",
            "source": "RUNTIME",
            "subsystem_health": {"certification": "NOT_READY"},
            "controls": {"execution": "DISABLED"},
        },
        "system_metrics": {"cpu": "12%", "memory": "40%"},
        "operations_timeline": {"events": [{"event": "sample"}]},
        "event_stream": {"event_count": 1, "alert_count": 1, "queue_depth": 0, "source": "RUNTIME"},
        "source_consistency": {"status": "UNKNOWN"},
    })
    assert 'aria-label="Runtime Operations sections"' in body
    assert 'aria-label="Runtime Operations priority"' in body
    assert 'href="#mc-runtime-health"' in body
    assert 'href="#mc-runtime-metrics"' in body
    assert 'href="#mc-runtime-timeline"' in body
    assert 'href="#mc-runtime-evidence"' in body
    assert body.find("<span>Runtime Status</span>") < body.find("<span>Engine Mode</span>")
    assert "Runtime Snapshot" in body
    assert "System Metrics" in body
    assert "<summary>Show operations timeline</summary>" in body
    assert "<summary>Show source-consistency evidence</summary>" in body
    assert "<summary>Show full runtime counter evidence</summary>" in body
    assert "<summary>Show disabled controls</summary>" in body
    assert "<details open" not in body
    assert "<form" not in body
    assert "method=" not in body


def test_runtime_operations_prioritizes_heartbeat_status_and_marks_missing_engine_mode() -> None:
    body = render_runtime_operations({
        "runtime": {
            "runtime_status": "STALE",
            "runtime_mode": "DISABLED",
            "engine_mode": None,
            "cycle": 6,
            "heartbeat": "2026-08-22T01:33:35+00:00",
            "heartbeat_status": "STALE",
            "source": "RUNTIME",
            "subsystem_health": {"certification": "RED"},
        }
    })
    assert "<span>Heartbeat Status</span><strong>STALE</strong>" in body
    assert "<span>Heartbeat At</span><strong>2026-08-22T01:33:35+00:00</strong>" in body
    assert '<span>Engine Mode</span><strong>UNAVAILABLE</strong><em class="mc-status bad">UNAVAILABLE</em>' in body
    assert body.find("<span>Heartbeat Status</span>") < body.find("<span>Heartbeat At</span>")


def test_portfolio_mobile_priority_and_evidence_disclosures_are_read_only() -> None:
    body = render_portfolio({
        "portfolio": {
            "equity": "UNAVAILABLE",
            "cash": "UNAVAILABLE",
            "buying_power": "UNAVAILABLE",
            "total_exposure": "UNAVAILABLE",
            "capital_available": "UNAVAILABLE",
            "drawdown": "UNAVAILABLE",
            "asset_allocation": {},
            "sector_allocation": {},
            "currency_exposure": {},
        },
        "portfolio_command": {
            "available_capital": "UNAVAILABLE",
            "deployed_capital": "UNAVAILABLE",
            "capital_utilization": "UNAVAILABLE",
            "collateral": "UNAVAILABLE",
            "state_hash": "hash",
        },
        "capital_allocation_center": {"state_hash": "hash"},
        "performance_attribution": {},
        "capital_committee": {},
    })
    assert 'aria-label="Portfolio sections"' in body
    assert 'aria-label="Portfolio priority"' in body
    assert 'href="#mc-portfolio-capital"' in body
    assert 'href="#mc-portfolio-allocation"' in body
    assert 'href="#mc-portfolio-committee"' in body
    assert 'href="#mc-portfolio-attribution"' in body
    assert "Capital Snapshot" in body
    assert "Allocation Snapshot" in body
    assert "Capital Committee Snapshot" in body
    assert "Performance Attribution Snapshot" in body
    assert "<summary>Show full portfolio command evidence</summary>" in body
    assert "<summary>Show full capital-allocation evidence</summary>" in body
    assert '<span>Equity</span><strong>UNAVAILABLE</strong><em class="mc-status bad">UNAVAILABLE</em>' in body
    assert "<details open" not in body
    assert "<form" not in body
    assert "method=" not in body


def test_portfolio_numeric_metrics_use_semantic_status_not_value_echo() -> None:
    body = render_portfolio({
        "portfolio": {
            "equity": 601.0005,
            "cash": 596.7317,
            "buying_power": 596.7317,
            "total_exposure": 0.0,
            "capital_available": 601.0005,
            "drawdown": "UNAVAILABLE",
        },
        "performance_attribution": {
            "broker_attribution": {"broker_quality": "DATA UNAVAILABLE"},
            "execution_attribution": {"quality": "UNKNOWN", "slippage": "DATA UNAVAILABLE"},
            "risk_attribution": {"risk_state": "RED", "drawdown": "UNAVAILABLE"},
        },
    })
    assert '<span>Equity</span><strong>601.0005</strong><em class="mc-status neutral">RECORDED</em>' in body
    assert '<span>Total Exposure</span><strong>0.0</strong><em class="mc-status neutral">RECORDED</em>' in body
    assert '<span>Drawdown</span><strong>UNAVAILABLE</strong><em class="mc-status bad">UNAVAILABLE</em>' in body
    assert "<strong>601.0005</strong><em class=\"mc-status neutral\">601.0005</em>" not in body
    assert "broker_quality" in body
    assert "execution_quality" in body
    assert "execution_slippage" in body
    assert "risk_state" in body
    assert "risk_drawdown" in body
    assert "{&#x27;broker_quality&#x27;" not in body


def test_market_intelligence_mobile_priority_and_disclosure_are_read_only() -> None:
    body = render_market_intelligence({
        "market_intelligence": {
            "market_regime": "DISABLED",
            "trend": "UNAVAILABLE",
            "volatility": "NORMAL",
            "liquidity": "UNAVAILABLE",
            "momentum": "UNAVAILABLE",
            "signal_confluence": "CONFIRMED",
            "pressure": "UNKNOWN",
            "probability": "UNKNOWN",
            "velocity": "UNKNOWN",
            "vwap_state": "UNAVAILABLE",
            "spread_quality": "TIGHT",
            "execution_cost_state": "UNKNOWN",
            "asset_class_rankings": [],
            "watchlists": [],
            "market_data_freshness": "DATA UNAVAILABLE",
        },
        "opportunity_ranking": {"opportunities": []},
    })
    assert 'aria-label="Market Intelligence sections"' in body
    assert 'aria-label="Market Intelligence priority"' in body
    assert 'href="#mc-market-snapshot"' in body
    assert 'href="#mc-market-rankings"' in body
    assert 'href="#mc-market-opportunities"' in body
    assert "Market Snapshot" in body
    assert "Rankings &amp; Watchlists" in body
    assert "Top Opportunity Snapshot" in body
    assert "<summary>Show full signal-surface evidence</summary>" in body
    assert "<details open" not in body
    assert "<form" not in body
    assert "method=" not in body


def test_market_intelligence_compacts_opportunity_rows() -> None:
    body = render_market_intelligence({
        "market_intelligence": {
            "market_regime": "DISABLED",
            "trend": "UNAVAILABLE",
            "volatility": "NORMAL",
            "liquidity": "UNAVAILABLE",
        },
        "opportunity_ranking": {
            "opportunities": [{
                "symbol": "DATA UNAVAILABLE",
                "asset_class": "DATA UNAVAILABLE",
                "confidence": "DATA UNAVAILABLE",
                "expected_quality": "UNKNOWN",
                "risk": "DATA UNAVAILABLE",
                "blocking_reason": "BLOCKED",
                "committee_outcome": "PASS",
                "ranking": 1,
                "freshness": "DATA UNAVAILABLE",
                "source": "RUNTIME",
                "source_module": "dashboard.mission_control.opportunity_ranking.opportunity",
                "provenance": {"large": "payload"},
                "runtime_id": "runtime",
                "state_hash": "hash",
                "decision_hash": "hash",
            }]
        },
    })
    assert "Top Opportunity Snapshot" in body
    assert "<summary>Show full opportunity evidence</summary>" in body
    snapshot_start = body.find("Top Opportunity Snapshot")
    full_start = body.find("<summary>Show full opportunity evidence</summary>")
    assert 0 <= snapshot_start < full_start
    compact = body[snapshot_start:full_start]
    for value in ("symbol", "asset_class", "confidence", "expected_quality", "risk", "blocking_reason", "committee_outcome", "ranking", "freshness"):
        assert value in compact
    assert "provenance" not in compact
    assert "runtime_id" not in compact
    assert "state_hash" not in compact
    assert "decision_hash" not in compact


def test_market_intelligence_top_opportunity_is_vertical_mobile_snapshot() -> None:
    body = render_market_intelligence({
        "market_intelligence": {},
        "opportunity_ranking": {
            "opportunities": [{
                "symbol": "ABC",
                "asset_class": "EQUITY",
                "confidence": "LOW",
                "expected_quality": "UNKNOWN",
                "risk": "HIGH",
                "blocking_reason": "BLOCKED",
                "committee_outcome": "PASS",
                "ranking": 1,
                "freshness": "STALE",
                "provenance": {"large": "payload"},
            }]
        },
    })
    start = body.find("Top Opportunity Snapshot")
    end = body.find("<summary>Show full opportunity evidence</summary>")
    assert 0 <= start < end
    compact = body[start:end]
    assert "<th>opportunity_count</th><td>1</td>" in compact
    assert "<th>symbol</th><td>ABC</td>" in compact
    assert "<th>ranking</th><td>1</td>" in compact
    assert "<thead>" not in compact
    assert "provenance" not in compact


def test_certification_mobile_priority_and_disclosures_are_read_only() -> None:
    body = render_certification_readiness({
        "certification": {
            "rc1_platform_certification": "PASS",
            "rc1_operational_readiness": "NOT_READY",
            "options_income_certification": "UNAVAILABLE",
            "broker_readiness": "RED",
            "runtime_readiness": "STALE",
            "ready_for_live_trading": False,
            "ready_for_controlled_rc1_runtime": True,
            "blockers": ["runtime stale"],
            "warnings": [],
            "live_disable_proof": {"execution": "BLOCKED"},
        },
        "governance_summary_console": {
            "write_routes_enabled": False,
            "operator_actions_enabled": False,
        },
        "final_certification": {
            "overall": "NOT_CERTIFIED",
            "checks": [],
        },
    })
    assert 'aria-label="Certification sections"' in body
    assert 'aria-label="Certification priority"' in body
    assert "Readiness Snapshot" in body
    assert "Blockers &amp; Warnings" in body
    assert "Governance Snapshot" in body
    assert "<summary>Show live-disable proof</summary>" in body
    assert "<summary>Show final certification evidence</summary>" in body
    assert "<summary>Show final certification checks</summary>" in body
    assert "<details open" not in body
    assert "<form" not in body
    assert "method=" not in body


def test_audit_explainability_mobile_hierarchy_and_disclosures_are_read_only() -> None:
    body = render_audit_explainability({
        "decision_explanation": {
            "decision": "BLOCKED",
            "plain_language": "Trade blocked",
            "blocking_subsystem": "RISK",
            "blocking_rule": "R7",
            "required_improvement": "Fresh runtime evidence",
        },
        "committee_view": {"committees": []},
        "counterfactuals": {"counterfactuals": []},
        "recommendation_panel": {"recommendations": []},
        "evidence_graph": {"status": "UNAVAILABLE", "nodes": [], "edges": [], "source_consistency": "STALE"},
        "audit": {"warnings": [], "failures": []},
        "audit_console": {},
        "change_history_console": {"changes": []},
    })
    assert 'aria-label="Audit and Explainability sections"' in body
    assert "Decision Explanation" in body
    assert "Committee Snapshot" in body
    assert "Operator Guidance" in body
    assert "Evidence Snapshot" in body
    assert "<summary>Show counterfactual evidence</summary>" in body
    assert "<summary>Show recommendation evidence</summary>" in body
    assert "<summary>Show evidence graph</summary>" in body
    assert "<summary>Show full decision evidence</summary>" in body
    assert "<summary>Show audit trail</summary>" in body
    assert "<summary>Show audit center evidence</summary>" in body
    assert "<summary>Show change history</summary>" in body
    assert "<details open" not in body
    assert "<form" not in body
    assert "method=" not in body


def test_audit_explainability_compacts_committee_guidance_and_consistency() -> None:
    body = render_audit_explainability({
        "committee_view": {
            "committees": [{
                "committee": "Risk Committee",
                "outcome": "NOT EVALUATED",
                "reason": "DATA UNAVAILABLE",
                "freshness": "DATA UNAVAILABLE",
                "source": "RUNTIME",
                "source_module": "module",
                "provenance": {"large": "payload"},
                "runtime_id": "runtime",
                "state_hash": "hash",
            }]
        },
        "recommendation_panel": {
            "recommendations": [{
                "action": "Increase evidence",
                "reason": "BLOCKED",
                "authority": "ADVISORY_ONLY",
                "changes_execution": False,
            }]
        },
        "evidence_graph": {
            "status": "PASS",
            "source_consistency": {"runtime_id": "runtime", "state_hash": "hash", "decision_id": "decision:latest"},
            "nodes": [1, 2],
            "edges": [1],
        },
        "counterfactuals": {"counterfactuals": []},
        "audit": {"warnings": [], "failures": []},
    })
    committee_start = body.find("Committee Snapshot")
    guidance_start = body.find("Operator Guidance")
    committee_compact = body[committee_start:guidance_start]
    assert "Risk Committee" in committee_compact
    assert "NOT EVALUATED" in committee_compact
    assert "provenance" not in committee_compact
    assert "runtime_id" not in committee_compact
    assert "state_hash" not in committee_compact
    assert "<th>top_action</th><td>Increase evidence</td>" in body
    assert "<th>top_reason</th><td>BLOCKED</td>" in body
    evidence_start = body.find("Evidence Snapshot")
    counterfactual_start = body.find("<summary>Show counterfactual evidence</summary>")
    compact_evidence = body[evidence_start:counterfactual_start]
    assert "<th>source_consistency</th><td>RECORDED</td>" in compact_evidence
    assert "decision:latest" not in compact_evidence


def test_audit_committee_snapshot_is_vertical_for_mobile() -> None:
    body = render_audit_explainability({
        "committee_view": {
            "committees": [
                {"committee": "Investment Committee", "outcome": "NOT EVALUATED", "reason": "DATA UNAVAILABLE", "freshness": "DATA UNAVAILABLE"},
                {"committee": "Risk Committee", "outcome": "NOT EVALUATED", "reason": "DATA UNAVAILABLE", "freshness": "DATA UNAVAILABLE"},
            ]
        }
    })
    start = body.find("Committee Snapshot")
    end = body.find("Operator Guidance")
    compact = body[start:end]
    assert "<th>Investment Committee</th><td>NOT EVALUATED | DATA UNAVAILABLE | DATA UNAVAILABLE</td>" in compact
    assert "<th>Risk Committee</th><td>NOT EVALUATED | DATA UNAVAILABLE | DATA UNAVAILABLE</td>" in compact
    assert "<thead>" not in compact

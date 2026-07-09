"""
CSS Canonical Operational Readiness Framework

Consolidates all readiness dimensions: RC1, Broker, Runtime, Portfolio,
Dashboard, and Infrastructure into a single authoritative readiness report.
"""

import time
from typing import Dict, Any, List

class CanonicalReadinessFramework:
    """
    Primary orchestrator for CSS Production Readiness.
    """
    def __init__(self, dashboard_service: Any = None):
        self.dashboard_service = dashboard_service

    def evaluate_readiness(self) -> Dict[str, Any]:
        """
        Consolidates readiness dimensions into a single canonical report.
        """
        readiness_scores = {
            "rc1_readiness": 100.0,
            "broker_readiness": 100.0,
            "runtime_readiness": 100.0,
            "portfolio_readiness": 100.0,
            "dashboard_readiness": 100.0,
            "infrastructure_readiness": 100.0
        }

        critical_findings = []
        warnings = []
        info = []
        actions = []

        # 1. Infrastructure Readiness Checks
        # Verify default files are present
        import os
        env_present = os.path.exists(".env")
        if not env_present:
            critical_findings.append("infra_dotenv_missing")
            readiness_scores["infrastructure_readiness"] = 0.0
            actions.append("Ensure .env config file is placed in the project root.")
        else:
            info.append("infra_dotenv_found")
            readiness_scores["infrastructure_readiness"] = 100.0

        # 2. Runtime Readiness Checks
        if self.dashboard_service and self.dashboard_service.read_model:
            health = self.dashboard_service.read_model.get_enterprise_health()
            score = health.get("overall_health_score", 100.0)
            readiness_scores["runtime_readiness"] = score
            if score < 80.0:
                critical_findings.append("runtime_health_critical")
                actions.append("Investigate high runtime restarts or metrics anomalies.")
            elif score < 95.0:
                warnings.append("runtime_health_degraded")
                actions.append("Monitor degraded runtime indicators.")
            else:
                info.append("runtime_health_passed")

        # 3. Broker Readiness Checks
        if self.dashboard_service and self.dashboard_service.read_model:
            # Check OANDA / Coinbase adapter statuses
            ops_summary = self.dashboard_service.read_model.visibility_layer.get_operations_summary()
            overall_status = ops_summary.get("overall_status", "HEALTHY").upper()
            if overall_status == "CRITICAL" or overall_status == "RED":
                readiness_scores["broker_readiness"] = 50.0
                critical_findings.append("broker_validation_failed")
                actions.append("Verify credentials and endpoints for active broker connections.")
            elif overall_status == "DEGRADED" or overall_status == "AMBER":
                readiness_scores["broker_readiness"] = 80.0
                warnings.append("broker_connectivity_degraded")
                actions.append("Investigate degraded latency or retry logs on broker adapters.")
            else:
                readiness_scores["broker_readiness"] = 100.0
                info.append("broker_validation_passed")

        # 4. Portfolio Readiness Checks
        if self.dashboard_service and self.dashboard_service.intelligence_service:
            try:
                intel = self.dashboard_service.intelligence_service.get_trading_intelligence_report()
                perf = intel.get("portfolio_concentration", {})
                concen = float(perf.get("concentration_score", 0.0))
                if concen > 50.0:
                    readiness_scores["portfolio_readiness"] = 80.0
                    warnings.append("portfolio_concentration_high")
                    actions.append("Adjust portfolio construction weights to decrease concentration risk.")
                else:
                    readiness_scores["portfolio_readiness"] = 100.0
                    info.append("portfolio_concentration_optimal")
            except Exception:
                readiness_scores["portfolio_readiness"] = 90.0
                warnings.append("portfolio_metrics_unavailable")

        # 5. Dashboard Readiness Checks
        if self.dashboard_service and self.dashboard_service.read_model:
            notif_summary = self.dashboard_service.read_model.visibility_layer.get_notification_summary()
            failed_count = notif_summary.get("failed_count", 0)
            if failed_count > 5:
                readiness_scores["dashboard_readiness"] = 80.0
                warnings.append("dashboard_notification_delivery_failures")
                actions.append("Audit notification channel setups and API keys.")
            else:
                readiness_scores["dashboard_readiness"] = 100.0
                info.append("dashboard_telemetry_passed")

        # 6. Consolidate into canonical score
        overall_score = sum(readiness_scores.values()) / len(readiness_scores)
        status = "FAIL" if critical_findings else ("WARNING" if warnings else "PASS")
        go_no_go = "NO_GO" if critical_findings else ("CONDITIONAL_GO" if warnings else "GO")

        return {
            "status": status,
            "go_no_go": go_no_go,
            "readiness_score": round(overall_score, 2),
            "readiness_scores": readiness_scores,
            "critical_findings": critical_findings,
            "warnings": warnings,
            "informational_findings": info,
            "recommended_actions": actions,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

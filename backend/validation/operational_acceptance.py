"""
CSS Operational Acceptance Testing Framework

Performs comprehensive validation across eight operational acceptance dimensions
to generate a consolidated operational acceptance result.
"""

from typing import Dict, Any, List

class OperationalAcceptanceFramework:
    """
    Unified Operational Acceptance Testing Framework.
    """
    def __init__(self, dashboard_service: Any = None):
        self.dashboard_service = dashboard_service

    def validate_acceptance(self) -> Dict[str, Any]:
        """
        Runs operational acceptance validation across all eight dimensions.
        """
        results = {
            "runtime_stability": "PASS",
            "broker_connectivity": "PASS",
            "portfolio_integrity": "PASS",
            "dashboard_integrity": "PASS",
            "reporting_integrity": "PASS",
            "audit_integrity": "PASS",
            "validation_integrity": "PASS",
            "readiness_integrity": "PASS"
        }

        failures = []

        # 1. Runtime stability check
        if self.dashboard_service and self.dashboard_service.read_model:
            health = self.dashboard_service.read_model.get_enterprise_health()
            if health.get("restart_count", 0) > 10:
                results["runtime_stability"] = "FAIL"
                failures.append("Excessive runtime supervisor restarts detected.")

        # 2. Broker connectivity check
        if self.dashboard_service and self.dashboard_service.read_model:
            ops_summary = self.dashboard_service.read_model.visibility_layer.get_operations_summary()
            overall_status = ops_summary.get("overall_status", "HEALTHY").upper()
            if overall_status == "CRITICAL" or overall_status == "RED":
                results["broker_connectivity"] = "FAIL"
                failures.append("Active broker connections are in critical failure status.")

        # 3. Portfolio integrity check
        if self.dashboard_service and self.dashboard_service.intelligence_service:
            try:
                intel = self.dashboard_service.intelligence_service.get_trading_intelligence_report()
                if "portfolio_concentration" not in intel:
                    results["portfolio_integrity"] = "FAIL"
                    failures.append("Portfolio concentration telemetry is missing.")
            except Exception:
                results["portfolio_integrity"] = "FAIL"
                failures.append("Portfolio intelligence service failed to compile report.")

        # 4. Dashboard integrity check
        if not self.dashboard_service:
            results["dashboard_integrity"] = "FAIL"
            failures.append("Dashboard service instance is missing.")

        # 5. Reporting integrity check
        if self.dashboard_service and self.dashboard_service.read_model:
            try:
                rep_summary = self.dashboard_service.read_model.get_report_status()
                if not isinstance(rep_summary, dict):
                    results["reporting_integrity"] = "FAIL"
                    failures.append("Report history logs are malformed.")
            except Exception:
                results["reporting_integrity"] = "FAIL"

        # 6. Audit integrity check
        if self.dashboard_service:
            try:
                audit_trail = self.dashboard_service.get_audit_intelligence_view()
                if not isinstance(audit_trail, dict):
                    results["audit_integrity"] = "FAIL"
                    failures.append("Audit trail log partition failed.")
            except Exception:
                results["audit_integrity"] = "FAIL"

        # 7. Validation integrity check
        if self.dashboard_service:
            try:
                val = self.dashboard_service.get_production_validation_view()
                if val.get("status") == "FAIL":
                    results["validation_integrity"] = "FAIL"
                    failures.append("Production validation framework reported failures.")
            except Exception:
                results["validation_integrity"] = "FAIL"

        # 8. Readiness integrity check
        if self.dashboard_service:
            try:
                readiness = self.dashboard_service.get_canonical_readiness_view()
                if readiness.get("status") == "FAIL":
                    results["readiness_integrity"] = "FAIL"
                    failures.append("Canonical readiness engine reported FAIL.")
            except Exception:
                results["readiness_integrity"] = "FAIL"

        status = "FAIL" if any(val == "FAIL" for val in results.values()) else "PASS"

        return {
            "status": status,
            "results": results,
            "failures": failures
        }

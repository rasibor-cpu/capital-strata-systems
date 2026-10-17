import unittest

from backend.app.brokers.ngx_bridge import (
    BROKERS, SOURCE_CATALOG, NGXSource, reconcile_ngx_positions,
    summarize_pension_snapshot,
)


class NGXBridgeTests(unittest.TestCase):
    def test_four_brokers_and_registrar_disabled(self):
        self.assertEqual(len(BROKERS), 4)
        self.assertEqual(len(SOURCE_CATALOG), 6)
        self.assertTrue(all(not source.execution_allowed for source in SOURCE_CATALOG))
        self.assertTrue(all(source.api_status == "not_authorized" for source in SOURCE_CATALOG))

    def test_consolidation_and_registrar_no_double_count(self):
        result = reconcile_ngx_positions(
            [
                {"broker": "investment_one", "account_key": "alias-a", "symbol": "UBA", "quantity": "100"},
                {"broker": "coronation_securities", "account_key": "alias-b", "symbol": "UBA", "quantity": "50"},
            ],
            [{"registrar": "gt_registrars", "symbol": "UBA", "quantity": "150"}],
        )
        self.assertEqual(result["consolidated_quantities"]["UBA"], "150")
        self.assertEqual(result["registrar_corroboration"][0]["status"], "MATCH")
        self.assertFalse(result["registrar_quantities_included_in_portfolio"])
        self.assertFalse(result["execution_allowed"])

    def test_duplicate_snapshot_rejected(self):
        position = {"broker": "meristem", "account_key": "alias-a", "symbol": "GTCO", "quantity": "20"}
        with self.assertRaises(ValueError):
            reconcile_ngx_positions([position, position])

    def test_invalid_quantities_rejected(self):
        for value in ("NaN", "Infinity", "-2", None, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                reconcile_ngx_positions([{
                    "broker": "cardinalstone", "account_key": "alias", "symbol": "UBA",
                    "quantity": value,
                }])

    def test_unapproved_source_or_execution_rejected(self):
        with self.assertRaises(ValueError):
            NGXSource("unknown", "broker")
        with self.assertRaises(ValueError):
            NGXSource("investment_one", "broker", execution_allowed=True)
        with self.assertRaises(ValueError):
            NGXSource("investment_one", "broker", api_status="connected")


if __name__ == "__main__":
    unittest.main()


class PensionBridgeTests(unittest.TestCase):
    def test_pension_is_not_trading_capital(self):
        result = summarize_pension_snapshot({"provider": "stanbic_ibtc_pension_managers",
                                            "account_key": "pension-alias", "balance": "150000"})
        self.assertEqual(result["balance"], "150000")
        self.assertFalse(result["included_in_trading_capital"])
        self.assertFalse(result["execution_allowed"])

    def test_bad_pension_balance_rejected(self):
        for value in ("NaN", "-1", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                summarize_pension_snapshot({"provider": "stanbic_ibtc_pension_managers",
                                            "account_key": "alias", "balance": value})

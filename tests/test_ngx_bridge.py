import unittest

from backend.app.brokers.ngx_bridge import (
    BROKERS, SOURCE_CATALOG, NGXSource, reconcile_ngx_positions,
    summarize_pension_snapshot, register_institution,
    summarize_bank_snapshot, CANADIAN_BANKS, CANADIAN_SIMULATION_CAPITAL_CAD,
    CANADIAN_BROKERS, summarize_broker_account,
    US_BANKS, US_BROKERS, summarize_us_institution_account,
    UK_BANKS, UK_BROKERS, summarize_uk_institution_account,
)


class NGXBridgeTests(unittest.TestCase):
    def test_four_brokers_and_registrar_disabled(self):
        self.assertEqual(len(BROKERS), 4)
        self.assertEqual(len(SOURCE_CATALOG), 37)
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
        self.assertEqual(register_institution("my_broker", "broker", display_name="My Broker").api_status, "not_authorized")
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


class ConfigurableInstitutionTests(unittest.TestCase):
    def test_custom_broker_and_registrar(self):
        broker = register_institution("new_broker", "broker", display_name="New Broker")
        self.assertFalse(broker.execution_allowed)
        result = reconcile_ngx_positions([{"broker": "new_broker", "account_key": "alias",
                                           "symbol": "UBA", "quantity": "12"}],
                                         [{"registrar": "another_registrar", "symbol": "UBA",
                                           "quantity": "12"}])
        self.assertEqual(result["consolidated_quantities"]["UBA"], "12")

    def test_invalid_custom_institution_rejected(self):
        with self.assertRaises(ValueError):
            register_institution("bad/id", "broker", display_name="Invalid")
        with self.assertRaises(ValueError):
            register_institution("valid", "exchange", display_name="Invalid kind")


class CanadianBankBridgeTests(unittest.TestCase):
    def test_canadian_bank_directory_is_metadata_only(self):
        self.assertEqual(len(CANADIAN_BANKS), 6)
        self.assertEqual(str(CANADIAN_SIMULATION_CAPITAL_CAD), "14600")
        self.assertEqual(register_institution("my_credit_union", "bank",
                         display_name="Credit Union").api_status, "not_authorized")

    def test_bank_balance_never_funds_simulation(self):
        result = summarize_bank_snapshot({"provider": "rbc", "account_key": "alias",
                                          "balance": "5000", "currency": "CAD"})
        self.assertEqual(result["balance"], "5000")
        self.assertFalse(result["included_in_trading_capital"])
        self.assertFalse(result["execution_allowed"])
        self.assertFalse(result["transfer_authority"])

    def test_user_defined_bank_and_bad_balances(self):
        result = summarize_bank_snapshot({"provider": "my_credit_union",
                                          "account_key": "alias", "balance": "25"})
        self.assertEqual(result["currency"], "CAD")
        for value in ("NaN", "-1", None, "Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                summarize_bank_snapshot({"provider": "td", "account_key": "alias",
                                         "balance": value})


class CanadianBrokerTests(unittest.TestCase):
    def test_questrade_registered_as_broker_not_bank(self):
        self.assertIn("questrade", CANADIAN_BROKERS)
        source = next(s for s in SOURCE_CATALOG if s.source_id == "questrade")
        self.assertEqual(source.kind, "broker")
        self.assertEqual(source.api_status, "not_authorized")
        self.assertFalse(source.execution_allowed)

    def test_read_only_questrade_account(self):
        result = summarize_broker_account({"provider": "questrade",
                                           "account_key": "qt-alias", "currency": "CAD"})
        self.assertEqual(result["connection_status"], "NOT_AUTHORIZED")
        self.assertFalse(result["execution_allowed"])
        self.assertFalse(result["transfer_authority"])


class USInstitutionBridgeTests(unittest.TestCase):
    def test_us_directory_is_not_a_connector(self):
        self.assertEqual(len(US_BANKS), 6)
        self.assertEqual(len(US_BROKERS), 7)
        self.assertTrue(all(not entry.execution_allowed for entry in SOURCE_CATALOG))
        self.assertEqual(register_institution("local_credit_union", "bank",
                         display_name="Local Credit Union").api_status, "not_authorized")

    def test_us_bank_and_broker_funding_denied(self):
        for provider, kind in (("chase", "bank"), ("fidelity", "broker"), ("alpaca", "broker"), ("oanda", "broker"),
                               ("custom_us_bank", "bank")):
            with self.subTest(provider=provider):
                result = summarize_us_institution_account({
                    "provider": provider, "kind": kind, "account_key": "alias", "currency": "USD"})
                self.assertFalse(result["transfer_authority"])
                self.assertFalse(result["ach_authority"])
                self.assertFalse(result["wire_authority"])
                self.assertFalse(result["execution_allowed"])

    def test_us_account_validation(self):
        for bad in ("NaN", "CAD", ""):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                summarize_us_institution_account({
                    "provider": "chase", "kind": "bank", "account_key": "alias", "currency": bad})


class UKInstitutionBridgeTests(unittest.TestCase):
    def test_uk_directory_and_custom_provider(self):
        self.assertEqual(len(UK_BANKS), 8)
        self.assertEqual(len(UK_BROKERS), 3)
        self.assertEqual(register_institution("my_building_society", "bank",
                         display_name="Building Society").api_status, "not_authorized")

    def test_gbp_and_funding_controls(self):
        for provider, kind in (("barclays", "bank"), ("aj_bell", "broker")):
            result = summarize_uk_institution_account({
                "provider": provider, "kind": kind, "account_key": "alias", "currency": "GBP"})
            self.assertFalse(result["transfer_authority"])
            self.assertFalse(result["open_banking_payment_authority"])
            self.assertFalse(result["execution_allowed"])
        with self.assertRaises(ValueError):
            summarize_uk_institution_account({
                "provider": "barclays", "kind": "bank", "account_key": "alias", "currency": "CAD"})

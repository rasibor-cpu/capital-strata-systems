from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.trading.canonical_futures_repository import CanonicalFuturesRepository
from backend.trading.canonical_options_repository import CanonicalOptionsRepository
from backend.trading.derivatives_models import DerivativesMarketSnapshot, serialize_derivatives
from backend.trading.futures_contract import CanonicalFuturesContract
from backend.trading.greeks_engine import GreeksEngine
from backend.trading.option_contract import CanonicalOptionContract


class _OptionsAdapter:
    def fetch_option_chain(self, underlying_symbol: str):
        if underlying_symbol != "SPY":
            return []
        return [
            {
                "underlying_symbol": "SPY",
                "option_symbol": "SPY-20260717-C-600",
                "expiration_date": "2026-07-17",
                "strike": 600.0,
                "option_type": "call",
                "bid": 4.0,
                "ask": 4.4,
                "last": 4.2,
                "volume": 250,
                "open_interest": 1300,
                "implied_volatility": 0.25,
                "delta": 0.51,
                "gamma": 0.02,
                "theta": -0.03,
                "vega": 0.14,
                "rho": 0.06,
                "intrinsic_value": 0.0,
                "exchange": "CBOE",
                "multiplier": 100,
                "currency": "USD",
                "timestamp": "2026-06-26T00:00:00+00:00",
            }
        ]

    def fetch_option_contract(self, option_symbol: str):
        return None

    def search_option_contracts(self, **filters):
        _ = filters
        return self.fetch_option_chain("SPY")


class _FuturesAdapter:
    def fetch_active_contracts(self, root_symbol: str | None = None):
        payload = {
            "root_symbol": "ES",
            "contract_symbol": "ESU2026",
            "expiration": "2026-09-18",
            "exchange": "CME",
            "tick_size": 0.25,
            "point_value": 50.0,
            "bid": 5400.0,
            "ask": 5400.25,
            "last": 5400.0,
            "volume": 12000,
            "open_interest": 300000,
            "active_contract": True,
            "rollover_date": "2026-09-13",
            "timestamp": "2026-06-26T00:00:00+00:00",
        }
        if root_symbol and root_symbol != "ES":
            return []
        return [payload]

    def fetch_futures_contract(self, contract_symbol: str):
        if contract_symbol == "ESU2026":
            return self.fetch_active_contracts("ES")[0]
        return None

    def search_futures_contracts(self, **filters):
        _ = filters
        return self.fetch_active_contracts("ES")


def test_option_normalization_from_adapter_chain():
    repo = CanonicalOptionsRepository(adapter=_OptionsAdapter())

    chain = repo.get_option_chain("SPY")

    assert len(chain) == 1
    contract = chain[0]
    assert contract.option_symbol == "SPY-20260717-C-600"
    assert contract.option_type == "CALL"
    assert contract.midpoint == pytest.approx(4.2)
    assert contract.extrinsic_value == pytest.approx(4.2)
    assert contract.probability_itm == pytest.approx(0.51)


def test_futures_normalization_from_adapter_contracts():
    repo = CanonicalFuturesRepository(adapter=_FuturesAdapter())

    active = repo.get_active_contracts("ES")

    assert len(active) == 1
    contract = active[0]
    assert contract.contract_symbol == "ESU2026"
    assert contract.exchange == "CME"
    assert contract.active_contract is True


def test_greeks_calculation_signals_are_consistent():
    result = GreeksEngine.calculate(
        option_type="CALL",
        spot_price=602.0,
        strike=600.0,
        risk_free_rate=0.04,
        implied_volatility=0.22,
        time_to_expiry_years=30.0 / 365.0,
        option_price=9.2,
    )

    assert 0.0 < result.delta < 1.0
    assert result.gamma > 0.0
    assert result.vega > 0.0
    assert 0.0 <= result.probability_itm <= 1.0
    assert result.extrinsic_value >= 0.0


def test_contract_serialization_round_trip_and_snapshot_serialization():
    option = CanonicalOptionContract.from_dict(
        {
            "underlying_symbol": "SPY",
            "option_symbol": "SPY-20260717-P-550",
            "expiration_date": "2026-07-17",
            "strike": 550,
            "option_type": "PUT",
            "bid": 3.2,
            "ask": 3.4,
            "midpoint": 3.3,
            "last": 3.35,
            "volume": 100,
            "open_interest": 210,
            "implied_volatility": 0.19,
            "delta": -0.42,
            "gamma": 0.015,
            "theta": -0.018,
            "vega": 0.11,
            "rho": -0.03,
            "intrinsic_value": 0.0,
            "extrinsic_value": 3.35,
            "probability_itm": 0.42,
            "exchange": "CBOE",
            "multiplier": 100,
            "currency": "USD",
            "timestamp": "2026-06-26T00:00:00+00:00",
        }
    )
    futures = CanonicalFuturesContract.from_dict(
        {
            "root_symbol": "NQ",
            "contract_symbol": "NQU2026",
            "expiration": "2026-09-18",
            "exchange": "CME",
            "tick_size": 0.25,
            "point_value": 20,
            "bid": 19000,
            "ask": 19000.25,
            "last": 19000,
            "volume": 5000,
            "open_interest": 40000,
            "active_contract": True,
            "rollover_date": "2026-09-13",
            "timestamp": "2026-06-26T00:00:00+00:00",
        }
    )

    option_roundtrip = CanonicalOptionContract.from_dict(option.to_dict())
    futures_roundtrip = CanonicalFuturesContract.from_dict(futures.to_dict())
    assert option_roundtrip == option
    assert futures_roundtrip == futures

    snapshot = DerivativesMarketSnapshot(
        options=[option],
        futures=[futures],
        timestamp=datetime.now(timezone.utc),
    )
    payload = snapshot.to_dict()
    assert payload["options"][0]["option_symbol"] == option.option_symbol
    assert payload["futures"][0]["contract_symbol"] == futures.contract_symbol

    serialized = serialize_derivatives([option], [futures])
    assert len(serialized["options"]) == 1
    assert len(serialized["futures"]) == 1


def test_invalid_contracts_fail_closed():
    with pytest.raises(ValueError):
        CanonicalOptionContract.from_dict(
            {
                "underlying_symbol": "SPY",
                "option_symbol": "SPY-INVALID",
                "expiration_date": "2026-07-17",
                "strike": 600,
                "option_type": "CALL",
                "bid": 5,
                "ask": 4,
                "midpoint": 4.5,
                "last": 4.5,
                "volume": 0,
                "open_interest": 0,
                "implied_volatility": 0.2,
                "delta": 0.5,
                "gamma": 0.01,
                "theta": -0.01,
                "vega": 0.12,
                "rho": 0.02,
                "intrinsic_value": 0,
                "extrinsic_value": 4.5,
                "probability_itm": 0.5,
                "exchange": "CBOE",
                "multiplier": 100,
                "currency": "USD",
                "timestamp": "2026-06-26T00:00:00+00:00",
            }
        )

    with pytest.raises(ValueError):
        CanonicalFuturesContract.from_dict(
            {
                "root_symbol": "ES",
                "contract_symbol": "ESU2026",
                "expiration": "2026-09-18",
                "exchange": "CME",
                "tick_size": -0.25,
                "point_value": 50,
                "bid": 0,
                "ask": 0,
                "last": 0,
                "volume": 0,
                "open_interest": 0,
                "active_contract": True,
                "rollover_date": "2026-09-13",
                "timestamp": "2026-06-26T00:00:00+00:00",
            }
        )


def test_empty_repositories_return_empty_contract_sets():
    options_repo = CanonicalOptionsRepository()
    futures_repo = CanonicalFuturesRepository()

    assert options_repo.get_option_chain("SPY") == []
    assert options_repo.search_contracts(underlying_symbol="SPY") == []
    assert options_repo.get_contract("SPY-20260717-C-600") is None

    assert futures_repo.get_active_contracts("ES") == []
    assert futures_repo.search_contracts(root_symbol="ES") == []
    assert futures_repo.get_contract("ESU2026") is None

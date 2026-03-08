from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from statistics import pstdev
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_FX_UNIVERSE = [
    "EUR_USD",
    "GBP_USD",
    "AUD_USD",
    "NZD_USD",
    "USD_JPY",
    "USD_CHF",
    "USD_CAD",
    "EUR_GBP",
    "EUR_JPY",
    "GBP_JPY",
    "AUD_JPY",
    "NZD_JPY",
    "EUR_CHF",
    "GBP_CHF",
    "EUR_AUD",
    "EUR_CAD",
    "GBP_AUD",
    "AUD_CAD",
    "AUD_CHF",
    "CAD_JPY",
    "CHF_JPY",
    "EUR_NZD",
    "GBP_CAD",
    "GBP_NZD",
    "NZD_CAD",
    "NZD_CHF",
    "CAD_CHF",
]

DEFAULT_HEADERS = {
    "Accept-Datetime-Format": "UNIX",
    "Content-Type": "application/json",
    "User-Agent": "Capital-Strata-Systems/1.0",
}


@dataclass
class FXScannerConfig:
    granularity: str = "M15"
    count: int = 60
    price_component: str = "M"
    top_n: int = 5
    request_timeout_seconds: float = 15.0
    instruments: Optional[List[str]] = None
    min_avg_range_pct: float = 0.0001
    min_abs_spread_from_vwap_pct: float = 0.00001
    vwap_window: int = 20
    debug: bool = True


@dataclass
class FXScanResult:
    instrument: str
    score: float
    last_mid: float
    vwap: float
    spread_from_vwap_pct: float
    volatility_pct: float
    trend_pct: float
    avg_range_pct: float
    candles_used: int


class OandaFXMarketScanner:
    def __init__(
        self,
        api_token: Optional[str] = None,
        config: Optional[FXScannerConfig] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.env_mode = os.getenv("OANDA_ENV", "practice").strip().lower()

        if self.env_mode == "live":
            self.base_url = "https://api-fxtrade.oanda.com/v3"
            env_token = os.getenv("OANDA_LIVE_TOKEN", "")
        else:
            self.base_url = "https://api-fxpractice.oanda.com/v3"
            env_token = os.getenv("OANDA_PRACTICE_TOKEN", "")

        self.api_token = (api_token or env_token).strip()
        self.config = config or FXScannerConfig()
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

        if self.api_token:
            self.session.headers["Authorization"] = f"Bearer {self.api_token}"

    def _debug(self, message: str) -> None:
        if self.config.debug:
            print(message)

    def validate_token(self) -> tuple[bool, str]:
        if not self.api_token:
            return False, f"OANDA token is missing for env={self.env_mode}."

        test_instrument = "EUR_USD"
        url = f"{self.base_url}/instruments/{test_instrument}/candles"
        params = {
            "count": 5,
            "granularity": self.config.granularity,
            "price": self.config.price_component,
        }

        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.config.request_timeout_seconds,
            )
            if response.status_code == 200:
                return True, f"Token validated successfully against OANDA {self.env_mode} environment."
            return (
                False,
                f"Token validation failed on {self.env_mode}: HTTP {response.status_code} | {response.text[:300]}",
            )
        except requests.RequestException as exc:
            return False, f"Token validation request failed: {exc}"

    def get_instruments(self) -> List[str]:
        instruments = self.config.instruments or DEFAULT_FX_UNIVERSE
        out: List[str] = []
        seen = set()
        for instrument in instruments:
            symbol = str(instrument).strip().upper()
            if symbol and symbol not in seen:
                out.append(symbol)
                seen.add(symbol)
        return out

    def get_candles(self, instrument: str) -> List[Dict[str, float]]:
        url = f"{self.base_url}/instruments/{instrument}/candles"
        params = {
            "count": self.config.count,
            "granularity": self.config.granularity,
            "price": self.config.price_component,
        }

        response = self.session.get(
            url,
            params=params,
            timeout=self.config.request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        raw_candles = payload.get("candles", [])

        candles: List[Dict[str, float]] = []
        for row in raw_candles:
            if not row.get("complete", False):
                continue

            mid = row.get("mid") or {}
            try:
                o = float(mid["o"])
                h = float(mid["h"])
                l = float(mid["l"])
                c = float(mid["c"])
            except (KeyError, TypeError, ValueError):
                continue

            candles.append(
                {
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": c,
                }
            )

        return candles

    def compute_vwap_proxy(self, candles: List[Dict[str, float]]) -> Optional[float]:
        if not candles:
            return None

        window = candles[-self.config.vwap_window :]
        weighted_sum = 0.0
        weight_sum = 0.0

        for c in window:
            typical = (c["high"] + c["low"] + c["close"]) / 3.0
            candle_range = max(c["high"] - c["low"], 1e-12)
            weighted_sum += typical * candle_range
            weight_sum += candle_range

        if weight_sum <= 0:
            return None
        return weighted_sum / weight_sum

    def compute_volatility_pct(self, candles: List[Dict[str, float]]) -> float:
        closes = [c["close"] for c in candles if c["close"] > 0]
        if len(closes) < 5:
            return 0.0

        returns_pct: List[float] = []
        for i in range(1, len(closes)):
            prev_close = closes[i - 1]
            curr_close = closes[i]
            ret = ((curr_close / prev_close) - 1.0) * 100.0
            returns_pct.append(ret)

        if len(returns_pct) < 2:
            return 0.0

        return float(pstdev(returns_pct))

    def compute_trend_pct(self, candles: List[Dict[str, float]]) -> float:
        closes = [c["close"] for c in candles if c["close"] > 0]
        if len(closes) < 5:
            return 0.0

        first_close = closes[0]
        last_close = closes[-1]
        if first_close <= 0:
            return 0.0

        return ((last_close / first_close) - 1.0) * 100.0

    def compute_avg_range_pct(self, candles: List[Dict[str, float]]) -> float:
        if len(candles) < 5:
            return 0.0

        values: List[float] = []
        for c in candles:
            close = c["close"]
            if close <= 0:
                continue
            rng_pct = ((c["high"] - c["low"]) / close) * 100.0
            values.append(rng_pct)

        if not values:
            return 0.0
        return sum(values) / len(values)

    def score_instrument(self, instrument: str) -> Optional[FXScanResult]:
        candles = self.get_candles(instrument)
        if len(candles) < max(20, self.config.vwap_window):
            self._debug(f"[SKIP] {instrument}: insufficient candles ({len(candles)})")
            return None

        last_mid = candles[-1]["close"]
        if last_mid <= 0:
            self._debug(f"[SKIP] {instrument}: invalid last price")
            return None

        vwap = self.compute_vwap_proxy(candles)
        if vwap is None or vwap <= 0:
            self._debug(f"[SKIP] {instrument}: invalid VWAP")
            return None

        spread_from_vwap_pct = ((last_mid / vwap) - 1.0) * 100.0
        volatility_pct = self.compute_volatility_pct(candles)
        trend_pct = self.compute_trend_pct(candles)
        avg_range_pct = self.compute_avg_range_pct(candles)

        if avg_range_pct < self.config.min_avg_range_pct:
            self._debug(f"[SKIP] {instrument}: avg_range_pct too low")
            return None

        if abs(spread_from_vwap_pct) < self.config.min_abs_spread_from_vwap_pct:
            self._debug(f"[SKIP] {instrument}: spread_from_vwap too low")
            return None

        trend_penalty = abs(trend_pct) * 0.20
        range_bonus = math.log1p(max(avg_range_pct, 0.0))
        vol_bonus = math.log1p(max(volatility_pct, 0.0))

        score = (
            abs(spread_from_vwap_pct) * 0.55
            + vol_bonus * 1.45
            + range_bonus * 1.15
            - trend_penalty
        )

        self._debug(
            f"[PASS] {instrument}: score={score:.6f}, spread={spread_from_vwap_pct:.6f}%, "
            f"vol={volatility_pct:.6f}%, range={avg_range_pct:.6f}%, trend={trend_pct:.6f}%"
        )

        return FXScanResult(
            instrument=instrument,
            score=round(score, 6),
            last_mid=round(last_mid, 6),
            vwap=round(vwap, 6),
            spread_from_vwap_pct=round(spread_from_vwap_pct, 6),
            volatility_pct=round(volatility_pct, 6),
            trend_pct=round(trend_pct, 6),
            avg_range_pct=round(avg_range_pct, 6),
            candles_used=len(candles),
        )

    def scan_market(self) -> List[FXScanResult]:
        ok, message = self.validate_token()
        self._debug(f"[AUTH] {message}")
        self._debug(f"[INFO] Environment: {self.env_mode}")
        self._debug(f"[INFO] Base URL: {self.base_url}")

        if not ok:
            raise ValueError(message)

        results: List[FXScanResult] = []
        for instrument in self.get_instruments():
            try:
                result = self.score_instrument(instrument)
                if result is not None:
                    results.append(result)
            except requests.HTTPError as exc:
                body = exc.response.text[:300] if exc.response is not None else ""
                self._debug(f"[HTTP ERROR] {instrument}: {exc} {body}")
            except requests.RequestException as exc:
                self._debug(f"[REQUEST ERROR] {instrument}: {exc}")
            except Exception as exc:
                self._debug(f"[ERROR] {instrument}: {exc}")

        results.sort(key=lambda x: x.score, reverse=True)
        return results[: self.config.top_n]


def print_fx_scan_results(results: List[FXScanResult]) -> None:
    print("\n=== CSS FX MARKET SCANNER ===")
    if not results:
        print("No qualifying FX instruments found.")
        return

    for i, r in enumerate(results, start=1):
        print(
            f"{i:>2}. {r.instrument:<10} "
            f"score={r.score:>8.4f}   "
            f"spread={r.spread_from_vwap_pct:>9.6f}%   "
            f"vol={r.volatility_pct:>8.6f}%   "
            f"range={r.avg_range_pct:>8.6f}%   "
            f"trend={r.trend_pct:>9.6f}%"
        )


if __name__ == "__main__":
    scanner = OandaFXMarketScanner(
        config=FXScannerConfig(
            granularity="M15",
            count=60,
            top_n=5,
            min_avg_range_pct=0.0001,
            min_abs_spread_from_vwap_pct=0.00001,
            vwap_window=20,
            debug=True,
        )
    )
    scan_results = scanner.scan_market()
    print_fx_scan_results(scan_results)

    print("\nTop instruments only:")
    for instrument in [r.instrument for r in scan_results]:
        print(instrument)
from __future__ import annotations

import requests
import statistics


COINBASE_API = "https://api.exchange.coinbase.com"


class AIOpportunityScorer:

    def __init__(self):

        self.max_assets = 200

    def _get_products(self):

        url = f"{COINBASE_API}/products"

        r = requests.get(url, timeout=10)

        data = r.json()

        symbols = []

        for p in data:

            if p.get("quote_currency") != "USD":
                continue

            if p.get("status") != "online":
                continue

            symbols.append(p["id"])

        return symbols[: self.max_assets]

    def _get_candles(self, product):

        url = f"{COINBASE_API}/products/{product}/candles"

        params = {"granularity": 900}

        r = requests.get(url, params=params, timeout=10)

        candles = r.json()

        closes = []

        volumes = []

        for c in candles[:20]:

            closes.append(float(c[4]))
            volumes.append(float(c[5]))

        if len(closes) < 10:
            return None

        return closes, volumes

    def _score_asset(self, product):

        data = self._get_candles(product)

        if not data:
            return None

        closes, volumes = data

        momentum = (closes[-1] - closes[0]) / closes[0]

        volatility = statistics.stdev(closes)

        volume_spike = volumes[-1] / (sum(volumes) / len(volumes))

        score = (
            momentum * 40
            + volatility * 20
            + volume_spike * 40
        )

        regime = "TREND"

        if momentum < 0:
            regime = "MEAN_REVERSION"

        return {
            "symbol": product,
            "asset_class": "CRYPTO",
            "signal": "BUY",
            "regime": regime,
            "opportunity_score": round(score, 2),
            "confidence_band": "HIGH",
            "action_priority": "TRADE_NOW",
            "explanation": f"{product} momentum {momentum:.3f} volatility {volatility:.4f} volume spike {volume_spike:.2f}",
        }

    def run(self):

        products = self._get_products()

        results = []

        for p in products:

            try:

                score = self._score_asset(p)

                if score:
                    results.append(score)

            except Exception:
                pass

        results.sort(
            key=lambda x: x["opportunity_score"],
            reverse=True,
        )

        return results[:20]
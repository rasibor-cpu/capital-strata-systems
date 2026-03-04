"""
Coinbase Executor
Capital Strata Systems

Handles:
- Best bid/ask retrieval
- Candle retrieval
- Order creation (paper safe)

Compatible with Coinbase Advanced Trade API
"""

from __future__ import annotations
import json
import os
from typing import Optional, Dict, Any
from coinbase.rest import RESTClient


class CoinbaseExecutor:

    def __init__(self):

        key_file = os.getenv("COINBASE_KEY_FILE", "coinbase_key.json")

        with open(key_file, "r") as f:
            key_data = json.load(f)

        self.client = RESTClient(
            api_key=key_data["name"],
            api_secret=key_data["privateKey"]
        )

    # -------------------------------------------------
    # BEST BID / ASK
    # -------------------------------------------------

    def get_best_bid_ask(self, product_id: str, limit: int = 1) -> Optional[Dict[str, float]]:

        try:
            resp = self.client.get_best_bid_ask(
                product_id=product_id,
                limit=limit
            )

            d = resp if isinstance(resp, dict) else resp.to_dict()

            # Coinbase response shape 1
            if "pricebooks" in d:
                pb = d["pricebooks"][0]
                bid = float(pb["bids"][0]["price"])
                ask = float(pb["asks"][0]["price"])
                return {"bid": bid, "ask": ask}

            # response shape 2
            if "pricebook" in d:
                pb = d["pricebook"]
                bid = float(pb["bids"][0]["price"])
                ask = float(pb["asks"][0]["price"])
                return {"bid": bid, "ask": ask}

            # response shape 3
            if "bids" in d and "asks" in d:
                bid = float(d["bids"][0]["price"])
                ask = float(d["asks"][0]["price"])
                return {"bid": bid, "ask": ask}

            # response shape 4
            if "best_bid" in d and "best_ask" in d:
                bid = float(d["best_bid"])
                ask = float(d["best_ask"])
                return {"bid": bid, "ask": ask}

            return None

        except Exception as e:
            print("BBA_ERROR:", e)
            return None

    # -------------------------------------------------
    # CANDLES
    # -------------------------------------------------

    def get_candles(self, product_id, granularity, start=None, end=None, limit=300):

        try:

            if start and end:

                resp = self.client.get_candles(
                    product_id=product_id,
                    start=start,
                    end=end,
                    granularity=granularity
                )

            else:

                resp = self.client.get_candles(
                    product_id=product_id,
                    granularity=granularity,
                    limit=limit
                )

            return resp if isinstance(resp, dict) else resp.to_dict()

        except Exception as e:
            print("CANDLE_ERROR:", e)
            return None

    # -------------------------------------------------
    # ORDER CREATION
    # -------------------------------------------------

    def create_order(self, product_id, side, quote_size=None, base_size=None):

        mode = os.getenv("TRADE_MODE", "PAPER")

        payload = {
            "product_id": product_id,
            "side": side,
            "order_configuration": {
                "market_market_ioc": {}
            }
        }

        if side == "BUY":
            payload["order_configuration"]["market_market_ioc"]["quote_size"] = str(quote_size)

        if side == "SELL":
            payload["order_configuration"]["market_market_ioc"]["base_size"] = str(base_size)

        if mode != "LIVE":
            return {
                "mode": mode,
                "paper_trade": True,
                "payload": payload
            }

        resp = self.client.create_order(**payload)

        return resp if isinstance(resp, dict) else resp.to_dict()
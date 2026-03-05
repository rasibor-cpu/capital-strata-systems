import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from coinbase.rest import RESTClient


@dataclass
class OrderIntent:
    product_id: str
    side: str
    order_type: str
    quote_size: str | None = None
    base_size: str | None = None


class CoinbaseExecutor:

    def __init__(self):

        with open("coinbase_key.json") as f:
            key = json.load(f)

        self.client = RESTClient(
            api_key=key["name"],
            api_secret=key["privateKey"]
        )

    def get_best_bid_ask(self, product_id, limit=1):

        resp = self.client.get_best_bid_ask(product_id=product_id, limit=limit)

        data = resp if isinstance(resp, dict) else resp.to_dict()

        books = data.get("pricebooks", [])

        for book in books:

            if book.get("product_id") == product_id:

                bid = float(book["bids"][0]["price"])
                ask = float(book["asks"][0]["price"])

                return {"bid": bid, "ask": ask}

        return None

    def get_candles(self, product_id, granularity):

        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=12)

        resp = self.client.get_candles(
            product_id=product_id,
            start=start.isoformat(),
            end=end.isoformat(),
            granularity=granularity
        )

        return resp if isinstance(resp, dict) else resp.to_dict()

    def create_order(self, intent: OrderIntent):

        mode = os.getenv("TRADE_MODE", "PAPER")

        payload = {
            "product_id": intent.product_id,
            "side": intent.side,
            "order_configuration": {
                "market_market_ioc": {}
            }
        }

        if intent.side == "BUY":
            payload["order_configuration"]["market_market_ioc"]["quote_size"] = intent.quote_size

        if intent.side == "SELL":
            payload["order_configuration"]["market_market_ioc"]["base_size"] = intent.base_size

        if mode != "LIVE":
            return {"paper_run": True, "payload": payload}

        resp = self.client.create_order(**payload)

        return resp if isinstance(resp, dict) else resp.to_dict()
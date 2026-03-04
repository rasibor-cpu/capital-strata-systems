"""
oanda_client.py
Capital Strata Systems (CSS)

Minimal OANDA v20 client (LIVE)
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

OANDA_DOMAIN = "https://api-fxtrade.oanda.com"  # LIVE endpoint

ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID")
API_KEY = os.getenv("OANDA_API_KEY")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}


def get_account_summary():
    url = f"{OANDA_DOMAIN}/v3/accounts/{ACCOUNT_ID}/summary"
    r = requests.get(url, headers=HEADERS)
    return r.json()


def get_price(instrument="EUR_USD"):
    url = f"{OANDA_DOMAIN}/v3/accounts/{ACCOUNT_ID}/pricing"
    params = {"instruments": instrument}
    r = requests.get(url, headers=HEADERS, params=params)
    return r.json()


def place_market_order(instrument="EUR_USD", units=1000):
    url = f"{OANDA_DOMAIN}/v3/accounts/{ACCOUNT_ID}/orders"

    data = {
        "order": {
            "type": "MARKET",
            "instrument": instrument,
            "units": str(units),
            "timeInForce": "FOK",
            "positionFill": "DEFAULT"
        }
    }

    r = requests.post(url, headers=HEADERS, json=data)
    return r.json()
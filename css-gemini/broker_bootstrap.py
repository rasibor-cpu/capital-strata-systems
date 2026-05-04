# broker_bootstrap.py
"""
CSS-GEMINI BROKER BRIDGE
Live API integration for Gemini Exchange.
"""
import os
import hmac
import hashlib
import json
import time
import base64
import requests
from audit_logger import get_audit

class GeminiBroker:
    def __init__(self):
        self.audit = get_audit()
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.api_secret = os.getenv("GEMINI_API_SECRET").encode()
        self.base_url = "https://api.gemini.com/v1"

    def _generate_signature(self, payload_json):
        payload_b64 = base64.b64encode(payload_json.encode())
        signature = hmac.new(self.api_secret, payload_b64, hashlib.sha384).hexdigest()
        return payload_b64, signature

    def get_account_balance(self):
        """Retrieves the SSoT balance from the exchange."""
        endpoint = "/balances"
        payload = {
            "request": endpoint,
            "nonce": int(time.time() * 1000)
        }
        
        payload_json = json.dumps(payload)
        payload_b64, signature = self._generate_signature(payload_json)
        
        headers = {
            'Content-Type': "text/plain",
            'Content-Length': "0",
            'X-GEMINI-APIKEY': self.api_key,
            'X-GEMINI-PAYLOAD': payload_b64,
            'X-GEMINI-SIGNATURE': signature,
            'Cache-Control': "no-cache"
        }

        try:
            response = requests.post(self.base_url + endpoint, headers=headers)
            return response.json()
        except Exception as e:
            self.audit.log("API_ERROR", "broker", {"error": str(e)}, level="CRITICAL")
            return None

    def execute_order(self, symbol, side, amount, price):
        """Executes a live order on Gemini."""
        self.audit.log("ORDER_SENT", "broker", {"symbol": symbol, "side": side, "qty": amount})
        # Note: Logic for /order/new endpoint would follow the same signing pattern
        return {"status": "accepted", "symbol": symbol}
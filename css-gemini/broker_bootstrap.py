"""
CSS-GEMINI BROKER BRIDGE
Institutional-grade API integration with Manual Key Parsing & SSoT Safety.
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
        
        # --- MANUAL KEY PARSING ---
        # Forces the system to read .env even if standard loaders fail
        self._load_keys_manually()
        
        self.api_key = os.getenv("GEMINI_API_KEY")
        raw_secret = os.getenv("GEMINI_API_SECRET")
        
        if raw_secret:
            self.api_secret = raw_secret.encode()
            self.audit.log("BOOTSTRAP_INIT", "broker", {"status": "keys_loaded"})
        else:
            self.api_secret = b""
            print("!! CRITICAL: GEMINI_API_SECRET NOT FOUND IN .ENV !!")
            self.audit.log("BOOTSTRAP_FAIL", "broker", {"error": "missing_secret"}, level="CRITICAL")

        self.base_url = "https://api.gemini.com/v1"

    def _load_keys_manually(self):
        """Manually parses .env to handle encoding issues and hidden paths."""
        env_path = os.path.join(os.getcwd(), ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            # Clean quotes and whitespace
                            os.environ[key.strip()] = value.strip().strip("'").strip('"')
            except Exception as e:
                print(f"Manual Load Failed: {e}")

    def _generate_signature(self, payload_json):
        """Standard Gemini API signing protocol."""
        payload_b64 = base64.b64encode(payload_json.encode())
        signature = hmac.new(self.api_secret, payload_b64, hashlib.sha384).hexdigest()
        return payload_b64, signature

    def get_account_balance(self):
        """Retrieves authoritative SSoT balance from the exchange."""
        endpoint = "/v1/balances"
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
            response = requests.post("https://api.gemini.com" + endpoint, headers=headers)
            data = response.json()
            
            if response.status_code == 200:
                self.audit.log("BALANCE_SYNC", "broker", {"status": "success"})
                return data
            else:
                error_msg = data.get('message', 'Unknown API Error')
                print(f"API Error: {error_msg}")
                return {"error": error_msg}
                
        except Exception as e:
            self.audit.log("CONNECTIVITY_FAIL", "broker", {"error": str(e)}, level="CRITICAL")
            return {"error": str(e)}

if __name__ == "__main__":
    print("Starting Institutional Broker Bootstrap...")
    broker = GeminiBroker()
    print("Handshake initiated. Checking SSoT Balance...")
    result = broker.get_account_balance()
    print(json.dumps(result, indent=4))
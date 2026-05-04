import os
import time
import jwt
import json
import requests
from audit_logger import get_audit

class CoinbaseBroker:
    def __init__(self):
        self.audit = get_audit()
        self._load_env_manually()
        
        # SSoT: Path to the clean JSON key file identified in the keys/ directory
        self.json_path = os.getenv("COINBASE_KEY_JSON_PATH")
        self.key_name = None
        self.key_secret = None
        
        self._extract_credentials()

    def _load_env_manually(self):
        env_path = os.path.join(os.getcwd(), ".env")
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip().strip("'").strip('"')

    def _extract_credentials(self):
        """Extracts credentials directly from the Coinbase JSON format."""
        if not self.json_path or not os.path.exists(self.json_path):
            print(f"!! CRITICAL: JSON file not found at {self.json_path} !!")
            return

        try:
            with open(self.json_path, 'r') as f:
                data = json.load(f)
                self.key_name = data.get("name")
                self.key_secret = data.get("privateKey")
                print(f"✅ Extracted SSoT Credentials for: {self.key_name}")
        except Exception as e:
            print(f"!! Extraction Error: {e} !!")

    def _generate_jwt(self):
        if not self.key_secret or not self.key_name:
            return None
        payload = {
            "iss": "coinbase-cloud",
            "nbf": int(time.time()),
            "exp": int(time.time()) + 60,
            "sub": self.key_name,
        }
        return jwt.encode(payload, self.key_secret, algorithm="ES256", headers={"kid": self.key_name})

    def get_account_balance(self):
        token = self._generate_jwt()
        if not token: 
            return {"error": "Handshake Generation Failed"}
        
        url = "https://api.coinbase.com/api/v3/brokerage/accounts"
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            response = requests.get(url, headers=headers)
            print(f"--- Handshake Debug ---")
            print(f"HTTP Status: {response.status_code}")
            
            if response.status_code == 200:
                self.audit.log("BALANCE_SYNC", "broker", {"status": "success"})
                return response.json()
            else:
                print(f"Raw API Message: {response.text}")
                return {"error": f"API Rejected Request - Status {response.status_code}"}
        except Exception as e:
            return {"error": f"Connection/Decode Error: {str(e)}"}

if __name__ == "__main__":
    print("--- Starting CSS-Gemini SSoT Sync ---")
    broker = CoinbaseBroker()
    if broker.key_secret:
        result = broker.get_account_balance()
        print("\n--- Final Result ---")
        print(json.dumps(result, indent=4))
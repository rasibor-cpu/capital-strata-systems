import os
import time
import jwt
import json
import requests

def load_env():
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().strip("'").strip('"')

def clean_handshake():
    load_env()
    json_path = os.getenv("COINBASE_KEY_JSON_PATH")
    
    with open(json_path, 'r') as f:
        data = json.load(f)
        name = data.get("name")
        private_key = data.get("privateKey")

    # Use a wider 2-minute buffer for the handshake to account for clock drift
    curr_time = int(time.time())
    payload = {
        "iss": "coinbase-cloud",
        "nbf": curr_time - 30, # Start 30 seconds in the past
        "exp": curr_time + 90, # End 90 seconds in the future
        "sub": name,
    }
    
    token = jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": name})
    url = "https://api.coinbase.com/api/v3/brokerage/accounts"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"--- Attempting Time-Corrected Handshake ---")
    response = requests.get(url, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

if __name__ == "__main__":
    clean_handshake()
import os
import time
import jwt
import json
import requests
import secrets

def load_env():
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().strip("'").strip('"')

def attempt_fresh_handshake():
    load_env()
    json_path = os.getenv("COINBASE_KEY_JSON_PATH")
    
    with open(json_path, 'r') as f:
        data = json.load(f)
        name = data.get("name")
        private_key = data.get("privateKey")

    # Coinbase often requires a unique nonce for institutional keys
    nonce = secrets.token_hex(16)
    curr_time = int(time.time())
    
    payload = {
        "iss": "coinbase-cloud",
        "nbf": curr_time,
        "exp": curr_time + 60,
        "sub": name,
        "jti": nonce # Added unique token identifier
    }
    
    token = jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": name})
    url = "https://api.coinbase.com/api/v3/brokerage/accounts"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"--- Attempting Fresh SSoT Handshake ---")
    print(f"Nonce generated: {nonce}")
    response = requests.get(url, headers=headers)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ SUCCESS: Brokerage Connection Established.")
    else:
        print(f"Details: {response.text}")

if __name__ == "__main__":
    attempt_fresh_handshake()
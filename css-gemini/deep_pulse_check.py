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

def pulse_check():
    load_env()
    json_path = os.getenv("COINBASE_KEY_JSON_PATH")
    
    with open(json_path, 'r') as f:
        data = json.load(f)
        name = data.get("name")
        private_key = data.get("privateKey")

    # Generate JWT
    payload = {
        "iss": "coinbase-cloud",
        "nbf": int(time.time()) - 5,
        "exp": int(time.time()) + 60,
        "sub": name,
    }
    token = jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": name})
    headers = {"Authorization": f"Bearer {token}"}

    # Test 1: Brokerage Accounts (The one failing)
    print("--- Pulse 1: Accounts ---")
    r1 = requests.get("https://api.coinbase.com/api/v3/brokerage/accounts", headers=headers)
    print(f"Status: {r1.status_code}")

    # Test 2: Product List (Public-facing data requiring auth)
    print("\n--- Pulse 2: Products ---")
    r2 = requests.get("https://api.coinbase.com/api/v3/brokerage/products", headers=headers)
    print(f"Status: {r2.status_code}")
    if r2.status_code == 200:
        print("Success: Key is VALID, but brokerage access is restricted.")
    else:
        print(f"Details: {r2.text}")

if __name__ == "__main__":
    pulse_check()
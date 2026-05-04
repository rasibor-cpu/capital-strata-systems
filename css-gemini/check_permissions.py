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

def check_key_vitals():
    load_env()
    json_path = os.getenv("COINBASE_KEY_JSON_PATH")
    
    if not json_path or not os.path.exists(json_path):
        print("!! JSON Key File Not Found !!")
        return

    with open(json_path, 'r') as f:
        data = json.load(f)
        name = data.get("name")
        private_key = data.get("privateKey")

    # Generate a test JWT for a simple API call
    payload = {
        "iss": "coinbase-cloud",
        "nbf": int(time.time()),
        "exp": int(time.time()) + 60,
        "sub": name,
    }
    token = jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": name})
    
    # Attempt to call the API Key details endpoint
    url = "https://api.coinbase.com/api/v3/brokerage/key_permissions"
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(url, headers=headers)
    print(f"--- Key Vital Check ---")
    print(f"Status: {response.status_code}")
    print(f"Details: {response.text}")

if __name__ == "__main__":
    check_key_vitals()
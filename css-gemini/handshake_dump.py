import os
import json
import time
import jwt

def audit_handshake_contents():
    # Load the path from .env
    env_path = os.path.join(os.getcwd(), ".env")
    json_path = ""
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if "COINBASE_KEY_JSON_PATH" in line:
                    json_path = line.split('=')[1].strip().strip('"').strip("'")

    print(f"--- Handshake Component Audit ---")
    if not os.path.exists(json_path):
        print(f"FAILED: File not found at {json_path}")
        return

    with open(json_path, 'r') as f:
        try:
            data = json.load(f)
            key_name = data.get("name")
            key_secret = data.get("privateKey")
            
            # Coinbase Key IDs must follow the 'organizations/.../apiKeys/...' format
            print(f"Key Name Found: {key_name}")
            if key_name and key_name.startswith("organizations/"):
                print("✅ Key Name Format: Valid Institutional String")
            else:
                print("❌ Key Name Format: Invalid or Unexpected")

            # Check for PEM headers in the private key
            if "BEGIN EC PRIVATE KEY" in key_secret:
                print("✅ Private Key Format: Valid PEM detected")
            else:
                print("❌ Private Key Format: Missing PEM headers")

        except Exception as e:
            print(f"Error reading JSON: {e}")

if __name__ == "__main__":
    audit_handshake_contents()
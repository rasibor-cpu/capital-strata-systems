import os
import sys
import socket
import uvicorn

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def build_startup_config():
    allow_lan = os.environ.get("CSS_MOBILE_LAN", "false").lower() == "true"
    host = "0.0.0.0" if allow_lan else "127.0.0.1"
    port = int(os.environ.get("CSS_MOBILE_PORT", "8090"))
    
    return {
        "app": "dashboard.mobile.mobile_app:app",
        "host": host,
        "port": port,
        "allow_lan": allow_lan
    }

def print_instructions(config):
    port = config["port"]
    print("\n" + "="*50)
    print("CSS MOBILE APP STARTUP")
    print("="*50)
    
    if config["allow_lan"]:
        ip = get_local_ip()
        print(f"LAN Access Enabled: http://{ip}:{port}")
        print("Note: To access from your phone, ensure you are on the same Wi-Fi network.")
    else:
        print(f"Local Access Only: http://127.0.0.1:{port}")
        print("Note: LAN access is disabled. To access from phone, run with CSS_MOBILE_LAN=true")
    
    print("-" * 50)
    print("SAFETY RULES:")
    print("1. Do not arm live mode from your phone.")
    print("2. The mobile app is intended for read-only monitoring and paper-trade management.")
    print("3. No broker credentials will be printed or exposed here.")
    print("4. Press Ctrl+C to safely shut down the mobile dashboard.")
    print("="*50 + "\n")

def main():
    config = build_startup_config()
    print_instructions(config)
    
    uvicorn.run(config["app"], host=config["host"], port=config["port"])

if __name__ == "__main__":
    main()

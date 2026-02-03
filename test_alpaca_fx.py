import os
import requests
import json
from typing import Dict, Any, Optional


def _get_env(name: str) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return None
    v = v.strip()
    return v if v else None


def main() -> int:
    key = _get_env("APCA_API_KEY_ID")
    secret = _get_env("APCA_API_SECRET_KEY")

    if not key or not secret:
        raise RuntimeError(
            "Alpaca API keys not found in environment. "
            "Expected APCA_API_KEY_ID and APCA_API_SECRET_KEY."
        )

    # Correct base endpoint (v1beta1, not v1beta3)
    url = "https://data.alpaca.markets/v1beta1/forex/latest/rates"

    headers = {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
    }

    # Try common parameter names, and auto-lock whichever one works.
    pair_list = "EUR/USD,USD/JPY,GBP/USD"
    candidate_params = [
        {"currency_pairs": pair_list},
        {"pairs": pair_list},
        {"symbols": pair_list},
    ]

    last_status = None
    last_text = None

    for params in candidate_params:
        try:
            r = requests.get(url, headers=headers, params=params, timeout=10)
            last_status = r.status_code
            last_text = r.text

            print("\n--- ATTEMPT ---")
            print("URL:", url)
            print("PARAMS:", params)
            print("HTTP:", r.status_code)

            # Try JSON parse; if not JSON, print raw
            try:
                payload: Dict[str, Any] = r.json()
                print(json.dumps(payload, indent=2))

                if 200 <= r.status_code < 300:
                    # Show a quick “shape probe” so we know what keys to parse in the adapter
                    top_keys = list(payload.keys())
                    print("\nOK ✅  Endpoint+param accepted.")
                    print("Top-level keys:", top_keys)

                    # Try to locate likely rates container
                    # We won’t assume the exact schema; just print a small preview.
                    preview = None
                    for k in ["rates", "data", "result"]:
                        if isinstance(payload.get(k), dict):
                            preview = payload[k]
                            print(f"Preview container: {k} (dict)")
                            break

                    if preview is not None:
                        # Print up to 2 items
                        items = list(preview.items())[:2]
                        print("Preview items (first 2):")
                        for sym, val in items:
                            print(" ", sym, "=>", val)
                    return 0

            except Exception:
                print("(Non-JSON response)")
                print(r.text[:800])

        except Exception as e:
            print("\n--- ATTEMPT FAILED (exception) ---")
            print("PARAMS:", params)
            print("ERR:", repr(e))

    print("\nFAILED ❌  None of the parameter variants worked.")
    print("Last HTTP:", last_status)
    if last_text:
        print("Last response (first 800 chars):")
        print(last_text[:800])
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

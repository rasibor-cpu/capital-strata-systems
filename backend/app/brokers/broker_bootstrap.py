"""
Capital Strata Systems (CSS)
Broker Bootstrap

Purpose
-------
Responsible for initializing the selected broker adapter
during system startup.

Flow
----
1. User selects broker.
2. Credentials are loaded.
3. Required SDK dependencies are checked.
4. Adapter instance is created.
5. Adapter is returned to the trading engine.

PCNRASS SAFE VERSION
--------------------
- Preserves existing bootstrap flow.
- Preserves governance behavior.
- Preserves OANDA behavior.
- Supports Coinbase CDP JSON credential files.
- Does not pass raw Coinbase private-key text as a file path.
- Fail-closed design maintained.
"""

from typing import Any, Dict

from .broker_registry import get_adapter
from .credential_loader import load_credentials
from .install_utils import ensure_broker_dependencies


class BrokerBootstrapError(Exception):
    """Raised when broker initialization fails."""

    pass


def run_broker_bootstrap_self_test(broker_name: str, mode: str) -> bool:
    """
    Run self-test stages for the selected broker bootstrap:
    ✓ .env located
    ✓ environment loaded
    ✓ credential object created
    ✓ required fields present
    ✓ authentication successful
    ✓ account accessible
    ✓ market data accessible
    """
    print(f"\n=== BROKER BOOTSTRAP SELF-TEST ({broker_name.upper()} | {mode}) ===")
    stages = {
        ".env located": "FAIL",
        "environment loaded": "FAIL",
        "credential object created": "FAIL",
        "required fields present": "FAIL",
        "authentication successful": "FAIL",
        "account accessible": "FAIL",
        "market data accessible": "FAIL",
    }
    
    # Stage 1: .env located
    from pathlib import Path
    import os
    from dotenv import load_dotenv
    import requests
    
    project_root = Path(__file__).resolve().parents[3]
    env_file = project_root / ".env"
    if env_file.exists():
        stages[".env located"] = "PASS"
    else:
        stages[".env located"] = "FAIL"
        
    # Stage 2: environment loaded
    load_dotenv(env_file)
    load_dotenv(project_root / ".env.practice", override=False)
    if os.getenv("OANDA_API_KEY") or os.getenv("COINBASE_KEY_NAME"):
        stages["environment loaded"] = "PASS"
    else:
        stages["environment loaded"] = "FAIL"
        
    # Stage 3: credential object created
    from .credential_loader import load_credentials
    creds = load_credentials(broker_name, mode=mode)
    if isinstance(creds, dict) and creds:
        stages["credential object created"] = "PASS"
    else:
        stages["credential object created"] = "FAIL"
        
    # Stage 4: required fields present
    if stages["credential object created"] == "PASS":
        keys_ok = False
        if broker_name.lower() == "coinbase":
            key_name = (
                creds.get("api_key_name")
                or creds.get("name")
                or creds.get("key_name")
                or creds.get("COINBASE_CDP_KEY_NAME")
                or creds.get("COINBASE_KEY_NAME")
            )
            private_key = (
                creds.get("COINBASE_CDP_PRIVATE_KEY")
                or creds.get("COINBASE_PRIVATE_KEY")
                or creds.get("COINBASE_KEY_FILE")
                or creds.get("COINBASE_KEY_JSON_PATH")
            )
            if key_name and private_key:
                keys_ok = True
        elif broker_name.lower() == "oanda":
            token = (
                creds.get("OANDA_API_KEY")
                or creds.get("OANDA_ACCESS_TOKEN")
                or creds.get("OANDA_TOKEN")
            )
            account_id = (
                creds.get("OANDA_ACCOUNT_ID")
                or creds.get("OANDA_PRACTICE_ACCOUNT_ID")
            )
            if token and account_id:
                keys_ok = True
        
        stages["required fields present"] = "PASS" if keys_ok else "FAIL"
    else:
        stages["required fields present"] = "FAIL"
        
    # Stage 5, 6, 7: Instantiate adapter and test live credentials
    if stages["required fields present"] == "PASS":
        try:
            from .broker_registry import get_adapter
            adapter_cls = get_adapter(broker_name)
            if adapter_cls is not None:
                adapter = _instantiate_adapter(
                    adapter_cls=adapter_cls,
                    broker_name=broker_name,
                    creds=creds,
                    mode=mode,
                )
                
                # Verify authentication and account access
                # OANDA:
                if broker_name.lower() == "oanda":
                    headers = {"Authorization": f"Bearer {adapter.api_key}"}
                    url = f"{adapter.base_url}/v3/accounts/{adapter.account_id}"
                    resp = requests.get(url, headers=headers, timeout=5)
                    if resp.status_code == 200:
                        stages["authentication successful"] = "PASS"
                        stages["account accessible"] = "PASS"
                    else:
                        stages["authentication successful"] = "FAIL"
                        stages["account accessible"] = "FAIL"
                    
                    md_url = f"{adapter.base_url}/v3/accounts/{adapter.account_id}/instruments"
                    md_resp = requests.get(md_url, headers=headers, timeout=5)
                    if md_resp.status_code == 200:
                        stages["market data accessible"] = "PASS"
                    else:
                        stages["market data accessible"] = "FAIL"
                
                # Coinbase:
                elif broker_name.lower() == "coinbase":
                    client = adapter._get_rest_client()
                    if client is not None:
                        try:
                            accounts = client.get_accounts()
                            stages["authentication successful"] = "PASS"
                            stages["account accessible"] = "PASS"
                        except Exception:
                            stages["authentication successful"] = "FAIL"
                            stages["account accessible"] = "FAIL"
                        
                        try:
                            client.get_product(product_id="BTC-USD")
                            stages["market data accessible"] = "PASS"
                        except Exception:
                            stages["market data accessible"] = "FAIL"
            else:
                stages["authentication successful"] = "FAIL"
                stages["account accessible"] = "FAIL"
                stages["market data accessible"] = "FAIL"
        except Exception:
            stages["authentication successful"] = "FAIL"
            stages["account accessible"] = "FAIL"
            stages["market data accessible"] = "FAIL"
    else:
        stages["authentication successful"] = "FAIL"
        stages["account accessible"] = "FAIL"
        stages["market data accessible"] = "FAIL"

    # Print results
    for stage, result in stages.items():
        symbol = "[v]" if result == "PASS" else "[x]"
        print(f" {symbol} {stage:<25} : {result}")
    print("=================================================\n")
    
    return all(res == "PASS" for res in stages.values())


def initialize_broker(broker_name: str, mode: str = "paper"):
    """
    Initialize a broker adapter.
    """

    broker_name = broker_name.lower()

    # Run self-test
    self_test_ok = run_broker_bootstrap_self_test(broker_name, mode)
    if not self_test_ok:
         print(f"[BROKER BOOTSTRAP] WARNING: Bootstrap self-test has failed stages.")

    print(f"[BROKER BOOTSTRAP] Initializing broker: {broker_name}")
    print(f"[BROKER BOOTSTRAP] Mode: {mode}")

    dependency_status = ensure_broker_dependencies(broker_name)

    if not dependency_status.get("ok"):
        raise BrokerBootstrapError(
            "Broker dependency unavailable for "
            f"{broker_name}: {dependency_status.get('package')}"
        )

    creds = load_credentials(broker_name, mode=mode)

    if creds is None:
        raise BrokerBootstrapError(
            f"No credentials found for broker: {broker_name}"
        )

    adapter_cls = get_adapter(broker_name)

    if adapter_cls is None:
        raise BrokerBootstrapError(
            f"No adapter registered for broker: {broker_name}"
        )

    adapter = _instantiate_adapter(
        adapter_cls=adapter_cls,
        broker_name=broker_name,
        creds=creds,
        mode=mode,
    )

    connect = getattr(adapter, "connect", None)

    if callable(connect):
        connect()
    else:
        is_configured = getattr(adapter, "is_configured", None)

        if callable(is_configured) and not is_configured():
            raise BrokerBootstrapError(
                f"{broker_name} adapter is not configured"
            )

    print(f"[BROKER BOOTSTRAP] {broker_name} successfully initialized")

    return adapter


def _instantiate_adapter(
    adapter_cls: type,
    broker_name: str,
    creds: Dict[str, Any],
    mode: str,
):
    """
    Instantiate adapter while supporting legacy and modern
    credential naming conventions.
    """

    if broker_name == "coinbase":
        api_key_name = str(
            creds.get("api_key_name")
            or creds.get("name")
            or creds.get("key_name")
            or creds.get("COINBASE_CDP_KEY_NAME")
            or creds.get("COINBASE_KEY_NAME")
            or ""
        )

        api_private_key_path = str(
            creds.get("COINBASE_KEY_JSON_PATH")
            or creds.get("COINBASE_KEY_FILE")
            or ""
        )

        return adapter_cls(
            api_key_name=api_key_name,
            api_private_key_path=api_private_key_path,
            paper_mode=(mode != "live"),
        )

    try:
        return adapter_cls(
            credentials=creds,
            mode=mode,
        )

    except TypeError:
        try:
            return adapter_cls(credentials=creds)
        except TypeError:
            return adapter_cls()
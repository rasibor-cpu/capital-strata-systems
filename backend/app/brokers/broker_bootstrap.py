"""
Capital Strata Systems (CSS)
Broker Bootstrap

Purpose
-------
Responsible for initializing the selected broker adapter
during system startup.

Canonical flow
--------------
1. Enterprise Broker Runtime composition is supplied.
2. A pre-registered native binding is resolved.
3. Capability-bound RuntimeSecretLease objects are issued.
4. An advisory-only native adapter is returned.

The historical self-test remains compatibility evidence only. It cannot
initialize a broker or be certified Enterprise Managed.
"""

from typing import Any

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
        "profile selected": "FAIL",
        "environment loaded": "FAIL",
        "credential object created": "FAIL",
        "required fields present": "FAIL",
        "authentication successful": "FAIL",
        "account accessible": "FAIL",
        "market data accessible": "FAIL",
    }
    
    # Stage 1: .env located
    import os
    from pathlib import Path
    from backend.runtime.live_environment_loader import load_css_runtime_environment
    
    project_root = Path(__file__).resolve().parents[3]
    env_trace = load_css_runtime_environment(project_root, mode=mode, broker=broker_name, env=os.environ)
    if env_trace.get("profile") not in {"UNSELECTED", "", None}:
        stages["profile selected"] = "PASS"
    if env_trace.get("validation_status") == "PASS" or os.getenv("OANDA_API_KEY") or os.getenv("COINBASE_KEY_NAME"):
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
        
    from backend.runtime.canonical_broker_state_builder import build_canonical_broker_runtime_state

    canonical = build_canonical_broker_runtime_state(
        broker=broker_name,
        mode=mode,
        runtime_payload={
            "selected_broker": broker_name.upper(),
            "broker_mode": mode,
            "credential_status": "PRESENT" if stages["required fields present"] == "PASS" else "MISSING",
            "broker_authenticated": False,
            "broker_connected": False,
            "account_loaded": False,
            "balances_loaded": False,
            "market_data_loaded": False,
            "products_loaded": 0,
            "validation_source": "broker_bootstrap_self_test",
        },
        env=os.environ,
        source_modules=("backend.app.brokers.broker_bootstrap",),
    )
    stages["authentication successful"] = canonical.authentication_status
    stages["account accessible"] = canonical.account_status
    stages["market data accessible"] = canonical.market_data_status

    # Print results
    for stage, result in stages.items():
        symbol = "[v]" if result == "PASS" else "[x]"
        print(f" {symbol} {stage:<25} : {result}")
    print(f" Canonical Overall Status      : {canonical.overall_status}")
    print(f" Canonical Failure Reason      : {canonical.failure_reason}")
    print(f" Canonical State Hash          : {canonical.stable_hash()}")
    print(f" Canonical Provenance          : {canonical.status_provenance}")
    print("=================================================\n")
    
    return all(res == "PASS" for res in stages.values())


def initialize_broker(
    broker_name: str,
    mode: str = "disabled",
    *,
    enterprise_runtime: Any | None = None,
    operator: str = "SYSTEM",
    provider: Any | None = None,
):
    """
    Initialize only through the Enterprise Broker Runtime.

    Legacy credential loading remains available solely to the separately named
    self-test above and cannot initialize a broker.
    """
    normalized = str(broker_name).upper()
    if str(mode).lower() not in {"disabled", "read_only", "advisory"}:
        raise BrokerBootstrapError("BROKER_RUNTIME_MODE_NOT_ADVISORY")
    if enterprise_runtime is None:
        raise BrokerBootstrapError("ENTERPRISE_BROKER_RUNTIME_REQUIRED")
    if normalized not in {"QUESTRADE", "COINBASE", "BINANCE", "OANDA"}:
        raise BrokerBootstrapError(f"UNSUPPORTED_ENTERPRISE_BROKER:{normalized}")
    try:
        return enterprise_runtime.native_adapter(
            normalized,
            operator=operator,
            provider=provider,
        )
    except Exception as exc:
        raise BrokerBootstrapError(
            f"ENTERPRISE_BROKER_RUNTIME_BINDING_UNAVAILABLE:{normalized}"
        ) from exc

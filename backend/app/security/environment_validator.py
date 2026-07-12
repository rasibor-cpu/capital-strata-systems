import os

class EnvironmentValidationError(Exception):
    pass

from typing import Mapping

def validate_startup_security_environment(broker_name: str, mode: str, env: Mapping[str, str] | None = None) -> dict[str, bool]:
    """
    Returns a dict with security status:
    {
        "ENVIRONMENT_VALID": bool,
        "BROKER_CONFIG_VALID": bool,
        "LIVE_PRACTICE_CONSISTENT": bool,
        "SECRET_VALIDATION_PASSED": bool
    }
    Raises EnvironmentValidationError if fail-closed conditions are met.
    """
    status = {
        "ENVIRONMENT_VALID": True,
        "BROKER_CONFIG_VALID": True,
        "LIVE_PRACTICE_CONSISTENT": True,
        "SECRET_VALIDATION_PASSED": True
    }
    
    broker = broker_name.upper()
    mode = mode.lower()
    env_source = env if env is not None else os.environ
    
    # 1. LIVE/PRACTICE CONTAMINATION CHECK
    if mode == "live":
        # Ensure no practice variables leak into a live session
        for key, value in env_source.items():
            if broker in key and ("PRACTICE" in key or "TEST" in key) and value:
                status["LIVE_PRACTICE_CONSISTENT"] = False
                raise EnvironmentValidationError(f"Live/Practice contamination: {key} is present in LIVE mode.")
                
        # 2. FAIL-CLOSED SECRETS CHECK (LIVE)
        if broker == "OANDA":
            token = env_source.get("OANDA_API_KEY") or env_source.get("OANDA_ACCESS_TOKEN") or env_source.get("OANDA_TOKEN")
            acc = env_source.get("OANDA_ACCOUNT_ID")
            env_val = env_source.get("OANDA_ENV")
            
            if not token or not token.strip():
                status["SECRET_VALIDATION_PASSED"] = False
                raise EnvironmentValidationError("OANDA live mode requires a non-empty token.")
            if not acc or not acc.strip():
                status["BROKER_CONFIG_VALID"] = False
                raise EnvironmentValidationError("OANDA live mode requires a non-empty OANDA_ACCOUNT_ID.")
            if env_val != "live":
                status["ENVIRONMENT_VALID"] = False
                raise EnvironmentValidationError(f"OANDA live mode requires OANDA_ENV=live. Got: {env_val}")
                
        elif broker == "COINBASE":
            key_name = env_source.get("COINBASE_CDP_KEY_NAME") or env_source.get("COINBASE_KEY_NAME")
            priv_key = env_source.get("COINBASE_CDP_PRIVATE_KEY") or env_source.get("COINBASE_PRIVATE_KEY")
            
            # Simplified check: just ensuring some credentials exist
            if not key_name and not priv_key and not env_source.get("COINBASE_KEY_FILE"):
                status["SECRET_VALIDATION_PASSED"] = False
                raise EnvironmentValidationError("COINBASE live mode requires valid CDP credentials.")
                
    elif mode == "paper":
        # 3. LIVE/PRACTICE CONTAMINATION CHECK (PAPER)
        if broker == "OANDA":
            env_val = env_source.get("OANDA_ENV")
            if env_val == "live":
                status["LIVE_PRACTICE_CONSISTENT"] = False
                raise EnvironmentValidationError("Paper mode requested but OANDA_ENV=live detected.")
                
            token = env_source.get("OANDA_API_KEY") or env_source.get("OANDA_ACCESS_TOKEN") or env_source.get("OANDA_TOKEN")
            acc = env_source.get("OANDA_PRACTICE_ACCOUNT_ID") or env_source.get("OANDA_ACCOUNT_ID")
            
            if not token or not token.strip():
                status["SECRET_VALIDATION_PASSED"] = False
                raise EnvironmentValidationError("OANDA paper mode requires a non-empty token.")
            if not acc or not acc.strip():
                status["BROKER_CONFIG_VALID"] = False
                raise EnvironmentValidationError("OANDA paper mode requires a non-empty account ID.")
    
    return status

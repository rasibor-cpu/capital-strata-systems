import os

class EnvironmentValidationError(Exception):
    pass

def validate_startup_security_environment(broker_name: str, mode: str) -> dict[str, bool]:
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
    
    # 1. LIVE/PRACTICE CONTAMINATION CHECK
    if mode == "live":
        # Ensure no practice variables leak into a live session
        for key, value in os.environ.items():
            if broker in key and ("PRACTICE" in key or "TEST" in key) and value:
                status["LIVE_PRACTICE_CONSISTENT"] = False
                raise EnvironmentValidationError(f"Live/Practice contamination: {key} is present in LIVE mode.")
                
        # 2. FAIL-CLOSED SECRETS CHECK (LIVE)
        if broker == "OANDA":
            token = os.getenv("OANDA_API_KEY") or os.getenv("OANDA_ACCESS_TOKEN") or os.getenv("OANDA_TOKEN")
            acc = os.getenv("OANDA_ACCOUNT_ID")
            env = os.getenv("OANDA_ENV")
            
            if not token or not token.strip():
                status["SECRET_VALIDATION_PASSED"] = False
                raise EnvironmentValidationError("OANDA live mode requires a non-empty token.")
            if not acc or not acc.strip():
                status["BROKER_CONFIG_VALID"] = False
                raise EnvironmentValidationError("OANDA live mode requires a non-empty OANDA_ACCOUNT_ID.")
            if env != "live":
                status["ENVIRONMENT_VALID"] = False
                raise EnvironmentValidationError(f"OANDA live mode requires OANDA_ENV=live. Got: {env}")
                
        elif broker == "COINBASE":
            key_name = os.getenv("COINBASE_CDP_KEY_NAME") or os.getenv("COINBASE_KEY_NAME")
            priv_key = os.getenv("COINBASE_CDP_PRIVATE_KEY") or os.getenv("COINBASE_PRIVATE_KEY")
            
            # Simplified check: just ensuring some credentials exist
            if not key_name and not priv_key and not os.getenv("COINBASE_KEY_FILE"):
                status["SECRET_VALIDATION_PASSED"] = False
                raise EnvironmentValidationError("COINBASE live mode requires valid CDP credentials.")
                
    elif mode == "paper":
        # 3. LIVE/PRACTICE CONTAMINATION CHECK (PAPER)
        if broker == "OANDA":
            env = os.getenv("OANDA_ENV")
            if env == "live":
                status["LIVE_PRACTICE_CONSISTENT"] = False
                raise EnvironmentValidationError("Paper mode requested but OANDA_ENV=live detected.")
                
            token = os.getenv("OANDA_API_KEY") or os.getenv("OANDA_ACCESS_TOKEN") or os.getenv("OANDA_TOKEN")
            acc = os.getenv("OANDA_PRACTICE_ACCOUNT_ID") or os.getenv("OANDA_ACCOUNT_ID")
            
            if not token or not token.strip():
                status["SECRET_VALIDATION_PASSED"] = False
                raise EnvironmentValidationError("OANDA paper mode requires a non-empty token.")
            if not acc or not acc.strip():
                status["BROKER_CONFIG_VALID"] = False
                raise EnvironmentValidationError("OANDA paper mode requires a non-empty account ID.")
    
    return status

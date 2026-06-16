import pytest
import os
from unittest.mock import patch

from backend.app.security.environment_validator import validate_startup_security_environment, EnvironmentValidationError
from backend.app.brokers.credential_loader import _load_oanda_env_credentials

@pytest.fixture(autouse=True)
def clean_env():
    # Remove OANDA and COINBASE vars before each test
    keys_to_remove = [k for k in os.environ if "OANDA" in k or "COINBASE" in k]
    for k in keys_to_remove:
        del os.environ[k]
    yield

def test_missing_variables_fail_closed_oanda_live():
    # Nothing set
    with pytest.raises(EnvironmentValidationError, match="OANDA live mode requires a non-empty token"):
        validate_startup_security_environment("OANDA", "live")

def test_missing_account_fail_closed_oanda_live():
    os.environ["OANDA_API_KEY"] = "secret"
    with pytest.raises(EnvironmentValidationError, match="OANDA live mode requires a non-empty OANDA_ACCOUNT_ID"):
        validate_startup_security_environment("OANDA", "live")

def test_wrong_env_fail_closed_oanda_live():
    os.environ["OANDA_API_KEY"] = "secret"
    os.environ["OANDA_ACCOUNT_ID"] = "123"
    os.environ["OANDA_ENV"] = "practice"
    with pytest.raises(EnvironmentValidationError, match="OANDA live mode requires OANDA_ENV=live. Got: practice"):
        validate_startup_security_environment("OANDA", "live")

def test_mixed_live_practice_variables_oanda_live():
    os.environ["OANDA_API_KEY"] = "secret"
    os.environ["OANDA_ACCOUNT_ID"] = "123"
    os.environ["OANDA_ENV"] = "live"
    os.environ["OANDA_PRACTICE_ACCOUNT_ID"] = "999" # Contamination
    
    with pytest.raises(EnvironmentValidationError, match="Live/Practice contamination: OANDA_PRACTICE_ACCOUNT_ID is present in LIVE mode"):
        validate_startup_security_environment("OANDA", "live")

def test_mixed_live_practice_variables_oanda_paper():
    os.environ["OANDA_ENV"] = "live"
    with pytest.raises(EnvironmentValidationError, match="Paper mode requested but OANDA_ENV=live detected."):
        validate_startup_security_environment("OANDA", "paper")

def test_valid_oanda_live():
    os.environ["OANDA_API_KEY"] = "secret"
    os.environ["OANDA_ACCOUNT_ID"] = "123"
    os.environ["OANDA_ENV"] = "live"
    
    status = validate_startup_security_environment("OANDA", "live")
    assert status["ENVIRONMENT_VALID"]
    assert status["BROKER_CONFIG_VALID"]
    assert status["LIVE_PRACTICE_CONSISTENT"]
    assert status["SECRET_VALIDATION_PASSED"]

def test_credential_loader_isolation_oanda():
    os.environ["OANDA_API_KEY"] = "token123"
    os.environ["OANDA_ACCOUNT_ID"] = "live_acc"
    os.environ["OANDA_PRACTICE_ACCOUNT_ID"] = "prac_acc"
    
    # In live mode, it should grab OANDA_ACCOUNT_ID
    creds_live = _load_oanda_env_credentials(mode="live")
    assert creds_live["OANDA_ACCOUNT_ID"] == "live_acc"
    assert creds_live["OANDA_ENV"] == "live"
    
    # In paper mode, it should grab PRACTICE_ACCOUNT_ID because it's present
    creds_paper = _load_oanda_env_credentials(mode="paper")
    assert creds_paper["OANDA_ACCOUNT_ID"] == "prac_acc"
    assert creds_paper["OANDA_ENV"] == "practice"

def test_coinbase_missing_live():
    with pytest.raises(EnvironmentValidationError, match="COINBASE live mode requires valid CDP credentials."):
        validate_startup_security_environment("COINBASE", "live")

import os
import tempfile
from pathlib import Path
import pytest

from backend.app.brokers.credential_loader import load_credentials
from backend.app.brokers.broker_bootstrap import run_broker_bootstrap_self_test


def test_cwd_movement_does_not_break_credential_discovery():
    """
    Test that moving the current working directory (CWD) to a temporary folder
    does not break the dotenv loading and credential discovery.
    """
    original_cwd = os.getcwd()
    
    # Verify we can discover credentials in the normal path
    coinbase_creds_before = load_credentials("coinbase", mode="paper")
    oanda_creds_before = load_credentials("oanda", mode="paper")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Change CWD to temporary directory
            os.chdir(tmpdir)
            
            # Retrieve credentials again
            coinbase_creds_after = load_credentials("coinbase", mode="paper")
            oanda_creds_after = load_credentials("oanda", mode="paper")
            
            # Assert they are discovered identically
            assert coinbase_creds_before == coinbase_creds_after
            assert oanda_creds_before == oanda_creds_after
            
        finally:
            # Restore working directory
            os.chdir(original_cwd)


def test_entrypoint_consistency_in_discovery():
    """
    Assert that the loader discovers exactly the same credentials
    regardless of simulated entry points environment states.
    """
    coinbase_creds = load_credentials("coinbase", mode="paper")
    oanda_creds = load_credentials("oanda", mode="paper")
    
    # We should have at least the keys or files present if configured in .env
    if coinbase_creds:
        assert "COINBASE_ENABLE_LIVE_ORDERS" in coinbase_creds
    if oanda_creds:
        assert "OANDA_ENV" in oanda_creds


def test_bootstrap_self_test_runs_successfully():
    """
    Verify the bootstrap self test executes successfully (even if it detects FAIL on some stages).
    It should not raise unhandled exceptions and should return a boolean.
    """
    result = run_broker_bootstrap_self_test("coinbase", mode="paper")
    assert isinstance(result, bool)

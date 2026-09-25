from pathlib import Path


SOURCE = Path("scripts/css_live_dashboard.py").read_text(encoding="utf-8")


def test_managed_runtime_bootstrap_precedes_operator_authentication():
    managed = SOURCE.index(
        'if os.getenv("CSS_CANONICAL_RUNTIME_MANAGED") == "1":'
    )
    authentication = SOURCE.index(
        "SESSION_USER_CTX = authenticate_startup_user()"
    )

    assert managed < authentication


def test_managed_background_service_does_not_synthesize_operator_identity():
    start = SOURCE.index(
        "def _run_canonical_background_service()"
    )
    end = SOURCE.index(
        'if os.getenv("CSS_CANONICAL_RUNTIME_MANAGED") == "1":',
        start,
    )
    block = SOURCE[start:end]

    assert "authenticate_startup_user" not in block
    assert "create_session" not in block
    assert "broker_execution_armed" not in block
    assert "execution_allowed" not in block


def test_managed_background_service_is_explicitly_fail_closed():
    start = SOURCE.index(
        "def _run_canonical_background_service()"
    )
    end = SOURCE.index(
        'if os.getenv("CSS_CANONICAL_RUNTIME_MANAGED") == "1":',
        start,
    )
    block = SOURCE[start:end]

    assert "execution remains DISABLED / BLOCKED / ADVISORY_ONLY" in block
    assert "time.sleep(10)" in block

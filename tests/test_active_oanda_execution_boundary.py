from pathlib import Path


def test_active_live_dashboard_supplies_oanda_mutation_identity_and_context():
    source = Path("scripts/css_live_dashboard.py").read_text(encoding="utf-8")
    assert "idempotency_key=order_idempotency_key" in source
    assert "user_context=SESSION_USER_CTX" in source
    assert "hashlib.sha256" in source

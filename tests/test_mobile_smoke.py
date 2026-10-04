"""Run the mobile smoke script inside the full suite.

``dashboard/mobile/mobile_smoke_test.py`` silently diverged from the product
for months (it still expected the pre-2026-06-16 PAPER/orders-enabled default
and live mobile execution) because nothing ran it. Running it here means any
future divergence fails every CI run that runs the suite.
"""
from dashboard.mobile import mobile_smoke_test


def test_mobile_smoke_script_passes():
    assert mobile_smoke_test.main() == 0

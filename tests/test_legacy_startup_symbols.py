import re
import os

def test_legacy_symbols_exist_and_no_double_prefix():
    # Load the target script directly
    script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'css_live_dashboard.py')
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Assert correct symbols exist in definitions
    assert "def _legacy_enforce_mode_dominance(" in content, "Missing _legacy_enforce_mode_dominance"
    assert "def _legacy_enforce_execution_boundary(" in content, "Missing _legacy_enforce_execution_boundary"
    
    # Assert no double prefix
    assert "_legacy__legacy" not in content, "Found _legacy__legacy in code"
    assert "_legacy_legacy" not in content, "Found _legacy_legacy in code"

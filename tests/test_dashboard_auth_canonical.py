import ast
from pathlib import Path

def test_dashboard_auth_canonicalization():
    """Ensure no duplicate inline declarations of await_login_ready_state exist in the script,
    and verify it uses the canonical import."""
    script_path = Path("scripts/css_live_dashboard.py")
    tree = ast.parse(script_path.read_text(encoding="utf-8"))
    
    found_import = False
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            assert node.name != "await_login_ready_state", "Duplicate inline function definition found!"
            
        if isinstance(node, ast.ImportFrom):
            if node.module == "dashboard.auth.css_sign_on":
                for alias in node.names:
                    if alias.name == "await_login_ready_state":
                        found_import = True
                        
    assert found_import, "Canonical import from dashboard.auth.css_sign_on not found in scripts/css_live_dashboard.py"

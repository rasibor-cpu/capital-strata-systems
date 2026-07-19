#!/usr/bin/env bash
# Idempotent install/update script for Cursor Cloud Agents.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[healthchecker+] Cursor install starting"

python3 -m pip install --user -U pip >/dev/null
if [[ -f requirements.txt ]]; then
  python3 -m pip install --user -r requirements.txt
fi

# Lightweight sanity checks (keep boot fast)
python3 - <<'PY'
from pathlib import Path
import ast

root = Path(".")
required = [
    "index.html",
    "app.js",
    "style.css",
    "manifest.webmanifest",
    "backend/intelligence/foot_pain_engine.py",
]
missing = [p for p in required if not (root / p).exists()]
if missing:
    raise SystemExit(f"Missing required files: {missing}")

ast.parse((root / "backend/intelligence/foot_pain_engine.py").read_text(encoding="utf-8"))
print("Required web + intelligence files present")
PY

python3 -m unittest discover -s tests -p 'test_*.py' -q
echo "[healthchecker+] Cursor install complete"

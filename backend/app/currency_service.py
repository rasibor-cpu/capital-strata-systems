from pathlib import Path
import json
from typing import Dict, Any, List

REPO_ROOT = Path(__file__).resolve().parents[2]
CURRENCY_FILE = REPO_ROOT / "backend" / "app" / "config" / "currency_master.json"


def get_currency_master() -> Dict[str, Any]:
    return json.loads(CURRENCY_FILE.read_text(encoding="utf-8"))


def list_currencies() -> List[Dict[str, Any]]:
    master = get_currency_master()
    return [
        {"code": code, "name": data["name"], "minor_unit": data["minor_unit"]}
        for code, data in sorted(master.items())
    ]
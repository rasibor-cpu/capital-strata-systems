import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.headless_guarded_entry import run_headless

def main():
    # Provide a simple smoke test payload for CLI execution
    req = {
        "execution_mode": "SIMULATION",
        "symbol": "EUR_USD",
        "current_equity": 100000.0,
        "steps": 1,
    }
    result = run_headless(req)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
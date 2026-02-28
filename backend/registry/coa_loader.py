import json
from pathlib import Path

REGISTRY_PATH = Path(__file__).parent / "coa_registry.json"


def load_coa_lookup() -> dict:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError("CoA registry not found.")

    with open(REGISTRY_PATH, "r") as f:
        data = json.load(f)

    # Basic validation
    for gl, meta in data.items():
        if "risk_type" not in meta:
            raise ValueError(f"GL {gl} missing risk_type.")
        if "regulatory_weight_default" not in meta:
            raise ValueError(f"GL {gl} missing regulatory_weight_default.")

    return data
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List


CONFIG_PATH = "config.json"
PAIR_RE = re.compile(r"^[A-Z]{3}_[A-Z]{3}$")


def load_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Missing {CONFIG_PATH} in current folder.")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = f.read().strip()
        if not raw:
            raise ValueError(f"{CONFIG_PATH} is empty. Paste valid JSON into it first.")
        return json.loads(raw)


def save_config(cfg: Dict[str, Any]) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")


def get_enabled_list(cfg: Dict[str, Any]) -> List[str]:
    ins = cfg.get("instruments", {})
    enabled = ins.get("enabled", [])
    if not isinstance(enabled, list):
        raise TypeError("config.json instruments.enabled must be a list.")
    # normalize
    out = []
    for x in enabled:
        s = str(x).strip().upper()
        if s:
            out.append(s)
    return out


def validate_pair(pair: str) -> str:
    p = pair.strip().upper()
    if not PAIR_RE.match(p):
        raise ValueError(f"Invalid pair '{pair}'. Use format like EUR_USD, USD_JPY.")
    return p


def cmd_list() -> int:
    cfg = load_config()
    enabled = sorted(set(get_enabled_list(cfg)))
    print("\nEnabled instruments:")
    for p in enabled:
        print(" -", p)
    print("")
    return 0


def cmd_add(pair: str) -> int:
    cfg = load_config()
    p = validate_pair(pair)

    enabled = get_enabled_list(cfg)
    s = set(enabled)
    if p in s:
        print(f"{p} already enabled.")
        return 0

    enabled.append(p)
    cfg.setdefault("instruments", {})["enabled"] = enabled
    save_config(cfg)
    print(f"Added {p}.")
    return 0


def cmd_remove(pair: str) -> int:
    cfg = load_config()
    p = validate_pair(pair)

    enabled = get_enabled_list(cfg)
    enabled2 = [x for x in enabled if x != p]
    if len(enabled2) == len(enabled):
        print(f"{p} was not enabled.")
        return 0

    cfg.setdefault("instruments", {})["enabled"] = enabled2
    save_config(cfg)
    print(f"Removed {p}.")
    return 0


def usage() -> int:
    print(
        "\nUsage:\n"
        "  python instrument_manager.py list\n"
        "  python instrument_manager.py add EUR_USD\n"
        "  python instrument_manager.py remove EUR_USD\n"
    )
    return 1


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        return usage()

    cmd = argv[1].lower().strip()

    if cmd == "list":
        return cmd_list()

    if cmd == "add" and len(argv) >= 3:
        return cmd_add(argv[2])

    if cmd == "remove" and len(argv) >= 3:
        return cmd_remove(argv[2])

    return usage()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
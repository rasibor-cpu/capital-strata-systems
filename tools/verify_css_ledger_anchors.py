"""Independent verifier for CSS-118 ledger anchors (read-only).

Usage:
  python tools/verify_css_ledger_anchors.py --root artifacts/trading_profiles \
      --public-key <base64 Ed25519 public key> [--statement latest_statement.json]

Exit code 0 only when every checkpoint signature and chain link verifies, every anchored
ledger prefix is intact and (if given) the externally held statement is present in the log.
Never writes anything.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.trading_profiles.ledger_anchor import LedgerAnchor  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--public-key", required=True)
    parser.add_argument("--statement")
    args = parser.parse_args(argv)
    statement = json.loads(Path(args.statement).read_text(encoding="utf-8")) if args.statement else None
    report = LedgerAnchor(args.root, key_provider=lambda: None).verify(args.public_key, external_statement=statement)
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

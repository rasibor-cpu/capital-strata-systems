"""CSS Binance Spot READ-ONLY connectivity and eligibility check.

    python scripts/css_binance_readonly_check.py --evidence-dir DIR --operator-id ID \
        --operating-country XX --kyc-country XX --attest-no-geo-bypass --attest-read-only-key

Credentials come only from this process's environment (BINANCE_API_KEY /
BINANCE_API_SECRET); use scripts/windows/css_binance_readonly.ps1 to supply them from
a DPAPI-protected file outside the repository. Nothing here can trade, transfer or
withdraw.

Exit codes: 0 ok, 10 public connectivity blocked (incl. HTTP 451), 11 attestation
failed, 12 credentials refused, 13 key/account not eligible, 14 API error.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.binance_readonly.readonly_check import run_check  # noqa: E402
from backend.shadow_paper.runner import detect_commit_sha  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--operator-id", required=True)
    parser.add_argument("--operating-country", required=True, help="ISO code of where this host is right now")
    parser.add_argument("--kyc-country", required=True, help="ISO code of the Binance account's KYC country")
    parser.add_argument("--attest-no-geo-bypass", action="store_true", help="no VPN/proxy is used to change location")
    parser.add_argument("--attest-read-only-key", action="store_true", help="the API key has only 'Enable Reading'")
    parser.add_argument("--history-limit", type=int, default=50)
    args = parser.parse_args(argv)

    evidence_dir = args.evidence_dir.resolve()
    if ROOT.resolve() in (evidence_dir, *evidence_dir.parents):
        print("REFUSED: --evidence-dir must be outside the repository", file=sys.stderr)
        return 2

    result = run_check(
        evidence_dir=evidence_dir,
        operator_id=args.operator_id,
        attestation={
            "operating_country": args.operating_country,
            "kyc_country": args.kyc_country,
            "no_geo_bypass": bool(args.attest_no_geo_bypass),
            "read_only_key": bool(args.attest_read_only_key),
        },
        environ=os.environ,
        repo_root=ROOT,
        commit_sha=detect_commit_sha(ROOT),
        history_limit=args.history_limit,
    )
    printable = {k: v for k, v in result.summary.items() if k != "account"}
    if "account" in result.summary:
        printable["account"] = {
            "account_type": result.summary["account"]["account_type"],
            "non_zero_balance_assets": [b["asset"] for b in result.summary["account"]["non_zero_balances"]],
        }
    print(json.dumps(printable, indent=2, sort_keys=True, default=str))
    print(f"Evidence journal: {evidence_dir}", file=sys.stderr)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())

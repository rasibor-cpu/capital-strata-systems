"""Staged, fail-closed Binance read-only connectivity check with an evidence journal.

Order (each stage must pass before the next runs):
  1. PUBLIC      ping, server time/clock skew, exchangeInfo for the paper symbols. HTTP 451 stops here.
  2. ATTESTATION operator location/KYC/no-geo-bypass/read-only-key. No credential is loaded before this.
  3. CREDENTIALS loaded from this process's environment; only a fingerprint is recorded.
  4. KEY/ACCOUNT apiRestrictions + account status; every write permission must be off.
  5. READ        balances (non-zero), recent orders and trades per symbol.

The journal never contains the API key, the secret or any signature.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from backend.binance_readonly.client import (
    BinanceReadOnlyClient,
    BinanceReadOnlyError,
    RestrictedLocationError,
    Transport,
)
from backend.binance_readonly.credentials import CredentialPolicyError, load_credentials
from backend.binance_readonly.eligibility import (
    combine,
    evaluate_account_status,
    evaluate_api_restrictions,
    evaluate_attestation,
)
from backend.shadow_paper.journal import EventJournal

LOGGER = logging.getLogger(__name__)

JOURNAL_FILENAME = "binance_readonly_journal.jsonl"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
MAX_CLOCK_SKEW_MS = 1000

EXIT_OK = 0
EXIT_PUBLIC_BLOCKED = 10
EXIT_ATTESTATION = 11
EXIT_CREDENTIALS = 12
EXIT_NOT_ELIGIBLE = 13
EXIT_API_ERROR = 14


@dataclass
class CheckResult:
    exit_code: int
    stage_reached: str
    summary: dict[str, Any]


def _summarize_balances(account: Any) -> dict[str, Any]:
    balances = []
    for item in (account or {}).get("balances", []) or []:
        try:
            free, locked = float(item.get("free", 0)), float(item.get("locked", 0))
        except (TypeError, ValueError):
            continue
        if free or locked:
            balances.append({"asset": item.get("asset"), "free": item.get("free"), "locked": item.get("locked")})
    return {
        "account_type": (account or {}).get("accountType"),
        "permissions": (account or {}).get("permissions"),
        "account_capabilities": {
            "canTrade": (account or {}).get("canTrade"),
            "canWithdraw": (account or {}).get("canWithdraw"),
            "canDeposit": (account or {}).get("canDeposit"),
            "note": "account-level capabilities; the API key itself is read-only (stage 4)",
        },
        "non_zero_balances": balances,
    }


def run_check(
    *,
    evidence_dir: Path,
    operator_id: str,
    attestation: Mapping[str, Any],
    environ: Mapping[str, str],
    repo_root: Path,
    commit_sha: str,
    transport: Optional[Transport] = None,
    history_limit: int = 50,
) -> CheckResult:
    journal = EventJournal(Path(evidence_dir) / JOURNAL_FILENAME, run_id=f"binance-ro-{operator_id}", commit_sha=commit_sha)
    summary: dict[str, Any] = {"operator_id": operator_id, "symbols": list(SYMBOLS)}

    def stop(code: int, stage: str, reason: str) -> CheckResult:
        summary["result"] = {"exit_code": code, "stopped_at": stage, "reason": reason}
        journal.append("CHECK_STOPPED", summary["result"])
        return CheckResult(code, stage, summary)

    journal.append("CHECK_STARTED", {"operator_id": operator_id, "symbols": list(SYMBOLS), "mode": "READ_ONLY"})

    # 1. PUBLIC (no credentials)
    public = BinanceReadOnlyClient(transport=transport)
    try:
        public.ping()
        clock = public.sync_time()
        info = public.exchange_info(list(SYMBOLS))
    except RestrictedLocationError as exc:
        journal.append("PUBLIC_CONNECTIVITY", {"status": "BLOCKED", "reason": "RESTRICTED_LOCATION", "detail": str(exc)})
        return stop(EXIT_PUBLIC_BLOCKED, "PUBLIC", "Binance reports a restricted location (HTTP 451); no workaround")
    except BinanceReadOnlyError as exc:
        journal.append("PUBLIC_CONNECTIVITY", {"status": "FAILED", "detail": str(exc)})
        return stop(EXIT_PUBLIC_BLOCKED, "PUBLIC", "public connectivity failed")
    symbols = {s.get("symbol"): s.get("status") for s in (info or {}).get("symbols", []) if isinstance(s, dict)}
    skew_ok = abs(int(clock["offset_ms"])) <= MAX_CLOCK_SKEW_MS
    summary["public"] = {"clock": clock, "clock_skew_ok": skew_ok, "symbol_status": symbols}
    journal.append("PUBLIC_CONNECTIVITY", {"status": "OK", **summary["public"]})
    if any(symbols.get(s) != "TRADING" for s in SYMBOLS):
        return stop(EXIT_PUBLIC_BLOCKED, "PUBLIC", f"symbols not all TRADING: {symbols}")

    # 2. ATTESTATION (before any credential is touched)
    attest = evaluate_attestation(attestation)
    summary["attestation"] = attest.to_dict()
    journal.append("OPERATOR_ATTESTATION", {"input": dict(attestation), **attest.to_dict()})
    if not attest.eligible:
        return stop(EXIT_ATTESTATION, "ATTESTATION", "operator attestation failed")

    # 3. CREDENTIALS
    try:
        credentials = load_credentials(environ, repo_root)
    except CredentialPolicyError as exc:
        journal.append("CREDENTIALS", {"status": "REFUSED", "detail": str(exc)})
        return stop(EXIT_CREDENTIALS, "CREDENTIALS", str(exc))
    summary["credentials"] = {"api_key_fingerprint": credentials.fingerprint}
    journal.append("CREDENTIALS", {"status": "LOADED", "api_key_fingerprint": credentials.fingerprint})

    # 4. KEY PERMISSIONS + ACCOUNT STATUS
    client = BinanceReadOnlyClient(credentials, transport=transport)
    try:
        client.sync_time()
        restrictions = client.api_restrictions()
        status = client.account_status()
    except RestrictedLocationError as exc:
        journal.append("KEY_PERMISSIONS", {"status": "BLOCKED", "detail": str(exc)})
        return stop(EXIT_PUBLIC_BLOCKED, "KEY_PERMISSIONS", "restricted location (HTTP 451)")
    except BinanceReadOnlyError as exc:
        journal.append("KEY_PERMISSIONS", {"status": "ERROR", "detail": str(exc)})
        return stop(EXIT_API_ERROR, "KEY_PERMISSIONS", str(exc))
    decision = combine(attest, evaluate_api_restrictions(restrictions), evaluate_account_status(status))
    reported = {k: v for k, v in (restrictions or {}).items() if k != "createTime"} if isinstance(restrictions, dict) else None
    summary["eligibility"] = decision.to_dict()
    journal.append("KEY_PERMISSIONS", {"reported": reported, "account_status": status, **decision.to_dict()})
    if not decision.eligible:
        return stop(EXIT_NOT_ELIGIBLE, "KEY_PERMISSIONS", "API key or account is not eligible for read-only use")
    client.confirm_eligibility(decision)

    # 5. READ-ONLY ACCOUNT DATA
    try:
        account = client.account()
        history: dict[str, Any] = {}
        for symbol in SYMBOLS:
            orders = client.all_orders(symbol, history_limit)
            trades = client.my_trades(symbol, history_limit)
            history[symbol] = {
                "orders_returned": len(orders or []),
                "trades_returned": len(trades or []),
                "orders": orders,
                "trades": trades,
            }
    except BinanceReadOnlyError as exc:
        journal.append("ACCOUNT_READ", {"status": "ERROR", "detail": str(exc)})
        return stop(EXIT_API_ERROR, "READ", str(exc))
    summary["account"] = _summarize_balances(account)
    summary["history_counts"] = {s: {k: v for k, v in h.items() if k.endswith("_returned")} for s, h in history.items()}
    journal.append("ACCOUNT_READ", {"status": "OK", "account": summary["account"]})
    for symbol, data in history.items():
        journal.append("HISTORY_READ", {"symbol": symbol, **data})

    summary["result"] = {"exit_code": EXIT_OK, "stopped_at": None, "reason": "read-only check complete"}
    journal.append("CHECK_COMPLETED", summary["result"])
    return CheckResult(EXIT_OK, "READ", summary)

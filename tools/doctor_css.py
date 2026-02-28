"""
tools/doctor_css.py
CSS Doctor — Handshake + DB + Sign-on Diagnostics

Run:
  python tools/doctor_css.py

Optional:
  python tools/doctor_css.py --db path/to/css.db
  python tools/doctor_css.py --verbose

What it does:
- Confirms repo-root assumptions
- Checks environment/config presence
- Locates DB path (arg > env > common defaults)
- Validates schema existence + foreign keys (SQLite)
- Searches for common auth/sign-on modules and verifies they import cleanly
- Attempts a minimal "handshake" import sweep for core packages
- Prints a clear PASS/FAIL checklist

Notes:
- This script is intentionally conservative and does NOT modify the DB.
- If you use Postgres/MySQL instead of SQLite, tell me and I’ll give you the DB-specific version.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]


# -----------------------------
# Utilities
# -----------------------------
@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str = ""


def _ok(name: str, details: str = "") -> CheckResult:
    return CheckResult(name=name, ok=True, details=details)


def _fail(name: str, details: str = "") -> CheckResult:
    return CheckResult(name=name, ok=False, details=details)


def banner(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def safe_import(module_path: str) -> Tuple[bool, str]:
    try:
        __import__(module_path)
        return True, "import ok"
    except Exception as e:
        tb = traceback.format_exc()
        return False, f"{e}\n{tb}"


def add_repo_root_to_path() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


def find_first_existing(paths: List[Path]) -> Optional[Path]:
    for p in paths:
        if p.exists():
            return p
    return None


# -----------------------------
# DB Checks (SQLite only)
# -----------------------------
def sqlite_checks(db_path: Path, verbose: bool) -> List[CheckResult]:
    results: List[CheckResult] = []

    try:
        import sqlite3
    except Exception as e:
        return [_fail("DB driver import (sqlite3)", f"Could not import sqlite3: {e}")]

    if not db_path.exists():
        return [_fail("DB file exists", f"DB not found: {db_path}")]

    results.append(_ok("DB file exists", str(db_path)))

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
    except Exception as e:
        return results + [_fail("DB connect", f"Could not connect: {e}")]

    # Ensure FK enforcement is on for checks
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
        results.append(_ok("DB pragma foreign_keys=ON"))
    except Exception as e:
        results.append(_fail("DB pragma foreign_keys=ON", str(e)))

    # List tables
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        ).fetchall()
        tables = sorted([r["name"] for r in rows])
        if not tables:
            results.append(_fail("DB tables present", "No tables found (empty DB?)"))
        else:
            results.append(_ok("DB tables present", f"{len(tables)} tables detected"))
            if verbose:
                print("Tables:", tables)
    except Exception as e:
        results.append(_fail("DB list tables", str(e)))
        conn.close()
        return results

    # Quick sanity: common CSS table names (best-effort)
    expected_hints = [
        "users", "user", "accounts", "ledger", "ledgers", "journal", "journals",
        "postings", "transactions", "approvals", "roles", "permissions"
    ]
    present_hint = [t for t in tables for h in expected_hints if t.lower() == h]
    if present_hint:
        results.append(_ok("DB contains common core tables (hint)", ", ".join(sorted(set(present_hint)))))
    else:
        results.append(_ok("DB contains common core tables (hint)", "Not detected (may be different naming)"))

    # Foreign key integrity check (best-effort)
    # Note: PRAGMA foreign_key_check returns rows if broken references exist.
    try:
        fk_rows = conn.execute("PRAGMA foreign_key_check;").fetchall()
        if fk_rows:
            sample = []
            for r in fk_rows[:10]:
                # columns: table, rowid, parent, fkid
                sample.append(dict(r))
            results.append(_fail("DB foreign_key_check", f"Broken FK refs found. Sample: {sample}"))
        else:
            results.append(_ok("DB foreign_key_check", "No broken FK refs"))
    except Exception as e:
        results.append(_fail("DB foreign_key_check", str(e)))

    # Optional: row counts for core-ish tables (avoid heavy scans)
    core_candidates = [t for t in tables if t.lower() in ("users", "accounts", "ledger", "journals", "transactions", "postings")]
    try:
        for t in core_candidates[:8]:
            cnt = conn.execute(f"SELECT COUNT(1) AS c FROM {t};").fetchone()["c"]
            results.append(_ok(f"DB rowcount: {t}", str(cnt)))
    except Exception as e:
        results.append(_fail("DB rowcount (core candidates)", str(e)))

    conn.close()
    return results


# -----------------------------
# Handshake / Import Sweep
# -----------------------------
def handshake_checks(verbose: bool) -> List[CheckResult]:
    results: List[CheckResult] = []
    add_repo_root_to_path()

    # These are “best guess” module roots. If a module doesn’t exist, we don’t fail—
    # we just report it as not found.
    likely_packages = [
        "engine",
        "governance",
        "posting",
        "postings",
        "reports",
        "audit",
        "auth",
        "security",
        "api",
        "app",
        "core",
        "ledger",
        "ledgers",
        "calendar",
    ]

    found_any = False
    for pkg in likely_packages:
        pkg_path = REPO_ROOT / pkg
        if pkg_path.exists() and pkg_path.is_dir() and (pkg_path / "__init__.py").exists():
            found_any = True
            ok, info = safe_import(pkg)
            if ok:
                results.append(_ok(f"Import handshake: {pkg}", info))
            else:
                results.append(_fail(f"Import handshake: {pkg}", info))
        else:
            # Not a failure — repo structure may differ
            if verbose:
                results.append(_ok(f"Package not present: {pkg}", "skipped"))

    if not found_any:
        results.append(_ok("Handshake baseline", "No standard packages detected; repo may be organized differently"))

    # Targeted auth imports
    auth_modules = [
        "auth.login",
        "auth.auth_service",
        "auth.user_service",
        "security.passwords",
        "security.sessions",
        "api.main",
        "app.main",
    ]
    for m in auth_modules:
        ok, info = safe_import(m)
        if ok:
            results.append(_ok(f"Import auth/signon: {m}", info))
        else:
            # Do not hard-fail on missing modules; only fail if module exists but fails import.
            # We can detect existence by file path.
            parts = m.split(".")
            candidate = REPO_ROOT.joinpath(*parts[:-1], parts[-1] + ".py")
            if candidate.exists():
                results.append(_fail(f"Import auth/signon: {m}", info))
            else:
                if verbose:
                    results.append(_ok(f"Auth module not present: {m}", "skipped"))

    return results


# -----------------------------
# Env / Config Checks
# -----------------------------
def env_checks() -> List[CheckResult]:
    results: List[CheckResult] = []
    results.append(_ok("Repo root", str(REPO_ROOT)))

    # Common env files
    env_file = find_first_existing([
        REPO_ROOT / ".env",
        REPO_ROOT / ".env.local",
        REPO_ROOT / "config" / ".env",
    ])
    if env_file:
        results.append(_ok("Env file found", str(env_file)))
    else:
        results.append(_ok("Env file found", "Not found (ok if you rely on system env vars)"))

    # Common config files
    config_file = find_first_existing([
        REPO_ROOT / "config.json",
        REPO_ROOT / "settings.json",
        REPO_ROOT / "config" / "settings.json",
        REPO_ROOT / "config" / "config.json",
    ])
    if config_file:
        results.append(_ok("Config file found", str(config_file)))
    else:
        results.append(_ok("Config file found", "Not found (ok if config is code-based)"))

    # DB env hints
    db_env_keys = ["CSS_DB_PATH", "DATABASE_URL", "DB_PATH"]
    present = [k for k in db_env_keys if os.getenv(k)]
    if present:
        results.append(_ok("DB env var(s) set", ", ".join([f"{k}={os.getenv(k)}" for k in present])))
    else:
        results.append(_ok("DB env var(s) set", "None detected (ok if DB path is hardcoded or CLI-provided)"))

    return results


# -----------------------------
# Main
# -----------------------------
def resolve_db_path(cli_db: Optional[str]) -> Optional[Path]:
    if cli_db:
        return Path(cli_db).expanduser().resolve()

    for k in ("CSS_DB_PATH", "DB_PATH"):
        v = os.getenv(k)
        if v:
            return Path(v).expanduser().resolve()

    # Common defaults
    candidates = [
        REPO_ROOT / "data" / "css.db",
        REPO_ROOT / "data" / "css.sqlite",
        REPO_ROOT / "data" / "db.sqlite3",
        REPO_ROOT / "db.sqlite3",
        REPO_ROOT / "css.db",
    ]
    p = find_first_existing(candidates)
    return p


def print_results(results: List[CheckResult]) -> int:
    failures = [r for r in results if not r.ok]
    for r in results:
        status = "PASS" if r.ok else "FAIL"
        print(f"[{status}] {r.name}")
        if r.details:
            # Keep details readable
            d = r.details.strip()
            if len(d) > 800:
                d = d[:800] + "\n... (truncated)"
            print(f"       {d.replace(chr(10), chr(10) + '       ')}")
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", help="Path to CSS SQLite DB (overrides env + defaults)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    banner("CSS DOCTOR — ENV / CONFIG CHECKS")
    env_res = env_checks()
    code = print_results(env_res)

    banner("CSS DOCTOR — HANDSHAKE / IMPORT CHECKS")
    hs_res = handshake_checks(verbose=args.verbose)
    code = max(code, print_results(hs_res))

    db_path = resolve_db_path(args.db)
    banner("CSS DOCTOR — DATABASE CHECKS (SQLite)")
    if not db_path:
        db_res = [_ok("DB path resolution", "No DB detected. Use --db <path> or set CSS_DB_PATH.")]
        code = max(code, print_results(db_res))
    else:
        db_res = sqlite_checks(db_path=db_path, verbose=args.verbose)
        code = max(code, print_results(db_res))

    banner("SUMMARY")
    if code == 0:
        print("All checks PASSED. If you still see glitches, we move to flow-based smoke tests next.")
    else:
        print("One or more checks FAILED. Fix failures top-down (ENV → IMPORT → DB) to stabilize runtime.")

    return code


if __name__ == "__main__":
    raise SystemExit(main())
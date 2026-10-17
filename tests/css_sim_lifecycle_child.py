"""Child process for the lifecycle signal tests (never collected by pytest).

Runs the real `tools/css_sim_cad146.py` `cmd_run` in its OWN process so a test can deliver a real
stop signal to it (POSIX: SIGTERM/SIGINT; Windows: CTRL_BREAK_EVENT to a CREATE_NEW_PROCESS_GROUP
child) without ever signalling the pytest process. Test-only seams, the same as the in-process tests:
preflight PASS, no Coinbase quotes, the test-only consent key store (DPAPI stand-in), no artifacts so
no market data is fetched. No network, no broker, paper only.

usage: python tests/css_sim_lifecycle_child.py <root> <keys_dir> <hours> <poll_seconds>
The exit code is cmd_run's return value.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parent
sys.path[:0] = [str(REPO), str(TESTS)]


def main(argv: list[str]) -> int:
    root, keys, hours, poll = argv[0], argv[1], float(argv[2]), float(argv[3])
    from backend.trading_profiles import consent_signing
    from agreement_support import accept_agreement, test_key_store

    store = test_key_store(Path(keys))
    consent_signing.default_consent_key_store = lambda: store
    spec = importlib.util.spec_from_file_location("css_sim_cad146_tool_child", REPO / "tools" / "css_sim_cad146.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    tool._preflight = lambda args, now=None: {"verdict": "PASS", "checks": []}
    tool.CoinbaseQuotes = lambda http: None
    tool._code_revision = lambda: "test-child"
    arts = Path(root).parent / "arts"
    arts.mkdir(parents=True, exist_ok=True)
    args = SimpleNamespace(root=root, artifacts=str(arts), approvals_root=str(Path(root).parent / "ops"),
                           operator="robert", capital_profile="engineering", custom_capital_cad=None,
                           source="coinbase", hours=hours, poll_seconds=poll, bar_settle_seconds=0.0,
                           on_session_expiry="continue", out=None)
    # default sleep (the production _sleep_in_slices), default clock: exactly what `run` uses
    return tool.cmd_run(args, presenter=accept_agreement, fetch=lambda i, g: None)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

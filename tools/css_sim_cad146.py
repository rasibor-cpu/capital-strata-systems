"""Run the CAD 146 two-track simulation of the CSS autonomous trader on live market data.

PAPER / RESEARCH ONLY: no broker is contacted, no order can leave this process.
Run on a host that can reach the public market-data endpoints (e.g. FINANCE), in wall-clock time.

  # 1) start (presents every manual page for the operator to confirm, once per run directory)
  python tools/css_sim_cad146.py run --root artifacts/simulation/cad146-20261016 \
      --artifacts artifacts/calibration --operator <your-user-id> --hours 48 --poll-seconds 300
  # 2) R7 requires a sign-on within the last hour for new entries; re-attest while attending
  python tools/css_sim_cad146.py attest --root artifacts/simulation/cad146-20261016 --operator <your-user-id>
  # 3) report at any time (and after 48 h)
  python tools/css_sim_cad146.py report --root artifacts/simulation/cad146-20261016 --out cad146_report.json

Stopping and re-running `run` with the same --root resumes the same 48-hour window: the start
time, ledger, positions and processed bars persist; a bar is never decided twice.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.signals.market_data import CoinbaseQuotes, build_provider, resilient_http  # noqa: E402
from backend.signals.research import DEFAULT_COSTS  # noqa: E402
from backend.simulation.cad146 import Cad146Simulation  # noqa: E402
from backend.simulation.capital_profiles import starting_capital, reference_comparison  # noqa: E402

DEFAULT_APPROVALS_ROOT = Path("artifacts") / "trading_profiles"  # operational ledger, read-only use


def _load_artifacts(folder: str) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(folder).glob("*.json"))]


def _terminal_presenter(page) -> bool:
    print(f"\n===== Manual page {page['index']}/{page['total']}: {page['title']} (v{page['manual_version']}) =====\n")
    print(page["markdown"])
    return input("\nConfirm you have read this page in full [yes/NO]: ").strip().lower() == "yes"


def _sim(args, presenter=None) -> Cad146Simulation:
    return Cad146Simulation(args.root, artifacts=_load_artifacts(args.artifacts) if getattr(args, "artifacts", None) else [],
                            costs=DEFAULT_COSTS, operational_approvals_root=args.approvals_root,
                            operator=args.operator, presenter=presenter,
                            quote_provider=CoinbaseQuotes(resilient_http()),
                            starting_equity=starting_capital(profile=args.capital_profile,
                                custom_cad=args.custom_capital_cad))


def cmd_run(args) -> int:
    sim = _sim(args, presenter=_terminal_presenter)
    meta = json.loads(sim.meta_path.read_text(encoding="utf-8"))
    requested = starting_capital(profile=args.capital_profile, custom_cad=args.custom_capital_cad)
    if float(meta["starting_equity_cad"]) != requested:
        raise SystemExit(f"refused: {args.root} was initialised with CAD {meta['starting_equity_cad']:.2f}; "
                         f"requested CAD {requested:.2f}. Use a new --root for a new scenario (no silent reset).")
    end = datetime.fromisoformat(meta["started_utc"]) + timedelta(hours=args.hours)
    provider = build_provider(args.source)
    instruments = sorted({(a["instrument"], int(a["granularity_s"])) for a in sim.artifacts}) or \
        [("BTC-USD", 3600), ("ETH-USD", 3600)]
    print(f"run started_utc={meta['started_utc']} ends_utc={end.isoformat()} instruments={instruments}")
    while datetime.now(timezone.utc) < end:
        summary = sim.cycle(lambda inst, g: provider.fetch(inst, granularity_s=g), instruments)
        print(json.dumps(summary, sort_keys=True), flush=True)
        time.sleep(args.poll_seconds)
    print(json.dumps(sim.report(), indent=2, sort_keys=True, default=str))
    return 0


def cmd_attest(args) -> int:
    sim = _sim(args)
    sim.attest_operator(args.operator)
    print("operator sign-on recorded (valid for R7 for 1 hour)")
    return 0


def cmd_report(args) -> int:
    rep = _sim(args).report()
    initial = rep["run"]["starting_equity_cad"]
    try:
        rep["reference_comparison"] = {
            name: reference_comparison(track["net_pnl_cad"], simulation_capital_cad=initial)
            for name, track in rep["tracks"].items()
        }
    except ValueError as exc:  # e.g. a legacy CAD 146 run: nothing to normalise
        rep["reference_comparison"] = {"unavailable": str(exc)}
    text = json.dumps(rep, indent=2, sort_keys=True, default=str)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "attest", "report"):
        p = sub.add_parser(name)
        p.add_argument("--root", required=True)
        p.add_argument("--operator", required=True if name != "report" else False, default="report-reader")
        p.add_argument("--approvals-root", default=str(DEFAULT_APPROVALS_ROOT))
        p.add_argument("--artifacts", default="artifacts/calibration")
        p.add_argument("--capital-profile", choices=("engineering", "standard", "small", "intermediate", "advanced", "custom"), default="engineering")
        p.add_argument("--custom-capital-cad", default=None)
        if name == "run":
            p.add_argument("--hours", type=float, default=48.0)
            p.add_argument("--poll-seconds", type=float, default=300.0)
            p.add_argument("--source", default="coinbase", choices=["coinbase", "alpaca_crypto"])
        if name == "report":
            p.add_argument("--out")
    args = ap.parse_args(argv)
    return {"run": cmd_run, "attest": cmd_attest, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())

"""Run the CAD 146 two-track simulation of the CSS autonomous trader on live market data.

PAPER / RESEARCH ONLY: no broker is contacted, no order can leave this process.
Run on a host that can reach the public market-data endpoints (e.g. FINANCE), in wall-clock time.

  # 0) preflight only (no run directory is created; nothing starts)
  python tools/css_sim_cad146.py preflight --root artifacts/simulation/cad14600-20261016 --operator <id>
  # 1) start: preflight must PASS, then the operating agreement is shown (Enter/p to page through,
  #    one ACCEPT on the final screen), then the 48-hour clock starts.
  #    Required: CSS_LIVE_ORDER_KILL_SWITCH=1 (live brokerage stays killed);
  #    CSS_SIM_ENTRY_HALT unset (it pauses simulated entries only).
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
from backend.signals.market_data import coinbase_server_time  # noqa: E402
from backend.simulation.cad146 import Cad146Simulation  # noqa: E402
from backend.simulation.preflight import run_preflight  # noqa: E402
from backend.simulation.capital_profiles import starting_capital, reference_comparison  # noqa: E402

DEFAULT_APPROVALS_ROOT = Path("artifacts") / "trading_profiles"  # operational ledger, read-only use


def _load_artifacts(folder: str) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(folder).glob("*.json"))]


_NEXT, _PREV = {"", "n", "next"}, {"p", "prev", "previous", "b", "back"}
_QUIT, _DECLINE = {"q", "quit"}, {"d", "decline"}


def _ask(read, prompt: str) -> str | None:
    try:
        return str(read(prompt)).strip().lower()
    except EOFError:
        return None


def terminal_agreement(review, *, read=input, write=print) -> None:
    """Operating agreement in the terminal: free next/previous paging, ONE acceptance at the end.

    No page needs a per-page confirmation. Unrecognised input never aborts: it is explained and
    the same prompt is shown again. Quitting, declining or closed input record a decline."""
    write(f"\nCSS operating agreement {review.manual.document_id} v{review.manual.version} - {review.total} pages.\n"
          "Read each page; press Enter (or n) for the next page, p for the previous one, q to quit.\n"
          "Nothing is accepted page by page: you accept once, on the final screen, after the last page.")
    while review.status == "REVIEWING":
        if review.at_final_screen:
            s = review.summary()
            write("\n===== Final acceptance =====")
            for label, key in (("Agreement", "document_id"), ("Version", "agreement_version"),
                               ("Content SHA-256", "agreement_sha256"), ("Operator", "operator_id"),
                               ("Operating mode", "operating_mode"), ("Risk personality", "risk_personality"),
                               ("Limits", "limits"), ("Policy hash", "policy_hash")):
                value = s[key] if s[key] not in ({}, None) else "none (personality defaults apply)"
                write(f"  {label:17s} {value}")
            write(f"  Pages reviewed    {s['pages_reviewed']}/{s['pages_total']}")
            write("  Live trading      NOT authorized (simulation only)")
            write(f"\n  {s['acknowledgement_text']}\n")
            answer = _ask(read, "Type ACCEPT to accept, p to go back, or d to decline: ")
            if answer is None:
                review.decline("input_closed")
            elif answer == "accept":
                receipts = review.accept(acknowledged=True, policy_hash_shown=s["policy_hash"])
                write(f"Accepted. Receipts: {', '.join(r['receipt_id'] for r in receipts)}")
            elif answer in _PREV:
                review.previous()
            elif answer in _DECLINE or answer in _QUIT:
                review.decline("declined_by_operator")
            else:
                write("Not recognised: nothing has been accepted or declined. Type ACCEPT, p or d.")
            continue
        page = review.page()
        write(f"\n===== Page {page['index']}/{page['total']}: {page['title']} "
              f"(agreement v{page['manual_version']}) =====\n")
        write(page["markdown"])
        while True:
            answer = _ask(read, f"\n[Enter] next  [p] previous  [q] quit without accepting   ({page['index']}/{page['total']}): ")
            if answer is None:
                review.decline("input_closed")
            elif answer in _NEXT:
                review.next()
            elif answer in _PREV:
                review.previous()
            elif answer in _QUIT:
                review.decline("quit_before_acceptance")
            else:
                write("Not recognised. Press Enter for the next page, p for the previous page or q to quit.")
                continue
            break


_terminal_presenter = terminal_agreement


def _sim(args, presenter=None, *, read_only=False) -> Cad146Simulation:
    return Cad146Simulation(args.root, artifacts=_load_artifacts(args.artifacts) if getattr(args, "artifacts", None) else [],
                            costs=DEFAULT_COSTS, operational_approvals_root=args.approvals_root,
                            operator=args.operator, presenter=presenter, require_current_agreement=not read_only,
                            quote_provider=CoinbaseQuotes(resilient_http()),
                            starting_equity=starting_capital(profile=args.capital_profile,
                                custom_cad=args.custom_capital_cad))


def _require_existing(args) -> None:
    if not (Path(args.root) / "run.json").exists():
        raise SystemExit(f"refused: no simulation initialised at {args.root} (use `run` after preflight)")


def _preflight(args, *, now=None) -> dict:
    provider = build_provider(args.source)
    http = resilient_http()
    quotes = CoinbaseQuotes(http) if args.source == "coinbase" else None
    return run_preflight(root=args.root, artifacts=_load_artifacts(args.artifacts),
                         approvals_root=args.approvals_root,
                         fetch=lambda inst, g: provider.fetch(inst, granularity_s=g),
                         quote=(lambda inst: quotes.quote(inst)) if quotes else None,
                         server_time=coinbase_server_time(http),
                         capital_cad=starting_capital(profile=args.capital_profile, custom_cad=args.custom_capital_cad),
                         now=now)


def _print_preflight(result: dict) -> None:
    for c in result["checks"]:
        print(f"{c['status']:4s} {c['name']}: {c['detail']}")
    print(f"PREFLIGHT {result['verdict']}")


def cmd_preflight(args) -> int:
    root_existed = Path(args.root).exists()
    result = _preflight(args)
    if not root_existed:
        try:
            Path(args.root).rmdir()  # preflight never leaves an initialised run behind
        except OSError:
            pass
    _print_preflight(result)
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result["verdict"] == "PASS" else 2


def cmd_run(args, *, presenter=None, sleep=time.sleep, clock=lambda: datetime.now(timezone.utc)) -> int:
    existing = (Path(args.root) / "run.json").exists()
    result = _preflight(args)
    _print_preflight(result)
    if result["verdict"] != "PASS":
        raise SystemExit(2)  # the 48-hour clock never starts on a failed preflight
    if not existing:
        Path(args.root).mkdir(parents=True, exist_ok=True)
        (Path(args.root) / "preflight.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    sim = _sim(args, presenter=presenter or _terminal_presenter)
    meta = json.loads(sim.meta_path.read_text(encoding="utf-8"))
    requested = starting_capital(profile=args.capital_profile, custom_cad=args.custom_capital_cad)
    if float(meta["starting_equity_cad"]) != requested:
        raise SystemExit(f"refused: {args.root} was initialised with CAD {meta['starting_equity_cad']:.2f}; "
                         f"requested CAD {requested:.2f}. Use a new --root for a new scenario (no silent reset).")
    end = datetime.fromisoformat(meta["started_utc"]) + timedelta(hours=args.hours)
    provider = build_provider(args.source)
    instruments = sorted({(a["instrument"], int(a["granularity_s"])) for a in sim.artifacts})
    print(f"run started_utc={meta['started_utc']} ends_utc={end.isoformat()} instruments={instruments}")
    while clock() < end:
        summary = sim.cycle(lambda inst, g: provider.fetch(inst, granularity_s=g), instruments)
        print(json.dumps(summary, sort_keys=True), flush=True)
        sleep(args.poll_seconds)
    print(json.dumps(sim.report(), indent=2, sort_keys=True, default=str))
    return 0


def cmd_attest(args, *, confirm=None) -> int:
    """R7 re-attestation: the operator must be present and type their own id. Never automated."""
    _require_existing(args)
    typed = (confirm or (lambda: input(f"Type your operator id ({args.operator}) to sign on for 1 hour: ")))()
    if str(typed).strip() != args.operator:
        raise SystemExit("refused: operator id not confirmed")
    sim = _sim(args)
    sim.attest_operator(args.operator)
    print("operator sign-on recorded (valid for R7 for 1 hour)")
    return 0


def cmd_report(args) -> int:
    _require_existing(args)
    rep = _sim(args, read_only=True).report()
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
    for name in ("preflight", "run", "attest", "report"):
        p = sub.add_parser(name)
        p.add_argument("--root", required=True)
        p.add_argument("--operator", required=name in ("run", "attest"), default="report-reader")
        p.add_argument("--approvals-root", default=str(DEFAULT_APPROVALS_ROOT))
        p.add_argument("--artifacts", default="artifacts/calibration")
        p.add_argument("--capital-profile", choices=("engineering", "standard", "small", "intermediate", "advanced", "custom"), default="engineering")
        p.add_argument("--custom-capital-cad", default=None)
        if name in ("run", "preflight"):
            p.add_argument("--source", default="coinbase", choices=["coinbase", "alpaca_crypto"])
        if name == "run":
            p.add_argument("--hours", type=float, default=48.0)
            p.add_argument("--poll-seconds", type=float, default=300.0)
        if name in ("report", "preflight"):
            p.add_argument("--out")
    args = ap.parse_args(argv)
    return {"preflight": cmd_preflight, "run": cmd_run, "attest": cmd_attest, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())

"""CSS live-data shadow paper runner (observation only).

    python scripts/css_shadow_paper_runner.py preflight --evidence-dir DIR --operator-id ID
    python scripts/css_shadow_paper_runner.py run       --evidence-dir DIR --operator-id ID [--max-cycles N]
    python scripts/css_shadow_paper_runner.py verify    --evidence-dir DIR

Real public BTC-USD / ETH-USD prices; simulated fills only; no broker connection.
Exit codes: 0 ok, 2 safety preflight/halt, 3 journal integrity failure, 5 feed not ready (preflight).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.shadow_paper.controls import SafetyPreflightError  # noqa: E402
from backend.shadow_paper.evidence import summarize  # noqa: E402
from backend.shadow_paper.journal import JournalIntegrityError  # noqa: E402
from backend.shadow_paper.runner import (  # noqa: E402
    BAR_INTERVAL_SECONDS,
    JOURNAL_FILENAME,
    ShadowPaperRunner,
)

LOGGER = logging.getLogger("css.shadow_paper")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "run"):
        p = sub.add_parser(name)
        p.add_argument("--evidence-dir", required=True, type=Path)
        p.add_argument("--operator-id", required=True)
        p.add_argument("--starting-equity", type=float, default=1000.0)
        if name == "run":
            p.add_argument("--max-cycles", type=int, default=0, help="0 = run until Ctrl+C")
    v = sub.add_parser("verify")
    v.add_argument("--evidence-dir", required=True, type=Path)
    return parser


def _print(obj: object) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, default=str))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = _parser().parse_args(argv)

    if args.command == "verify":
        summary = summarize(args.evidence_dir / JOURNAL_FILENAME)
        _print(summary)
        return 0 if summary.get("journal_integrity") == "PASS" else 3

    runner = ShadowPaperRunner(
        args.evidence_dir, operator_id=args.operator_id, starting_equity=args.starting_equity,
    )
    try:
        preflight = runner.start()
    except JournalIntegrityError as exc:
        print(f"REFUSED: journal integrity failure: {exc}", file=sys.stderr)
        return 3
    except SafetyPreflightError as exc:
        print("REFUSED: safety preflight failed:", file=sys.stderr)
        for failure in exc.failures:
            print(f"  - {failure}", file=sys.stderr)
        return 2

    _print({"preflight": preflight, "run_id": runner.run_id, "commit_sha": runner.commit_sha})
    if args.command == "preflight":
        probe = runner.probe_feed()
        _print({"feed_probe": probe})
        runner.stop("preflight_only")
        if not all(item["accepted"] for item in probe.values()):
            print("FEED NOT READY: at least one instrument returned no valid fresh quote", file=sys.stderr)
            return 5
        return 0

    cycles = 0
    try:
        while True:
            cycle_started = time.monotonic()
            runner.run_cycle()
            cycles += 1
            LOGGER.info(
                "cycle %d complete at %s; open=%d realized_net=%.6f halted=%s",
                cycles, datetime.now(timezone.utc).isoformat(), len(runner.positions),
                runner.realized_net, runner.entries_halted,
            )
            if args.max_cycles and cycles >= args.max_cycles:
                runner.stop("max_cycles_reached")
                return 0
            time.sleep(max(0.0, BAR_INTERVAL_SECONDS - (time.monotonic() - cycle_started)))
    except KeyboardInterrupt:
        runner.stop("operator_interrupt")
        return 0
    except SafetyPreflightError as exc:
        runner.stop("safety_halt")
        print("HALTED: safety recheck failed:", file=sys.stderr)
        for failure in exc.failures:
            print(f"  - {failure}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

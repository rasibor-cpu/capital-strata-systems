from __future__ import annotations
from datetime import datetime, timedelta, timezone

from data.models import Bar
from data.session import SessionPolicy
from data.validator_1m import OneMinuteValidator, OneMinuteValidationPolicy
from data.health import FeedHealthManager, HealthPolicy
from data.builder_5m import FiveMinuteBuilder


def make_bar(symbol: str, ts: datetime, o: float, c: float) -> Bar:
    h = max(o, c) * 1.0005
    l = min(o, c) * 0.9995
    return Bar(symbol=symbol, timeframe="1m", ts=ts, o=o, h=h, l=l, c=c, v=1000.0)


def main():
    symbol = "SPY"

    sess = SessionPolicy()
    vpol = OneMinuteValidationPolicy(latency_seconds=60, max_rel_jump=0.008)
    validator = OneMinuteValidator(vpol)
    health = FeedHealthManager(HealthPolicy(required_clean_minutes_to_resume=2))
    builder = FiveMinuteBuilder(symbol=symbol)

    # Example start time in UTC; choose something that usually maps into US session.
    start = datetime(2026, 1, 22, 14, 45, tzinfo=timezone.utc)

    print("Allowed window at start?", sess.is_within_allowed_window(start))
    print("Health (initial):", health.snapshot())

    # Feed 7 minutes of clean data
    price = 480.00
    for i in range(7):
        ts = start + timedelta(minutes=i)
        received = ts + timedelta(minutes=1, seconds=20)  # within latency
        bar = make_bar(symbol, ts, price, price + 0.05)

        ok, issue = validator.validate(bar, received)
        if not ok:
            health.mark_issue(issue)
            print(f"[{i}] ISSUE:", issue.code, "-", issue.message)
        else:
            resumed, msg = health.mark_clean_minute()
            if msg:
                print("HEALTH:", msg)

            bar5 = builder.push_1m(bar)
            if bar5:
                print("5m BAR:", bar5.ts.isoformat(), bar5.o, bar5.h, bar5.l, bar5.c)

        price += 0.02

    # Inject a gap (skips expected minutes) to force SAFE MODE
    print("\nInjecting a GAP to force SAFE MODE...")
    gap_ts = start + timedelta(minutes=9)  # missing minute 7 and 8
    received = gap_ts + timedelta(minutes=1, seconds=10)
    bad_bar = make_bar(symbol, gap_ts, price, price + 0.03)

    ok, issue = validator.validate(bad_bar, received)
    if not ok:
        health.mark_issue(issue)
        print("GAP ISSUE:", issue.code, "-", issue.message)

    print("Health (after issue):", health.snapshot())

    # Simulate reconnect: new validator + health manager
    print("\nSimulating feed reconnect (fresh validator/health)...")
    validator = OneMinuteValidator(vpol)
    health = FeedHealthManager(HealthPolicy(required_clean_minutes_to_resume=2))

    ts0 = start + timedelta(minutes=20)
    price = 481.00
    for i in range(2):
        ts = ts0 + timedelta(minutes=i)
        received = ts + timedelta(minutes=1, seconds=15)
        bar = make_bar(symbol, ts, price, price + 0.02)

        ok, issue = validator.validate(bar, received)
        if ok:
            resumed, msg = health.mark_clean_minute()
            if msg:
                print("HEALTH:", msg)
        else:
            health.mark_issue(issue)
            print("ISSUE:", issue.code, "-", issue.message)

        price += 0.01

    print("Health (final):", health.snapshot())


if __name__ == "__main__":
    main()

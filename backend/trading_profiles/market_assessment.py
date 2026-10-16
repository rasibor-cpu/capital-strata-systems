"""CSS market-assessment source for manual paper orders.

A manual order carries the user's decision: instrument, side, size and stop. The CSS gates
also need CSS's own view of the market (probability, expected move, costs, regime, price),
which the user must not be able to supply. This store keeps the most recent assessment the
CSS engine produced for each (symbol, side), recorded whenever a CSS engine signal enters
the governed router, and serves it only while fresh.

Rules: no assessment, a stale one, a different asset class or the opposite side -> no
assessment (the order is rejected, never filled on defaults). The reference price always
comes from CSS, never from the user.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from backend.certification.ov002_persistence import PersistenceError, atomic_write_json, read_json_object
from backend.runtime.interprocess_lock import exclusive_file_lock

SCHEMA = "css.trading_profiles.market_assessments.v1"
DEFAULT_TTL = timedelta(minutes=5)
ASSESSMENT_FIELDS = ("reference_price", "probability", "signal_score", "confidence", "expected_move_bps", "fee_bps",
                     "spread_bps", "slippage_bps", "risk_reward", "market_regime", "strategy_score",
                     "replay_confidence", "liquidity_score", "regime_alignment", "risk_score", "volatility_state",
                     "regime_persistence")


class MarketAssessmentStore:
    def __init__(self, root: Path | str, *, ttl: timedelta = DEFAULT_TTL) -> None:
        self.root = Path(root)
        self.path = self.root / "css_market_assessments.json"
        self.lock_path = self.root / "css_market_assessments.lock"
        self.ttl = ttl

    @staticmethod
    def _key(symbol: str, side: str) -> str:
        return f"{str(symbol).strip().upper()}|{str(side).strip().upper()}"

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            doc = read_json_object(self.path)
        except PersistenceError:
            return {}  # unreadable -> no assessment -> manual orders rejected (fail closed)
        return doc.get("assessments", {}) if doc.get("schema") == SCHEMA else {}

    def record(self, signal: Any, *, now: datetime) -> None:
        """Record a CSS engine signal's market view (callers pass only CSS engine signals)."""
        body = asdict(signal)
        entry = {k: body[k] for k in ASSESSMENT_FIELDS}
        entry.update({"asset_class": str(body["asset_class"]).upper(), "source_signal_id": body["signal_id"],
                      "assessed_at_utc": now.isoformat()})
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path, timeout_seconds=10.0):
            items = self._read()
            items[self._key(body["symbol"], body["side"])] = entry
            atomic_write_json(self.path, {"schema": SCHEMA, "assessments": items}, expected_root=self.root)

    def get(self, symbol: str, asset_class: str, side: str, *, now: datetime) -> dict[str, Any] | None:
        entry = self._read().get(self._key(symbol, side))
        if not entry or entry.get("asset_class") != str(asset_class).strip().upper():
            return None
        try:
            assessed = datetime.fromisoformat(entry["assessed_at_utc"])
        except (KeyError, ValueError):
            return None
        if assessed > now or now - assessed > self.ttl:
            return None
        return dict(entry)

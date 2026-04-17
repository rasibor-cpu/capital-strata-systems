"""
Capital Strata Systems (CSS)
Broker Gate Audit Logger

Purpose
-------
Writes an audit record every time any broker/instrument execution gate
blocks or allows an order attempt.

This module is broker-neutral and instrument-neutral.

It does NOT place orders.
It only records gate decisions for governance, debugging, and future
compliance/audit review.

Default output:
    audit_logs/broker_gate_audit.jsonl
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class BrokerGateAuditLogger:
    def __init__(self, audit_file: Optional[Path] = None) -> None:
        self.audit_file = audit_file or Path("audit_logs") / "broker_gate_audit.jsonl"
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)

    def log_decision(
        self,
        *,
        broker: str,
        gate_name: str,
        allowed: bool,
        reason: str,
        symbol: str = "",
        instrument: str = "",
        asset_class: str = "",
        size: float = 0.0,
        size_unit: str = "",
        selected_broker: str = "",
        broker_mode: str = "",
        engine_mode: str = "",
        execution_armed: bool = False,
        live_orders_flag: bool = False,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload: Dict[str, Any] = {
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "event": "broker_gate_decision",
            "broker": str(broker),
            "gate_name": str(gate_name),
            "allowed": bool(allowed),
            "reason": str(reason),
            "symbol": str(symbol),
            "instrument": str(instrument or symbol),
            "asset_class": str(asset_class),
            "size": float(size),
            "size_unit": str(size_unit),
            "selected_broker": str(selected_broker),
            "broker_mode": str(broker_mode),
            "engine_mode": str(engine_mode),
            "execution_armed": bool(execution_armed),
            "live_orders_flag": bool(live_orders_flag),
            "extra": extra or {},
        }

        with open(self.audit_file, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
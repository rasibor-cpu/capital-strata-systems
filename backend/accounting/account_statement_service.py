from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEDGER_FILE = PROJECT_ROOT / "artifacts" / "css_account_ledger.jsonl"

VALID_ENTRY_TYPES = {"DEBIT", "CREDIT"}
VALID_DATE_BASES = {"transaction", "value", "settlement"}
VALID_PERIODS = {"all", "daily", "weekly", "monthly", "annual", "custom"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value if value not in (None, "") else "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _date_window(period: str, *, today: date, date_from: str = "", date_to: str = "") -> tuple[date | None, date | None]:
    p = str(period or "all").strip().lower()
    if p not in VALID_PERIODS:
        raise ValueError("period must be all, daily, weekly, monthly, annual, or custom")
    if p == "all":
        return None, None
    if p == "daily":
        return today, today
    if p == "weekly":
        return today - timedelta(days=today.weekday()), today
    if p == "monthly":
        return today.replace(day=1), today
    if p == "annual":
        return today.replace(month=1, day=1), today

    start = _parse_date(date_from)
    end = _parse_date(date_to)
    if start is None or end is None:
        raise ValueError("custom period requires valid date_from and date_to")
    if end < start:
        raise ValueError("date_to cannot precede date_from")
    return start, end


@dataclass(frozen=True)
class StatementQuery:
    user_id: str
    period: str = "all"
    entry_type: str = "ALL"
    date_basis: str = "transaction"
    date_from: str = ""
    date_to: str = ""
    limit: int = 1000

    def normalized(self) -> "StatementQuery":
        uid = str(self.user_id or "").strip()
        if not uid:
            raise ValueError("user_id is required")
        period = str(self.period or "all").strip().lower()
        if period not in VALID_PERIODS:
            raise ValueError("invalid period")
        entry_type = str(self.entry_type or "ALL").strip().upper()
        if entry_type not in VALID_ENTRY_TYPES | {"ALL"}:
            raise ValueError("entry_type must be ALL, DEBIT, or CREDIT")
        date_basis = str(self.date_basis or "transaction").strip().lower()
        if date_basis not in VALID_DATE_BASES:
            raise ValueError("date_basis must be transaction, value, or settlement")
        return StatementQuery(
            user_id=uid,
            period=period,
            entry_type=entry_type,
            date_basis=date_basis,
            date_from=str(self.date_from or "").strip(),
            date_to=str(self.date_to or "").strip(),
            limit=max(1, min(int(self.limit or 1000), 5000)),
        )


class AccountStatementService:
    """Append-only user account ledger and read-only statement generator."""

    def __init__(self, ledger_file: Path = LEDGER_FILE) -> None:
        self.ledger_file = ledger_file

    def record_entry(
        self,
        *,
        user_id: str,
        entry_type: str,
        amount: Any,
        currency: str,
        description: str,
        transaction_date: str | None = None,
        value_date: str | None = None,
        settlement_date: str | None = None,
        reference: str = "",
        source_type: str = "SYSTEM",
        source_id: str = "",
        broker: str = "",
        asset_class: str = "",
        symbol: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        uid = str(user_id or "").strip()
        if not uid:
            raise ValueError("user_id is required")
        kind = str(entry_type or "").strip().upper()
        if kind not in VALID_ENTRY_TYPES:
            raise ValueError("entry_type must be DEBIT or CREDIT")
        numeric_amount = _decimal(amount)
        if numeric_amount < 0:
            raise ValueError("amount cannot be negative")
        transaction_ts = str(transaction_date or _utc_now())
        value_ts = str(value_date or transaction_ts)
        settlement_ts = str(settlement_date or value_ts)
        row = {
            "ledger_id": f"{uid}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            "user_id": uid,
            "entry_type": kind,
            "amount": format(numeric_amount, "f"),
            "currency": str(currency or "USD").strip().upper() or "USD",
            "description": str(description or "").strip(),
            "transaction_date": transaction_ts,
            "value_date": value_ts,
            "settlement_date": settlement_ts,
            "reference": str(reference or "").strip(),
            "source_type": str(source_type or "SYSTEM").strip().upper(),
            "source_id": str(source_id or "").strip(),
            "broker": str(broker or "").strip().upper(),
            "asset_class": str(asset_class or "").strip().upper(),
            "symbol": str(symbol or "").strip().upper(),
            "metadata": dict(metadata or {}),
            "recorded_at": _utc_now(),
        }
        self.ledger_file.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
        return row

    def _entries(self) -> list[dict[str, Any]]:
        try:
            lines = self.ledger_file.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        rows: list[dict[str, Any]] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows

    def statement(self, query: StatementQuery, *, today: date | None = None) -> dict[str, Any]:
        q = query.normalized()
        start, end = _date_window(
            q.period,
            today=today or datetime.now(timezone.utc).date(),
            date_from=q.date_from,
            date_to=q.date_to,
        )
        date_key = {
            "transaction": "transaction_date",
            "value": "value_date",
            "settlement": "settlement_date",
        }[q.date_basis]

        selected: list[dict[str, Any]] = []
        for row in self._entries():
            if str(row.get("user_id") or "") != q.user_id:
                continue
            if q.entry_type != "ALL" and str(row.get("entry_type") or "").upper() != q.entry_type:
                continue
            row_date = _parse_date(row.get(date_key))
            if start is not None and (row_date is None or row_date < start):
                continue
            if end is not None and (row_date is None or row_date > end):
                continue
            selected.append(dict(row))

        selected.sort(key=lambda row: str(row.get(date_key) or ""), reverse=True)
        selected = selected[: q.limit]
        debit_total = sum((_decimal(r.get("amount")) for r in selected if str(r.get("entry_type")).upper() == "DEBIT"), Decimal("0"))
        credit_total = sum((_decimal(r.get("amount")) for r in selected if str(r.get("entry_type")).upper() == "CREDIT"), Decimal("0"))
        return {
            "user_id": q.user_id,
            "period": q.period,
            "date_basis": q.date_basis,
            "entry_type": q.entry_type,
            "date_from": None if start is None else start.isoformat(),
            "date_to": None if end is None else end.isoformat(),
            "transactions": selected,
            "transaction_count": len(selected),
            "debit_total": format(debit_total, "f"),
            "credit_total": format(credit_total, "f"),
            "net_movement": format(credit_total - debit_total, "f"),
            "generated_at": _utc_now(),
            "read_only": True,
        }

    @staticmethod
    def to_csv(statement: dict[str, Any]) -> str:
        output = io.StringIO()
        fields = [
            "transaction_date",
            "value_date",
            "settlement_date",
            "entry_type",
            "amount",
            "currency",
            "description",
            "reference",
            "source_type",
            "source_id",
            "broker",
            "asset_class",
            "symbol",
        ]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in statement.get("transactions") or []:
            if isinstance(row, dict):
                writer.writerow(row)
        return output.getvalue()


__all__ = [
    "AccountStatementService",
    "StatementQuery",
    "VALID_DATE_BASES",
    "VALID_ENTRY_TYPES",
    "VALID_PERIODS",
]

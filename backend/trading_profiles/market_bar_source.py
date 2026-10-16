"""Authorized market-bar sources for the CSS-118 B1 calibrated signal producer.

Only replayable CSV (or future licensed feed adapters) may supply prices.
Synthetic invented prices are forbidden for routing provenance.
"""
from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence


@dataclass(frozen=True)
class BarRecord:
    instrument: str
    ts_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    source_id: str
    content_hash: str


class BarSourceError(RuntimeError):
    pass


def _parse_ts(raw: object) -> datetime:
    if raw is None or str(raw).strip() == "":
        raise BarSourceError("bar_timestamp_missing")
    text = str(raw).strip()
    try:
        if text.replace(".", "", 1).isdigit():
            value = float(text)
            if value > 1e12:
                value /= 1000.0
            return datetime.fromtimestamp(value, tz=timezone.utc)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, OSError) as exc:
        raise BarSourceError(f"bar_timestamp_invalid:{raw!r}") from exc


def _f(row: dict[str, str], *keys: str) -> float:
    for key in keys:
        if key in row and str(row[key]).strip() != "":
            try:
                return float(str(row[key]).replace(",", ""))
            except ValueError as exc:
                raise BarSourceError(f"bar_numeric_invalid:{key}") from exc
    raise BarSourceError(f"bar_field_missing:{'/'.join(keys)}")


class ReplayCsvBarSource:
    """Load OHLC bars from a certified/replay CSV. Fail closed on empty or malformed input."""

    def __init__(self, csv_path: Path | str, *, instrument: str, source_id: str = "replay_csv") -> None:
        self.csv_path = Path(csv_path)
        self.instrument = str(instrument).strip()
        self.source_id = source_id
        if not self.instrument:
            raise BarSourceError("instrument_required")
        if not self.csv_path.is_file():
            raise BarSourceError(f"csv_not_found:{self.csv_path}")

    def iter_bars(self) -> Iterator[BarRecord]:
        with self.csv_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                raise BarSourceError("csv_headers_missing")
            norm_fields = {h: (h or "").strip().lower() for h in reader.fieldnames}
            count = 0
            for row in reader:
                nrow = {norm_fields.get(k, k): (v if v is not None else "") for k, v in row.items()}
                ts = _parse_ts(nrow.get("ts_utc") or nrow.get("timestamp") or nrow.get("time") or nrow.get("date"))
                o = _f(nrow, "open")
                h = _f(nrow, "high")
                low = _f(nrow, "low")
                c = _f(nrow, "close")
                vol = 0.0
                try:
                    vol = _f(nrow, "volume", "vol")
                except BarSourceError:
                    vol = 0.0
                if not all(x > 0 and x == x for x in (o, h, low, c)):
                    raise BarSourceError("bar_prices_invalid")
                if h < max(o, c) or low > min(o, c):
                    raise BarSourceError("bar_ohlc_inconsistent")
                payload = f"{self.instrument}|{ts.isoformat()}|{o}|{h}|{low}|{c}|{vol}"
                digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
                yield BarRecord(
                    instrument=self.instrument,
                    ts_utc=ts,
                    open=o,
                    high=h,
                    low=low,
                    close=c,
                    volume=vol,
                    source_id=self.source_id,
                    content_hash=digest,
                )
                count += 1
            if count == 0:
                raise BarSourceError("csv_empty")

    def load(self) -> list[BarRecord]:
        return list(self.iter_bars())


def write_fixture_csv(path: Path | str, rows: Sequence[tuple[str, float, float, float, float]]) -> Path:
    """Test helper: write a minimal OHLC CSV. Not a live data source."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ts_utc", "open", "high", "low", "close", "volume"])
        for ts, o, h, low, c in rows:
            writer.writerow([ts, o, h, low, c, 1000])
    return out

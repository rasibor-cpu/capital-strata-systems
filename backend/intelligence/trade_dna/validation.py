"""DIP-002 Trade DNA validation rules for immutable fact records."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional

from backend.intelligence.trade_dna.constants import (
    COMPATIBLE_SCHEMA_PREFIX,
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
)
from backend.intelligence.trade_dna.hashing import verify_content_hash
from backend.intelligence.trade_dna.schema import TradeDNARecord, trade_dna_from_dict


class TradeDNAValidationError(ValueError):
    """Raised when a Trade DNA fact record fails validation."""

    def __init__(self, code: str, detail: Optional[str] = None) -> None:
        self.code = code
        self.detail = detail
        message = code if detail is None else f"{code}:{detail}"
        super().__init__(message)


def _parse_iso(value: Optional[str], *, field: str) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise TradeDNAValidationError("invalid_timestamp_type", field)
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise TradeDNAValidationError("invalid_timestamp", field) from exc


def _require_positive_price(value: Any, *, field: str) -> None:
    if value is None:
        return
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TradeDNAValidationError("invalid_price_type", field) from exc
    if number != number or number in (float("inf"), float("-inf")):  # NaN/inf
        raise TradeDNAValidationError("invalid_price", field)
    if number <= 0:
        raise TradeDNAValidationError("non_positive_price", field)


def _require_non_negative(value: Any, *, field: str) -> None:
    if value is None:
        return
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TradeDNAValidationError("invalid_numeric_type", field) from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise TradeDNAValidationError("invalid_numeric", field)
    if number < 0:
        raise TradeDNAValidationError("negative_numeric", field)


def validate_schema_version(schema_version: str, *, allow_compatible: bool = False) -> None:
    if schema_version in SUPPORTED_SCHEMA_VERSIONS:
        return
    if allow_compatible and schema_version.startswith(COMPATIBLE_SCHEMA_PREFIX):
        # Future minor readers may accept older css.trade_dna.v* once registered.
        # Unknown future majors still fail closed unless explicitly supported.
        if schema_version == SCHEMA_VERSION:
            return
        raise TradeDNAValidationError("unsupported_schema_version", schema_version)
    raise TradeDNAValidationError("unsupported_schema_version", schema_version)


def validate_trade_dna(
    record: TradeDNARecord | Mapping[str, Any],
    *,
    require_hash: bool = True,
    allow_compatible_schema: bool = False,
) -> TradeDNARecord:
    """Validate required fields, types, prices, timestamps, instrument, and hash."""
    if isinstance(record, Mapping):
        try:
            dna = trade_dna_from_dict(record)
        except (TypeError, ValueError) as exc:
            raise TradeDNAValidationError("deserialize_failed", str(exc)) from exc
    else:
        dna = record

    validate_schema_version(dna.schema_version, allow_compatible=allow_compatible_schema)

    if not dna.identity.trade_id:
        raise TradeDNAValidationError("missing_required_field", "identity.trade_id")
    if not dna.identity.dna_id:
        raise TradeDNAValidationError("missing_required_field", "identity.dna_id")

    if dna.revision.revision < 1:
        raise TradeDNAValidationError("invalid_revision", "revision must be >= 1")
    if dna.revision.revision > 1 and not dna.revision.supersedes_dna_id:
        raise TradeDNAValidationError("revision_missing_supersedes", dna.identity.dna_id)
    if dna.revision.supersedes_dna_id == dna.identity.dna_id:
        raise TradeDNAValidationError("revision_self_reference", dna.identity.dna_id)

    instrument = dna.identity.instrument
    market_symbol = dna.market.symbol
    if instrument and market_symbol and str(instrument) != str(market_symbol):
        raise TradeDNAValidationError(
            "instrument_inconsistency",
            f"{instrument}!={market_symbol}",
        )

    _require_positive_price(dna.execution.entry_price, field="execution.entry_price")
    _require_positive_price(dna.execution.exit_price, field="execution.exit_price")
    _require_non_negative(dna.execution.requested_quantity, field="execution.requested_quantity")
    _require_non_negative(dna.execution.filled_quantity, field="execution.filled_quantity")
    _require_non_negative(dna.execution.fees, field="execution.fees")
    _require_non_negative(dna.volatility.atr, field="volatility.atr")

    opened = _parse_iso(dna.timing.opened_at, field="timing.opened_at")
    closed = _parse_iso(dna.timing.closed_at, field="timing.closed_at")
    decision = _parse_iso(dna.timing.decision_at, field="timing.decision_at")
    executed = _parse_iso(dna.timing.executed_at, field="timing.executed_at")
    _parse_iso(dna.revision.created_at, field="revision.created_at")
    _parse_iso(dna.evidence_custody.captured_at, field="evidence_custody.captured_at")

    if opened and closed and closed < opened:
        raise TradeDNAValidationError("timestamp_order", "closed_at<opened_at")
    if decision and executed and executed < decision:
        raise TradeDNAValidationError("timestamp_order", "executed_at<decision_at")
    if opened and executed and executed < opened:
        raise TradeDNAValidationError("timestamp_order", "executed_at<opened_at")

    if not dna.evidence_custody.evidence_version:
        raise TradeDNAValidationError("missing_required_field", "evidence_custody.evidence_version")

    payload = dna.to_dict()
    if require_hash:
        if not dna.content_hash:
            raise TradeDNAValidationError("missing_content_hash")
        if not verify_content_hash(payload):
            raise TradeDNAValidationError("content_hash_mismatch")

    return dna

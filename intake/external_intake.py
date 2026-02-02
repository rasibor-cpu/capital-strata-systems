"""
external_intake.py — REA Capital Trading Engine
----------------------------------------------
Purpose:
- Standardize intake of “external prompts/signals” from sources like Finelo, newsletters,
  YouTube educators, Discord/Telegram callouts, etc.
- Normalize into a consistent payload REA can analyze (prompt-only).
- Persist as JSONL in reporting_store/external_intake/YYYY-MM-DD/<source>.jsonl

Hard constraints:
- NO trade execution
- NO auto-risk escalation
- Intake + normalization + logging only

This file is additive (safe). Engine integration can come later.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime, date
import json
import os
import re


# -----------------------------
# Data model
# -----------------------------

@dataclass
class SourceMeta:
    source_name: str               # e.g., "finelo"
    source_type: str               # e.g., "course", "newsletter", "social", "app"
    captured_at_iso: str           # ISO timestamp (device time is acceptable)
    captured_by: str = "manual"    # "manual" | "copy_paste" | "screenshot_note"
    source_url: Optional[str] = None
    raw_text: Optional[str] = None


@dataclass
class ExternalSignal:
    """
    Normalized “external idea” object.
    This is NOT an instruction to trade. It is an input to REA’s analysis workflow.
    """
    symbol: str                    # e.g., "AAPL", "BTC/USD"
    asset_class: str               # "equity" | "crypto" | "fx" | "etf" | "index" | "other"
    timeframe: str                 # "1m" | "5m" | "15m" | "1h" | "4h" | "1d" | etc.
    setup_type: str                # "breakout" | "mean_reversion" | "trend_pullback" | etc.
    bias: str                      # "long" | "short" | "both" | "unknown"

    # Optional trade-plan hints (still non-binding)
    entry: Optional[str] = None    # free text
    stop: Optional[str] = None     # free text
    target: Optional[str] = None   # free text
    invalidation: Optional[str] = None

    confidence: Optional[float] = None  # 0..1 if provided by user/source
    notes: Optional[str] = None         # any extra context

    meta: Optional[SourceMeta] = None


# -----------------------------
# Normalization helpers
# -----------------------------

_ALLOWED_TIMEFRAMES = {"1m","2m","3m","5m","10m","15m","30m","45m","1h","2h","4h","1d","1w"}
_ALLOWED_BIAS = {"long","short","both","unknown"}

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _clean_symbol(sym: str) -> str:
    s = (sym or "").strip().upper()
    s = s.replace(" ", "")
    return s

def _infer_asset_class(symbol: str) -> str:
    """
    Light heuristic:
    - contains "/" and looks like FX/crypto pair => "fx" or "crypto" unknown, default "fx"
    - otherwise equity-like => "equity"
    You can override when calling.
    """
    if "/" in symbol:
        # Could be "EUR/USD" or "BTC/USD"
        # Heuristic: if first leg is BTC/ETH/SOL etc -> crypto else fx
        base = symbol.split("/")[0]
        if base in {"BTC","ETH","SOL","BNB","XRP","ADA","DOGE","AVAX","MATIC","LTC","BCH","DOT","LINK"}:
            return "crypto"
        return "fx"
    return "equity"

def _normalize_setup(setup: str) -> str:
    s = (setup or "").strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    if not s:
        return "unknown_setup"
    return s

def _normalize_timeframe(tf: str) -> str:
    t = (tf or "").strip().lower()
    t = t.replace("min", "m").replace("mins","m").replace("hour","h").replace("hours","h")
    t = t.replace(" ", "")
    # common variants
    if t == "60m":
        t = "1h"
    if t == "240m":
        t = "4h"
    return t

def validate_external_signal(sig: ExternalSignal) -> List[str]:
    errors: List[str] = []
    if not sig.symbol or len(sig.symbol) < 2:
        errors.append("symbol is required")
    if not sig.timeframe:
        errors.append("timeframe is required")
    if sig.timeframe and _normalize_timeframe(sig.timeframe) not in _ALLOWED_TIMEFRAMES:
        errors.append(f"unsupported timeframe: {sig.timeframe} (allowed: {sorted(_ALLOWED_TIMEFRAMES)})")
    if not sig.setup_type:
        errors.append("setup_type is required")
    if sig.bias not in _ALLOWED_BIAS:
        errors.append(f"unsupported bias: {sig.bias} (allowed: {sorted(_ALLOWED_BIAS)})")
    if sig.confidence is not None:
        try:
            c = float(sig.confidence)
            if not (0.0 <= c <= 1.0):
                errors.append("confidence must be between 0 and 1")
        except Exception:
            errors.append("confidence must be a number between 0 and 1")
    return errors

def normalize_external_signal(sig: ExternalSignal) -> ExternalSignal:
    symbol = _clean_symbol(sig.symbol)
    timeframe = _normalize_timeframe(sig.timeframe)
    setup_type = _normalize_setup(sig.setup_type)
    bias = (sig.bias or "unknown").strip().lower()
    if bias not in _ALLOWED_BIAS:
        bias = "unknown"

    asset_class = (sig.asset_class or "").strip().lower()
    if not asset_class or asset_class == "auto":
        asset_class = _infer_asset_class(symbol)

    meta = sig.meta
    if meta is None:
        meta = SourceMeta(
            source_name="unknown",
            source_type="unknown",
            captured_at_iso=_now_iso(),
            captured_by="manual",
        )
    else:
        # Ensure timestamp exists
        if not meta.captured_at_iso:
            meta.captured_at_iso = _now_iso()

    return ExternalSignal(
        symbol=symbol,
        asset_class=asset_class,
        timeframe=timeframe,
        setup_type=setup_type,
        bias=bias,
        entry=sig.entry,
        stop=sig.stop,
        target=sig.target,
        invalidation=sig.invalidation,
        confidence=sig.confidence,
        notes=sig.notes,
        meta=meta,
    )


# -----------------------------
# Storage (JSONL)
# -----------------------------

def _default_store_dir() -> str:
    """
    Store under reporting_store/external_intake/YYYY-MM-DD/
    relative to repo working directory (source/REA-capital-trading-engine).
    """
    d = date.today().isoformat()
    return os.path.join("reporting_store", "external_intake", d)

def write_signal_jsonl(sig: ExternalSignal, store_dir: Optional[str] = None) -> str:
    """
    Appends one normalized signal as a JSON line.
    Returns filepath written to.
    """
    store_dir = store_dir or _default_store_dir()
    os.makedirs(store_dir, exist_ok=True)

    source = (sig.meta.source_name if sig.meta else "unknown") or "unknown"
    source = re.sub(r"[^a-zA-Z0-9_\-]+", "_", source.strip().lower()) or "unknown"
    path = os.path.join(store_dir, f"{source}.jsonl")

    payload = asdict(sig)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    return path


# -----------------------------
# Convenience builders (Finelo etc.)
# -----------------------------

def finelo_intake(
    symbol: str,
    timeframe: str,
    setup_type: str,
    bias: str = "unknown",
    notes: Optional[str] = None,
    source_url: Optional[str] = None,
    raw_text: Optional[str] = None,
) -> ExternalSignal:
    """
    Build an ExternalSignal tagged as Finelo.
    """
    sig = ExternalSignal(
        symbol=symbol,
        asset_class="auto",
        timeframe=timeframe,
        setup_type=setup_type,
        bias=bias,
        notes=notes,
        meta=SourceMeta(
            source_name="finelo",
            source_type="course",
            captured_at_iso=_now_iso(),
            captured_by="manual",
            source_url=source_url,
            raw_text=raw_text,
        ),
    )
    sig = normalize_external_signal(sig)
    errs = validate_external_signal(sig)
    if errs:
        raise ValueError("Invalid finelo intake: " + "; ".join(errs))
    return sig


def generic_intake(
    source_name: str,
    source_type: str,
    symbol: str,
    timeframe: str,
    setup_type: str,
    bias: str = "unknown",
    notes: Optional[str] = None,
    source_url: Optional[str] = None,
    raw_text: Optional[str] = None,
) -> ExternalSignal:
    """
    Build an ExternalSignal tagged to any external source.
    """
    sig = ExternalSignal(
        symbol=symbol,
        asset_class="auto",
        timeframe=timeframe,
        setup_type=setup_type,
        bias=bias,
        notes=notes,
        meta=SourceMeta(
            source_name=(source_name or "unknown").strip().lower(),
            source_type=(source_type or "unknown").strip().lower(),
            captured_at_iso=_now_iso(),
            captured_by="manual",
            source_url=source_url,
            raw_text=raw_text,
        ),
    )
    sig = normalize_external_signal(sig)
    errs = validate_external_signal(sig)
    if errs:
        raise ValueError("Invalid generic intake: " + "; ".join(errs))
    return sig


# -----------------------------
# Tiny self-test runner (optional)
# -----------------------------

if __name__ == "__main__":
    # Example usage (does not trade)
    demo = finelo_intake(
        symbol="AAPL",
        timeframe="1d",
        setup_type="trend_pullback",
        bias="long",
        notes="Demo intake from Finelo-like plan.",
        source_url="https://quiz.finelo.com/",
        raw_text="Trend pullback idea, wait for confirmation candle.",
    )
    out = write_signal_jsonl(demo)
    print("WROTE:", out)
    print("OK:", demo.symbol, demo.timeframe, demo.setup_type, demo.bias, demo.asset_class)

"""Phase 178A — symbol normalization for Options Income advisory paths."""

from __future__ import annotations

import re
from typing import Any

_CRYPTO_SEP = re.compile(r"^([A-Z0-9]{2,10})[-_/](USD|USDT|USDC|CAD|EUR|BTC|ETH)$", re.I)
_CA_SUFFIX = re.compile(r"^([A-Z0-9.\-]+)\.(TO|V|CN)$", re.I)
_OCC_LIKE = re.compile(
    r"^([A-Z]{1,6})(\d{6})([CP])(\d{8})$",
    re.I,
)


def normalize_equity_symbol(raw: str | None) -> dict[str, Any]:
    """Normalize equity/ETF symbols; keep crypto aliases out of listed-options paths."""
    text = str(raw or "").strip().upper().replace(" ", "")
    if not text:
        return {
            "canonical": None,
            "provider_native": None,
            "asset_class": "UNKNOWN",
            "exchange_suffix": None,
            "currency_hint": None,
            "listed_options_eligible_symbol": False,
            "status": "EMPTY",
        }

    crypto = _CRYPTO_SEP.match(text)
    if crypto or text in {"BTC", "ETH", "SOL", "XRP"} or text.endswith("_USD") or text.endswith("-USD"):
        native = text.replace("_", "-")
        return {
            "canonical": native,
            "provider_native": text,
            "asset_class": "CRYPTO",
            "exchange_suffix": None,
            "currency_hint": crypto.group(2).upper() if crypto else "USD",
            "listed_options_eligible_symbol": False,
            "status": "CRYPTO_ALIAS",
            "note": "Crypto symbols must not contaminate listed-equity option logic",
        }

    ca = _CA_SUFFIX.match(text)
    if ca:
        root = ca.group(1).upper()
        suffix = ca.group(2).upper()
        return {
            "canonical": f"{root}.{suffix}",
            "provider_native": text,
            "asset_class": "EQUITY_CA",
            "exchange_suffix": suffix,
            "currency_hint": "CAD",
            "listed_options_eligible_symbol": True,
            "status": "OK",
        }

    if text.endswith(":US") or text.endswith(".US"):
        root = text.split(":")[0].split(".")[0]
        return {
            "canonical": root,
            "provider_native": text,
            "asset_class": "EQUITY_US",
            "exchange_suffix": "US",
            "currency_hint": "USD",
            "listed_options_eligible_symbol": True,
            "status": "OK",
        }

    clean = text.replace("/", "").replace("-", "") if len(text) <= 6 else text
    # Prefer simple ticker for US listings
    ticker = re.sub(r"[^A-Z0-9.]", "", text)
    return {
        "canonical": ticker or clean,
        "provider_native": text,
        "asset_class": "EQUITY",
        "exchange_suffix": None,
        "currency_hint": None,
        "listed_options_eligible_symbol": bool(ticker) and len(ticker) <= 6,
        "status": "OK",
    }


def parse_occ_option_symbol(raw: str | None) -> dict[str, Any]:
    text = str(raw or "").strip().upper()
    m = _OCC_LIKE.match(text)
    if not m:
        return {
            "canonical": None,
            "provider_native": text or None,
            "status": "UNPARSED",
            "underlying": None,
            "expiration": None,
            "option_type": None,
            "strike": None,
        }
    underlying, yymmdd, cp, strike_raw = m.groups()
    strike = int(strike_raw) / 1000.0
    expiration = f"20{yymmdd[0:2]}-{yymmdd[2:4]}-{yymmdd[4:6]}"
    return {
        "canonical": text,
        "provider_native": text,
        "status": "OK",
        "underlying": underlying,
        "expiration": expiration,
        "option_type": "CALL" if cp == "C" else "PUT",
        "strike": strike,
        "strike_precision": 3,
    }


def build_occ_option_symbol(
    *,
    underlying: str,
    expiration: str,
    option_type: str,
    strike: float,
) -> str:
    """Build a simple OCC-like symbol (root + YYMMDD + C/P + strike*1000)."""
    root = normalize_equity_symbol(underlying)["canonical"] or str(underlying).upper()
    root = re.sub(r"[^A-Z0-9]", "", str(root))[:6]
    exp = str(expiration).replace("-", "")
    if len(exp) == 8:
        yymmdd = exp[2:]
    elif len(exp) == 6:
        yymmdd = exp
    else:
        yymmdd = "000000"
    cp = "C" if str(option_type).upper().startswith("C") else "P"
    strike_i = int(round(float(strike) * 1000))
    return f"{root}{yymmdd}{cp}{strike_i:08d}"


__all__ = [
    "build_occ_option_symbol",
    "normalize_equity_symbol",
    "parse_occ_option_symbol",
]

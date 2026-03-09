from __future__ import annotations

import requests
from typing import List, Dict, Any


COINBASE_PRODUCTS_URL = "https://api.exchange.coinbase.com/products"


def fetch_all_products() -> List[Dict[str, Any]]:
    """
    Fetch all Coinbase products.
    """
    r = requests.get(COINBASE_PRODUCTS_URL, timeout=15)
    r.raise_for_status()
    return r.json()


def filter_usd_crypto_pairs(products: List[Dict[str, Any]]) -> List[str]:
    """
    Keep only crypto USD pairs like BTC-USD.
    """
    pairs: List[str] = []

    for p in products:
        pid = p.get("id", "")
        if not isinstance(pid, str):
            continue

        if not pid.endswith("-USD"):
            continue

        if pid.startswith("USD-"):
            continue

        pairs.append(pid)

    return pairs


def rank_pairs_by_liquidity(pairs: List[str], limit: int = 200) -> List[str]:
    """
    Simple liquidity proxy: prefer shorter symbols first
    (BTC, ETH, etc). Later we will improve with volume.
    """
    pairs = sorted(pairs)
    return pairs[:limit]


def get_top_universe(limit: int = 200) -> List[str]:
    """
    Return the top N crypto USD pairs.
    """
    products = fetch_all_products()

    usd_pairs = filter_usd_crypto_pairs(products)

    return rank_pairs_by_liquidity(usd_pairs, limit)
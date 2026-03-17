from typing import List, Dict, Any


class VWAPDeviationEngine:
    """
    Detects how far price deviates from VWAP.

    Institutional logic:
    large deviation → higher probability of mean reversion
    """

    def enrich_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        for r in rows:

            price = float(r.get("price", 0))
            vwap = float(r.get("vwap", 0))

            if vwap <= 0:
                r["vwap_dev"] = 0.0
                r["vwap_dev_abs"] = 0.0
                continue

            dev = (price - vwap) / vwap

            r["vwap_dev"] = dev
            r["vwap_dev_abs"] = abs(dev)

        return rows
from typing import List, Dict, Any


class EliteSignalClassifier:
    """
    Assigns signal tiers.

    WATCH
    QUALIFIED
    ELITE
    """

    def classify(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        for r in rows:

            confluence = float(r.get("confluence_score", 0))
            pressure = float(r.get("pressure_score", 0))
            accel = float(r.get("pressure_acceleration", 0))
            vwap_dev = float(r.get("vwap_dev_abs", 0))
            trade_score = float(r.get("trade_score", 0))

            tier = "WATCH"

            if trade_score >= 0.45:
                tier = "QUALIFIED"

            if (
                confluence >= 0.88
                and pressure >= 0.30
                and vwap_dev >= 0.015
                and trade_score >= 0.55
            ):
                tier = "ELITE"

            r["signal_tier"] = tier

        return rows
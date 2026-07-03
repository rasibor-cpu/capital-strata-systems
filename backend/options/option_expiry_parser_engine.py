from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional


class OptionExpiryParserEngine:
    """
    Capital Strata Systems
    Real Expiry Metadata Parsing Engine

    Extracts and normalizes expiry dates from option chain rows,
    then computes real days-to-expiry for pricing realism.
    """

    DATE_FORMATS = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%Y%m%d",
    ]

    EXPIRY_KEYS = [
        "expiry",
        "expiration",
        "expiration_date",
        "expiry_date",
        "exp_date",
    ]

    def _try_parse_date(self, raw_value: str) -> Optional[datetime]:
        raw_value = str(raw_value).strip()

        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(raw_value, fmt)
            except Exception:
                continue

        return None

    def extract_expiry_string(self, selected: Dict) -> Optional[str]:
        for key in self.EXPIRY_KEYS:
            value = selected.get(key)
            if value:
                return str(value)
        return None

    def parse_expiry_date(self, selected: Dict) -> Optional[datetime]:
        raw_expiry = self.extract_expiry_string(selected)
        if raw_expiry is None:
            return None
        return self._try_parse_date(raw_expiry)

    def compute_days_to_expiry(
        self,
        selected: Dict,
        fallback_days: int = 14
    ) -> int:
        parsed = self.parse_expiry_date(selected)
        if parsed is None:
            return fallback_days

        today = datetime.now(timezone.utc)
        delta = (parsed.date() - today.date()).days

        if delta <= 0:
            return 1

        return delta

    def build_expiry_result(
        self,
        selected: Dict,
        fallback_days: int = 14
    ) -> Dict:
        expiry_str = self.extract_expiry_string(selected)
        days = self.compute_days_to_expiry(
            selected,
            fallback_days=fallback_days
        )

        return {
            "expiry_string": expiry_str if expiry_str else "SIM-EXPIRY",
            "days_to_expiry": days
        }

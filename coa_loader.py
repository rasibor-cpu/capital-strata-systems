"""
backend/app/ledger/coa_loader.py

COA Loader (Institution-Mode Aware)
-----------------------------------
Loads a Chart of Accounts (COA) JSON file from:

    backend/app/ledger/Chart Of Accounts/<institution>.json

Primary goals:
- Deterministic account classification via range policy
- Central source of truth for account metadata (name/type/normal balance/statement)
- Reusable by journal_writer, trial_balance, gl_ledger, reports

COA file format:
{
  "meta": {
    "institution_type": "BANK",
    "version": "1.0",
    "range_policy": {
      "100000-199999": "ASSETS",
      "200000-299999": "LIABILITIES",
      "300000-399999": "EQUITY",
      "400000-499999": "INCOME",
      "500000-599999": "EXPENSE"
    }
  },
  "accounts": {
    "100100": {"name":"Cash on Hand","type":"ASSET","normal_balance":"DR","statement":"BALANCE_SHEET"},
    ...
  }
}
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class COAAccount:
    account_no: str
    name: str
    type: str
    normal_balance: str
    statement: str


class COALoader:
    def __init__(self, institution_type: str = "BANK") -> None:
        self.institution_type = institution_type.upper().strip()
        self._coa: Dict[str, Any] = self._load_coa()

    @staticmethod
    def _coa_dir() -> Path:
        # NOTE: folder name includes spaces by design (user requested)
        return Path(__file__).parent / "Chart Of Accounts"

    def _file_map(self) -> Dict[str, str]:
        return {
            "BANK": "bank_coa.json",
            "INVESTMENT_FIRM": "investment_firm_coa.json",
            "FINTECH": "fintech_coa.json",
        }

    def _load_coa(self) -> Dict[str, Any]:
        file_map = self._file_map()
        if self.institution_type not in file_map:
            raise ValueError(f"Unsupported institution type: {self.institution_type}")

        path = self._coa_dir() / file_map[self.institution_type]
        if not path.exists():
            raise FileNotFoundError(
                f"COA file not found for {self.institution_type}: {path}"
            )

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @property
    def meta(self) -> Dict[str, Any]:
        return self._coa.get("meta", {})

    @property
    def accounts(self) -> Dict[str, Any]:
        return self._coa.get("accounts", {})

    def get_account(self, account_no: str) -> Optional[COAAccount]:
        k = str(account_no).strip()
        raw = self.accounts.get(k)
        if not raw:
            return None
        return COAAccount(
            account_no=k,
            name=str(raw.get("name", "")),
            type=str(raw.get("type", "")),
            normal_balance=str(raw.get("normal_balance", "")),
            statement=str(raw.get("statement", "")),
        )

    def validate_account_exists(self, account_no: str) -> None:
        if not self.get_account(account_no):
            raise ValueError(f"Account not found in COA: {account_no}")

    def classify_by_range(self, account_no: str) -> str:
        """
        Returns the range bucket label from meta.range_policy.
        Example: 420100 -> INCOME
        """
        n = int(str(account_no).strip())
        policy = (self.meta.get("range_policy") or {})
        for key, label in policy.items():
            start_s, end_s = key.split("-", 1)
            if int(start_s) <= n <= int(end_s):
                return str(label)
        raise ValueError(f"Account {account_no} outside COA allowed ranges.")

    def validate_account_range(self, account_no: str) -> None:
        _ = self.classify_by_range(account_no)
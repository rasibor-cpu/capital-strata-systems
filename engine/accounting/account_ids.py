"""
Central Account Number Governance – Phase 14
"""

import re
from typing import Dict


ACCOUNT_PATTERN = re.compile(r"^\d{4}-\d{3}-\d{3}$")


def is_valid_format(account_no: str) -> bool:
    return bool(ACCOUNT_PATTERN.match(account_no))


def is_internal_gl(account_no: str) -> bool:
    return account_no.startswith("000-")


def validate_account(account_no: str, is_customer: bool) -> Dict[str, str | bool]:

    if not is_valid_format(account_no):
        return {"ok": False, "reason": "Account must follow ####-###-### format"}

    if is_customer and is_internal_gl(account_no):
        return {"ok": False, "reason": "Customer accounts cannot start with 000"}

    if not is_customer and not is_internal_gl(account_no):
        return {"ok": False, "reason": "Internal GL accounts must start with 000"}

    return {"ok": True, "reason": ""}
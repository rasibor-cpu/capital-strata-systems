import re
import json
import hashlib
from decimal import Decimal
from typing import Dict, List, Set

from registry.coa_loader import load_coa_lookup
from .exceptions import (
    PostingValidationError,
    BranchValidationError,
    GLValidationError,
    PostingTypeError,
    DimensionValidationError,
    BalanceValidationError,
)

from risk.risk_delta_calculator import RiskDeltaCalculator

ENGINE_VERSION = "v2.1"
MAX_LINES = 1000

BIC_REGEX = re.compile(r"^CSSX[A-Z]{2}[A-Z0-9]{2}[A-Z0-9]{3}$")
GL_REGEX = re.compile(r"^[1234568][0-9][0-9][0-9]{6}$")
VALID_PTC = {1, 2, 3, 4, 5, 6, 7}


class PostingGovernanceEngine:

    _PTC_RULES = {
        1: {"allow": {0, 1, 5}, "require_any": {1}},
        2: {"allow": {0, 3, 4, 5}, "require_any": set()},
        3: {"allow": {0, 4, 5}, "require_any": {4}},
        4: {"allow": {0, 2, 5}, "require_any": {2}},
        5: {"allow": {0, 1, 5}, "require_any": {5}},
        6: {"allow": {0, 1, 5}, "require_any": {1}},
        7: {"allow": {0, 1, 3, 5}, "require_any": {1}},
    }

    # ==========================================================
    # PUBLIC ENTRY
    # ==========================================================

    def validate_and_authorize_posting(self, journal: Dict) -> Dict:
        normalized = self._normalize(journal)
        self._validate(normalized)

        governance_hash = self._generate_governance_hash(normalized)
        risk_snapshot = self._compute_risk_snapshot(normalized)

        return {
            "status": "APPROVED",
            "normalized_journal": normalized,
            "governance_hash": governance_hash,
            "risk_snapshot": risk_snapshot,
            "engine_version": ENGINE_VERSION,
        }

    # ==========================================================
    # NORMALIZATION
    # ==========================================================

    def _normalize(self, journal: Dict) -> Dict:
        if not isinstance(journal, dict):
            raise PostingValidationError("Journal must be a dict.")

        journal["branch_bic"] = str(journal.get("branch_bic", "")).upper().strip()

        ptc = journal.get("posting_type_code")
        if ptc not in VALID_PTC:
            raise PostingTypeError("Invalid posting_type_code (must be 1-7).")

        lines = journal.get("lines")
        if not isinstance(lines, list) or len(lines) < 2:
            raise PostingValidationError("Journal must contain at least 2 lines.")
        if len(lines) > MAX_LINES:
            raise PostingValidationError("Journal exceeds maximum allowed lines.")

        for line in lines:
            if not isinstance(line, dict):
                raise PostingValidationError("Each line must be a dict.")

            line["gl_code"] = str(line.get("gl_code", "")).strip()
            line["dc"] = str(line.get("dc", "")).upper().strip()

            if line["dc"] not in ("D", "C"):
                raise BalanceValidationError("Each line must specify D or C.")

            if "amount" not in line:
                raise PostingValidationError("Each line must include amount.")

            amt = Decimal(str(line["amount"]))
            if amt <= 0:
                raise BalanceValidationError("Line amount must be > 0.")

            line["amount"] = amt

            if "counterparty_branch_bic" in line and line["counterparty_branch_bic"] is not None:
                line["counterparty_branch_bic"] = (
                    str(line["counterparty_branch_bic"]).upper().strip()
                )

        return journal

    # ==========================================================
    # VALIDATION
    # ==========================================================

    def _validate(self, journal: Dict) -> None:
        self._validate_branch(journal["branch_bic"])
        self._validate_balance(journal["lines"])

        ptc = journal["posting_type_code"]
        rules = self._PTC_RULES[ptc]

        lanes_present: Set[int] = set()

        for line in journal["lines"]:
            self._validate_gl(line["gl_code"])
            lane = self._extract_lane(line["gl_code"])
            lanes_present.add(lane)

            if lane not in rules["allow"]:
                raise PostingTypeError(f"PTC {ptc} does not allow lane T={lane}.")

            self._validate_dimensions(journal, line, lane)

        if rules["require_any"] and lanes_present.isdisjoint(rules["require_any"]):
            raise PostingTypeError("Required lane not present for this PTC.")

        self._validate_structural_shape(ptc, lanes_present)

    # ==========================================================
    # STRUCTURAL SHAPE CONTROL
    # ==========================================================

    def _validate_structural_shape(self, ptc: int, lanes_present: Set[int]) -> None:

        if ptc in {1, 6, 7}:
            if 1 not in lanes_present or len(lanes_present - {1}) == 0:
                raise PostingTypeError(
                    "Customer/Fees/Interest postings must include lane 1 and at least one non-lane-1 line."
                )

        if ptc == 3:
            if 4 not in lanes_present or len(lanes_present - {4}) == 0:
                raise PostingTypeError(
                    "Interbranch postings must include lane 4 and at least one non-lane-4 line."
                )

        if ptc == 4:
            if 2 not in lanes_present or len(lanes_present - {2}) == 0:
                raise PostingTypeError(
                    "Trading postings must include lane 2 and at least one non-lane-2 line."
                )

        if ptc == 5:
            if 5 not in lanes_present or len(lanes_present - {5}) == 0:
                raise PostingTypeError(
                    "Suspense postings must include lane 5 and at least one non-lane-5 line."
                )

    # ==========================================================
    # CORE VALIDATORS
    # ==========================================================

    def _validate_branch(self, bic: str) -> None:
        if not BIC_REGEX.match(bic):
            raise BranchValidationError(f"Invalid CSSX BIC format: {bic}")

    def _validate_gl(self, gl_code: str) -> None:
        if not GL_REGEX.match(gl_code):
            raise GLValidationError(f"Invalid 9-digit GL format: {gl_code}")

    def _validate_balance(self, lines: List[Dict]) -> None:
        total = Decimal("0")
        for line in lines:
            total += line["amount"] if line["dc"] == "D" else -line["amount"]

        if total != Decimal("0"):
            raise BalanceValidationError(
                "Journal is not balanced (debits must equal credits)."
            )

    def _extract_lane(self, gl_code: str) -> int:
        return int(gl_code[2])

    # ==========================================================
    # DIMENSION VALIDATION
    # ==========================================================

    def _validate_dimensions(self, journal: Dict, line: Dict, lane: int) -> None:

        ptc = journal["posting_type_code"]

        if lane == 1:
            if not journal.get("customer_id") and not line.get("customer_id"):
                raise DimensionValidationError(
                    f"Customer ID required for lane T=1. gl_code={line['gl_code']}"
                )

        if lane == 2:
            if not line.get("instrument_id"):
                raise DimensionValidationError(
                    "Instrument ID required for trading account."
                )

        if lane == 4:
            cp = line.get("counterparty_branch_bic")
            if not cp or not BIC_REGEX.match(cp):
                raise DimensionValidationError(
                    "Valid counterparty_branch_bic required for interbranch."
                )

        if ptc == 5 and not journal.get("exception_reason_code"):
            raise DimensionValidationError("PTC 5 requires exception_reason_code.")

        if ptc == 6 and not journal.get("fee_code") and not line.get("fee_code"):
            raise DimensionValidationError("PTC 6 requires fee_code.")

        if ptc == 7 and not journal.get("interest_scheme_id") and not line.get("interest_scheme_id"):
            raise DimensionValidationError("PTC 7 requires interest_scheme_id.")

    # ==========================================================
    # GOVERNANCE HASH
    # ==========================================================

    def _generate_governance_hash(self, journal: Dict) -> str:
        canonical = json.dumps(journal, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    # ==========================================================
    # RISK SNAPSHOT
    # ==========================================================

    def _compute_risk_snapshot(self, journal: Dict) -> Dict:

        coa_lookup = load_coa_lookup()
        calculator = RiskDeltaCalculator()
        risk_delta = calculator.compute(journal, coa_lookup=coa_lookup)

        return {
            "rwa_delta": risk_delta,
            "capital_warning": False,
        }
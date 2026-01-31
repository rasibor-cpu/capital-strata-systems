"""
eod_validations.py — REA Capital Trading Engine
-----------------------------------------------
End-of-Day (EOD) Validations & Escalations Engine

Scope:
- Double-entry integrity checks
- Balance Sheet integrity checks
- Ageing escalation logic
- Suspense / Sundry / Unsettled controls
- Supervisor / Admin escalation payload

READ-ONLY. No posting. No mutation.
"""

from typing import Dict, Any, List


# =====================================================
# Escalation Policy (LOCKED)
# =====================================================
AGE_ESCALATION_MATRIX = {
    "T+1": "INFO",
    "T+3": "WARNING",
    "T+7": "HIGH",
    "T+30": "CRITICAL",
    "T+180": "CRITICAL",
    "T+>180": "ADMIN_AUDIT",
}


# =====================================================
# EOD Validation Engine
# =====================================================
class EODValidationEngine:
    def __init__(self):
        self.breaches: List[Dict[str, Any]] = []

    # -------------------------------------------------
    # Ledger Integrity Checks
    # -------------------------------------------------
    def validate_double_entry(self, ledger_summary):
        total_dr = total_cr = 0.0

        for _, ccy_map in ledger_summary.items():
            for _, r in ccy_map.items():
                total_dr += r["debits"]
                total_cr += r["credits"]

        if round(total_dr, 2) != round(total_cr, 2):
            self._add_breach(
                breach_type="DOUBLE_ENTRY_MISMATCH",
                severity="CRITICAL",
                details={
                    "total_debits": total_dr,
                    "total_credits": total_cr,
                },
            )

    def validate_balance_sheet(self, assets, liabilities, equity):
        if round(assets, 2) != round(liabilities + equity, 2):
            self._add_breach(
                breach_type="BALANCE_SHEET_MISMATCH",
                severity="CRITICAL",
                details={
                    "assets": assets,
                    "liabilities": liabilities,
                    "equity": equity,
                },
            )

    # -------------------------------------------------
    # Ageing Escalations
    # -------------------------------------------------
    def validate_ageing(self, ageing_report):
        """
        ageing_report structure:
        {
          "LEDGER|CCY|DOMAIN": {
              "T+1": amt,
              "T+3": amt,
              ...
          }
        }
        """
        for key, buckets in ageing_report.items():
            ledger, ccy, domain = key.split("|")

            for bucket, amount in buckets.items():
                if amount <= 0:
                    continue

                severity = AGE_ESCALATION_MATRIX.get(bucket)
                if not severity:
                    continue

                self._add_breach(
                    breach_type="AGEING_THRESHOLD",
                    severity=severity,
                    details={
                        "ledger": ledger,
                        "currency": ccy,
                        "domain": domain,
                        "bucket": bucket,
                        "amount": amount,
                    },
                )

    # -------------------------------------------------
    # Breach Handling
    # -------------------------------------------------
    def _add_breach(self, breach_type: str, severity: str, details: Dict[str, Any]):
        self.breaches.append(
            {
                "breach_type": breach_type,
                "severity": severity,
                "details": details,
            }
        )

    def print_summary(self):
        print("\n=== EOD VALIDATION SUMMARY ===")

        if not self.breaches:
            print("NO BREACHES — SYSTEM BALANCED.")
            return

        for b in self.breaches:
            print(
                f"- {b['breach_type']} | {b['severity']} | {b['details']}"
            )

    def supervisor_payload(self):
        payload = [
            b for b in self.breaches
            if b["severity"] in ("HIGH", "CRITICAL", "ADMIN_AUDIT")
        ]

        print("\n=== SUPERVISOR / ADMIN PAYLOAD ===")

        if not payload:
            print("NIL — No escalations required.")
            return

        for p in payload:
            print(
                f"- {p['severity']} | {p['breach_type']} | {p['details']}"
            )

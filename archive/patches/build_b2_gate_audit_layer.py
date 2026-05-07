from pathlib import Path
from datetime import datetime
import re

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "backend" / "governance" / "css_unified_trade_gate.py"

if not TARGET.exists():
    raise FileNotFoundError(f"Gate file not found: {TARGET}")

text = TARGET.read_text(encoding="utf-8")

backup = TARGET.with_name(
    f"css_unified_trade_gate_PRE_B2_AUDIT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
)
backup.write_text(text, encoding="utf-8")

# Add json + Path imports
text = text.replace("import time\n", "import time\nimport json\nfrom pathlib import Path\n", 1)

# Add audit constants after SESSION_TIMEOUT_SECONDS
anchor = "SESSION_TIMEOUT_SECONDS = 3600\n"
audit_constants = '''
AUDIT_DIR = Path("audit_logs")
AUDIT_FILE = AUDIT_DIR / "css_unified_trade_gate_audit.jsonl"
'''
if audit_constants.strip() not in text:
    text = text.replace(anchor, anchor + audit_constants + "\n", 1)

# Add audit method before _validate_candidate
helper_anchor = "    def _validate_candidate(self, candidate: Dict[str, Any]) -> Tuple[bool, str]:"
audit_method = '''    def _write_audit_decision(
        self,
        *,
        approved: bool,
        reason: str,
        engine_mode: str,
        timestamp: float,
        candidate: Dict[str, Any] = None,
        details: Dict[str, Any] = None,
    ) -> None:
        """
        B2: Decision audit trail.
        Fail-safe: audit failure must never approve or block trades by itself.
        """
        try:
            AUDIT_DIR.mkdir(parents=True, exist_ok=True)

            payload = {
                "timestamp": timestamp,
                "approved": bool(approved),
                "reason": str(reason),
                "engine_mode": str(engine_mode),
                "symbol": candidate.get("symbol") if candidate else None,
                "asset_class": candidate.get("asset_class") if candidate else None,
                "candidate": candidate or {},
                "details": details or {},
            }

            with AUDIT_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, default=str) + "\\n")

        except Exception:
            pass

'''
if audit_method.strip() not in text:
    text = text.replace(helper_anchor, audit_method + helper_anchor, 1)

# Replace approval reason block
text = text.replace(
'''        return GateDecision(
            approved=True,
            reason="approved",
            engine_mode=engine_mode,
            timestamp=now,
            details={
                "asset_class": asset_class,
                "expected_value": expected_value,
                "cost": cost,
                "probability": probability,
                "threshold": threshold,
            },
        )
''',
'''        approval_reason = (
            f"approved: probability={probability:.4f} >= threshold={threshold:.4f}; "
            f"cost={cost:.4f} < expected_value={expected_value:.4f}; "
            f"asset_class={asset_class}; engine_mode={engine_mode}"
        )

        approval_details = {
            "asset_class": asset_class,
            "expected_value": expected_value,
            "cost": cost,
            "probability": probability,
            "threshold": threshold,
        }

        self._write_audit_decision(
            approved=True,
            reason=approval_reason,
            engine_mode=engine_mode,
            timestamp=now,
            candidate=candidate,
            details=approval_details,
        )

        return GateDecision(
            approved=True,
            reason=approval_reason,
            engine_mode=engine_mode,
            timestamp=now,
            details=approval_details,
        )
''',
1)

# Replace _reject return block
text = re.sub(
r'''    def _reject\(
        self,
        reason: str,
        engine_mode: str,
        timestamp: float,
        candidate: Dict\[str, Any\] = None,
    \) -> GateDecision:
        return GateDecision\(
            approved=False,
            reason=reason,
            engine_mode=engine_mode,
            timestamp=timestamp,
            details=\{
                "asset_class": candidate\.get\("asset_class"\) if candidate else None,
                "symbol": candidate\.get\("symbol"\) if candidate else None,
            \},
        \)
''',
'''    def _reject(
        self,
        reason: str,
        engine_mode: str,
        timestamp: float,
        candidate: Dict[str, Any] = None,
    ) -> GateDecision:
        rejection_reason = f"rejected: {reason}"

        rejection_details = {
            "asset_class": candidate.get("asset_class") if candidate else None,
            "symbol": candidate.get("symbol") if candidate else None,
        }

        self._write_audit_decision(
            approved=False,
            reason=rejection_reason,
            engine_mode=engine_mode,
            timestamp=timestamp,
            candidate=candidate,
            details=rejection_details,
        )

        return GateDecision(
            approved=False,
            reason=rejection_reason,
            engine_mode=engine_mode,
            timestamp=timestamp,
            details=rejection_details,
        )
''',
text,
count=1,
)

TARGET.write_text(text, encoding="utf-8")

print("[PCNRASS B2 BUILDER COMPLETE]")
print(f"Target updated: {TARGET}")
print(f"Backup created: {backup}")
print("Next: python -m py_compile backend\\governance\\css_unified_trade_gate.py")
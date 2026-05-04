# audit_logger.py
import json
import datetime
import os

class CSSAuditLogger:
    def __init__(self):
        self.log_file = "css_institutional_audit.json"
        # Ensure the log file exists as a valid JSON list if it doesn't
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w') as f:
                json.dump([], f)

    def log_event(self, message, level="INFO"):
        """Logs a standard system event with timestamp."""
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "level": level,
            "message": message
        }
        self._write_to_log(entry)
        print(f"[{level}] {message}")

    def log_rejection(self, signal, reason):
        """Specifically logs trade rejections for post-session analysis."""
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "level": "TRADE_REJECTED",
            "asset": signal.get('asset', 'UNKNOWN'),
            "reason": reason,
            "context": "Capital Protection Layer"
        }
        self._write_to_log(entry)
        print(f"[REJECTED] {signal.get('asset')} - Reason: {reason}")

    def _write_to_log(self, entry):
        """Appends the entry to the JSON audit file."""
        try:
            with open(self.log_file, 'r+') as f:
                data = json.load(f)
                data.append(entry)
                f.seek(0)
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Audit Logging Error: {e}")
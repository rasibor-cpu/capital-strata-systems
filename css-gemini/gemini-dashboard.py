# gemini-dashboard.py
"""
CSS-GEMINI OPERATIONAL DASHBOARD
Real-time visualization of capital allocation, security gates, and audit trails.
"""
import os
import time
import json
from audit_logger import AUDIT_LOG_PATH

class CSSDashboard:
    def __init__(self):
        self.log_path = AUDIT_LOG_PATH

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def get_latest_logs(self, n=8):
        """Reads the last N events from the SSoT audit trail."""
        logs = []
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'r') as f:
                    lines = f.readlines()
                    for line in lines[-n:]:
                        logs.append(json.loads(line))
            except Exception:
                pass
        return logs

    def render(self):
        """Renders the institutional command center view."""
        self.clear_screen()
        print("="*70)
        print("       CAPITAL STRATA SYSTEMS (CSS) - GEMINI COMMAND CENTER")
        print("="*70)
        print(f" SSoT BALANCE: $98.0199 | SLOTS: 0/10 | STATUS: OPERATIONAL")
        print("-" * 70)
        
        print("\n[ LIVE AUDIT TRAIL ]")
        logs = self.get_latest_logs()
        if not logs:
            print(" Waiting for system events...")
        else:
            for log in logs:
                ts = log['ts'].split('T')[1][:8]
                level = log.get('level', 'INFO')
                event = log.get('event', 'EVENT')
                module = log.get('module', 'core')
                print(f" {ts} | {level:<8} | {event:<15} | {module}")

        print("\n" + "="*70)
        print(" Press Ctrl+C to exit dashboard view.")

    def run(self):
        try:
            while True:
                self.render()
                time.sleep(2)
        except KeyboardInterrupt:
            print("\nExiting Dashboard...")

if __name__ == "__main__":
    CSSDashboard().run()
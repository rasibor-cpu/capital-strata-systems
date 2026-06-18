"""
CSS-GEMINI INSTITUTIONAL COMMAND CENTER
Merged: High-Density UI + SSoT Audit Trail + Session Context
"""
import sys
sys.exit("NON-CANONICAL RETIREMENT CANDIDATE: Use scripts/css_live_dashboard.py instead.")

import os
import time
import json
import socket
from datetime import datetime
from colorama import Fore, Back, Style, init
from audit_logger import AUDIT_LOG_PATH

# Initialize colorama for Windows CLI compatibility (Ref: image_b83519.png)
init(autoreset=True)

class CSSDashboard:
    def __init__(self, user_id="00000", role="SUPER_USER"):
        self.log_path = AUDIT_LOG_PATH
        self.user_id = user_id
        self.role = role
        self.start_time = time.monotonic()
        self.cycle_count = 1
        self.computer_name = socket.gethostname().upper()

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def get_latest_logs(self, n=6):
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

    def _draw_header(self, title):
        print(f"{Fore.CYAN}{Style.BRIGHT}--- {title} ---")

    def render(self):
        """Renders the combined Command Center view (Ref: image_b8315b.png)"""
        self.clear_screen()
        
        # PRIMARY HEADER
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        print(f"{Fore.WHITE}{Style.BRIGHT}=== Cycle {self.cycle_count} | {timestamp} ===")

        # 1. SESSION CONTEXT (Ref: image_b83117.png)
        self._draw_header("SESSION CONTEXT")
        print(f"USER ID: {self.user_id}")
        print(f"ROLE: {Fore.YELLOW}{self.role}")
        print(f"COMPUTER NAME: {self.computer_name}")
        print(f"SESSION AGE SEC: {int(time.monotonic() - self.start_time)}")
        print(f"CAN LIVE EXECUTE: {Fore.GREEN if self.role == 'SUPER_USER' else Fore.RED}YES")

        # 2. BROKER STATUS & PNL AUTHORITY (Ref: image_b830c0.png)
        self._draw_header("PNL RECONCILIATION (SSoT)")
        # These values should eventually be passed from your live Accounting Engine
        print(f"MTM REALIZED PNL: {Fore.GREEN}+0.0000")
        print(f"MTM UNREALIZED PNL: {Fore.GREEN}+0.0000")
        print(f"LIVE EQUITY: {Fore.CYAN}$98.0199")
        print(f"{Style.DIM}[PNL AUTHORITY] MTM/accounting PnL is authoritative.")

        # 3. LIVE AUDIT TRAIL (Your Original Logic)
        self._draw_header("LIVE AUDIT TRAIL")
        logs = self.get_latest_logs()
        if not logs:
            print(f"{Fore.YELLOW} Waiting for system events...")
        else:
            for log in logs:
                ts = log['ts'].split('T')[1][:8]
                level = log.get('level', 'INFO')
                event = log.get('event', 'EVENT')
                # Color code levels for high-glance scannability
                lvl_color = Fore.RED if level == "ERROR" else (Fore.YELLOW if level == "WARN" else Fore.WHITE)
                print(f" {ts} | {lvl_color}{level:<8}{Style.RESET_ALL} | {event:<20} | {log.get('module', 'core')}")

        # 4. EXECUTION CONTROL
        print("\n" + "="*70)
        print(f"{Fore.GREEN}[CSS OPERATIONAL]{Style.RESET_ALL} Press Ctrl+C to exit dashboard.")

    def run(self):
        try:
            while True:
                self.render()
                self.cycle_count += 1
                time.sleep(2)
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Exiting Dashboard...")

if __name__ == "__main__":
    # Ensure colorama is installed: pip install colorama
    CSSDashboard().run()
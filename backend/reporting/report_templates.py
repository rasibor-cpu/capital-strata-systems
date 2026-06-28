"""
Report Templates for CSS Reporting Framework

Defines layout templates for DAILY, WEEKLY, MONTHLY, RUNTIME, PORTFOLIO, and RISK reports.
"""

from typing import Dict, Any

class ReportTemplates:
    """
    Renders report contents from predefined string templates.
    
    Responsibility: Standardize format layout of report contents.
    Dependencies: None.
    Thread-safety: Read-only, safe.
    Integration: Leveraged by ReportGenerator.
    """
    def __init__(self):
        self._templates = {
            "DAILY": "Daily Operational Report\nTimestamp: {timestamp}\nTrades: {trades_count}\nVolume: {total_volume}\nPnL: {pnl}\n",
            "WEEKLY": "Weekly Trading Summary\nPeriod: {period}\nSharpe Ratio: {sharpe}\nDrawdown: {max_drawdown}\nPnL: {pnl}\n",
            "MONTHLY": "Monthly Performance Analysis\nMonth: {month}\nStarting Equity: {starting_equity}\nEnding Equity: {ending_equity}\nReturn: {total_return}%\n",
            "RUNTIME": "System Runtime Diagnostics\nUptime: {uptime_seconds}s\nMemory Usage: {memory_mb} MB\nCPU Load: {cpu_percent}%\nAlerts Logged: {alerts_count}\n",
            "PORTFOLIO": "Portfolio Exposure Report\nTotal Value: {total_value}\nAsset Allocations: {allocations}\nFree Margin: {free_margin}\nLeverage: {leverage}\n",
            "RISK": "Risk Limit Integrity Audit\nActive Limit Checks: {checks_run}\nBreaches: {breaches_count}\nMax Exposure: {max_exposure}\n"
        }

    def render(self, report_type: str, context: Dict[str, Any]) -> str:
        """Render a report layout using local context variables."""
        template = self._templates.get(report_type.upper())
        if not template:
            raise KeyError(f"Template for report type '{report_type}' not found.")
        return template.format(**context)

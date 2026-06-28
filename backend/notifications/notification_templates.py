"""
Notification Templates for CSS Notification Framework

Enables simple templating string formats for common alerts.
"""

from typing import Dict, Any

class NotificationTemplates:
    """
    Renders messages from predefined text templates.
    
    Responsibility: Standardize the message body strings based on contexts.
    Dependencies: None.
    Thread-safety: Read-only, safe.
    Integration: Leveraged by NotificationService when formatting raw alerts before dispatch.
    """
    def __init__(self):
        self._templates = {
            "daily_digest": "Daily Digest Report: {report_summary}",
            "order_fill": "Order Filled: {symbol} - {quantity} shares at {price}",
            "risk_alert": "Risk Warning: {limit_name} limit exceeded by {excess_percent}%"
        }

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render templates utilizing local context variables."""
        template = self._templates.get(template_name)
        if not template:
            raise KeyError(f"Template '{template_name}' not found.")
        return template.format(**context)

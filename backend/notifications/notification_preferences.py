"""
User Preferences for CSS Notification Framework

Tracks enabled channels, quiet hours, and minimum severity thresholds.
"""

import datetime
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class UserPreferences:
    """
    Dataclass mapping user delivery preferences.
    
    Responsibility: Store and apply user-specific filtering rules.
    Dependencies: None.
    Thread-safety: Read-only check helper, safe.
    Integration: Leveraged by NotificationService to filter incoming Event objects.
    """
    user_id: str
    enabled_channels: List[str] = field(default_factory=lambda: ["email", "desktop"])
    severity_threshold: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    quiet_hours_start: Optional[str] = None  # HH:MM format e.g., "22:00"
    quiet_hours_end: Optional[str] = None    # HH:MM format e.g., "08:00"
    report_subscriptions: List[str] = field(default_factory=list)

    def is_channel_enabled(self, channel: str) -> bool:
        """Check if a specific channel is enabled by the user."""
        return channel in self.enabled_channels

    def should_deliver(self, severity: str, timestamp: float) -> bool:
        """Check if severity levels and quiet hour limits permit message dispatch."""
        severities = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        try:
            user_idx = severities.index(self.severity_threshold)
            event_idx = severities.index(severity)
            if event_idx < user_idx:
                return False
        except ValueError:
            pass

        if self.quiet_hours_start and self.quiet_hours_end:
            try:
                dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
                current_time = dt.time()

                start_h, start_m = map(int, self.quiet_hours_start.split(":"))
                end_h, end_m = map(int, self.quiet_hours_end.split(":"))

                start_time = datetime.time(start_h, start_m)
                end_time = datetime.time(end_h, end_m)

                if start_time < end_time:
                    if start_time <= current_time <= end_time:
                        return False
                else:
                    if current_time >= start_time or current_time <= end_time:
                        return False
            except Exception:
                pass
        return True

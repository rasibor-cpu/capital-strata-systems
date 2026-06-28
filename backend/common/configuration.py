"""
CSS Configuration Base and Subsystem Configurations
"""

from dataclasses import dataclass, field
from typing import List, Optional
from backend.common.exceptions import ConfigurationException

class BaseConfig:
    """
    Interface requiring validation of configuration dataclasses.
    """
    def validate(self) -> None:
        """Validate config parameters, raising ConfigurationException on failure."""
        raise NotImplementedError

@dataclass
class NotificationConfig(BaseConfig):
    """
    Configuration parameters for the Notification Framework.
    """
    max_retries: int = 3
    default_channels: List[str] = field(default_factory=lambda: ["email", "desktop"])
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None

    def validate(self) -> None:
        if self.max_retries < 0:
            raise ConfigurationException("max_retries cannot be negative")
        if not isinstance(self.default_channels, list):
            raise ConfigurationException("default_channels must be a list")
        for start_end in (self.quiet_hours_start, self.quiet_hours_end):
            if start_end is not None:
                if ":" not in start_end or len(start_end) != 5:
                    raise ConfigurationException(f"Invalid quiet hour format: {start_end}. Expected HH:MM")

@dataclass
class ReportingConfig(BaseConfig):
    """
    Configuration parameters for the Reporting Framework.
    """
    default_source: str = "reporting_service"
    archive_dir: str = "artifacts/reports/"
    history_file: str = "artifacts/reports/report_history.json"

    def validate(self) -> None:
        if not self.default_source:
            raise ConfigurationException("default_source cannot be empty")
        if not self.archive_dir:
            raise ConfigurationException("archive_dir cannot be empty")
        if not self.history_file:
            raise ConfigurationException("history_file cannot be empty")

@dataclass
class OperationsConfig(BaseConfig):
    """
    Configuration parameters for the Operations Control Centre.
    """
    default_source: str = "operations_service"
    state_file: str = "artifacts/operations/operational_state.json"
    timeline_file: str = "artifacts/operations/operational_timeline.json"

    def validate(self) -> None:
        if not self.default_source:
            raise ConfigurationException("default_source cannot be empty")
        if not self.state_file:
            raise ConfigurationException("state_file cannot be empty")
        if not self.timeline_file:
            raise ConfigurationException("timeline_file cannot be empty")

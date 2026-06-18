"""Read-only information module surfaces for CSS runtime visibility."""

from engine.information.stock_alerts import (
    STOCK_ALERT_TYPES,
    STOCK_ALERT_SEVERITIES,
    StockAlertRule,
    generate_stock_alerts,
)

__all__ = [
    "STOCK_ALERT_TYPES",
    "STOCK_ALERT_SEVERITIES",
    "StockAlertRule",
    "generate_stock_alerts",
]

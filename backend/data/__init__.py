"""Data-provider compatibility boundary.

Live market connectivity is intentionally not implemented in this remote repair.
"""

from .price_feed import PriceFeed, get_price_feed

__all__ = ["PriceFeed", "get_price_feed"]

"""Canonical Capital Strata Systems branding authority."""

from .models import (
    BrandAsset,
    BrandPalette,
    ExecutiveDocumentStandard,
    WatermarkStandard,
)
from .service import (
    APPLICATION_NAME,
    BRAND_ASSET_VERSION,
    BRAND_SCHEMA_VERSION,
    CONFIDENTIALITY_BANNER,
    CSSBrandService,
    DEFAULT_CLASSIFICATION,
    ORGANIZATION_NAME,
    SHORT_APPLICATION_NAME,
    get_brand_service,
)

__all__ = [
    "APPLICATION_NAME",
    "BRAND_ASSET_VERSION",
    "BRAND_SCHEMA_VERSION",
    "BrandAsset",
    "BrandPalette",
    "CONFIDENTIALITY_BANNER",
    "CSSBrandService",
    "DEFAULT_CLASSIFICATION",
    "ExecutiveDocumentStandard",
    "ORGANIZATION_NAME",
    "SHORT_APPLICATION_NAME",
    "WatermarkStandard",
    "get_brand_service",
]

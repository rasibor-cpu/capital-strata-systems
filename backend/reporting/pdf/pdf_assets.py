"""Branding-Service-only asset resolution for PDF rendering."""

from __future__ import annotations

from pathlib import Path

from backend.common.branding import CSSBrandService, get_brand_service


class PDFAssetProvider:
    def __init__(self, brand: CSSBrandService | None = None) -> None:
        self.brand = brand or get_brand_service()

    def logo(self) -> Path:
        return self._required("logo")

    def watermark(self) -> Path:
        return self._required(self.brand.watermark.asset_key)

    def _required(self, key: str) -> Path:
        path = self.brand.asset_path(key)
        if not path.is_file():
            raise FileNotFoundError(f"branding_asset_missing:{key}")
        return path


__all__ = ["PDFAssetProvider"]

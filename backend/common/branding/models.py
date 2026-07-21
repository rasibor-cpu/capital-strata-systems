"""Immutable contracts for the canonical CSS branding authority."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class BrandPalette:
    theme: str
    background: str
    surface: str
    gold: str
    platinum: str
    ink: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class BrandAsset:
    key: str
    filename: str
    media_type: str
    url: str
    width: int | None = None
    height: int | None = None
    purpose: str = "any"
    rendering: str = "colour"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WatermarkStandard:
    asset_key: str
    opacity: float
    width_percent: int
    position: str
    printable: bool
    pdf_compatible: bool
    pointer_events: str
    z_index: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutiveDocumentStandard:
    organization: str
    classification: str
    confidentiality_banner: str
    runtime_label: str
    header_fields: tuple[str, ...]
    footer_fields: tuple[str, ...]
    watermark: WatermarkStandard

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["header_fields"] = list(self.header_fields)
        value["footer_fields"] = list(self.footer_fields)
        return value


__all__ = [
    "BrandAsset",
    "BrandPalette",
    "ExecutiveDocumentStandard",
    "WatermarkStandard",
]

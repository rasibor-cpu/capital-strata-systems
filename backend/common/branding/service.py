"""Single canonical provider for CSS identity, assets, and document branding."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from .models import (
    BrandAsset,
    BrandPalette,
    ExecutiveDocumentStandard,
    WatermarkStandard,
)

BRAND_SCHEMA_VERSION = "css.branding.v1"
BRAND_ASSET_VERSION = "180a1"
APPLICATION_NAME = "Capital Strata Systems Mission Control"
SHORT_APPLICATION_NAME = "CSS Mission Control"
ORGANIZATION_NAME = "Capital Strata Systems"
DEFAULT_CLASSIFICATION = "CSS CONFIDENTIAL — ADVISORY ONLY"
CONFIDENTIALITY_BANNER = (
    "CSS CONFIDENTIAL — ADVISORY ONLY — NOT AN EXECUTION ORDER"
)


class CSSBrandService:
    """Immutable branding authority shared by backend and presentation surfaces."""

    def __init__(self, *, repository_root: Path | str | None = None) -> None:
        root = (
            Path(repository_root)
            if repository_root is not None
            else Path(__file__).resolve().parents[3]
        )
        self.repository_root = root
        self.branding_root = root / "assets" / "branding"
        self.palette = BrandPalette(
            theme="#101820",
            background="#101820",
            surface="#17232d",
            gold="#d5a844",
            platinum="#f0d58a",
            ink="#10202a",
        )
        self.watermark = WatermarkStandard(
            asset_key="watermark_logo",
            opacity=0.055,
            width_percent=42,
            position="center",
            printable=True,
            pdf_compatible=True,
            pointer_events="none",
            z_index=0,
        )
        self.document_standard = ExecutiveDocumentStandard(
            organization=ORGANIZATION_NAME,
            classification=DEFAULT_CLASSIFICATION,
            confidentiality_banner=CONFIDENTIALITY_BANNER,
            runtime_label="CSS Runtime",
            header_fields=(
                "organization",
                "report_title",
                "generation_timestamp",
                "classification",
            ),
            footer_fields=(
                "page_number",
                "page_count",
                "document_id",
                "runtime_version",
                "confidentiality_banner",
            ),
            watermark=self.watermark,
        )
        self._assets = self._build_assets()

    @property
    def schema_version(self) -> str:
        return BRAND_SCHEMA_VERSION

    @property
    def asset_version(self) -> str:
        return BRAND_ASSET_VERSION

    @property
    def application_name(self) -> str:
        return APPLICATION_NAME

    @property
    def short_application_name(self) -> str:
        return SHORT_APPLICATION_NAME

    @property
    def organization_name(self) -> str:
        return ORGANIZATION_NAME

    def asset(self, key: str) -> BrandAsset:
        try:
            return self._assets[str(key)]
        except KeyError as exc:
            raise KeyError(f"unknown_brand_asset:{key}") from exc

    def asset_path(self, key: str) -> Path:
        return self.branding_root / self.asset(key).filename

    def asset_url(self, key: str) -> str:
        return self.asset(key).url

    def assets(self) -> dict[str, dict[str, Any]]:
        return {key: asset.as_dict() for key, asset in self._assets.items()}

    def manifest(
        self,
        *,
        start_url: str = "/dashboard",
        app_id: str = "/css-mission-control",
        name: str | None = None,
        short_name: str | None = None,
        shell_cache: str | None = None,
    ) -> dict[str, Any]:
        icon_keys = (
            "icon_192",
            "icon_512",
            "maskable_192",
            "maskable_512",
        )
        return {
            "name": name or self.application_name,
            "short_name": short_name or self.short_application_name,
            "description": (
                "Read-only Capital Strata Systems Mission Control mobile application."
            ),
            "id": app_id,
            "start_url": start_url,
            "scope": "/",
            "display": "standalone",
            "display_override": [
                "window-controls-overlay",
                "standalone",
                "minimal-ui",
            ],
            "orientation": "any",
            "background_color": self.palette.background,
            "theme_color": self.palette.theme,
            "css_pwa_version": self.asset_version,
            "css_shell_cache": shell_cache or f"css-mobile-pwa-{self.asset_version}",
            "icons": [
                {
                    "src": self.asset(key).url,
                    "sizes": f"{self.asset(key).width}x{self.asset(key).height}",
                    "type": self.asset(key).media_type,
                    "purpose": self.asset(key).purpose,
                }
                for key in icon_keys
            ],
        }

    def html_head(
        self,
        *,
        manifest_href: str,
        include_manifest: bool = True,
        include_viewport: bool = True,
        application_name: str | None = None,
    ) -> str:
        app_name = escape(application_name or self.short_application_name, quote=True)
        parts = []
        if include_viewport:
            parts.append(
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            )
        parts.extend(
            [
                f'<meta name="theme-color" content="{self.palette.theme}">',
                f'<meta name="application-name" content="{app_name}">',
                '<meta name="mobile-web-app-capable" content="yes">',
                '<meta name="apple-mobile-web-app-capable" content="yes">',
                f'<meta name="apple-mobile-web-app-title" content="{app_name}">',
            ]
        )
        if include_manifest:
            parts.append(
                f'<link rel="manifest" href="{escape(manifest_href, quote=True)}">'
            )
        parts.extend(
            [
                f'<link rel="icon" href="{self.asset_url("favicon")}" sizes="any">',
                (
                    '<link rel="icon" type="image/png" sizes="16x16" '
                    f'href="{self.asset_url("favicon_16")}">'
                ),
                (
                    '<link rel="icon" type="image/png" sizes="32x32" '
                    f'href="{self.asset_url("favicon_32")}">'
                ),
                (
                    '<link rel="apple-touch-icon" sizes="180x180" '
                    f'href="{self.asset_url("apple_touch")}">'
                ),
            ]
        )
        return "\n  ".join(parts)

    def watermark_markup(self, *, class_name: str = "css-brand-watermark") -> str:
        return (
            f'<img class="{escape(class_name, quote=True)}" '
            f'src="{escape(self.asset_url("watermark_logo"), quote=True)}" '
            'alt="" aria-hidden="true">'
        )

    def watermark_css(
        self,
        *,
        page_selector: str,
        class_name: str = "css-brand-watermark",
    ) -> str:
        return (
            f"{page_selector}{{position:relative;isolation:isolate;}}"
            f"{page_selector}>:not(.{class_name}){{position:relative;z-index:1;}}"
            f".{class_name}{{position:absolute;left:50%;top:50%;"
            f"transform:translate(-50%,-50%);width:{self.watermark.width_percent}%;"
            f"height:auto;opacity:{self.watermark.opacity};"
            f"pointer-events:{self.watermark.pointer_events};z-index:{self.watermark.z_index};"
            "filter:grayscale(1);object-fit:contain;page-break-inside:avoid;}}"
            f"@media print{{.{class_name}{{display:block!important;"
            "-webkit-print-color-adjust:exact;print-color-adjust:exact;}}}"
        )

    def document_context(
        self,
        *,
        report_title: str,
        generated_at: str,
        document_id: str,
        runtime_version: str,
        classification: str | None = None,
    ) -> dict[str, Any]:
        return {
            "organization": self.organization_name,
            "report_title": str(report_title),
            "generation_timestamp": str(generated_at),
            "classification": classification or self.document_standard.classification,
            "document_id": str(document_id),
            "runtime_version": str(runtime_version),
            "confidentiality_banner": self.document_standard.confidentiality_banner,
            "watermark": self.watermark.as_dict(),
            "watermark_asset_url": self.asset_url("watermark_logo"),
            "branding_schema_version": self.schema_version,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "asset_version": self.asset_version,
            "application_name": self.application_name,
            "short_application_name": self.short_application_name,
            "organization_name": self.organization_name,
            "palette": self.palette.as_dict(),
            "assets": self.assets(),
            "document_standard": self.document_standard.as_dict(),
        }

    def _build_assets(self) -> dict[str, BrandAsset]:
        version = self.asset_version
        icon_512 = f"/pwa/css-icon-512.png?v={version}"
        return {
            "logo": BrandAsset(
                "logo",
                "css-icon-512.png",
                "image/png",
                icon_512,
                512,
                512,
            ),
            "monochrome_logo": BrandAsset(
                "monochrome_logo",
                "css-icon-512.png",
                "image/png",
                icon_512,
                512,
                512,
                rendering="monochrome_css_filter",
            ),
            "watermark_logo": BrandAsset(
                "watermark_logo",
                "css-icon-512.png",
                "image/png",
                icon_512,
                512,
                512,
                rendering="watermark",
            ),
            "favicon": BrandAsset(
                "favicon",
                "favicon.ico",
                "image/x-icon",
                "/favicon.ico",
            ),
            "favicon_16": BrandAsset(
                "favicon_16",
                "favicon-16x16.png",
                "image/png",
                f"/favicon-16x16.png?v={version}",
                16,
                16,
            ),
            "favicon_32": BrandAsset(
                "favicon_32",
                "favicon-32x32.png",
                "image/png",
                f"/favicon-32x32.png?v={version}",
                32,
                32,
            ),
            "apple_touch": BrandAsset(
                "apple_touch",
                "apple-touch-icon.png",
                "image/png",
                f"/apple-touch-icon.png?v={version}",
                180,
                180,
            ),
            "icon_192": BrandAsset(
                "icon_192",
                "css-icon-192.png",
                "image/png",
                f"/pwa/css-icon-192.png?v={version}",
                192,
                192,
            ),
            "icon_512": BrandAsset(
                "icon_512",
                "css-icon-512.png",
                "image/png",
                icon_512,
                512,
                512,
            ),
            "maskable_192": BrandAsset(
                "maskable_192",
                "css-icon-maskable-192.png",
                "image/png",
                f"/pwa/css-icon-maskable-192.png?v={version}",
                192,
                192,
                purpose="maskable",
            ),
            "maskable_512": BrandAsset(
                "maskable_512",
                "css-icon-maskable-512.png",
                "image/png",
                f"/pwa/css-icon-maskable-512.png?v={version}",
                512,
                512,
                purpose="maskable",
            ),
        }


_BRAND_SERVICE = CSSBrandService()


def get_brand_service() -> CSSBrandService:
    return _BRAND_SERVICE


__all__ = [
    "APPLICATION_NAME",
    "BRAND_ASSET_VERSION",
    "BRAND_SCHEMA_VERSION",
    "CONFIDENTIALITY_BANNER",
    "CSSBrandService",
    "DEFAULT_CLASSIFICATION",
    "ORGANIZATION_NAME",
    "SHORT_APPLICATION_NAME",
    "get_brand_service",
]

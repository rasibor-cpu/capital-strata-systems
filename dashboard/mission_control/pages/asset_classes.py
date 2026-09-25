from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, page_header, section, warning_banner


_ASSET_CLASSES = (
    ("equities-etfs", "Equities / ETFs", "EQUITIES / ETFs"),
    ("crypto", "Crypto", "CRYPTO"),
    ("fx", "FX", "FX"),
    ("futures", "Futures", "FUTURES"),
    ("options", "Options", "OPTIONS"),
    ("other-derivatives", "Other Derivatives", "OTHER DERIVATIVES"),
)


def _asset_status_rows(state: dict, canonical_name: str) -> dict[str, object]:
    portfolio = section(state, "portfolio")
    market = section(state, "market_intelligence")
    learning = section(state, "learning")
    safety = section(state, "safety")

    allocation = portfolio.get("asset_allocation")
    allocation_value: object = "EVIDENCE_MISSING"
    if isinstance(allocation, dict):
        aliases = {
            "EQUITIES / ETFs": ("EQUITIES", "EQUITY", "ETF", "ETFS"),
            "CRYPTO": ("CRYPTO", "CRYPTOCURRENCY"),
            "FX": ("FX", "FOREX", "FOREIGN_EXCHANGE"),
            "FUTURES": ("FUTURES", "FUTURE"),
            "OPTIONS": ("OPTIONS", "OPTION"),
            "OTHER DERIVATIVES": ("DERIVATIVES", "OTHER_DERIVATIVES"),
        }
        for key in aliases.get(canonical_name, (canonical_name,)):
            if key in allocation:
                allocation_value = allocation.get(key)
                break

    rankings = learning.get("asset_class_rankings")
    ranking_value: object = "EVIDENCE_MISSING"
    if isinstance(rankings, list):
        for row in rankings:
            if not isinstance(row, dict):
                continue
            asset = str(row.get("asset_class") or row.get("name") or "").strip().upper()
            if asset and asset in canonical_name:
                ranking_value = row.get("rank") or row.get("score") or row.get("status") or "RECORDED"
                break

    return {
        "allocation_evidence": allocation_value,
        "market_regime": market.get("market_regime", "EVIDENCE_MISSING"),
        "learning_rank": ranking_value,
        "execution": "BLOCKED" if safety.get("live_trading_blocked", True) else "UNAVAILABLE",
        "mode": "READ_ONLY",
    }


def _asset_panel(anchor: str, label: str, canonical_name: str) -> str:
    options_link = (
        '<a href="/mission-control/options-income">Open Options Income workbench</a>'
        if canonical_name == "OPTIONS"
        else ""
    )
    return (
        f'<section class="mc-panel mc-section-anchor" id="{anchor}" '
        f'aria-label="{label} asset-class destination">'
        f"<h2>{label}</h2>"
        '<p class="mc-muted">Dedicated read-only asset-class destination. '
        'Portfolio, market, risk, and learning evidence is shown only when canonical data is available.</p>'
        f'{detail_table(f"{label} Snapshot", _asset_status_rows(_CURRENT_STATE, canonical_name))}'
        '<p class="mc-muted">'
        '<a href="/mission-control/trade-operations">Trade Operations</a> · '
        '<a href="/mission-control/portfolio">Portfolio</a> · '
        '<a href="/mission-control/market-intelligence">Market Intelligence</a> · '
        '<a href="/mission-control/risk-command">Risk Command</a>'
        + (f" · {options_link}" if options_link else "")
        + "</p></section>"
    )


_CURRENT_STATE: dict = {}


def render(state: dict) -> str:
    global _CURRENT_STATE
    _CURRENT_STATE = state
    try:
        jump_links = "".join(
            f'<a href="#mc-asset-{anchor}">{label}</a>'
            for anchor, label, _ in _ASSET_CLASSES
        )
        panels = "".join(
            _asset_panel(f"mc-asset-{anchor}", label, canonical)
            for anchor, label, canonical in _ASSET_CLASSES
        )
        return (
            page_header(
                "Asset Classes",
                "Multi-asset read-only operator hub for equities/ETFs, crypto, FX, futures, options, and other derivatives.",
            )
            + warning_banner(
                "Asset-class pages are advisory/read-only. No destination can place, modify, or cancel orders.",
                status="warn",
            )
            + '<nav class="mc-page-jump" aria-label="Asset Classes">'
            + jump_links
            + "</nav>"
            + '<div class="mc-operator-stack">'
            + panels
            + "</div>"
        )
    finally:
        _CURRENT_STATE = {}


__all__ = ["render"]

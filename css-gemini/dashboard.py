"""
Live Trading Dashboard
Real-time web UI served at http://localhost:8050
Auto-refreshes every 5 seconds. Shows:
  - Engine status & kill switch controls
  - Capital & drawdown metrics
  - Open positions table
  - Equity curve chart
  - Recent trades log
  - Per-asset-class breakdown
"""
import sys
sys.exit("NON-CANONICAL RETIREMENT CANDIDATE: Use scripts/css_live_dashboard.py instead.")

import threading
import logging
from datetime import datetime

import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import plotly.express as px

import config
from orchestrator import TradeOrchestrator

logger = logging.getLogger(__name__)

# ── Shared orchestrator instance (set by main.py before starting dashboard) ──
_orchestrator: TradeOrchestrator = None


def set_orchestrator(orch: TradeOrchestrator):
    global _orchestrator
    _orchestrator = orch


# ══════════════════════════════════════════════════════════════════
# DASH APP
# ══════════════════════════════════════════════════════════════════

app = dash.Dash(
    __name__,
    title="Trading Engine",
    update_title=None,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)

# ── Colour palette ──────────────────────────────────────────────
C = {
    "bg":       "#0a0e1a",
    "surface":  "#111827",
    "border":   "#1f2937",
    "accent":   "#00d4aa",
    "red":      "#ff4d6d",
    "yellow":   "#fbbf24",
    "text":     "#e2e8f0",
    "subtext":  "#6b7280",
    "green":    "#10b981",
}

CARD_STYLE = {
    "backgroundColor": C["surface"],
    "border": f"1px solid {C['border']}",
    "borderRadius": "12px",
    "padding": "20px",
    "marginBottom": "16px",
}

# ── Layout ──────────────────────────────────────────────────────

app.layout = html.Div(style={"backgroundColor": C["bg"], "minHeight": "100vh",
                              "fontFamily": "'IBM Plex Mono', monospace", "color": C["text"]}, children=[

    # Google Font
    html.Link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;600&display=swap"),

    # Header
    html.Div(style={"padding": "24px 32px", "borderBottom": f"1px solid {C['border']}",
                    "display": "flex", "justifyContent": "space-between", "alignItems": "center"}, children=[
        html.Div([
            html.H1("⚡ TRADING ENGINE", style={"margin": 0, "fontSize": "20px",
                                                "letterSpacing": "3px", "color": C["accent"]}),
            html.Span(id="engine-status-badge", style={"fontSize": "11px"}),
        ]),
        html.Div([
            html.Span(id="clock", style={"color": C["subtext"], "fontSize": "12px", "marginRight": "20px"}),
            html.Button("⏹ HALT ENGINE", id="halt-btn", n_clicks=0,
                        style={"backgroundColor": C["red"], "color": "white", "border": "none",
                               "borderRadius": "6px", "padding": "8px 16px", "cursor": "pointer",
                               "fontSize": "12px", "letterSpacing": "1px", "marginRight": "8px"}),
            html.Button("▶ RESUME", id="resume-btn", n_clicks=0,
                        style={"backgroundColor": C["green"], "color": "white", "border": "none",
                               "borderRadius": "6px", "padding": "8px 16px", "cursor": "pointer",
                               "fontSize": "12px", "letterSpacing": "1px"}),
        ]),
    ]),

    # Alert banner
    html.Div(id="alert-banner", style={"display": "none"}),

    # Main content
    html.Div(style={"padding": "24px 32px"}, children=[

        # ── Row 1: Metric cards ──────────────────────────
        html.Div(style={"display": "grid", "gridTemplateColumns": "repeat(6, 1fr)", "gap": "12px",
                        "marginBottom": "20px"}, children=[
            _metric_card("capital-card",    "CAPITAL",       "$0.00"),
            _metric_card("pnl-card",        "DAILY PnL",     "$0.00"),
            _metric_card("drawdown-card",   "DRAWDOWN",      "0.00%"),
            _metric_card("winrate-card",    "WIN RATE",      "0%"),
            _metric_card("trades-card",     "TOTAL TRADES",  "0"),
            _metric_card("positions-card",  "OPEN POSITIONS","0"),
        ]),

        # ── Row 2: Equity curve + Asset breakdown ────────
        html.Div(style={"display": "grid", "gridTemplateColumns": "2fr 1fr", "gap": "16px",
                        "marginBottom": "20px"}, children=[
            html.Div(style=CARD_STYLE, children=[
                html.H3("Equity Curve", style={"margin": "0 0 12px", "fontSize": "12px",
                                               "letterSpacing": "2px", "color": C["subtext"]}),
                dcc.Graph(id="equity-chart", style={"height": "260px"},
                          config={"displayModeBar": False}),
            ]),
            html.Div(style=CARD_STYLE, children=[
                html.H3("Asset Class PnL", style={"margin": "0 0 12px", "fontSize": "12px",
                                                   "letterSpacing": "2px", "color": C["subtext"]}),
                dcc.Graph(id="asset-chart", style={"height": "260px"},
                          config={"displayModeBar": False}),
            ]),
        ]),

        # ── Row 3: Open positions ────────────────────────
        html.Div(style=CARD_STYLE, children=[
            html.H3("Open Positions", style={"margin": "0 0 12px", "fontSize": "12px",
                                             "letterSpacing": "2px", "color": C["subtext"]}),
            dash_table.DataTable(
                id="positions-table",
                columns=[
                    {"name": "Symbol",        "id": "symbol"},
                    {"name": "Side",          "id": "side"},
                    {"name": "Entry",         "id": "entry"},
                    {"name": "Stop Loss",     "id": "sl"},
                    {"name": "Take Profit",   "id": "tp"},
                    {"name": "Unrealised PnL","id": "unrealised_pnl"},
                    {"name": "Asset Class",   "id": "asset_class"},
                ],
                data=[],
                style_table={"overflowX": "auto"},
                style_header={"backgroundColor": C["bg"], "color": C["subtext"],
                              "border": "none", "fontSize": "11px", "letterSpacing": "1px"},
                style_cell={"backgroundColor": C["surface"], "color": C["text"],
                            "border": f"1px solid {C['border']}", "fontSize": "12px",
                            "padding": "8px 12px", "textAlign": "left"},
                style_data_conditional=[
                    {"if": {"filter_query": "{side} = long"},  "color": C["green"]},
                    {"if": {"filter_query": "{side} = short"}, "color": C["red"]},
                    {"if": {"filter_query": "{unrealised_pnl} < 0"}, "color": C["red"]},
                ],
            ),
        ]),

        # ── Row 4: Recent trades ─────────────────────────
        html.Div(style=CARD_STYLE, children=[
            html.H3("Recent Trades", style={"margin": "0 0 12px", "fontSize": "12px",
                                            "letterSpacing": "2px", "color": C["subtext"]}),
            dash_table.DataTable(
                id="trades-table",
                columns=[
                    {"name": "#",          "id": "trade_id"},
                    {"name": "Symbol",     "id": "symbol"},
                    {"name": "Side",       "id": "side"},
                    {"name": "Entry",      "id": "entry_price"},
                    {"name": "Exit",       "id": "exit_price"},
                    {"name": "PnL ($)",    "id": "pnl"},
                    {"name": "PnL (%)",    "id": "pnl_pct"},
                    {"name": "Score",      "id": "signal_score"},
                    {"name": "Exit",       "id": "exit_reason"},
                    {"name": "Duration",   "id": "duration_secs"},
                ],
                data=[],
                page_size=15,
                style_table={"overflowX": "auto"},
                style_header={"backgroundColor": C["bg"], "color": C["subtext"],
                              "border": "none", "fontSize": "11px", "letterSpacing": "1px"},
                style_cell={"backgroundColor": C["surface"], "color": C["text"],
                            "border": f"1px solid {C['border']}", "fontSize": "12px",
                            "padding": "8px 12px", "textAlign": "left"},
                style_data_conditional=[
                    {"if": {"filter_query": "{pnl} > 0"}, "color": C["green"]},
                    {"if": {"filter_query": "{pnl} < 0"}, "color": C["red"]},
                    {"if": {"filter_query": "{exit_reason} = TP"}, "backgroundColor": "#0f2a1e"},
                    {"if": {"filter_query": "{exit_reason} = SL"}, "backgroundColor": "#2a0f0f"},
                ],
            ),
        ]),
    ]),

    # Interval component
    dcc.Interval(id="interval", interval=5_000, n_intervals=0),
    dcc.Store(id="halt-state", data=False),
])


# ── Helper: metric card ─────────────────────────────────────────

def _metric_card(card_id: str, label: str, default_value: str):
    return html.Div(id=card_id, style={**CARD_STYLE, "marginBottom": 0, "textAlign": "center"}, children=[
        html.Div(label, style={"fontSize": "10px", "letterSpacing": "2px", "color": C["subtext"], "marginBottom": "8px"}),
        html.Div(default_value, style={"fontSize": "22px", "fontWeight": "600", "color": C["accent"]}),
    ])


# ══════════════════════════════════════════════════════════════════
# CALLBACKS
# ══════════════════════════════════════════════════════════════════

@app.callback(
    Output("halt-state", "data"),
    Input("halt-btn",   "n_clicks"),
    Input("resume-btn", "n_clicks"),
    State("halt-state", "data"),
    prevent_initial_call=True,
)
def handle_halt_resume(halt_clicks, resume_clicks, current_halted):
    ctx = dash.callback_context
    if not ctx.triggered or not _orchestrator:
        return current_halted
    btn = ctx.triggered[0]["prop_id"].split(".")[0]
    if btn == "halt-btn":
        _orchestrator.risk._halt("Manual halt via dashboard")
        return True
    elif btn == "resume-btn":
        _orchestrator.risk.resume()
        return False
    return current_halted


@app.callback(
    Output("clock",              "children"),
    Output("engine-status-badge","children"),
    Output("engine-status-badge","style"),
    Output("alert-banner",       "children"),
    Output("alert-banner",       "style"),
    Output("capital-card",       "children"),
    Output("pnl-card",           "children"),
    Output("drawdown-card",      "children"),
    Output("winrate-card",       "children"),
    Output("trades-card",        "children"),
    Output("positions-card",     "children"),
    Output("equity-chart",       "figure"),
    Output("asset-chart",        "figure"),
    Output("positions-table",    "data"),
    Output("trades-table",       "data"),
    Input("interval",            "n_intervals"),
)
def update_dashboard(n):
    now = datetime.utcnow().strftime("%Y-%m-%d  %H:%M:%S UTC")

    if _orchestrator is None:
        return _empty_dashboard(now)

    status = _orchestrator.status()
    risk   = status["risk"]
    pnl    = status["pnl"]

    halted = risk["halted"]
    status_text  = f"● HALTED — {risk['halt_reason']}" if halted else "● LIVE"
    status_color = C["red"] if halted else C["green"]
    status_style = {"fontSize": "12px", "color": status_color, "marginLeft": "12px"}

    alert_style = {"display": "none"}
    alert_content = ""
    if halted:
        alert_style = {"backgroundColor": C["red"], "color": "white", "padding": "10px 32px",
                       "fontSize": "13px", "fontWeight": "600", "display": "block"}
        alert_content = f"⚠ ENGINE HALTED: {risk['halt_reason']}"

    # Metric cards
    dd_color = C["red"] if risk["drawdown_pct"] > 3 else C["yellow"] if risk["drawdown_pct"] > 1 else C["accent"]
    capital_card   = _card_content("CAPITAL",        f"${risk['capital']:,.2f}", C["accent"])
    daily_pnl      = risk.get("daily_pnl", 0)
    pnl_color      = C["green"] if daily_pnl >= 0 else C["red"]
    pnl_card       = _card_content("DAILY PnL",      f"${daily_pnl:+,.2f}", pnl_color)
    dd_card        = _card_content("DRAWDOWN",        f"{risk['drawdown_pct']:.2f}%", dd_color)
    wr_card        = _card_content("WIN RATE",        f"{pnl.get('win_rate', 0):.1f}%", C["accent"])
    trades_card    = _card_content("TOTAL TRADES",    str(pnl.get("total_trades", 0)), C["accent"])
    positions_card = _card_content("OPEN POSITIONS",  str(risk["open_positions"]), C["accent"])

    # Equity curve
    curve = _orchestrator.pnl.equity_curve(config.STARTING_CAPITAL)
    eq_fig = go.Figure()
    if len(curve) > 1:
        times  = [p["time"] for p in curve]
        equities = [p["equity"] for p in curve]
        eq_fig.add_trace(go.Scatter(
            x=times, y=equities, mode="lines",
            line={"color": C["accent"], "width": 2},
            fill="tozeroy", fillcolor="rgba(0,212,170,0.08)",
        ))
    eq_fig.update_layout(**_chart_layout())

    # Asset breakdown bar chart
    breakdown = _orchestrator.pnl.asset_breakdown()
    asset_fig = go.Figure()
    if breakdown:
        labels = list(breakdown.keys())
        values = [breakdown[a]["pnl"] for a in labels]
        colors = [C["green"] if v >= 0 else C["red"] for v in values]
        asset_fig.add_trace(go.Bar(x=labels, y=values, marker_color=colors))
    asset_fig.update_layout(**_chart_layout())

    # Positions table
    pos_data = [
        {
            "symbol":         sym,
            "side":           p["side"],
            "entry":          f"{p['entry']:.6g}",
            "sl":             f"{p['sl']:.6g}",
            "tp":             f"{p['tp']:.6g}",
            "unrealised_pnl": f"${p['unrealised_pnl']:+.2f}",
            "asset_class":    p["asset_class"],
        }
        for sym, p in status["positions"].items()
    ]

    # Recent trades table
    trades_data = []
    for t in _orchestrator.pnl.recent_trades(20):
        trades_data.append({
            "trade_id":     t["trade_id"],
            "symbol":       t["symbol"],
            "side":         t["side"],
            "entry_price":  f"{t['entry_price']:.6g}",
            "exit_price":   f"{t['exit_price']:.6g}",
            "pnl":          f"${t['pnl']:+.2f}",
            "pnl_pct":      f"{t['pnl_pct']:+.2f}%",
            "signal_score": f"{t['signal_score']:.2f}",
            "exit_reason":  t["exit_reason"],
            "duration_secs":f"{t['duration_secs']/60:.1f}m",
        })

    return (
        now, status_text, status_style, alert_content, alert_style,
        capital_card, pnl_card, dd_card, wr_card, trades_card, positions_card,
        eq_fig, asset_fig, pos_data, trades_data,
    )


def _card_content(label: str, value: str, color: str):
    return [
        html.Div(label, style={"fontSize": "10px", "letterSpacing": "2px",
                               "color": C["subtext"], "marginBottom": "8px"}),
        html.Div(value, style={"fontSize": "22px", "fontWeight": "600", "color": color}),
    ]


def _chart_layout():
    return {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor":  "rgba(0,0,0,0)",
        "margin":        {"l": 40, "r": 10, "t": 10, "b": 30},
        "font":          {"color": C["subtext"], "family": "IBM Plex Mono", "size": 10},
        "xaxis":         {"gridcolor": C["border"], "showgrid": True, "zeroline": False},
        "yaxis":         {"gridcolor": C["border"], "showgrid": True, "zeroline": False},
    }


def _empty_dashboard(now):
    empty_fig = go.Figure()
    empty_fig.update_layout(**_chart_layout())
    card = lambda l, v: _card_content(l, v, C["accent"])
    return (
        now, "● CONNECTING...", {"fontSize": "12px", "color": C["yellow"], "marginLeft": "12px"},
        "", {"display": "none"},
        card("CAPITAL", "$—"), card("DAILY PnL", "$—"), card("DRAWDOWN", "—"),
        card("WIN RATE", "—"), card("TOTAL TRADES", "—"), card("OPEN POSITIONS", "—"),
        empty_fig, empty_fig, [], [],
    )


# ══════════════════════════════════════════════════════════════════
# ENTRY POINT (standalone)
# ══════════════════════════════════════════════════════════════════

def run_dashboard():
    app.run(host="0.0.0.0", port=config.DASHBOARD_PORT, debug=False)


if __name__ == "__main__":
    run_dashboard()

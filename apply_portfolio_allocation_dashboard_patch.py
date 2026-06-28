from pathlib import Path

launcher_path = Path("launcher/css_mobile_launcher.py")
template_path = Path("launcher/templates/mobile_dashboard.html")

launcher = launcher_path.read_text(encoding="utf-8")

feed_function = """
def get_portfolio_allocation_feed() -> Dict[str, Any]:
    audit_dir = os.path.join(LauncherConfig.ARTIFACTS_DIR, "portfolio_audit")
    try:
        if not os.path.isdir(audit_dir):
            return {
                "status": "UNAVAILABLE",
                "message": "No portfolio allocation audit directory",
                "allocations": [],
                "diversification_metrics": {},
            }

        files = [
            os.path.join(audit_dir, name)
            for name in os.listdir(audit_dir)
            if name.startswith("portfolio_allocation_") and name.endswith(".json")
        ]
        if not files:
            return {
                "status": "UNAVAILABLE",
                "message": "No portfolio allocation audit records",
                "allocations": [],
                "diversification_metrics": {},
            }

        latest = max(files, key=os.path.getmtime)
        with open(latest, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {
            "status": "OK",
            "source_file": os.path.basename(latest),
            "generated_at": data.get("generated_at", ""),
            "market_regime": data.get("market_regime", "UNKNOWN"),
            "risk_profile": data.get("risk_profile", "UNKNOWN"),
            "total_capital": data.get("total_capital", 0.0),
            "validation_status": data.get("validation_status", "PENDING"),
            "allocations": data.get("allocations", []),
            "diversification_metrics": data.get("diversification_metrics", {}),
            "total_allocated_percent": data.get("total_allocated_percent", 0.0),
            "total_allocated_amount": data.get("total_allocated_amount", 0.0),
        }
    except Exception as exc:
        return {
            "status": "ERROR",
            "message": str(exc),
            "allocations": [],
            "diversification_metrics": {},
        }


"""

if "def get_portfolio_allocation_feed()" not in launcher:
    marker = "def build_mobile_dashboard_context() -> Dict[str, Any]:"
    launcher = launcher.replace(marker, feed_function + marker)

if '"portfolio_allocation": get_portfolio_allocation_feed(),' not in launcher:
    launcher = launcher.replace(
        '        "strategy_evolution": strategy_evolution,\n',
        '        "strategy_evolution": strategy_evolution,\n        "portfolio_allocation": get_portfolio_allocation_feed(),\n',
    )

launcher_path.write_text(launcher, encoding="utf-8")

template = template_path.read_text(encoding="utf-8")

card = """
        <div class="card" id="portfolio-allocation-card">
            <div class="card-header">
                Portfolio Allocation Plan
                {% if portfolio_allocation.status == 'OK' %}
                <span class="badge badge-info">AUDITED</span>
                {% elif portfolio_allocation.status == 'ERROR' %}
                <span class="badge badge-danger">ERROR</span>
                {% else %}
                <span class="badge badge-warning">UNAVAILABLE</span>
                {% endif %}
            </div>
            {% if portfolio_allocation.status == 'OK' %}
            <div class="status-row"><span>Risk Profile</span><strong id="pa-risk-profile">{{ portfolio_allocation.risk_profile }}</strong></div>
            <div class="status-row"><span>Market Regime</span><strong id="pa-market-regime">{{ portfolio_allocation.market_regime }}</strong></div>
            <div class="status-row"><span>Total Capital</span><strong id="pa-total-capital">{{ portfolio_allocation.total_capital }}</strong></div>
            <div class="status-row"><span>Allocated</span><strong id="pa-total-allocated">{{ portfolio_allocation.total_allocated_percent }}% / {{ portfolio_allocation.total_allocated_amount }}</strong></div>
            <div class="status-row"><span>Validation</span><strong id="pa-validation-status">{{ portfolio_allocation.validation_status }}</strong></div>
            <div class="status-row"><span>Generated</span><strong id="pa-generated-at">{{ portfolio_allocation.generated_at }}</strong></div>
            <div style="margin-top:8px; font-size:12px; color:var(--text-secondary);">Allocations</div>
            <pre id="pa-allocations" style="white-space:pre-wrap; font-size:11px; color:var(--text-secondary);">{{ portfolio_allocation.allocations | tojson(indent=2) }}</pre>
            <div style="margin-top:8px; font-size:12px; color:var(--text-secondary);">Diversification Metrics</div>
            <pre id="pa-diversification" style="white-space:pre-wrap; font-size:11px; color:var(--text-secondary);">{{ portfolio_allocation.diversification_metrics | tojson(indent=2) }}</pre>
            {% else %}
            <div class="empty-state">Portfolio allocation audit unavailable.</div>
            {% endif %}
        </div>

"""

if 'id="portfolio-allocation-card"' not in template:
    marker = '        <div class="card" id="trade-decision-console">'
    template = template.replace(marker, card + marker)

template_path.write_text(template, encoding="utf-8")

print("Patched launcher dashboard with portfolio allocation visibility.")

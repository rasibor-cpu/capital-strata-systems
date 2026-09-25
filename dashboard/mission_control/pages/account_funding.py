from __future__ import annotations

from html import escape

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, section, warning_banner


def _v(row: object, key: str, default: str = "UNAVAILABLE") -> str:
    return str(row.get(key, default)) if isinstance(row, dict) else default


def _balance_rows(summary: dict) -> list[dict]:
    rows = []
    for key in (
        "cash",
        "settled_cash",
        "available_to_trade",
        "effective_available_balance",
        "pending_debits",
        "pending_credits",
        "held_reserved",
        "buying_power",
        "margin_available",
        "total_account_value",
    ):
        row = summary.get(key) if isinstance(summary.get(key), dict) else {}
        rows.append(
            {
                "balance": key.replace("_", " ").title(),
                "amount": row.get("value"),
                "currency": row.get("currency"),
                "verification": row.get("verification_state"),
                "freshness": row.get("freshness"),
                "as_of": row.get("as_of"),
            }
        )
    return rows


def _funding_table(rows: object) -> str:
    if not isinstance(rows, list) or not rows:
        return "<p class='mc-muted'>No funding requests recorded.</p>"
    body = "".join(
        "<tr>"
        f"<td>{escape(str(row.get('funding_id') or '—'))}</td>"
        f"<td>{escape(str(row.get('amount') or '—'))}</td>"
        f"<td>{escape(str(row.get('currency') or '—'))}</td>"
        f"<td>{escape(str(row.get('funding_method') or '—'))}</td>"
        f"<td>{escape(str(row.get('status') or '—'))}</td>"
        f"<td>{escape(str(row.get('verification_source') or '—'))}</td>"
        "</tr>"
        for row in rows if isinstance(row, dict)
    )
    return (
        '<div class="mc-table-wrap"><table><thead><tr>'
        '<th>ID</th><th>Amount</th><th>Currency</th><th>Method</th><th>Status</th><th>Verification</th>'
        f"</tr></thead><tbody>{body}</tbody></table></div>"
    )


def render(state: dict) -> str:
    balances = section(state, "broker_balance_summary")
    summary = balances.get("account_summary") if isinstance(balances.get("account_summary"), dict) else {}
    controls = section(state, "account_controls")
    margin = controls.get("margin_control") if isinstance(controls.get("margin_control"), dict) else {}
    funding = controls.get("funding_requests") if isinstance(controls.get("funding_requests"), list) else []
    auth = state.get("authorization_context") if isinstance(state.get("authorization_context"), dict) else {}
    uid = str(auth.get("user_id") or controls.get("user_id") or "")
    available = summary.get("effective_available_balance") if isinstance(summary.get("effective_available_balance"), dict) else summary.get("available_to_trade", {})
    pending_debits = summary.get("pending_debits") if isinstance(summary.get("pending_debits"), dict) else {}
    pending_credits = summary.get("pending_credits") if isinstance(summary.get("pending_credits"), dict) else {}

    return (
        page_header(
            "Balances & Funding",
            "Verified multi-currency balances, pending postings, funding requests, margin availability, and set-off controls.",
        )
        + warning_banner(
            "Funding requests do not increase tradable balance until independently verified. Overdrafts are blocked unless a verified margin facility and executed set-off instruction cover the shortfall.",
            status="warn",
        )
        + metric_grid(
            (
                ("Available", f"{available.get('value', 'UNAVAILABLE')} {available.get('currency', '')}", available.get("verification_state")),
                ("Pending Debits", f"{pending_debits.get('value', 'UNAVAILABLE')} {pending_debits.get('currency', '')}", pending_debits.get("verification_state")),
                ("Pending Credits", f"{pending_credits.get('value', 'UNAVAILABLE')} {pending_credits.get('currency', '')}", pending_credits.get("verification_state")),
                ("Margin", margin.get("status", "DISABLED"), margin.get("status", "DISABLED")),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority",
            aria_label="Balance and funding priority",
        )
        + '<nav class="mc-page-jump" aria-label="Balance and funding sections">'
          '<a href="#mc-balance-detail">Balances</a><a href="#mc-fund-account">Fund Account</a>'
          '<a href="#mc-funding-history">Funding History</a><a href="#mc-margin-control">Margin / Set-Off</a></nav>'
        + '<div class="mc-section-anchor" id="mc-balance-detail">'
        + detail_table("Verified Balance Detail", _balance_rows(summary))
        + '</div>'
        + """
<section class="mc-panel mc-section-anchor" id="mc-fund-account">
<h2>Fund Account</h2>
<p class="mc-muted">Submit a funding notice. CSS will keep it pending until matched to external bank/broker/payment evidence.</p>
<form id="mc-funding-form" class="mc-filter-form">
<label>Amount<input name="amount" inputmode="decimal" required></label>
<label>Currency<input name="currency" value="USD" maxlength="8" required></label>
<label>Funding method<select name="funding_method" required>
<option value="">Select</option><option value="BANK_TRANSFER">Bank transfer</option>
<option value="BROKER_TRANSFER">Broker transfer</option><option value="CARD">Card / payment processor</option>
<option value="INTERNAL_TRANSFER">Verified internal transfer</option></select></label>
<label>External reference<input name="external_reference" placeholder="Bank/broker/payment reference"></label>
<button type="submit">Submit Funding for Verification</button>
</form>
<p id="mc-funding-result" class="mc-muted" aria-live="polite"></p>
</section>
<script>
document.getElementById('mc-funding-form')?.addEventListener('submit', async (ev) => {
 ev.preventDefault(); const out=document.getElementById('mc-funding-result');
 const body=new URLSearchParams(new FormData(ev.currentTarget));
 try { const r=await fetch('/account/funding/request',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest'},body});
 const data=await r.json(); if(!r.ok) throw new Error(data.detail||'Funding request failed');
 out.textContent='Funding submitted. Status: PENDING VERIFICATION. It is not yet available to trade.';
 } catch(err){out.textContent=String(err.message||err);}
});
</script>
"""
        + '<section class="mc-panel mc-section-anchor" id="mc-funding-history"><h2>Funding History</h2>'
        + _funding_table(funding)
        + '</section>'
        + '<section class="mc-panel mc-section-anchor" id="mc-margin-control"><h2>Margin / Set-Off Control</h2>'
        + detail_table("Margin Facility", {
            "status": margin.get("status", "DISABLED"),
            "currency": margin.get("currency", "UNAVAILABLE"),
            "margin_limit": margin.get("margin_limit", "0"),
            "linked_credit_account_alias": margin.get("linked_credit_account_alias", "UNAVAILABLE"),
            "setoff_form_version": margin.get("setoff_form_version", "UNAVAILABLE"),
            "setoff_executed": margin.get("setoff_executed", False),
            "setoff_executed_at": margin.get("setoff_executed_at", "UNAVAILABLE"),
            "verification_source": margin.get("verification_source", "UNAVAILABLE"),
            "verification_reference": margin.get("verification_reference", "UNAVAILABLE"),
        })
        + (
            '<form id="mc-setoff-form" class="mc-filter-form">'
            f'<input type="hidden" name="setoff_form_version" value="{escape(str(margin.get("setoff_form_version") or ""), quote=True)}">'
            '<label><input type="checkbox" required> I execute the displayed set-off instruction and authorize eligible credit balances in the linked account to cover permitted transaction costs/losses subject to the agreement.</label>'
            '<button type="submit">Execute Set-Off Instruction</button></form>'
            '<p id="mc-setoff-result" class="mc-muted" aria-live="polite"></p>'
            '<script>document.getElementById("mc-setoff-form")?.addEventListener("submit",async(ev)=>{ev.preventDefault();'
            'const out=document.getElementById("mc-setoff-result");const body=new URLSearchParams(new FormData(ev.currentTarget));'
            'try{const r=await fetch("/account/margin/setoff/accept",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/x-www-form-urlencoded","X-Requested-With":"XMLHttpRequest"},body});'
            'const data=await r.json();if(!r.ok)throw new Error(data.detail||"Set-off failed");out.textContent="Set-off instruction executed. Margin remains unavailable until independently verified.";}'
            'catch(err){out.textContent=String(err.message||err);}});</script>'
            if uid and margin.get("setoff_form_version") and not margin.get("setoff_executed")
            else '<p class="mc-muted">No user set-off action is currently required.</p>'
        )
        + '</section>'
    )


__all__ = ["render"]

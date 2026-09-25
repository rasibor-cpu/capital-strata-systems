from __future__ import annotations

from html import escape

from dashboard.mission_control.pages._components import metric_grid, page_header, warning_banner


def _opt(value: str, label: str, selected: str) -> str:
    return f'<option value="{escape(value, quote=True)}"{" selected" if value == selected else ""}>{escape(label)}</option>'


def _profile_table(profiles: dict[str, dict]) -> str:
    if not profiles:
        return '<section class="mc-panel"><h2>Configured Accounts</h2><p class="mc-muted">No user commercial configuration is recorded.</p></section>'
    rows = []
    for user_id, profile in sorted(profiles.items()):
        access = profile.get("system_access_charge") if isinstance(profile.get("system_access_charge"), dict) else {}
        commission = profile.get("trade_commission") if isinstance(profile.get("trade_commission"), dict) else {}
        independent = profile.get("independent_trade_platform_fee") if isinstance(profile.get("independent_trade_platform_fee"), dict) else {}
        rows.append(
            "<tr>"
            f"<td>{escape(str(user_id))}</td>"
            f"<td>{escape(str(profile.get('role') or '—'))}</td>"
            f"<td>{escape(str(profile.get('user_mode') or '—'))}</td>"
            f"<td>{escape(str(access.get('type') or '—'))} {escape(str(access.get('amount') or '0'))} {escape(str(access.get('currency') or ''))}</td>"
            f"<td>{escape(str(commission.get('basis') or '—'))} {escape(str(commission.get('rate') or '0'))}</td>"
            f"<td>{escape(str(independent.get('basis') or '—'))} {escape(str(independent.get('rate') or '0'))}</td>"
            f"<td>{escape(str(profile.get('acceptance_status') or 'PENDING'))}</td>"
            "</tr>"
        )
    return (
        '<section class="mc-panel"><h2>Configured Accounts</h2>'
        '<div class="mc-table-wrap"><table><thead><tr>'
        '<th>User</th><th>Role</th><th>User Mode</th><th>System Access Charge</th>'
        '<th>CSS Trade Commission</th><th>Independent Trade Fee</th><th>Terms</th>'
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>"
    )


def render(state: dict) -> str:
    config = state.get("user_account_configuration") if isinstance(state.get("user_account_configuration"), dict) else {}
    users = config.get("users") if isinstance(config.get("users"), list) else []
    profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
    auth = state.get("authorization_context") if isinstance(state.get("authorization_context"), dict) else {}
    admin = str(auth.get("role") or "").upper() in {"SUPER_USER", "ADMIN"}

    user_options = "".join(
        _opt(str(row.get("user_id") or ""), f"{row.get('user_id')} — {row.get('display_name')} ({row.get('role')})", "")
        for row in users if isinstance(row, dict)
    )
    roles = config.get("roles") if isinstance(config.get("roles"), list) else []
    role_options = "".join(_opt(str(role), str(role), "") for role in roles)

    admin_form = ""
    if admin:
        admin_form = f"""
<section class="mc-panel">
  <h2>Configure User Account</h2>
  <p class="mc-muted">Administrative configuration is persisted separately from execution authority. Saving these terms does not enable trading.</p>
  <form id="mc-user-account-config" class="mc-filter-form">
    <label>User<select name="user_id" required><option value="">Select user</option>{user_options}</select></label>
    <label>Role / privilege<select name="role" required><option value="">Select role</option>{role_options}</select></label>
    <label>User mode<select name="user_mode" required>
      <option value="SELF_DIRECTED">Self-directed — user trades and accepts trading risk</option>
      <option value="CSS_ADVISORY_CONFIRM">CSS advisory — user accepts/rejects suggestions; accepted trades may execute only when the platform is separately authorized</option>
    </select></label>
    <label>System access charge type<select name="system_access_charge_type">
      <option value="NONE">None</option><option value="FIXED_MONTHLY">Fixed monthly</option><option value="FIXED_ANNUAL">Fixed annual</option>
    </select></label>
    <label>System access charge amount<input name="system_access_charge_amount" inputmode="decimal" value="0"></label>
    <label>Access charge currency<input name="system_access_currency" value="USD" maxlength="8"></label>
    <label>CSS trade commission basis<select name="trade_commission_basis">
      <option value="NONE">None</option><option value="PERCENT_PROFIT">Percent of attributable profit</option>
      <option value="FIXED_PER_TRADE">Fixed per accepted trade</option><option value="PERCENT_NOTIONAL">Percent of notional</option>
    </select></label>
    <label>CSS trade commission rate / amount<input name="trade_commission_rate" inputmode="decimal" value="20"></label>
    <label>Independent trade platform fee basis<select name="independent_trade_fee_basis">
      <option value="NONE">None</option><option value="FIXED_PER_TRADE">Fixed per trade</option><option value="PERCENT_NOTIONAL">Percent of notional</option>
    </select></label>
    <label>Independent trade platform fee rate / amount<input name="independent_trade_fee_rate" inputmode="decimal" value="0"></label>
    <label><input type="checkbox" name="broker_charges_pass_through" value="true"> Pass broker/exchange charges through separately</label>
    <label>Agreement version<input name="agreement_version" required placeholder="e.g. CSS-TERMS-2026-09"></label>
    <button type="submit">Save Configuration</button>
  </form>
  <p id="mc-user-config-result" class="mc-muted" aria-live="polite"></p>
</section>
<script>
document.getElementById('mc-user-account-config')?.addEventListener('submit', async (ev) => {{
  ev.preventDefault();
  const result = document.getElementById('mc-user-config-result');
  const body = new URLSearchParams(new FormData(ev.currentTarget));
  try {{
    const response = await fetch('/operator-config/user-account', {{
      method: 'POST',
      credentials: 'same-origin',
      headers: {{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest'}},
      body
    }});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Save failed');
    result.textContent = 'Configuration saved. User acceptance remains ' + (data.profile?.acceptance_status || 'PENDING') + '.';
  }} catch (err) {{
    result.textContent = String(err.message || err);
  }}
}});
</script>
"""

    current_user = str(auth.get("user_id") or "")
    own = profiles.get(current_user) if isinstance(profiles.get(current_user), dict) else {}
    acceptance = ""
    if own and own.get("acceptance_status") != "ACCEPTED":
        agreement = escape(str(own.get("agreement_version") or ""), quote=True)
        acceptance = f"""
<section class="mc-panel">
  <h2>Accept Account Terms</h2>
  <p>Review the configured access charges, trade commissions, user mode, and trading-risk acknowledgement before accepting version <strong>{agreement}</strong>.</p>
  <form id="mc-user-account-accept">
    <input type="hidden" name="user_id" value="{escape(current_user, quote=True)}">
    <input type="hidden" name="agreement_version" value="{agreement}">
    <label><input type="checkbox" required> I accept the configured charges, commission terms, selected user mode, and the stated trading risks.</label>
    <button type="submit">Accept Terms</button>
  </form>
  <p id="mc-user-accept-result" class="mc-muted" aria-live="polite"></p>
</section>
<script>
document.getElementById('mc-user-account-accept')?.addEventListener('submit', async (ev) => {{
  ev.preventDefault();
  const result = document.getElementById('mc-user-accept-result');
  const body = new URLSearchParams(new FormData(ev.currentTarget));
  try {{
    const response = await fetch('/operator-config/user-account/accept', {{
      method: 'POST',
      credentials: 'same-origin',
      headers: {{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest'}},
      body
    }});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Acceptance failed');
    result.textContent = 'Terms accepted and timestamped.';
  }} catch (err) {{
    result.textContent = String(err.message || err);
  }}
}});
</script>
"""

    return (
        page_header(
            "User Accounts & Commercial Terms",
            "User privileges, operating mode, system access charges, trade commissions, independent-trade fees, and executed acceptance records.",
        )
        + warning_banner(
            "Commercial terms and user preferences do not themselves authorize live execution. CSS remains subject to platform, broker, risk, certification, and execution gates.",
            status="warn",
        )
        + metric_grid(
            (
                ("Configured Users", len(profiles), "neutral"),
                ("Current User", current_user or "UNAVAILABLE", "neutral"),
                ("Administration", "ENABLED" if admin else "VIEW_ONLY", "neutral"),
                ("Execution", "BLOCKED", "blocked"),
            ),
            css_class="mc-metric-grid mc-metric-grid-priority",
            aria_label="User account configuration summary",
        )
        + admin_form
        + acceptance
        + _profile_table(profiles)
    )


__all__ = ["render"]

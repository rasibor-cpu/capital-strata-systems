"""Mandatory onboarding and risk-acceptance page (served by the mobile app).

Client-side gating is UX only; the server enforces everything again (consent.py).
Accessibility:
  - each page is a focusable scroll region; arrow keys / Page Down scroll it;
  - an end-of-page marker counts as reached when it scrolls into view or receives
    keyboard / screen-reader focus;
  - a page that does not need scrolling is counted as reviewed once presented;
  - progress and errors are announced through aria-live regions;
  - the acknowledgement checkbox starts unchecked and is never pre-checked.
"""
from __future__ import annotations

import html
import json

from backend.trading_profiles.manual import ACKNOWLEDGEMENT_TEXT
from backend.trading_profiles.operating_modes import OperatingMode
from backend.trading_profiles.risk_personalities import RiskPersonality

_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CSS onboarding and risk agreement</title>
<style>
  :root { --fg:#111; --bg:#fff; --muted:#555; --accent:#0b57d0; --border:#888; --warn:#8a1c00; }
  @media (prefers-color-scheme: dark) { :root { --fg:#eee; --bg:#121212; --muted:#bbb; --accent:#8ab4f8; --border:#777; --warn:#ffb4a2; } }
  * { box-sizing: border-box; }
  body { margin:0; font: 16px/1.5 system-ui, sans-serif; color:var(--fg); background:var(--bg); }
  main { max-width: 760px; margin: 0 auto; padding: 16px; }
  h1 { font-size: 1.4rem; } h2 { font-size: 1.2rem; }
  fieldset { border:1px solid var(--border); border-radius:8px; margin: 0 0 16px; padding: 12px; }
  label { display:block; margin: 6px 0; }
  input[type=number], input[type=text], select { width: 100%; max-width: 320px; padding: 8px; font-size: 1rem; }
  button { font-size: 1rem; padding: 10px 16px; border-radius: 8px; border:1px solid var(--accent); background: var(--accent); color: #fff; cursor:pointer; }
  button.secondary { background: transparent; color: var(--accent); }
  button:disabled { opacity: .45; cursor: not-allowed; }
  :focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
  .reader { border:1px solid var(--border); border-radius:8px; height: 55vh; overflow-y: auto; padding: 12px 16px; }
  .reader table { border-collapse: collapse; width: 100%; font-size: .9rem; display:block; overflow-x:auto; }
  .reader th, .reader td { border:1px solid var(--border); padding: 4px 6px; text-align:left; }
  .end-marker { margin-top: 24px; padding: 8px; border-top: 2px dashed var(--border); color: var(--muted); }
  .status { margin: 8px 0; min-height: 1.5em; }
  .error { color: var(--warn); }
  .emergency { position: sticky; top: 0; background: var(--bg); padding: 8px 0; border-bottom: 1px solid var(--border); z-index: 2; }
  .hidden { display:none; }
  .ack { border:2px solid var(--accent); border-radius:8px; padding:12px; }
  @media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
</style>
</head>
<body>
<main id="main">
  <div class="emergency">
    <button type="button" class="secondary" id="pause-btn">Pause new trading now</button>
    <span class="status" id="pause-status" role="status" aria-live="polite"></span>
  </div>
  <h1 id="title" tabindex="-1">Set up CSS trading</h1>
  <p>Nothing you choose here sends orders to a broker or enables live trading. Settings take effect only after you review and accept the agreement.</p>
  <div id="error" class="status error" role="alert" aria-live="assertive"></div>

  <section id="step-settings" aria-labelledby="h-settings">
    <h2 id="h-settings">Step 1 of 4: choose your settings</h2>
    <form id="settings-form">
      <fieldset><legend>Trading mode</legend>__MODES__</fieldset>
      <fieldset id="personality-set"><legend>Risk personality</legend>
        <label for="personality">Personality</label>
        <select id="personality" name="risk_personality"><option value="">Choose…</option>__PERSONALITIES__</select>
      </fieldset>
      <fieldset><legend>Optional: your own stricter limits</legend>
        <p>These can only make your personality stricter. A looser value is rejected.</p>
        <label>Max position (% of equity) <input type="number" step="0.1" min="0" name="max_position_pct_of_equity"></label>
        <label>Max total exposure (% of equity) <input type="number" step="0.1" min="0" name="max_total_exposure_pct_of_equity"></label>
        <label>Max open positions <input type="number" step="1" min="1" name="max_open_copied_positions"></label>
        <label>Daily-loss pause (%) <input type="number" step="0.1" min="0" name="daily_loss_halt_pct"></label>
        <label>Drawdown pause (%) <input type="number" step="0.1" min="0" name="max_drawdown_halt_pct"></label>
      </fieldset>
      <fieldset id="mandate-set" class="hidden"><legend>Copy mandate</legend>
        <label>Trader ID <input type="text" name="trader_id" autocomplete="off"></label>
        <fieldset><legend>Asset classes</legend>
          <label><input type="checkbox" name="asset" value="FX"> FX</label>
          <label><input type="checkbox" name="asset" value="CRYPTO"> Crypto</label>
          <label><input type="checkbox" name="asset" value="FUTURES"> Futures</label>
          <label><input type="checkbox" name="asset" value="OPTIONS"> Options</label>
        </fieldset>
        <label>Allocation ceiling <input type="number" step="1" min="1" name="max_allocation"></label>
        <label>Currency <input type="text" name="currency" value="CAD"></label>
        <label>Valid for (days, max 90) <input type="number" step="1" min="1" max="90" name="valid_days" value="30"></label>
        <label>Renew authorization
          <select name="reauthorization_policy"><option value="EACH_SIGN_ON">at each sign-on</option><option value="INTERVAL">every N hours</option></select></label>
        <label>Hours between renewals <input type="number" step="1" min="1" name="reauthorization_interval_hours" value="168"></label>
      </fieldset>
      <button type="submit" id="review-settings-btn">Review these settings</button>
    </form>
  </section>

  <section id="step-summary" class="hidden" aria-labelledby="h-summary">
    <h2 id="h-summary" tabindex="-1">Step 2 of 4: confirm the exact settings</h2>
    <div id="summary"></div>
    <button type="button" id="to-agreement-btn">Continue to the agreement</button>
    <button type="button" class="secondary" id="back-btn">Change settings</button>
  </section>

  <section id="step-reader" class="hidden" aria-labelledby="h-reader">
    <h2 id="h-reader" tabindex="-1">Step 3 of 4: review every page of the agreement</h2>
    <p>Scroll to the end of each page, or move focus to the end-of-page marker with the keyboard or a screen reader. Reaching the end of a page does not prove that you understood it: please read carefully.</p>
    <p id="progress" class="status" role="status" aria-live="polite"></p>
    <div id="reader" class="reader" role="region" tabindex="0" aria-labelledby="page-title">
      <div id="page-content"></div>
      <p id="end-marker" class="end-marker" tabindex="0">End of page</p>
    </div>
    <p>
      <button type="button" class="secondary" id="prev-btn">Previous page</button>
      <button type="button" id="next-btn" disabled>Next page</button>
    </p>
  </section>

  <section id="step-accept" class="hidden" aria-labelledby="h-accept">
    <h2 id="h-accept" tabindex="-1">Step 4 of 4: acknowledgement</h2>
    <p id="doc-ref"></p>
    <div class="ack">
      <input type="checkbox" id="ack-checkbox" disabled aria-describedby="ack-help">
      <label for="ack-checkbox" id="ack-label">__ACK__</label>
      <p id="ack-help" class="status">Available after every page has been reviewed.</p>
    </div>
    <p><button type="button" id="accept-btn" disabled>Accept and activate these settings</button>
       <button type="button" class="secondary" id="cancel-btn">Cancel</button></p>
  </section>

  <section id="step-done" class="hidden" aria-labelledby="h-done">
    <h2 id="h-done" tabindex="-1">Accepted: your receipt</h2>
    <div id="receipt"></div>
  </section>

  <section aria-labelledby="h-docs">
    <h2 id="h-docs">Agreement documents</h2>
    <ul>
      <li><a href="__API__/manual/download?format=md" id="download-md">Download the agreement (Markdown)</a></li>
      <li><a href="__API__/manual/download?format=txt" id="download-txt">Download the agreement (plain text, accessible format)</a></li>
      <li><a href="#" id="history-link">View your acceptance history and document versions</a></li>
    </ul>
    <div id="history" aria-live="polite"></div>
  </section>
</main>
<script>
(() => {
  const API = __API_JSON__;
  const ACK_SHA = __ACK_SHA_JSON__;
  const $ = (id) => document.getElementById(id);
  const state = { change: null, review: null, pages: [], index: 0, reviewed: new Set(), current: null };

  async function call(method, path, body) {
    const res = await fetch(API + path, { method, credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined });
    const data = await res.json().catch(() => ({ ok: false, reason: "invalid_response" }));
    if (!res.ok || data.ok === false) throw new Error(data.reason || ("http_" + res.status));
    return data;
  }
  function showError(e) { $("error").textContent = e ? "Problem: " + (e.message || e) : ""; }
  function show(step) {
    for (const id of ["step-settings", "step-summary", "step-reader", "step-accept", "step-done"]) $(id).classList.toggle("hidden", id !== step);
    const heading = document.querySelector("#" + step + " h2"); if (heading) heading.focus();
  }
  const esc = (s) => String(s).replace(/[&<>"']/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));

  // Emergency risk reduction: always available, never requires acceptance.
  $("pause-btn").addEventListener("click", async () => {
    try { await call("POST", "/emergency/pause"); $("pause-status").textContent = "New trading is paused."; }
    catch (e) { $("pause-status").textContent = "Pause failed: " + e.message; }
  });

  const form = $("settings-form");
  form.addEventListener("change", () => {
    const mode = (form.querySelector("input[name=operating_mode]:checked") || {}).value;
    $("mandate-set").classList.toggle("hidden", mode !== "Copy a CSS Trader");
  });
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault(); showError(null);
    const fd = new FormData(form);
    const limits = {};
    for (const k of ["max_position_pct_of_equity", "max_total_exposure_pct_of_equity", "daily_loss_halt_pct", "max_drawdown_halt_pct"])
      if (fd.get(k)) limits[k] = parseFloat(fd.get(k));
    if (fd.get("max_open_copied_positions")) limits.max_open_copied_positions = parseInt(fd.get("max_open_copied_positions"), 10);
    const payload = { operating_mode: fd.get("operating_mode"), risk_personality: fd.get("risk_personality") || null, limits };
    if (payload.operating_mode === "Copy a CSS Trader") {
      payload.mandate = { trader_id: fd.get("trader_id"), asset_classes: fd.getAll("asset"), max_allocation: parseFloat(fd.get("max_allocation")),
        currency: fd.get("currency"), valid_days: parseFloat(fd.get("valid_days")), reauthorization_policy: fd.get("reauthorization_policy"),
        reauthorization_interval_hours: parseFloat(fd.get("reauthorization_interval_hours") || "0") };
    }
    try {
      const data = await call("POST", "/changes", payload);
      state.change = data.change;
      const s = state.change.effective_settings;
      const rows = Object.entries(s).filter(([k]) => typeof s[k] !== "object" || s[k] === null)
        .map(([k, v]) => "<tr><th scope='row'>" + esc(k.replaceAll("_", " ")) + "</th><td>" + esc(v) + "</td></tr>").join("");
      $("summary").innerHTML = "<p><strong>" + esc(state.change.kind.replaceAll("_", " ")) + "</strong> — policy fingerprint <code>" +
        esc(state.change.policy_hash.slice(0, 16)) + "…</code></p><table>" + rows + "</table><h3>What this means</h3><ul>" +
        state.change.implications.map(i => "<li>" + esc(i) + "</li>").join("") + "</ul>";
      show("step-summary");
    } catch (e) { showError(e); }
  });
  $("back-btn").addEventListener("click", () => show("step-settings"));
  $("cancel-btn").addEventListener("click", () => { state.review = null; show("step-settings"); });

  $("to-agreement-btn").addEventListener("click", async () => {
    showError(null);
    try {
      state.review = await call("POST", "/consent/reviews", { change_id: state.change.change_id });
      state.pages = state.review.pages; state.index = 0; state.reviewed = new Set();
      show("step-reader"); await loadPage(0);
    } catch (e) { showError(e); }
  });

  let observer = null;
  async function loadPage(i) {
    state.index = i;
    const pid = state.pages[i].page_id;
    const page = await call("GET", "/consent/reviews/" + state.review.review_id + "/pages/" + pid);
    state.current = page;
    $("page-content").innerHTML = "<div id='page-title'></div>" + page.html;
    $("page-title").textContent = "Page " + page.index + " of " + page.total + ": " + page.title;
    $("end-marker").textContent = "End of page " + page.index + " of " + page.total;
    $("reader").scrollTop = 0;
    updateButtons();
    if (observer) observer.disconnect();
    if (state.reviewed.has(pid)) return;
    const reader = $("reader");
    if (reader.scrollHeight <= reader.clientHeight + 2) { await markReviewed("non_scrollable_presented"); return; }
    observer = new IntersectionObserver((entries) => {
      if (entries.some(e => e.isIntersecting)) markReviewed("scroll_bottom");
    }, { root: reader, threshold: 1.0 });
    observer.observe($("end-marker"));
  }
  $("end-marker").addEventListener("focus", () => markReviewed("keyboard_end"));

  async function markReviewed(method) {
    const pid = state.current && state.current.page_id;
    if (!pid || state.reviewed.has(pid)) return;
    state.reviewed.add(pid);
    try {
      await call("POST", "/consent/reviews/" + state.review.review_id + "/pages/" + pid + "/reviewed",
        { method, page_sha256: state.current.sha256 });
    } catch (e) { state.reviewed.delete(pid); showError(e); }
    updateButtons();
  }
  function updateButtons() {
    const pid = state.pages[state.index] && state.pages[state.index].page_id;
    const last = state.index === state.pages.length - 1;
    $("prev-btn").disabled = state.index === 0;
    $("next-btn").disabled = !state.reviewed.has(pid);
    $("next-btn").textContent = last ? "Continue to acknowledgement" : "Next page";
    $("progress").textContent = "Pages reviewed: " + state.reviewed.size + " of " + state.pages.length +
      (state.reviewed.has(pid) ? ". This page is reviewed." : ". Reach the end of this page to continue.");
  }
  $("prev-btn").addEventListener("click", () => loadPage(Math.max(0, state.index - 1)).catch(showError));
  $("next-btn").addEventListener("click", () => {
    if (state.index < state.pages.length - 1) { loadPage(state.index + 1).catch(showError); return; }
    $("doc-ref").textContent = "Agreement version " + state.review.manual_version + ", fingerprint " + state.review.manual_sha256.slice(0, 16) + "…";
    const allDone = state.pages.every(p => state.reviewed.has(p.page_id));
    $("ack-checkbox").checked = false;
    $("ack-checkbox").disabled = !allDone;
    $("ack-help").textContent = allDone ? "Check the box to confirm, then accept." : "Available after every page has been reviewed.";
    $("accept-btn").disabled = true;
    show("step-accept");
  });
  $("ack-checkbox").addEventListener("change", () => { $("accept-btn").disabled = !$("ack-checkbox").checked; });

  $("accept-btn").addEventListener("click", async () => {
    if (!$("ack-checkbox").checked) return;
    $("accept-btn").disabled = true; showError(null);
    try {
      const data = await call("POST", "/consent/reviews/" + state.review.review_id + "/accept", {
        acknowledgement_checked: true, acknowledgement_sha256: ACK_SHA, manual_version: state.review.manual_version,
        manual_sha256: state.review.manual_sha256, policy_hash: state.change.policy_hash });
      const r = data.receipt;
      $("receipt").innerHTML = "<dl>" + [["Receipt", r.receipt_id], ["Accepted at (UTC)", r.accepted_at_utc],
        ["Agreement version", r.document.version], ["Agreement fingerprint", r.document.sha256],
        ["Mode", r.operating_mode], ["Personality", r.risk_personality || "—"], ["Policy fingerprint", r.policy_hash],
        ["Live trading authorized", "No"]].map(([k, v]) => "<dt>" + esc(k) + "</dt><dd>" + esc(v) + "</dd>").join("") +
        "</dl><p><a href='" + API + "/consent/receipts/" + encodeURIComponent(r.receipt_id) + "/download'>Download this receipt</a></p>";
      show("step-done");
    } catch (e) { $("accept-btn").disabled = !$("ack-checkbox").checked; showError(e); }
  });

  $("history-link").addEventListener("click", async (ev) => {
    ev.preventDefault();
    try {
      const data = await call("GET", "/consent/receipts");
      $("history").innerHTML = "<h3>Your acceptances</h3><ul>" + (data.receipts.map(r => "<li>" + esc(r.accepted_at_utc) + " — version " +
        esc(r.document.version) + " — " + esc(r.operating_mode) + "</li>").join("") || "<li>None yet</li>") +
        "</ul><h3>Document versions</h3><ul>" + data.document_history.map(h => "<li>" + esc(h.version) + " (" + esc(h.effective_date) + ")" +
        (h.material ? " — material change" : "") + ": " + esc(h.summary) + "</li>").join("") + "</ul>";
    } catch (e) { showError(e); }
  });
})();
</script>
</body>
</html>
"""


def onboarding_html(*, api_prefix: str) -> str:
    from backend.trading_profiles.manual import ACKNOWLEDGEMENT_SHA256

    modes = "".join(
        f'<label><input type="radio" name="operating_mode" value="{html.escape(m.value)}" required> {html.escape(m.value)}</label>'
        for m in OperatingMode)
    personalities = "".join(f'<option value="{html.escape(p.value)}">{html.escape(p.value)}</option>' for p in RiskPersonality)
    return (_PAGE.replace("__MODES__", modes).replace("__PERSONALITIES__", personalities)
            .replace("__ACK__", html.escape(ACKNOWLEDGEMENT_TEXT)).replace("__API_JSON__", json.dumps(api_prefix))
            .replace("__ACK_SHA_JSON__", json.dumps(ACKNOWLEDGEMENT_SHA256)).replace("__API__", html.escape(api_prefix)))

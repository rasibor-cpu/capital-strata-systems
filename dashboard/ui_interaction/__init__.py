"""Enterprise UI interaction helpers (Phase 176B).

Reusable disclosure / accordion contracts that avoid the Chromium/WebKit bug where
``display:flex|grid`` on ``<summary>`` prevents ``<details>`` from toggling.
"""

from __future__ import annotations

import html
import re
from typing import Any


def escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def render_disclosure(
    *,
    title: str,
    body_html: str,
    panel_id: str,
    meta: str = "",
    open_by_default: bool = False,
    class_name: str = "css-disclosure",
) -> str:
    """Render an accessible expand/collapse control that always receives pointer events."""
    expanded = "true" if open_by_default else "false"
    hidden = "" if open_by_default else " hidden"
    trigger_id = f"{panel_id}-trigger"
    meta_html = f'<span class="css-disclosure-meta">{escape(meta)}</span>' if meta else ""
    return f"""
<div class="{escape(class_name)}" data-css-disclosure>
  <button type="button"
          class="css-disclosure-trigger"
          id="{escape(trigger_id)}"
          aria-expanded="{expanded}"
          aria-controls="{escape(panel_id)}"
          data-css-disclosure-trigger>
    <span class="css-disclosure-label">{escape(title)}</span>
    {meta_html}
    <span class="css-disclosure-chevron" aria-hidden="true"></span>
  </button>
  <div id="{escape(panel_id)}"
       class="css-disclosure-panel"
       role="region"
       aria-labelledby="{escape(trigger_id)}"
       data-css-disclosure-panel{hidden}>
    {body_html}
  </div>
</div>
"""


DISCLOSURE_JS = r"""
(function () {
  function bindDisclosure(root) {
    root.querySelectorAll('[data-css-disclosure-trigger]').forEach(function (btn) {
      if (btn.dataset.cssDisclosureBound === '1') return;
      btn.dataset.cssDisclosureBound = '1';
      btn.addEventListener('click', function () {
        var panelId = btn.getAttribute('aria-controls');
        var panel = panelId ? document.getElementById(panelId) : null;
        if (!panel) return;
        var open = btn.getAttribute('aria-expanded') === 'true';
        var next = !open;
        btn.setAttribute('aria-expanded', next ? 'true' : 'false');
        if (next) {
          panel.hidden = false;
          panel.removeAttribute('hidden');
        } else {
          panel.hidden = true;
          panel.setAttribute('hidden', '');
        }
      });
    });
  }
  function bindExpandCollapseAll(root) {
    root.querySelectorAll('[data-css-disclosure-expand-all]').forEach(function (btn) {
      if (btn.dataset.cssDisclosureBound === '1') return;
      btn.dataset.cssDisclosureBound = '1';
      btn.addEventListener('click', function () {
        var scope = btn.closest('[data-css-disclosure-scope]') || document;
        var open = btn.getAttribute('data-css-disclosure-expand-all') !== 'false';
        scope.querySelectorAll('[data-css-disclosure-trigger]').forEach(function (trigger) {
          var panel = document.getElementById(trigger.getAttribute('aria-controls') || '');
          if (!panel) return;
          trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
          panel.hidden = !open;
          if (open) panel.removeAttribute('hidden'); else panel.setAttribute('hidden', '');
        });
      });
    });
  }
  function init(root) {
    root = root || document;
    bindDisclosure(root);
    bindExpandCollapseAll(root);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { init(document); });
  } else {
    init(document);
  }
  window.CSSUIInteraction = { init: init };
})();
"""


# Patterns used for enterprise interaction inventory / certification.
INTERACTIVE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("disclosure_trigger", r"data-css-disclosure-trigger"),
    ("details_summary", r"<summary\b"),
    ("button", r"<button\b"),
    ("select", r"<select\b"),
    ("anchor_nav", r"<a\b[^>]*\shref="),
    ("onclick", r"\bonclick\s*="),
    ("aria_expanded", r"aria-expanded="),
    ("role_button", r'role=["\']button["\']'),
    ("input_control", r"<input\b"),
    ("textarea", r"<textarea\b"),
    ("dialog", r"<dialog\b"),
    ("data_action", r"data-(?:rc-)?action="),
    ("hx_attr", r"\bhx-(?:get|post|target|trigger)\b"),
)


def inventory_html(html_text: str, *, surface: str) -> dict[str, Any]:
    """Count interactive control markers in rendered HTML."""
    counts: dict[str, int] = {}
    total = 0
    for name, pattern in INTERACTIVE_PATTERNS:
        n = len(re.findall(pattern, html_text, flags=re.IGNORECASE))
        counts[name] = n
        total += n
    # Defect heuristics
    defects: list[str] = []
    # summary with display:flex style attribute (inline) is rare; check class patterns in CSS separately
    if re.search(r"<summary\b[^>]*style=[^>]*display\s*:\s*flex", html_text, re.I):
        defects.append("summary_inline_display_flex")
    # decorative selects without name/id
    for m in re.finditer(r"<select\b([^>]*)>", html_text, re.I):
        attrs = m.group(1)
        if "disabled" not in attrs.lower() and "name=" not in attrs.lower() and "id=" not in attrs.lower():
            defects.append("select_without_name_or_id")
    # buttons without type/action/href-like behavior
    dead_buttons = 0
    for m in re.finditer(r"<button\b([^>]*)>(.*?)</button>", html_text, re.I | re.S):
        attrs = m.group(1)
        if "disabled" in attrs.lower():
            continue
        if not any(tok in attrs.lower() for tok in ("onclick", "data-", "aria-controls", "formaction", "name=")):
            # type=submit inside form is ok
            if 'type="submit"' in attrs.lower() or "type='submit'" in attrs.lower():
                continue
            if 'type="button"' in attrs.lower() or "type='button'" in attrs.lower():
                dead_buttons += 1
    if dead_buttons:
        defects.append(f"button_type_button_without_handler:{dead_buttons}")
    return {
        "surface": surface,
        "total_markers": total,
        "counts": counts,
        "defects": defects,
    }

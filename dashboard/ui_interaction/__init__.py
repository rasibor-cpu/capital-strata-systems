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
    anchor_id: str = "",
) -> str:
    """Render an accessible expand/collapse control that always receives pointer events.

    ``anchor_id`` (optional) places a stable deep-link target on the wrapper
    (e.g. ``cat-trading_transactions``) so hash navigation can open the panel.
    """
    expanded = "true" if open_by_default else "false"
    hidden = "" if open_by_default else " hidden"
    trigger_id = f"{panel_id}-trigger"
    meta_html = f'<span class="css-disclosure-meta">{escape(meta)}</span>' if meta else ""
    wrapper_id = f' id="{escape(anchor_id)}"' if anchor_id else ""
    return f"""
<div class="{escape(class_name)}" data-css-disclosure{wrapper_id}>
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
  function setOpen(trigger, panel, open) {
    if (!trigger || !panel) return;
    trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
    panel.hidden = !open;
    if (open) panel.removeAttribute('hidden'); else panel.setAttribute('hidden', '');
  }
  function openDisclosureForTarget(raw) {
    if (!raw) return false;
    var key = String(raw).replace(/^#/, '');
    var candidates = [key];
    if (key.indexOf('cat-panel-') === 0) candidates.push(key.replace(/^cat-panel-/, 'cat-'));
    if (key.indexOf('cat-') === 0 && key.indexOf('cat-panel-') !== 0) {
      candidates.push('cat-panel-' + key.slice(4));
    }
    var i, el, trigger, panel, wrap;
    for (i = 0; i < candidates.length; i++) {
      el = document.getElementById(candidates[i]);
      if (!el) continue;
      if (el.hasAttribute('data-css-disclosure-panel')) {
        panel = el;
        trigger = document.querySelector('[data-css-disclosure-trigger][aria-controls="' + el.id + '"]');
        setOpen(trigger, panel, true);
        wrap = el.closest('[data-css-disclosure]');
        if (wrap && wrap.id) wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
        else el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return true;
      }
      if (el.hasAttribute('data-css-disclosure')) {
        trigger = el.querySelector('[data-css-disclosure-trigger]');
        panel = trigger ? document.getElementById(trigger.getAttribute('aria-controls') || '') : null;
        setOpen(trigger, panel, true);
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return true;
      }
    }
    var section = document.getElementById(key);
    if (section) {
      section.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return true;
    }
    return false;
  }
  function syncSubtabs() {
    var hash = (window.location.hash || '').replace(/^#/, '');
    var section = hash.split(/[?&]/)[0];
    document.querySelectorAll('[data-css-subtab]').forEach(function (link) {
      var target = (link.getAttribute('data-css-subtab') || link.getAttribute('href') || '').replace(/^#/, '');
      var active = target && section && (section === target || section.indexOf(target) === 0);
      link.classList.toggle('is-active', !!active);
      if (active) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
  }
  function applyHash() {
    var hash = window.location.hash || '';
    if (!hash || hash === '#') return;
    var bare = hash.replace(/^#/, '');
    openDisclosureForTarget(bare);
    syncSubtabs();
  }
  function bindDisclosure(root) {
    root.querySelectorAll('[data-css-disclosure-trigger]').forEach(function (btn) {
      if (btn.dataset.cssDisclosureBound === '1') return;
      btn.dataset.cssDisclosureBound = '1';
      btn.addEventListener('click', function () {
        var panelId = btn.getAttribute('aria-controls');
        var panel = panelId ? document.getElementById(panelId) : null;
        if (!panel) return;
        var open = btn.getAttribute('aria-expanded') === 'true';
        setOpen(btn, panel, !open);
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
          setOpen(trigger, panel, open);
        });
      });
    });
  }
  function bindSubtabs(root) {
    root.querySelectorAll('[data-css-subtab]').forEach(function (link) {
      if (link.dataset.cssSubtabBound === '1') return;
      link.dataset.cssSubtabBound = '1';
      link.addEventListener('click', function (ev) {
        var target = (link.getAttribute('data-css-subtab') || link.getAttribute('href') || '').replace(/^#/, '');
        if (!target) return;
        // Same-page hash navigation: open disclosures / scroll, mark active.
        if (link.getAttribute('href') && link.getAttribute('href').charAt(0) === '#') {
          ev.preventDefault();
          if (window.history && window.history.pushState) {
            window.history.pushState(null, '', '#' + target);
          } else {
            window.location.hash = '#' + target;
          }
          openDisclosureForTarget(target);
          syncSubtabs();
        }
      });
    });
  }
  function init(root) {
    root = root || document;
    bindDisclosure(root);
    bindExpandCollapseAll(root);
    bindSubtabs(root);
    applyHash();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { init(document); });
  } else {
    init(document);
  }
  window.addEventListener('hashchange', applyHash);
  window.CSSUIInteraction = {
    init: init,
    openDisclosureForTarget: openDisclosureForTarget,
    applyHash: applyHash,
    syncSubtabs: syncSubtabs
  };
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
    ("subtab", r"data-css-subtab"),
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

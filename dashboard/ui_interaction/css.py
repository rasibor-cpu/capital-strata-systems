"""Shared CSS for enterprise disclosures (Phase 176B)."""

from __future__ import annotations

CSS_DISCLOSURE = """
/* Phase 176B — button disclosures (do NOT use display:flex on <summary>) */
.css-disclosure { margin: 0 0 10px; border: 1px solid var(--mc-line, #2b3b4a); border-radius: 8px; background: var(--mc-surface, #151d25); }
.css-disclosure-trigger {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  min-height: 44px;
  padding: 12px 14px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}
.css-disclosure-trigger:focus-visible {
  outline: 2px solid var(--mc-info, #68a8ff);
  outline-offset: 2px;
}
.css-disclosure-label { flex: 1 1 auto; }
.css-disclosure-meta { color: var(--mc-muted, #a8b4c0); font-size: .78rem; font-weight: 700; }
.css-disclosure-chevron::before { content: "▸"; display: inline-block; transition: transform .15s ease; }
.css-disclosure-trigger[aria-expanded="true"] .css-disclosure-chevron::before { transform: rotate(90deg); }
.css-disclosure-panel { padding: 0 14px 14px; display: grid; gap: 10px; }
.css-disclosure-panel[hidden] { display: none !important; }
.css-disclosure-toolbar { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 12px; }
"""

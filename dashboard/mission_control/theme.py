from __future__ import annotations

from dashboard.ui_interaction.css import CSS_DISCLOSURE


MISSION_CONTROL_CSS = """
:root {
  --mc-bg: #0f1419;
  --mc-surface: #151d25;
  --mc-panel: #1b2631;
  --mc-line: #2b3b4a;
  --mc-text: #e9eef4;
  --mc-muted: #a8b4c0;
  --mc-good: #33c481;
  --mc-warn: #f4b64a;
  --mc-bad: #ff6b6b;
  --mc-info: #68a8ff;
}
* { box-sizing: border-box; }
body.mc-body {
  margin: 0;
  font-family: Inter, Segoe UI, Roboto, Arial, sans-serif;
  background: var(--mc-bg);
  color: var(--mc-text);
}
.mc-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 288px 1fr;
}
.mc-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  z-index: 6;
  background: #101820;
  border-right: 1px solid var(--mc-line);
  padding: 18px 12px;
}
.mc-brand { padding: 8px 10px 18px; }
.mc-brand strong { display: block; font-size: 1.08rem; letter-spacing: .02em; }
.mc-brand span { color: var(--mc-muted); font-size: .82rem; }
.mc-nav { display: grid; gap: 4px; position: relative; z-index: 1; }
.mc-nav a {
  display: flex;
  gap: 8px;
  align-items: center;
  min-height: 44px;
  padding: 8px 10px;
  color: var(--mc-muted);
  text-decoration: none;
  border-radius: 6px;
  border: 1px solid transparent;
  touch-action: manipulation;
  -webkit-tap-highlight-color: rgba(104, 168, 255, .25);
  position: relative;
  z-index: 2;
  cursor: pointer;
  -webkit-user-select: none;
  user-select: none;
}
/* Ensure nested icon/label spans do not become the exclusive touch target. */
.mc-nav a > * {
  pointer-events: none;
}
.mc-nav a[aria-current="page"], .mc-nav a:hover, .mc-nav a:active {
  color: var(--mc-text);
  background: var(--mc-panel);
  border-color: var(--mc-line);
}
.mc-main { min-width: 0; position: relative; z-index: 1; }
.mc-topbar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 14px 22px;
  background: rgba(15, 20, 25, .95);
  border-bottom: 1px solid var(--mc-line);
}
.mc-status-strip { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.mc-badge, .mc-status {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: .76rem;
  font-weight: 700;
  border: 1px solid var(--mc-line);
}
.good { color: #dff8ec; background: rgba(51, 196, 129, .14); border-color: rgba(51, 196, 129, .45); }
.warn { color: #ffe6b1; background: rgba(244, 182, 74, .13); border-color: rgba(244, 182, 74, .48); }
.bad { color: #ffd5d5; background: rgba(255, 107, 107, .14); border-color: rgba(255, 107, 107, .48); }
.neutral { color: var(--mc-text); background: rgba(104, 168, 255, .11); }
.mc-content { padding: 22px; }
.mc-breadcrumb { color: var(--mc-muted); font-size: .82rem; margin-bottom: 12px; }
.css-breadcrumbs { display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin-top:6px; font-size:.82rem; color:var(--mc-muted); }
.css-crumb { color:var(--mc-info); text-decoration:none; }
.css-crumb.current { color:var(--mc-text); font-weight:700; }
.css-crumb-sep { opacity:.55; }
.css-brand-home { display:inline-flex; align-items:center; gap:8px; text-decoration:none; color:var(--mc-text); margin-bottom:6px; min-height:44px; }
.css-brand-mark { background:var(--mc-info); color:#061018; padding:4px 7px; border-radius:4px; font-size:.75rem; font-weight:800; }
.mc-nav-home { margin-bottom:8px; }
.mc-nav-home a {
  display:flex; gap:8px; align-items:center; min-height:44px; padding:8px 10px;
  color:var(--mc-text); text-decoration:none; border-radius:6px; border:1px solid var(--mc-line);
  background:var(--mc-panel);
}
.mc-page-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.mc-page-header h1 { margin: 0 0 6px; font-size: 1.8rem; }
.mc-page-header p { margin: 0; color: var(--mc-muted); max-width: 860px; line-height: 1.45; }
.mc-eyebrow { text-transform: uppercase; letter-spacing: .08em; font-size: .72rem; color: var(--mc-info) !important; margin-bottom: 4px !important; }
.mc-warning {
  margin: 0 0 16px;
  padding: 12px 14px;
  border-radius: 6px;
  border: 1px solid var(--mc-line);
}
.mc-metric-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.mc-metric-card, .mc-panel {
  background: var(--mc-surface);
  border: 1px solid var(--mc-line);
  border-radius: 8px;
  padding: 14px;
}
.mc-metric-card span { display: block; color: var(--mc-muted); font-size: .78rem; margin-bottom: 8px; }
.mc-metric-card strong { display: block; font-size: 1.08rem; line-height: 1.25; overflow-wrap: anywhere; }
.mc-metric-card em { margin-top: 10px; font-style: normal; }
.mc-panel-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.mc-panel h2 { margin: 0 0 10px; font-size: 1rem; }
table { width: 100%; border-collapse: collapse; }
th, td {
  text-align: left;
  vertical-align: top;
  border-top: 1px solid var(--mc-line);
  padding: 8px 6px;
  overflow-wrap: anywhere;
}
th { color: var(--mc-muted); width: 34%; font-weight: 600; }
.mc-footer { color: var(--mc-muted); font-size: .8rem; padding: 18px 22px 28px; }
.rc-subnav { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 16px; }
.rc-subnav-link, .rc-btn, .rc-linkish {
  display: inline-flex; align-items: center; gap: 6px;
  min-height: 36px; padding: 6px 12px;
  border-radius: 6px; border: 1px solid var(--mc-line);
  background: var(--mc-panel); color: var(--mc-text);
  text-decoration: none; cursor: pointer; font: inherit;
}
.rc-subnav-link.is-active, .rc-subnav-link[aria-current="true"] {
  background: rgba(104, 168, 255, .18); border-color: rgba(104, 168, 255, .55); font-weight: 700;
}
.rc-linkish { border: none; background: transparent; color: var(--mc-info); padding: 0; min-height: auto; text-align: left; }
.rc-linkish:focus-visible, .rc-btn:focus-visible, .rc-subnav-link:focus-visible, .css-disclosure-trigger:focus-visible {
  outline: 2px solid var(--mc-info); outline-offset: 2px;
}
.rc-btn-primary { background: rgba(104, 168, 255, .18); border-color: rgba(104, 168, 255, .5); }
.rc-btn:disabled, .rc-btn[disabled] { opacity: .45; cursor: not-allowed; }
/* Phase 176B: category expanders use .css-disclosure (button), not <details>/<summary>.
   Do NOT set display:flex on <summary> — it breaks native details toggle in Chromium/WebKit. */
.rc-card-grid { display: grid; gap: 10px; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
.rc-card { border: 1px solid var(--mc-line); border-radius: 8px; padding: 12px; background: var(--mc-panel); }
.rc-card header { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 8px; }
.rc-card h3 { margin: 0; flex: 1 1 auto; font-size: 1rem; }
.rc-badge { display: inline-flex; align-items: center; min-height: 22px; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--mc-line); font-size: .72rem; font-weight: 700; }
.rc-meta { display: grid; gap: 6px; margin: 0 0 10px; }
.rc-meta div { display: grid; grid-template-columns: 110px 1fr; gap: 8px; }
.rc-meta dt { color: var(--mc-muted); margin: 0; }
.rc-meta dd { margin: 0; overflow-wrap: anywhere; }
.rc-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.rc-form { display: grid; gap: 12px; max-width: 720px; }
.rc-field { display: grid; gap: 6px; }
.rc-field input, .rc-field select, .rc-library-tools input {
  min-height: 38px; padding: 8px 10px; border-radius: 6px;
  border: 1px solid var(--mc-line); background: #0f1419; color: var(--mc-text); font: inherit;
}
.rc-filters { display: grid; gap: 10px; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); }
.rc-result { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 420px; overflow: auto; background: #0f1419; border: 1px solid var(--mc-line); border-radius: 6px; padding: 12px; }
.rc-muted { color: var(--mc-muted); }
.rc-table-wrap { overflow-x: auto; }
.rc-table { width: 100%; border-collapse: collapse; }
.rc-table th, .rc-table td { border-top: 1px solid var(--mc-line); padding: 8px 6px; text-align: left; }
.rc-library-tools { display: flex; flex-wrap: wrap; gap: 8px; align-items: end; margin-bottom: 12px; }
.rc-status-available, .rc-status-available_with_limitations { border-color: rgba(51,196,129,.45); }
.rc-status-coming_soon, .rc-status-data_unavailable, .rc-status-disabled { border-color: rgba(244,182,74,.48); }
@media (max-width: 1100px) {
  /* Phase 176H.3: isolate scrolling so Android Chrome does not pointercancel
     native <a href> taps while the HTML document is the pan surface. */
  html,
  body.mc-body {
    height: 100%;
    max-height: 100dvh;
    overflow: hidden;
  }
  .mc-shell {
    display: flex;
    flex-direction: column;
    height: 100dvh;
    max-height: 100dvh;
    min-height: 0;
    overflow: hidden;
    grid-template-columns: none;
  }
  .mc-sidebar {
    position: static;
    height: auto;
    max-height: min(46vh, 420px);
    overflow: auto;
    flex: 0 0 auto;
    z-index: auto;
    -webkit-overflow-scrolling: touch;
    border-right: 0;
    border-bottom: 1px solid var(--mc-line);
  }
  .mc-main {
    flex: 1;
    min-height: 0;
    overflow: auto;
    position: relative;
    z-index: 1;
  }
  .mc-topbar {
    position: static;
    z-index: auto;
  }
  .mc-nav {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    position: static;
    z-index: auto;
  }
  .mc-metric-grid { grid-template-columns: repeat(2, minmax(140px, 1fr)); }
}
@media (max-width: 680px) {
  .mc-topbar, .mc-page-header { flex-direction: column; align-items: stretch; }
  .mc-nav, .mc-metric-grid, .mc-panel-grid { grid-template-columns: 1fr; }
  .mc-content { padding: 16px; }
  .rc-card-grid, .rc-filters { grid-template-columns: 1fr; }
  .mc-nav a { min-height: 48px; }
}
""" + CSS_DISCLOSURE


__all__ = ["MISSION_CONTROL_CSS"]

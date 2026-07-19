# HealthChecker+

iOS-compatible health tracking web app with trend intelligence and a Python foot-pain diagnostic engine.

## Layout

- `index.html` — primary v6 app shell (dashboard, add, symptoms, reports)
- `app.js`, `js/app.js` — client logic (localStorage-first)
- `style.css`, `css/style.css` — styles
- `gi.html`, `healthchecker_plus_v3.html` — alternate / legacy surfaces
- `manifest.webmanifest`, icons, `sw.js` — PWA assets
- `backend/intelligence/foot_pain_engine.py` — foot pain cause scoring

## Commands

- Serve locally: `python3 -m http.server 8080 --bind 127.0.0.1`
- Open app: `http://127.0.0.1:8080/`
- Unit tests: `python3 -m unittest discover -s tests -p 'test_*.py' -q`
- Syntax check engine: `python3 -c "import ast; ast.parse(open('backend/intelligence/foot_pain_engine.py').read())"`

## Product constraints

- Client state is localStorage-first; do not introduce a required backend for core flows unless explicitly requested.
- Keep medical guidance cautious and non-diagnostic in user-facing copy.
- Preserve iOS / PWA compatibility (viewport meta, manifest, touch icons).

## Cursor Cloud specific instructions

- `scripts/cursor-install.sh` already validated required files and ran unit tests.
- The `web` terminal should already be serving on port `8080`; restart with the serve command above if needed.
- Prefer editing `index.html` + root `app.js` / `style.css` for the current v6 experience.
- Treat `healthchecker_plus_v3.html` and duplicate `js/` / `css/` copies as legacy unless a task names them.
- Do not commit secrets; this app should not need API keys for local UI work.
- Before opening a PR, run: `python3 -m unittest discover -s tests -p 'test_*.py' -q`

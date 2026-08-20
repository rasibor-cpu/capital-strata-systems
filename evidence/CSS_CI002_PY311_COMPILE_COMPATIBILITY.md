# CSS-CI-002 — Python 3.11 compile compatibility repair

**Date (UTC):** 2026-08-20  
**Notepad:** not opened (cloud agent)  
**Canonical line:** `css-v1.0.1-maintenance`  
**Work branch:** `css-agent/css-ci001-gate2-maintenance-target-af15`  
**Draft PR:** https://github.com/rasibor-cpu/capital-strata-systems/pull/65 (not merged)

CI-001 retargeted Gate-2 onto maintenance. Both GitHub checks failed at
`compileall` under Python 3.11.16 before pytest. This gate is the smallest
semantics-preserving repair for that compile blocker.

---

## Phase 1 — offending source

File: `dashboard/enterprise_shell/shell.py` (More-menu link join, previously line 141)

```python
more_links = "".join(
    f'<li><a href="{_esc(href)}"{" aria-current=\"page\"" if active == key else ""}>{_esc(label)}</a></li>'
    for key, label, href in more_items
)
```

### Exact source expression

Inside the f-string, the interpolated expression was:

```python
{" aria-current=\"page\"" if active == key else ""}
```

### Why Python 3.11 rejects it

PEP 498 (f-strings through 3.11) forbids a backslash in the *expression*
part of an f-string. `\"` is a backslash-escaped quote inside `{...}`, so
CPython 3.11 raises:

`SyntaxError: f-string expression part cannot include a backslash`

This is a parse-time error. Pytest never starts.

### Why Python 3.12 accepts it

PEP 701 (Python 3.12) formalized f-string parsing and allows quotes and
backslashes inside interpolations. Cloud agent Python is **3.12.3**, so
local `compileall` passed during CI-001 and hid the GitHub failure.

### Intended resulting string

Identical to the adjacent primary-nav / footer pattern already in this file:

- when `active == key`: ` aria-current="page"` (leading space + quoted attr)
- otherwise: empty string

Example More-list items:

- active `risk`: `<li><a href="/risk" aria-current="page">Risk Command</a></li>`
- inactive: `<li><a href="/risk">Risk Command</a></li>`

### Smallest semantics-preserving rewrite

Compute the attribute string outside the f-string (same form as lines 101–111
and 191), then interpolate the variable:

```python
cur = ' aria-current="page"' if active == key else ""
f'<li><a href="{_esc(href)}"{cur}>{_esc(label)}</a></li>'
```

No dashboard routing, RBAC, or trading behavior change.

---

## Repository-wide scan

Tokenized all `.py` files (2414) for f-string *expressions* containing `\`.

| Location | Classification |
| --- | --- |
| `dashboard/enterprise_shell/shell.py:141` | **IN-SCOPE.** Only Gate-2 compile blocker. Same class as GitHub 3.11 failure. Repaired. |
| `scripts/build_r9c_live_mode_display_capital_fix.py` etc. | **NOT this class.** Regular string literals that *contain* f-string-like text with `\'`. They are not f-string expressions. Left unchanged. |
| `archive/dashboard_versions/*` (5 files) | **OUT OF SCOPE.** Tokenize/syntax errors in archived copies. Gate-2 `compileall` is `backend dashboard launcher scripts` only. |

**SAME_PATTERN_OTHER_FILES=NO** for live Gate-2 compile paths.

---

## Phase 2 — Python version contract

| Source | Finding |
| --- | --- |
| `.github/workflows/css_gate2_release_ci.yml` | `python-version: "3.11"` (step named "Set up Python 3.11") |
| `.github/workflows/css_governance.yml` | `python-version: "3.11"` |
| `.github/workflows/ai-governance-sweep.yml` | `python-version: "3.11"` (not Gate-2; not modified) |
| `pyproject.toml` / `setup.cfg` / `setup.py` | **Absent** |
| `CSS_AI_AGENT_INSTRUCTIONS.md` | Coding standard lists "Python 3.12" |
| Cloud agent | Python **3.12.3** |

CI explicitly pins 3.11. Agent-doc 3.12 is not evidence that Gate-2's 3.11
job is obsolete. **Python 3.11 compatibility is required.** This gate does
**not** retarget CI to 3.12.

`PY311_REQUIRED=YES`

---

## Phase 3 — repair

Files:

- `dashboard/enterprise_shell/shell.py` — More-menu `aria-current` built outside the f-string
- `tests/test_phase177h_navigation_and_paginated_viewer.py` — markup identity
- `tests/test_ci002_py311_fstring_compat.py` — source parse + no-backslash scan
- `evidence/CSS_CI002_PY311_COMPILE_COMPATIBILITY.md` — this file

Trading / R7 / R14F / AntiBleed / caps / execution modes / COW-001 / FINANCE:
not touched.

---

## Phase 4 — compile validation

Cloud Python 3.11 package: **not installed** (`apt` could not locate
`python3.11`). Local 3.11 py_compile / compileall were **not claimed**.

Authoritative 3.11 acceptance is GitHub Actions (this PR's Gate-2 jobs).

Local Python 3.12.3:

```
python3 -m py_compile dashboard/enterprise_shell/shell.py   # OK
python3 -m compileall -q backend dashboard launcher scripts  # OK
```

`git diff --check` — OK (no whitespace errors)

---

## Phase 5 — tests

Focused (cloud 3.12):

- `tests/test_ci002_py311_fstring_compat.py` — **passed**
- `test_more_menu_aria_current_markup_is_plain_attribute` — **passed**
- `test_brand_and_home_links_point_to_landing` — **passed**

One other test in `test_phase177h_navigation_and_paginated_viewer.py`
(`test_options_income_viewer_route_on_launcher`) failed on missing
`reportlab`. Pre-existing environment gap. Not a Gate-2 test. Not repaired.

Exact Gate-2 pytest list from CI-001:

```
51 collected
49 passed
2 failed
```

Failures (unchanged AR-023, not repaired):

- `test_ar023_no_hardcoded_bootstrap_password` (`MIN_PASSWORD_LENGTH` is 8; test expects `>= 12`)
- `test_ar023_bootstrap_seeds_with_strong_secret` (bootstrap helper requires exactly 8-char `CSS_BOOTSTRAP_ADMIN_PASSWORD`)

OV-002 identity probe failures are not in this Gate-2 list. Not repaired.

---

## Phase 6 — PR #65 integration

The compatibility fix is committed on the existing CI-001 branch
`css-agent/css-ci001-gate2-maintenance-target-af15` behind draft PR **#65**.
No rebase, no force-push, no merge.

### GitHub Actions before this commit (CI-001 HEAD `50bfcf74`)

- compileall → **FAIL** (Python 3.11, `shell.py` f-string backslash)
- pytest → **NOT STARTED**

### GitHub Actions after this commit (`e9f97705`, Python 3.11.16)

Both named checks ran on the `pull_request` event.

| Workflow | Run | Compile step | Pytest started | Job result |
| --- | --- | --- | --- | --- |
| CSS Gate 2 Release CI | [32388277442](https://github.com/rasibor-cpu/capital-strata-systems/actions/runs/32388277442) | **PASS** (`Python compile (scoped)`) | **YES** | FAILURE (pytest) |
| CSS Governance Validation | [32388277428](https://github.com/rasibor-cpu/capital-strata-systems/actions/runs/32388277428) | **PASS** (`Python Syntax Validation (scoped)`) | **YES** | FAILURE (pytest) |

GitHub pytest: **2 failed, 49 passed** — same AR-023 pair as local. No new compile error. No new P0/P1 functional blocker before pytest.

`PYTHON311_COMPILE_BLOCKER_CLEARED=YES`

---

## Phase 7 — additional compile errors

GitHub 3.11 compileall advanced past `shell.py` with **no further syntax
errors**. No additional compatibility repair was required.

---

## Phase 8 — next task

Not started in this gate.

**NEXT_CLOUD_TASK_ID=RSM-P1-03**  
Reconcile Package D metadata drift (`STATUS.md` still REVIEW; canonical status
still vs `d53e665` even though PR #62 is merged). Small, cloud-safe, no FINANCE.

---

## Recommendation

CI-002 acceptance is met: Python 3.11 compileall **PASS**, pytest **STARTED**.
Keep PR #65 draft and unmerged until the operator accepts CI-001+CI-002
together. Remaining Gate-2 red is **AR-023 only** and is out of this gate.
Do not start RSM-P1-03 here.

`PYTHON311_COMPILE_BLOCKER_CLEARED=YES`

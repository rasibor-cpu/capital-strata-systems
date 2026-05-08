# CSS Auth And Mobile Smoke Gate

This gate protects the CSS sign-on and mobile surfaces from accidental
regression. Any change touching auth, mobile, runtime access, user session
handling, execution controls, broker mode selection, or order enablement must
run the smoke checks below before commit.

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m dashboard.auth.css_sign_on_smoke_test
.\.venv\Scripts\python.exe -m dashboard.mobile.mobile_smoke_test
.\.venv\Scripts\python.exe -m dashboard.runtime.runtime_smoke_test
```

Required pass output:

- `CSS sign-on smoke test PASSED`
- `CSS mobile web smoke test PASSED`
- `CSS runtime smoke test PASSED`

The smoke scripts are command-style checks, not pytest test suites. If they are
converted to pytest tests later, keep these three gate areas covered:

- sign-on authentication/session behavior
- mobile protected access and execution controls
- runtime dashboard bootstrap and payload compatibility

Do not bypass this gate for auth or mobile changes. If any smoke check fails,
fix the failing behavior or explicitly document the blocked state before
continuing the sprint.

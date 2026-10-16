# H2 test evidence (Linux box, Python 3.13.5, 2026-10-16 18:35 EDT)

| Run | Result |
|---|---|
| New H2 suite tests/test_css129_h2_questrade_refresh_hardening.py | 19 passed (5 consecutive runs, all 19 passed) |
| Same suite against pre-change code | 19 errors (import of new coordination module fails), red before green |
| Existing Questrade suites (test_mc_r8*, r83, r84*, r85*, phase178d) | 67 passed |
| Full suite, this branch | 1 failed, 4489 passed, 9 skipped (19m27s) |
| Full suite, base css-final-integration@a7a9bcd5 | 1 failed, 4470 passed, 9 skipped (19m34s) |

The only failure is identical on the base and the branch (pre-existing, unrelated):
```
FAILED tests/test_css118_router.py::test_http_assisted_flow_and_paper_book - ...
```

Windows: comes from the css118-validation workflow (full-suite windows-latest) on push of this branch; the msvcrt lock path is exercised only there.

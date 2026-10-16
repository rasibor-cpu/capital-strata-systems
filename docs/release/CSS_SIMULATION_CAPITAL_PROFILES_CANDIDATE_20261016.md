# CSS simulated capital profiles — isolated candidate

Status: implementation candidate, **NOT RELEASED**, no live broker path added.

## User experience
Default standard simulated balance: CAD 100,000. Presets: small CAD 10,000, intermediate CAD 25,000, standard CAD 100,000, advanced CAD 250,000. Custom: CAD 1,000–1,000,000, with cents precision. Account resets must preserve an audit trail; this candidate does not yet implement a reset UI or an onboarding UI.

## Engineering trial
For the isolated two-track 48-hour trial use:

```sh
python tools/css_sim_cad146.py run --root artifacts/simulation/cad14600-20261016 --artifacts artifacts/calibration --operator YOUR_ID --hours 48 --capital-profile engineering
python tools/css_sim_cad146.py report --root artifacts/simulation/cad14600-20261016 --capital-profile engineering
```

Engineering capital: CAD 14,600. Reference: CAD 146. Report includes illustrative P&L scaling, 100:1, not executable results at CAD 146. Returns (%) are compared without scaling. The CLI default is engineering to preserve the intended internal trial; standard customer onboarding must explicitly select the standard profile.

Existing per-run metadata persists capital on restart; changing the profile against an existing root must not silently reset the balance. Use a new root for a new scenario.

**Governance unchanged:** Track A requires calibration approvals; Track B is research-only; R7 sign-on, AntiBleed CAD 50 minimum, R14F, consent, safety flags, position limits and data outage controls stay intact. Live orders disabled. No 48-hour run was started.

## Acceptance pending
The new unit tests were committed but have not been executed by this assistant. Linux/Windows full regression, browser UX, runtime integration, capital-selection UI, reset audit trail, operator sign-off, real data access and persistent cloud runtime are outstanding. Do not merge or describe as production ready until independently verified.

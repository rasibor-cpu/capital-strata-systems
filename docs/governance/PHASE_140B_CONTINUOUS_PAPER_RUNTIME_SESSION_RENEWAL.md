# Phase 140B Continuous Paper Runtime Session Renewal

Phase 140B permits automatic max-age renewal only for CSS PAPER runtime sessions when broker execution is disabled.

## Safety Boundaries

- LIVE mode is never auto-renewed.
- Any enabled broker execution flag blocks renewal.
- Session renewal does not enable live execution, broker permissions, RBAC, Capital Governor, Unified Trade Gate, or AntiBleedGuard.
- Expired LIVE sessions still require explicit valid re-authentication before trading can continue.
- The renewal status API is read-only and exposes no action that can place trades or enable live trading.

## Audit Fields

- `session_renewal_mode`
- `last_session_renewal_at`
- `session_renewal_count`
- `session_renewal_reason`
- `continuous_paper_runtime_enabled`

## Visibility

`GET /api/session-renewal-status` reports session age, max session seconds, renewal count, renewal mode, renewal allowed, next expiry or renewal time, and live renewal blocked status.

The mobile dashboard also shows renewal count, mode, allowed status, next expiry or renewal time, and live renewal blocked status in the Session Continuity card.

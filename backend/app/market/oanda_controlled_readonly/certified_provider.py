"""Phase 188 — controlled OANDA read-only certification provider.

Uses ONLY backend.runtime.oanda_live_read_only_adapter.OandaLiveReadOnlyAdapter.
Never imports the execution-capable broker adapter module.

Controlled network I/O occurs only when credentials are present AND
allow_controlled_network=True (or a read_client is injected).
Execution remains impossible.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from backend.app.market.oanda_readonly_certification.contracts import (
    SCHEMA_VERSION,
    OandaReadOnlyCertification,
)
from backend.app.market.oanda_readonly_certification.evidence import (
    OandaReadOnlyEvidencePackage,
    build_evidence_package,
    redact_diagnostics,
)
from backend.app.market.oanda_readonly_certification.fingerprint import (
    ProviderFingerprint,
    build_provider_fingerprint,
)
from backend.app.market.oanda_readonly_certification.framework import (
    OandaReadOnlyCertificationFramework,
)
from backend.app.market.oanda_readonly_certification.gates import evaluate_gates
from backend.app.market.oanda_controlled_readonly.firewall import (
    adapter_has_no_write_methods,
    verify_phase188_firewall,
)
from backend.app.market.oanda_controlled_readonly.network_validators import (
    validate_dns,
    validate_tls,
)
from backend.app.market.oanda_controlled_readonly.readonly_transport import (
    OandaReadOnlyHttpTransport,
    build_transport_from_env,
)
from backend.runtime.oanda_live_read_only_adapter import OandaLiveReadOnlyAdapter

PHASE188_VERSION = "188.1"
PROVIDER_NAME_188 = "OANDA_CONTROLLED_READONLY_CERTIFIED_PROVIDER"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _redact_account_id(value: str) -> str:
    text = str(value or "")
    if len(text) <= 4:
        return "[REDACTED]"
    return f"...{text[-4:]}"


class CertifiedOandaReadOnlyProvider:
    """Controlled read-only certification orchestrator."""

    FORBIDDEN_METHODS: frozenset[str] = frozenset(
        {
            "place_order",
            "submit_order",
            "cancel_order",
            "modify_order",
            "create_order",
            "close_order",
            "close_trade",
            "close_position",
            "arm_live_authority",
            "enable_execution",
            "set_execution_enabled",
            "modify_anti_bleed",
            "set_anti_bleed_min_size",
            "modify_risk_governor",
            "modify_phase152a",
            "modify_margin",
            "disable_kill_switch",
        }
    )

    def __init__(
        self,
        *,
        env: Mapping[str, Any] | None = None,
        adapter: OandaLiveReadOnlyAdapter | None = None,
        read_client: Any | None = None,
        allow_controlled_network: bool = False,
        dns_validator: Callable[..., Any] | None = None,
        tls_validator: Callable[..., Any] | None = None,
        now: Callable[[], datetime] | None = None,
        instrument: str = "EUR_USD",
    ) -> None:
        import os

        self.env = env if isinstance(env, Mapping) else os.environ
        self.allow_controlled_network = bool(allow_controlled_network)
        self.instrument = instrument
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._dns_validator = dns_validator or validate_dns
        self._tls_validator = tls_validator or validate_tls
        self._framework = OandaReadOnlyCertificationFramework()
        self._last_evidence: OandaReadOnlyEvidencePackage | None = None
        self._last_cert: OandaReadOnlyCertification | None = None

        client = read_client
        if client is None and self.allow_controlled_network:
            client = build_transport_from_env(self.env)

        # Always construct the canonical RO adapter; never the execution adapter class.
        self.adapter = adapter or OandaLiveReadOnlyAdapter(
            env=self.env,
            read_client=client,
            now=self.now,
        )
        if not isinstance(self.adapter, OandaLiveReadOnlyAdapter):
            raise TypeError("Phase 188 requires OandaLiveReadOnlyAdapter")

    @property
    def last_evidence(self) -> OandaReadOnlyEvidencePackage | None:
        return self._last_evidence

    @property
    def last_certification(self) -> OandaReadOnlyCertification | None:
        return self._last_cert

    def certify(self, *, timestamp: str | None = None) -> OandaReadOnlyCertification:
        ts = timestamp or _utc_now()
        started = time.perf_counter()
        diagnostics: dict[str, Any] = {
            "phase": "188",
            "phase_version": PHASE188_VERSION,
            "network_mode": "CONTROLLED" if self.allow_controlled_network else "OFF",
            "instrument": self.instrument,
        }
        flags: dict[str, bool] = {}
        latency: dict[str, float] = {}

        # --- credentials / environment / endpoint ---
        cred = self.adapter.credential_diagnostics()
        diagnostics["credentials"] = {
            "token_present": cred.get("oanda_token_present"),
            "account_present": cred.get("oanda_account_present"),
            "base_url_present": cred.get("oanda_base_url_present"),
            "credential_status": cred.get("credential_status"),
            "missing_credentials": list(cred.get("missing_credentials") or []),
            "redacted": True,
        }
        flags["config_present"] = cred.get("credential_status") == "PRESENT"

        endpoint = str(self.env.get("OANDA_BASE_URL", "") or "").strip()
        env_name = self._infer_environment(endpoint)
        diagnostics["environment"] = env_name
        diagnostics["endpoint"] = endpoint
        endpoint_ok = bool(endpoint) and endpoint.lower().startswith("https://")
        flags["config_validated"] = bool(
            flags["config_present"] and endpoint_ok and env_name != "UNKNOWN"
        )

        fp = build_provider_fingerprint(
            endpoint=endpoint,
            api_version="v3",
            provider_name=PROVIDER_NAME_188,
            provider_version=PHASE188_VERSION,
            adapter_version=getattr(OandaReadOnlyHttpTransport, "ADAPTER_VERSION", "188.1"),
            schema_version=SCHEMA_VERSION,
        )
        diagnostics["provider_fingerprint"] = fp.as_dict()

        # Firewall proof embedded in diagnostics (static).
        fw = verify_phase188_firewall()
        diagnostics["execution_firewall"] = {
            "ok": fw["ok"],
            "grants_execution": False,
            "violations": list(fw.get("violations") or []),
        }
        adapter_fw = adapter_has_no_write_methods()
        diagnostics["adapter_firewall"] = adapter_fw

        if not flags["config_present"]:
            cert = self._emit(
                flags,
                diagnostics,
                latency,
                ts,
                fp,
                failure_reason="missing_credentials",
            )
            return cert

        if not flags["config_validated"]:
            cert = self._emit(
                flags,
                diagnostics,
                latency,
                ts,
                fp,
                failure_reason="invalid_environment_or_endpoint",
            )
            return cert

        # --- DNS / TLS ---
        # Injected read_client path: structural endpoint checks only (no live DNS/TLS).
        # Controlled network path: real or injected validators.
        if self.adapter.read_client is not None and not self.allow_controlled_network:
            from backend.app.market.oanda_controlled_readonly.network_validators import (
                parse_endpoint,
            )

            host, _port = parse_endpoint(endpoint)
            flags["dns_ok"] = bool(host)
            latency["dns_ms"] = 0.0
            diagnostics["dns"] = {
                "ok": flags["dns_ok"],
                "host": host,
                "address_count": 1 if host else 0,
                "error": "" if host else "missing_host",
                "mode": "structural_injected_client",
            }
            flags["tls_ok"] = endpoint.lower().startswith("https://")
            latency["tls_ms"] = 0.0
            diagnostics["tls"] = {
                "ok": flags["tls_ok"],
                "protocol": "HTTPS" if flags["tls_ok"] else "",
                "cipher": "",
                "not_after": "",
                "clock_skew_ok": True,
                "error": "" if flags["tls_ok"] else "https_required",
                "mode": "structural_injected_client",
            }
            diagnostics["certificate_info"] = {
                "protocol": diagnostics["tls"]["protocol"],
                "not_after": "",
                "cipher": "",
                "mode": "structural_injected_client",
            }
        elif self.allow_controlled_network or self._dns_validator is not validate_dns:
            dns = self._dns_validator(endpoint)
            latency["dns_ms"] = float(getattr(dns, "latency_ms", 0.0))
            flags["dns_ok"] = bool(getattr(dns, "ok", False))
            diagnostics["dns"] = {
                "ok": flags["dns_ok"],
                "host": getattr(dns, "host", ""),
                "address_count": len(getattr(dns, "addresses", ()) or ()),
                "error": getattr(dns, "error", ""),
            }
            if flags["dns_ok"] and (
                self.allow_controlled_network or self._tls_validator is not validate_tls
            ):
                tls = self._tls_validator(endpoint)
                latency["tls_ms"] = float(getattr(tls, "latency_ms", 0.0))
                flags["tls_ok"] = bool(getattr(tls, "ok", False)) and bool(
                    getattr(tls, "clock_skew_ok", True)
                )
                diagnostics["tls"] = {
                    "ok": flags["tls_ok"],
                    "protocol": getattr(tls, "protocol", ""),
                    "cipher": getattr(tls, "cipher", ""),
                    "not_after": getattr(tls, "not_after", ""),
                    "clock_skew_ok": getattr(tls, "clock_skew_ok", True),
                    "error": getattr(tls, "error", ""),
                }
                diagnostics["certificate_info"] = {
                    "protocol": getattr(tls, "protocol", ""),
                    "not_after": getattr(tls, "not_after", ""),
                    "cipher": getattr(tls, "cipher", ""),
                }
            else:
                flags["tls_ok"] = False
                diagnostics["tls"] = {"ok": False, "error": "dns_failed_or_tls_skipped"}
        else:
            flags["dns_ok"] = False
            flags["tls_ok"] = False
            diagnostics["dns"] = {"ok": False, "error": "network_disabled"}
            diagnostics["tls"] = {"ok": False, "error": "network_disabled"}

        flags["auth_pending"] = bool(flags.get("tls_ok"))

        # --- authentication / account / market (via RO adapter only) ---
        if flags["auth_pending"] and (
            self.allow_controlled_network or self.adapter.read_client is not None
        ):
            t0 = time.perf_counter()
            auth = self.adapter.authenticate()
            latency["auth_ms"] = (time.perf_counter() - t0) * 1000.0
            flags["auth_ok"] = bool(auth.get("authenticated")) and bool(auth.get("connected"))
            diagnostics["authentication"] = {
                "authenticated": bool(auth.get("authenticated")),
                "connected": bool(auth.get("connected")),
                "broker_health": auth.get("broker_health"),
                "connection_error": str(auth.get("connection_error") or "")[:160],
            }
        else:
            flags["auth_ok"] = False
            diagnostics["authentication"] = {
                "authenticated": False,
                "reason": "auth_skipped_no_client_or_network",
            }

        if flags["auth_ok"]:
            t0 = time.perf_counter()
            summary = self.adapter.account_summary()
            latency["account_ms"] = (time.perf_counter() - t0) * 1000.0
            currency = str(summary.get("currency") or "")
            account_id = str(summary.get("account_id") or "")
            flags["account_ok"] = bool(currency) and account_id not in {"", "UNKNOWN"}
            # Scope: FX margin account with currency; balances redacted from evidence.
            flags["account_scope_ok"] = flags["account_ok"] and currency.upper() in {
                "USD",
                "CAD",
                "EUR",
                "GBP",
                "AUD",
                "JPY",
                "CHF",
                "NZD",
            }
            diagnostics["account_scope"] = {
                "currency": currency,
                "account_id_redacted": _redact_account_id(account_id),
                "financials_excluded": True,
            }

            t0 = time.perf_counter()
            instruments = self.adapter.get_instruments()
            latency["instruments_ms"] = (time.perf_counter() - t0) * 1000.0
            instrument_names = _instrument_names(instruments)
            visible = self.instrument in instrument_names or bool(instrument_names)
            t0 = time.perf_counter()
            quote = self.adapter.market_data(self.instrument)
            latency["market_ms"] = (time.perf_counter() - t0) * 1000.0
            price = float(quote.get("price") or 0.0)
            fresh = str(quote.get("status") or "") == "OK" and price > 0
            flags["marketdata_ok"] = bool(visible and fresh)
            diagnostics["market_data_quality"] = {
                "instrument": self.instrument,
                "instrument_visible": visible,
                "instrument_count": len(instrument_names),
                "quote_status": quote.get("status"),
                "price_positive": price > 0,
                "freshness": "OK" if fresh else "STALE_OR_MISSING",
            }
            flags["read_only_certified"] = (
                flags.get("marketdata_ok", False)
                and fw["ok"]
                and adapter_fw["ok"]
            )
        else:
            flags["account_ok"] = False
            flags["account_scope_ok"] = False
            flags["marketdata_ok"] = False
            flags["read_only_certified"] = False

        latency["overall_ms"] = (time.perf_counter() - started) * 1000.0
        diagnostics["latency_ms"] = dict(latency)
        diagnostics["schema_versions"] = {"contracts": SCHEMA_VERSION, "phase188": PHASE188_VERSION}
        diagnostics["provider_versions"] = {
            "phase188": PHASE188_VERSION,
            "adapter": "OandaLiveReadOnlyAdapter",
            "transport": OandaReadOnlyHttpTransport.ADAPTER_VERSION,
        }

        return self._emit(flags, diagnostics, latency, ts, fp)

    def _emit(
        self,
        flags: Mapping[str, bool],
        diagnostics: Mapping[str, Any],
        latency: Mapping[str, float],
        ts: str,
        fp: ProviderFingerprint,
        *,
        failure_reason: str = "",
    ) -> OandaReadOnlyCertification:
        failed = bool(failure_reason) and not flags.get("config_present")
        cert = self._framework.certify(
            flags,
            failed=failed,
            failure_reason=failure_reason,
            diagnostics={
                **dict(diagnostics),
                "latency_ms": dict(latency),
                "endpoint": fp.endpoint,
                "certificate_info": dict(diagnostics.get("certificate_info") or {}),
                "account_scope": dict(diagnostics.get("account_scope") or {}),
                "market_data_quality": dict(diagnostics.get("market_data_quality") or {}),
                "api_version": "v3",
            },
            timestamp=ts,
            fingerprint=fp,
        )
        # Reinforce execution isolation on returned object.
        if cert.execution_authority:
            raise RuntimeError("Phase 188 invariant violated: execution_authority true")

        gates = evaluate_gates(flags)
        evidence = build_evidence_package(
            timestamp=ts,
            certification_state=cert.certification_state,
            connection_diagnostics=redact_diagnostics(
                {
                    "credentials": diagnostics.get("credentials"),
                    "dns": diagnostics.get("dns"),
                    "tls": diagnostics.get("tls"),
                    "authentication": diagnostics.get("authentication"),
                    "execution_firewall": diagnostics.get("execution_firewall"),
                    "network_mode": diagnostics.get("network_mode"),
                }
            ),
            provider_versions=dict(diagnostics.get("provider_versions") or {}),
            schema_versions=dict(diagnostics.get("schema_versions") or {}),
            latency_ms=dict(latency),
            endpoint=fp.endpoint,
            certificate_info=dict(diagnostics.get("certificate_info") or {}),
            account_scope=dict(diagnostics.get("account_scope") or {}),
            market_data_quality=dict(diagnostics.get("market_data_quality") or {}),
            gate_results=[
                {
                    "gate_id": g.gate_id,
                    "name": g.name,
                    "passed": g.passed,
                    "reason": g.reason,
                    "grants_execution": False,
                }
                for g in gates
            ],
            parent_certification_id=cert.parent_certification_id,
            previous_evidence_hash="",
            lineage_generation=cert.certification_generation,
            provider_fingerprint_hash=fp.fingerprint_hash(),
            certification_id=cert.certification_id,
        )
        self._last_evidence = evidence
        self._last_cert = cert
        return cert

    def _infer_environment(self, endpoint: str) -> str:
        lower = endpoint.lower()
        if "fxtrade" in lower:
            return "LIVE"
        if "fxpractice" in lower:
            return "PRACTICE"
        if not endpoint:
            return "UNKNOWN"
        return "CUSTOM"

    def __getattribute__(self, name: str) -> Any:
        if name in CertifiedOandaReadOnlyProvider.FORBIDDEN_METHODS:
            raise AttributeError(
                f"Phase 188 forbids execution method '{name}' on CertifiedOandaReadOnlyProvider"
            )
        return object.__getattribute__(self, name)


def run_controlled_certification(
    *,
    env: Mapping[str, Any] | None = None,
    allow_controlled_network: bool | None = None,
    read_client: Any | None = None,
    instrument: str = "EUR_USD",
) -> OandaReadOnlyCertification:
    """Entry point: enable controlled network only when credentials already exist."""
    import os

    source = env if isinstance(env, Mapping) else os.environ
    probe = OandaLiveReadOnlyAdapter(env=source)
    creds_present = probe.credential_diagnostics().get("credential_status") == "PRESENT"
    if allow_controlled_network is None:
        allow = bool(creds_present and read_client is None)
    else:
        allow = bool(allow_controlled_network) and bool(creds_present or read_client is not None)
    # Never enable network when credentials missing (unless injected client for tests).
    if not creds_present and read_client is None:
        allow = False
    provider = CertifiedOandaReadOnlyProvider(
        env=source,
        read_client=read_client,
        allow_controlled_network=allow,
        instrument=instrument,
    )
    return provider.certify()


def _instrument_names(payload: Any) -> list[str]:
    if payload is None:
        return []
    if isinstance(payload, list):
        names: list[str] = []
        for item in payload:
            if isinstance(item, Mapping):
                name = item.get("name") or item.get("instrument") or item.get("symbol")
                if name:
                    names.append(str(name))
            elif isinstance(item, str):
                names.append(item)
        return names
    if isinstance(payload, Mapping):
        for key in ("instruments", "products", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return _instrument_names(value)
    return []

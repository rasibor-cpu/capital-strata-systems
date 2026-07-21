"""Enterprise-lease Questrade advisory runtime with no built-in network transport."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from backend.brokers.questrade.contracts import (
    map_accounts,
    map_balances,
    map_option_chain,
    map_positions,
    map_quotes,
)
from backend.brokers.runtime.runtime_models import BrokerCapabilityContract
from backend.options.options_income_freshness import utc_now
from backend.security.identity.runtime_secret_lease import RuntimeSecretLease


QUESTRADE_READ_ONLY_CAPABILITIES = BrokerCapabilityContract(
    broker="QUESTRADE",
    operations=(
        "ACCOUNTS",
        "BALANCES",
        "HOLDINGS",
        "POSITIONS",
        "OPTION_POSITIONS",
        "WATCHLISTS",
        "MARKET_PERMISSIONS",
        "EQUITIES",
        "ETFS",
        "QUOTES",
        "OPTION_CHAINS",
        "EXPIRATION_CALENDARS",
    ),
    credential_capabilities=("OAUTH_ACCESS_TOKEN",),
)


class QuestradeEnterpriseDataProvider(Protocol):
    def fetch(
        self,
        dataset: str,
        *,
        authorization: memoryview,
        parameters: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


class DisabledQuestradeEnterpriseDataProvider:
    def fetch(self, *_: Any, **__: Any) -> Mapping[str, Any]:
        raise RuntimeError("QUESTRADE_PROVIDER_DISABLED")


class QuestradeEnterpriseReadOnlyRuntime:
    def __init__(
        self,
        *,
        access_token_lease: RuntimeSecretLease,
        provider: QuestradeEnterpriseDataProvider | None = None,
        capabilities: BrokerCapabilityContract = QUESTRADE_READ_ONLY_CAPABILITIES,
        account_reference: str | None = None,
    ):
        if access_token_lease.metadata.broker != "QUESTRADE":
            raise ValueError("QUESTRADE_LEASE_REQUIRED")
        if access_token_lease.metadata.capability != "OAUTH_ACCESS_TOKEN":
            raise ValueError("QUESTRADE_ACCESS_TOKEN_CAPABILITY_REQUIRED")
        self.lease = access_token_lease
        self.provider = provider or DisabledQuestradeEnterpriseDataProvider()
        self.capabilities = capabilities
        self._account_reference = account_reference

    def discover_accounts(self) -> dict[str, Any]:
        raw = self._fetch("ACCOUNTS")
        if raw.get("status") != "ADVISORY_READY":
            return raw
        mapped = map_accounts(raw["payload"], generated_at=raw["acquisition_timestamp"])
        source_accounts = raw["payload"].get("accounts")
        source_accounts = source_accounts if isinstance(source_accounts, list) else []
        aliases = [
            {
                "account_hash": row.get("account_hash"),
                "alias": source.get("alias") or source.get("name") or row.get("masked_identifier"),
                "provenance": "QUESTRADE_ACCOUNT_DISCOVERY",
            }
            for row, source in zip(
                mapped.get("accounts", []),
                source_accounts,
            )
            if isinstance(source, Mapping)
        ]
        return self._ready("ACCOUNTS", {**mapped, "account_aliases": aliases}, raw)

    def balances(self, *, account_reference: str, account_type: str | None = None) -> dict[str, Any]:
        raw = self._fetch("BALANCES", account_reference=account_reference)
        if raw.get("status") != "ADVISORY_READY":
            return raw
        mapped = map_balances(
            raw["payload"],
            account_type=account_type,
            generated_at=raw["acquisition_timestamp"],
        )
        return self._ready("BALANCES", mapped, raw)

    def positions(self, *, account_reference: str) -> dict[str, Any]:
        raw = self._fetch("POSITIONS", account_reference=account_reference)
        if raw.get("status") != "ADVISORY_READY":
            return raw
        mapped = map_positions(raw["payload"], generated_at=raw["acquisition_timestamp"])
        return self._ready("POSITIONS", mapped, raw)

    def select_account_reference(self, account_reference: str) -> None:
        """Bind an opaque provider account reference without exposing it in outputs."""
        if not str(account_reference or "").strip():
            raise ValueError("ACCOUNT_REFERENCE_REQUIRED")
        self._account_reference = str(account_reference)

    def get_holdings_snapshot(self) -> dict[str, Any]:
        if not self._account_reference:
            return self._failure(
                "HOLDINGS",
                "DATA_DEPENDENCY_BLOCKED",
                "ACCOUNT_REFERENCE_REQUIRED",
                utc_now(),
            )
        positions = self.positions(account_reference=self._account_reference)
        balances = self.balances(account_reference=self._account_reference)
        if positions.get("runtime_status") != "ADVISORY_READY":
            return positions
        if balances.get("runtime_status") != "ADVISORY_READY":
            return balances
        balance_rows = list(balances.get("balances") or [])
        primary = balance_rows[0] if balance_rows else {}
        return {
            **positions,
            "status": "HOLDINGS_READY",
            "broker": "QUESTRADE",
            "cash": primary.get("cash"),
            "buying_power": primary.get("buying_power"),
            "maintenance_excess": primary.get("maintenance_excess"),
            "base_currency": primary.get("currency"),
            "balances": balance_rows,
            "provider_timestamp": positions.get("provider_timestamp")
            or balances.get("provider_timestamp"),
            "provenance": "BROKER",
            "fabricated": False,
            "execution_allowed": False,
        }

    def watchlists(self) -> dict[str, Any]:
        raw = self._fetch("WATCHLISTS")
        if raw.get("status") != "ADVISORY_READY":
            return raw
        rows = raw["payload"].get("watchlists")
        return self._ready(
            "WATCHLISTS",
            {
                "watchlists": list(rows) if isinstance(rows, list) else [],
                "provenance": "QUESTRADE_WATCHLISTS",
            },
            raw,
        )

    def market_permissions(self, *, account_reference: str) -> dict[str, Any]:
        raw = self._fetch("MARKET_PERMISSIONS", account_reference=account_reference)
        if raw.get("status") != "ADVISORY_READY":
            return raw
        return self._ready(
            "MARKET_PERMISSIONS",
            {
                "permissions": dict(raw["payload"].get("permissions") or {}),
                "broker_confirmed": bool(raw["payload"].get("permissions")),
                "provenance": "QUESTRADE_MARKET_PERMISSIONS",
            },
            raw,
        )

    def quotes(self, symbols: tuple[str, ...]) -> dict[str, Any]:
        raw = self._fetch("QUOTES", symbols=symbols)
        if raw.get("status") != "ADVISORY_READY":
            return raw
        return self._ready(
            "QUOTES",
            map_quotes(raw["payload"], generated_at=raw["acquisition_timestamp"]),
            raw,
        )

    def get_underlying_quote(self, symbol: str) -> dict[str, Any]:
        result = self.quotes((symbol,))
        rows = list(result.get("quotes") or [])
        return {
            **(rows[0] if rows else {}),
            **result,
            "status": result.get("status") or "MARKET_DATA_UNAVAILABLE",
            "provenance": "MARKET_DATA_PROVIDER",
        }

    def option_chain(self, symbol: str) -> dict[str, Any]:
        raw = self._fetch("OPTION_CHAINS", symbol=symbol)
        if raw.get("status") != "ADVISORY_READY":
            return raw
        return self._ready(
            "OPTION_CHAINS",
            map_option_chain(raw["payload"], generated_at=raw["acquisition_timestamp"]),
            raw,
        )

    def get_option_chain(self, underlying: str) -> dict[str, Any]:
        result = self.option_chain(underlying)
        return {
            **result,
            "status": result.get("status") or "OPTION_CHAIN_UNAVAILABLE",
            "provenance": "OPTION_CHAIN_PROVIDER",
        }

    def operational_summary(self) -> dict[str, Any]:
        lease = self.lease.health()
        return {
            "broker_health": "READY" if lease["status"] == "HEALTHY" else "BLOCKED",
            "oauth_status": "HANDLE_BOUND",
            "secret_lease_health": lease,
            "provider_health": "CONFIGURED"
            if not isinstance(self.provider, DisabledQuestradeEnterpriseDataProvider)
            else "PROVIDER_UNAVAILABLE",
            "holdings_readiness": "ADVISORY_ONLY",
            "market_data_readiness": "ADVISORY_ONLY",
            "options_readiness": "ADVISORY_ONLY",
            "advisory_readiness": "ADVISORY_ONLY",
            "execution_posture": "DISABLED",
            "execution_authority": "BLOCKED",
            "fail_closed": True,
            "execution_allowed": False,
        }

    def _fetch(self, dataset: str, **parameters: Any) -> dict[str, Any]:
        operation = str(dataset).upper()
        acquired = utc_now()
        if not self.capabilities.permits(operation):
            return self._failure(operation, "DATA_DEPENDENCY_BLOCKED", "CAPABILITY_NOT_ALLOWED", acquired)
        try:
            with self.lease.open(
                consumer=self.lease.metadata.consumer,
                capability="OAUTH_ACCESS_TOKEN",
            ) as authorization:
                payload = dict(
                    self.provider.fetch(
                        operation,
                        authorization=authorization,
                        parameters=parameters,
                    )
                    or {}
                )
        except PermissionError:
            return self._failure(operation, "DATA_DEPENDENCY_BLOCKED", "SECRET_LEASE_UNAVAILABLE", acquired)
        except Exception:
            return self._failure(operation, "PROVIDER_UNAVAILABLE", "QUESTRADE_PROVIDER_UNAVAILABLE", acquired)
        return {
            "dataset": operation,
            "status": "ADVISORY_READY",
            "payload": payload,
            "acquisition_timestamp": acquired,
            "provider_timestamp": payload.get("timestamp"),
            "provenance": f"QUESTRADE_{operation}",
            "plaintext_returned": False,
            "execution_allowed": False,
        }

    def _ready(self, dataset: str, payload: Mapping[str, Any], raw: Mapping[str, Any]) -> dict[str, Any]:
        return {
            **dict(payload),
            "dataset": dataset,
            "runtime_status": "ADVISORY_READY",
            "acquisition_timestamp": raw.get("acquisition_timestamp"),
            "provider_timestamp": raw.get("provider_timestamp"),
            "advisory_only": True,
            "plaintext_returned": False,
            "execution_allowed": False,
        }

    @staticmethod
    def _failure(dataset: str, status: str, reason: str, acquired: str) -> dict[str, Any]:
        return {
            "dataset": dataset,
            "status": status,
            "failure_reason": reason,
            "acquisition_timestamp": acquired,
            "provider_timestamp": None,
            "provenance": "QUESTRADE_RUNTIME",
            "fabricated": False,
            "advisory_only": True,
            "execution_allowed": False,
        }


__all__ = [
    "DisabledQuestradeEnterpriseDataProvider",
    "QUESTRADE_READ_ONLY_CAPABILITIES",
    "QuestradeEnterpriseDataProvider",
    "QuestradeEnterpriseReadOnlyRuntime",
]

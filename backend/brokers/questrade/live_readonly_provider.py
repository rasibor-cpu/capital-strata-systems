"""GET-only QuestradeEnterpriseDataProvider for LIVE READ-ONLY datasets."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from backend.brokers.questrade.errors import ConfigurationRequiredError, ProviderUnavailableError
from backend.brokers.questrade.readonly_client import QuestradeReadOnlyClient


_SUPPORTED_DATASETS = frozenset({"ACCOUNTS", "BALANCES", "POSITIONS"})


class QuestradeLiveReadOnlyDataProvider:
    """Map ACCOUNTS/BALANCES/POSITIONS onto the existing GET-only client."""

    execution_allowed = False
    live_trading_blocked = True
    broker_execution_armed = False
    advisory_only = True

    def __init__(
        self,
        client: QuestradeReadOnlyClient,
        *,
        account_reference: str | None = None,
    ) -> None:
        self._client = client
        self._account_reference = _normalize_account_reference(account_reference, required=False)

    def bind_account_reference(self, account_reference: str) -> None:
        self._account_reference = _normalize_account_reference(account_reference, required=True)

    def fetch(
        self,
        dataset: str,
        *,
        authorization: memoryview,
        parameters: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if authorization is None or len(authorization) == 0:
            raise ProviderUnavailableError("QUESTRADE_AUTHORIZATION_REQUIRED")
        operation = str(dataset or "").strip().upper()
        if operation not in _SUPPORTED_DATASETS:
            raise ProviderUnavailableError("QUESTRADE_DATASET_UNSUPPORTED")
        path = self._path_for(operation, parameters)
        result = self._client.request(path, method="GET")
        if not result.success:
            raise ProviderUnavailableError(result.failure_code or "QUESTRADE_PROVIDER_UNAVAILABLE")
        payload = dict(result.payload)
        payload.setdefault("acquisition_timestamp", datetime.now(timezone.utc).isoformat())
        return payload

    def _path_for(self, operation: str, parameters: Mapping[str, Any]) -> str:
        if operation == "ACCOUNTS":
            return "/accounts"
        reference = _normalize_account_reference(
            parameters.get("account_reference") or self._account_reference,
            required=True,
        )
        if operation == "BALANCES":
            return f"/accounts/{reference}/balances"
        return f"/accounts/{reference}/positions"

    def __repr__(self) -> str:
        return (
            "QuestradeLiveReadOnlyDataProvider("
            "datasets=('ACCOUNTS','BALANCES','POSITIONS'), "
            f"account_reference_bound={bool(self._account_reference)}, "
            "execution_allowed=False, secret_material_redacted=True)"
        )


def _normalize_account_reference(value: Any, *, required: bool) -> str | None:
    text = str(value or "").strip()
    if not text:
        if required:
            raise ConfigurationRequiredError("ACCOUNT_REFERENCE_REQUIRED")
        return None
    if any(token in text for token in ("/", "\\", "..", "://", "?", "#")):
        raise ConfigurationRequiredError("ACCOUNT_REFERENCE_REJECTED")
    return text


__all__ = ["QuestradeLiveReadOnlyDataProvider"]

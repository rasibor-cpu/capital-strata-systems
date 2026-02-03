"""
Config Drift Detection (Hash + Log)
REA Capital Trading Engine

Purpose:
- Compute a stable hash of "effective runtime config"
- Log CONFIG_HASH at startup
- Detect mid-run drift (warn or hard-block via toggle)

Design goals:
- No external dependencies
- Fail-safe: never crash engine unless explicitly configured to hard-block
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.app.observability.logger import get_logger, with_trace

log = get_logger("observability.config_drift")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stable_json(obj: Any) -> str:
    """
    Stable JSON encoding for hashing.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _env_pick(keys: list[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k in keys:
        v = os.getenv(k)
        if v is not None:
            out[k] = v
    return out


@dataclass(frozen=True)
class ConfigFingerprint:
    hash: str
    payload: Dict[str, Any]
    created_utc: datetime


class ConfigDriftGuard:
    """
    Holds an initial fingerprint and can check for drift later.
    """

    def __init__(
        self,
        env_keys: Optional[list[str]] = None,
        extra_payload: Optional[Dict[str, Any]] = None,
        hard_block_on_drift: bool = False,
    ) -> None:
        self.env_keys = env_keys or [
            # Runner + ops
            "LOG_LEVEL",
            "REA_COMMAND_TIMEOUT_SECONDS",
            "REA_ASSET_CLASS",
            "REA_ENGINE_ENTRYPOINT",
            "REA_ENGINE_TICKS",
            "REA_ENGINE_SLEEP_S",
            # Safety controls
            "REA_KILL_SWITCH",
        ]
        self.extra_payload = extra_payload or {}
        self.hard_block_on_drift = bool(hard_block_on_drift)

        self._initial: Optional[ConfigFingerprint] = None

    def build_payload(self) -> Dict[str, Any]:
        """
        Define the "effective config" you care about.
        Extend this safely over time.
        """
        payload: Dict[str, Any] = {
            "env": _env_pick(self.env_keys),
            "extra": self.extra_payload,
        }
        return payload

    def fingerprint(self) -> ConfigFingerprint:
        payload = self.build_payload()
        h = _sha256(_stable_json(payload))
        return ConfigFingerprint(hash=h, payload=payload, created_utc=_utc_now())

    def init_and_log(self) -> ConfigFingerprint:
        """
        Capture and log the initial fingerprint.
        """
        fp = self.fingerprint()
        self._initial = fp

        adapter = with_trace(log, "CONFIG")
        adapter.info("CONFIG_HASH | %s", fp.hash)
        return fp

    def check_drift(self) -> bool:
        """
        Returns True if drift detected.
        """
        if self._initial is None:
            # If not initialized, treat as drift to be safe.
            return True

        current = self.fingerprint()
        return current.hash != self._initial.hash

    def enforce(self) -> bool:
        """
        Drift enforcement hook.
        - Logs warning if drift detected.
        - If hard_block_on_drift=True, returns False (block).
        - Else returns True (allow) but logs AMBER.

        This function does NOT raise exceptions.
        """
        adapter = with_trace(log, "CONFIG")

        if self._initial is None:
            adapter.warning("CONFIG_DRIFT | state=AMBER | reason=guard_not_initialized")
            return not self.hard_block_on_drift

        current = self.fingerprint()
        if current.hash == self._initial.hash:
            return True

        adapter.warning(
            "CONFIG_DRIFT | state=AMBER | initial=%s | current=%s",
            self._initial.hash,
            current.hash,
        )

        if self.hard_block_on_drift:
            adapter.critical("CONFIG_DRIFT_BLOCK | state=RED | hard_block_on_drift=true")
            return False

        return True


# Singleton guard (default: warn only)
DEFAULT_CONFIG_GUARD = ConfigDriftGuard(
    hard_block_on_drift=bool(os.getenv("REA_HARD_BLOCK_ON_CONFIG_DRIFT") in {"1", "true", "TRUE", "yes", "YES"})
)

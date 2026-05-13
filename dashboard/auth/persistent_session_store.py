from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional


class PersistentSessionStore:
    """
    Restart-safe local session store.

    Cookie/session tokens are never written in clear text. The persisted key is a
    SHA-256 token hash, while the in-memory mobile layer can continue using the
    raw cookie token for normal request lookup.
    """

    def __init__(self, path: str | Path, *, max_age_seconds: int) -> None:
        self.path = Path(path)
        self.max_age_seconds = int(max_age_seconds)

    def save(self, token: str, session: Dict[str, Any]) -> None:
        sessions = self._load_all()
        sessions[self._hash_token(token)] = self._json_safe(session)
        self._write_all(self._purge_expired(sessions))

    def get(self, token: str) -> Optional[Dict[str, Any]]:
        sessions = self._purge_expired(self._load_all())
        record = sessions.get(self._hash_token(token))
        if not isinstance(record, dict):
            self._write_all(sessions)
            return None
        self._write_all(sessions)
        return dict(record)

    def touch(self, token: str, *, now: float | None = None) -> Optional[Dict[str, Any]]:
        sessions = self._purge_expired(self._load_all())
        key = self._hash_token(token)
        record = sessions.get(key)
        if not isinstance(record, dict):
            self._write_all(sessions)
            return None
        record["last_activity"] = float(now if now is not None else time.time())
        sessions[key] = record
        self._write_all(sessions)
        return dict(record)

    def revoke(self, token: str) -> None:
        sessions = self._load_all()
        sessions.pop(self._hash_token(token), None)
        self._write_all(sessions)

    def purge_expired(self) -> int:
        sessions = self._load_all()
        purged = len(sessions)
        active = self._purge_expired(sessions)
        purged -= len(active)
        self._write_all(active)
        return purged

    def _load_all(self) -> Dict[str, Dict[str, Any]]:
        try:
            raw = self.path.read_text(encoding="utf-8").strip()
            data = json.loads(raw) if raw else {}
        except FileNotFoundError:
            return {}
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        return {
            str(key): value
            for key, value in data.items()
            if isinstance(value, dict)
        }

    def _write_all(self, sessions: Dict[str, Dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(sessions, indent=2, sort_keys=True), encoding="utf-8")

    def _purge_expired(self, sessions: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        now = time.time()
        active: Dict[str, Dict[str, Any]] = {}
        for key, record in sessions.items():
            created = self._safe_float(record.get("created"), now)
            if now - created <= self.max_age_seconds:
                active[key] = record
        return active

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(str(token).encode("utf-8")).hexdigest()

    @staticmethod
    def _safe_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        if isinstance(value, tuple):
            return [self._json_safe(item) for item in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

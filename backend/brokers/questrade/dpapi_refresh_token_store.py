"""Windows DPAPI refresh-token store for Questrade LIVE READ-ONLY activation.

Persists only the rotated refresh token. Access tokens stay memory-only.
Never falls back to environment plaintext credentials.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Protocol

from backend.brokers.questrade.errors import ConfigurationRequiredError, TokenStoreError
from backend.brokers.questrade.token_lifecycle import QuestradeTokenBundle


class DpapiProtectBackend(Protocol):
    def encrypt(self, plaintext: str) -> bytes: ...

    def decrypt(self, ciphertext: bytes) -> str: ...


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _repository_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists():
            return parent
    return None


class WindowsDpapiRefreshTokenStore:
    """Explicit-path Windows DPAPI store. Fail-closed without an injected backend off Windows."""

    def __init__(
        self,
        path: str | Path,
        *,
        protect_backend: DpapiProtectBackend | None = None,
        now: datetime | None = None,
    ) -> None:
        self._path = _require_external_absolute_path(path)
        self._now = now
        if protect_backend is not None:
            self._backend = protect_backend
        elif sys.platform == "win32":
            self._backend = WindowsPowerShellDpapiBackend()
        else:
            raise TokenStoreError("WINDOWS_DPAPI_REQUIRED", code="WINDOWS_DPAPI_REQUIRED")
        self._last_rotation: datetime | None = None

    def load(self) -> str:
        if not self._path.exists():
            raise TokenStoreError("QUESTRADE_TOKEN_FILE_MISSING", code="QUESTRADE_TOKEN_FILE_MISSING")
        try:
            ciphertext = self._path.read_bytes()
        except OSError as exc:
            raise TokenStoreError("QUESTRADE_TOKEN_STORE_UNREADABLE", code="QUESTRADE_TOKEN_STORE_UNREADABLE") from exc
        if not ciphertext.strip():
            raise TokenStoreError("QUESTRADE_TOKEN_FILE_MISSING", code="QUESTRADE_TOKEN_FILE_MISSING")
        try:
            token = self._backend.decrypt(ciphertext)
        except TokenStoreError:
            raise
        except Exception as exc:
            raise TokenStoreError(
                "QUESTRADE_TOKEN_DECRYPTION_FAILED",
                code="QUESTRADE_TOKEN_DECRYPTION_FAILED",
            ) from exc
        if not str(token or "").strip():
            raise TokenStoreError(
                "QUESTRADE_TOKEN_DECRYPTION_FAILED",
                code="QUESTRADE_TOKEN_DECRYPTION_FAILED",
            )
        return str(token)

    def load_refresh_token(self) -> str:
        return self.load()

    def replace(self, bundle: QuestradeTokenBundle) -> None:
        token = str(getattr(bundle, "refresh_token", "") or "")
        if not token.strip():
            raise TokenStoreError("QUESTRADE_REFRESH_TOKEN_MISSING", code="QUESTRADE_REFRESH_TOKEN_MISSING")
        try:
            ciphertext = self._backend.encrypt(token)
        except TokenStoreError:
            raise
        except Exception as exc:
            raise TokenStoreError("QUESTRADE_TOKEN_ENCRYPT_FAILED", code="QUESTRADE_TOKEN_ENCRYPT_FAILED") from exc
        if not ciphertext:
            raise TokenStoreError("QUESTRADE_TOKEN_ENCRYPT_FAILED", code="QUESTRADE_TOKEN_ENCRYPT_FAILED")
        self._atomic_replace(ciphertext)
        self._last_rotation = self._now or _utc_now()

    def save_refresh_token(self, token: str) -> None:
        if not str(token or "").strip():
            raise TokenStoreError("QUESTRADE_REFRESH_TOKEN_MISSING", code="QUESTRADE_REFRESH_TOKEN_MISSING")
        try:
            ciphertext = self._backend.encrypt(str(token))
        except TokenStoreError:
            raise
        except Exception as exc:
            raise TokenStoreError("QUESTRADE_TOKEN_ENCRYPT_FAILED", code="QUESTRADE_TOKEN_ENCRYPT_FAILED") from exc
        if not ciphertext:
            raise TokenStoreError("QUESTRADE_TOKEN_ENCRYPT_FAILED", code="QUESTRADE_TOKEN_ENCRYPT_FAILED")
        self._atomic_replace(ciphertext)
        self._last_rotation = self._now or _utc_now()

    def clear(self) -> None:
        raise TokenStoreError("QUESTRADE_TOKEN_CLEAR_DISABLED", code="QUESTRADE_TOKEN_CLEAR_DISABLED")

    def metadata(self) -> dict[str, Any]:
        return {
            "token_present": self._path.exists() and self._path.stat().st_size > 0,
            "provider": "WINDOWS_DPAPI",
            "path_reference": str(self._path),
            "last_rotation_timestamp": self._last_rotation.isoformat() if self._last_rotation else None,
            "token_values_returned": False,
        }

    def _atomic_replace(self, ciphertext: bytes) -> None:
        tmp = self._path.with_name(self._path.name + ".tmp")
        try:
            fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(ciphertext)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self._path)
        except TokenStoreError:
            raise
        except Exception as exc:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise TokenStoreError("QUESTRADE_TOKEN_REPLACE_FAILED", code="QUESTRADE_TOKEN_REPLACE_FAILED") from exc

    def __repr__(self) -> str:
        return (
            "WindowsDpapiRefreshTokenStore("
            f"token_present={self._path.exists()}, "
            "provider='WINDOWS_DPAPI', "
            "secret_material_redacted=True)"
        )


class WindowsPowerShellDpapiBackend:
    """Decrypt/encrypt ConvertFrom-SecureString ciphertext for the current Windows user."""

    def encrypt(self, plaintext: str) -> bytes:
        if sys.platform != "win32":
            raise TokenStoreError("WINDOWS_DPAPI_REQUIRED", code="WINDOWS_DPAPI_REQUIRED")
        return _powershell_protect(plaintext)

    def decrypt(self, ciphertext: bytes) -> str:
        if sys.platform != "win32":
            raise TokenStoreError("WINDOWS_DPAPI_REQUIRED", code="WINDOWS_DPAPI_REQUIRED")
        return _powershell_unprotect(ciphertext)


def _require_external_absolute_path(path: str | Path) -> Path:
    raw = Path(path)
    if not raw.is_absolute():
        raise ConfigurationRequiredError("QUESTRADE_TOKEN_PATH_NOT_ABSOLUTE")
    resolved = raw.expanduser().resolve()
    repo = _repository_root()
    if repo is not None and (resolved == repo or repo in resolved.parents):
        raise ConfigurationRequiredError("REPOSITORY_SECRET_STORAGE_REJECTED")
    return resolved


def _powershell_protect(plaintext: str) -> bytes:
    env = os.environ.copy()
    env["CSS_QT_DPAPI_PLAINTEXT"] = plaintext
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                (
                    "$ErrorActionPreference='Stop'; "
                    "$secure=ConvertTo-SecureString -String $env:CSS_QT_DPAPI_PLAINTEXT -AsPlainText -Force; "
                    "ConvertFrom-SecureString -SecureString $secure"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
            check=False,
        )
    except Exception as exc:
        raise TokenStoreError("QUESTRADE_TOKEN_ENCRYPT_FAILED", code="QUESTRADE_TOKEN_ENCRYPT_FAILED") from exc
    finally:
        env.pop("CSS_QT_DPAPI_PLAINTEXT", None)
    if completed.returncode != 0 or not str(completed.stdout or "").strip():
        raise TokenStoreError("QUESTRADE_TOKEN_ENCRYPT_FAILED", code="QUESTRADE_TOKEN_ENCRYPT_FAILED")
    return completed.stdout.strip().encode("utf-8")


def _powershell_unprotect(ciphertext: bytes) -> str:
    env = os.environ.copy()
    env["CSS_QT_DPAPI_CIPHERTEXT"] = ciphertext.decode("utf-8", errors="strict")
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                (
                    "$ErrorActionPreference='Stop'; "
                    "$secure=ConvertTo-SecureString -String $env:CSS_QT_DPAPI_CIPHERTEXT; "
                    "$bstr=[System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure); "
                    "try { [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr) } "
                    "finally { [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
            check=False,
        )
    except Exception as exc:
        raise TokenStoreError(
            "QUESTRADE_TOKEN_DECRYPTION_FAILED",
            code="QUESTRADE_TOKEN_DECRYPTION_FAILED",
        ) from exc
    finally:
        env.pop("CSS_QT_DPAPI_CIPHERTEXT", None)
    if completed.returncode != 0 or not str(completed.stdout or "").strip():
        raise TokenStoreError(
            "QUESTRADE_TOKEN_DECRYPTION_FAILED",
            code="QUESTRADE_TOKEN_DECRYPTION_FAILED",
        )
    return completed.stdout.strip()


__all__ = [
    "DpapiProtectBackend",
    "WindowsDpapiRefreshTokenStore",
    "WindowsPowerShellDpapiBackend",
]

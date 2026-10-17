"""Authenticated consent records (Grok audit A-M2).

The consent ledger is a SHA-256 chain: tamper-EVIDENT against accidents, but anyone who can write
the run directory can rewrite a record, recompute the chain and repoint the active settings. This
module adds what a hash chain cannot give: authentication with a key the run directory never holds.

  * Signing keys are Ed25519 (the same primitive and checkpoint format as ledger_anchor.py). The
    private seed is protected with Windows DPAPI in the CURRENT USER's scope and stored in a key
    directory OUTSIDE every simulation root (default %LOCALAPPDATA%\\CapitalStrata\\consent-signing).
    The key store refuses a directory that is inside, equal to, or contains the run root.
  * Explicit account binding: each key records the Windows account (DOMAIN\\user) and machine it
    was created for, and the same identity is DPAPI "entropy", so the seed only decrypts for that
    account. A mismatch fails closed (consent_key_account_mismatch).
  * Every ledger entry carries an Ed25519 signature over its entry_hash; the active acceptance
    pointer (record hash, policy hash, run binding) is a separate signed file.
  * After every append, a ledger_anchor checkpoint over the consent ledger is signed and its
    statement is written to the key directory (outside the run): truncation, rollback or a
    rewritten prefix of the ledger is detected against that external statement.
  * Rotation: a new ACTIVE key; the previous one becomes RETIRED (still verifies what it signed,
    never signs again). Revocation: REVOKED keys verify nothing, so everything they signed needs a
    fresh acceptance. Only public keys are exportable (backup of the verification registry); the
    private seed is intentionally not exportable - losing it means rotate and re-accept.
  * Nothing here logs, returns or reprs key material.
"""
from __future__ import annotations

import base64
import ctypes
import getpass
import hashlib
import json
import os
import platform
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from backend.runtime.interprocess_lock import exclusive_file_lock
from backend.trading_profiles import ledger_anchor
from backend.trading_profiles.ledger_anchor import LedgerAnchor, _canonical, _head, _lines, _prefix, public_key_b64

REGISTRY_SCHEMA = "css.consent_signing.registry.v1"
POINTER_SCHEMA = "css.consent_signing.active_pointer.v1"
KEY_DIR_ENV = "CSS_CONSENT_KEY_DIR"  # optional override of the key directory (still DPAPI-protected)
ACTIVE, RETIRED, REVOKED = "ACTIVE", "RETIRED", "REVOKED"
ENTRY_CONTEXT = b"css-consent-entry-v1|"
POINTER_CONTEXT = b"css-consent-active-pointer-v1|"
POINTER_FILE = "consent_active_pointer.json"
CHECKPOINT_FILE = "consent_anchor_checkpoints.jsonl"
CONSENT_LEDGER_FILE = "consent_ledger.jsonl"


class ConsentSigningError(RuntimeError):
    """Signing or verification failure; the message is a stable reason code (never key material)."""


class ProtectBackend(Protocol):
    def protect(self, data: bytes, entropy: bytes) -> bytes: ...

    def unprotect(self, blob: bytes, entropy: bytes) -> bytes: ...


# --------------------------------------------------------------------------- Windows DPAPI
class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> tuple[_DataBlob, Any]:
    buf = ctypes.create_string_buffer(data, len(data))
    return _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


class WindowsDpapiBackend:
    """CryptProtectData / CryptUnprotectData in the current user's scope (no LOCAL_MACHINE flag),
    with no UI. Called in-process through ctypes: the secret never crosses a process boundary."""

    CRYPTPROTECT_UI_FORBIDDEN = 0x1

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise ConsentSigningError("consent_key_store_requires_windows_dpapi")

    def _call(self, fn_name: str, data: bytes, entropy: bytes) -> bytes:
        crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        data_in, _keep1 = _blob(data)
        ent, _keep2 = _blob(entropy)
        out = _DataBlob()
        fn = getattr(crypt32, fn_name)
        if fn_name == "CryptProtectData":
            ok = fn(ctypes.byref(data_in), "css-consent-signing", ctypes.byref(ent), None, None,
                    self.CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out))
        else:
            ok = fn(ctypes.byref(data_in), None, ctypes.byref(ent), None, None,
                    self.CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out))
        if not ok:
            raise ConsentSigningError("consent_key_dpapi_failed")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            kernel32.LocalFree(out.pbData)

    def protect(self, data: bytes, entropy: bytes) -> bytes:
        return self._call("CryptProtectData", data, entropy)

    def unprotect(self, blob: bytes, entropy: bytes) -> bytes:
        return self._call("CryptUnprotectData", blob, entropy)


def current_account() -> str:
    domain = os.environ.get("USERDOMAIN", "") if sys.platform == "win32" else ""
    user = getpass.getuser()
    return f"{domain}\\{user}" if domain else user


def current_machine() -> str:
    return platform.node()


def default_consent_key_store() -> "ConsentKeyStore":
    """The operator's key store: DPAPI per-user, in the user's local profile (never a run root).
    Fails closed where DPAPI is unavailable."""
    if sys.platform != "win32":
        raise ConsentSigningError("consent_key_store_requires_windows_dpapi")
    override = os.environ.get(KEY_DIR_ENV, "").strip()
    if override:
        directory = Path(override)
    else:
        base = os.environ.get("LOCALAPPDATA", "").strip()
        if not base:
            raise ConsentSigningError("consent_key_store_location_unavailable")
        directory = Path(base) / "CapitalStrata" / "consent-signing"
    return ConsentKeyStore(directory, backend=WindowsDpapiBackend())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _overlaps(a: Path, b: Path) -> bool:
    a, b = Path(os.path.normcase(str(a.resolve()))), Path(os.path.normcase(str(b.resolve())))
    return a == b or a in b.parents or b in a.parents


# --------------------------------------------------------------------------- key store
class ConsentKeyStore:
    def __init__(self, directory: Path | str, *, backend: ProtectBackend, account: str | None = None,
                 machine: str | None = None, clock: Callable[[], datetime] = _now) -> None:
        directory = Path(directory)
        if not directory.is_absolute():
            raise ConsentSigningError("consent_key_dir_not_absolute")
        self.directory = directory
        self.backend = backend
        self.account = account if account is not None else current_account()
        self.machine = machine if machine is not None else current_machine()
        self.clock = clock
        self.registry_path = directory / "registry.json"
        self.lock_path = directory / "registry.lock"
        self._cache: dict[str, Ed25519PrivateKey] = {}

    def __repr__(self) -> str:
        return f"ConsentKeyStore(directory={str(self.directory)!r}, key_material_redacted=True)"

    # -- placement -----------------------------------------------------------------
    def ensure_outside(self, run_root: Path | str) -> None:
        """Signing keys and statements must never live in (or contain) a simulation root."""
        root = Path(run_root)
        root.mkdir(parents=True, exist_ok=True)
        self.directory.mkdir(parents=True, exist_ok=True)
        if _overlaps(self.directory, root):
            raise ConsentSigningError("consent_key_dir_overlaps_run_root")

    # -- registry --------------------------------------------------------------------
    def _registry(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return {"schema": REGISTRY_SCHEMA, "keys": []}
        try:
            reg = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ConsentSigningError("consent_key_registry_unreadable") from None
        if reg.get("schema") != REGISTRY_SCHEMA or not isinstance(reg.get("keys"), list):
            raise ConsentSigningError("consent_key_registry_invalid")
        return reg

    def _save_registry(self, reg: Mapping[str, Any]) -> None:
        _atomic_write(self.registry_path, json.dumps(reg, indent=2, sort_keys=True).encode("utf-8"))

    def _entropy(self, key_id: str) -> bytes:
        return f"css-consent-signing-v1|{key_id}|{self.account}|{self.machine}".encode("utf-8")

    def _blob_path(self, key_id: str) -> Path:
        return self.directory / f"{key_id}.ed25519.dpapi"

    def _new_key(self, reg: dict[str, Any]) -> str:
        key = Ed25519PrivateKey.generate()
        seed = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        pub = public_key_b64(key)
        key_id = ledger_anchor.fingerprint(pub)
        _atomic_write(self._blob_path(key_id), self.backend.protect(seed, self._entropy(key_id)))
        reg["keys"].append({"key_id": key_id, "public_b64": pub, "status": ACTIVE, "account": self.account,
                            "machine": self.machine, "created_utc": self.clock().isoformat()})
        self._cache[key_id] = key
        return key_id

    def _entry(self, reg: Mapping[str, Any], key_id: str) -> dict[str, Any] | None:
        return next((k for k in reg["keys"] if k.get("key_id") == key_id), None)

    def signing_key(self) -> tuple[str, Ed25519PrivateKey]:
        """The ACTIVE key (created on first use), after checking the account binding."""
        self.directory.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path, timeout_seconds=10.0):
            reg = self._registry()
            active = [k for k in reg["keys"] if k.get("status") == ACTIVE]
            if len(active) > 1:
                raise ConsentSigningError("consent_key_registry_multiple_active")
            if not active:
                key_id = self._new_key(reg)
                self._save_registry(reg)
                return key_id, self._cache[key_id]
            entry = active[0]
        key_id = entry["key_id"]
        if entry.get("account") != self.account or entry.get("machine") != self.machine:
            raise ConsentSigningError("consent_key_account_mismatch")
        if key_id not in self._cache:
            try:
                seed = self.backend.unprotect(self._blob_path(key_id).read_bytes(), self._entropy(key_id))
                key = Ed25519PrivateKey.from_private_bytes(seed)
            except ConsentSigningError:
                raise
            except Exception:
                raise ConsentSigningError("consent_key_unavailable") from None
            if public_key_b64(key) != entry.get("public_b64"):
                raise ConsentSigningError("consent_key_does_not_match_registry")
            self._cache[key_id] = key
        return key_id, self._cache[key_id]

    def public_key(self, key_id: str) -> Ed25519PublicKey | None:
        """Public key for verification; None for unknown or REVOKED keys."""
        entry = self._entry(self._registry(), key_id)
        if entry is None or entry.get("status") not in (ACTIVE, RETIRED):
            return None
        try:
            return Ed25519PublicKey.from_public_bytes(base64.b64decode(entry["public_b64"]))
        except Exception:
            return None

    def rotate(self, *, reason: str = "scheduled_rotation") -> str:
        """New ACTIVE key; the previous ACTIVE key becomes RETIRED (verifies, never signs)."""
        self.directory.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path, timeout_seconds=10.0):
            reg = self._registry()
            for k in reg["keys"]:
                if k.get("status") == ACTIVE:
                    k.update(status=RETIRED, retired_utc=self.clock().isoformat(), retired_reason=str(reason)[:120])
            key_id = self._new_key(reg)
            self._save_registry(reg)
        return key_id

    def revoke(self, key_id: str, *, reason: str) -> None:
        """Compromise response: the key verifies nothing any more; its acceptances must be redone."""
        with exclusive_file_lock(self.lock_path, timeout_seconds=10.0):
            reg = self._registry()
            entry = self._entry(reg, key_id)
            if entry is None:
                raise ConsentSigningError("consent_key_unknown")
            entry.update(status=REVOKED, revoked_utc=self.clock().isoformat(), revoked_reason=str(reason)[:120])
            self._save_registry(reg)
            self._cache.pop(key_id, None)
            try:
                self._blob_path(key_id).unlink()  # the protected seed is destroyed, not just disabled
            except OSError:
                pass

    def public_registry(self) -> dict[str, Any]:
        """Backup / evidence export: public keys and their history only (no private material)."""
        reg = self._registry()
        return {"schema": REGISTRY_SCHEMA + ".public",
                "keys": [{k: v for k, v in e.items()} for e in reg["keys"]]}

    # -- external anchor statements -------------------------------------------------
    def _statement_path(self, anchor_id: str) -> Path:
        return self.directory / "anchors" / f"{anchor_id}.json"

    def save_statement(self, anchor_id: str, statement: Mapping[str, Any]) -> None:
        _atomic_write(self._statement_path(anchor_id), json.dumps(statement, sort_keys=True).encode("utf-8"))

    def load_statement(self, anchor_id: str) -> dict[str, Any] | None:
        path = self._statement_path(anchor_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ConsentSigningError("consent_anchor_statement_unreadable") from None


# --------------------------------------------------------------------------- per-root integrity
def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


class ConsentIntegrity:
    """Signs and verifies one consent root's ledger entries, active pointer and anchor checkpoints."""

    def __init__(self, store: ConsentKeyStore, root: Path | str) -> None:
        self.store = store
        self.root = Path(root)
        store.ensure_outside(self.root)
        location = os.path.normcase(str(self.root.resolve()))
        self.anchor_id = hashlib.sha256(location.encode("utf-8")).hexdigest()
        self.pointer_path = self.root / POINTER_FILE

    def __repr__(self) -> str:
        return f"ConsentIntegrity(root={str(self.root)!r}, key_material_redacted=True)"

    # -- entries -----------------------------------------------------------------------
    def sign_entry(self, entry_hash: str) -> dict[str, str]:
        key_id, key = self.store.signing_key()
        return {"key_id": key_id, "sig_b64": _b64(key.sign(ENTRY_CONTEXT + entry_hash.encode("ascii")))}

    def _verify(self, key_id: Any, message: bytes, sig_b64: Any) -> bool:
        pub = self.store.public_key(str(key_id or ""))
        if pub is None:
            return False
        try:
            pub.verify(base64.b64decode(str(sig_b64 or "")), message)
            return True
        except (InvalidSignature, ValueError, TypeError):
            return False

    def verify_entry(self, record: Mapping[str, Any]) -> bool:
        sig = record.get("signature")
        if not isinstance(sig, Mapping):
            return False
        return self._verify(sig.get("key_id"), ENTRY_CONTEXT + str(record.get("entry_hash", "")).encode("ascii"),
                            sig.get("sig_b64"))

    # -- active pointer ----------------------------------------------------------------
    @staticmethod
    def _pointer_body(user_id: str, record_hash: str, policy_hash: str, run_binding: str | None,
                      activated_at_utc: str) -> dict[str, Any]:
        return {"schema": POINTER_SCHEMA, "user_id": user_id, "consent_record_hash": record_hash,
                "policy_hash": policy_hash, "run_binding": run_binding, "activated_at_utc": activated_at_utc}

    def write_pointer(self, user_id: str, *, record_hash: str, policy_hash: str, run_binding: str | None,
                      activated_at_utc: str) -> None:
        body = self._pointer_body(user_id, record_hash, policy_hash, run_binding, activated_at_utc)
        key_id, key = self.store.signing_key()
        signed = {"body": body, "key_id": key_id, "sig_b64": _b64(key.sign(POINTER_CONTEXT + _canonical(body)))}
        try:
            current = json.loads(self.pointer_path.read_text(encoding="utf-8")) if self.pointer_path.exists() else {}
        except (OSError, ValueError):
            current = {}
        users = dict(current.get("users") or {})
        users[user_id] = signed
        _atomic_write(self.pointer_path, json.dumps({"users": users}, indent=2, sort_keys=True).encode("utf-8"))

    def verify_pointer(self, user_id: str, *, record: Mapping[str, Any], policy_hash: str) -> str | None:
        try:
            signed = json.loads(self.pointer_path.read_text(encoding="utf-8"))["users"][user_id]
            body = signed["body"]
        except (OSError, ValueError, KeyError, TypeError):
            return "consent_active_pointer_missing"
        if not self._verify(signed.get("key_id"), POINTER_CONTEXT + _canonical(body), signed.get("sig_b64")):
            return "consent_active_pointer_signature_invalid"
        if (body.get("user_id") != user_id or body.get("consent_record_hash") != record.get("entry_hash")
                or body.get("policy_hash") != policy_hash or body.get("run_binding") != record.get("run_binding")):
            return "consent_active_pointer_mismatch"
        return None

    # -- external anchoring (ledger_anchor checkpoints, statement kept outside the root) --
    def _anchor(self, key: Ed25519PrivateKey) -> LedgerAnchor:
        anchor = LedgerAnchor(self.root, ledgers={"consent": CONSENT_LEDGER_FILE}, key_provider=lambda: key)
        anchor.path = self.root / CHECKPOINT_FILE
        anchor.lock_path = self.root / "consent_anchor.lock"
        return anchor

    def anchor(self, *, now: datetime | None = None) -> dict[str, Any]:
        _key_id, key = self.store.signing_key()
        statement = self._anchor(key).checkpoint(now=now)
        self.store.save_statement(self.anchor_id, statement)
        return statement

    def verify_anchor(self, *, record_hash: str) -> str | None:
        """Checkpoints signed by known, unrevoked keys and chained; the latest equals the external
        statement; the consent ledger still starts with exactly the anchored prefix; and the
        active record lies inside it."""
        statement = self.store.load_statement(self.anchor_id)
        if statement is None:
            return "consent_anchor_statement_missing"
        try:
            records = [json.loads(ln) for ln in _lines(self.root / CHECKPOINT_FILE)]
        except ValueError:
            return "consent_anchor_log_unparseable"
        if not records:
            return "consent_anchor_log_missing"
        # Every checkpoint's digest and linkage is checked; the LATEST must be signed by a known,
        # unrevoked key. Through prev_checkpoint_sha256 it commits to every earlier checkpoint, so
        # history signed by a key that was later retired or revoked stays covered after rotation.
        prev_digest, prev_seq = ledger_anchor.GENESIS, 0
        for rec in records:
            body = rec.get("body") or {}
            try:
                digest = hashlib.sha256(_canonical(body)).hexdigest()
            except (TypeError, ValueError):
                return "consent_anchor_digest_mismatch"
            if digest != rec.get("checkpoint_sha256"):
                return "consent_anchor_digest_mismatch"
            if body.get("seq") != prev_seq + 1 or body.get("prev_checkpoint_sha256") != prev_digest:
                return "consent_anchor_chain_broken"
            prev_digest, prev_seq = digest, body["seq"]
        latest = records[-1]
        pub = self.store.public_key(str(latest["body"].get("anchor_key_fingerprint") or ""))
        if pub is None:
            return "consent_anchor_key_unknown_or_revoked"
        try:
            pub.verify(base64.b64decode(latest.get("signature_b64") or ""), _canonical(latest["body"]))
        except (InvalidSignature, ValueError, TypeError):
            return "consent_anchor_signature_invalid"
        if statement.get("seq") != latest["body"]["seq"] or statement.get("checkpoint_sha256") != latest["checkpoint_sha256"]:
            return "consent_anchor_rolled_back_or_diverged"
        entry = latest["body"]["ledgers"].get("consent") or {}
        lines = _lines(self.root / CONSENT_LEDGER_FILE)
        count = int(entry.get("lines", -1))
        if count < 0 or len(lines) < count:
            return "consent_ledger_truncated"
        if _prefix(lines, count) != entry.get("prefix_sha256") or _head(lines, count) != entry.get("head_entry_hash"):
            return "consent_ledger_anchored_prefix_modified"
        anchored = {json.loads(ln).get("entry_hash") for ln in lines[:count]}
        if record_hash not in anchored:
            return "consent_record_not_anchored"
        return None


__all__ = [
    "ACTIVE", "RETIRED", "REVOKED", "ConsentIntegrity", "ConsentKeyStore", "ConsentSigningError",
    "ProtectBackend", "WindowsDpapiBackend", "current_account", "current_machine", "default_consent_key_store",
]

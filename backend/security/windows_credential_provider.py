"""Windows Credential Manager (DPAPI) signing-key provider for pilot dual control.

The approved production secret interface (owner decision 2026-10-07). Each
approver's Ed25519 signing seed is stored as a *generic credential* in that
approver's own Windows Credential Manager, which Windows encrypts with DPAPI
under the user's logon credentials. Persistence is LOCAL_MACHINE (the secret
does not roam with the profile).

Guarantees:
- no key material is ever written to the repository, ``.env``, files, logs,
  manifests or evidence: ``enroll`` returns only the PUBLIC key, and ``repr``
  never includes material;
- off Windows, without an explicitly injected backend, it fails closed;
- ``enroll`` refuses to overwrite an existing credential (rotation = new key_id).

This module is a tool for a human approver on their own machine. It does not
provision anything by itself, and nothing in CSS calls ``enroll`` automatically.
"""
from __future__ import annotations

import re
import sys
from typing import Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from backend.runtime.pilot_dual_control import SEED_BYTES, public_key_hex_from_seed

TARGET_PREFIX = "CSS/PilotApproval/"
_KEY_ID = re.compile(r"^[A-Za-z0-9._:\-]{1,64}$")


class PilotSecretUnavailable(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class CredentialBackend(Protocol):
    def read(self, target: str) -> bytes | None: ...

    def write_new(self, target: str, blob: bytes, comment: str) -> None: ...


class WindowsCredentialManagerBackend:
    """ctypes binding to advapi32 CredReadW / CredWriteW (CRED_TYPE_GENERIC)."""

    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2
    ERROR_NOT_FOUND = 1168

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise PilotSecretUnavailable("WINDOWS_CREDENTIAL_MANAGER_REQUIRED")
        import ctypes
        from ctypes import wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR), ("LastWritten", FILETIME),
                ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR),
            ]

        self._ctypes = ctypes
        self._CREDENTIAL = CREDENTIAL
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self._read = advapi32.CredReadW
        self._read.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                               ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
        self._read.restype = wintypes.BOOL
        self._write = advapi32.CredWriteW
        self._write.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
        self._write.restype = wintypes.BOOL
        self._free = advapi32.CredFree
        self._free.argtypes = [ctypes.c_void_p]

    def read(self, target: str) -> bytes | None:
        ctypes = self._ctypes
        pcred = ctypes.POINTER(self._CREDENTIAL)()
        if not self._read(target, self.CRED_TYPE_GENERIC, 0, ctypes.byref(pcred)):
            if ctypes.get_last_error() == self.ERROR_NOT_FOUND:
                return None
            raise PilotSecretUnavailable("WINDOWS_CREDENTIAL_READ_FAILED")
        try:
            cred = pcred.contents
            return ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
        finally:
            self._free(pcred)

    def write_new(self, target: str, blob: bytes, comment: str) -> None:
        if self.read(target) is not None:
            raise PilotSecretUnavailable("PILOT_KEY_ALREADY_ENROLLED")
        ctypes = self._ctypes
        buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        cred = self._CREDENTIAL()
        cred.Type = self.CRED_TYPE_GENERIC
        cred.TargetName = target
        cred.Comment = comment
        cred.CredentialBlobSize = len(blob)
        cred.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
        cred.Persist = self.CRED_PERSIST_LOCAL_MACHINE
        try:
            if not self._write(ctypes.byref(cred), 0):
                raise PilotSecretUnavailable("WINDOWS_CREDENTIAL_WRITE_FAILED")
        finally:
            ctypes.memset(buffer, 0, len(blob))


class WindowsCredentialSigningKeyProvider:
    """``PilotSigningKeyProvider`` backed by Windows Credential Manager (DPAPI)."""

    def __init__(self, *, backend: CredentialBackend | None = None) -> None:
        self._backend = backend if backend is not None else WindowsCredentialManagerBackend()

    @staticmethod
    def target_for(key_id: str) -> str:
        if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
            raise PilotSecretUnavailable("PILOT_KEY_ID_INVALID")
        return TARGET_PREFIX + key_id

    def get_signing_seed(self, key_id: str) -> bytes:
        try:
            blob = self._backend.read(self.target_for(key_id))
        except PilotSecretUnavailable:
            raise
        except Exception as exc:
            raise PilotSecretUnavailable("WINDOWS_CREDENTIAL_READ_FAILED") from exc
        if blob is None:
            raise PilotSecretUnavailable("PILOT_KEY_NOT_ENROLLED")
        if len(blob) != SEED_BYTES:
            raise PilotSecretUnavailable("PILOT_KEY_MALFORMED")
        return bytes(blob)

    def enroll(self, key_id: str) -> str:
        """Generate a new key inside this user's Credential Manager; return ONLY the public key hex."""
        target = self.target_for(key_id)
        seed = Ed25519PrivateKey.generate().private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        self._backend.write_new(target, seed, "CSS pilot approval signing key (Ed25519). Do not export.")
        return public_key_hex_from_seed(seed)

    def __repr__(self) -> str:
        return f"WindowsCredentialSigningKeyProvider(backend={type(self._backend).__name__})"

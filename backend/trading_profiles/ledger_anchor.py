"""Independently verifiable anchoring for the CSS-118 hash-chained ledgers.

Problem: each ledger (consent, attribution, trader registry, signal feed) is an unkeyed
SHA-256 chain. Anyone with write access to the files can rewrite history and re-hash it.

Design (no production key is enrolled by this code):
  * A CHECKPOINT commits, for every anchored ledger, to a PREFIX: the number of lines and
    the SHA-256 of exactly those bytes, plus the head entry_hash. Ledgers stay append-only,
    so later appends never invalidate an earlier checkpoint; any edit, deletion, reorder or
    truncation of anchored lines does.
  * Checkpoints form their own chain (seq, prev_checkpoint_sha256) and are signed with an
    Ed25519 ANCHOR key that the server never needs for normal operation. The key is held
    separately from the data (owner / HSM / offline signer). Without the key, checkpoints
    cannot be forged; without it configured, anchoring reports UNANCHORED and nothing is
    signed.
  * Each checkpoint yields a compact ANCHOR STATEMENT (seq, checkpoint hash, time, key
    fingerprint) meant to be published outside the system (e.g. a GitHub issue comment, a
    separate repository, email to the owner, or an RFC 3161 timestamp). A verifier given the
    latest external statement also detects truncation or rollback of the anchor log itself.
  * `verify()` needs only the files, the anchor PUBLIC key and (optionally) the latest
    external statement: it is runnable by anyone (tools/verify_css_ledger_anchors.py).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from backend.certification.ov002_persistence import atomic_append_jsonl
from backend.runtime.interprocess_lock import exclusive_file_lock

SCHEMA = "css.trading_profiles.ledger_anchor.v1"
ANCHOR_KEY_ENV = "CSS_LEDGER_ANCHOR_SIGNING_KEY"  # hex Ed25519 seed; never committed, never defaulted
ANCHOR_LOG = "ledger_anchor_checkpoints.jsonl"
DEFAULT_LEDGERS = {
    "consent": "consent_ledger.jsonl",
    "attribution": "copy_trade_attribution.jsonl",
    "trader_registry": "trader_registry.jsonl",
    "signal_feed": "signal_feed.jsonl",
}
GENESIS = "GENESIS"


class AnchorError(RuntimeError):
    """Anchoring/verification failure; message is a stable reason code."""


def _canonical(body: Mapping[str, Any]) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def public_key_b64(key: Ed25519PrivateKey | Ed25519PublicKey) -> str:
    pub = key.public_key() if isinstance(key, Ed25519PrivateKey) else key
    return base64.b64encode(pub.public_bytes(Encoding.Raw, PublicFormat.Raw)).decode("ascii")


def fingerprint(public_b64: str) -> str:
    return hashlib.sha256(base64.b64decode(public_b64)).hexdigest()[:16]


def env_anchor_key() -> Ed25519PrivateKey | None:
    raw = os.environ.get(ANCHOR_KEY_ENV, "").strip()
    if not raw:
        return None
    try:
        seed = bytes.fromhex(raw)
        return Ed25519PrivateKey.from_private_bytes(seed) if len(seed) == 32 else None
    except ValueError:
        return None


def _lines(path: Path) -> list[bytes]:
    if not path.exists():
        return []
    return [ln for ln in path.read_bytes().splitlines(keepends=True) if ln.strip()]


def _prefix(lines: list[bytes], count: int) -> str:
    h = hashlib.sha256()
    for ln in lines[:count]:
        h.update(ln.rstrip(b"\r\n") + b"\n")  # line-ending independent
    return h.hexdigest()


def _head(lines: list[bytes], count: int) -> str:
    if count == 0:
        return GENESIS
    try:
        return str(json.loads(lines[count - 1]).get("entry_hash") or "")
    except ValueError as exc:
        raise AnchorError("ledger_line_unparseable") from exc


@dataclass
class VerificationReport:
    ok: bool
    status: str  # VERIFIED | UNANCHORED | FAILED
    checkpoints: int
    latest_seq: int | None
    problems: list[str] = field(default_factory=list)
    ledgers: dict[str, dict[str, Any]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "status": self.status, "checkpoints": self.checkpoints,
                "latest_seq": self.latest_seq, "problems": list(self.problems), "ledgers": self.ledgers}


class LedgerAnchor:
    def __init__(self, root: Path | str, *, ledgers: Mapping[str, str] | None = None,
                 key_provider: Callable[[], Ed25519PrivateKey | None] = env_anchor_key) -> None:
        self.root = Path(root)
        self.ledgers = dict(ledgers or DEFAULT_LEDGERS)
        self.key_provider = key_provider
        self.path = self.root / ANCHOR_LOG
        self.lock_path = self.root / "ledger_anchor.lock"

    # -- checkpoints ------------------------------------------------------------
    def checkpoints(self) -> list[dict[str, Any]]:
        out = []
        for ln in _lines(self.path):
            try:
                out.append(json.loads(ln))
            except ValueError as exc:
                raise AnchorError("anchor_log_unparseable") from exc
        return out

    def checkpoint(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Sign and append a checkpoint over the current ledger prefixes. Returns the anchor statement."""
        key = self.key_provider()
        if key is None:
            raise AnchorError("anchor_key_unavailable")
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path, timeout_seconds=10.0):
            existing = self.checkpoints()
            prev = existing[-1] if existing else None
            entries = {}
            for name, rel in sorted(self.ledgers.items()):
                lines = _lines(self.root / rel)
                entries[name] = {"file": rel, "lines": len(lines), "prefix_sha256": _prefix(lines, len(lines)),
                                 "head_entry_hash": _head(lines, len(lines))}
                if prev is not None:  # a new checkpoint must extend, never contradict, the previous one
                    old = prev["body"]["ledgers"].get(name)
                    if old and (len(lines) < old["lines"] or _prefix(lines, old["lines"]) != old["prefix_sha256"]):
                        raise AnchorError(f"ledger_diverged_from_previous_checkpoint:{name}")
            body = {"schema": SCHEMA, "seq": (prev["body"]["seq"] + 1) if prev else 1,
                    "prev_checkpoint_sha256": prev["checkpoint_sha256"] if prev else GENESIS,
                    "created_at_utc": (now or datetime.now(timezone.utc)).isoformat(),
                    "anchor_key_fingerprint": fingerprint(public_key_b64(key)), "ledgers": entries}
            digest = hashlib.sha256(_canonical(body)).hexdigest()
            record = {"body": body, "checkpoint_sha256": digest,
                      "signature_b64": base64.b64encode(key.sign(_canonical(body))).decode("ascii")}
            atomic_append_jsonl(self.path, record, expected_root=self.root)
        return self.statement(record)

    @staticmethod
    def statement(record: Mapping[str, Any]) -> dict[str, Any]:
        """Compact statement to publish outside the system (independent witness)."""
        body = record["body"]
        return {"schema": SCHEMA + ".statement", "seq": body["seq"], "checkpoint_sha256": record["checkpoint_sha256"],
                "created_at_utc": body["created_at_utc"], "anchor_key_fingerprint": body["anchor_key_fingerprint"],
                "signature_b64": record["signature_b64"]}

    # -- verification -------------------------------------------------------------
    def verify(self, public_b64: str | None, *, external_statement: Mapping[str, Any] | None = None) -> VerificationReport:
        problems: list[str] = []
        try:
            records = self.checkpoints()
        except AnchorError as exc:
            return VerificationReport(False, "FAILED", 0, None, [str(exc)])
        if not records:
            status = "FAILED" if external_statement else "UNANCHORED"
            return VerificationReport(False, status, 0, None,
                                      ["anchor_log_missing_but_external_statement_exists"] if external_statement else
                                      ["no_checkpoints"])
        if not public_b64:
            return VerificationReport(False, "FAILED", len(records), None, ["anchor_public_key_required"])
        try:
            pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_b64))
        except Exception:
            return VerificationReport(False, "FAILED", len(records), None, ["anchor_public_key_invalid"])
        fp = fingerprint(public_b64)
        prev_digest, prev_seq = GENESIS, 0
        for rec in records:
            body = rec.get("body") or {}
            seq = body.get("seq")
            try:
                digest = hashlib.sha256(_canonical(body)).hexdigest()
                pub.verify(base64.b64decode(rec.get("signature_b64") or ""), _canonical(body))
            except (InvalidSignature, ValueError, TypeError):
                problems.append(f"checkpoint_signature_invalid:{seq}")
                continue
            if digest != rec.get("checkpoint_sha256"):
                problems.append(f"checkpoint_digest_mismatch:{seq}")
            if body.get("anchor_key_fingerprint") != fp:
                problems.append(f"checkpoint_key_mismatch:{seq}")
            if seq != prev_seq + 1 or body.get("prev_checkpoint_sha256") != prev_digest:
                problems.append(f"checkpoint_chain_broken:{seq}")
            prev_digest, prev_seq = digest, seq if isinstance(seq, int) else prev_seq + 1
        latest = records[-1]["body"]
        ledgers: dict[str, dict[str, Any]] = {}
        for name, entry in sorted(latest.get("ledgers", {}).items()):
            lines = _lines(self.root / entry["file"])
            if len(lines) < entry["lines"]:
                problems.append(f"ledger_truncated:{name}")
                ledgers[name] = {"status": "TRUNCATED"}
                continue
            if _prefix(lines, entry["lines"]) != entry["prefix_sha256"] or _head(lines, entry["lines"]) != entry["head_entry_hash"]:
                problems.append(f"ledger_anchored_prefix_modified:{name}")
                ledgers[name] = {"status": "MODIFIED"}
                continue
            ledgers[name] = {"status": "VERIFIED", "anchored_lines": entry["lines"],
                             "unanchored_tail_lines": len(lines) - entry["lines"]}
        if external_statement is not None:
            ext_seq = external_statement.get("seq")
            match = next((r for r in records if r["body"].get("seq") == ext_seq), None)
            if match is None:
                problems.append("anchor_log_rolled_back_before_external_statement")
            elif match.get("checkpoint_sha256") != external_statement.get("checkpoint_sha256"):
                problems.append("external_statement_mismatch")
        ok = not problems
        return VerificationReport(ok, "VERIFIED" if ok else "FAILED", len(records), latest.get("seq"), problems, ledgers)

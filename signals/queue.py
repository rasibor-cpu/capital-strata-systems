from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

from .vwap_mean_reversion import SignalPrompt


@dataclass
class QueuePolicy:
    """
    Approval queue policy.
    """
    max_queue_size: int = 50
    dedupe_window_minutes: int = 30   # prevent spam of near-identical prompts
    ttl_minutes: int = 90             # expire old prompts automatically


@dataclass
class PendingSignal:
    """
    Wrapper around a SignalPrompt with lifecycle state.
    """
    prompt: SignalPrompt
    created_at_utc: datetime
    expires_at_utc: datetime
    status: str = "PENDING"  # PENDING | APPROVED | REJECTED | EXPIRED
    user_note: Optional[str] = None


class SignalApprovalQueue:
    """
    Stores prompts and manages their lifecycle.
    This module NEVER executes. It only queues and tracks approvals/rejections.
    """

    def __init__(self, policy: Optional[QueuePolicy] = None):
        self.policy = policy or QueuePolicy()
        self._items: List[PendingSignal] = []
        self._recent_fingerprints: Dict[str, datetime] = {}

    def _fingerprint(self, p: SignalPrompt) -> str:
        # Conservative fingerprint: symbol + direction + rounded zscore bucket
        bucket = round(p.zscore, 1)
        return f"{p.symbol}|{p.direction}|{bucket}"

    def _cleanup(self, now: datetime) -> None:
        # expire old prompts
        for item in self._items:
            if item.status == "PENDING" and now >= item.expires_at_utc:
                item.status = "EXPIRED"

        # drop fingerprints outside dedupe window
        dedupe_cutoff = now - timedelta(minutes=self.policy.dedupe_window_minutes)
        self._recent_fingerprints = {
            k: t for k, t in self._recent_fingerprints.items() if t >= dedupe_cutoff
        }

        # enforce max size by removing oldest non-pending first, then oldest overall
        if len(self._items) > self.policy.max_queue_size:
            # remove expired/rejected/approved first
            non_pending = [x for x in self._items if x.status != "PENDING"]
            pending = [x for x in self._items if x.status == "PENDING"]
            # sort by created time
            non_pending.sort(key=lambda x: x.created_at_utc)
            pending.sort(key=lambda x: x.created_at_utc)
            trimmed = pending + non_pending  # keep pending preferentially
            self._items = trimmed[: self.policy.max_queue_size]

    def enqueue(self, prompt: SignalPrompt, now_utc: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Add a prompt to queue if not duplicate and if it is timely.
        Returns: (accepted, message)
        """
        now = now_utc or datetime.utcnow()
        self._cleanup(now)

        fp = self._fingerprint(prompt)
        last = self._recent_fingerprints.get(fp)
        if last is not None:
            return False, "Duplicate signal suppressed (within dedupe window)."

        expires = now + timedelta(minutes=self.policy.ttl_minutes)

        self._items.append(
            PendingSignal(
                prompt=prompt,
                created_at_utc=now,
                expires_at_utc=expires,
                status="PENDING",
            )
        )
        self._recent_fingerprints[fp] = now
        self._cleanup(now)
        return True, "Signal queued."

    def list_pending(self, now_utc: Optional[datetime] = None) -> List[PendingSignal]:
        now = now_utc or datetime.utcnow()
        self._cleanup(now)
        return [x for x in self._items if x.status == "PENDING"]

    def list_all(self, now_utc: Optional[datetime] = None) -> List[PendingSignal]:
        now = now_utc or datetime.utcnow()
        self._cleanup(now)
        return list(self._items)

    def approve(self, index: int, note: Optional[str] = None, now_utc: Optional[datetime] = None) -> bool:
        """
        Marks a pending signal as APPROVED. Still does not execute trades.
        """
        now = now_utc or datetime.utcnow()
        self._cleanup(now)
        pending = self.list_pending(now)

        if index < 0 or index >= len(pending):
            return False

        item = pending[index]
        item.status = "APPROVED"
        item.user_note = note
        return True

    def reject(self, index: int, note: Optional[str] = None, now_utc: Optional[datetime] = None) -> bool:
        """
        Marks a pending signal as REJECTED.
        """
        now = now_utc or datetime.utcnow()
        self._cleanup(now)
        pending = self.list_pending(now)

        if index < 0 or index >= len(pending):
            return False

        item = pending[index]
        item.status = "REJECTED"
        item.user_note = note
        return True

    def top_n(self, n: int = 5, now_utc: Optional[datetime] = None) -> List[PendingSignal]:
        """
        Returns top-N pending signals ranked by confidence then abs(zscore).
        """
        now = now_utc or datetime.utcnow()
        self._cleanup(now)
        pending = self.list_pending(now)

        pending.sort(key=lambda x: (x.prompt.confidence, abs(x.prompt.zscore)), reverse=True)
        return pending[:n]

"""
postings/mandates.py
--------------------
Customer mandate records (signature mandate now; extensible for KYC/doc mandates).

This is a stub-ready module:
- Stores metadata for signature mandates
- Supports maker/checker approval fields
- File blobs are NOT stored here (only references + hashes)
- Scanning tool will be added later at the UI layer and connected here

Design intent:
- Bank-grade immutability: captured artifacts referenced by file_id + sha256
- Governed workflow: created_by, approved_by, approval_level, status
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid


class MandateStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REVOKED = "REVOKED"


class MandateType(str, Enum):
    SIGNATURE = "SIGNATURE"
    KYC_DOC = "KYC_DOC"
    BOARD_RESOLUTION = "BOARD_RESOLUTION"


class SigningRule(str, Enum):
    SINGLE = "SINGLE"
    ANY_TWO = "ANY_TWO"
    ALL = "ALL"


@dataclass
class MandateArtifactRef:
    """
    Reference to a captured artifact (image/pdf) stored elsewhere.
    """
    file_id: str
    filename: str
    mime_type: str
    sha256: str
    captured_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


@dataclass
class CustomerMandate:
    mandate_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str = ""

    mandate_type: MandateType = MandateType.SIGNATURE
    status: MandateStatus = MandateStatus.PENDING

    signing_rule: SigningRule = SigningRule.SINGLE
    specimen_count: int = 1

    artifacts: List[MandateArtifactRef] = field(default_factory=list)

    # Governance metadata
    created_by: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    approved_by: Optional[str] = None
    approval_level: Optional[str] = None
    approved_at: Optional[str] = None

    revoked_by: Optional[str] = None
    revoked_at: Optional[str] = None
    revoke_reason: Optional[str] = None

    effective_from: Optional[str] = None
    expires_at: Optional[str] = None

    def add_artifact(self, ref: MandateArtifactRef) -> None:
        if self.status == MandateStatus.REVOKED:
            raise ValueError("Cannot add artifact to a REVOKED mandate")
        self.artifacts.append(ref)

    def approve(self, *, approved_by: str, approval_level: str) -> None:
        if self.status != MandateStatus.PENDING:
            raise ValueError("Only PENDING mandates can be approved")
        if not approved_by.strip():
            raise ValueError("approved_by is required")
        if not approval_level.strip():
            raise ValueError("approval_level is required")

        self.status = MandateStatus.APPROVED
        self.approved_by = approved_by.strip()
        self.approval_level = approval_level.strip().upper()
        self.approved_at = datetime.utcnow().isoformat() + "Z"

    def revoke(self, *, revoked_by: str, reason: str) -> None:
        if self.status != MandateStatus.APPROVED:
            raise ValueError("Only APPROVED mandates can be revoked")
        if not revoked_by.strip():
            raise ValueError("revoked_by is required")
        if not reason.strip():
            raise ValueError("revoke reason is required")

        self.status = MandateStatus.REVOKED
        self.revoked_by = revoked_by.strip()
        self.revoked_at = datetime.utcnow().isoformat() + "Z"
        self.revoke_reason = reason.strip()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["mandate_type"] = self.mandate_type.value
        d["status"] = self.status.value
        d["signing_rule"] = self.signing_rule.value
        return d


class MandateStore:
    """
    Minimal in-memory mandate registry keyed by customer_id.

    This will later be swapped for persistence.
    """

    def __init__(self) -> None:
        self._by_customer: Dict[str, List[CustomerMandate]] = {}

    def create_signature_mandate(
        self,
        *,
        customer_id: str,
        created_by: str,
        signing_rule: SigningRule = SigningRule.SINGLE,
        specimen_count: int = 1,
    ) -> CustomerMandate:
        if not customer_id.strip():
            raise ValueError("customer_id is required")
        if not created_by.strip():
            raise ValueError("created_by is required")
        if specimen_count < 1 or specimen_count > 3:
            raise ValueError("specimen_count must be between 1 and 3")

        m = CustomerMandate(
            customer_id=customer_id.strip(),
            mandate_type=MandateType.SIGNATURE,
            signing_rule=signing_rule,
            specimen_count=int(specimen_count),
            created_by=created_by.strip(),
        )
        self._by_customer.setdefault(m.customer_id, []).append(m)
        return m

    def list_mandates(self, customer_id: str) -> List[CustomerMandate]:
        return list(self._by_customer.get(customer_id.strip(), []))

    def get_active_signature_mandate(self, customer_id: str) -> Optional[CustomerMandate]:
        mandates = self._by_customer.get(customer_id.strip(), [])
        # “Active” = most recent APPROVED signature mandate
        approved = [m for m in mandates if m.mandate_type == MandateType.SIGNATURE and m.status == MandateStatus.APPROVED]
        if not approved:
            return None
        return approved[-1]

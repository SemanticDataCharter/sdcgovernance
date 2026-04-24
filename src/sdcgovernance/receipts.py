"""
Tamper-evident decision receipt chain for SDC governance.

Every enforcement decision (PERMIT, DENY, INDETERMINATE) produces a
receipt containing the decision, reasoning, PROV record, instance identity,
and a SHA-256 hash linking to the previous receipt. The chain is
deterministic: same input replays to the same decision.

Receipts reference DM.instance_id and DM.instance_version to bind the
provenance trail to the correct instance lineage.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Decision(Enum):
    """OASIS XACML decision semantics."""
    PERMIT = "PERMIT"
    DENY = "DENY"
    INDETERMINATE = "INDETERMINATE"


@dataclass
class GovernanceResult:
    """
    Result of a governance validation or advisory call.

    Returned by validate_governance() and GovernanceEngine methods.
    """
    decision: Decision
    has_governance: bool = True
    errors: list[str] = field(default_factory=list)
    receipt: Receipt | None = None
    dimensions_validated: dict[str, Any] = field(default_factory=dict)


@dataclass
class Receipt:
    """
    Tamper-evident decision receipt.

    Each receipt is a PROV-formatted record of a governance decision,
    hash-chained to the previous receipt for tamper evidence.
    """
    # Decision
    decision: Decision
    reasoning: str = ""

    # Instance identity (from DM root)
    instance_id: str = ""
    instance_version: str = ""

    # Temporal
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Hash chain
    previous_hash: str | None = None
    receipt_hash: str = ""

    # Dimensions that were checked
    dimensions_checked: list[str] = field(default_factory=list)

    # Errors for DENY/INDETERMINATE
    errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Compute the receipt hash after initialization."""
        if not self.receipt_hash:
            self.receipt_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """
        Compute SHA-256 hash of the receipt content.

        The hash covers all fields except receipt_hash itself.
        Timestamp IS included - each receipt is unique in time.
        """
        content = {
            "decision": self.decision.value,
            "reasoning": self.reasoning,
            "instance_id": self.instance_id,
            "instance_version": self.instance_version,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "dimensions_checked": self.dimensions_checked,
            "errors": self.errors,
        }
        canonical = json.dumps(content, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def verify_hash(self) -> bool:
        """Verify that the receipt hash matches the content."""
        return self.receipt_hash == self._compute_hash()

    def to_dict(self) -> dict[str, Any]:
        """Serialize receipt to a dictionary."""
        d = asdict(self)
        d["decision"] = self.decision.value
        return d


class ReceiptChain:
    """
    Append-only chain of decision receipts.

    Each receipt is hash-chained to the previous one. The chain
    provides tamper-evident audit trail of all governance decisions
    for an instance lineage.
    """

    def __init__(self) -> None:
        self._receipts: list[Receipt] = []

    @property
    def receipts(self) -> list[Receipt]:
        """Read-only access to the receipt list."""
        return list(self._receipts)

    @property
    def length(self) -> int:
        """Number of receipts in the chain."""
        return len(self._receipts)

    @property
    def last_hash(self) -> str | None:
        """Hash of the most recent receipt, or None if chain is empty."""
        if self._receipts:
            return self._receipts[-1].receipt_hash
        return None

    def append(
        self,
        decision: Decision,
        reasoning: str = "",
        instance_id: str = "",
        instance_version: str = "",
        dimensions_checked: list[str] | None = None,
        errors: list[str] | None = None,
    ) -> Receipt:
        """
        Create a new receipt and append it to the chain.

        The receipt's previous_hash is automatically set to the hash
        of the last receipt in the chain (or None for the first receipt).

        Returns the newly created receipt.
        """
        receipt = Receipt(
            decision=decision,
            reasoning=reasoning,
            instance_id=instance_id,
            instance_version=instance_version,
            previous_hash=self.last_hash,
            dimensions_checked=dimensions_checked or [],
            errors=errors or [],
        )
        self._receipts.append(receipt)
        return receipt

    def verify_chain(self) -> bool:
        """
        Verify the integrity of the entire receipt chain.

        Checks:
        1. Each receipt's hash matches its content.
        2. Each receipt's previous_hash matches the prior receipt's hash.
        3. First receipt has previous_hash = None.

        Returns True if the chain is intact, False if tampered.
        """
        for i, receipt in enumerate(self._receipts):
            # Verify receipt hash matches content
            if not receipt.verify_hash():
                return False

            # Verify chain linkage
            if i == 0:
                if receipt.previous_hash is not None:
                    return False
            else:
                if receipt.previous_hash != self._receipts[i - 1].receipt_hash:
                    return False

        return True

    def to_list(self) -> list[dict[str, Any]]:
        """Serialize the entire chain to a list of dicts."""
        return [r.to_dict() for r in self._receipts]

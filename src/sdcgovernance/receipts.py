"""
Tamper-evident decision receipt chain for SDC governance.

Every enforcement decision produces a receipt containing the decision,
reasoning, status code, obligations, instance identity, and a SHA-256
hash linking to the previous receipt.

Decision values follow OASIS XACML 3.0 Section 5.53 (all four values):
PERMIT, DENY, INDETERMINATE, NOT_APPLICABLE.

Receipts reference DM.instance_id and DM.instance_version to bind the
provenance trail to the correct instance lineage.

Note on determinism: the decision is deterministic (same inputs produce
the same decision). The receipt_hash includes a timestamp and is therefore
unique per evaluation. This is intentional for tamper evidence but means
the hash itself is not replayable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Decision(Enum):
    """
    OASIS XACML 3.0 Section 5.53 decision values.

    All four normative values per XACML 3.0 Section 7.17:
    - PERMIT: all governance checks pass, action is authorized
    - DENY: one or more governance checks fail, action is refused
    - INDETERMINATE: evaluation error (missing attribute, processing
      failure, unsupported function). The evaluator could not reach
      a definitive PERMIT or DENY.
    - NOT_APPLICABLE: the policy did not apply to the request (no
      governance components defined, no rules matched, policy target
      did not match). Distinct from INDETERMINATE - NOT_APPLICABLE
      means the policy was evaluated successfully but simply does
      not cover this case.
    """
    PERMIT = "PERMIT"
    DENY = "DENY"
    INDETERMINATE = "INDETERMINATE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class StatusCode(Enum):
    """
    XACML 3.0 Section 10.2.4 standard status codes.

    Machine-readable identifiers for why a decision was reached,
    especially for INDETERMINATE and NOT_APPLICABLE outcomes.
    """
    OK = "urn:oasis:names:tc:xacml:1.0:status:ok"
    MISSING_ATTRIBUTE = "urn:oasis:names:tc:xacml:1.0:status:missing-attribute"
    SYNTAX_ERROR = "urn:oasis:names:tc:xacml:1.0:status:syntax-error"
    PROCESSING_ERROR = "urn:oasis:names:tc:xacml:1.0:status:processing-error"


@dataclass
class Obligation:
    """
    A policy-attached side effect per XACML 3.0 Section 5.34/5.39.

    Obligations are actions that MUST be performed in conjunction with
    the enforcement of a decision. If the PEP (agent) cannot fulfill
    an obligation, it MUST NOT permit access (XACML 3.0 Section 7.2.1).

    In ACAL 1.0, Obligations and Advice are unified into Notice with
    an is_obligation flag.
    """
    obligation_id: str = ""
    description: str = ""
    is_obligation: bool = True  # True = must fulfill; False = advice (may fulfill)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class GovernanceResult:
    """
    Result of a governance validation or advisory call.

    Returned by validate_governance() and GovernanceEngine methods.
    """
    decision: Decision
    has_governance: bool = True
    status_code: StatusCode = StatusCode.OK
    errors: list[str] = field(default_factory=list)
    obligations: list[Obligation] = field(default_factory=list)
    receipt: Receipt | None = None
    dimensions_validated: dict[str, Any] = field(default_factory=dict)


@dataclass
class Receipt:
    """
    Tamper-evident decision receipt.

    Each receipt records a governance decision with hash-chained
    tamper evidence. The receipt embeds an XACML decision value
    and status code but is an SDC-specific structure, not an
    XACML ResultType.
    """
    # Decision (XACML 3.0 Section 5.53 - all four values)
    decision: Decision
    reasoning: str = ""

    # Status (XACML 3.0 Section 5.54-5.55)
    status_code: StatusCode = StatusCode.OK

    # Obligations / Advice (XACML 3.0 Section 5.34/5.35)
    obligations: list[Obligation] = field(default_factory=list)

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
        Timestamp IS included for tamper evidence - this means the
        hash is unique per evaluation (not replayable), but the
        decision value is deterministic.
        """
        content = {
            "decision": self.decision.value,
            "reasoning": self.reasoning,
            "status_code": self.status_code.value,
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
        d["status_code"] = self.status_code.value
        d["obligations"] = [asdict(o) for o in self.obligations]
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
        status_code: StatusCode = StatusCode.OK,
        obligations: list[Obligation] | None = None,
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
            status_code=status_code,
            obligations=obligations or [],
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

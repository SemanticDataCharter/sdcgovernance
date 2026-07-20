"""
GovernanceEngine - the decision engine agents query.

Wraps the validation modules into a stateful engine that agents interact
with. Provides the advisory interface: what transitions are allowed,
can this transition proceed, record what happened.

This is the core that both the Python API and the MCP server expose.

Usage::

    from sdcgovernance.engine import GovernanceEngine

    engine = GovernanceEngine(schema_path)
    options = engine.get_allowed_transitions(current_state="draft")
    decision = engine.evaluate_transition(current_state="draft", target_state="review", actor="dr_smith")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sdcgovernance.model_inspector import GovernanceModel, inspect_model
from sdcgovernance.receipts import Decision, GovernanceResult, ReceiptChain, StatusCode
from sdcgovernance.workflow import (
    WorkflowTree,
    extract_workflow_from_instance,
)


class GovernanceEngine:
    """
    Governance advisory engine for SDC data instances.

    Wraps model_inspector and validation modules. Maintains a receipt
    chain across multiple calls within a session. Agents interact with
    this engine via get_allowed_transitions, evaluate_transition, etc.

    The engine is stateful: it caches model inspection results and
    maintains a receipt chain. Create one engine per schema.
    """

    def __init__(self, schema_path: str | Path) -> None:
        """
        Initialize the engine by inspecting the model.

        Args:
            schema_path: Path to the SDC data model XSD file.
        """
        self._schema_path = Path(schema_path)
        self._model: GovernanceModel = inspect_model(self._schema_path)
        self._receipt_chain = ReceiptChain()

    @property
    def model(self) -> GovernanceModel:
        """The inspected governance model."""
        return self._model

    @property
    def receipt_chain(self) -> ReceiptChain:
        """The session receipt chain."""
        return self._receipt_chain

    @property
    def has_governance(self) -> bool:
        """True if the model defines any governance dimensions."""
        return self._model.has_governance

    def get_governance_status(self) -> dict[str, Any]:
        """
        Report which governance dimensions the model defines.

        Returns a dict mapping dimension names to their active status.
        """
        return {
            "model_id": self._model.model_id,
            "model_label": self._model.model_label,
            "has_governance": self._model.has_governance,
            "dimensions": self._model.active_dimensions,
        }

    def get_allowed_transitions(
        self,
        current_state: str,
        workflow_tree: WorkflowTree | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get valid next states from the current state.

        Args:
            current_state: The current workflow state symbol.
            workflow_tree: Pre-parsed workflow tree. If None, returns empty
                (workflow tree must be provided from instance or model).

        Returns:
            List of valid transitions with target state info and path(s).
        """
        if not self._model.workflow.present:
            return []

        if workflow_tree is None:
            return []

        return workflow_tree.get_allowed_transitions(current_state)

    def evaluate_transition(
        self,
        current_state: str,
        target_state: str,
        actor: str = "",
        instance_id: str = "",
        instance_version: str = "",
        source_instance_id: str = "",
        source_version_id: str = "",
        workflow_tree: WorkflowTree | None = None,
    ) -> GovernanceResult:
        """
        Evaluate whether a specific transition is permitted.

        Args:
            current_state: Current workflow state symbol.
            target_state: Proposed target state symbol.
            actor: Identity of the actor requesting the transition.
            instance_id: DM.instance_id for receipt chain binding.
            instance_version: DM.instance_version for receipt chain binding.
            source_instance_id: DM.source_instance_id, upstream source lineage.
            source_version_id: DM.source_version_id, upstream source version.
            workflow_tree: Pre-parsed workflow tree.

        Returns:
            GovernanceResult with XACML decision and receipt.
        """
        if not self._model.workflow.present:
            receipt = self._receipt_chain.append(
                decision=Decision.NOT_APPLICABLE,
                reasoning="Model does not define workflow governance",
                instance_id=instance_id,
                instance_version=instance_version,
                source_instance_id=source_instance_id,
                source_version_id=source_version_id,
                dimensions_checked=["workflow"],
                status_code=StatusCode.OK,
            )
            return GovernanceResult(
                decision=Decision.NOT_APPLICABLE,
                has_governance=False,
                status_code=StatusCode.OK,
                receipt=receipt,
                dimensions_validated={"workflow": False},
            )

        if workflow_tree is None:
            receipt = self._receipt_chain.append(
                decision=Decision.INDETERMINATE,
                reasoning="Workflow governance defined but no workflow tree provided",
                instance_id=instance_id,
                instance_version=instance_version,
                source_instance_id=source_instance_id,
                source_version_id=source_version_id,
                dimensions_checked=["workflow"],
                errors=["No workflow tree available for validation"],
                status_code=StatusCode.MISSING_ATTRIBUTE,
            )
            return GovernanceResult(
                decision=Decision.INDETERMINATE,
                status_code=StatusCode.MISSING_ATTRIBUTE,
                errors=["No workflow tree available for validation"],
                receipt=receipt,
                dimensions_validated={"workflow": True},
            )

        # Check if current state exists in the workflow
        current_matches = workflow_tree.find_current_state(current_state)
        if not current_matches:
            receipt = self._receipt_chain.append(
                decision=Decision.DENY,
                reasoning=f"Current state '{current_state}' not found in any workflow path",
                instance_id=instance_id,
                instance_version=instance_version,
                source_instance_id=source_instance_id,
                source_version_id=source_version_id,
                dimensions_checked=["workflow"],
                errors=[f"Current state '{current_state}' is not a valid workflow state"],
            )
            return GovernanceResult(
                decision=Decision.DENY,
                errors=[f"Current state '{current_state}' is not a valid workflow state"],
                receipt=receipt,
                dimensions_validated={"workflow": True},
            )

        # Check if transition is valid
        allowed = workflow_tree.get_allowed_transitions(current_state)
        valid_targets = [t["target_symbol"] for t in allowed]

        if target_state in valid_targets:
            # Find the matching transition details
            transition = next(t for t in allowed if t["target_symbol"] == target_state)
            receipt = self._receipt_chain.append(
                decision=Decision.PERMIT,
                reasoning=(
                    f"Transition '{current_state}' -> '{target_state}' is valid "
                    f"in path(s): {transition['paths']}"
                ),
                instance_id=instance_id,
                instance_version=instance_version,
                source_instance_id=source_instance_id,
                source_version_id=source_version_id,
                dimensions_checked=["workflow"],
            )
            return GovernanceResult(
                decision=Decision.PERMIT,
                receipt=receipt,
                dimensions_validated={"workflow": True},
            )
        else:
            receipt = self._receipt_chain.append(
                decision=Decision.DENY,
                reasoning=(
                    f"Transition '{current_state}' -> '{target_state}' does not exist "
                    f"in any workflow path. Valid targets: {valid_targets}"
                ),
                instance_id=instance_id,
                instance_version=instance_version,
                source_instance_id=source_instance_id,
                source_version_id=source_version_id,
                dimensions_checked=["workflow"],
                errors=[
                    f"Invalid transition: '{current_state}' -> '{target_state}'",
                    f"Valid transitions from '{current_state}': {valid_targets}",
                ],
            )
            return GovernanceResult(
                decision=Decision.DENY,
                errors=[
                    f"Invalid transition: '{current_state}' -> '{target_state}'",
                    f"Valid transitions from '{current_state}': {valid_targets}",
                ],
                receipt=receipt,
                dimensions_validated={"workflow": True},
            )

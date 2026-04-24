"""
Tests for workflow validation and GovernanceEngine - Phase 2.

Tests workflow cluster tree extraction, ordinal adjacency validation,
branching paths, component reuse, and the GovernanceEngine advisory API.
"""

import pytest
from pathlib import Path
from sdcgovernance.workflow import (
    WorkflowState,
    WorkflowPath,
    WorkflowTree,
    extract_workflow_from_instance,
)
from sdcgovernance.engine import GovernanceEngine
from sdcgovernance.receipts import Decision

FIXTURES = Path(__file__).parent / "fixtures"


class TestWorkflowTree:
    """Unit tests for WorkflowTree data structures."""

    def test_empty_tree(self):
        tree = WorkflowTree()
        assert tree.paths == []
        assert tree.get_allowed_transitions("draft") == []

    def test_single_path(self):
        path = WorkflowPath(
            label="main",
            states=[
                WorkflowState(ordinal=0, symbol="draft", label="Draft"),
                WorkflowState(ordinal=1, symbol="review", label="Review"),
                WorkflowState(ordinal=2, symbol="approved", label="Approved"),
            ],
        )
        tree = WorkflowTree(paths=[path])
        assert tree.is_valid_transition("draft", "review")
        assert tree.is_valid_transition("review", "approved")
        assert not tree.is_valid_transition("draft", "approved")  # skip
        assert not tree.is_valid_transition("approved", "draft")  # reverse

    def test_branching_paths(self):
        approval = WorkflowPath(
            label="approval",
            states=[
                WorkflowState(ordinal=0, symbol="draft", label="Draft"),
                WorkflowState(ordinal=1, symbol="review", label="Review"),
                WorkflowState(ordinal=2, symbol="approved", label="Approved"),
            ],
        )
        rejection = WorkflowPath(
            label="rejection",
            states=[
                WorkflowState(ordinal=0, symbol="draft", label="Draft"),
                WorkflowState(ordinal=1, symbol="review", label="Review"),
                WorkflowState(ordinal=2, symbol="rejected", label="Rejected"),
            ],
        )
        tree = WorkflowTree(paths=[approval, rejection])

        # From review, both approved and rejected are valid
        allowed = tree.get_allowed_transitions("review")
        symbols = {t["target_symbol"] for t in allowed}
        assert symbols == {"approved", "rejected"}

        assert tree.is_valid_transition("review", "approved")
        assert tree.is_valid_transition("review", "rejected")
        assert not tree.is_valid_transition("review", "draft")  # reverse

    def test_shared_state_across_paths(self):
        """Component reuse: same symbol in multiple paths."""
        path_a = WorkflowPath(
            label="path_a",
            states=[
                WorkflowState(ordinal=0, symbol="start", label="Start"),
                WorkflowState(ordinal=1, symbol="middle", label="Middle"),
                WorkflowState(ordinal=2, symbol="end_a", label="End A"),
            ],
        )
        path_b = WorkflowPath(
            label="path_b",
            states=[
                WorkflowState(ordinal=0, symbol="start", label="Start"),
                WorkflowState(ordinal=1, symbol="middle", label="Middle"),
                WorkflowState(ordinal=2, symbol="end_b", label="End B"),
            ],
        )
        tree = WorkflowTree(paths=[path_a, path_b])

        allowed = tree.get_allowed_transitions("middle")
        symbols = {t["target_symbol"] for t in allowed}
        assert symbols == {"end_a", "end_b"}

    def test_find_current_state(self):
        path = WorkflowPath(
            label="main",
            states=[
                WorkflowState(ordinal=0, symbol="draft", label="Draft"),
                WorkflowState(ordinal=1, symbol="review", label="Review"),
            ],
        )
        tree = WorkflowTree(paths=[path])
        matches = tree.find_current_state("draft")
        assert len(matches) == 1
        assert matches[0][1].symbol == "draft"

    def test_nonexistent_state(self):
        path = WorkflowPath(
            label="main",
            states=[
                WorkflowState(ordinal=0, symbol="draft", label="Draft"),
            ],
        )
        tree = WorkflowTree(paths=[path])
        assert tree.find_current_state("nonexistent") == []
        assert tree.get_allowed_transitions("nonexistent") == []

    def test_last_state_has_no_transitions(self):
        path = WorkflowPath(
            label="main",
            states=[
                WorkflowState(ordinal=0, symbol="draft", label="Draft"),
                WorkflowState(ordinal=1, symbol="final", label="Final"),
            ],
        )
        tree = WorkflowTree(paths=[path])
        assert tree.get_allowed_transitions("final") == []

    def test_transition_includes_path_info(self):
        path = WorkflowPath(
            label="approval_path",
            states=[
                WorkflowState(ordinal=0, symbol="draft", label="Draft"),
                WorkflowState(ordinal=1, symbol="review", label="Review"),
            ],
        )
        tree = WorkflowTree(paths=[path])
        allowed = tree.get_allowed_transitions("draft")
        assert len(allowed) == 1
        assert allowed[0]["target_symbol"] == "review"
        assert allowed[0]["target_label"] == "Review"
        assert allowed[0]["target_ordinal"] == 1.0
        assert "approval_path" in allowed[0]["paths"]


class TestExtractWorkflowFromInstance:
    """Tests for parsing workflow from XML instances."""

    def test_linear_workflow(self):
        path = FIXTURES / "instance-linear-workflow.xml"
        current_state, tree = extract_workflow_from_instance(str(path))
        assert current_state == "draft"
        assert tree is not None
        assert len(tree.paths) == 1
        assert len(tree.paths[0].states) == 4

    def test_linear_workflow_states(self):
        path = FIXTURES / "instance-linear-workflow.xml"
        _, tree = extract_workflow_from_instance(str(path))
        states = tree.paths[0].state_symbols
        assert states == ["draft", "review", "approved", "published"]

    def test_branching_workflow(self):
        path = FIXTURES / "instance-branching-workflow.xml"
        current_state, tree = extract_workflow_from_instance(str(path))
        assert current_state == "review"
        assert tree is not None
        assert len(tree.paths) == 2

    def test_branching_allowed_transitions(self):
        path = FIXTURES / "instance-branching-workflow.xml"
        _, tree = extract_workflow_from_instance(str(path))
        allowed = tree.get_allowed_transitions("review")
        symbols = {t["target_symbol"] for t in allowed}
        assert symbols == {"approved", "rejected"}


class TestGovernanceEngine:
    """Tests for the GovernanceEngine advisory API."""

    @pytest.fixture
    def engine(self, model_workflow_only):
        return GovernanceEngine(model_workflow_only)

    @pytest.fixture
    def engine_no_governance(self, model_no_governance):
        return GovernanceEngine(model_no_governance)

    @pytest.fixture
    def linear_tree(self):
        _, tree = extract_workflow_from_instance(
            str(FIXTURES / "instance-linear-workflow.xml")
        )
        return tree

    @pytest.fixture
    def branching_tree(self):
        _, tree = extract_workflow_from_instance(
            str(FIXTURES / "instance-branching-workflow.xml")
        )
        return tree

    def test_engine_caches_model(self, engine):
        assert engine.model is not None
        assert engine.model.workflow.present is True

    def test_engine_has_governance(self, engine):
        assert engine.has_governance is True

    def test_engine_no_governance(self, engine_no_governance):
        assert engine_no_governance.has_governance is False

    def test_get_governance_status(self, engine):
        status = engine.get_governance_status()
        assert status["has_governance"] is True
        assert status["dimensions"]["workflow"] is True

    def test_get_allowed_transitions(self, engine, linear_tree):
        allowed = engine.get_allowed_transitions("draft", linear_tree)
        assert len(allowed) == 1
        assert allowed[0]["target_symbol"] == "review"

    def test_get_allowed_transitions_branching(self, engine, branching_tree):
        allowed = engine.get_allowed_transitions("review", branching_tree)
        symbols = {t["target_symbol"] for t in allowed}
        assert symbols == {"approved", "rejected"}

    def test_evaluate_valid_transition(self, engine, linear_tree):
        result = engine.evaluate_transition(
            current_state="draft",
            target_state="review",
            instance_id="test-001",
            workflow_tree=linear_tree,
        )
        assert result.decision == Decision.PERMIT
        assert result.receipt is not None
        assert result.receipt.instance_id == "test-001"

    def test_evaluate_invalid_transition_skip(self, engine, linear_tree):
        """Skipping a state is DENY."""
        result = engine.evaluate_transition(
            current_state="draft",
            target_state="approved",
            workflow_tree=linear_tree,
        )
        assert result.decision == Decision.DENY
        assert len(result.errors) > 0
        assert "approved" in result.errors[0]

    def test_evaluate_invalid_transition_reverse(self, engine, linear_tree):
        """Reversing is DENY."""
        result = engine.evaluate_transition(
            current_state="approved",
            target_state="draft",
            workflow_tree=linear_tree,
        )
        assert result.decision == Decision.DENY

    def test_evaluate_invalid_current_state(self, engine, linear_tree):
        """Unknown current state is DENY."""
        result = engine.evaluate_transition(
            current_state="nonexistent",
            target_state="review",
            workflow_tree=linear_tree,
        )
        assert result.decision == Decision.DENY
        assert "nonexistent" in result.errors[0]

    def test_evaluate_no_workflow_tree(self, engine):
        """No workflow tree provided is INDETERMINATE."""
        result = engine.evaluate_transition(
            current_state="draft",
            target_state="review",
        )
        assert result.decision == Decision.INDETERMINATE

    def test_evaluate_no_governance(self, engine_no_governance, linear_tree):
        """Model without workflow governance returns PERMIT."""
        result = engine_no_governance.evaluate_transition(
            current_state="draft",
            target_state="review",
            workflow_tree=linear_tree,
        )
        assert result.decision == Decision.PERMIT
        assert result.has_governance is False

    def test_receipt_chain_accumulates(self, engine, linear_tree):
        """Multiple evaluate calls build the receipt chain."""
        engine.evaluate_transition("draft", "review", workflow_tree=linear_tree)
        engine.evaluate_transition("review", "approved", workflow_tree=linear_tree)
        engine.evaluate_transition("approved", "draft", workflow_tree=linear_tree)  # DENY

        assert engine.receipt_chain.length == 3
        assert engine.receipt_chain.verify_chain() is True

        receipts = engine.receipt_chain.receipts
        assert receipts[0].decision == Decision.PERMIT
        assert receipts[1].decision == Decision.PERMIT
        assert receipts[2].decision == Decision.DENY

    def test_deny_includes_valid_alternatives(self, engine, branching_tree):
        """DENY result tells the agent what the valid options are."""
        result = engine.evaluate_transition(
            current_state="review",
            target_state="published",  # not adjacent
            workflow_tree=branching_tree,
        )
        assert result.decision == Decision.DENY
        # Should mention valid alternatives
        assert any("approved" in e or "rejected" in e for e in result.errors)

    def test_branching_permit_approval_path(self, engine, branching_tree):
        result = engine.evaluate_transition(
            current_state="review",
            target_state="approved",
            workflow_tree=branching_tree,
        )
        assert result.decision == Decision.PERMIT

    def test_branching_permit_rejection_path(self, engine, branching_tree):
        result = engine.evaluate_transition(
            current_state="review",
            target_state="rejected",
            workflow_tree=branching_tree,
        )
        assert result.decision == Decision.PERMIT

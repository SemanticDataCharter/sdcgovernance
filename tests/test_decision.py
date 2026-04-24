"""
Tests for DMN decision table evaluation - Phase 5.

Tests decision table evaluation with single/multi conditions,
hit policies (FIRST, UNIQUE, COLLECT), protocol and XdLink
context inputs, and deterministic evaluation.
"""

import pytest
from pathlib import Path
from sdcgovernance.decision import (
    Condition,
    ComparisonOp,
    Rule,
    DecisionTable,
    DecisionResult,
    HitPolicy,
    evaluate_decision_table,
    build_context_from_instance,
)
from sdcgovernance.receipts import Decision

FIXTURES = Path(__file__).parent / "fixtures"


class TestCondition:
    """Individual condition evaluation."""

    def test_eq(self):
        c = Condition("status", ComparisonOp.EQ, "active")
        assert c.evaluate({"status": "active"}) is True
        assert c.evaluate({"status": "inactive"}) is False

    def test_ne(self):
        c = Condition("status", ComparisonOp.NE, "blocked")
        assert c.evaluate({"status": "active"}) is True
        assert c.evaluate({"status": "blocked"}) is False

    def test_lt(self):
        c = Condition("risk_score", ComparisonOp.LT, 5)
        assert c.evaluate({"risk_score": 3}) is True
        assert c.evaluate({"risk_score": 5}) is False
        assert c.evaluate({"risk_score": 7}) is False

    def test_le(self):
        c = Condition("risk_score", ComparisonOp.LE, 5)
        assert c.evaluate({"risk_score": 5}) is True
        assert c.evaluate({"risk_score": 6}) is False

    def test_gt(self):
        c = Condition("risk_score", ComparisonOp.GT, 5)
        assert c.evaluate({"risk_score": 7}) is True
        assert c.evaluate({"risk_score": 5}) is False

    def test_ge(self):
        c = Condition("risk_score", ComparisonOp.GE, 5)
        assert c.evaluate({"risk_score": 5}) is True
        assert c.evaluate({"risk_score": 4}) is False

    def test_in(self):
        c = Condition("role", ComparisonOp.IN, ["admin", "approver"])
        assert c.evaluate({"role": "admin"}) is True
        assert c.evaluate({"role": "viewer"}) is False

    def test_not_in(self):
        c = Condition("role", ComparisonOp.NOT_IN, ["blocked", "suspended"])
        assert c.evaluate({"role": "admin"}) is True
        assert c.evaluate({"role": "blocked"}) is False

    def test_missing_field_returns_false(self):
        c = Condition("missing_field", ComparisonOp.EQ, "value")
        assert c.evaluate({"other_field": "value"}) is False

    def test_type_mismatch_returns_false(self):
        c = Condition("score", ComparisonOp.LT, 5)
        assert c.evaluate({"score": "not_a_number"}) is False


class TestRule:
    """Rule evaluation (AND logic across conditions)."""

    def test_single_condition_match(self):
        rule = Rule(
            conditions=[Condition("status", ComparisonOp.EQ, "active")],
            outcome=Decision.PERMIT,
        )
        assert rule.evaluate({"status": "active"}) is True

    def test_multi_condition_all_match(self):
        rule = Rule(
            conditions=[
                Condition("risk_score", ComparisonOp.LT, 5),
                Condition("attestation_level", ComparisonOp.EQ, "senior"),
            ],
            outcome=Decision.PERMIT,
        )
        assert rule.evaluate({"risk_score": 3, "attestation_level": "senior"}) is True

    def test_multi_condition_partial_match(self):
        rule = Rule(
            conditions=[
                Condition("risk_score", ComparisonOp.LT, 5),
                Condition("attestation_level", ComparisonOp.EQ, "senior"),
            ],
            outcome=Decision.PERMIT,
        )
        assert rule.evaluate({"risk_score": 3, "attestation_level": "junior"}) is False

    def test_empty_conditions_always_match(self):
        rule = Rule(conditions=[], outcome=Decision.PERMIT)
        assert rule.evaluate({}) is True


class TestDecisionTableFirstHit:
    """FIRST hit policy - return first matching rule."""

    @pytest.fixture
    def risk_table(self):
        return DecisionTable(
            name="risk_assessment",
            hit_policy=HitPolicy.FIRST,
            rules=[
                Rule(
                    conditions=[Condition("risk_score", ComparisonOp.GE, 8)],
                    outcome=Decision.DENY,
                    description="High risk: deny",
                ),
                Rule(
                    conditions=[Condition("risk_score", ComparisonOp.GE, 5)],
                    outcome=Decision.INDETERMINATE,
                    description="Medium risk: escalate",
                ),
                Rule(
                    conditions=[Condition("risk_score", ComparisonOp.LT, 5)],
                    outcome=Decision.PERMIT,
                    description="Low risk: permit",
                ),
            ],
        )

    def test_high_risk_deny(self, risk_table):
        result = evaluate_decision_table(risk_table, {"risk_score": 9})
        assert result.decision == Decision.DENY
        assert 0 in result.matched_rules

    def test_medium_risk_indeterminate(self, risk_table):
        result = evaluate_decision_table(risk_table, {"risk_score": 6})
        assert result.decision == Decision.INDETERMINATE
        assert 1 in result.matched_rules

    def test_low_risk_permit(self, risk_table):
        result = evaluate_decision_table(risk_table, {"risk_score": 3})
        assert result.decision == Decision.PERMIT
        assert 2 in result.matched_rules

    def test_first_hit_returns_first(self, risk_table):
        """risk_score=9 matches both rule 0 (>=8) and rule 1 (>=5). FIRST returns rule 0."""
        result = evaluate_decision_table(risk_table, {"risk_score": 9})
        assert result.matched_rules == [0]

    def test_no_match_indeterminate(self, risk_table):
        result = evaluate_decision_table(risk_table, {"risk_score": None})
        assert result.decision == Decision.INDETERMINATE
        assert result.matched_rules == []


class TestDecisionTableUnique:
    """UNIQUE hit policy - exactly one rule must match."""

    @pytest.fixture
    def status_table(self):
        return DecisionTable(
            name="status_check",
            hit_policy=HitPolicy.UNIQUE,
            rules=[
                Rule(
                    conditions=[Condition("status", ComparisonOp.EQ, "active")],
                    outcome=Decision.PERMIT,
                    description="Active users permitted",
                ),
                Rule(
                    conditions=[Condition("status", ComparisonOp.EQ, "suspended")],
                    outcome=Decision.DENY,
                    description="Suspended users denied",
                ),
            ],
        )

    def test_unique_match(self, status_table):
        result = evaluate_decision_table(status_table, {"status": "active"})
        assert result.decision == Decision.PERMIT
        assert result.matched_rules == [0]

    def test_unique_no_match(self, status_table):
        result = evaluate_decision_table(status_table, {"status": "unknown"})
        assert result.decision == Decision.INDETERMINATE

    def test_unique_multiple_match_error(self):
        """UNIQUE policy with overlapping rules produces INDETERMINATE + error."""
        table = DecisionTable(
            name="overlap",
            hit_policy=HitPolicy.UNIQUE,
            rules=[
                Rule(conditions=[Condition("x", ComparisonOp.GT, 0)], outcome=Decision.PERMIT),
                Rule(conditions=[Condition("x", ComparisonOp.LT, 10)], outcome=Decision.DENY),
            ],
        )
        result = evaluate_decision_table(table, {"x": 5})
        assert result.decision == Decision.INDETERMINATE
        assert len(result.errors) > 0
        assert len(result.matched_rules) == 2


class TestDecisionTableCollect:
    """COLLECT hit policy - return all matching, most restrictive wins."""

    def test_collect_most_restrictive(self):
        table = DecisionTable(
            name="multi_check",
            hit_policy=HitPolicy.COLLECT,
            rules=[
                Rule(
                    conditions=[Condition("has_attestation", ComparisonOp.EQ, True)],
                    outcome=Decision.PERMIT,
                    description="Attestation present",
                ),
                Rule(
                    conditions=[Condition("risk_score", ComparisonOp.GE, 8)],
                    outcome=Decision.DENY,
                    description="High risk",
                ),
            ],
        )
        result = evaluate_decision_table(
            table, {"has_attestation": True, "risk_score": 9}
        )
        assert result.decision == Decision.DENY  # most restrictive
        assert len(result.matched_rules) == 2

    def test_collect_all_permit(self):
        table = DecisionTable(
            name="all_good",
            hit_policy=HitPolicy.COLLECT,
            rules=[
                Rule(conditions=[Condition("a", ComparisonOp.EQ, True)], outcome=Decision.PERMIT),
                Rule(conditions=[Condition("b", ComparisonOp.EQ, True)], outcome=Decision.PERMIT),
            ],
        )
        result = evaluate_decision_table(table, {"a": True, "b": True})
        assert result.decision == Decision.PERMIT
        assert len(result.matched_rules) == 2


class TestProtocolCondition:
    """DM.protocol as decision table input (P5-04)."""

    @pytest.fixture
    def protocol_table(self):
        return DecisionTable(
            name="protocol_check",
            hit_policy=HitPolicy.FIRST,
            rules=[
                Rule(
                    conditions=[Condition("protocol", ComparisonOp.EQ, "HIPAA-compliant")],
                    outcome=Decision.PERMIT,
                    description="HIPAA protocol accepted",
                ),
                Rule(
                    conditions=[],
                    outcome=Decision.DENY,
                    description="Non-HIPAA protocol denied",
                ),
            ],
        )

    def test_matching_protocol_permits(self, protocol_table):
        result = evaluate_decision_table(
            protocol_table, {"protocol": "HIPAA-compliant"}
        )
        assert result.decision == Decision.PERMIT

    def test_non_matching_protocol_denies(self, protocol_table):
        result = evaluate_decision_table(
            protocol_table, {"protocol": "internal-only"}
        )
        assert result.decision == Decision.DENY

    def test_missing_protocol_denies(self, protocol_table):
        result = evaluate_decision_table(protocol_table, {})
        assert result.decision == Decision.DENY


class TestXdLinkCondition:
    """DM.XdLink[] relation type validation (P5-05)."""

    def test_valid_relation_type(self):
        table = DecisionTable(
            name="link_check",
            hit_policy=HitPolicy.FIRST,
            rules=[
                Rule(
                    conditions=[
                        Condition("xdlink_relations", ComparisonOp.IN, [["replaces", "evidence"]]),
                    ],
                    outcome=Decision.PERMIT,
                ),
            ],
        )
        # This tests that xdlink_relations list contains valid types
        # For a simpler approach, test individual relation values
        table2 = DecisionTable(
            name="link_check_simple",
            hit_policy=HitPolicy.FIRST,
            rules=[
                Rule(
                    conditions=[Condition("has_replaces_link", ComparisonOp.EQ, True)],
                    outcome=Decision.DENY,
                    description="Supersession link requires review",
                ),
                Rule(conditions=[], outcome=Decision.PERMIT),
            ],
        )
        result = evaluate_decision_table(table2, {"has_replaces_link": True})
        assert result.decision == Decision.DENY

    def test_no_supersession_link_permits(self):
        table = DecisionTable(
            name="link_check",
            hit_policy=HitPolicy.FIRST,
            rules=[
                Rule(
                    conditions=[Condition("has_replaces_link", ComparisonOp.EQ, True)],
                    outcome=Decision.DENY,
                ),
                Rule(conditions=[], outcome=Decision.PERMIT),
            ],
        )
        result = evaluate_decision_table(table, {"has_replaces_link": False})
        assert result.decision == Decision.PERMIT


class TestBuildContext:
    """Build evaluation context from XML instances."""

    def test_context_from_instance(self):
        ctx = build_context_from_instance(
            str(FIXTURES / "instance-decision-context.xml")
        )
        assert ctx["instance_id"] == "cuid2-test-decision-001"
        assert ctx["current_state"] == "review"
        assert ctx["protocol"] == "HIPAA-compliant"
        assert "replaces" in ctx["xdlink_relations"]
        assert "evidence" in ctx["xdlink_relations"]

    def test_context_with_extra(self):
        ctx = build_context_from_instance(
            str(FIXTURES / "instance-decision-context.xml"),
            extra={"risk_score": 3, "attestation_level": "senior"},
        )
        assert ctx["risk_score"] == 3
        assert ctx["attestation_level"] == "senior"
        assert ctx["protocol"] == "HIPAA-compliant"

    def test_context_minimal_instance(self):
        ctx = build_context_from_instance(
            str(FIXTURES / "instance-no-audit.xml")
        )
        assert ctx.get("instance_id") == "cuid2-test-noaudit-001"
        assert "protocol" not in ctx
        assert "xdlink_relations" not in ctx


class TestDecisionTableDeterminism:
    """Same inputs must produce same results (Web3 requirement)."""

    def test_deterministic_evaluation(self):
        table = DecisionTable(
            name="determinism_test",
            hit_policy=HitPolicy.FIRST,
            rules=[
                Rule(
                    conditions=[Condition("x", ComparisonOp.GT, 5)],
                    outcome=Decision.PERMIT,
                ),
                Rule(conditions=[], outcome=Decision.DENY),
            ],
        )
        ctx = {"x": 7}
        r1 = evaluate_decision_table(table, ctx)
        r2 = evaluate_decision_table(table, ctx)
        r3 = evaluate_decision_table(table, ctx)
        assert r1.decision == r2.decision == r3.decision == Decision.PERMIT
        assert r1.matched_rules == r2.matched_rules == r3.matched_rules


class TestMultiConditionRules:
    """P5-02: Multi-condition rules with AND logic."""

    def test_risk_and_attestation(self):
        table = DecisionTable(
            name="compound_check",
            hit_policy=HitPolicy.FIRST,
            rules=[
                Rule(
                    conditions=[
                        Condition("risk_score", ComparisonOp.LT, 5),
                        Condition("attestation_level", ComparisonOp.EQ, "senior"),
                    ],
                    outcome=Decision.PERMIT,
                    description="Low risk + senior attestation",
                ),
                Rule(
                    conditions=[
                        Condition("risk_score", ComparisonOp.LT, 5),
                    ],
                    outcome=Decision.INDETERMINATE,
                    description="Low risk but no senior attestation",
                ),
                Rule(conditions=[], outcome=Decision.DENY),
            ],
        )

        # Both conditions met
        result = evaluate_decision_table(
            table, {"risk_score": 3, "attestation_level": "senior"}
        )
        assert result.decision == Decision.PERMIT

        # Only risk met
        result = evaluate_decision_table(
            table, {"risk_score": 3, "attestation_level": "junior"}
        )
        assert result.decision == Decision.INDETERMINATE

        # Neither met
        result = evaluate_decision_table(
            table, {"risk_score": 7, "attestation_level": "junior"}
        )
        assert result.decision == Decision.DENY

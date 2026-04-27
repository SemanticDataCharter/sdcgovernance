"""
DMN-based decision table evaluation for SDC governance.

Evaluates conditional governance rules using OMG Decision Model and
Notation (DMN) semantics. Enables governance rules that go beyond
simple state machine matching - conditional logic based on data
values, thresholds, combinations of conditions.

Decision tables are modeled as SDC components. sdcgovernance evaluates
instance content against the decision table conditions and returns
XACML decisions (PERMIT/DENY/INDETERMINATE).

Hit policies (subset of DMN):
- FIRST: return the first matching rule's outcome
- UNIQUE: exactly one rule must match (error if multiple match)
- COLLECT: return all matching rules (for multi-outcome evaluation)

This module is a critical foundation for the Web3 settlement layer
(Q4 2026 - Q1 2027) where smart contracts need deterministic,
standards-based decision logic that can be verified on-chain.

Standards: OMG DMN (https://www.omg.org/spec/DMN/)
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from sdcgovernance.receipts import Decision


class HitPolicy(Enum):
    """DMN hit policy - how to resolve when multiple rules match."""
    FIRST = "FIRST"       # Return first matching rule
    UNIQUE = "UNIQUE"     # Exactly one rule must match
    COLLECT = "COLLECT"   # Return all matching rules


class ComparisonOp(Enum):
    """Supported comparison operators for rule conditions."""
    EQ = "=="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    IN = "in"
    NOT_IN = "not_in"

    def evaluate(self, left: Any, right: Any) -> bool:
        """Evaluate the comparison."""
        ops: dict[str, Callable] = {
            "==": operator.eq,
            "!=": operator.ne,
            "<": operator.lt,
            "<=": operator.le,
            ">": operator.gt,
            ">=": operator.ge,
        }
        if self.value in ops:
            try:
                return ops[self.value](left, right)
            except TypeError:
                return False
        elif self.value == "in":
            return left in right
        elif self.value == "not_in":
            return left not in right
        return False


@dataclass
class Condition:
    """A single condition in a decision rule."""
    field: str              # field name to check (e.g., "risk_score", "protocol")
    op: ComparisonOp        # comparison operator
    value: Any              # value to compare against

    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate this condition against a context dict."""
        actual = context.get(self.field)
        if actual is None:
            return False
        return self.op.evaluate(actual, self.value)


@dataclass
class Rule:
    """A single rule in a decision table: conditions -> outcome."""
    conditions: list[Condition]
    outcome: Decision
    description: str = ""

    def evaluate(self, context: dict[str, Any]) -> bool:
        """True if all conditions match (AND logic)."""
        return all(c.evaluate(context) for c in self.conditions)


@dataclass
class DecisionTable:
    """
    A DMN-aligned decision table for governance evaluation.

    Contains a set of rules with conditions and outcomes. The hit policy
    determines how matches are resolved. Evaluation is deterministic:
    same inputs always produce the same result.
    """
    name: str = ""
    hit_policy: HitPolicy = HitPolicy.FIRST
    rules: list[Rule] = field(default_factory=list)
    description: str = ""


@dataclass
class DecisionResult:
    """Result of evaluating a decision table."""
    decision: Decision
    matched_rules: list[int] = field(default_factory=list)  # indices of matched rules
    reasoning: str = ""
    errors: list[str] = field(default_factory=list)


def evaluate_decision_table(
    table: DecisionTable,
    context: dict[str, Any],
) -> DecisionResult:
    """
    Evaluate a decision table against a context.

    The context is a dict of field names to values, extracted from the
    instance and DM root elements. For example:
    {
        "risk_score": 3,
        "attestation_level": "senior",
        "protocol": "HIPAA-compliant",
        "current_state": "review",
        "xdlink_relation": "replaces",
    }

    Args:
        table: The decision table to evaluate.
        context: Dict of field values from the instance.

    Returns:
        DecisionResult with XACML decision, matched rules, and reasoning.
    """
    matched: list[tuple[int, Rule]] = []

    for i, rule in enumerate(table.rules):
        if rule.evaluate(context):
            matched.append((i, rule))

    if not matched:
        return DecisionResult(
            decision=Decision.NOT_APPLICABLE,
            reasoning=f"No rules matched in decision table '{table.name}'",
        )

    if table.hit_policy == HitPolicy.FIRST:
        idx, rule = matched[0]
        return DecisionResult(
            decision=rule.outcome,
            matched_rules=[idx],
            reasoning=f"First matching rule (#{idx}): {rule.description}" if rule.description else f"First matching rule (#{idx})",
        )

    elif table.hit_policy == HitPolicy.UNIQUE:
        if len(matched) > 1:
            indices = [i for i, _ in matched]
            return DecisionResult(
                decision=Decision.INDETERMINATE,
                matched_rules=indices,
                reasoning=f"UNIQUE hit policy violated: {len(matched)} rules matched",
                errors=[
                    f"UNIQUE hit policy requires exactly 1 match, "
                    f"but {len(matched)} rules matched: {indices}"
                ],
            )
        idx, rule = matched[0]
        return DecisionResult(
            decision=rule.outcome,
            matched_rules=[idx],
            reasoning=f"Unique matching rule (#{idx}): {rule.description}" if rule.description else f"Unique matching rule (#{idx})",
        )

    elif table.hit_policy == HitPolicy.COLLECT:
        indices = [i for i, _ in matched]
        # For COLLECT, use the most restrictive outcome
        # DENY > INDETERMINATE > PERMIT
        outcomes = [rule.outcome for _, rule in matched]
        if Decision.DENY in outcomes:
            final = Decision.DENY
        elif Decision.INDETERMINATE in outcomes:
            final = Decision.INDETERMINATE
        else:
            final = Decision.PERMIT

        descriptions = [
            f"Rule #{i}: {r.description}" for i, r in matched if r.description
        ]
        return DecisionResult(
            decision=final,
            matched_rules=indices,
            reasoning=f"COLLECT: {len(matched)} rules matched, "
                      f"most restrictive outcome: {final.value}. "
                      + "; ".join(descriptions),
        )

    # Should not reach here
    return DecisionResult(
        decision=Decision.INDETERMINATE,
        errors=[f"Unknown hit policy: {table.hit_policy}"],
    )


def build_context_from_instance(
    instance_path: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a decision table evaluation context from an XML instance.

    Extracts DM root elements relevant to decision evaluation:
    - protocol value
    - current-state
    - XdLink relation types
    - instance_id, instance_version

    Additional context values can be passed via the extra dict.

    Args:
        instance_path: Path to the XML instance.
        extra: Additional context key-value pairs.

    Returns:
        Context dict for decision table evaluation.
    """
    from lxml import etree

    SDC4_NS = "https://semanticdatacharter.com/ns/sdc4/"

    tree = etree.parse(str(instance_path))
    root = tree.getroot()

    context: dict[str, Any] = {}

    # instance_id
    elem = root.find(f"{{{SDC4_NS}}}instance_id")
    if elem is None:
        elem = root.find("instance_id")
    if elem is not None and elem.text:
        context["instance_id"] = elem.text.strip()

    # current-state
    elem = root.find(f"{{{SDC4_NS}}}current-state")
    if elem is None:
        elem = root.find("current-state")
    if elem is not None and elem.text:
        context["current_state"] = elem.text.strip()

    # protocol (XdStringType - get the xdstring-value)
    elem = root.find(f"{{{SDC4_NS}}}protocol")
    if elem is None:
        elem = root.find("protocol")
    if elem is not None:
        val = elem.find(f"{{{SDC4_NS}}}xdstring-value")
        if val is None:
            val = elem.find("xdstring-value")
        if val is not None and val.text:
            context["protocol"] = val.text.strip()

    # XdLink relations (collect all)
    xdlink_relations = []
    for link_elem in root.findall(f"{{{SDC4_NS}}}XdLink"):
        rel = link_elem.find(f"{{{SDC4_NS}}}relation")
        if rel is None:
            rel = link_elem.find("relation")
        if rel is not None and rel.text:
            xdlink_relations.append(rel.text.strip())
    if not xdlink_relations:
        for link_elem in root.findall("XdLink"):
            rel = link_elem.find("relation")
            if rel is not None and rel.text:
                xdlink_relations.append(rel.text.strip())
    if xdlink_relations:
        context["xdlink_relations"] = xdlink_relations

    # Merge extra context
    if extra:
        context.update(extra)

    return context

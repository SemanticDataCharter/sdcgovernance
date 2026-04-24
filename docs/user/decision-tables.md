# Decision Tables (DMN)

Evaluates conditional governance rules using OMG Decision Model and Notation (DMN) semantics. Enables governance logic beyond simple state matching - conditional rules based on data values, thresholds, and combinations.

Critical foundation for the Web3 settlement layer where smart contracts need deterministic, standards-based decision logic.

## Decision Table Structure

A decision table contains rules. Each rule has conditions (all must match - AND logic) and an outcome (PERMIT/DENY/INDETERMINATE).

```python
from sdcgovernance.decision import (
    DecisionTable, Rule, Condition, ComparisonOp, HitPolicy,
    evaluate_decision_table,
)
from sdcgovernance.receipts import Decision

table = DecisionTable(
    name="risk_assessment",
    hit_policy=HitPolicy.FIRST,
    rules=[
        Rule(
            conditions=[Condition("risk_score", ComparisonOp.GE, 8)],
            outcome=Decision.DENY,
            description="High risk",
        ),
        Rule(
            conditions=[Condition("risk_score", ComparisonOp.GE, 5)],
            outcome=Decision.INDETERMINATE,
            description="Medium risk - escalate",
        ),
        Rule(
            conditions=[Condition("risk_score", ComparisonOp.LT, 5)],
            outcome=Decision.PERMIT,
            description="Low risk",
        ),
    ],
)
```

## Comparison Operators

| Operator | Symbol | Example |
|---|---|---|
| `ComparisonOp.EQ` | `==` | `field == "active"` |
| `ComparisonOp.NE` | `!=` | `field != "blocked"` |
| `ComparisonOp.LT` | `<` | `score < 5` |
| `ComparisonOp.LE` | `<=` | `score <= 5` |
| `ComparisonOp.GT` | `>` | `score > 5` |
| `ComparisonOp.GE` | `>=` | `score >= 5` |
| `ComparisonOp.IN` | `in` | `role in ["admin", "approver"]` |
| `ComparisonOp.NOT_IN` | `not_in` | `role not in ["blocked"]` |

## Hit Policies

| Policy | Behavior |
|---|---|
| `FIRST` | Return the first matching rule's outcome |
| `UNIQUE` | Exactly one rule must match. Multiple matches = INDETERMINATE + error |
| `COLLECT` | All matching rules evaluated. Most restrictive outcome wins (DENY > INDETERMINATE > PERMIT) |

## Evaluating a Decision Table

```python
context = {"risk_score": 3, "attestation_level": "senior"}
result = evaluate_decision_table(table, context)

print(result.decision)       # Decision.PERMIT
print(result.matched_rules)  # [2]
print(result.reasoning)      # "First matching rule (#2): Low risk"
```

## Multi-Condition Rules

All conditions in a rule use AND logic:

```python
Rule(
    conditions=[
        Condition("risk_score", ComparisonOp.LT, 5),
        Condition("attestation_level", ComparisonOp.EQ, "senior"),
    ],
    outcome=Decision.PERMIT,
    description="Low risk AND senior attestation required",
)
```

## DM.protocol as Decision Input

```python
Rule(
    conditions=[Condition("protocol", ComparisonOp.EQ, "HIPAA-compliant")],
    outcome=Decision.PERMIT,
    description="Only HIPAA-compliant protocols allowed",
)
```

## Building Context from Instances

```python
from sdcgovernance.decision import build_context_from_instance

# Extracts: instance_id, current_state, protocol, xdlink_relations
context = build_context_from_instance("instance.xml")

# Add extra context from agent logic
context = build_context_from_instance(
    "instance.xml",
    extra={"risk_score": 3, "attestation_level": "senior"},
)
```

## JSON Format for MCP

Decision tables can be passed as JSON via the MCP `evaluate_decision` tool:

```json
{
    "name": "risk_check",
    "hit_policy": "FIRST",
    "rules": [
        {
            "conditions": [{"field": "risk_score", "op": ">=", "value": 8}],
            "outcome": "DENY",
            "description": "High risk"
        },
        {
            "conditions": [{"field": "risk_score", "op": "<", "value": 8}],
            "outcome": "PERMIT",
            "description": "Acceptable risk"
        }
    ]
}
```

## Determinism

Same inputs always produce the same result. This is required for Web3 settlement where smart contracts verify decision logic on-chain.

```python
r1 = evaluate_decision_table(table, {"risk_score": 7})
r2 = evaluate_decision_table(table, {"risk_score": 7})
assert r1.decision == r2.decision
assert r1.matched_rules == r2.matched_rules
```

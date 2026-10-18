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

## Table Identity: Content Hash

Every table has a content hash: the SHA-256 of its RFC 8785 canonical JSON, the same convention as `receipt_hash` and `evidence_pack_hash`. Two spellings of one table (key order, whitespace, a description left out) hash the same; one changed threshold does not.

```python
from sdcgovernance.decision import decision_table_hash, decision_table_to_dict

decision_table_hash(table)      # "e2d2173c..." (64 hex characters)
decision_table_to_dict(table)   # the JSON form that was hashed
```

## The Registry

A `TableRegistry` holds tables under a stable id and an immutable version, each with its content hash and an optional domain and policy label. Registering the same content again under the same id and version is a no-op; different content under an existing id and version is refused, so a version means one thing forever. `get` without a version returns the highest (numeric dotted versions compare numerically, so `1.10` follows `1.9`).

```python
from sdcgovernance import TableRegistry

registry = TableRegistry()
entry = registry.register("cordova.access-control", "1.0", table, domain="access-control", policy="POL-7")
entry.table_hash                              # content hash
registry.get("cordova.access-control")         # highest version
registry.get("cordova.access-control", "1.0")  # pinned
registry.versions("cordova.access-control")    # ["1.0"]
registry.list(domain="access-control")
registry.find_by_hash(entry.table_hash)        # resolve a receipt's table_hash
```

A registry is saved to and loaded from a directory, one JSON file per table version (`<table_id>--<version>.json`), so a deployment's policies are files under version control:

```python
registry.save("policies/")
registry = TableRegistry.from_directory("policies/")
```

Loading checks each file's recorded `table_hash` against its content; a file edited after registration is refused.

## Receipts Name the Policy

A Receipt produced by evaluating a table carries `table_hash`, and `table_id` and `table_version` when the table came from the registry. All three are inside `receipt_hash`, so the receipt binds evidence (`context_hash`), policy, decision and outcome; two different tables that reach the same decision on the same evidence produce different receipts, and the policy version that applied is provable later. Receipts issued before 4.3.0 carry no table fields and verify exactly as they did.

```python
from sdcgovernance import ReceiptChain

chain = ReceiptChain()
chain.append(result.decision, reasoning=result.reasoning,
             table_id=entry.table_id, table_version=entry.version, table_hash=entry.table_hash)
```

## JSON Format for MCP

Over MCP, `evaluate_decision` names a registered table with `table_id` (and `table_version`; the highest registered version when omitted) or takes one inline as `table_json`. `register_decision_table` and `list_decision_tables` manage the registry; the server loads and persists it in the directory given by `--tables-dir` or `SDCGOVERNANCE_TABLES_DIR`. The inline form:

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

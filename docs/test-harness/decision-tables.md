# Decision Table Tests - OMG DMN Compliance

**Standard**: OMG DMN (Decision Model and Notation)
**Module**: `sdcgovernance/decision.py`
**Tests**: 33

## Condition Operators

All comparison operators tested individually:

| Operator | Test | Input | Result |
|---|---|---|---|
| `==` | `status == "active"` | `{"status": "active"}` | True |
| `==` | `status == "active"` | `{"status": "inactive"}` | False |
| `!=` | `status != "blocked"` | `{"status": "active"}` | True |
| `<` | `risk_score < 5` | `{"risk_score": 3}` | True |
| `<` | `risk_score < 5` | `{"risk_score": 5}` | False |
| `<=` | `risk_score <= 5` | `{"risk_score": 5}` | True |
| `>` | `risk_score > 5` | `{"risk_score": 7}` | True |
| `>=` | `risk_score >= 5` | `{"risk_score": 5}` | True |
| `in` | `role in ["admin", "approver"]` | `{"role": "admin"}` | True |
| `not_in` | `role not_in ["blocked"]` | `{"role": "admin"}` | True |
| missing field | `missing == "value"` | `{"other": "value"}` | False |
| type mismatch | `score < 5` | `{"score": "text"}` | False |

## Hit Policy: FIRST

Returns the first matching rule.

**Decision table**: risk_assessment

| Rule | Condition | Outcome |
|---|---|---|
| 0 | risk_score >= 8 | DENY |
| 1 | risk_score >= 5 | INDETERMINATE |
| 2 | risk_score < 5 | PERMIT |

| Input | Matched Rule | Decision |
|---|---|---|
| `{"risk_score": 9}` | 0 | DENY |
| `{"risk_score": 6}` | 1 | INDETERMINATE |
| `{"risk_score": 3}` | 2 | PERMIT |
| `{"risk_score": 9}` (matches 0 AND 1) | 0 only | DENY (first hit) |

## Hit Policy: UNIQUE

Exactly one rule must match. Multiple matches = INDETERMINATE + error.

| Input | Matched Rules | Decision | Error |
|---|---|---|---|
| `{"status": "active"}` | [0] | PERMIT | - |
| `{"status": "unknown"}` | [] | INDETERMINATE | "No rules matched" |
| `{"x": 5}` (matches 2 overlapping rules) | [0, 1] | INDETERMINATE | "UNIQUE hit policy requires exactly 1 match, but 2 rules matched" |

## Hit Policy: COLLECT

All matching rules evaluated. Most restrictive outcome wins (DENY > INDETERMINATE > PERMIT).

| Input | Matched Rules | Outcomes | Final Decision |
|---|---|---|---|
| `{"has_attestation": True, "risk_score": 9}` | [0, 1] | [PERMIT, DENY] | DENY |
| `{"a": True, "b": True}` | [0, 1] | [PERMIT, PERMIT] | PERMIT |

## Multi-Condition Rules (AND logic)

| Conditions | Input | Match |
|---|---|---|
| `risk_score < 5 AND attestation_level == "senior"` | `{risk: 3, att: "senior"}` | True -> PERMIT |
| `risk_score < 5 AND attestation_level == "senior"` | `{risk: 3, att: "junior"}` | False |
| Empty conditions `[]` | `{}` | True (always matches) |

## DM.protocol as Input (P5-04)

| Protocol Value | Rule | Decision |
|---|---|---|
| "HIPAA-compliant" | `protocol == "HIPAA-compliant"` -> PERMIT | PERMIT |
| "internal-only" | Falls through to default DENY | DENY |
| absent | Falls through to default DENY | DENY |

## Determinism (Web3 Foundation)

```python
def test_deterministic_evaluation():
    ctx = {"x": 7}
    r1 = evaluate_decision_table(table, ctx)
    r2 = evaluate_decision_table(table, ctx)
    r3 = evaluate_decision_table(table, ctx)
    assert r1.decision == r2.decision == r3.decision == Decision.PERMIT
    assert r1.matched_rules == r2.matched_rules == r3.matched_rules
```

**Result**: Same inputs always produce the same decision and matched rules. Required for Web3 settlement verification.

## Context Building from Instances

**Input**: `instance-decision-context.xml`

| Extracted Field | Value |
|---|---|
| `instance_id` | "cuid2-test-decision-001" |
| `current_state` | "review" |
| `protocol` | "HIPAA-compliant" |
| `xdlink_relations` | ["replaces", "evidence"] |

Extra context can be merged: `{"risk_score": 3, "attestation_level": "senior"}`

# Workflow Tests - W3C SCXML Vocabulary Compliance

**Standard**: W3C SCXML (State Chart XML) - vocabulary only
**Structure**: SDC native (XdOrdinal components in ClusterType paths)
**Module**: `sdcgovernance/workflow.py`, `sdcgovernance/engine.py`
**Tests**: 28

## Workflow Architecture

The workflow state machine is modeled as a ClusterType tree using SDC native structures. Labels use W3C SCXML vocabulary for interoperability. Validation is ordinal adjacency checking - no external state machine parser needed.

## Test Fixtures

### Linear Workflow (instance-linear-workflow.xml)

```
Path: Main Path
  ordinal=0, symbol="draft"     (Initial State)
  ordinal=1, symbol="review"    (Review State)
  ordinal=2, symbol="approved"  (Approved State)
  ordinal=3, symbol="published" (Published State)

current-state: "draft"
```

### Branching Workflow (instance-branching-workflow.xml)

```
Path: Approval Path
  ordinal=0, symbol="draft"      (shared)
  ordinal=1, symbol="review"     (shared)
  ordinal=2, symbol="approved"
  ordinal=3, symbol="published"

Path: Rejection Path
  ordinal=0, symbol="draft"      (shared)
  ordinal=1, symbol="review"     (shared)
  ordinal=2, symbol="rejected"
  ordinal=3, symbol="archived"

current-state: "review"
```

## Extraction Tests

### Test: Linear workflow extraction

```python
def test_linear_workflow():
    current_state, tree = extract_workflow_from_instance("instance-linear-workflow.xml")
    assert current_state == "draft"
    assert len(tree.paths) == 1
    assert len(tree.paths[0].states) == 4

def test_linear_workflow_states():
    _, tree = extract_workflow_from_instance("instance-linear-workflow.xml")
    states = tree.paths[0].state_symbols
    assert states == ["draft", "review", "approved", "published"]
```

**Result**: Four states extracted in ordinal order from a single path.

### Test: Branching workflow extraction

```python
def test_branching_workflow():
    current_state, tree = extract_workflow_from_instance("instance-branching-workflow.xml")
    assert current_state == "review"
    assert len(tree.paths) == 2
```

**Result**: Two paths extracted from two sub-clusters.

## Ordinal Adjacency Validation

### Test: Valid transition (adjacent ordinal)

```python
def test_single_path():
    tree = WorkflowTree(paths=[WorkflowPath(states=[
        WorkflowState(ordinal=0, symbol="draft"),
        WorkflowState(ordinal=1, symbol="review"),
        WorkflowState(ordinal=2, symbol="approved"),
    ])])
    assert tree.is_valid_transition("draft", "review")      # ordinal 0->1: VALID
    assert tree.is_valid_transition("review", "approved")    # ordinal 1->2: VALID
```

### Test: Skip transition denied

```python
    assert not tree.is_valid_transition("draft", "approved") # ordinal 0->2: DENIED (skip)
```

**Result**: Transitions must be to the next ordinal position. Skipping states is DENY.

### Test: Reverse transition denied

```python
    assert not tree.is_valid_transition("approved", "draft") # ordinal 2->0: DENIED (reverse)
```

**Result**: Backward transitions are DENY. Ordinal adjacency is forward-only.

## Branching Path Validation

### Test: Both branches valid from shared state

```python
def test_branching_paths():
    tree = WorkflowTree(paths=[approval_path, rejection_path])
    allowed = tree.get_allowed_transitions("review")
    symbols = {t["target_symbol"] for t in allowed}
    assert symbols == {"approved", "rejected"}
```

**Result**: From a shared state ("review"), both path targets are valid transitions.

### Test: Transition includes path info

```python
def test_transition_includes_path_info():
    allowed = tree.get_allowed_transitions("draft")
    assert allowed[0]["target_symbol"] == "review"
    assert allowed[0]["target_ordinal"] == 1.0
    assert "approval_path" in allowed[0]["paths"]
```

**Result**: Each allowed transition reports which path(s) it belongs to.

## GovernanceEngine Integration

### Test: PERMIT on valid transition

```python
def test_evaluate_valid_transition(engine, linear_tree):
    result = engine.evaluate_transition(
        current_state="draft", target_state="review",
        instance_id="test-001", workflow_tree=linear_tree,
    )
    assert result.decision == Decision.PERMIT
    assert result.receipt.instance_id == "test-001"
```

**Result**: Valid transition returns XACML PERMIT with hash-chained receipt bound to instance_id.

### Test: DENY on skip transition

```python
def test_evaluate_invalid_transition_skip(engine, linear_tree):
    result = engine.evaluate_transition(
        current_state="draft", target_state="approved", workflow_tree=linear_tree,
    )
    assert result.decision == Decision.DENY
    assert len(result.errors) > 0
```

**Result**: `["Invalid transition: 'draft' -> 'approved'", "Valid transitions from 'draft': ['review']"]`

### Test: DENY includes valid alternatives

```python
def test_deny_includes_valid_alternatives(engine, branching_tree):
    result = engine.evaluate_transition(
        current_state="review", target_state="published", workflow_tree=branching_tree,
    )
    assert result.decision == Decision.DENY
    assert any("approved" in e or "rejected" in e for e in result.errors)
```

**Result**: DENY response tells the agent what the valid options are.

### Test: Receipt chain accumulates

```python
def test_receipt_chain_accumulates(engine, linear_tree):
    engine.evaluate_transition("draft", "review", workflow_tree=linear_tree)
    engine.evaluate_transition("review", "approved", workflow_tree=linear_tree)
    engine.evaluate_transition("approved", "draft", workflow_tree=linear_tree)  # DENY

    assert engine.receipt_chain.length == 3
    assert engine.receipt_chain.verify_chain() is True
    assert engine.receipt_chain.receipts[0].decision == Decision.PERMIT
    assert engine.receipt_chain.receipts[1].decision == Decision.PERMIT
    assert engine.receipt_chain.receipts[2].decision == Decision.DENY
```

**Result**: Three governance decisions produce a tamper-evident receipt chain with mixed PERMIT/DENY outcomes.

## Standards Mapping Summary

| SCXML Concept | SDC Implementation |
|---|---|
| State | XdOrdinal component with ordinal position and SCXML-labeled symbol |
| Transition | Ordinal adjacency (N to N+1) within a cluster path |
| Parallel states | Multiple sub-clusters in the Workflow cluster |
| State machine | Cluster tree structure (no external SCXML parser needed) |

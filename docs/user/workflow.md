# Workflow Validation

Workflow states are modeled as XdOrdinal components within sub-clusters of a Workflow cluster. Each sub-cluster defines a valid path. Validation is ordinal adjacency checking within the cluster tree.

## How Workflow is Modeled

The `DM.workflow` element is a ClusterType containing sub-clusters (valid paths). Each sub-cluster contains XdOrdinal components defining the sequenced states in that path.

```
DM.workflow (ClusterType)
  +-- sub-cluster: "Approval Path"
  |     +-- XdOrdinal: ordinal=0, symbol="draft"
  |     +-- XdOrdinal: ordinal=1, symbol="review"
  |     +-- XdOrdinal: ordinal=2, symbol="approved"
  |     +-- XdOrdinal: ordinal=3, symbol="published"
  +-- sub-cluster: "Rejection Path"
        +-- XdOrdinal: ordinal=0, symbol="draft"
        +-- XdOrdinal: ordinal=1, symbol="review"
        +-- XdOrdinal: ordinal=2, symbol="rejected"
        +-- XdOrdinal: ordinal=3, symbol="archived"
```

**Branching**: Multiple sub-clusters = multiple valid paths. Components with the same symbol (e.g., "draft", "review") represent shared states across paths.

**Ordinal adjacency**: A transition is valid only if the target state is at ordinal position N+1 from the current state in at least one valid path. Skipping states or reversing is DENY.

**SCXML vocabulary**: Labels on XdOrdinal components and clusters use W3C SCXML terms for interoperability.

## Extracting Workflow from an Instance

```python
from sdcgovernance.workflow import extract_workflow_from_instance

current_state, workflow_tree = extract_workflow_from_instance("instance.xml")
print(current_state)        # "draft"
print(len(workflow_tree.paths))  # number of valid paths
```

The instance carries:
- `DM.current-state` - the current workflow position (e.g., "draft")
- `DM.workflow` - the cluster tree defining valid paths

## Querying Allowed Transitions

```python
allowed = workflow_tree.get_allowed_transitions("draft")
# [{"target_symbol": "review", "target_label": "Review State",
#   "target_ordinal": 1.0, "paths": ["Main Path"]}]
```

For branching workflows, multiple targets may be returned:

```python
allowed = workflow_tree.get_allowed_transitions("review")
# [{"target_symbol": "approved", ..., "paths": ["Approval Path"]},
#  {"target_symbol": "rejected", ..., "paths": ["Rejection Path"]}]
```

## Validating a Transition

```python
assert workflow_tree.is_valid_transition("draft", "review")      # True
assert not workflow_tree.is_valid_transition("draft", "approved") # False (skip)
assert not workflow_tree.is_valid_transition("review", "draft")   # False (reverse)
```

## Via GovernanceEngine

```python
from sdcgovernance import GovernanceEngine

engine = GovernanceEngine("model.xsd")
result = engine.evaluate_transition(
    current_state="draft",
    target_state="review",
    instance_id="cuid2-abc123",
    workflow_tree=workflow_tree,
)
print(result.decision)  # Decision.PERMIT
print(result.receipt)   # Hash-chained receipt with reasoning
```

On DENY, the result includes valid alternatives:

```python
result = engine.evaluate_transition(
    current_state="draft",
    target_state="published",  # not adjacent
    workflow_tree=workflow_tree,
)
print(result.decision)  # Decision.DENY
print(result.errors)
# ["Invalid transition: 'draft' -> 'published'",
#  "Valid transitions from 'draft': ['review']"]
```

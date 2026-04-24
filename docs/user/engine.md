# GovernanceEngine

The GovernanceEngine is the stateful advisory core that agents interact with. It wraps model inspection, workflow validation, and receipt chain management into a single session-aware interface.

## Creating an Engine

```python
from sdcgovernance import GovernanceEngine

engine = GovernanceEngine("path/to/model.xsd")
```

The engine:
- Inspects the model once and caches the results
- Maintains a receipt chain across multiple calls
- Provides the advisory API: what can I do, can I do this, what happened

## Properties

```python
engine.model              # GovernanceModel (cached inspection result)
engine.has_governance      # True if model defines any governance
engine.receipt_chain       # ReceiptChain (session audit trail)
```

## Methods

### get_governance_status()

```python
status = engine.get_governance_status()
# {
#     "model_id": "dm-healthcare-abc123",
#     "model_label": "Healthcare Record",
#     "has_governance": True,
#     "dimensions": {"workflow": True, "audit": True, ...}
# }
```

### get_allowed_transitions()

```python
from sdcgovernance.workflow import extract_workflow_from_instance

current_state, tree = extract_workflow_from_instance("instance.xml")
allowed = engine.get_allowed_transitions(current_state, tree)
# [{"target_symbol": "review", "target_ordinal": 1.0, "paths": ["Main Path"]}]
```

### evaluate_transition()

```python
result = engine.evaluate_transition(
    current_state="draft",
    target_state="review",
    actor="dr_smith",
    instance_id="cuid2-abc123",
    instance_version="1",
    workflow_tree=tree,
)
print(result.decision)   # Decision.PERMIT or Decision.DENY
print(result.receipt)    # Hash-chained receipt
print(result.errors)     # [] on PERMIT, details on DENY
```

## Receipt Chain

Every call to `evaluate_transition` appends a receipt to the session chain:

```python
engine.evaluate_transition("draft", "review", workflow_tree=tree)
engine.evaluate_transition("review", "approved", workflow_tree=tree)
engine.evaluate_transition("approved", "draft", workflow_tree=tree)  # DENY

chain = engine.receipt_chain
print(chain.length)          # 3
print(chain.verify_chain())  # True (intact)

for r in chain.receipts:
    print(f"{r.decision.value}: {r.reasoning}")
```

The receipt chain provides a tamper-evident audit trail of all governance decisions within a session. Each receipt contains a SHA-256 hash linking to the previous receipt.

## Agent Interaction Pattern

```
Agent receives a task
  --> engine.get_governance_status(): "what governance exists?"
  --> engine.get_allowed_transitions(): "what can I do next?"
  --> engine.evaluate_transition(): "can I do this specific thing?"
  --> if PERMIT: agent performs the action
  --> if DENY: agent reports the refusal
  --> if INDETERMINATE: agent requests human review
  --> record_provenance(): "here's what I did"
```

The engine advises. The agent decides what happens after the decision. The operational response to DENY or INDETERMINATE is the customer's business logic.

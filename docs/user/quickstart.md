# Quick Start

## 1. Inspect a model for governance

```python
from sdcgovernance import inspect_model

model = inspect_model("path/to/model.xsd")

print(model.has_governance)        # True if any governance dimension is active
print(model.active_dimensions)     # {'workflow': True, 'audit': True, ...}
print(model.model_label)           # "Healthcare Record"
```

## 2. Validate governance (one-shot)

```python
from sdcgovernance import validate_governance

result = validate_governance("model.xsd", "instance.xml")

print(result.decision)             # Decision.PERMIT, Decision.DENY, or Decision.INDETERMINATE
print(result.has_governance)       # True if model defines governance
print(result.errors)               # [] on PERMIT, error list on DENY
print(result.dimensions_validated) # {'workflow': True, 'audit': True, ...}
```

## 3. Use the GovernanceEngine (conversational)

For agentic workflows where multiple governance calls happen during a single workflow:

```python
from sdcgovernance import GovernanceEngine
from sdcgovernance.workflow import extract_workflow_from_instance

# Initialize engine (caches model inspection)
engine = GovernanceEngine("model.xsd")

# Check what governance exists
status = engine.get_governance_status()
print(status["dimensions"])

# Extract workflow from instance
current_state, workflow_tree = extract_workflow_from_instance("instance.xml")

# Ask: what can I do from here?
allowed = engine.get_allowed_transitions(current_state, workflow_tree)
for t in allowed:
    print(f"  Can transition to: {t['target_symbol']} via {t['paths']}")

# Ask: can I do this specific thing?
result = engine.evaluate_transition(
    current_state=current_state,
    target_state="approved",
    actor="dr_smith",
    instance_id="cuid2-abc123",
    workflow_tree=workflow_tree,
)
print(result.decision)  # PERMIT or DENY
print(result.receipt)   # Hash-chained receipt

# The receipt chain accumulates across calls
print(engine.receipt_chain.length)
print(engine.receipt_chain.verify_chain())  # True if intact
```

## 4. Record provenance

```python
from sdcgovernance.provenance import record_provenance, provenance_to_rdf

rec = record_provenance(
    activity_type="Update",
    agent_name="Dr. Smith",
    entity_id="cuid2-abc123",
    system_id="sdc-studio-cloud",
    description="Approved patient encounter after review",
)

# Export as RDF/Turtle
turtle = provenance_to_rdf([rec], instance_id="cuid2-abc123")
print(turtle)
```

## 5. Start the MCP server

```bash
sdcgovernance serve --mcp
```

Any agent that speaks MCP can now query governance tools via JSON-RPC 2.0 over stdio. See [MCP Server](mcp-server.md) for tool details.

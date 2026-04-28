# Architecture

## Data Flow

```
SDC Data Model (XSD)
        |
        v
  model_inspector.py
  (reads DMType root slots)
        |
        v
  GovernanceModel
  (which dimensions are active)
        |
        v
  GovernanceEngine
  (caches model, maintains receipt chain)
        |
        +-- workflow.py        (cluster tree, ordinal adjacency)
        +-- attestation.py     (AttestationType content)
        +-- party_role.py      (subject, provider, participation)
        +-- provenance.py      (AuditType, retention, PROV-O)
        +-- decision.py        (DMN tables, condition evaluation)
        +-- shacl_runtime.py   (cross-entity constraints)
        |
        v
  GovernanceResult
  (XACML decision + receipt)
        |
        v
  ReceiptChain
  (SHA-256 hash-linked audit trail)
```

## Two Interfaces

```
Python API                      MCP Server (JSON-RPC 2.0 stdio)
     |                                    |
     v                                    v
GovernanceEngine  <---------->  mcp_server.py
                                (same engine, different interface)
```

## Module Responsibilities

### model_inspector.py

Reads the XSD model once. Detects governance by checking known DMType root positions:

```python
# Elements checked by name=
"workflow", "current-state", "subject", "provider", "protocol", "acs", "attestation"

# Elements checked by ref=
"sdc4:Audit", "sdc4:Participation", "sdc4:XdLink"
```

Returns a `GovernanceModel` dataclass. No XML instance needed.

### engine.py

Wraps model_inspector and validation modules. Stateful:
- Caches `GovernanceModel` from model inspection
- Maintains `ReceiptChain` across multiple advisory calls
- Provides the API agents interact with

One engine per schema. Create a new engine for a different model.

### receipts.py

Three core types:
- `Decision` enum: PERMIT, DENY, INDETERMINATE (XACML)
- `Receipt`: single decision record with SHA-256 hash
- `ReceiptChain`: append-only linked list of receipts

The receipt hash covers: decision, reasoning, instance_id, instance_version, timestamp, previous_hash, dimensions_checked, errors. Changing any field invalidates the hash.

### workflow.py

Two extraction paths:
1. `extract_workflow_from_model()` - reads workflow definition from XSD
2. `extract_workflow_from_instance()` - reads workflow state from XML instance

Returns `WorkflowTree` with `WorkflowPath` list, each containing `WorkflowState` objects with ordinal position and symbol.

Transition validation: ordinal N to N+1 in at least one valid path.

### mcp_server.py

Raw JSON-RPC 2.0. No SDK. Handles:
- `initialize` - server capabilities
- `notifications/initialized` - client acknowledgment (no response)
- `tools/list` - 6 tool definitions with inputSchema
- `tools/call` - dispatches to tool handlers
- `ping` - keepalive

All tools return `{"content": [{"type": "text", "text": "...JSON..."}]}`. Consistent format.

## Design Principles

1. **Known positions, not search.** Governance slots are at fixed DMType positions.
2. **Standards concepts, not custom.** XACML decisions, SCXML state/transition concepts, PROV-O records.
3. **Independent dimensions.** Adding attestation doesn't affect workflow validation.
4. **Advise, don't enforce.** The engine returns decisions. The agent acts on them.
5. **Deterministic.** Same inputs produce same outputs. Required for Web3.
6. **Append-only audit.** Receipts cannot be modified after creation.

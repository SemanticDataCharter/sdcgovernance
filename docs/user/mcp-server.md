# MCP Server

sdcgovernance exposes all governance tools via a JSON-RPC 2.0 stdio server implementing the Model Context Protocol (MCP). Any agent that speaks MCP can connect and use governance without importing the Python library.

**No external MCP SDK dependency.** The server implements JSON-RPC 2.0 directly - simple, reliable, no third-party serialization surprises.

## Starting the Server

```bash
sdcgovernance serve --mcp
```

The server reads JSON-RPC 2.0 messages from stdin (one per line) and writes responses to stdout.

## MCP Protocol Flow

```
Agent                          sdcgovernance
  |                                 |
  |------ initialize -------------->|
  |<----- capabilities + info ------|
  |                                 |
  |------ tools/list -------------->|
  |<----- 6 tool definitions ------|
  |                                 |
  |------ tools/call -------------->|
  |       (get_governance_status)   |
  |<----- result ------------------|
  |                                 |
  |------ tools/call -------------->|
  |       (evaluate_transition)     |
  |<----- PERMIT/DENY + receipt ---|
  |                                 |
```

## Available Tools

### get_governance_status

Report which governance dimensions the model defines.

**Input:**
```json
{"schema_path": "path/to/model.xsd"}
```

**Output:**
```json
{
    "model_id": "dm-healthcare-abc123",
    "model_label": "Healthcare Record",
    "has_governance": true,
    "dimensions": {
        "workflow": true,
        "audit": true,
        "attestation": true,
        "party_role": true,
        "protocol": false,
        "acs": false,
        "xdlink": false
    }
}
```

### get_allowed_transitions

Get valid next states from the current workflow state.

**Input:**
```json
{
    "schema_path": "model.xsd",
    "instance_path": "instance.xml"
}
```

**Output:**
```json
[
    {
        "target_symbol": "approved",
        "target_label": "Approved State",
        "target_ordinal": 2.0,
        "paths": ["Approval Path"]
    },
    {
        "target_symbol": "rejected",
        "target_label": "Rejected State",
        "target_ordinal": 2.0,
        "paths": ["Rejection Path"]
    }
]
```

### evaluate_transition

Evaluate whether a specific workflow transition is permitted.

**Input:**
```json
{
    "schema_path": "model.xsd",
    "instance_path": "instance.xml",
    "target_state": "approved",
    "actor": "dr_smith"
}
```

**Output (PERMIT):**
```json
{
    "decision": "PERMIT",
    "has_governance": true,
    "errors": [],
    "receipt": {
        "decision": "PERMIT",
        "reasoning": "Transition 'review' -> 'approved' is valid in path(s): ['Approval Path']",
        "instance_id": "cuid2-abc123",
        "receipt_hash": "a1b2c3...",
        "previous_hash": null
    },
    "dimensions_validated": {"workflow": true}
}
```

**Output (DENY):**
```json
{
    "decision": "DENY",
    "has_governance": true,
    "errors": [
        "Invalid transition: 'draft' -> 'published'",
        "Valid transitions from 'draft': ['review']"
    ],
    "receipt": { ... },
    "dimensions_validated": {"workflow": true}
}
```

### validate_governance

Full governance validation of an instance against its model.

**Input:**
```json
{
    "schema_path": "model.xsd",
    "instance_path": "instance.xml"
}
```

### record_provenance

Record a provenance event as a W3C PROV-O record.

**Input:**
```json
{
    "activity_type": "Update",
    "agent_name": "Dr. Smith",
    "entity_id": "cuid2-abc123",
    "system_id": "sdc-studio-cloud",
    "description": "Approved patient encounter"
}
```

**Output:**
```json
{
    "activity_type": "Update",
    "agent_name": "Dr. Smith",
    "entity_id": "cuid2-abc123",
    "started_at": "2026-04-24T10:30:00+00:00",
    "ended_at": "2026-04-24T10:30:00+00:00",
    "system_id": "sdc-studio-cloud",
    "description": "Approved patient encounter"
}
```

### evaluate_decision

Evaluate a DMN decision table against instance context.

**Input:**
```json
{
    "instance_path": "instance.xml",
    "table_json": "{\"name\": \"risk_check\", \"hit_policy\": \"FIRST\", \"rules\": [{\"conditions\": [{\"field\": \"risk_score\", \"op\": \">=\", \"value\": 8}], \"outcome\": \"DENY\"}, {\"conditions\": [], \"outcome\": \"PERMIT\"}]}",
    "extra_context": "{\"risk_score\": 3}"
}
```

**Output:**
```json
{
    "decision": "PERMIT",
    "matched_rules": [1],
    "reasoning": "First matching rule (#1)",
    "errors": []
}
```

## JSON-RPC 2.0 Format

Every request:
```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "tool_name", "arguments": {...}}}
```

Every response:
```json
{"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "...JSON..."}]}}
```

All tools return exactly one content block with `type: "text"` containing a JSON string. Consistent serialization, no format surprises.

## Connecting from Agent Frameworks

Any agent that can spawn a subprocess and communicate via stdio JSON-RPC can use sdcgovernance. No SDK, no client library, no protocol negotiation beyond the standard MCP handshake.

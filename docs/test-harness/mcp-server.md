# MCP Server Tests

**Protocol**: JSON-RPC 2.0 over stdio (MCP)
**Module**: `sdcgovernance/mcp_server.py`
**Tests**: 24

## Protocol Tests

| Request Method | Response | Verified |
|---|---|---|
| `initialize` | Server info + capabilities | serverInfo.name == "sdcgovernance", tools capability present |
| `notifications/initialized` | None (notification) | No response returned |
| `tools/list` | 6 tool definitions | All names present, all have inputSchema |
| `ping` | Empty result | Response with matching id |
| Unknown method | JSON-RPC error -32601 | "Method not found" |
| Unknown tool | JSON-RPC error -32601 | "Unknown tool" |

## Consistent Serialization

Every tool returns exactly one content block with `type: "text"` containing valid JSON:

```python
def test_all_tools_return_single_text_content():
    for tool_name, args in test_calls:
        response = _handle_request(request)
        content = response["result"]["content"]
        assert len(content) == 1
        assert content[0]["type"] == "text"
        parsed = json.loads(content[0]["text"])
        assert parsed is not None
```

**Result**: All 6 tools verified. No format inconsistencies.

## Tool Results

### get_governance_status

| Input Model | has_governance | workflow | audit | attestation |
|---|---|---|---|---|
| dm-all-governance.xsd | True | True | True | True |
| dm-no-governance.xsd | False | False | False | False |

### get_allowed_transitions

| Input Instance | current-state | Allowed Targets |
|---|---|---|
| instance-linear-workflow.xml | "draft" | ["review"] |
| instance-branching-workflow.xml | "review" | ["approved", "rejected"] |

### evaluate_transition

| Target State | Decision | Receipt |
|---|---|---|
| "review" (valid) | PERMIT | instance_id="cuid2-test-linear-001" |
| "published" (skip) | DENY | errors include valid alternatives |

### validate_governance

| Input | Decision | has_governance |
|---|---|---|
| dm-all-governance.xsd (model only) | PERMIT | True |
| dm-no-governance.xsd (model only) | PERMIT | False |

### record_provenance

| Activity Type | Agent | Result |
|---|---|---|
| "Create" | "Dr. Smith" | activity_type="Create", started_at set |
| "Update" | "System" | entity_hash_before/after preserved |

### evaluate_decision

| Decision Table | Context | Decision |
|---|---|---|
| Protocol check (HIPAA) | protocol="HIPAA-compliant" | PERMIT |
| Risk check | risk_score=3 (extra context) | PERMIT |
| No matching rules | nonexistent field | INDETERMINATE |

## JSON-RPC Format Verification

Request:
```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
 "params": {"name": "get_governance_status",
            "arguments": {"schema_path": "model.xsd"}}}
```

Response:
```json
{"jsonrpc": "2.0", "id": 1,
 "result": {"content": [{"type": "text", "text": "{...JSON...}"}]}}
```

No SDK dependency. Raw JSON-RPC 2.0. Consistent, predictable, testable.

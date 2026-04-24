# Testing

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific module
python -m pytest tests/test_workflow.py -v

# With coverage
python -m pytest tests/ --cov=sdcgovernance --cov-report=term-missing
```

## Test Structure

```
tests/
  conftest.py           # Shared fixtures (model paths)
  fixtures/             # XSD models and XML instances
  test_model_inspector.py
  test_receipts.py
  test_workflow.py
  test_attestation.py
  test_party_role.py
  test_provenance.py
  test_decision.py
  test_shacl_runtime.py
  test_mcp_server.py
```

## Fixture Conventions

**XSD model fixtures** test governance slot detection:
- Named `dm-{description}.xsd`
- Must restrict `sdc4:DMType` with a `<xsd:restriction base="sdc4:DMType">` block
- Include RDF annotation with model id and label

**XML instance fixtures** test governance content extraction:
- Named `instance-{description}.xml`
- Root element in `sdc4:` namespace
- Include `instance_id` element
- One fixture per test scenario (valid, invalid, missing)

**SHACL tests** use inline Turtle strings (no fixture files) because SHACL shapes are self-contained.

## Writing Tests

Follow the existing pattern:

```python
class TestExtractSomething:
    """Extract content from XML instances."""

    def test_valid_content(self):
        data = extract_something("tests/fixtures/instance-valid.xml")
        assert data.field == "expected"

class TestValidateSomething:
    """Validate against requirements."""

    def test_passes_with_valid_data(self):
        data = extract_something("tests/fixtures/instance-valid.xml")
        result = validate_something(data)
        assert result.valid is True

    def test_fails_when_required_field_missing(self):
        data = extract_something("tests/fixtures/instance-missing.xml")
        reqs = SomethingRequirements(require_field=True)
        result = validate_something(data, reqs)
        assert result.valid is False
        assert any("field" in e for e in result.errors)
```

## MCP Server Tests

MCP tests call `_handle_request()` directly with JSON-RPC messages:

```python
def call_tool(name, arguments):
    request = {
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    response = _handle_request(request)
    content = response["result"]["content"]
    return json.loads(content[0]["text"])
```

No subprocess, no stdio, no async. Direct function calls for speed and reliability.

## Test Counts by Module

| Module | Tests |
|---|---|
| test_model_inspector.py | 27 |
| test_receipts.py | 26 |
| test_workflow.py | 28 |
| test_attestation.py | 13 |
| test_party_role.py | 25 |
| test_provenance.py | 29 |
| test_decision.py | 33 |
| test_shacl_runtime.py | 14 |
| test_mcp_server.py | 24 |
| Placeholders (audit, etc.) | 6 |
| **Total** | **225** |

All tests run in ~0.22 seconds.

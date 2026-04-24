# Adding a New Governance Dimension

How to extend sdcgovernance with a new governance capability.

## Steps

### 1. Identify the DMType root slot

Every governance dimension maps to a known position in the DMType root. Check the [RM Reference](../RM_Reference.md) for the slot. If the slot doesn't exist in sdc4, it may need to be added in sdc5.

### 2. Update model_inspector.py

Add detection for the new slot in `_map_sequence_elements()` and a new `_inspect_*()` function:

```python
# In GovernanceModel, add a new dimension dataclass
@dataclass
class NewDimensionInfo:
    present: bool = False
    # dimension-specific fields

# In GovernanceModel class
new_dimension: NewDimensionInfo = field(default_factory=NewDimensionInfo)

# Add to has_governance property
@property
def has_governance(self) -> bool:
    return (
        ...existing checks...
        or self.new_dimension.present
    )

# Add to active_dimensions property
@property
def active_dimensions(self) -> dict[str, bool]:
    return {
        ...existing...
        "new_dimension": self.new_dimension.present,
    }

# Add inspector function
def _inspect_new_dimension(elements, result):
    elem = elements.get("new-element-name")
    if elem is not None:
        result.new_dimension.present = True
```

### 3. Create the validation module

Create `src/sdcgovernance/new_dimension.py`:

```python
"""
New dimension validation for SDC governance.
Standards: [reference]
"""

@dataclass
class NewDimensionData:
    """Extracted content from instance."""
    ...

@dataclass
class NewDimensionRequirements:
    """What the model requires."""
    ...

@dataclass
class NewDimensionResult:
    """Validation result."""
    valid: bool = True
    errors: list[str] = field(default_factory=list)

def extract_new_dimension(instance_path: str) -> NewDimensionData:
    ...

def validate_new_dimension(data, requirements=None) -> NewDimensionResult:
    ...
```

### 4. Create test fixtures

Add XML instance fixtures in `tests/fixtures/`:
- `instance-new-dimension-valid.xml`
- `instance-new-dimension-invalid.xml`
- `instance-new-dimension-missing.xml`

Add XSD model fixture if needed:
- `dm-new-dimension-only.xsd`

### 5. Write tests

Create `tests/test_new_dimension.py` following the existing pattern:
- Extraction tests (parse XML, verify fields)
- Validation tests (requirements met/not met)
- Edge cases (missing elements, empty values)
- Independence test (doesn't affect other dimensions)

### 6. Update MCP server

Add a new tool handler in `mcp_server.py` if the dimension needs its own MCP tool. Or integrate into existing tools like `validate_governance`.

### 7. Update documentation

- `docs/user/new-dimension.md` - user documentation
- `docs/test-harness/new-dimension.md` - compliance evidence
- `docs/user/index.md` - add to contents
- `docs/test-harness/index.md` - add to contents and standards table
- `docs/RM_Reference.md` - add DMType slot mapping

### 8. Update PRD

Add requirements with acceptance criteria to the PRD.

## Conventions

- Each dimension is independent. No imports between dimension modules.
- Extract functions take a file path or parsed element. Return a data object.
- Validate functions take data + optional requirements. Return a result with valid/errors.
- All errors are human-readable strings.
- Tests use XML fixture files, not inline XML strings (except for SHACL Turtle).

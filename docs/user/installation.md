# Installation

## Requirements

- Python 3.10 or later
- lxml (XML parsing)
- rdflib (RDF/PROV record generation)
- pyshacl (SHACL constraint validation)

## Install from PyPI

```bash
pip install sdcgovernance
```

## Install from source

```bash
git clone https://github.com/SemanticDataCharter/sdcgovernance.git
cd sdcgovernance
pip install -e ".[dev]"
```

## Verify installation

```python
import sdcgovernance
print(sdcgovernance.__version__)
# 4.0.0
```

## No additional dependencies for MCP

The MCP server is implemented as raw JSON-RPC 2.0 over stdio. No external MCP SDK is required. The only dependencies are lxml, rdflib, and pyshacl.

## Relationship to sdcvalidator

sdcgovernance and sdcvalidator are independent libraries. Install them separately:

```bash
pip install sdcvalidator   # structural XSD validation
pip install sdcgovernance   # governance advisory
```

Agents call each library independently, at different points in a workflow, in whatever order the operational logic requires.

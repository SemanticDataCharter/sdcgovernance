"""
MCP server exposing sdcgovernance tools to any agent framework.

Runs as a standalone MCP (Model Context Protocol) server that exposes
governance decision tools. Any agent that speaks MCP can connect and
use governance without importing the Python library directly.

Start the server::

    sdcgovernance serve --mcp

MCP Tools exposed:
- get_allowed_transitions: what transitions are available from current state?
- evaluate_transition: can this specific transition proceed? (PERMIT/DENY/INDETERMINATE)
- record_provenance: record what happened for the audit trail
- validate_governance: full governance validation of an instance
- get_governance_status: what governance components does this model define?

The MCP server wraps the same GovernanceEngine that the Python API uses.
Same engine, different interface. Agent holds the loop. sdcgovernance advises.

sdcgovernance and sdcvalidator are independent libraries. Agents call each
one separately, at different points in a workflow, in whatever order their
operational logic requires.
"""

# TODO: Phase 7 implementation (after core engine is working)
# - MCP stdio server using the MCP Python SDK
# - Tool definitions matching the GovernanceEngine methods
# - CLI entry point: sdcgovernance serve --mcp
# - Schema/model loading from configuration or command line
# - Session management for receipt chain continuity
# - All decisions use OASIS XACML semantics (PERMIT/DENY/INDETERMINATE)

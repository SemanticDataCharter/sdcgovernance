"""
MCP server exposing sdcgovernance tools to any agent framework.

Implements the MCP (Model Context Protocol) as a raw JSON-RPC 2.0
stdio server. No external MCP SDK dependency - the protocol is simple
enough that a direct implementation is more reliable and maintainable.

Start the server::

    sdcgovernance serve --mcp

MCP Tools exposed:
- get_governance_status: what governance dimensions does this model define?
- get_allowed_transitions: what transitions are available from current state?
- evaluate_transition: can this specific transition proceed? (PERMIT/DENY/INDETERMINATE)
- evaluate_decision: evaluate a DMN decision table against instance context
- record_provenance: record what happened for the audit trail
- validate_governance: full governance validation of an instance

Protocol: JSON-RPC 2.0 over stdio (one JSON object per line).
"""

from __future__ import annotations

import json
import sys
from typing import Any

from sdcgovernance.engine import GovernanceEngine
from sdcgovernance.receipts import Decision
from sdcgovernance.workflow import extract_workflow_from_instance
from sdcgovernance.provenance import record_provenance as _record_provenance
from sdcgovernance.decision import (
    DecisionTable,
    Rule,
    Condition,
    ComparisonOp,
    HitPolicy,
    evaluate_decision_table,
    build_context_from_instance,
)

# Protocol constants
JSONRPC_VERSION = "2.0"
# Protocol revisions this server actually implements, oldest to newest.
#
# 2025-11-25 is the newest *initialization-based* revision. The 2026-07-28
# spec removes the initialize handshake entirely and moves protocol metadata
# into per-request `_meta.io.modelcontextprotocol/*` fields, which is a
# different architecture rather than a larger version number; that spec
# defines a compatibility path for servers of this era, so advertising it
# here would be a false conformance claim.
#
# 2024-11-05 and 2025-03-26 are deliberately absent: both require servers to
# accept JSON-RPC batches, and this server reads exactly one JSON object per
# line. Older clients still work, because negotiation lets us answer with a
# version we do support.
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-11-25")

#: Advertised when the client requests a revision we do not implement.
MCP_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[-1]
SERVER_NAME = "sdcgovernance"
SERVER_VERSION = "4.0.4"

# Engine cache
_engines: dict[str, GovernanceEngine] = {}


def _get_engine(schema_path: str) -> GovernanceEngine:
    """Get or create a GovernanceEngine for the given schema."""
    if schema_path not in _engines:
        _engines[schema_path] = GovernanceEngine(schema_path)
    return _engines[schema_path]


# --- Tool definitions ---

TOOLS = [
    {
        "name": "get_governance_status",
        "description": (
            "Report which governance dimensions the model defines. "
            "Returns model_id, model_label, has_governance, and active dimensions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schema_path": {
                    "type": "string",
                    "description": "Path to the SDC data model XSD file.",
                },
            },
            "required": ["schema_path"],
        },
    },
    {
        "name": "get_allowed_transitions",
        "description": (
            "Get valid next states from the current workflow state. "
            "Returns list of valid transitions with target state info and path(s)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schema_path": {
                    "type": "string",
                    "description": "Path to the SDC data model XSD file.",
                },
                "instance_path": {
                    "type": "string",
                    "description": "Path to the XML instance file containing workflow and current-state.",
                },
            },
            "required": ["schema_path", "instance_path"],
        },
    },
    {
        "name": "evaluate_transition",
        "description": (
            "Evaluate whether a specific workflow transition is permitted. "
            "Returns PERMIT/DENY/INDETERMINATE with receipt."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schema_path": {
                    "type": "string",
                    "description": "Path to the SDC data model XSD file.",
                },
                "instance_path": {
                    "type": "string",
                    "description": "Path to the XML instance file.",
                },
                "target_state": {
                    "type": "string",
                    "description": "Proposed target state symbol.",
                },
                "actor": {
                    "type": "string",
                    "description": "Identity of the actor requesting the transition.",
                    "default": "",
                },
            },
            "required": ["schema_path", "instance_path", "target_state"],
        },
    },
    {
        "name": "validate_governance",
        "description": (
            "Full governance validation of an instance against its model. "
            "Returns decision, has_governance, errors, dimensions_validated."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schema_path": {
                    "type": "string",
                    "description": "Path to the SDC data model XSD file.",
                },
                "instance_path": {
                    "type": "string",
                    "description": "Path to the XML instance file. Optional - if omitted, returns model governance status only.",
                },
            },
            "required": ["schema_path"],
        },
    },
    {
        "name": "record_provenance",
        "description": (
            "Record a provenance event as a W3C PROV-O record. "
            "Returns the PROV record content."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "activity_type": {
                    "type": "string",
                    "description": "W3C Activity Streams 2.0 type (Create, Update, Accept, etc.)",
                },
                "agent_name": {
                    "type": "string",
                    "description": "Name of the agent performing the action.",
                },
                "entity_id": {"type": "string", "description": "ID of the entity (DM.instance_id).", "default": ""},
                "agent_ref": {"type": "string", "description": "URI reference for the agent.", "default": ""},
                "system_id": {"type": "string", "description": "System that produced this record.", "default": ""},
                "description": {"type": "string", "description": "Human-readable description.", "default": ""},
                "entity_hash_before": {"type": "string", "description": "SHA-256 hash before action.", "default": ""},
                "entity_hash_after": {"type": "string", "description": "SHA-256 hash after action.", "default": ""},
            },
            "required": ["activity_type", "agent_name"],
        },
    },
    {
        "name": "evaluate_decision",
        "description": (
            "Evaluate a DMN decision table against instance context. "
            "Returns decision, matched_rules, reasoning, errors, and a "
            "tamper-evident Receipt with SHA-256 receipt_hash. "
            "instance_path is optional: when omitted, the decision is "
            "evaluated against extra_context alone, which is the path "
            "external context-only consumers (e.g. MTCP Evidence Packs) "
            "should use. Pass previous_hash to chain receipts; the caller "
            "is responsible for chain persistence."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "instance_path": {
                    "type": "string",
                    "description": (
                        "Path to the XML instance file for context "
                        "extraction. Optional. Omit to evaluate against "
                        "extra_context only."
                    ),
                },
                "table_json": {
                    "type": "string",
                    "description": (
                        "JSON string defining the decision table. "
                        'Format: {"name": "...", "hit_policy": "FIRST|UNIQUE|COLLECT", '
                        '"rules": [{"conditions": [{"field": "...", "op": "==|!=|<|<=|>|>=|in|not_in", "value": ...}], '
                        '"outcome": "PERMIT|DENY|INDETERMINATE", "description": "..."}]}'
                    ),
                },
                "extra_context": {
                    "type": "string",
                    "description": "JSON string with additional context key-value pairs.",
                    "default": "{}",
                },
                "instance_id": {
                    "type": "string",
                    "description": (
                        "Identifier for the entity being evaluated, recorded "
                        "in the Receipt. For SDC instances this is the DM "
                        "instance_id (CUID2). For external consumers this "
                        "is the entity identifier (e.g. an MTCP model_id "
                        "such as 'gpt-4o')."
                    ),
                    "default": "",
                },
                "instance_version": {
                    "type": "string",
                    "description": (
                        "Version of the entity being evaluated, recorded in "
                        "the Receipt."
                    ),
                    "default": "",
                },
                "previous_hash": {
                    "type": ["string", "null"],
                    "description": (
                        "SHA-256 hash of the prior Receipt in the caller's "
                        "chain. Pass null (default) to start a new chain. "
                        "The caller is responsible for chain persistence."
                    ),
                    "default": None,
                },
                "context_hash": {
                    "type": "string",
                    "description": (
                        "SHA-256 hash of the extra_context payload, computed "
                        "by the caller. Binds the Receipt cryptographically "
                        "to the context that produced the decision. MTCP "
                        "consumers pass the Evidence Pack hash here."
                    ),
                    "default": "",
                },
            },
            "required": ["table_json"],
        },
    },
    {
        "name": "verify_evidence_pack",
        "description": (
            "Verify the integrity of an MTCP Evidence Pack by recomputing "
            "its evidence_pack_hash. Returns valid (bool), computed_hash, "
            "and expected_hash. Canonicalization follows RFC 8785: keys "
            "sorted, no whitespace, comma-colon separators, UTF-8."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "evidence_pack": {
                    "type": "string",
                    "description": (
                        "JSON string of the MTCP Evidence Pack including "
                        "its evidence_pack_hash field. Hash is recomputed "
                        "over the remaining fields and compared."
                    ),
                },
            },
            "required": ["evidence_pack"],
        },
    },
]


# --- Tool handlers ---

def _handle_get_governance_status(args: dict[str, Any]) -> Any:
    engine = _get_engine(args["schema_path"])
    return engine.get_governance_status()


def _handle_get_allowed_transitions(args: dict[str, Any]) -> Any:
    engine = _get_engine(args["schema_path"])
    current_state, workflow_tree = extract_workflow_from_instance(args["instance_path"])
    if workflow_tree is None:
        return []
    return engine.get_allowed_transitions(current_state, workflow_tree)


def _handle_evaluate_transition(args: dict[str, Any]) -> Any:
    engine = _get_engine(args["schema_path"])
    current_state, workflow_tree = extract_workflow_from_instance(args["instance_path"])

    # Extract instance identity
    from lxml import etree
    tree = etree.parse(args["instance_path"])
    root = tree.getroot()
    instance_id = ""
    instance_version = ""
    source_instance_id = ""
    source_version_id = ""
    for elem in root:
        local = etree.QName(elem.tag).localname if isinstance(elem.tag, str) else ""
        if local == "instance_id" and elem.text:
            instance_id = elem.text.strip()
        elif local == "instance_version" and elem.text:
            instance_version = elem.text.strip()
        elif local == "source_instance_id" and elem.text:
            source_instance_id = elem.text.strip()
        elif local == "source_version_id" and elem.text:
            source_version_id = elem.text.strip()

    result = engine.evaluate_transition(
        current_state=current_state,
        target_state=args["target_state"],
        actor=args.get("actor", ""),
        instance_id=instance_id,
        instance_version=instance_version,
        source_instance_id=source_instance_id,
        source_version_id=source_version_id,
        workflow_tree=workflow_tree,
    )
    return {
        "decision": result.decision.value,
        "has_governance": result.has_governance,
        "errors": result.errors,
        "receipt": result.receipt.to_dict() if result.receipt else None,
        "dimensions_validated": result.dimensions_validated,
    }


def _handle_validate_governance(args: dict[str, Any]) -> Any:
    from sdcgovernance import validate_governance as _validate
    result = _validate(args["schema_path"], args.get("instance_path"))
    return {
        "decision": result.decision.value,
        "has_governance": result.has_governance,
        "errors": result.errors,
        "receipt": result.receipt.to_dict() if result.receipt else None,
        "dimensions_validated": result.dimensions_validated,
    }


def _handle_record_provenance(args: dict[str, Any]) -> Any:
    rec = _record_provenance(
        activity_type=args["activity_type"],
        agent_name=args["agent_name"],
        entity_id=args.get("entity_id", ""),
        agent_ref=args.get("agent_ref", ""),
        system_id=args.get("system_id", ""),
        description=args.get("description", ""),
        entity_hash_before=args.get("entity_hash_before", ""),
        entity_hash_after=args.get("entity_hash_after", ""),
    )
    return rec.to_dict()


def _handle_evaluate_decision(args: dict[str, Any]) -> Any:
    from sdcgovernance.receipts import Receipt, StatusCode

    table_data = json.loads(args["table_json"])
    table = _parse_decision_table(table_data)
    extra = json.loads(args.get("extra_context", "{}"))
    instance_path = args.get("instance_path")
    if instance_path:
        # Path supplied: extract context from the SDC instance and merge extra.
        context = build_context_from_instance(instance_path, extra=extra)
    else:
        # No SDC instance available (e.g. MTCP Evidence Pack consumer):
        # evaluate against extra_context only.
        context = dict(extra)
    result = evaluate_decision_table(table, context)

    # Compute dimensions_checked: union of fields referenced by the rules
    # that participated in the decision (preserving first-seen order).
    dimensions_checked: list[str] = []
    for idx in result.matched_rules:
        if 0 <= idx < len(table.rules):
            for cond in table.rules[idx].conditions:
                if cond.field not in dimensions_checked:
                    dimensions_checked.append(cond.field)

    # XACML 3.0 Section 7.18 status code mapping. Errors from the decision
    # evaluator (e.g. UNIQUE hit-policy violation, unknown hit policy) map
    # to processing-error. Normal PERMIT / DENY / NOT_APPLICABLE /
    # INDETERMINATE-by-no-match are processed-cleanly (status: ok).
    status_code = (
        StatusCode.PROCESSING_ERROR if result.errors else StatusCode.OK
    )

    receipt = Receipt(
        decision=result.decision,
        reasoning=result.reasoning,
        status_code=status_code,
        instance_id=args.get("instance_id", "") or "",
        instance_version=args.get("instance_version", "") or "",
        previous_hash=args.get("previous_hash"),
        dimensions_checked=dimensions_checked,
        errors=list(result.errors),
        context_hash=args.get("context_hash", "") or "",
    )

    return {
        "decision": result.decision.value,
        "matched_rules": result.matched_rules,
        "reasoning": result.reasoning,
        "errors": result.errors,
        "receipt": receipt.to_dict(),
    }


def _handle_verify_evidence_pack(args: dict[str, Any]) -> Any:
    from sdcgovernance.mtcp import verify_evidence_pack

    ep = json.loads(args["evidence_pack"])
    return verify_evidence_pack(ep)


TOOL_HANDLERS = {
    "get_governance_status": _handle_get_governance_status,
    "get_allowed_transitions": _handle_get_allowed_transitions,
    "evaluate_transition": _handle_evaluate_transition,
    "validate_governance": _handle_validate_governance,
    "record_provenance": _handle_record_provenance,
    "evaluate_decision": _handle_evaluate_decision,
    "verify_evidence_pack": _handle_verify_evidence_pack,
}


# --- Decision table JSON parsing ---

def _parse_decision_table(data: dict[str, Any]) -> DecisionTable:
    """Parse a decision table from a JSON-compatible dict."""
    op_map = {
        "==": ComparisonOp.EQ, "!=": ComparisonOp.NE,
        "<": ComparisonOp.LT, "<=": ComparisonOp.LE,
        ">": ComparisonOp.GT, ">=": ComparisonOp.GE,
        "in": ComparisonOp.IN, "not_in": ComparisonOp.NOT_IN,
    }
    decision_map = {
        "PERMIT": Decision.PERMIT,
        "DENY": Decision.DENY,
        "INDETERMINATE": Decision.INDETERMINATE,
        "NOT_APPLICABLE": Decision.NOT_APPLICABLE,
    }
    policy_map = {
        "FIRST": HitPolicy.FIRST,
        "UNIQUE": HitPolicy.UNIQUE,
        "COLLECT": HitPolicy.COLLECT,
    }

    rules = []
    for rule_data in data.get("rules", []):
        conditions = [
            Condition(field=c["field"], op=op_map[c["op"]], value=c["value"])
            for c in rule_data.get("conditions", [])
        ]
        rules.append(Rule(
            conditions=conditions,
            outcome=decision_map[rule_data["outcome"]],
            description=rule_data.get("description", ""),
        ))

    return DecisionTable(
        name=data.get("name", ""),
        hit_policy=policy_map.get(data.get("hit_policy", "FIRST"), HitPolicy.FIRST),
        rules=rules,
        description=data.get("description", ""),
    )


# --- JSON-RPC 2.0 stdio server ---

def _jsonrpc_response(id: Any, result: Any) -> dict:
    """Build a JSON-RPC 2.0 success response."""
    return {"jsonrpc": JSONRPC_VERSION, "id": id, "result": result}


def _jsonrpc_error(id: Any, code: int, message: str, data: Any = None) -> dict:
    """Build a JSON-RPC 2.0 error response."""
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": JSONRPC_VERSION, "id": id, "error": error}


def _handle_request(request: dict) -> dict | None:
    """
    Handle a single JSON-RPC 2.0 request.

    Returns a response dict, or None for notifications (no id).
    """
    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "initialize":
        # Negotiate rather than assert: honour the client's revision when we
        # implement it, otherwise answer with our newest and let the client
        # decide whether to continue.
        requested = params.get("protocolVersion")
        negotiated = (
            requested
            if requested in SUPPORTED_PROTOCOL_VERSIONS
            else MCP_PROTOCOL_VERSION
        )
        result = {
            "protocolVersion": negotiated,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
            "instructions": (
                "SDC Governance advisory engine. Validates governance content "
                "in SDC data instances against model-defined governance components. "
                "Returns OASIS XACML decisions: PERMIT, DENY, or INDETERMINATE."
            ),
        }
        return _jsonrpc_response(req_id, result)

    elif method == "notifications/initialized":
        # Client acknowledgment - no response needed
        return None

    elif method == "tools/list":
        return _jsonrpc_response(req_id, {"tools": TOOLS})

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if handler is None:
            return _jsonrpc_error(
                req_id, -32601, f"Unknown tool: {tool_name}"
            )

        try:
            result = handler(tool_args)
            return _jsonrpc_response(req_id, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, default=str),
                    }
                ],
            })
        except Exception as exc:
            # SEP-1303: execution and input-validation failures are tool
            # errors, not protocol errors. Returning them in the result lets
            # the calling model see what went wrong and correct itself; a
            # JSON-RPC error is invisible to it.
            return _jsonrpc_response(req_id, {
                "content": [
                    {"type": "text", "text": f"Tool execution error: {exc}"}
                ],
                "isError": True,
            })

    elif method == "ping":
        return _jsonrpc_response(req_id, {})

    else:
        if req_id is not None:
            return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")
        return None


def run_stdio() -> None:
    """
    Run the MCP server on stdio.

    Reads JSON-RPC 2.0 messages from stdin (one per line),
    processes them, and writes responses to stdout.
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = _jsonrpc_error(None, -32700, f"Parse error: {exc}")
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            continue

        response = _handle_request(request)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


def main() -> None:
    """Entry point for the sdcgovernance CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="sdcgovernance",
        description="SDC Governance advisory engine",
    )
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Start the governance server")
    serve_parser.add_argument(
        "--mcp", action="store_true", help="Run as MCP stdio server"
    )

    args = parser.parse_args()

    if args.command == "serve" and args.mcp:
        run_stdio()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

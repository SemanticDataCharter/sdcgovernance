"""
Tests for MCP server - Phase 7.

Tests the JSON-RPC 2.0 MCP server handlers directly.
No external MCP SDK dependency - tests call _handle_request()
with JSON-RPC messages and verify responses.
"""

import json
import pytest
from pathlib import Path
from sdcgovernance.mcp_server import (
    MCP_PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
    _handle_request,
    _parse_decision_table,
    TOOLS,
    TOOL_HANDLERS,
)
from sdcgovernance.receipts import Decision

FIXTURES = Path(__file__).parent / "fixtures"


def call_tool(name: str, arguments: dict) -> dict:
    """Helper: call an MCP tool via JSON-RPC and return the parsed result."""
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    response = _handle_request(request)
    assert "result" in response, f"Expected result, got: {response}"
    content = response["result"]["content"]
    assert len(content) == 1
    assert content[0]["type"] == "text"
    return json.loads(content[0]["text"])


class TestMcpProtocol:
    """JSON-RPC 2.0 MCP protocol handling."""

    def test_initialize(self):
        request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        response = _handle_request(request)
        assert response["id"] == 1
        result = response["result"]
        assert result["serverInfo"]["name"] == "sdcgovernance"
        assert "tools" in result["capabilities"]

    def test_initialized_notification(self):
        request = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        response = _handle_request(request)
        assert response is None  # notifications have no response

    def test_tools_list(self):
        request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        response = _handle_request(request)
        tools = response["result"]["tools"]
        assert len(tools) == 7
        names = {t["name"] for t in tools}
        assert names == {
            "get_governance_status",
            "get_allowed_transitions",
            "evaluate_transition",
            "validate_governance",
            "record_provenance",
            "evaluate_decision",
            "verify_evidence_pack",
        }

    def test_tools_have_input_schemas(self):
        request = {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
        response = _handle_request(request)
        for tool in response["result"]["tools"]:
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_ping(self):
        request = {"jsonrpc": "2.0", "id": 4, "method": "ping", "params": {}}
        response = _handle_request(request)
        assert response["id"] == 4
        assert response["result"] == {}

    def test_unknown_method(self):
        request = {"jsonrpc": "2.0", "id": 5, "method": "nonexistent", "params": {}}
        response = _handle_request(request)
        assert "error" in response
        assert response["error"]["code"] == -32601

    def test_unknown_tool(self):
        request = {
            "jsonrpc": "2.0", "id": 6,
            "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}},
        }
        response = _handle_request(request)
        assert "error" in response
        assert "Unknown tool" in response["error"]["message"]


class TestGetGovernanceStatus:
    """get_governance_status MCP tool."""

    def test_all_governance_model(self):
        data = call_tool("get_governance_status", {
            "schema_path": str(FIXTURES / "dm-all-governance.xsd"),
        })
        assert data["has_governance"] is True
        assert data["dimensions"]["workflow"] is True
        assert data["dimensions"]["audit"] is True
        assert data["dimensions"]["attestation"] is True

    def test_no_governance_model(self):
        data = call_tool("get_governance_status", {
            "schema_path": str(FIXTURES / "dm-no-governance.xsd"),
        })
        assert data["has_governance"] is False


class TestGetAllowedTransitions:
    """get_allowed_transitions MCP tool."""

    def test_linear_workflow(self):
        data = call_tool("get_allowed_transitions", {
            "schema_path": str(FIXTURES / "dm-workflow-only.xsd"),
            "instance_path": str(FIXTURES / "instance-linear-workflow.xml"),
        })
        assert len(data) == 1
        assert data[0]["target_symbol"] == "review"

    def test_branching_workflow(self):
        data = call_tool("get_allowed_transitions", {
            "schema_path": str(FIXTURES / "dm-workflow-only.xsd"),
            "instance_path": str(FIXTURES / "instance-branching-workflow.xml"),
        })
        symbols = {t["target_symbol"] for t in data}
        assert symbols == {"approved", "rejected"}


class TestEvaluateTransition:
    """evaluate_transition MCP tool."""

    def test_valid_transition_permit(self):
        data = call_tool("evaluate_transition", {
            "schema_path": str(FIXTURES / "dm-workflow-only.xsd"),
            "instance_path": str(FIXTURES / "instance-linear-workflow.xml"),
            "target_state": "review",
        })
        assert data["decision"] == "PERMIT"
        assert data["receipt"] is not None

    def test_invalid_transition_deny(self):
        data = call_tool("evaluate_transition", {
            "schema_path": str(FIXTURES / "dm-workflow-only.xsd"),
            "instance_path": str(FIXTURES / "instance-linear-workflow.xml"),
            "target_state": "published",
        })
        assert data["decision"] == "DENY"
        assert len(data["errors"]) > 0

    def test_receipt_has_instance_id(self):
        data = call_tool("evaluate_transition", {
            "schema_path": str(FIXTURES / "dm-workflow-only.xsd"),
            "instance_path": str(FIXTURES / "instance-linear-workflow.xml"),
            "target_state": "review",
        })
        assert data["receipt"]["instance_id"] == "cuid2-test-linear-001"


class TestValidateGovernance:
    """validate_governance MCP tool."""

    def test_model_only(self):
        data = call_tool("validate_governance", {
            "schema_path": str(FIXTURES / "dm-all-governance.xsd"),
        })
        assert data["decision"] == "PERMIT"
        assert data["has_governance"] is True

    def test_no_governance_model(self):
        data = call_tool("validate_governance", {
            "schema_path": str(FIXTURES / "dm-no-governance.xsd"),
        })
        assert data["decision"] == "NOT_APPLICABLE"
        assert data["has_governance"] is False


class TestRecordProvenance:
    """record_provenance MCP tool."""

    def test_record_create(self):
        data = call_tool("record_provenance", {
            "activity_type": "Create",
            "agent_name": "Dr. Smith",
            "entity_id": "cuid2-test-001",
            "system_id": "sdc-studio-cloud",
            "description": "Created patient encounter",
        })
        assert data["activity_type"] == "Create"
        assert data["agent_name"] == "Dr. Smith"
        assert data["entity_id"] == "cuid2-test-001"
        assert data["started_at"] != ""

    def test_record_with_hashes(self):
        data = call_tool("record_provenance", {
            "activity_type": "Update",
            "agent_name": "System",
            "entity_hash_before": "abc123",
            "entity_hash_after": "def456",
        })
        assert data["entity_hash_before"] == "abc123"
        assert data["entity_hash_after"] == "def456"


class TestEvaluateDecision:
    """evaluate_decision MCP tool."""

    def test_protocol_check(self):
        table = {
            "name": "protocol_check",
            "hit_policy": "FIRST",
            "rules": [
                {
                    "conditions": [{"field": "protocol", "op": "==", "value": "HIPAA-compliant"}],
                    "outcome": "PERMIT",
                    "description": "HIPAA protocol accepted",
                },
                {
                    "conditions": [],
                    "outcome": "DENY",
                    "description": "Non-HIPAA denied",
                },
            ],
        }
        data = call_tool("evaluate_decision", {
            "instance_path": str(FIXTURES / "instance-decision-context.xml"),
            "table_json": json.dumps(table),
        })
        assert data["decision"] == "PERMIT"
        assert 0 in data["matched_rules"]

    def test_risk_check_with_extra(self):
        table = {
            "name": "risk_check",
            "hit_policy": "FIRST",
            "rules": [
                {"conditions": [{"field": "risk_score", "op": ">=", "value": 8}], "outcome": "DENY"},
                {"conditions": [{"field": "risk_score", "op": "<", "value": 8}], "outcome": "PERMIT"},
            ],
        }
        data = call_tool("evaluate_decision", {
            "instance_path": str(FIXTURES / "instance-decision-context.xml"),
            "table_json": json.dumps(table),
            "extra_context": json.dumps({"risk_score": 3}),
        })
        assert data["decision"] == "PERMIT"

    def test_no_match_not_applicable(self):
        table = {
            "name": "impossible",
            "hit_policy": "FIRST",
            "rules": [
                {"conditions": [{"field": "nonexistent", "op": "==", "value": "x"}], "outcome": "PERMIT"},
            ],
        }
        data = call_tool("evaluate_decision", {
            "instance_path": str(FIXTURES / "instance-decision-context.xml"),
            "table_json": json.dumps(table),
        })
        assert data["decision"] == "NOT_APPLICABLE"

    def test_extra_context_only_no_instance_path(self):
        """instance_path is optional: external consumers (e.g. MTCP) can
        evaluate against extra_context alone."""
        table = {
            "name": "model_grade_check",
            "hit_policy": "FIRST",
            "rules": [
                {
                    "conditions": [{"field": "model_grade", "op": "in", "value": ["D", "F"]}],
                    "outcome": "DENY",
                    "description": "Low model grade rejected",
                },
                {"conditions": [], "outcome": "PERMIT"},
            ],
        }
        data = call_tool("evaluate_decision", {
            "table_json": json.dumps(table),
            "extra_context": json.dumps({"model_grade": "D"}),
        })
        assert data["decision"] == "DENY"
        assert 0 in data["matched_rules"]

    def test_extra_context_only_permit(self):
        """Same path, PERMIT branch."""
        table = {
            "name": "model_grade_check",
            "hit_policy": "FIRST",
            "rules": [
                {
                    "conditions": [{"field": "model_grade", "op": "in", "value": ["D", "F"]}],
                    "outcome": "DENY",
                },
                {"conditions": [], "outcome": "PERMIT"},
            ],
        }
        data = call_tool("evaluate_decision", {
            "table_json": json.dumps(table),
            "extra_context": json.dumps({"model_grade": "A"}),
        })
        assert data["decision"] == "PERMIT"

    def test_evaluate_decision_input_schema_makes_instance_path_optional(self):
        """The MCP inputSchema should not list instance_path as required."""
        from sdcgovernance.mcp_server import TOOLS
        evaluate_decision_tool = next(t for t in TOOLS if t["name"] == "evaluate_decision")
        required = evaluate_decision_tool["inputSchema"].get("required", [])
        assert "instance_path" not in required
        assert "table_json" in required


class TestEvaluateDecisionReceipt:
    """evaluate_decision returns a tamper-evident Receipt (4.0.3+)."""

    @staticmethod
    def _basic_table() -> dict:
        return {
            "name": "model_grade_check",
            "hit_policy": "FIRST",
            "rules": [
                {
                    "conditions": [
                        {"field": "model_grade", "op": "in", "value": ["D", "F"]}
                    ],
                    "outcome": "DENY",
                    "description": "Low model grade rejected",
                },
                {"conditions": [], "outcome": "PERMIT"},
            ],
        }

    def test_response_includes_receipt(self):
        data = call_tool("evaluate_decision", {
            "table_json": json.dumps(self._basic_table()),
            "extra_context": json.dumps({"model_grade": "D"}),
        })
        assert "receipt" in data
        assert data["receipt"]["decision"] == "DENY"
        assert data["receipt"]["receipt_hash"]
        assert len(data["receipt"]["receipt_hash"]) == 64  # SHA-256 hex

    def test_legacy_response_fields_preserved(self):
        """Backward compatibility: existing fields still present."""
        data = call_tool("evaluate_decision", {
            "table_json": json.dumps(self._basic_table()),
            "extra_context": json.dumps({"model_grade": "A"}),
        })
        assert data["decision"] == "PERMIT"
        assert data["matched_rules"] == [1]
        assert "reasoning" in data
        assert "errors" in data

    def test_receipt_records_instance_id_and_version(self):
        data = call_tool("evaluate_decision", {
            "table_json": json.dumps(self._basic_table()),
            "extra_context": json.dumps({"model_grade": "D"}),
            "instance_id": "gpt-4o",
            "instance_version": "2024-08-06",
        })
        assert data["receipt"]["instance_id"] == "gpt-4o"
        assert data["receipt"]["instance_version"] == "2024-08-06"

    def test_receipt_dimensions_checked_first_match(self):
        """For FIRST hit policy, dimensions_checked is the firing rule's fields."""
        data = call_tool("evaluate_decision", {
            "table_json": json.dumps(self._basic_table()),
            "extra_context": json.dumps({"model_grade": "F"}),
        })
        assert data["receipt"]["dimensions_checked"] == ["model_grade"]

    def test_receipt_dimensions_checked_multiple_fields(self):
        table = {
            "name": "multi_field",
            "hit_policy": "FIRST",
            "rules": [
                {
                    "conditions": [
                        {"field": "regime", "op": "==", "value": "R3"},
                        {"field": "data_class", "op": ">=", "value": "Restricted"},
                    ],
                    "outcome": "DENY",
                },
            ],
        }
        data = call_tool("evaluate_decision", {
            "table_json": json.dumps(table),
            "extra_context": json.dumps({
                "regime": "R3",
                "data_class": "Restricted",
            }),
        })
        assert data["receipt"]["decision"] == "DENY"
        assert data["receipt"]["dimensions_checked"] == ["regime", "data_class"]

    def test_receipt_dimensions_checked_empty_when_no_match(self):
        table = {
            "name": "no_match",
            "hit_policy": "FIRST",
            "rules": [
                {"conditions": [{"field": "x", "op": "==", "value": "y"}], "outcome": "PERMIT"},
            ],
        }
        data = call_tool("evaluate_decision", {
            "table_json": json.dumps(table),
            "extra_context": json.dumps({"x": "z"}),
        })
        assert data["receipt"]["decision"] == "NOT_APPLICABLE"
        assert data["receipt"]["dimensions_checked"] == []

    def test_receipt_status_code_ok_on_clean_evaluation(self):
        data = call_tool("evaluate_decision", {
            "table_json": json.dumps(self._basic_table()),
            "extra_context": json.dumps({"model_grade": "A"}),
        })
        # XACML 3.0 ok URN
        assert data["receipt"]["status_code"] == "urn:oasis:names:tc:xacml:1.0:status:ok"

    def test_receipt_status_code_processing_error_on_unique_violation(self):
        """UNIQUE hit policy with multiple matches sets PROCESSING_ERROR."""
        table = {
            "name": "unique_conflict",
            "hit_policy": "UNIQUE",
            "rules": [
                {"conditions": [{"field": "x", "op": "==", "value": 1}], "outcome": "PERMIT"},
                {"conditions": [{"field": "x", "op": "==", "value": 1}], "outcome": "DENY"},
            ],
        }
        data = call_tool("evaluate_decision", {
            "table_json": json.dumps(table),
            "extra_context": json.dumps({"x": 1}),
        })
        assert data["receipt"]["decision"] == "INDETERMINATE"
        assert data["receipt"]["status_code"] == (
            "urn:oasis:names:tc:xacml:1.0:status:processing-error"
        )
        assert data["receipt"]["errors"]

    def test_receipt_chain_links_via_previous_hash(self):
        """First call starts a chain; second call links via previous_hash."""
        first = call_tool("evaluate_decision", {
            "table_json": json.dumps(self._basic_table()),
            "extra_context": json.dumps({"model_grade": "D"}),
            "instance_id": "gpt-4o",
        })
        first_hash = first["receipt"]["receipt_hash"]
        assert first["receipt"]["previous_hash"] is None

        second = call_tool("evaluate_decision", {
            "table_json": json.dumps(self._basic_table()),
            "extra_context": json.dumps({"model_grade": "B"}),
            "instance_id": "gpt-4o",
            "previous_hash": first_hash,
        })
        assert second["receipt"]["previous_hash"] == first_hash
        assert second["receipt"]["receipt_hash"] != first_hash

    def test_receipt_hash_is_deterministic_over_content(self):
        """Receipt rebuilt from to_dict() output reproduces the same hash."""
        from sdcgovernance.receipts import Receipt, Decision, StatusCode
        data = call_tool("evaluate_decision", {
            "table_json": json.dumps(self._basic_table()),
            "extra_context": json.dumps({"model_grade": "D"}),
            "instance_id": "gpt-4o",
            "instance_version": "2024-08-06",
        })
        rec = data["receipt"]
        # Reconstruct a Receipt with the same content and verify the hash.
        reconstructed = Receipt(
            decision=Decision(rec["decision"]),
            reasoning=rec["reasoning"],
            status_code=StatusCode(rec["status_code"]),
            instance_id=rec["instance_id"],
            instance_version=rec["instance_version"],
            timestamp=rec["timestamp"],
            previous_hash=rec["previous_hash"],
            dimensions_checked=rec["dimensions_checked"],
            errors=rec["errors"],
        )
        assert reconstructed.verify_hash()
        assert reconstructed.receipt_hash == rec["receipt_hash"]


class TestEvaluateDecisionContextHash:
    """evaluate_decision binds context_hash into the Receipt (4.0.4+)."""

    @staticmethod
    def _basic_table() -> dict:
        return {
            "name": "model_grade_check",
            "hit_policy": "FIRST",
            "rules": [
                {"conditions": [], "outcome": "PERMIT"},
            ],
        }

    def test_context_hash_recorded_in_receipt(self):
        ctx_hash = "89586bf4507cca361db03bd9005d97ddaaec42d1b6dea61ad498965ae172d283"
        data = call_tool("evaluate_decision", {
            "table_json": json.dumps(self._basic_table()),
            "extra_context": json.dumps({"x": 1}),
            "context_hash": ctx_hash,
        })
        assert data["receipt"]["context_hash"] == ctx_hash

    def test_context_hash_default_empty(self):
        data = call_tool("evaluate_decision", {
            "table_json": json.dumps(self._basic_table()),
            "extra_context": json.dumps({"x": 1}),
        })
        assert data["receipt"]["context_hash"] == ""

    def test_context_hash_changes_receipt_hash(self):
        """Different context_hash values produce different receipt hashes."""
        a = call_tool("evaluate_decision", {
            "table_json": json.dumps(self._basic_table()),
            "extra_context": json.dumps({"x": 1}),
            "context_hash": "aaa",
            "instance_id": "test",
        })
        b = call_tool("evaluate_decision", {
            "table_json": json.dumps(self._basic_table()),
            "extra_context": json.dumps({"x": 1}),
            "context_hash": "bbb",
            "instance_id": "test",
        })
        # Timestamps will differ too, so this is a weak check; the
        # round-trip verify_hash test in test_receipts gives the
        # deterministic guarantee.
        assert a["receipt"]["receipt_hash"] != b["receipt"]["receipt_hash"]


class TestVerifyEvidencePackTool:
    """verify_evidence_pack MCP tool (4.0.4+)."""

    def test_valid_pack(self):
        from sdcgovernance.mtcp import compute_evidence_pack_hash

        ep = {"model_id": "gpt-4o", "score": 0.95}
        ep["evidence_pack_hash"] = compute_evidence_pack_hash(ep)
        data = call_tool("verify_evidence_pack", {
            "evidence_pack": json.dumps(ep),
        })
        assert data["valid"] is True

    def test_tampered_pack(self):
        from sdcgovernance.mtcp import compute_evidence_pack_hash

        ep = {"model_id": "gpt-4o", "score": 0.95}
        ep["evidence_pack_hash"] = compute_evidence_pack_hash(ep)
        ep["score"] = 0.10
        data = call_tool("verify_evidence_pack", {
            "evidence_pack": json.dumps(ep),
        })
        assert data["valid"] is False


class TestParseDecisionTable:
    """JSON to DecisionTable parsing."""

    def test_parse_simple(self):
        data = {
            "name": "test",
            "hit_policy": "FIRST",
            "rules": [
                {"conditions": [{"field": "x", "op": ">", "value": 5}], "outcome": "PERMIT", "description": "x > 5"},
            ],
        }
        table = _parse_decision_table(data)
        assert table.name == "test"
        assert table.hit_policy.value == "FIRST"
        assert len(table.rules) == 1
        assert table.rules[0].outcome == Decision.PERMIT

    def test_parse_all_ops(self):
        ops = ["==", "!=", "<", "<=", ">", ">=", "in", "not_in"]
        for op in ops:
            data = {"rules": [{"conditions": [{"field": "x", "op": op, "value": 1}], "outcome": "PERMIT"}]}
            table = _parse_decision_table(data)
            assert len(table.rules) == 1


class TestConsistentSerialization:
    """Verify all tools return consistent JSON-RPC format."""

    def test_all_tools_return_single_text_content(self):
        """Every tool returns exactly one content block with type=text."""
        test_calls = [
            ("get_governance_status", {"schema_path": str(FIXTURES / "dm-all-governance.xsd")}),
            ("get_allowed_transitions", {
                "schema_path": str(FIXTURES / "dm-workflow-only.xsd"),
                "instance_path": str(FIXTURES / "instance-linear-workflow.xml"),
            }),
            ("evaluate_transition", {
                "schema_path": str(FIXTURES / "dm-workflow-only.xsd"),
                "instance_path": str(FIXTURES / "instance-linear-workflow.xml"),
                "target_state": "review",
            }),
            ("validate_governance", {"schema_path": str(FIXTURES / "dm-no-governance.xsd")}),
            ("record_provenance", {"activity_type": "Create", "agent_name": "Test"}),
            ("evaluate_decision", {
                "instance_path": str(FIXTURES / "instance-decision-context.xml"),
                "table_json": json.dumps({"rules": [{"conditions": [], "outcome": "PERMIT"}]}),
            }),
        ]
        for tool_name, args in test_calls:
            request = {
                "jsonrpc": "2.0", "id": 1,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": args},
            }
            response = _handle_request(request)
            assert "result" in response, f"{tool_name} returned error: {response}"
            content = response["result"]["content"]
            assert len(content) == 1, f"{tool_name} returned {len(content)} content blocks"
            assert content[0]["type"] == "text", f"{tool_name} content type: {content[0]['type']}"
            # Must be valid JSON
            parsed = json.loads(content[0]["text"])
            assert parsed is not None, f"{tool_name} returned None"


class TestProtocolVersionNegotiation:
    """
    initialize must negotiate, not assert. The server previously answered
    with a hardcoded revision whatever the client asked for.
    """

    def _initialize(self, requested=None):
        params = {} if requested is None else {"protocolVersion": requested}
        return _handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": params,
        })["result"]

    @pytest.mark.parametrize("version", SUPPORTED_PROTOCOL_VERSIONS)
    def test_supported_version_is_echoed(self, version):
        assert self._initialize(version)["protocolVersion"] == version

    def test_unsupported_version_falls_back_to_ours(self):
        """
        An older or newer client is answered with a revision we do implement,
        and decides for itself whether to proceed.
        """
        for unsupported in ("2024-11-05", "2026-07-28", "not-a-version"):
            assert (
                self._initialize(unsupported)["protocolVersion"]
                == MCP_PROTOCOL_VERSION
            )

    def test_absent_version_falls_back_to_ours(self):
        assert self._initialize()["protocolVersion"] == MCP_PROTOCOL_VERSION

    def test_advertised_version_is_the_newest_supported(self):
        assert MCP_PROTOCOL_VERSION == SUPPORTED_PROTOCOL_VERSIONS[-1]

    def test_initialization_based_revisions_only(self):
        """
        2026-07-28 removed the initialize handshake in favour of per-request
        _meta fields. This server is initialization-based, so advertising it
        would be a false conformance claim.
        """
        assert "2026-07-28" not in SUPPORTED_PROTOCOL_VERSIONS


class TestToolErrorsAreToolErrors:
    """
    SEP-1303: execution and input-validation failures belong in the result
    as isError, not in a JSON-RPC error, so the calling model can see them
    and correct itself.
    """

    def test_execution_failure_returns_is_error_result(self):
        response = _handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            # Missing every required argument, so the handler raises.
            "params": {"name": "get_governance_status", "arguments": {}},
        })

        assert "error" not in response
        result = response["result"]
        assert result["isError"] is True
        assert result["content"][0]["type"] == "text"

    def test_unknown_tool_is_still_a_protocol_error(self):
        """An unroutable method name is genuinely protocol-level."""
        response = _handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "no_such_tool", "arguments": {}},
        })
        assert response["error"]["code"] == -32601

"""
Decision tables are tracked entities (issue #3): identity, version, content
hash, and receipts bound to the table that produced the decision.
"""
import hashlib
import json

import pytest

from sdcgovernance.decision import decision_table_hash, decision_table_to_dict
from sdcgovernance.jcs import canonicalize
from sdcgovernance.mcp_server import _handle_request, configure_tables, get_registry
from sdcgovernance.receipts import Decision, Receipt, ReceiptChain
from sdcgovernance.tables import TableConflict, TableNotFound, TableRegistry, parse_decision_table

RISK = {
    "name": "risk_check",
    "hit_policy": "FIRST",
    "rules": [
        {"conditions": [{"field": "risk_score", "op": ">=", "value": 8}], "outcome": "DENY", "description": "High risk"},
        {"conditions": [{"field": "risk_score", "op": "<", "value": 8}], "outcome": "PERMIT", "description": "Acceptable"},
    ],
}
# The same table, spelled differently: key order, an explicit empty description.
RISK_RESPELLED = {
    "rules": [
        {"description": "High risk", "outcome": "DENY", "conditions": [{"value": 8, "op": ">=", "field": "risk_score"}]},
        {"description": "Acceptable", "outcome": "PERMIT", "conditions": [{"value": 8, "op": "<", "field": "risk_score"}]},
    ],
    "description": "",
    "hit_policy": "FIRST",
    "name": "risk_check",
}
RISK_V2 = json.loads(json.dumps(RISK))
RISK_V2["rules"][0]["conditions"][0]["value"] = 7


def call_tool(name, arguments):
    response = _handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                "params": {"name": name, "arguments": arguments}})
    result = response["result"]
    text = result["content"][0]["text"]
    if result.get("isError"):
        raise AssertionError(text)
    return json.loads(text)


def tool_error(name, arguments):
    response = _handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                "params": {"name": name, "arguments": arguments}})
    result = response["result"]
    assert result.get("isError"), result
    return result["content"][0]["text"]


@pytest.fixture(autouse=True)
def fresh_registry():
    get_registry().clear()
    configure_tables(None)
    yield
    get_registry().clear()
    configure_tables(None)


class TestTableHash:
    def test_spelling_does_not_change_the_hash(self):
        assert decision_table_hash(parse_decision_table(RISK)) == decision_table_hash(parse_decision_table(RISK_RESPELLED))

    def test_one_threshold_does(self):
        assert decision_table_hash(parse_decision_table(RISK)) != decision_table_hash(parse_decision_table(RISK_V2))

    def test_to_dict_round_trips(self):
        table = parse_decision_table(RISK)
        again = parse_decision_table(decision_table_to_dict(table))
        assert decision_table_to_dict(again) == decision_table_to_dict(table)
        assert decision_table_hash(again) == decision_table_hash(table)

    def test_hash_is_sha256_of_canonical_json(self):
        table = parse_decision_table(RISK)
        expected = hashlib.sha256(canonicalize(decision_table_to_dict(table)).encode("utf-8")).hexdigest()
        assert decision_table_hash(table) == expected


class TestParse:
    @pytest.mark.parametrize("bad, message", [
        ({"hit_policy": "ALL", "rules": []}, "hit_policy"),
        ({"rules": [{"outcome": "MAYBE"}]}, "outcome"),
        ({"rules": [{"outcome": "PERMIT", "conditions": [{"field": "x", "op": "~", "value": 1}]}]}, "op"),
        ({"rules": [{"outcome": "PERMIT", "conditions": [{"field": "x"}]}]}, "condition"),
        ({"rules": "no"}, "rules"),
        ([], "object"),
    ])
    def test_malformed_tables_are_refused_not_defaulted(self, bad, message):
        with pytest.raises(ValueError, match=message):
            parse_decision_table(bad)


class TestRegistry:
    def test_register_get_and_versions(self):
        reg = TableRegistry()
        one = reg.register("cordova.access", "1.0", RISK, domain="access-control", policy="POL-7")
        two = reg.register("cordova.access", "1.1", RISK_V2, domain="access-control")
        reg.register("cordova.access", "1.10", RISK, domain="access-control")
        assert one.table_hash == decision_table_hash(parse_decision_table(RISK))
        assert reg.get("cordova.access", "1.1") is two
        assert reg.versions("cordova.access") == ["1.0", "1.1", "1.10"], "numeric ordering, not text"
        assert reg.get("cordova.access").version == "1.10"
        assert [e.version for e in reg.list(domain="access-control")] == ["1.0", "1.1", "1.10"]
        assert reg.list(domain="retention") == []
        assert len(reg.find_by_hash(one.table_hash)) == 2

    def test_same_content_is_idempotent_and_different_content_is_a_conflict(self):
        reg = TableRegistry()
        first = reg.register("t", "1", RISK)
        assert reg.register("t", "1", RISK_RESPELLED) is first
        with pytest.raises(TableConflict):
            reg.register("t", "1", RISK_V2)
        assert len(reg) == 1

    def test_unknown_ids_and_versions(self):
        reg = TableRegistry()
        reg.register("t", "1", RISK)
        with pytest.raises(TableNotFound):
            reg.get("missing")
        with pytest.raises(TableNotFound):
            reg.get("t", "2")

    @pytest.mark.parametrize("bad", ["", "with space", "slash/y", ".hidden", "x" * 129])
    def test_ids_and_versions_are_tokens(self, bad):
        with pytest.raises(ValueError):
            TableRegistry().register(bad, "1", RISK)
        with pytest.raises(ValueError):
            TableRegistry().register("ok", bad, RISK)

    def test_save_and_load_round_trip(self, tmp_path):
        reg = TableRegistry()
        reg.register("cordova.access", "1.0", RISK, domain="access-control", policy="POL-7")
        reg.register("cordova.retention", "2026-10", RISK_V2, domain="retention")
        paths = reg.save(tmp_path)
        assert sorted(p.name for p in paths) == ["cordova.access--1.0.json", "cordova.retention--2026-10.json"]
        loaded = TableRegistry.from_directory(tmp_path)
        key = lambda e: (e.table_id, e.version, e.table_hash, e.domain, e.policy)
        assert {key(e) for e in loaded.list()} == {key(e) for e in reg.list()}

    def test_a_file_edited_after_registration_is_refused(self, tmp_path):
        reg = TableRegistry()
        reg.register("t", "1", RISK)
        path = reg.save(tmp_path)[0]
        record = json.loads(path.read_text())
        record["table"]["rules"][0]["conditions"][0]["value"] = 3
        path.write_text(json.dumps(record))
        with pytest.raises(ValueError, match="changed after it was registered"):
            TableRegistry.from_directory(tmp_path)

    def test_a_list_file_and_a_missing_directory(self, tmp_path):
        (tmp_path / "bundle.json").write_text(json.dumps([
            {"table_id": "a", "version": "1", "table": RISK},
            {"table_id": "b", "version": "1", "table": RISK_V2, "domain": "d"},
        ]))
        loaded = TableRegistry.from_directory(tmp_path)
        assert [e.table_id for e in loaded.list()] == ["a", "b"]
        with pytest.raises(FileNotFoundError):
            TableRegistry.from_directory(tmp_path / "nowhere")


class TestReceiptBinding:
    def test_table_fields_are_inside_the_hash(self):
        base = dict(decision=Decision.DENY, reasoning="r", timestamp="2026-10-18T00:00:00+00:00")
        plain = Receipt(**base)
        bound = Receipt(**base, table_id="t", table_version="1", table_hash="a" * 64)
        assert plain.receipt_hash != bound.receipt_hash
        assert Receipt(**base, table_id="t", table_version="2", table_hash="a" * 64).receipt_hash != bound.receipt_hash
        assert Receipt(**base, table_id="t", table_version="1", table_hash="b" * 64).receipt_hash != bound.receipt_hash
        assert bound.verify_hash()
        d = bound.to_dict()
        assert (d["table_id"], d["table_version"], d["table_hash"]) == ("t", "1", "a" * 64)

    def test_receipts_without_a_table_hash_as_before(self):
        """Nothing about the hashed content changes for a receipt with no table."""
        r = Receipt(decision=Decision.PERMIT, reasoning="ok", timestamp="2026-10-18T00:00:00+00:00",
                    dimensions_checked=["x"], context_hash="c" * 64)
        content = {
            "decision": "PERMIT", "reasoning": "ok", "status_code": r.status_code.value,
            "instance_id": "", "instance_version": "", "timestamp": r.timestamp,
            "previous_hash": None, "dimensions_checked": ["x"], "errors": [],
            "context_hash": "c" * 64, "canonicalization": r.canonicalization,
        }
        assert r.receipt_hash == hashlib.sha256(canonicalize(content).encode("utf-8")).hexdigest()

    def test_chain_append_binds_the_table(self):
        chain = ReceiptChain()
        r = chain.append(Decision.PERMIT, table_id="t", table_version="1", table_hash="a" * 64)
        assert (r.table_id, r.table_version, r.table_hash) == ("t", "1", "a" * 64)
        assert chain.verify_chain()


class TestMcpTools:
    def test_register_list_and_evaluate_by_id(self):
        reg = call_tool("register_decision_table", {
            "table_id": "cordova.access", "version": "1.0", "table_json": json.dumps(RISK),
            "domain": "access-control", "policy": "POL-7",
        })
        assert reg["table_hash"] == decision_table_hash(parse_decision_table(RISK))
        assert reg["persisted"] is False
        call_tool("register_decision_table", {"table_id": "cordova.access", "version": "1.1", "table_json": json.dumps(RISK_V2)})

        listing = call_tool("list_decision_tables", {})
        assert listing["count"] == 2
        assert "table" not in listing["tables"][0]
        by_id = call_tool("list_decision_tables", {"table_id": "cordova.access"})
        assert [t["version"] for t in by_id["tables"]] == ["1.0", "1.1"]
        assert by_id["tables"][0]["table"]["rules"][0]["conditions"][0]["value"] == 8
        assert call_tool("list_decision_tables", {"domain": "access-control"})["count"] == 1

        latest = call_tool("evaluate_decision", {"table_id": "cordova.access", "extra_context": json.dumps({"risk_score": 7})})
        assert latest["decision"] == "DENY", "1.1 lowered the threshold to 7"
        assert latest["table"] == {"table_id": "cordova.access", "table_version": "1.1",
                                   "table_hash": decision_table_hash(parse_decision_table(RISK_V2))}
        pinned = call_tool("evaluate_decision", {"table_id": "cordova.access", "table_version": "1.0",
                                                 "extra_context": json.dumps({"risk_score": 7})})
        assert pinned["decision"] == "PERMIT"
        rec = pinned["receipt"]
        assert (rec["table_id"], rec["table_version"]) == ("cordova.access", "1.0")
        assert rec["table_hash"] == reg["table_hash"]
        rebuilt = Receipt(decision=Decision(rec["decision"]), reasoning=rec["reasoning"], timestamp=rec["timestamp"],
                          dimensions_checked=rec["dimensions_checked"], table_id=rec["table_id"],
                          table_version=rec["table_version"], table_hash=rec["table_hash"])
        assert rebuilt.receipt_hash == rec["receipt_hash"]

    def test_inline_tables_carry_the_hash_alone(self):
        data = call_tool("evaluate_decision", {"table_json": json.dumps(RISK), "extra_context": json.dumps({"risk_score": 1})})
        assert data["table"] == {"table_id": "", "table_version": "",
                                 "table_hash": decision_table_hash(parse_decision_table(RISK))}
        assert data["receipt"]["table_hash"] == data["table"]["table_hash"]

    def test_the_two_ways_are_exclusive_and_one_is_required(self):
        assert "not both" in tool_error("evaluate_decision", {"table_id": "x", "table_json": json.dumps(RISK)})
        assert "table_id" in tool_error("evaluate_decision", {"extra_context": "{}"})
        assert "needs a `table_id`" in tool_error("evaluate_decision", {"table_version": "1", "table_json": json.dumps(RISK)})
        assert "No decision table" in tool_error("evaluate_decision", {"table_id": "ghost"})

    def test_conflicting_registration_is_a_tool_error(self):
        call_tool("register_decision_table", {"table_id": "t", "version": "1", "table_json": json.dumps(RISK)})
        assert "already registered" in tool_error("register_decision_table",
                                                  {"table_id": "t", "version": "1", "table_json": json.dumps(RISK_V2)})

    def test_tables_dir_persists_and_reloads(self, tmp_path):
        configure_tables(tmp_path)
        reg = call_tool("register_decision_table", {"table_id": "t", "version": "1", "table_json": json.dumps(RISK)})
        assert reg["persisted"] is True
        assert (tmp_path / "t--1.json").exists()
        get_registry().clear()
        configure_tables(tmp_path)
        assert call_tool("list_decision_tables", {})["count"] == 1

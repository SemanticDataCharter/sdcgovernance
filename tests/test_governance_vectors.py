"""
The decision-table and governance-Receipt vectors in test-vectors/ are what
other implementations check against (sdcreceipt-ts among them), so they must
not drift from the library they describe.

Rebuilding them from the library must give the published files, apart from the
version that built them; and each governance Receipt must verify, or fail to,
as the file says.
"""
import importlib.util
import json
import pathlib

from sdcgovernance.receipts import LEGACY_CANONICALIZATION, Decision, Obligation, Receipt, StatusCode

VECTORS = pathlib.Path(__file__).parent.parent / "test-vectors"


def _builder():
    spec = importlib.util.spec_from_file_location("build_governance_vectors", VECTORS / "build_governance_vectors.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _published(name):
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))


def _same(built, published):
    built = json.loads(json.dumps(built, ensure_ascii=False))
    built.pop("sdcgovernance_version")
    published = dict(published)
    published.pop("sdcgovernance_version")
    return built == published


def test_the_decision_table_vectors_are_what_the_library_computes():
    assert _same(_builder().decision_tables(), _published("decision-tables.json")), (
        "decision-tables.json differs from the library; rebuild it with "
        "`PYTHONPATH=src python test-vectors/build_governance_vectors.py` if the change is deliberate"
    )


def test_the_governance_receipt_vectors_are_what_the_library_computes():
    assert _same(_builder().governance_receipts(), _published("governance-receipts.json"))


def _from_wire(wire):
    """A Receipt rebuilt from its JSON form, its hash recomputed from that content."""
    return Receipt(
        decision=Decision(wire["decision"]),
        reasoning=wire["reasoning"],
        status_code=StatusCode(wire["status_code"]),
        obligations=[Obligation(**o) for o in wire["obligations"]],
        instance_id=wire["instance_id"],
        instance_version=wire["instance_version"],
        source_instance_id=wire["source_instance_id"],
        source_version_id=wire["source_version_id"],
        timestamp=wire["timestamp"],
        previous_hash=wire["previous_hash"],
        dimensions_checked=wire["dimensions_checked"],
        errors=wire["errors"],
        context_hash=wire["context_hash"],
        table_id=wire.get("table_id", ""),
        table_version=wire.get("table_version", ""),
        table_hash=wire.get("table_hash", ""),
        # No field on the wire is a receipt hashed before RFC 8785.
        canonicalization=wire.get("canonicalization", LEGACY_CANONICALIZATION),
    )


def test_each_governance_receipt_verifies_as_the_file_says():
    for vector in _published("governance-receipts.json")["vectors"]:
        recomputed = _from_wire(vector["receipt"]).receipt_hash
        assert (recomputed == vector["receipt"]["receipt_hash"]) == vector["verifies"], vector["description"]

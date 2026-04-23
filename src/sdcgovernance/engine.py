"""
GovernanceEngine - the decision engine agents query.

Wraps the validation modules into a stateful engine that agents interact
with through a session. Provides the advisory interface: what transitions
are allowed, can this transition proceed, record what happened.

This is the core that both the Python API and the MCP server expose.

Usage::

    from sdcgovernance.engine import GovernanceEngine

    engine = GovernanceEngine(schema_path)
    options = engine.get_allowed_transitions(instance)
    decision = engine.evaluate_transition(instance, target_state, actor)
    engine.record_provenance(instance, activity, agent, result)
"""

# TODO: Phase 2 implementation
# - GovernanceEngine class wrapping model_inspector + validation modules
# - get_allowed_transitions(instance) -> list of transitions with conditions
# - evaluate_transition(instance, target_state, actor) -> decision + receipt
# - record_provenance(instance, activity, agent, result) -> PROV record
# - get_governance_status(schema) -> which governance components exist
# - validate_governance(schema, instance) -> full validation (convenience)
# - Receipt chain management across multiple calls

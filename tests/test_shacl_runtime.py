"""
Tests for SHACL constraint validation - Phase 6.

Tests SHACL shapes validation via pyshacl, cross-entity constraints,
and integration with governance decisions.
"""

import pytest
from sdcgovernance.shacl_runtime import (
    ShaclResult,
    ShaclViolation,
    validate_shacl_from_strings,
)
from sdcgovernance.receipts import Decision


# Simple SHACL shapes for testing
PERSON_SHAPE = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:PersonShape
    a sh:NodeShape ;
    sh:targetClass ex:Person ;
    sh:property [
        sh:path ex:name ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:message "Person must have a name" ;
    ] ;
    sh:property [
        sh:path ex:age ;
        sh:minCount 1 ;
        sh:datatype xsd:integer ;
        sh:minInclusive 0 ;
        sh:message "Person must have a non-negative age" ;
    ] .
"""

# Cross-entity shape: patient must have a provider
CROSS_ENTITY_SHAPE = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:PatientShape
    a sh:NodeShape ;
    sh:targetClass ex:Patient ;
    sh:property [
        sh:path ex:hasProvider ;
        sh:minCount 1 ;
        sh:class ex:Provider ;
        sh:message "Patient must have at least one Provider" ;
    ] .

ex:ProviderShape
    a sh:NodeShape ;
    sh:targetClass ex:Provider ;
    sh:property [
        sh:path ex:providerName ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:message "Provider must have a name" ;
    ] .
"""


class TestShaclValidation:
    """Basic SHACL shape validation."""

    def test_valid_data_conforms(self):
        data = """
        @prefix ex: <http://example.org/> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

        ex:person1 a ex:Person ;
            ex:name "John Doe"^^xsd:string ;
            ex:age 30 .
        """
        result = validate_shacl_from_strings(data, PERSON_SHAPE)
        assert result.conforms is True
        assert result.decision == Decision.PERMIT
        assert len(result.violations) == 0

    def test_missing_name_violates(self):
        data = """
        @prefix ex: <http://example.org/> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

        ex:person1 a ex:Person ;
            ex:age 30 .
        """
        result = validate_shacl_from_strings(data, PERSON_SHAPE)
        assert result.conforms is False
        assert result.decision == Decision.DENY
        assert len(result.violations) >= 1
        assert any("name" in v.message.lower() for v in result.violations)

    def test_missing_age_violates(self):
        data = """
        @prefix ex: <http://example.org/> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

        ex:person1 a ex:Person ;
            ex:name "John Doe"^^xsd:string .
        """
        result = validate_shacl_from_strings(data, PERSON_SHAPE)
        assert result.conforms is False
        assert result.decision == Decision.DENY

    def test_multiple_violations_reported(self):
        data = """
        @prefix ex: <http://example.org/> .

        ex:person1 a ex:Person .
        """
        result = validate_shacl_from_strings(data, PERSON_SHAPE)
        assert result.conforms is False
        assert len(result.violations) >= 2

    def test_empty_data_graph(self):
        data = """
        @prefix ex: <http://example.org/> .
        """
        result = validate_shacl_from_strings(data, PERSON_SHAPE)
        assert result.conforms is True  # No target nodes = conforms

    def test_report_text_present(self):
        data = """
        @prefix ex: <http://example.org/> .
        ex:person1 a ex:Person .
        """
        result = validate_shacl_from_strings(data, PERSON_SHAPE)
        assert result.report_text != ""


class TestCrossEntityConstraints:
    """Cross-entity SHACL validation (P6-03)."""

    def test_patient_with_provider_conforms(self):
        data = """
        @prefix ex: <http://example.org/> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

        ex:patient1 a ex:Patient ;
            ex:hasProvider ex:provider1 .

        ex:provider1 a ex:Provider ;
            ex:providerName "Dr. Smith"^^xsd:string .
        """
        result = validate_shacl_from_strings(data, CROSS_ENTITY_SHAPE)
        assert result.conforms is True
        assert result.decision == Decision.PERMIT

    def test_patient_without_provider_violates(self):
        data = """
        @prefix ex: <http://example.org/> .

        ex:patient1 a ex:Patient .
        """
        result = validate_shacl_from_strings(data, CROSS_ENTITY_SHAPE)
        assert result.conforms is False
        assert result.decision == Decision.DENY
        assert any("provider" in v.message.lower() for v in result.violations)

    def test_provider_without_name_violates(self):
        data = """
        @prefix ex: <http://example.org/> .

        ex:patient1 a ex:Patient ;
            ex:hasProvider ex:provider1 .

        ex:provider1 a ex:Provider .
        """
        result = validate_shacl_from_strings(data, CROSS_ENTITY_SHAPE)
        assert result.conforms is False
        assert any("name" in v.message.lower() for v in result.violations)

    def test_multiple_providers_valid(self):
        data = """
        @prefix ex: <http://example.org/> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

        ex:patient1 a ex:Patient ;
            ex:hasProvider ex:provider1 ;
            ex:hasProvider ex:provider2 .

        ex:provider1 a ex:Provider ;
            ex:providerName "Dr. Smith"^^xsd:string .

        ex:provider2 a ex:Provider ;
            ex:providerName "Dr. Jones"^^xsd:string .
        """
        result = validate_shacl_from_strings(data, CROSS_ENTITY_SHAPE)
        assert result.conforms is True


class TestShaclViolationDetails:
    """Violation details extraction."""

    def test_violation_has_focus_node(self):
        data = """
        @prefix ex: <http://example.org/> .
        ex:person1 a ex:Person .
        """
        result = validate_shacl_from_strings(data, PERSON_SHAPE)
        assert len(result.violations) > 0
        assert any(v.focus_node != "" for v in result.violations)

    def test_violation_has_message(self):
        data = """
        @prefix ex: <http://example.org/> .
        ex:person1 a ex:Person .
        """
        result = validate_shacl_from_strings(data, PERSON_SHAPE)
        assert any(v.message != "" for v in result.violations)

    def test_errors_populated_from_violations(self):
        data = """
        @prefix ex: <http://example.org/> .
        ex:person1 a ex:Person .
        """
        result = validate_shacl_from_strings(data, PERSON_SHAPE)
        assert len(result.errors) > 0


class TestShaclGovernanceIntegration:
    """SHACL results as governance decisions (P6-02)."""

    def test_conformant_is_permit(self):
        data = """
        @prefix ex: <http://example.org/> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        ex:person1 a ex:Person ;
            ex:name "John"^^xsd:string ;
            ex:age 30 .
        """
        result = validate_shacl_from_strings(data, PERSON_SHAPE)
        assert result.decision == Decision.PERMIT

    def test_non_conformant_is_deny(self):
        data = """
        @prefix ex: <http://example.org/> .
        ex:person1 a ex:Person .
        """
        result = validate_shacl_from_strings(data, PERSON_SHAPE)
        assert result.decision == Decision.DENY

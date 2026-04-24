"""
Provenance/Audit validation and W3C PROV record generation for SDC governance.

Audit and Provenance are the same governance dimension in SDC. Both answer:
what happened, who did it, when, to what entity. This module handles both.

The SDC RM component is sdc4:AuditType, which provides who/where/when
tracking of instances as they move between systems:
- system-id (XdStringType, required) -> prov:Entity context
- system-user (PartyType, optional) -> prov:Agent
- location (ClusterType, optional) -> provenance metadata
- timestamp (xs:dateTime, required) -> prov:Activity temporal bounds

External docs use "Provenance" (W3C vocabulary). Implementation discovers
AuditType components by their PROV-O vocabulary bindings.

Validates that provenance records in the XML instance meet the requirements
defined in the SDC data model (discovered via W3C PROV-O vocabulary bindings).
Also validates retention policy (discovered via W3C DPV vocabulary bindings)
and generates W3C PROV-O compliant records for governance decisions.

Retention policies (modeled via DPV, same vocabulary used for SDC access control):
- Most recent record + hash (long-lived records, e.g., patient records)
- Last N records (configurable per model)
- Full chain (short-lived records, e.g., financial transactions)

Industry-specific agents advise on retention policy during modeling.
sdcgovernance validates whatever the model defines.

Standards: W3C PROV-O (https://www.w3.org/TR/prov-o/)
           W3C PROV-DM (https://www.w3.org/TR/prov-dm/)
           W3C Activity Streams 2.0 (https://www.w3.org/TR/activitystreams-core/)
           W3C DPV (https://w3c.github.io/dpv/dpv/)
"""

# TODO: Phase 4 implementation
# - Discover provenance components via PROV-O vocabulary bindings
# - Discover retention policy via DPV vocabulary bindings
# - Validate provenance content in instance against model requirements
# - Validate retention policy: correct number of records present, hash chain intact
# - Generate PROV records for governance decisions (PERMIT/DENY/INDETERMINATE)
# - prov:Activity, prov:Agent, prov:Entity relationships
# - Activity types from W3C Activity Streams 2.0 vocabulary
# - SHA-256 hash of entity state before and after
# - RDF/Turtle export via rdflib

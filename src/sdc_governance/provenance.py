"""
W3C PROV record generation for SDC governance.

Produces PROV-O compliant provenance records for every state change
in a governed system. Records are exportable as RDF/Turtle and
queryable via SPARQL.

Standards: W3C PROV-O (https://www.w3.org/TR/prov-o/)
           W3C PROV-DM (https://www.w3.org/TR/prov-dm/)
"""

# TODO: Phase 1 implementation
# - prov:Activity for each state change (create, update, delete, transition)
# - prov:Agent for the actor (user, API client, agent)
# - prov:Entity for the data entity affected
# - prov:wasGeneratedBy / prov:used relationships
# - prov:startedAtTime / prov:endedAtTime temporal bounds
# - SHA-256 hash of entity state before and after
# - RDF/Turtle export via rdflib

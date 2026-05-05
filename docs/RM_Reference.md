# SDC Reference Model Components for Governance

**Purpose**: Maps SDC4 Reference Model types to sdcgovernance governance dimensions. This is the implementation reference - how governance is structurally present in the data model and instances.

**Source**: [SDC4 Reference Model Documentation](https://semanticdatacharter.com/docs/sdc4/)

---

## DMType - The Root

[DMType documentation](https://semanticdatacharter.com/docs/sdc4/sdc4_xsd_Complex_Type_sdc4_DMType.html#DMType)

DMType is the root node of every Data Model. It already defines governance slots as optional elements. sdcgovernance inspects these slots to determine which governance dimensions are active.

| Element | Type | Cardinality | Governance Dimension |
|---|---|---|---|
| `workflow` | ClusterType | 0..1 | **Workflow** - state definitions and transitions as a cluster tree |
| `current-state` | xs:string | 0..1 | **Workflow** - current state from workflow engine |
| `sdc4:Audit` | AuditType | 0..* | **Provenance/Audit** - unbounded audit trail records |
| `attestation` | AttestationType | 0..1 | **Attestation** - data instance attestation |
| `subject` | PartyType | 0..1 | **Party/Role** - human subject (patient, customer, etc.) |
| `provider` | PartyType | 0..* | **Party/Role** - information source(s) |
| `sdc4:Participation` | ParticipationType | 0..* | **Party/Role** - additional participations |
| `acs` | XdLinkType | 0..1 | **Access Control** - link to access control system. DPV recommended but as an XdLinkType it can reference any vocabulary, including industry-specific or local system vocabularies. |

Elements with governance relevance but not primary governance dimensions:

| Element | Type | Cardinality | Governance Relevance |
|---|---|---|---|
| `instance_id` | xs:string | **1..1** | **Receipt chain identity** - mandatory, globally unique CUID2 identifier. Receipts reference instance_id to verify provenance trail belongs to the correct instance lineage. |
| `instance_version` | xs:string | 0..1 | **Receipt chain versioning** - paired with instance_id. Provenance chain tracks which version each governance decision applied to. |
| `source_instance_id` | xs:string | 0..1 | **Source system lineage** - identifier of the data instance in the originating source system (e.g., Epic, SAP). Decouples sovereign SDC identity from legacy source identity, enabling auditable data lineage across system boundaries. |
| `source_version_id` | xs:string | 0..1 | **Source system versioning** - version identifier as it existed in the originating source system. Paired with source_instance_id for complete upstream reference. |
| `protocol` | XdStringType | 0..1 | **Decision table input** - clinical guideline or operations protocol under which data was captured. A workflow transition may only be valid under certain protocols. Consumed as a condition input by DMN decision tables (Phase 5). |
| `sdc4:XdLink` | XdLinkType | 0..* | **Governed relationships** - originally intended for model supersession ("this model replaces model X"), but the semantics support any type of related link. See XdLink governance section below. |

Elements sdcgovernance does not inspect (except as noted):
- `label` (xs:string, 0..1) - semantic name
- `dm-language` (xs:language, 1..1) - language code
- `dm-encoding` (xs:string, 1..1) - encoding, default utf-8
- `creation_timestamp` (xs:dateTime, 0..1) - runtime creation timestamp
- `sdc4:Item` (ItemType, 1..1) - the actual data content (sdcvalidator's domain). **Exception**: sdcgovernance inspects a `validation-details` sub-cluster within the data Cluster if present. See Validation Details section below.

---

## XdLinkType - Governed Relationships

XdLinkType extends XdAnyType and carries `link`, `relation`, and `relation-uri` fields. The `relation` and `relation-uri` fields carry the semantics of WHY the link exists, not just WHERE it points.

Originally intended for model supersession chains ("this model replaces model X"), the semantics are general enough to define any type of related link. In a governance context:

**Supersession chains**: "This model replaces model X." sdcgovernance can validate that a transition from an old model version to a new one is legitimate - the new model's XdLink points back to the predecessor with the appropriate relation type.

**Cross-domain references**: "This health record references this law enforcement incident." Governance can check whether the actor has the right to create or follow that link across domain boundaries. The CordovaOS Contagion Beat 6 scenario - law enforcement accessing health records - is carried by XdLinks between domain instances.

**Evidence references**: "This governance decision was based on these external artifacts." An XdLink from a governed instance to the evidence that justified the decision. Pairs naturally with the receipt chain.

**Regulatory references**: "This instance is governed under HIPAA Rule X" or "EU AI Act Article 12." Industry-specific agents can validate that the governance components in the model satisfy the linked regulation's requirements.

sdcgovernance can validate that the `relation` type on an XdLink is appropriate for the governance context - a health record cannot link to a law enforcement incident with relation type "replaces."

**Key insight for model_inspector**: Governance components are at known positions in the DMType root - not scattered arbitrarily in the model. The inspector reads the DM and checks which optional governance slots are populated and what vocabulary bindings they carry.

---

## ClusterType - Grouping and Workflow Trees

[ClusterType documentation](https://semanticdatacharter.com/docs/sdc4/sdc4_xsd_Complex_Type_sdc4_ClusterType.html#ClusterType)

ClusterType extends ItemType. It is the grouping component - may contain further instances of itself or any eXtended datatype, in an ordered list.

| Element | Type | Cardinality |
|---|---|---|
| `label` | xs:string | 0..1 |
| `sdc4:Items` | ItemType | 0..* |

**Governance usage**: The `DM.workflow` element is a ClusterType. For workflow governance:
- The top-level Workflow cluster contains sub-clusters representing valid paths (decision tree branches)
- Each sub-cluster contains XdOrdinal components defining the sequenced states in that path
- ClusterType's recursive composition (clusters within clusters) naturally models branching workflows
- Components (same CUID2) can be reused across sub-clusters to represent shared states between paths

**Other governance usage**:
- `AuditType.location` is a ClusterType (location information for provenance)
- `PartyType.party-details` is a ClusterType (structured party information)

---

## AuditType - Provenance/Audit Records

[AuditType documentation](https://semanticdatacharter.com/docs/sdc4/sdc4_xsd_Complex_Type_sdc4_AuditType.html#AuditType)

"Provides a mechanism to identify the who/where/when tracking of instances as they move from system to system."

| Element | Type | Cardinality | PROV-O Mapping |
|---|---|---|---|
| `label` | xs:string | 0..1 | - |
| `system-id` | XdStringType | **1..1** | prov:Entity context (which system handled it) |
| `system-user` | PartyType | 0..1 | prov:Agent (who handled it) |
| `location` | ClusterType | 0..1 | Provenance metadata (where) |
| `timestamp` | xs:dateTime | **1..1** | prov:Activity temporal bounds (when) |

**Key facts**:
- `system-id` and `timestamp` are required. Every audit record must identify the system and the time.
- `system-user` is optional (some system-to-system transfers may not have a human user).
- DM.Audit is 0..* - a DM instance can carry zero or many audit records. This is where the retention policy applies (most recent + hash, last N, or full chain).
- External documentation uses "Provenance" (W3C PROV-O vocabulary). Implementation uses AuditType.
- sdcgovernance discovers AuditType by PROV-O vocabulary bindings on the components.

---

## Validation Details - Entity State Hashes

In SDC4, entity state hashes for tamper-evident provenance chains are modeled as a `validation-details` sub-cluster within the data Cluster (`sdc4:Item`). This is necessary because AuditType does not have a native slot for validation metadata in SDC4. (An SDC5 issue has been filed to add a `validation` ClusterType slot to AuditType directly.)

The `validation-details` cluster uses XdFileType components, leveraging the RM-defined `hash-function` and `hash-result` elements:

```
sdc4:Item (data Cluster)
├── [domain-specific data components]
└── validation-details (ClusterType, 0..1)
    ├── entity-state-before (XdFileType, 0..1)
    │   ├── hash-function: "SHA-256"
    │   └── hash-result: [computed hash of entity state before the activity]
    └── entity-state-after (XdFileType, 0..1)
        ├── hash-function: "SHA-256"
        └── hash-result: [computed hash of entity state after the activity]
```

**Key facts**:
- `hash-function` and `hash-result` are existing XdFileType elements defined in the SDC4 RM. No namespace extensions are introduced.
- sdcgovernance discovers the `validation-details` cluster by vocabulary bindings, consistent with how it discovers other governance components.
- The hash chain enables detection of unauthorized modifications, gaps in the provenance chain, and retroactive alteration of records.
- In PROV-O RDF export, these hashes are represented as structured blank nodes linked to each `prov:Activity` via `sdc4:validation-details`.

**SDC5 note**: An issue has been filed on the sdc5-planning branch to add a `validation` ClusterType slot directly to AuditType, eliminating the need to place validation metadata in the data Cluster.

---

## AttestationType - Authority Assertions

[AttestationType documentation](https://semanticdatacharter.com/docs/sdc4/sdc4_xsd_Complex_Type_sdc4_AttestationType.html#AttestationType)

"Record an attestation by a party of the DM content. The type of attestation is recorded by the reason attribute, which may be coded."

| Element | Type | Cardinality | VC Mapping |
|---|---|---|---|
| `label` | xs:string | 0..1 | - |
| `view` | XdFileType | 0..1 | Visual representation of attested content (e.g., screen image) |
| `proof` | XdFileType | 0..1 | Proof of attestation (e.g., GPG signature) |
| `reason` | XdStringType | 0..1 | Reason/type of attestation, usually coded from standard vocabulary |
| `committer` | PartyType | 0..1 | Identity of person who committed the item (maps to VC issuer) |
| `committed` | xs:dateTime | 0..1 | Timestamp of committal |
| `pending` | xs:boolean | **1..1** | True if outstanding; false if completed |

**Key facts**:
- `pending` is the only required element. An attestation can exist in a pending state before it is completed.
- `committer` maps to the W3C VC issuer concept - who is making the assertion.
- `proof` supports cryptographic attestation (GPG signatures, etc.).
- `reason` carries the type of attestation, ideally bound to a standard vocabulary.
- DM.attestation is 0..1 - a DM instance carries zero or one attestation.
- Attestation is independent from workflow. They compose optionally.

---

## PartyType - Actor Identity

[PartyType documentation](https://semanticdatacharter.com/docs/sdc4/sdc4_xsd_Complex_Type_sdc4_PartyType.html#PartyType)

"Description of a party, including an optional external link to data for this party in a demographic or other identity management system."

| Element | Type | Cardinality |
|---|---|---|
| `label` | xs:string | 0..1 |
| `party-name` | xs:string | 0..1 |
| `party-ref` | XdLinkType | 0..1 |
| `party-details` | ClusterType | 0..1 |

**Key facts**:
- All elements are optional. Anonymous party information is valid.
- `party-ref` links to an external identity management system - this is how party identity is resolved across domain boundaries.
- PartyType appears in multiple governance contexts: DM.subject, DM.provider, AuditType.system-user, AttestationType.committer, ParticipationType.performer.
- For party/role governance, the role is carried by the context (provider, committer, performer function) not by PartyType itself.

---

## ParticipationType - Role in Activity

[ParticipationType documentation](https://semanticdatacharter.com/docs/sdc4/sdc4_xsd_Complex_Type_sdc4_ParticipationType.html#ParticipationType)

"A participation of a Party (any Actor or Role) in an activity."

| Element | Type | Cardinality |
|---|---|---|
| `label` | xs:string | 0..1 |
| `performer` | PartyType | 0..1 |
| `function` | XdStringType | 0..1 |
| `mode` | XdStringType | 0..1 |
| `start` | xs:dateTime | 0..1 |
| `end` | xs:dateTime | 0..1 |

**Key facts**:
- `function` is the role/function of the performer. This is where role-based governance checks match - "only parties with function 'approver' can perform this action."
- `mode` captures how the participation happened (present, by telephone, by email).
- `start` and `end` provide temporal bounds for the participation.
- DM.Participation is 0..* - a DM instance can have multiple participations.
- ParticipationType maps to W3C PROV concepts: performer maps to prov:Agent, function maps to prov:hadRole, start/end map to temporal bounds.

---

## How model_inspector Uses This

The model_inspector does NOT need to search arbitrarily through the model for governance components. The DMType root defines exactly where they are:

```
DM (DMType root)
├── dm-label (xs:string, 1..1)       → Semantic name (fixed per model)
├── dm-language (xs:language, 1..1)  → Language code
├── dm-encoding (xs:string, 1..1)    → Character encoding
├── creation_timestamp (xs:dateTime, 0..1) → Runtime creation instant
├── instance_id (xs:string, 1..1)    → Receipt chain identity (mandatory, CUID2)
├── instance_version (xs:string, 0..1) → Receipt chain versioning
├── source_instance_id (xs:string, 0..1) → Source system lineage (e.g., Epic, SAP)
├── source_version_id (xs:string, 0..1) → Source system versioning
├── current-state (xs:string, 0..1)  → Current workflow position
├── sdc4:Item (ItemType, 1..1)       → Data content (sdcvalidator's domain)
│   ├── [domain-specific components]
│   └── validation-details (ClusterType, 0..1) → Entity state hashes
│       ├── entity-state-before (XdFileType) → hash-function + hash-result
│       └── entity-state-after (XdFileType)  → hash-function + hash-result
├── subject (PartyType, 0..1)        → Party/Role dimension
├── provider[] (PartyType, 0..*)     → Party/Role dimension
├── Participation[] (0..*)           → Party/Role dimension
│   ├── performer (PartyType)
│   └── function (XdStringType)     → Role check target
├── protocol (XdStringType, 0..1)    → DMN decision table input
├── workflow (ClusterType, 0..1)     → Workflow dimension
│   ├── sub-cluster: Path A          → Valid workflow path
│   │   ├── XdOrdinal: State 1      → Sequenced state (SCXML label)
│   │   ├── XdOrdinal: State 2
│   │   └── XdOrdinal: State 3
│   └── sub-cluster: Path B          → Alternative path (branching)
│       ├── XdOrdinal: State 1      → Same CUID2 = shared state
│       ├── XdOrdinal: State 4
│       └── XdOrdinal: State 5
├── acs (XdLinkType, 0..1)          → Access control (DPV recommended, any vocabulary via link)
├── Audit[] (AuditType, 0..*)        → Provenance/Audit dimension
│   ├── system-id (required)
│   ├── system-user (PartyType)
│   ├── location (ClusterType)
│   └── timestamp (required)
├── attestation (AttestationType, 0..1) → Attestation dimension
│   ├── committer (PartyType)
│   ├── proof (XdFileType)
│   ├── reason (XdStringType)
│   └── pending (required)
└── XdLink[] (XdLinkType, 0..*)      → Governed relationships
    ├── link                         → Target URI
    ├── relation                     → Why this link exists
    └── relation-uri                 → Vocabulary term for relation type
```

model_inspector checks:
1. Is `instance_id` present? → Store for receipt chain identity. Pair with `instance_version` if present.
2. Is `workflow` populated? → Workflow governance active. Extract cluster tree.
3. Is `current-state` populated? → Workflow state tracking active.
4. Are there `Audit` elements? → Provenance governance active. Check retention policy via DPV bindings on `acs`.
5. Is `attestation` populated? → Attestation governance active.
6. Is `subject` populated? → Party governance active (subject identity).
7. Are there `provider` elements? → Party governance active (information source identity).
8. Are there `Participation` elements with `function` constraints? → Party/Role governance active.
9. Is `protocol` populated? → Available as condition input for DMN decision tables.
10. Is `acs` populated? → Access control and retention policy vocabulary available.
11. Are there `XdLink` elements? → Governed relationships present. Validate relation types against governance context.
12. Is there a `validation-details` cluster in the data Cluster? → Entity state hashes present for tamper-evident provenance. Discovered by vocabulary bindings.

Most checks are at known positions in the DM root. The `validation-details` cluster is the one exception - it lives inside the data Cluster (`sdc4:Item`) and is discovered by vocabulary bindings rather than by fixed position. This exception is documented for SDC5 resolution (AuditType should carry validation details natively).

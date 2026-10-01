# STRATEGY CANDIDATE REGISTRY

**Registry schema:** `CANDIDATE_REGISTRY_V1`  
**Registry version:**  
**Created UTC:**
**Predecessor version / exact-byte SHA-256 (or null for root):**
**Frozen UTC:**  
**Structured registry:** validated `CANDIDATE_REGISTRY_V1` JSON
**Identity:** version and exact-byte SHA-256 are stored by external receipts

# Purpose

This registry records the complete strategy universe considered in the research program.

Strategies must not disappear from the registry because they:

- performed poorly;
- could not be implemented;
- required unavailable data;
- required unsupported engine functionality;
- were abandoned;
- failed validation;
- were later adapted.

The registry exists to control survivorship and selection bias.

A stable Candidate ID and `IDENTIFIED` intake timestamp must be created before
substantive source review, strategy formalization, or any historical testing.
Production preflight rejects an unregistered candidate.

# Candidate Universe

| Candidate ID | Strategy | Source | Inclusion date | Initial status | Current status | Reason |
|---|---|---|---|---|---|---|
| C001 | | | | | | |

Allowed statuses:

- `IDENTIFIED`
- `SOURCE_REVIEW`
- `SPEC_DRAFT`
- `BLOCKED_SOURCE_AMBIGUITY`
- `BLOCKED_DATA`
- `BLOCKED_ENGINE`
- `FROZEN`
- `BACKTESTED`
- `REJECTED`
- `ADVANCES_TO_ADAPTATION`
- `ABANDONED`

# Variant Registry

Every tested or materially considered variant must remain visible. The
structured registry also requires parent ID, creation time, exact change,
parameter changes/search space, spec hash, canonical parameter-identity hash,
computed fidelity class, and historical results already seen.

| Variant ID | Candidate ID | Version | Type | Created before/after result | Status |
|---|---|---|---|---|---|
| C001-V1 | | | PURE_REPLICATION / TRANSFER / ADAPTED | | |

# Candidate Inclusion Rules

Program-level candidate selection must be defined before results are used for ranking.

Record:

**Universe definition:**  

**Inclusion criteria:**  

**Exclusion criteria:**  

**Maximum / target candidate count:**  

**Sources searched:**  

# Rejected / Blocked Candidates

| Candidate ID | Stage | Reason | Evidence |
|---|---|---|---|
| | | | |

Blocked or failed candidates remain part of the historical research record.

# Program Counts

Counts are computed from structured candidate/variant rows. Manually entered
totals are non-authoritative.

# Change Ledger

| Registry version | Date UTC | Change | Reason |
|---|---|---|---|
| | | | |

Every non-root version supplies its predecessor document for validation. Never
silently delete a candidate or variant from a previous registry version. A
candidate/variant/version identity cannot be reused for different parameters or
spec bytes.

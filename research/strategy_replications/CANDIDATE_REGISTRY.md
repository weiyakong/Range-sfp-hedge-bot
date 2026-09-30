# STRATEGY CANDIDATE REGISTRY

**Registry schema:** `CANDIDATE_REGISTRY_V1`  
**Registry version:**  
**Frozen UTC:**  
**Git commit:**  
**SHA-256:**  

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

Every tested or materially considered variant must remain visible.

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

**Candidates identified:**  
**Specs started:**  
**Blocked before backtest:**  
**Backtested:**  
**Adapted:**  
**Rejected after backtest:**  
**Still active:**  

# Change Ledger

| Registry version | Date UTC | Change | Reason |
|---|---|---|---|
| | | | |

Never silently delete a candidate or variant from a previous registry version.

# Strategy Replication Enforcement Layer V1

Markdown files in this directory explain the research standard. They are not
parsed and cannot authorize a production historical run.

Machine authority is split as follows:

- Candidate Registry JSON: candidate intake, status history, and variants.
- Evaluation Protocol JSON: common window, execution, metrics, ranking,
  protected validation, and multiple-testing rules.
- Strategy Spec JSON: source evidence, fidelity, rules, parameters, data
  allowlist, state decisions, tests, and strategy-specific exceptions.
- Capability manifest: the exact supported V2 execution contract.
- Run config: effective values used by V2.
- Freeze/run receipts: immutable hashes and post-run lineage.

Schemas are in `schema/`. Domain invariants are enforced by the standard-library
validators in `validation/`; no arbitrary Markdown parsing or third-party schema
dependency is required.

## Freeze

```bash
python3 -m research.strategy_replications.validation.validate_freeze \
  --spec path/to/spec.json \
  --registry path/to/registry.json \
  --protocol path/to/protocol.json \
  --capability research/strategy_replications/capability/backtester_v2_capabilities.json \
  --data-manifest path/to/data-manifest.json \
  --repo-root . \
  --receipt-out path/to/freeze_receipt.json
```

The command reports every detected defect and writes a receipt only on PASS.
Receipt files are immutable: existing files are never overwritten.

## Production preflight

```bash
python3 -m research.strategy_replications.validation.validate_production_run \
  --spec path/to/spec.json --registry path/to/registry.json \
  --protocol path/to/protocol.json \
  --capability research/strategy_replications/capability/backtester_v2_capabilities.json \
  --data-manifest path/to/data-manifest.json \
  --strategy-code path/to/strategy.py \
  --receipt path/to/freeze_receipt.json --repo-root .
```

Declaring `FROZEN` without a valid receipt never passes this gate.

## Hashing and immutability

Every SHA-256 is calculated over the exact bytes stored on disk. No document
contains its own hash. A freeze receipt is external to all artifacts it hashes.
The output manifest similarly excludes itself; its exact-byte SHA-256 is stored
in the external run receipt. Frozen specs are never edited with run facts or
change history.

## Data access limitation

V1 enforces an explicit strategy input declaration against the spec allowlist.
It does not statically analyze arbitrary Python or prevent direct filesystem
access by malicious strategy code. Production runners must expose inputs through
the declared interface and invoke preflight before execution.

## Status mapping

`DRAFT` strategy specs correspond to registry `IDENTIFIED`, `SOURCE_REVIEW`, or
`SPEC_DRAFT`. `BLOCKED` corresponds to `BLOCKED_SOURCE`, `BLOCKED_DATA`, or
`BLOCKED_ENGINE`. `FROZEN` and `TESTED` correspond to registry `FROZEN` and
`BACKTESTED`. A freeze receipt is issued only for the exact `FROZEN` pair.

## Exit ordering

Engine-controlled ordering is authoritative in the capability manifest and V2
engine. A strategy spec declares only strategy-controlled simultaneous choices;
it cannot override liquidation, gap, protective-order, or callback ordering.

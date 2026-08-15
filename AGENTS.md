# AGENTS.md

## Purpose

This repository contains research, data-processing, and trading-system development code.

Data correctness, provenance, causality, reproducibility, preservation of approved behavior, and verifiable implementation are higher priority than implementation speed.

Code running successfully or producing files is not sufficient evidence that a task is complete.

A task is complete only when its explicit requirements have been implemented and the applicable validation gates have actually passed.

---

## 1. Responsibility boundaries

The current approved specification defines WHAT the system must calculate and produce.

This `AGENTS.md` defines HOW implementation and verification must be performed.

Do not use a task specification to silently bypass engineering integrity requirements such as:

- no fabricated data;
- honest QA status;
- preservation of provenance;
- no false PASS reporting;
- required validation;
- causal integrity.

If an explicit user-approved requirement conflicts with an engineering rule in this file, report the conflict clearly and follow only the explicitly approved exception.

Routine implementation decisions do not require user approval. Make reasonable engineering decisions within the approved specification and repository conventions.

Ask or stop only when a decision would change business logic, data semantics, approved behavior, external dependencies, destructive behavior, or remote repository state.

---

## 2. Source of truth

For task-specific business logic, use this precedence:

1. Current approved specification and acceptance criteria.
2. Approved data contracts and schemas.
3. Approved behavior.
4. Current production code.
5. Legacy or failed implementations.

Approved behavior means behavior that is established by at least one of the following:

- the current approved specification;
- approved acceptance criteria;
- regression tests that protect previously confirmed behavior;
- an explicit user statement that the behavior is correct or must be preserved.

If it is unclear whether existing behavior is approved, do not remove or materially change it silently. Preserve it where safe and report the ambiguity.

Do not silently reconcile conflicting authoritative requirements.

Do not invent missing business logic.

---

## 3. Preserve approved behavior

When modifying an existing pipeline:

- preserve previously approved functionality unless explicitly changed or removed;
- preserve required outputs unless explicitly removed;
- preserve semantic meaning of existing fields;
- do not silently rename, delete, repurpose, or change units of existing columns;
- do not replace an approved calculation with an approximation unless explicitly authorized.

A new version must not lose unrelated approved functionality merely because the current task focuses on another component.

If a change or removal appears necessary, report it explicitly.

---

## 4. No silent assumptions

Do not guess:

- file meaning;
- market source;
- timeframe;
- symbol;
- units;
- timezone;
- structural relationships;
- missing values;
- missing history;
- future values;
- expected schema;
- business rules.

Use repository files, approved specifications, manifests, schemas, and supplied data as evidence.

If information is missing and blocks one component, mark that component blocked and continue independent work where safe.

Stop the entire task only when continuing would require guessing or would corrupt downstream results.

---

## 5. Data provenance

Preserve source provenance end to end.

Never overwrite an existing provenance field with a generic convenience value.

In particular:

- do not silently convert spot data to futures data;
- do not silently convert futures data to spot data;
- do not mix market sources unless the specification explicitly defines the relationship;
- do not relabel mixed data as a single source;
- preserve source file, market source, symbol, timeframe, and relevant coverage metadata when available.

Any transformation combining sources must be explicit, reproducible, and tested.

---

## 6. No fabricated production data

Production and research outputs must use available source data only.

Never:

- synthesize missing market candles;
- silently interpolate missing periods;
- extend regimes beyond available evidence;
- fill unavailable future horizons;
- fabricate successful QA results;
- populate required calculated outputs with unrelated placeholder tables.

Synthetic data is permitted only in isolated tests and fixtures.

Synthetic test data must never be written or presented as production output.

---

## 7. Missing values must preserve meaning

Do not silently convert:

- unavailable data;
- failed calculations;
- unknown values;
- insufficient history

into valid business values such as:

- `0`;
- `False`;
- empty string;
- empty collection;
- arbitrary default category.

`Unavailable`, `not calculated`, and a real numeric or boolean value are semantically different states.

Represent missing or invalid states explicitly according to the approved schema.

---

## 8. Local-data rule

Do not download additional market data or call external market-data APIs unless explicitly authorized for the current task.

Do not consume paid data/API credits without explicit approval.

If required data is unavailable locally, report the missing dependency.

---

## 9. Causal integrity

Causal and retrospective calculations must remain explicitly separated.

A causal feature at time `t` may use only information available at time `t`.

Never leak into causal calculations:

- future bars;
- final leg endpoints;
- final structural classifications;
- future parent/reference relationships;
- information computed only after the observation time.

Retrospective features must be explicitly identified as retrospective in their contract.

Causality requirements require dedicated regression tests.

---

## 10. Type safety

All new Python production code must use explicit type annotations.

Requirements:

- annotate public functions and methods;
- annotate function arguments and return values;
- annotate configuration and dataclass fields;
- avoid untyped dictionaries for structured domain objects;
- prefer `dataclass`, `TypedDict`, `Literal`, `Enum`, `Protocol`, or equivalent explicit structures where appropriate;
- avoid `Any` unless unavoidable and documented.

For a new major pipeline or module set, configure one repository-standard static type checker before implementation proceeds beyond the contract/test stage.

The selected type checker is a development validation tool, not trading/business logic.

Once an approved type checker is recorded in the repository development dependencies, use it consistently.

A type-check failure is a failed validation gate.

Do not report type checking as passed unless the configured checker was actually executed successfully.

---

## 11. Dependency discipline

Do not add new runtime or development dependencies silently.

Prefer the existing repository stack when it can satisfy the requirement correctly.

Dependencies already explicitly approved by the user or already recorded in the repository dependency configuration may be used normally.

Any new dependency not already approved requires explicit user approval before it is added.

If a new dependency is proposed:

- explain why existing dependencies are insufficient;
- distinguish runtime dependencies from development-only validation tools;
- add it explicitly to repository dependency configuration only after approval;
- use a reproducible version constraint consistent with project policy;
- verify that the repository still installs and runs correctly.

Do not install an ad hoc package in the agent environment and leave the repository unaware of that dependency.

---

## 12. Runtime table contracts

`pd.DataFrame -> pd.DataFrame` is not a sufficient contract for important pipeline boundaries.

Every material input/output table must define and validate, as applicable:

- required columns;
- dtypes;
- nullable/non-nullable fields;
- permitted categorical values;
- primary/unique keys;
- timestamp and timezone requirements;
- units;
- row-level invariants;
- provenance requirements.

Validate schemas at pipeline boundaries.

Schema failures must affect QA and final task status.

---

## 13. Time-series integrity

Market time-series inputs and outputs must be checked where applicable for:

- UTC/timezone consistency;
- chronological ordering;
- duplicate timestamps;
- unexpected gaps;
- timeframe alignment;
- impossible OHLC relationships;
- invalid or non-finite numeric values;
- coverage boundaries.

Do not silently repair time-series corruption unless the approved specification explicitly defines the repair.

---

## 14. Tests before implementation

For new specified behavior:

1. identify the requirement;
2. define its acceptance criterion;
3. create or update the corresponding test;
4. verify that the test can detect the absent or broken behavior whenever the requirement is testable;
5. implement the behavior;
6. run the test again.

If a requirement cannot be meaningfully tested, mark it explicitly as `NOT VERIFIED` and explain why.

Tests must verify semantics.

Do not treat the following alone as sufficient verification:

- file existence;
- non-empty output;
- process exit code;
- presence of a column;
- a success field written by the implementation itself.

Use concrete expected values, relationships, or invariants where feasible.

---

## 15. Do not weaken validation to obtain PASS

Do not modify tests, schemas, fixtures, expected values, tolerances, acceptance criteria, validation rules, or QA severity merely to make an implementation pass.

Do not:

- delete a failing test because the implementation does not satisfy it;
- replace a strict expected value with a looser one without justification;
- add `skip`, `xfail`, or equivalent suppression merely to obtain a green suite;
- weaken schema constraints to accommodate incorrect output;
- downgrade a critical validation failure;
- alter a fixture so that it no longer exercises the failing behavior.

If an existing acceptance criterion or test is genuinely incorrect, report the issue and justify the required change before relying on modified validation.

---

## 16. Regression tests for confirmed historical failures

Every confirmed historical bug that can recur must receive a regression test before the affected component is considered fixed.

Known failure classes include:

- CLI option exists but is not functionally used;
- resume/checkpoint functionality is declared but does not actually resume;
- required local package/module is omitted;
- calculated output contains an unrelated intermediate table;
- a required calculation is produced but never reaches its required output;
- source provenance is overwritten;
- spot/futures inputs are accepted but ignored;
- QA errors are added after final QA evaluation;
- final success status is assigned unconditionally;
- integration tests trust the implementation's own success field instead of independently validating outputs.

Do not delete, skip, weaken, or reinterpret a regression test merely to make the suite pass.

---

## 17. Error handling must preserve failures

Do not hide critical failures through broad exception handling.

Do not catch exceptions and silently replace the failed result with:

- `None`;
- empty DataFrames;
- empty files;
- default values;
- warnings;
- successful status.

If an exception is expected and recoverable, handle it explicitly and preserve enough information to distinguish a recovered condition from a valid normal result.

Critical calculation, data-integrity, provenance, schema, or validation failures must remain visible to QA and final status.

---

## 18. Independent validation

Production logic must not be its own sole validator.

Validation must inspect produced artifacts independently of the code path that generated them whenever the requirement is externally observable.

Integration tests must verify actual output semantics and invariants rather than trusting a builder-generated status field.

Final QA status must be derived from validation results.

---

## 19. QA must fail honestly

QA is an independent validation layer.

A critical failure discovered at any stage must affect the final result.

Never:

- assign successful final status unconditionally;
- downgrade a critical failure to permit completion;
- finalize status before all critical checks have been incorporated;
- declare successful completion while known critical failures remain.

Unless the approved specification explicitly defines otherwise, critical validation failure must result in unsuccessful final status and a non-zero process exit code.

---

## 20. Partial completion and coverage

Partial output must never appear indistinguishable from complete output.

If only part of the requested coverage is successfully processed:

- record the completed coverage explicitly;
- record missing or failed partitions explicitly;
- preserve the reason for each missing part;
- ensure final status reflects incomplete coverage;
- do not label the dataset or run as complete.

Coverage metadata must be independently checkable against produced artifacts.

---

## 21. Checkpoints and resume

If a CLI or specification exposes resume/checkpoint functionality, it must be functional and tested.

Checkpoint identity should include sufficient information to prove compatibility, including where applicable:

- input fingerprint;
- configuration hash;
- stage/version identity;
- output/checkpoint checksum.

A valid resume implementation must prove that it:

- reads existing checkpoint state;
- verifies compatibility;
- verifies completed artifacts;
- skips valid completed stages;
- resumes from the correct stage;
- safely rejects stale, incompatible, or corrupted checkpoint state.

Create checkpoints only after a stage has completed and its outputs have passed required validation.

Writing a checkpoint only after the full computation has completed is not resume functionality.

---

## 22. Atomic artifact creation

Any saved file that:

- is consumed by a later pipeline stage;
- is used by QA;
- is used for resume/checkpointing;
- or is a final research/production output

is considered a production artifact.

Do not expose partially written production artifacts or checkpoints as valid completed outputs.

Use a safe write pattern:

`temporary output -> successful write -> validation -> atomic promotion to final output`

A failed or interrupted process must not leave a partial artifact that can later be mistaken for a valid completed result.

---

## 23. Current-run artifact verification

Validation must not accidentally pass against stale artifacts from an earlier run.

Every artifact used to prove current-task success must be demonstrably associated with:

- the current run;
- or a previously validated compatible checkpoint.

Where applicable verify run identifier, input/config fingerprint, timestamps, checksum, or equivalent identity metadata.

Do not report current validation success based solely on an artifact whose origin cannot be established.

---

## 24. Reproducibility

Material research runs must preserve enough metadata to reproduce and audit the result.

Where applicable record:

- input fingerprints;
- configuration hash;
- code version or commit identifier;
- whether the repository had uncommitted changes;
- processing coverage;
- row counts;
- relevant schema/version identifiers;
- run identifier.

If a run occurs from a dirty working tree, record that state explicitly.

Equivalent inputs, configuration, and code should produce deterministic results unless nondeterminism is explicitly required and documented.

---

## 25. Package completeness

Before reporting completion, verify that all local modules imported by user-facing entrypoints and tests exist in the delivered repository state.

Perform a clean import/startup check from the repository environment.

A solution depending on locally created but undelivered modules is incomplete.

---

## 26. Repository integrity

Before reporting completion, inspect repository changes.

At minimum verify that:

- unrelated files were not modified;
- user changes were not overwritten or deleted;
- required new source files are present;
- imported local modules are present;
- temporary files are removed;
- debug artifacts are removed unless explicitly required;
- generated test artifacts are not accidentally treated as source;
- no requested functionality disappeared through unrelated refactoring.

Review the repository diff before final completion reporting.

Do not silently revert or overwrite user-authored changes.

---

## 27. Local Git and remote GitHub policy

Codex may modify local repository files and create local commits within the scope of the current task.

Codex may use local branches or worktrees when useful for isolating tasks or parallel experiments.

The following require explicit user approval for the current action:

- pushing commits to any remote;
- creating or updating a remote branch;
- creating a pull request;
- merging a pull request or branch;
- rebasing or force-updating remote history;
- deleting a remote branch or tag;
- any other operation that changes remote GitHub state.

Do not interpret permission to make local changes or local commits as permission to publish them remotely.

---

## 28. No dead implementation

For each specified calculation, trace:

`input -> calculation -> required output -> validation/test`

If a value is computed but never reaches its specified output, the requirement is not implemented.

If an output is required to contain calculated features, do not populate it with raw or unrelated intermediate data merely to satisfy the filename or schema superficially.

---

## 29. Resource safety

Implementation must be feasible on the intended data volume and environment.

Do not unnecessarily:

- load multi-year high-frequency datasets fully into memory;
- create unbounded concatenations;
- duplicate very large datasets in memory;
- trigger full-history recomputation when a bounded stage is sufficient.

Prefer chunked, streaming, partitioned, or bounded processing where appropriate.

Do not trade correctness for performance.

If resource-safe processing requires an architectural change that affects semantics, report it.

---

## 30. Smoke before expensive full runs

Use the smallest meaningful real-data smoke test before any expensive full historical run.

A smoke test should use representative real local project data where available.

Synthetic unit tests and real-data smoke tests do not substitute for one another.

Do not launch a large run that can consume substantial compute, storage, time, or data credits without explicit approval when a smaller validation run can be performed first.

---

## 31. Validation gates

Before declaring a coding task complete, run all applicable gates:

- clean repository/package import;
- runtime schema validation;
- time-series integrity checks;
- static type checking;
- unit tests;
- regression tests;
- integration tests;
- real-data smoke test;
- QA critical-failure check;
- requirement/compliance verification;
- repository diff review;
- current-run artifact verification.

A gate that was not executed must be reported as `NOT RUN` or `NOT CONFIGURED`.

Never report `PASS` for a check that did not actually run successfully.

---

## 32. Requirement traceability

Large pipeline work must maintain requirement-to-code-to-test traceability.

For each requirement, identify:

- requirement ID;
- responsible module/function;
- affected output;
- test(s);
- implementation status;
- validation status.

Do not mark a requirement complete because a related or neighboring test passes.

---

## 33. Scope discipline

Do not perform unrelated refactors while implementing a defined task.

Do not redesign market logic, structural logic, or upstream data unless the current specification requires it.

Do not silently fix upstream ambiguities.

When an upstream problem is outside scope:

- preserve the source;
- surface the issue in QA;
- continue independent safe work;
- do not corrupt downstream semantics to work around it.

---

## 34. Legacy implementations

Previous failed versions may be inspected for:

- historical bugs;
- file naming;
- input formats;
- upstream structure;
- negative examples.

Do not copy known-broken behavior because it already exists.

When the specification requires independent implementation, do not import or reuse legacy implementation logic unless explicitly allowed.

---

## 35. Completion report

At the end of a coding task, report the actual verification state.

Include:

- files created;
- files modified;
- requirements completed;
- requirements incomplete or blocked;
- validation commands actually executed;
- test results;
- type-check result;
- schema-validation result;
- smoke-test result;
- critical QA failures;
- coverage gaps;
- unresolved ambiguities or missing inputs.

Never hide partial completion behind a general statement such as `implemented successfully`.

If required validation remains incomplete, explicitly state that the task is not fully verified.

---

## 36. Stop conditions

Stop only the affected component and report the issue when:

- a required source is missing;
- a requirement is ambiguous;
- required data coverage is unavailable;
- an independent component cannot be implemented without guessing.

Continue other independent work where safe.

Stop the entire implementation only when:

- authoritative requirements conflict in a way that affects the whole design;
- continuing would require inventing business logic;
- continuing would corrupt downstream semantics;
- a destructive or incompatible change is required but not authorized.
